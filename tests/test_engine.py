"""Phase 1 regression tests — stdlib unittest, no third-party runner needed.

    python -m unittest discover -s tests

These pin the behaviour the demo depends on: the flagship margin-call signal,
look-through concentration, the managed-vs-custody distinction, exclusion
breaches, encumbered-liquidity netting, and the book-wide ranking.
"""

import unittest

from wealth_intelligence.data_model import TODAY, load_book
from wealth_intelligence.detectors import (
    detect_collateral,
    detect_concentration,
    detect_income_suitability,
    detect_liquidity,
    detect_mandate,
)
from wealth_intelligence.engine import analyse_book
from wealth_intelligence.findings import Severity


class LoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = load_book()

    def test_book_shape(self):
        self.assertEqual(len(self.book.clients), 20)
        self.assertEqual(len(self.book.portfolios), 24)
        self.assertEqual(len(self.book.holdings), 1015)
        self.assertEqual(len(self.book.instruments), 62)
        self.assertEqual(len(self.book.transactions), 393)

    def test_fx_hkd_conversion(self):
        # USDHKD ~ 7.81 at TODAY: 7.81 HKD -> ~1 USD.
        usd = self.book.fx.to_usd(781.0, "HKD", TODAY)
        self.assertAlmostEqual(usd, 100.0, delta=1.0)

    def test_fx_eur_conversion(self):
        # EURUSD ~ 1.092 at TODAY: 1 EUR -> ~1.09 USD.
        usd = self.book.fx.to_usd(100.0, "EUR", TODAY)
        self.assertGreater(usd, 105.0)
        self.assertLess(usd, 115.0)


class CollateralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = load_book()

    def test_lau_margin_call_is_severe(self):
        findings = detect_collateral(self.book, "CL-0014")
        self.assertTrue(findings)
        f = findings[0]
        self.assertEqual(f.severity, Severity.SEVERE)
        self.assertLess(f.facts["distance_pts"], 1.0)
        self.assertEqual(f.facts["margin_call_ltv_pct"], 70.0)

    def test_ravi_facility_fires(self):
        findings = detect_collateral(self.book, "CL-0002")
        self.assertTrue(findings)
        self.assertLessEqual(findings[0].facts["distance_pts"], 1.5)

    def test_comfortable_facility_is_quiet(self):
        # CL-0013's Lombard sits around 20% LTV vs a 75% call — nothing to raise.
        self.assertEqual(detect_collateral(self.book, "CL-0013"), [])


class ConcentrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = load_book()

    def test_golden_harbour_lookthrough(self):
        findings = detect_concentration(self.book, "CL-0014")
        gh = next(f for f in findings if f.facts["issuer"] == "Golden Harbour Properties")
        # Stock + perpetual + accumulator must all roll up to one name.
        self.assertGreaterEqual(len(gh.facts["instruments"]), 3)
        self.assertTrue(gh.facts["over_limit"])
        self.assertGreater(gh.facts["direct_pct"], 25.0)

    def test_custody_legacy_is_not_a_breach(self):
        findings = detect_concentration(self.book, "CL-0001")
        bara = next(f for f in findings if f.facts["issuer"] == "Bara Nusantara Energy")
        self.assertTrue(bara.facts["custody_only"])
        self.assertFalse(bara.facts["over_limit"])
        self.assertLessEqual(bara.severity, Severity.HIGH)

    def test_helios_single_name_via_note(self):
        findings = detect_concentration(self.book, "CL-0013")
        helios = next(f for f in findings if f.facts["issuer"] == "Helios Cloud Systems")
        # Stock + the ELN referencing it.
        self.assertGreaterEqual(len(helios.facts["instruments"]), 2)


class MandateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = load_book()

    def test_sustainable_exclusion_breach(self):
        findings = detect_mandate(self.book, "CL-0005")
        exclusions = [f for f in findings if f.category == "exclusion"]
        self.assertTrue(exclusions, "CL-0005 holds excluded names in a sustainable mandate")


class IncomeSuitabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = load_book()

    def test_retiree_impaired_capital_horizon(self):
        # CL-0012 (Cheung, retired): income covers the draw, so this must NOT be
        # framed as a shortfall — it must flag impaired long-dated capital.
        findings = detect_income_suitability(self.book, "CL-0012")
        self.assertTrue(findings)
        f = findings[0]
        self.assertGreaterEqual(f.facts["coverage_ratio"], 1.0)  # income covers draw
        self.assertTrue(f.facts["maturities_beyond_horizon"])    # bond beyond horizon
        self.assertIn("2045", f.headline)
        self.assertEqual(f.severity, Severity.HIGH)

    def test_genuine_shortfall_flags(self):
        # CL-0006 draws far more than the portfolio yields.
        findings = detect_income_suitability(self.book, "CL-0006")
        self.assertTrue(findings)
        self.assertLess(findings[0].facts["coverage_ratio"], 0.9)

    def test_pre_retirement_not_marked_retired(self):
        # CL-0004 is "Pre-retirement" — must not be treated as retired (would
        # otherwise over-rate severity). Branch B severity should be Medium.
        findings = detect_income_suitability(self.book, "CL-0004")
        if findings and findings[0].facts["coverage_ratio"] >= 0.9:
            self.assertEqual(findings[0].severity, Severity.MEDIUM)


class LiquidityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = load_book()

    def test_encumbered_collateral_is_netted(self):
        findings = detect_liquidity(self.book, "CL-0014")
        self.assertTrue(findings)
        facts = findings[0].facts
        self.assertGreater(facts["encumbered_usd"], 0)
        self.assertLess(facts["liquid_free_usd"], facts["liquid_gross_usd"])


class RankingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = load_book()

    def test_lau_is_top_of_the_book(self):
        dossiers = analyse_book(self.book)
        self.assertEqual(dossiers[0].client_id, "CL-0014")
        self.assertEqual(dossiers[0].top_severity, Severity.SEVERE)

    def test_every_client_analysed_without_error(self):
        dossiers = analyse_book(self.book)
        self.assertEqual(len(dossiers), 20)
        for d in dossiers:
            self.assertFalse(
                any(f.category == "engine-error" for f in d.findings),
                f"{d.client_id} raised an engine error",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
