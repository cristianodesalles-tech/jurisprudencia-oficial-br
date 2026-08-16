import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.core import Candidate, CaseProfile, LegalReview, finalize_validation, is_official_url, plan_research, validate_candidate


class CoreTests(unittest.TestCase):
    def test_official_domains(self):
        self.assertTrue(is_official_url("https://scon.stj.jus.br/SCON/"))
        self.assertTrue(is_official_url("https://api-publica.datajud.cnj.jus.br/x"))
        self.assertFalse(is_official_url("https://stj.jus.br.example.com/falso"))
        self.assertFalse(is_official_url("https://agregador.example/acordao"))

    def test_plan_has_local_and_superior(self):
        plan = plan_research(CaseProfile(summary="dano moral", branch="civil", defended_side="réu", theses=["mero inadimplemento"] ))
        self.assertEqual(plan["hierarchy"][:2], ["TJGO", "STJ"])
        self.assertGreaterEqual(len(plan["theses"][0]["queries"]), 3)

    def test_full_state_name_is_normalized(self):
        plan = plan_research(CaseProfile(summary="tese", branch="civil", defended_side="réu", state="Goiás"))
        self.assertEqual(plan["hierarchy"][0], "TJGO")

    def test_validation_fails_without_document(self):
        candidate = Candidate(court="STJ", case_number="REsp 123", official_record_url="https://scon.stj.jus.br/x", full_text_url="https://scon.stj.jus.br/y", panel="3ª Turma", rapporteur="Ministro X", judgment_date="2025-01-01", holding="tese", applicable_excerpt="trecho", excerpt_location="p. 2", thesis="tese", outcome="provido")
        self.assertEqual(validate_candidate(candidate)["status"], "NÃO VALIDADO")

    def test_validation_hashes_document(self):
        candidate = Candidate(court="TJGO", case_number="5000000-00.2025.8.09.0001", official_record_url="https://projudi.tjgo.jus.br/x", full_text_url="https://projudi.tjgo.jus.br/y", panel="1ª Câmara", rapporteur="Desembargador X", judgment_date="2025-01-01", holding="tese", applicable_excerpt="trecho", excerpt_location="p. 2", thesis="tese", outcome="desprovido")
        with tempfile.NamedTemporaryFile() as stream:
            stream.write(b"documento oficial simulado"); stream.flush()
            output = validate_candidate(candidate, stream.name)
        self.assertEqual(output["status"], "CONFIRMADO")
        self.assertEqual(len(output["document_sha256"]), 64)

    def test_legal_review_is_required_for_validated_status(self):
        structural = {"status": "CONFIRMADO", "errors": [], "candidate": {}, "document_sha256": "a" * 64}
        review = LegalReview("Advogado revisor", True, True, True, True, True, True, "conferido")
        self.assertEqual(finalize_validation(structural, review)["status"], "VALIDADO")
        review.current_law_verified = False
        self.assertEqual(finalize_validation(structural, review)["status"], "NÃO VALIDADO")


if __name__ == "__main__": unittest.main()
