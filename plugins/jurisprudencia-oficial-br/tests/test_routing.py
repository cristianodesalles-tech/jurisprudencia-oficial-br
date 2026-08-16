import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.routing import CourtRouter


class RoutingTests(unittest.TestCase):
    def test_goias_hierarchies(self):
        router = CourtRouter()
        self.assertEqual(router.route("civil", "GO")["local"], ["TJGO"])
        self.assertEqual(router.route("trabalhista", "GO")["local"], ["TRT18"])
        self.assertEqual(router.route("federal", "GO")["local"], ["TRF1"])

    def test_sao_paulo_labor_is_ambiguous_by_design(self):
        self.assertEqual(CourtRouter().route("trabalho", "SP")["local"], ["TRT2", "TRT15"])

    def test_datajud_allowlist_excludes_stf(self):
        indexes = CourtRouter().datajud_indexes()
        self.assertIn("tjgo", indexes); self.assertIn("trt18", indexes); self.assertNotIn("stf", indexes)


if __name__ == "__main__": unittest.main()
