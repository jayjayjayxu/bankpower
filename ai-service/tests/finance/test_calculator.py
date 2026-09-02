from __future__ import annotations

import json
import sys
import unittest
from decimal import Decimal, localcontext
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.finance import FinanceCalculator, FinanceInput, ProvenancedValue, RepaymentMethod, SourceType, calculate_max_debt_ratio
from app.finance.validators import FinanceValidationError


def value(number: str | int | float, unit: str, source_type: SourceType = SourceType.ASSUMPTION, source_id: str = "USER") -> ProvenancedValue:
    return ProvenancedValue.of(number, unit, source_type, source_id)


def finance_input(
    *, capex: str = "100", debt_ratio: str = "0.5", interest_rate: str = "0.1",
    term: str = "2", cfads: tuple[str, ...] = ("40", "40"), required: str = "1.2",
) -> FinanceInput:
    return FinanceInput(
        project_id="TEST-PROJECT",
        capex=value(capex, "CNY", SourceType.FACT, "SQL:CAPEX-1"),
        debt_ratio=value(debt_ratio, "RATIO"),
        interest_rate=value(interest_rate, "RATIO"),
        loan_term_years=value(term, "YEAR"),
        repayment_method=RepaymentMethod.EQUAL_PRINCIPAL,
        annual_cfads=tuple(value(item, "CNY", SourceType.ASSUMPTION, f"USER:CFADS-{index}") for index, item in enumerate(cfads, 1)),
        required_min_dscr=value(required, "RATIO"),
    )


class FinanceCalculatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calculator = FinanceCalculator()

    def test_loan_amount_is_capex_times_debt_ratio(self) -> None:
        result = self.calculator.calculate(finance_input())
        self.assertEqual(result.loan_amount, Decimal("50"))

    def test_equal_principal_schedule_matches_hand_calculation(self) -> None:
        result = self.calculator.calculate(finance_input())
        year1, year2 = result.annual_schedule
        self.assertEqual((year1.beginning_balance, year1.principal, year1.interest, year1.debt_service), (Decimal("50"), Decimal("25"), Decimal("5.0"), Decimal("30.0")))
        self.assertEqual((year2.beginning_balance, year2.principal, year2.interest, year2.debt_service), (Decimal("25"), Decimal("25"), Decimal("2.5"), Decimal("27.5")))
        self.assertEqual(sum(item.principal for item in result.annual_schedule), Decimal("50"))

    def test_dscr_min_and_average_match_hand_calculation(self) -> None:
        result = self.calculator.calculate(finance_input())
        with localcontext() as context:
            context.prec = 40
            year1 = Decimal("40") / Decimal("30")
            year2 = Decimal("40") / Decimal("27.5")
            expected_average = (year1 + year2) / Decimal("2")
        self.assertEqual(result.annual_schedule[0].dscr, year1)
        self.assertEqual(result.annual_schedule[1].dscr, year2)
        self.assertEqual(result.min_dscr, year1)
        self.assertEqual(result.avg_dscr, expected_average)

    def test_zero_interest_rate_removes_interest_only(self) -> None:
        result = self.calculator.calculate(finance_input(interest_rate="0"))
        self.assertEqual([item.interest for item in result.annual_schedule], [Decimal("0"), Decimal("0")])
        self.assertEqual([item.debt_service for item in result.annual_schedule], [Decimal("25"), Decimal("25")])
        self.assertEqual(result.min_dscr, Decimal("1.6"))

    def test_zero_debt_has_no_dscr_not_infinite_dscr(self) -> None:
        result = self.calculator.calculate(finance_input(debt_ratio="0"))
        self.assertEqual(result.loan_amount, Decimal("0"))
        self.assertEqual(result.min_dscr, None)
        self.assertTrue(all(item.dscr is None for item in result.annual_schedule))
        self.assertIn("债务比例为 0", result.warnings[0])

    def test_zero_and_negative_cfads_are_calculated_not_silently_coerced(self) -> None:
        zero = self.calculator.calculate(finance_input(cfads=("0", "40")))
        negative = self.calculator.calculate(finance_input(cfads=("-1", "40")))
        self.assertEqual(zero.annual_schedule[0].dscr, Decimal("0"))
        self.assertLess(negative.min_dscr or Decimal("0"), Decimal("0"))
        self.assertTrue(any("零或负数" in item for item in negative.warnings))

    def test_max_debt_ratio_matches_hand_derived_capacity(self) -> None:
        maximum = calculate_max_debt_ratio(finance_input(), resolution=Decimal("0.00000001"))
        # Year 1 binds: 40 / (100 * ratio * (1/2 + 10%)) >= 1.2, so ratio <= 5/9.
        self.assertLess(abs(maximum.max_debt_ratio - (Decimal("5") / Decimal("9"))), Decimal("0.00000002"))
        self.assertLess(abs(maximum.max_loan_amount - (Decimal("500") / Decimal("9"))), Decimal("0.000002"))
        self.assertIsNotNone(maximum.calculation)
        self.assertGreaterEqual(maximum.calculation.min_dscr or Decimal("0"), Decimal("1.2"))

    def test_max_debt_ratio_returns_zero_when_no_positive_debt_is_feasible(self) -> None:
        maximum = calculate_max_debt_ratio(finance_input(cfads=("-1", "-1")))
        self.assertEqual(maximum.max_debt_ratio, Decimal("0"))
        self.assertEqual(maximum.max_loan_amount, Decimal("0"))
        self.assertIn("没有正的债务比例", maximum.warnings[0])

    def test_full_debt_is_returned_when_dscr_constraint_is_met(self) -> None:
        maximum = calculate_max_debt_ratio(finance_input(cfads=("1000", "1000")))
        self.assertEqual(maximum.max_debt_ratio, Decimal("1"))
        self.assertEqual(maximum.max_loan_amount, Decimal("100"))

    def test_invalid_debt_ratio_is_rejected(self) -> None:
        with self.assertRaises(FinanceValidationError):
            self.calculator.calculate(finance_input(debt_ratio="1.01"))

    def test_invalid_term_is_rejected(self) -> None:
        with self.assertRaises(FinanceValidationError):
            self.calculator.calculate(finance_input(term="0", cfads=()))
        with self.assertRaises(FinanceValidationError):
            self.calculator.calculate(finance_input(term="2.5", cfads=("1", "1")))

    def test_missing_or_mismatched_cfads_is_rejected(self) -> None:
        with self.assertRaises(FinanceValidationError):
            self.calculator.calculate(finance_input(cfads=("40",)))

    def test_input_sources_are_preserved_and_derived_result_is_not_reclassified_as_fact(self) -> None:
        result = self.calculator.calculate(finance_input())
        public = result.public_dict()
        self.assertEqual(public["inputs"]["capex"]["source_type"], "FACT")
        self.assertEqual(public["inputs"]["annual_cfads"][0]["source_type"], "ASSUMPTION")
        self.assertEqual(public["results"]["loan_amount"], "50.0")

    def test_baiwangxin_phase_three_gold_case_keeps_facts_and_assumptions_separate(self) -> None:
        cases_path = SERVICE_ROOT / "eval" / "v04_finance_golden_cases.json"
        cases = json.loads(cases_path.read_text(encoding="utf-8"))
        case = next(item for item in cases if item["case_id"] == "BAIWANGXIN-PHASE3-ASSUMPTION-001")
        inputs = case["inputs"]
        capex_provenance = case["input_provenance"]["capex"]
        cfads_provenance = case["input_provenance"]["annual_cfads"]
        calculation = self.calculator.calculate(FinanceInput(
            project_id=case["project_id"],
            capex=value(inputs["capex_cny"], "CNY", SourceType.FACT, capex_provenance["source_id"]),
            debt_ratio=value(inputs["debt_ratio"], "RATIO", SourceType.ASSUMPTION, "SCENARIO:BASE:DEBT_RATIO"),
            interest_rate=value(inputs["interest_rate"], "RATIO", SourceType.ASSUMPTION, "SCENARIO:BASE:INTEREST_RATE"),
            loan_term_years=value(inputs["loan_term_years"], "YEAR", SourceType.ASSUMPTION, "SCENARIO:BASE:LOAN_TERM"),
            repayment_method=RepaymentMethod.EQUAL_PRINCIPAL,
            annual_cfads=tuple(
                value(amount, "CNY", SourceType.ASSUMPTION, f"{cfads_provenance['source_id']}:YEAR-{year}")
                for year, amount in enumerate(inputs["annual_cfads_cny"], 1)
            ),
            required_min_dscr=value(inputs["required_min_dscr"], "RATIO", SourceType.ASSUMPTION, "SCENARIO:BASE:MIN_DSCR"),
        ))
        maximum = calculate_max_debt_ratio(calculation.inputs, resolution=Decimal("0.00000001"))

        self.assertEqual(calculation.loan_amount, Decimal(case["expected"]["loan_amount"]))
        self.assertEqual(calculation.annual_schedule[0].debt_service, Decimal(case["expected"]["year_1_debt_service"]))
        self.assertEqual(calculation.min_dscr, Decimal(case["expected"]["min_dscr"]))
        self.assertLess(abs(maximum.max_debt_ratio - Decimal(case["expected"]["max_debt_ratio"])), Decimal("0.00000002"))
        self.assertEqual(calculation.inputs.capex.source_type, SourceType.FACT)
        self.assertTrue(all(item.source_type == SourceType.ASSUMPTION for item in calculation.inputs.annual_cfads))
        self.assertTrue(any(case["expected"]["warning_contains"] in warning for warning in calculation.warnings))


if __name__ == "__main__":
    unittest.main()
