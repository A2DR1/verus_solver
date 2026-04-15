import unittest

from verus_solver.config import SolverConfig
from verus_solver.solver import AdaptiveState, VerifierGuidedSolver


class AdaptivePlannerTests(unittest.TestCase):
    def test_strategy_sequence_rotates_after_stagnation(self):
        cfg = SolverConfig(verus_path="/tmp/verus")
        solver = VerifierGuidedSolver(cfg)
        st = AdaptiveState(stagnation_rounds=0, strategy_cursor=0)
        seq0 = solver._adaptive_strategy_sequence("overflow", st)
        self.assertEqual(seq0[0], "overflow")

        st.stagnation_rounds = 2
        st.strategy_cursor = 1
        seq1 = solver._adaptive_strategy_sequence("overflow", st)
        self.assertIn("overflow", seq1)
        self.assertGreaterEqual(len(seq1), 2)


if __name__ == "__main__":
    unittest.main()

