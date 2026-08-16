import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.audit import HashChainAudit
from engine.domain import EvidenceStatus, SearchRequest
from engine.embeddings import HashingEmbedder
from engine.pipeline import IngestionPipeline
from engine.repository import SQLiteRepository
from engine.search import HybridSearchEngine
from engine.storage import FileObjectStore
from helpers import make_document


class PipelineSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.repository = SQLiteRepository(root / "db.sqlite3")
        self.embedder = HashingEmbedder(768)
        self.pipeline = IngestionPipeline(self.repository, FileObjectStore(root / "objects"), self.embedder,
                                          HashChainAudit(root / "audit.jsonl"))

    def tearDown(self):
        self.temp.cleanup()

    def test_ingestion_is_idempotent_and_confirmed(self):
        document, raw = make_document()
        first = self.pipeline.ingest(document, raw, ".txt")
        second = self.pipeline.ingest(document, raw, ".txt")
        self.assertTrue(first.inserted)
        self.assertFalse(second.inserted)
        self.assertEqual(first.status, EvidenceStatus.CONFIRMADO)
        self.assertEqual(self.repository.counts()["documents"], 1)

    def test_hybrid_search_returns_local_and_superior(self):
        local, raw_local = make_document(court="TJGO", case_number="5000000-00.2025.8.09.0001")
        superior, raw_superior = make_document(court="STJ", case_number="REsp 1234567/GO",
            text="Segundo o STJ, mero inadimplemento contratual sem violação da personalidade não configura dano moral.",
            precedent_kind="repetitivo", binding=True)
        irrelevant, raw_irrelevant = make_document(court="TJSP", case_number="1000000-00.2024.8.26.0001",
            text="Discussão exclusivamente tributária sobre ICMS.")
        for document, raw in ((local, raw_local), (superior, raw_superior), (irrelevant, raw_irrelevant)):
            self.pipeline.ingest(document, raw, ".txt")
        hits = HybridSearchEngine(self.repository, self.embedder).search(SearchRequest(
            "mero inadimplemento contratual dano moral", state="GO", branch="civil", limit=5,
        ))
        self.assertEqual([hit.document.court for hit in hits[:2]], ["TJGO", "STJ"])
        self.assertTrue(all(hit.document.provenance.content_sha256 for hit in hits))
        self.assertTrue(any("vinculante" in hit.reasons for hit in hits if hit.document.court == "STJ"))


if __name__ == "__main__": unittest.main()
