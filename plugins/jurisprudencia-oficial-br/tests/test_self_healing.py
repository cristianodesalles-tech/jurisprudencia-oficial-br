import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.self_healing import CircuitState, ResilientExecutor, SourceCircuit


class SelfHealingTests(unittest.TestCase):
    def test_transient_failure_recovers_without_opening_circuit(self):
        circuit = SourceCircuit("stj")
        calls = {"count": 0}
        def operation():
            calls["count"] += 1
            if calls["count"] < 2: raise TimeoutError("temporário")
            return "ok"
        self.assertEqual(ResilientExecutor(circuit, 3).run(operation, (TimeoutError,)), "ok")
        self.assertEqual(circuit.state, CircuitState.CLOSED)

    def test_repeated_failure_opens_circuit(self):
        circuit = SourceCircuit("stf", failure_threshold=1)
        with self.assertRaises(TimeoutError):
            ResilientExecutor(circuit, 1).run(lambda: (_ for _ in ()).throw(TimeoutError("falha")), (TimeoutError,))
        self.assertEqual(circuit.state, CircuitState.OPEN)
        with self.assertRaises(RuntimeError):
            ResilientExecutor(circuit).run(lambda: "não executar", (TimeoutError,))


if __name__ == "__main__": unittest.main()
