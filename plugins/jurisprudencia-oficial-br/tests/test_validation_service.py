import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.audit import HashChainAudit
from engine.domain import EvidenceStatus
from engine.embeddings import HashingEmbedder
from engine.pipeline import IngestionPipeline
from engine.repository import SQLiteRepository
from engine.storage import FileObjectStore
from engine.validation import LegalValidationService, ValidationChecklist
from helpers import make_document


class ValidationServiceTests(unittest.TestCase):
    def test_only_complete_review_promotes_to_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); repository = SQLiteRepository(root / "db.sqlite")
            audit = HashChainAudit(root / "audit.jsonl")
            pipeline = IngestionPipeline(repository, FileObjectStore(root / "objects"), HashingEmbedder(), audit)
            document, raw = make_document(); result = pipeline.ingest(document, raw, ".txt")
            service = LegalValidationService(repository, audit)
            checklist = ValidationChecklist("Advogado responsável", True, True, True, True, True, True, "Conferido")
            reviewed = service.review(result.document_id, checklist)
            self.assertEqual(reviewed["status"], "VALIDADO")
            self.assertEqual(repository.get_document(result.document_id).status, EvidenceStatus.VALIDADO)
            self.assertTrue(audit.verify().valid)

    def test_incomplete_review_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); repository = SQLiteRepository(root / "db.sqlite")
            pipeline = IngestionPipeline(repository, FileObjectStore(root / "objects"), HashingEmbedder())
            document, raw = make_document(); result = pipeline.ingest(document, raw, ".txt")
            checklist = ValidationChecklist("Revisor", True, True, True, False, True, True)
            reviewed = LegalValidationService(repository).review(result.document_id, checklist)
            self.assertEqual(reviewed["status"], "NÃO VALIDADO")
            self.assertIn("current_law_verified", reviewed["missing"])


if __name__ == "__main__": unittest.main()
