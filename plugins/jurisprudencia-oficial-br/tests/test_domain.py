import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.domain import SearchRequest, chunk_document, normalize_text
from helpers import make_document


class DomainTests(unittest.TestCase):
    def test_normalization_and_stable_id(self):
        document, _ = make_document(text="  Texto\x00  com   espaços. ")
        document.canonicalize()
        first_id = document.id
        self.assertEqual(document.full_text, "Texto com espaços.")
        document.canonicalize()
        self.assertEqual(document.id, first_id)

    def test_chunk_overlap_is_bounded(self):
        document, _ = make_document(text=("Fundamento jurídico aplicável. " * 300))
        document.canonicalize()
        chunks = chunk_document(document, max_chars=500, overlap=50)
        self.assertGreater(len(chunks), 5)
        self.assertTrue(all(0 < len(chunk.text) <= 500 for chunk in chunks))
        self.assertEqual([chunk.ordinal for chunk in chunks], list(range(len(chunks))))

    def test_search_request_rejects_empty_query(self):
        with self.assertRaises(ValueError):
            SearchRequest("   ").normalize()


if __name__ == "__main__": unittest.main()
