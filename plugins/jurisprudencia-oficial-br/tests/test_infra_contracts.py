import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


class InfrastructureContracts(unittest.TestCase):
    def test_migration_has_required_integrity_and_search_indexes(self):
        sql = (ROOT / "infra" / "migrations" / "001_init.sql").read_text(encoding="utf-8").lower()
        for fragment in ("create extension if not exists vector", "unique", "search_vector", "using gin", "using hnsw", "content_sha256", "audit_events"):
            self.assertIn(fragment, sql)

    def test_compose_does_not_expose_databases(self):
        compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn('"127.0.0.1:${API_PORT:-8080}:8080"', compose)
        postgres_section = compose.split("  postgres:", 1)[1].split("  redis:", 1)[0]
        redis_section = compose.split("  redis:", 1)[1].split("  minio:", 1)[0]
        self.assertNotIn("ports:", postgres_section)
        self.assertNotIn("ports:", redis_section)

    def test_manifests_are_valid_json(self):
        for path in (
            ROOT / ".codex-plugin" / "plugin.json",
            ROOT / ".claude-plugin" / "plugin.json",
            ROOT / ".mcp.json",
            REPO / ".agents" / "plugins" / "marketplace.json",
            REPO / ".claude-plugin" / "marketplace.json",
        ):
            self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)

    def test_claude_marketplace_is_self_contained_and_cache_safe(self):
        marketplace = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        entry = marketplace["plugins"][0]
        self.assertEqual(entry["name"], "jurisprudencia-oficial-br")
        self.assertEqual((REPO / entry["source"]).resolve(), ROOT.resolve())
        self.assertTrue((ROOT / ".claude-plugin" / "plugin.json").is_file())
        self.assertTrue((ROOT / "skills" / "pesquisar-jurisprudencia-oficial" / "SKILL.md").is_file())
        mcp = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["jurisprudencia-oficial-br"]
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", " ".join(mcp["args"]))
        self.assertIn("${CLAUDE_PLUGIN_DATA}", mcp["env"]["STATE_DIR"])
        codex_manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(codex_manifest["mcpServers"]["jurisprudencia-oficial-br"]["args"], ["mcp/server.py"])

    def test_public_install_commands_match_current_clients(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        self.assertIn("codex plugin add jurisprudencia-oficial-br@jurisprudencia-oficial-br", readme)
        self.assertNotIn("codex plugin install", readme)
        self.assertIn("claude plugin marketplace add cristianodesalles-tech/jurisprudencia-oficial-br", readme)
        self.assertIn("claude plugin install jurisprudencia-oficial-br@jurisprudencia-oficial-br", readme)

    def test_research_is_isolated_from_quota_providers(self):
        skill = (ROOT / "skills" / "pesquisar-jurisprudencia-oficial" / "SKILL.md").read_text(encoding="utf-8")
        command = (ROOT / "commands" / "pesquisar-jurisprudencia.md").read_text(encoding="utf-8")
        self.assertIn("Isolamento obrigatório de provedores", skill)
        self.assertIn("ERRO_DE_ROTEAMENTO_EXTERNO", skill)
        self.assertIn('matcher: "mcp__claude_ai_jusratio__.*"', skill)
        self.assertIn("exit 2", skill)
        self.assertIn("Não invoque JurisRatio", command)

        configured = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))["sources"]
        self.assertTrue(configured)
        self.assertTrue(all(source["authority"] in {"official", "primary"} for source in configured))
        forbidden = ("jurisratio", "jusbrasil")
        for source in configured:
            identity = f'{source["id"]} {source["base_url"]}'.lower()
            self.assertFalse(any(provider in identity for provider in forbidden))

    def test_api_fails_closed_and_protects_operational_routes(self):
        source = (ROOT / "engine" / "api.py").read_text(encoding="utf-8")
        self.assertIn('docs_url=None, redoc_url=None', source)
        self.assertIn('if not configured:', source)
        self.assertIn('HTTP_503_SERVICE_UNAVAILABLE', source)
        for route in ('/health/ready', '/metrics', '/v1/search', '/v1/ingestions'):
            declaration = source.split(f'"{route}"', 1)[1].split("\n\n", 1)[0]
            self.assertIn('Depends(require_api_key)', declaration)

    def test_container_runs_unprivileged_with_one_api_worker(self):
        dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("USER appuser", dockerfile)
        self.assertIn('"--workers", "1"', dockerfile)
        self.assertNotIn("USER root", dockerfile)


if __name__ == "__main__": unittest.main()
