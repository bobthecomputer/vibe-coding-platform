import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.planner import build_docs_first_plan


class PlannerTests(unittest.TestCase):
    def test_execute_first_objective_starts_with_product_implementation(self) -> None:
        plan = build_docs_first_plan(
            "EXECUTE FIRST, NO PREFLIGHT TESTS. First action must edit product files.",
            docs=["docs/LIVE_UI_DEVELOPMENT.md"],
        )

        self.assertEqual(
            plan.plan_steps[0],
            "Implement smallest vertical slice in product files",
        )
        self.assertNotIn("Review referenced docs", plan.plan_steps[0])


if __name__ == "__main__":
    unittest.main()
