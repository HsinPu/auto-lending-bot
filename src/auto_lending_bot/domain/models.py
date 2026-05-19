from dataclasses import dataclass, field
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
class TransferPreview:
    currency: str
    amount: float
    source: str = "exchange"
    destination: str = "lending"
    external_transfer_id: str = ""


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
    external_offer_id: str = ""
    created_at: str = ""


@dataclass(frozen=True)
class RateCandidate:
    daily_rate: float
    annual_rate: float
    fill_probability: float
    expected_score: float
    meets_min_probability: bool
    selected: bool = False
    selection_role: str = ""
    source: str = ""


@dataclass(frozen=True)
class FillOutcome:
    daily_rate: float
    filled: bool


@dataclass(frozen=True)
class MarketRegime:
    label: str
    trend: str
    volatility: str
    current_daily_rate: float
    short_average_daily_rate: float | None
    long_average_daily_rate: float | None
    sample_count: int
    reason: str


@dataclass(frozen=True)
class ActiveLoan:
    currency: str
    amount: float
    daily_rate: float
    duration_days: int
    external_loan_id: str


@dataclass(frozen=True)
class LendingHistoryEntry:
    currency: str
    amount: float
    daily_rate: float
    duration_days: float
    interest: float
    fee: float
    earned: float
    opened_at: str
    closed_at: str
    external_entry_id: str


@dataclass(frozen=True)
class LendingDecision:
    currency: str
    offers: list[LoanOffer]
    reason: str
    rate_candidates: list[RateCandidate] = field(default_factory=list)
    market_regime: MarketRegime | None = None
    allocation_mode: str = "none"
    allocation_reason: str = "No offers were allocated."
    duration_mode: str = "none"
    duration_reason: str = "No offer duration was selected."

    @property
    def should_lend(self) -> bool:
        return len(self.offers) > 0


@dataclass(frozen=True)
class BotRun:
    id: int
    started_at: datetime
    dry_run: bool
    status: str
