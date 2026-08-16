import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class McpTests(unittest.TestCase):
    def test_initialize_and_list_tools(self):
        messages = "\n".join([
            json.dumps({"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}),
            json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}),
        ]) + "\n"
        process = subprocess.run(["python3", str(ROOT / "mcp" / "server.py")], input=messages, text=True, capture_output=True, check=True)
        lines = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual(lines[0]["result"]["serverInfo"]["name"], "jurisprudencia-oficial-br")
        self.assertGreaterEqual(len(lines[1]["result"]["tools"]), 5)


if __name__ == "__main__": unittest.main()
