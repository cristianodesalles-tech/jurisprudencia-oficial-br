import json
import tempfile
import unittest
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.audit import HashChainAudit
from engine.storage import FileObjectStore


class AuditStorageTests(unittest.TestCase):
    def test_hash_chain_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            audit = HashChainAudit(path)
            audit.append("one", {"value": 1}); audit.append("two", {"value": 2})
            self.assertTrue(audit.verify().valid)
            events = path.read_text(encoding="utf-8").splitlines()
            first = json.loads(events[0]); first["payload"]["value"] = 99
            events[0] = json.dumps(first)
            path.write_text("\n".join(events) + "\n", encoding="utf-8")
            self.assertFalse(audit.verify().valid)

    def test_concurrent_append_preserves_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            audit = HashChainAudit(Path(directory) / "audit.jsonl")
            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(lambda value: audit.append("event", {"value": value}), range(50)))
            verification = audit.verify()
            self.assertTrue(verification.valid)
            self.assertEqual(verification.events, 50)

    def test_object_store_is_content_addressed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FileObjectStore(directory)
            first_key, first_hash = store.put_immutable(b"conteudo", "text/plain", ".txt")
            second_key, second_hash = store.put_immutable(b"conteudo", "text/plain", ".txt")
            self.assertEqual((first_key, first_hash), (second_key, second_hash))
            self.assertEqual(store.get(first_key), b"conteudo")
            with self.assertRaises(FileNotFoundError):
                store.get("../fora")


if __name__ == "__main__": unittest.main()
