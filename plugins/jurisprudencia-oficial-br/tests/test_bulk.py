import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.bulk import BulkImporter, RecordMapping, UnsafeArchive, safe_zip_members
from engine.domain import SourceRole
from engine.embeddings import HashingEmbedder
from engine.pipeline import IngestionPipeline
from engine.repository import SQLiteRepository
from engine.storage import FileObjectStore


class BulkTests(unittest.TestCase):
    def test_zip_traversal_is_rejected(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("../escape.json", "[]")
        with self.assertRaises(UnsafeArchive):
            list(safe_zip_members(buffer.getvalue()))

    def test_jsonl_import_is_idempotent(self):
        records = [
            {"numeroProcesso":"REsp 1/GO","ementa":"Mero inadimplemento contratual não causa dano moral automaticamente em situação comum."},
            {"numeroProcesso":"REsp 2/GO","ementa":"A responsabilidade civil exige demonstração do dano e do nexo de causalidade no caso concreto."},
        ]
        payload = "\n".join(json.dumps(item, ensure_ascii=False) for item in records).encode()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); repository = SQLiteRepository(root / "db.sqlite")
            pipeline = IngestionPipeline(repository, FileObjectStore(root / "objects"), HashingEmbedder())
            mapping = RecordMapping("stj-open-data", "https://dadosabertos.web.stj.jus.br/export.jsonl", "STJ", SourceRole.DISCOVERY)
            importer = BulkImporter(pipeline, mapping)
            first = importer.import_file("stj.jsonl", payload); second = importer.import_file("stj.jsonl", payload)
            self.assertEqual(first["inserted"], 2)
            self.assertEqual(second["duplicates"], 2)
            self.assertEqual(repository.counts()["documents"], 2)


if __name__ == "__main__": unittest.main()
