"""Frozen shared contracts (Gate 0).

Change only via an interface-change proposal in docs/DECISIONS.md.

Everything that crosses an ownership boundary (simulator -> environment -> evaluator -> agents)
is a plain JSON-compatible dict described here. Dataclasses are used only where an object never
leaves one side of the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

SCHEMA_VERSION = "1.0.0"
GENERATOR_VERSION = "0.1.0"

# --- Error types (official four) -------------------------------------------------------------
DUPLICATE_INVOICE = "duplicate_invoice"
PAYMENT_ALLOCATION = "payment_allocation"
FX_RATE = "fx_rate"
REPORTING_PERIOD = "reporting_period"
ERROR_TYPES = (DUPLICATE_INVOICE, PAYMENT_ALLOCATION, FX_RATE, REPORTING_PERIOD)

# Interaction scenarios (two required)
DUPLICATE_WITH_ALLOCATION = "duplicate_with_allocation"
FX_WITH_PERIOD = "fx_with_period"
INTERACTIONS = (DUPLICATE_WITH_ALLOCATION, FX_WITH_PERIOD)

# --- Environment limits (official section 04/05) ---------------------------------------------
MAX_STEPS = 100
MAX_PAGE = 50
MAX_FINDINGS = 30
MAX_EVIDENCE = 10
MAX_EXPLANATION = 1000
MAX_AFFECTED = 10
EPISODE_TIME_LIMIT_S = 60.0
CALC_MAX_CHARS = 256

# Matcher tolerance: |abs(claimed) - expected| <= this many minor units of the finding currency.
AMOUNT_TOLERANCE_MINOR = 1

TOOLS = ("list_records", "get_record", "get_document", "calculator", "submit")
TABLES = ("ledger", "invoices", "payments", "fx")
# Primary key used by get_record for each table.
TABLE_KEYS = {"ledger": "row_id", "invoices": "invoice_id", "payments": "payment_id", "fx": "fx_id"}

# --- Public record field order (official section 03) -----------------------------------------
LEDGER_FIELDS = (
    "row_id",
    "timestamp",
    "account",
    "debit_minor",
    "credit_minor",
    "currency",
    "entity_id",
    "invoice_id",
    "payment_id",
)
INVOICE_FIELDS = (
    "doc_id",
    "invoice_id",
    "entity_id",
    "issued_at",
    "due_at",
    "currency",
    "total_minor",
    "line_items",
)
PAYMENT_FIELDS = ("doc_id", "payment_id", "timestamp", "currency", "amount_minor", "invoice_refs")
FX_FIELDS = ("date", "source_currency", "target_currency", "rate")

# Currency minor-unit exponents.
CURRENCY_EXPONENTS = {"KZT": 2, "USD": 2, "EUR": 2, "RUB": 2, "CNY": 2, "JPY": 0, "KWD": 3}

# Ledger accounts (code + name, exact strings appear in ledger.csv).
ACC_BANK = "1010 Bank"
ACC_INVENTORY = "1300 Inventory"
ACC_EQUIPMENT = "1500 Equipment"
ACC_ACCUM_DEPR = "1590 Accumulated Depreciation"
ACC_AP = "2100 Accounts Payable"
ACC_ADVANCES = "2190 Supplier Advances (Unapplied)"
ACC_PAYROLL_PAYABLE = "2300 Payroll Payable"
ACC_MATERIALS = "5100 Materials Expense"
ACC_SUBCONTRACT = "5200 Subcontractor Services"
ACC_RENT = "5300 Rent and Leases"
ACC_UTILITIES = "5400 Utilities"
ACC_PAYROLL = "6100 Payroll Expense"
ACC_DEPRECIATION = "6500 Depreciation"
ACC_BANK_FEES = "6800 Bank Charges"
ACC_FX = "7600 FX Difference"


def fx_id(date: str, source: str, target: str) -> str:
    """Record key for an fx.csv row; also the evidence id for that rate."""
    return f"{date}:{source}:{target}"


# --- Scenario configuration -------------------------------------------------------------------
DIFFICULTIES = ("basic", "intermediate", "advanced", "expert")
INDUSTRIES = ("industrial_procurement", "construction", "manufacturing", "retail_services")
DEFAULT_INVOICES = {"basic": 30, "intermediate": 50, "advanced": 70, "expert": 100}


@dataclass(frozen=True)
class ScenarioConfig:
    """Input to reset(seed, config). Unknown keys are rejected so typos cannot silently pass."""

    industry: str = "industrial_procurement"
    difficulty: str = "intermediate"
    base_currency: str = "KZT"
    n_invoices: int | None = None  # None -> DEFAULT_INVOICES[difficulty]
    faults: dict[str, int] = field(default_factory=dict)  # error type -> count (standalone)
    interactions: dict[str, int] = field(default_factory=dict)  # interaction -> count
    distractors: bool = True
    # Metamorphic transforms (benign): rename every id / reorder every table.
    id_salt: str | None = None
    order_salt: str | None = None
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ScenarioConfig:
        data = dict(data or {})
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        cfg = cls(**data)
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.industry not in INDUSTRIES:
            raise ValueError(f"industry must be one of {INDUSTRIES}")
        if self.difficulty not in DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {DIFFICULTIES}")
        if self.base_currency not in CURRENCY_EXPONENTS:
            raise ValueError(f"base_currency must be one of {sorted(CURRENCY_EXPONENTS)}")
        if self.n_invoices is not None and not 20 <= self.n_invoices <= 150:
            raise ValueError("n_invoices must be in 20..150")
        for key, n in self.faults.items():
            if key not in ERROR_TYPES or not isinstance(n, int) or n < 0:
                raise ValueError(f"bad fault entry {key}={n}")
        for key, n in self.interactions.items():
            if key not in INTERACTIONS or not isinstance(n, int) or n < 0:
                raise ValueError(f"bad interaction entry {key}={n}")
        if self.total_errors() > 12:
            raise ValueError("at most 12 errors per episode")

    def total_errors(self) -> int:
        return sum(self.faults.values()) + 2 * sum(self.interactions.values())

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


# --- Private truth ----------------------------------------------------------------------------
@dataclass(frozen=True)
class TruthIssue:
    issue_id: str
    type: str
    affected_ids: tuple[str, ...]  # canonical doc ids, sorted
    expected_amount_minor: int  # always > 0, base currency
    currency: str
    allowed_evidence_sets: tuple[tuple[str, ...], ...]  # any one set, fully included, suffices

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "type": self.type,
            "affected_ids": list(self.affected_ids),
            "expected_amount_minor": self.expected_amount_minor,
            "currency": self.currency,
            "allowed_evidence_sets": [list(s) for s in self.allowed_evidence_sets],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TruthIssue:
        return cls(
            issue_id=d["issue_id"],
            type=d["type"],
            affected_ids=tuple(d["affected_ids"]),
            expected_amount_minor=int(d["expected_amount_minor"]),
            currency=d["currency"],
            allowed_evidence_sets=tuple(tuple(s) for s in d["allowed_evidence_sets"]),
        )


@dataclass(frozen=True)
class PublicEpisode:
    """Everything an agent may ever see. Tables are lists of dicts in official field order."""

    manifest: dict[str, Any]
    policy: dict[str, Any]
    ledger: list[dict[str, Any]]
    invoices: list[dict[str, Any]]
    payments: list[dict[str, Any]]
    fx: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest,
            "policy": self.policy,
            "ledger": self.ledger,
            "invoices": self.invoices,
            "payments": self.payments,
            "fx": self.fx,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PublicEpisode:
        return cls(
            **{k: d[k] for k in ("manifest", "policy", "ledger", "invoices", "payments", "fx")}
        )


@dataclass(frozen=True)
class PrivateTruthBundle:
    """Evaluator-only. Never crosses into the agent process."""

    episode_id: str
    issues: tuple[TruthIssue, ...]
    provenance: dict[str, Any]  # generation history: seed, config, mutations, counterfactuals

    def truth_dict(self) -> dict[str, Any]:
        return {"episode_id": self.episode_id, "issues": [i.to_dict() for i in self.issues]}


# --- Agent side -------------------------------------------------------------------------------
class AgentPolicy(Protocol):
    """Baseline adapters implement this. act() receives the latest observation only."""

    name: str

    def reset(self, observation: dict[str, Any]) -> None: ...

    def act(self, observation: dict[str, Any]) -> dict[str, Any]: ...
