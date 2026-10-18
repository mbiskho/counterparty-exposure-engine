import unittest
from xml.etree import ElementTree

from counterparty_exposure import (
    Collateral,
    CounterpartyExposureEngine,
    Trade,
)
from counterparty_exposure.visualization import (
    render_flow_screenshot,
    render_project_screenshot,
)


class CounterpartyExposureEngineTests(unittest.TestCase):
    def test_nets_mtm_and_haircut_collateral_within_netting_set(self) -> None:
        engine = CounterpartyExposureEngine(
            currency="USD",
            trades=[
                Trade("t1", "Bank A", "set-1", "Rates", 150, 1000, 0.02),
                Trade("t2", "Bank A", "set-1", "Rates", -50, 500, 0.02),
            ],
            collateral=[
                Collateral("c1", "Bank A", "set-1", 40, 0.25),
            ],
            limits={"Bank A": 200},
        )

        result = engine.run().counterparties["Bank A"]
        netting_set = result.netting_sets["set-1"]

        self.assertEqual(netting_set.net_mtm, 100)
        self.assertEqual(netting_set.eligible_collateral, 30)
        self.assertEqual(netting_set.current_exposure, 70)
        self.assertEqual(netting_set.pfe_addon, 30)
        self.assertEqual(netting_set.pfe, 100)
        self.assertEqual(result.limit_utilization, 0.35)
        self.assertFalse(result.limit_breached)

    def test_does_not_offset_across_separate_netting_sets(self) -> None:
        engine = CounterpartyExposureEngine(
            currency="USD",
            trades=[
                Trade("positive", "Bank A", "set-1", "Rates", 100, 1000, 0.01),
                Trade("negative", "Bank A", "set-2", "Rates", -90, 1000, 0.01),
            ],
            collateral=[],
            limits={"Bank A": 50},
        )

        result = engine.run().counterparties["Bank A"]

        self.assertEqual(result.net_mtm, 10)
        self.assertEqual(result.current_exposure, 100)
        self.assertTrue(result.limit_breached)

    def test_collateral_cannot_create_negative_exposure(self) -> None:
        engine = CounterpartyExposureEngine(
            currency="USD",
            trades=[Trade("t1", "Bank A", "set-1", "Rates", 20, 100, 0.01)],
            collateral=[Collateral("c1", "Bank A", "set-1", 100, 0)],
            limits={"Bank A": 100},
        )

        result = engine.run().counterparties["Bank A"]

        self.assertEqual(result.current_exposure, 0)
        self.assertEqual(result.pfe, 1)

    def test_rejects_duplicate_ids_unknown_collateral_set_and_missing_limit(self) -> None:
        first_trade = Trade("t1", "Bank A", "set-1", "Rates", 10, 100, 0.01)
        with self.assertRaisesRegex(ValueError, "trade identifiers must be unique"):
            CounterpartyExposureEngine(
                "USD",
                [first_trade, first_trade],
                [],
                {"Bank A": 100},
            )
        with self.assertRaisesRegex(ValueError, "unknown netting set"):
            CounterpartyExposureEngine(
                "USD",
                [first_trade],
                [Collateral("c1", "Bank A", "set-other", 10, 0)],
                {"Bank A": 100},
            )
        with self.assertRaisesRegex(ValueError, "missing limits"):
            CounterpartyExposureEngine("USD", [first_trade], [], {})

    def test_rejects_invalid_haircuts_and_rates(self) -> None:
        with self.assertRaisesRegex(ValueError, "haircut must be less than 1"):
            Collateral("c1", "Bank A", "set-1", 10, 1)
        with self.assertRaisesRegex(ValueError, "cannot exceed 1"):
            Trade("t1", "Bank A", "set-1", "Rates", 10, 100, 1.1)

    def test_generates_valid_white_project_and_flow_screenshots(self) -> None:
        report = CounterpartyExposureEngine(
            "USD",
            [
                Trade("t1", "Bank A", "set-1", "Rates", 150, 1000, 0.02),
                Trade("t2", "Bank B", "set-2", "FX", 80, 500, 0.04),
            ],
            [Collateral("c1", "Bank A", "set-1", 40, 0.1)],
            {"Bank A": 200, "Bank B": 100},
        ).run()

        project = render_project_screenshot(report)
        flow = render_flow_screenshot(report)

        self.assertIn('fill="#ffffff"', project)
        self.assertIn("Current exposure by counterparty", project)
        self.assertIn('fill="#ffffff"', flow)
        self.assertIn("From trade ledger to counterparty exposure", flow)
        self.assertIn("Current exposure by netting set", flow)
        ElementTree.fromstring(project)
        ElementTree.fromstring(flow)


if __name__ == "__main__":
    unittest.main()
