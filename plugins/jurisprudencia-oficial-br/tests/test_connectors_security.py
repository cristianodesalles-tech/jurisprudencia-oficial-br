import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.connectors import SourceRegistry, UnsafeURL, validate_official_url
from engine.repository import PostgresRepository


class ConnectorSecurityTests(unittest.TestCase):
    def test_only_official_https_hosts_are_allowed(self):
        self.assertEqual(validate_official_url("https://scon.stj.jus.br/SCON/", resolve_dns=False), "https://scon.stj.jus.br/SCON/")
        for unsafe in (
            "http://scon.stj.jus.br/", "https://stj.jus.br.evil.example/", "https://127.0.0.1/",
            "https://user:password@scon.stj.jus.br/",
        ):
            with self.subTest(unsafe=unsafe), self.assertRaises(UnsafeURL):
                validate_official_url(unsafe, resolve_dns=False)

    def test_source_registry_separates_discovery_and_validation(self):
        registry = SourceRegistry(ROOT / "config" / "sources.json")
        self.assertFalse(registry.get("datajud")["validation_capability"])
        self.assertIn("tjgo-juris", {item["id"] for item in registry.validation_sources()})

    def test_vector_serialization_has_no_sql_tokens(self):
        literal = PostgresRepository._vector_literal([0.1, -0.2, 1.0])
        self.assertEqual(literal, "[0.1,-0.2,1]")
        self.assertNotIn(";", literal)


if __name__ == "__main__": unittest.main()
