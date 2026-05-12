from auto_lending_bot.domain.models import LoanApplication
from auto_lending_bot.domain.services import evaluate_application


def test_evaluate_application_approves_reasonable_application() -> None:
    decision = evaluate_application(
        LoanApplication(applicant_name="Alice", requested_amount=100_000, annual_income=50_000)
    )

    assert decision.approved is True


def test_evaluate_application_rejects_over_limit_application() -> None:
    decision = evaluate_application(
        LoanApplication(applicant_name="Alice", requested_amount=300_000, annual_income=50_000)
    )

    assert decision.approved is False
    assert decision.reason == "Requested amount is too high."
