from auto_lending_bot.domain.models import LoanApplication, LoanDecision


def evaluate_application(application: LoanApplication) -> LoanDecision:
    if application.requested_amount <= 0:
        return LoanDecision(approved=False, reason="Requested amount must be positive.")

    if application.annual_income <= 0:
        return LoanDecision(approved=False, reason="Annual income must be positive.")

    if application.requested_amount > application.annual_income * 5:
        return LoanDecision(approved=False, reason="Requested amount is too high.")

    return LoanDecision(approved=True, reason="Application passed the initial rule check.")
