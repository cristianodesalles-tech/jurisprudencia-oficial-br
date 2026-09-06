"""Regressão das travas de integridade: nenhum caminho pode carimbar VALIDADO sem prova."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.bulk import BulkImporter, RecordMapping
from engine.domain import EvidenceStatus, SearchRequest, SourceRole
from engine.embeddings import HashingEmbedder
from engine.evidence import EvidenceRuleViolation
from engine.pipeline import IngestionPipeline
from engine.repository import SQLiteRepository
from engine.search import HybridSearchEngine
from engine.storage import FileObjectStore
from engine.validation import LegalValidationService, ReviewerNotIdentified, ValidationChecklist
from engine.assisted import AssistedCapture, AssistedCaptureError
from engine.overruling import SUPERSEDED_PREFIX, OverrulingEntry, OverrulingEntryError, OverrulingRegistry
from helpers import make_confirmable_document, make_document, test_grader

EMENTA = ("RECURSO ESPECIAL. Mero inadimplemento contratual não gera dano moral. "
          "Ementa usada para tentar entrar no acervo como se fosse inteiro teor.")


def build(root: Path) -> tuple[SQLiteRepository, IngestionPipeline]:
    repository = SQLiteRepository(root / "db.sqlite")
    pipeline = IngestionPipeline(repository, FileObjectStore(root / "objects"), HashingEmbedder())
    return repository, pipeline


class EvidenceLockTests(unittest.TestCase):
    def test_lote_de_ementa_nao_vira_inteiro_teor_nem_confirmado(self):
        payload = json.dumps({"numeroProcesso": "REsp 1.111.111/GO", "ementa": EMENTA,
                              "tribunal": "STJ"}, ensure_ascii=False).encode()
        with tempfile.TemporaryDirectory() as directory:
            repository, pipeline = build(Path(directory))
            mapping = RecordMapping("stj-scon", "https://scon.stj.jus.br/SCON/", "STJ", SourceRole.VALIDATION)
            self.assertEqual(mapping.role, SourceRole.DISCOVERY, "lote precisa ser rebaixado a descoberta")
            result = BulkImporter(pipeline, mapping).import_file("lote.jsonl", payload)
            document = repository.get_document(result["document_ids"][0])
            self.assertEqual(document.status, EvidenceStatus.LOCALIZADO)
            self.assertTrue(document.metadata["ementa_only"])
            self.assertEqual(document.ementa, EMENTA)

    def test_fonte_sem_capacidade_de_validacao_nao_confirma(self):
        with tempfile.TemporaryDirectory() as directory:
            _, pipeline = build(Path(directory))
            document, raw = make_confirmable_document(court="TJSP", case_number="1000000-00.2024.8.26.0001")
            result = pipeline.ingest(document, raw, ".txt")
            self.assertEqual(result.status, EvidenceStatus.LOCALIZADO)
            self.assertIn("fonte-nao-registrada", result.evidence_reasons)

    def test_texto_curto_nao_confirma_mesmo_em_fonte_oficial(self):
        with tempfile.TemporaryDirectory() as directory:
            _, pipeline = build(Path(directory))
            document, raw = make_document(court="STJ", case_number="REsp 9/GO")
            result = pipeline.ingest(document, raw, ".txt")
            self.assertEqual(result.status, EvidenceStatus.LOCALIZADO)
            self.assertTrue(any("texto-curto" in reason for reason in result.evidence_reasons))

    def test_agente_nao_assina_a_revisao(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, pipeline = build(Path(directory))
            document, raw = make_confirmable_document(court="STJ", case_number="REsp 3/GO")
            result = pipeline.ingest(document, raw, ".txt")
            self.assertEqual(result.status, EvidenceStatus.CONFIRMADO)
            for nome, oab in (("agente", "GO 59078"), ("Claude Opus", "GO 59078"),
                              ("Ana Paula Ferreira", ""), ("Ana", "GO 59078")):
                with self.assertRaises(ReviewerNotIdentified):
                    LegalValidationService(repository).review(result.document_id, ValidationChecklist(
                        reviewer=nome, reviewer_oab=oab, document_sha256=result.sha256,
                        excerpt_verified=True, majority_reasoning_verified=True, factual_fit_verified=True,
                        current_law_verified=True, adverse_authority_searched=True, metadata_crosschecked=True))

    def test_localizado_nao_e_promovivel_e_hash_precisa_bater(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, pipeline = build(Path(directory))
            fraco, raw_fraco = make_document(court="STJ", case_number="REsp 4/GO")
            localizado = pipeline.ingest(fraco, raw_fraco, ".txt")
            forte, raw_forte = make_confirmable_document(court="STJ", case_number="REsp 5/GO")
            confirmado = pipeline.ingest(forte, raw_forte, ".txt")
            service = LegalValidationService(repository)
            base = dict(reviewer="Ana Paula Ferreira", reviewer_oab="GO 12345",
                        excerpt_verified=True, majority_reasoning_verified=True, factual_fit_verified=True,
                        current_law_verified=True, adverse_authority_searched=True, metadata_crosschecked=True)
            with self.assertRaises(EvidenceRuleViolation):
                service.review(localizado.document_id, ValidationChecklist(document_sha256=localizado.sha256, **base))
            with self.assertRaises(EvidenceRuleViolation):
                service.review(confirmado.document_id, ValidationChecklist(document_sha256="f" * 64, **base))
            promovido = service.review(confirmado.document_id, ValidationChecklist(document_sha256=confirmado.sha256, **base))
            self.assertEqual(promovido["status"], "VALIDADO")

    def test_filtro_de_uf_nao_elimina_tribunal_superior(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, pipeline = build(Path(directory))
            superior, raw = make_confirmable_document(
                court="STJ", case_number="REsp 6/GO",
                text="Segundo o STJ, mero inadimplemento contratual não configura dano moral.")
            superior.state = ""  # acórdão de tribunal superior não tem UF
            pipeline.ingest(superior, raw, ".txt")
            hits = HybridSearchEngine(repository, HashingEmbedder()).search(
                SearchRequest("mero inadimplemento contratual dano moral", state="GO", limit=5))
            self.assertEqual([hit.document.court for hit in hits], ["STJ"])


class AssistedCaptureTests(unittest.TestCase):
    """A conferência humana em portal protegido é o único caminho para TJGO, TRT18 e STF."""

    URL = "https://projudi.tjgo.jus.br/ConsultaJurisprudencia/j/12345/acordao-integral?p=2#trecho"
    TEXTO = ("ACÓRDÃO. APELAÇÃO CÍVEL. " + "Fundamentação integral conferida na tela do portal oficial. " * 40)

    def capture(self, **overrides):
        base = dict(court="TJGO", source_id="tjgo-juris", official_url=self.URL,
                    captured_text=self.TEXTO, raw_content=self.TEXTO.encode("utf-8"),
                    operator="Cristiano de Salles Santos", operator_oab="GO 59078",
                    case_number="5000000-00.2025.8.09.0001", panel="1ª Câmara Cível",
                    judgment_date="2025-04-10", state="GO", branch="civil")
        base.update(overrides)
        return AssistedCapture(**base)

    def test_captura_humana_confirma_fonte_assistida(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, pipeline = build(Path(directory))
            document, raw = self.capture().build()
            result = pipeline.ingest(document, raw, ".html")
            self.assertEqual(result.status, EvidenceStatus.CONFIRMADO)
            stored = repository.get_document(result.document_id)
            self.assertEqual(stored.provenance.source_url, self.URL, "a URL precisa ser guardada verbatim")
            self.assertEqual(stored.metadata["capture_operator_oab"], "GO 59078")

    def test_busca_automatizada_em_fonte_assistida_nao_confirma(self):
        with tempfile.TemporaryDirectory() as directory:
            _, pipeline = build(Path(directory))
            document, raw = make_confirmable_document(court="TJGO")
            result = pipeline.ingest(document, raw, ".txt")
            self.assertEqual(result.status, EvidenceStatus.LOCALIZADO)
            self.assertIn("fonte-assistida-exige-captura-humana-identificada", result.evidence_reasons)

    def test_captura_sem_operador_identificado_e_recusada(self):
        for operador, oab in (("agente", "GO 59078"), ("Cristiano", "GO 59078"),
                              ("Cristiano de Salles Santos", "")):
            with self.assertRaises(ReviewerNotIdentified):
                self.capture(operator=operador, operator_oab=oab)

    def test_captura_fora_de_dominio_oficial_e_recusada(self):
        with self.assertRaises(AssistedCaptureError):
            self.capture(official_url="https://www.jusbrasil.com.br/acordao/12345")


if __name__ == "__main__":
    unittest.main()


class OverrulingTests(unittest.TestCase):
    """O registro de superação é curadoria: sem fonte oficial e curador, não entra."""

    def base(self, **overrides):
        entry = dict(case_number="REsp 1.111.111/GO", court="STJ", status="superado",
                     nota="Tese revista pela Corte Especial.", tema="dano moral",
                     fonte_url="https://scon.stj.jus.br/SCON/doc/9999",
                     curador="Cristiano de Salles Santos", curador_oab="GO 59078")
        entry.update(overrides)
        return entry

    def test_entrada_valida_marca_o_documento(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overruling.json"
            registry = OverrulingRegistry(path)
            registry.add(OverrulingEntry(**self.base(case_number="5000000-00.2025.8.09.0001")))
            document, _ = make_confirmable_document()
            self.assertTrue(registry.annotate(document))
            self.assertEqual(document.metadata["overruling_status"], "superado")
            self.assertTrue(document.title.startswith(SUPERSEDED_PREFIX))
            self.assertTrue(OverrulingRegistry(path).lookup("5000000-00.2025.8.09.0001"))

    def test_fonte_nao_oficial_e_curador_anonimo_sao_recusados(self):
        with self.assertRaises(OverrulingEntryError):
            OverrulingEntry(**self.base(fonte_url="https://www.jusbrasil.com.br/x"))
        with self.assertRaises(OverrulingEntryError):
            OverrulingEntry(**self.base(status="inventado"))
        with self.assertRaises(ReviewerNotIdentified):
            OverrulingEntry(**self.base(curador="agente"))
        with self.assertRaises(ReviewerNotIdentified):
            OverrulingEntry(**self.base(curador_oab=""))

    def test_superado_sai_da_busca_por_padrao(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = OverrulingRegistry(root / "overruling.json")
            registry.add(OverrulingEntry(**self.base(case_number="REsp 7/GO")))
            repository = SQLiteRepository(root / "db.sqlite")
            pipeline = IngestionPipeline(repository, FileObjectStore(root / "objects"), HashingEmbedder(),
                                         grader=test_grader(), overruling=registry)
            document, raw = make_confirmable_document(court="STJ", case_number="REsp 7/GO")
            pipeline.ingest(document, raw, ".txt")
            engine = HybridSearchEngine(repository, HashingEmbedder())
            self.assertEqual(engine.search(SearchRequest("mero inadimplemento contratual", limit=5)), [])
            com_superados = engine.search(SearchRequest("mero inadimplemento contratual", limit=5,
                                                        include_overruled=True))
            self.assertEqual(len(com_superados), 1)
            self.assertEqual(com_superados[0].document.metadata["overruling_status"], "superado")
