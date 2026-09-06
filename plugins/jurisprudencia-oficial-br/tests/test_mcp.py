import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ESSENCIAIS = {
    "plan_research", "search_local_corpus", "get_document", "get_document_chunk",
    "ingest_assisted_capture", "validate_candidate", "finalize_legal_validation",
    "overruling_lookup", "official_source_status", "search_trf1_official",
    "prepare_assisted_search", "corpus_health",
}


def conversa(*mensagens: dict) -> list[dict]:
    entrada = "\n".join(json.dumps(item) for item in mensagens) + "\n"
    processo = subprocess.run(["python3", str(ROOT / "mcp" / "server.py")], input=entrada,
                              text=True, capture_output=True, check=True)
    return [json.loads(linha) for linha in processo.stdout.splitlines()]


class McpTests(unittest.TestCase):
    def test_initialize_e_catalogo(self):
        linhas = conversa({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                          {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual(linhas[0]["result"]["serverInfo"]["name"], "jurisprudencia-oficial-br")
        self.assertEqual(linhas[0]["result"]["protocolVersion"], "2025-06-18", "deve ecoar a versão do cliente")
        ferramentas = linhas[1]["result"]["tools"]
        nomes = [tool["name"] for tool in ferramentas]
        self.assertEqual(len(nomes), len(set(nomes)), "nome de ferramenta duplicado")
        self.assertTrue(ESSENCIAIS.issubset(set(nomes)), ESSENCIAIS - set(nomes))
        for tool in ferramentas:
            self.assertEqual(tool["inputSchema"]["type"], "object")
            self.assertTrue(tool["description"].strip())

    def test_protocolo_nao_derruba_o_servidor(self):
        linhas = conversa({"jsonrpc": "2.0", "method": "notifications/initialized"},
                          {"jsonrpc": "2.0", "id": 1, "method": "ping"},
                          {"jsonrpc": "2.0", "id": 2, "method": "resources/list"},
                          {"jsonrpc": "2.0", "id": 3, "method": "metodo/inexistente"},
                          {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                           "params": {"name": "ferramenta_que_nao_existe", "arguments": {}}},
                          {"jsonrpc": "2.0", "id": 5, "method": "tools/list", "params": {}})
        self.assertEqual(len(linhas), 5, "notificação não responde, o resto responde")
        self.assertEqual(linhas[0]["result"], {})
        self.assertEqual(linhas[1]["result"], {"resources": []})
        self.assertEqual(linhas[2]["error"]["code"], -32601)
        self.assertEqual(linhas[3]["error"]["code"], -32602)
        self.assertIn("tools", linhas[4]["result"])


if __name__ == "__main__":
    unittest.main()
