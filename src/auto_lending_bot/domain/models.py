from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LoanApplication:
    applicant_name: str
    requested_amount: int
    annual_income: int


@dataclass(frozen=True)
class LoanDecision:
    approved: bool
    reason: str


@dataclass(frozen=True)
class CurrencyBalance:
    currency: str
    amount: float


@dataclass(frozen=True)
class LoanOrder:
    currency: str
    amount: float
    daily_rate: float


@dataclass(frozen=True)
class LoanOffer:
    currency: str
    amount: float
    daily_rate: float
    duration_days: int


@dataclass(frozen=True)
class ActiveLoan:
    currency: str
    amount: float
    daily_rate: float
    duration_days: int
    external_loan_id: str


@dataclass(frozen=True)
class LendingDecision:
    currency: str
    offers: list[LoanOffer]
    reason: str

    @property
    def should_lend(self) -> bool:
        return len(self.offers) > 0


@dataclass(frozen=True)
class BotRun:
    id: int
    started_at: datetime
    dry_run: bool
    status: str
