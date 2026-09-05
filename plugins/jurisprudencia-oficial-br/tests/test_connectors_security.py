import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.connectors import SourceRegistry, TRF1SearchConnector, UnsafeURL, validate_official_url
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
        self.assertIn("trf1-cjf", {item["id"] for item in registry.validation_sources()})
        self.assertIn("tjgo-juris", {item["id"] for item in registry.assisted_sources()})

    def test_trf1_parser_keeps_results_unvalidated(self):
        page = '''<div id="item_resultado-7"><span class="label_pontilhada">Tipo</span></tr><tr><td>Acórdão</td>
        <span class="label_pontilhada">Número</span></tr><tr><td>0000001-00.2026.4.01.3400</td>
        <span class="label_pontilhada">Ementa</span></tr><tr><td>RESPONSABILIDADE CIVIL. RECURSO DESPROVIDO.</td>
        <a href="https://arquivo.trf1.jus.br/PesquisaMenuArquivo.asp?p1=1">Acesse</a></div>'''
        item = TRF1SearchConnector.parse(page, 1)[0]
        self.assertEqual(item["status"], "NÃO VALIDADO")
        self.assertEqual(item["court"], "TRF1")

    def test_vector_serialization_has_no_sql_tokens(self):
        literal = PostgresRepository._vector_literal([0.1, -0.2, 1.0])
        self.assertEqual(literal, "[0.1,-0.2,1]")
        self.assertNotIn(";", literal)


if __name__ == "__main__": unittest.main()
