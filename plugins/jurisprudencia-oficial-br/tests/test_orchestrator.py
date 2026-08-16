import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.orchestrator import Attempt, FailureKind, StrategyController


class OrchestratorTests(unittest.TestCase):
    def test_empty_result_broadens_query(self):
        controller = StrategyController()
        controller.record(Attempt("tjgo", '"tese exata"', "exact", "failure", FailureKind.EMPTY))
        self.assertEqual(controller.next_action()["action"], "broaden_query")

    def test_access_control_is_never_bypassed(self):
        controller = StrategyController()
        controller.record(Attempt("portal", "tese", "portal", "failure", FailureKind.ACCESS_CONTROL))
        action = controller.next_action()
        self.assertEqual(action["action"], "stop")
        self.assertEqual(action["reason"], "do_not_bypass_access_control")


if __name__ == "__main__": unittest.main()
