"""Canonical clean financial world: one company, one reporting quarter, balanced books.

Internal model (private): invoices/payments are the public dicts; every ledger row belongs to a
journal {key, kind, doc_id, lines}. Journal grouping is projected publicly by a published rule
(see docs/CONTRACTS.md section "Journal grouping") instead of an extra journal_id column.
"""

from __future__ import annotations

import calendar
import math
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from ledgerforge.contracts.money import (
    FxTable,
    convert,
    fmt_ts,
    local_date,
    parse_offset,
    parse_ts,
)
from ledgerforge.contracts.schemas import (
    ACC_ACCUM_DEPR,
    ACC_ADVANCES,
    ACC_AP,
    ACC_BANK,
    ACC_BANK_FEES,
    ACC_DEPRECIATION,
    ACC_FX,
    ACC_PAYROLL,
    ACC_PAYROLL_PAYABLE,
    CURRENCY_EXPONENTS,
    DEFAULT_INVOICES,
    ScenarioConfig,
)
from ledgerforge.sim import profiles

FOREIGN_POOL = ("USD", "EUR", "CNY", "RUB", "JPY", "KWD")
MIN_LEDGER_ROWS = 200


@dataclass
class World:
    seed: int
    attempt: int
    config: ScenarioConfig
    tz_name: str = ""
    tz: str = ""
    start: str = ""
    end: str = ""
    base: str = ""
    episode_id: str = ""
    vendors: list[dict[str, Any]] = field(default_factory=list)
    fx_rows: list[dict[str, Any]] = field(default_factory=list)
    invoices: list[dict[str, Any]] = field(default_factory=list)
    payments: list[dict[str, Any]] = field(default_factory=list)
    journals: dict[str, dict[str, Any]] = field(default_factory=dict)  # key -> journal
    meta: dict[str, dict[str, Any]] = field(default_factory=dict)  # doc_id -> private facts
    used_ids: set[str] = field(default_factory=set)
    used_seconds: set[str] = field(default_factory=set)
    fx: FxTable | None = None

    def rng(self, phase: str) -> random.Random:
        # str seeds hash with SHA-512: identical across processes and PYTHONHASHSEED values.
        return random.Random(f"ledgerforge:{self.seed}:{self.attempt}:{phase}")

    # --- ids and time ------------------------------------------------------------------------
    def new_id(self, r: random.Random, prefix: str, digits: int = 6) -> str:
        while True:
            value = f"{prefix}{r.randrange(10 ** (digits - 1), 10**digits)}"
            if value not in self.used_ids:
                self.used_ids.add(value)
                return value

    def local_dt(self, day: str, seconds: int) -> datetime:
        d = date.fromisoformat(day)
        return datetime(d.year, d.month, d.day, tzinfo=parse_offset(self.tz)) + timedelta(
            seconds=seconds
        )

    def unique_ts(self, dt: datetime) -> str:
        """Ledger timestamp in the episode offset, unique to the second (journal grouping)."""
        while fmt_ts(dt) in self.used_seconds:
            dt += timedelta(seconds=1)
        self.used_seconds.add(fmt_ts(dt))
        return fmt_ts(dt)

    def rec_day(self, doc_ts: str) -> str:
        return local_date(doc_ts, self.tz)

    # --- postings ----------------------------------------------------------------------------
    def row(
        self,
        r: random.Random,
        ts: str,
        account: str,
        amount: int,
        entity: str | None,
        invoice_id: str | None = None,
        payment_id: str | None = None,
    ) -> dict[str, Any]:
        """amount > 0 -> debit, < 0 -> credit."""
        return {
            "row_id": self.new_id(r, "R", 7),
            "timestamp": ts,
            "account": account,
            "debit_minor": max(amount, 0),
            "credit_minor": max(-amount, 0),
            "currency": self.base,
            "entity_id": entity,
            "invoice_id": invoice_id,
            "payment_id": payment_id,
        }

    def rate_for(self, currency: str, day: str) -> tuple[str | None, str | None]:
        if currency == self.base:
            return None, None
        found = self.fx.effective(currency, self.base, day)
        if found is None:
            raise ValueError(f"no fx rate for {currency} on {day}")
        return found

    def post_invoice(
        self,
        inv: dict[str, Any],
        post_dt: datetime,
        rate_day: str | None = None,
    ) -> dict[str, Any]:
        """Debit expense lines, credit AP. Rate from the recognition date unless overridden."""
        r = self.rng(f"post:{inv['doc_id']}:{len(self.journals)}")
        rate_day = rate_day or self.rec_day(inv["issued_at"])
        fxid, rate = self.rate_for(inv["currency"], rate_day)
        to_base = (
            (lambda a: a)
            if rate is None
            else (lambda a: convert(a, inv["currency"], self.base, rate))
        )
        ap = to_base(inv["total_minor"])
        ts = self.unique_ts(post_dt)
        lines, booked = [], 0
        accounts = self.meta[inv["doc_id"]]["accounts"]
        for i, (item, account) in enumerate(zip(inv["line_items"], accounts, strict=True)):
            last = i == len(accounts) - 1
            amount = ap - booked if last else to_base(item["amount_minor"])
            booked += amount
            lines.append(self.row(r, ts, account, amount, inv["entity_id"], inv["invoice_id"]))
        ap_row = self.row(r, ts, ACC_AP, -ap, inv["entity_id"], inv["invoice_id"])
        lines.append(ap_row)
        journal = {
            "key": f"inv:{inv['doc_id']}",
            "kind": "invoice",
            "doc_id": inv["doc_id"],
            "lines": lines,
        }
        self.journals[journal["key"]] = journal
        self.meta[inv["doc_id"]].update(
            ap=-ap_row["credit_minor"] + ap_row["debit_minor"],
            ap_row=ap_row["row_id"],
            rate_fx_id=fxid,
            posted_at=ts,
        )
        return journal

    def ap_relief(self, invoice_doc: str, amount: int) -> int:
        """Published rule: AP relieved proportionally to the invoice's booked base amount."""
        inv = self.doc(invoice_doc)
        booked = -self.meta[invoice_doc]["ap"]  # AP credit, positive for normal invoices
        value = Decimal(amount) * Decimal(booked) / Decimal(inv["total_minor"])
        return int(value.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))

    def post_payment(self, pay: dict[str, Any], entity: str) -> dict[str, Any]:
        r = self.rng(f"post:{pay['doc_id']}:{len(self.journals)}")
        _, rate = self.rate_for(pay["currency"], self.rec_day(pay["timestamp"]))
        to_base = (
            (lambda a: a)
            if rate is None
            else (lambda a: convert(a, pay["currency"], self.base, rate))
        )
        ts = self.unique_ts(parse_ts(pay["timestamp"]).astimezone(parse_offset(self.tz)))
        bank = to_base(pay["amount_minor"])
        lines, applied = [], 0
        for ref in pay["invoice_refs"]:
            relief = self.ap_relief(self.inv_doc(ref["invoice_id"]), ref["amount_minor"])
            applied += relief
            lines.append(
                self.row(r, ts, ACC_AP, relief, entity, ref["invoice_id"], pay["payment_id"])
            )
        remainder = pay["amount_minor"] - sum(ref["amount_minor"] for ref in pay["invoice_refs"])
        if remainder:
            unapplied = to_base(remainder)
            applied += unapplied
            lines.append(self.row(r, ts, ACC_ADVANCES, unapplied, entity, None, pay["payment_id"]))
        if bank != applied:
            lines.append(self.row(r, ts, ACC_FX, bank - applied, entity, None, pay["payment_id"]))
        lines.append(self.row(r, ts, ACC_BANK, -bank, entity, None, pay["payment_id"]))
        journal = {
            "key": f"pay:{pay['doc_id']}",
            "kind": "payment",
            "doc_id": pay["doc_id"],
            "lines": lines,
        }
        self.journals[journal["key"]] = journal
        self.meta[pay["doc_id"]]["entity_id"] = entity
        return journal

    def post_manual(
        self, r: random.Random, dt: datetime, debit: str, credit: str, amount: int, key: str
    ) -> None:
        ts = self.unique_ts(dt)
        lines = [self.row(r, ts, debit, amount, None), self.row(r, ts, credit, -amount, None)]
        self.journals[key] = {"key": key, "kind": "manual", "doc_id": None, "lines": lines}

    # --- lookups -----------------------------------------------------------------------------
    def doc(self, doc_id: str) -> dict[str, Any]:
        for d in self.invoices + self.payments:
            if d["doc_id"] == doc_id:
                return d
        raise KeyError(doc_id)

    def inv_doc(self, invoice_id: str) -> str:
        return next(i["doc_id"] for i in self.invoices if i["invoice_id"] == invoice_id)

    def ledger(self) -> list[dict[str, Any]]:
        return [row for j in self.journals.values() for row in j["lines"]]

    def tagged(self, tag: str) -> list[dict[str, Any]]:
        return [i for i in self.invoices if tag in self.meta[i["doc_id"]]["tags"]]


# --- construction ------------------------------------------------------------------------------
def _sig_rate(value: float) -> str:
    """Decimal string with six significant digits."""
    decimals = max(2, 6 - math.ceil(math.log10(value)))
    return str(Decimal(value).quantize(Decimal(1).scaleb(-decimals)))


def _quarter(r: random.Random) -> tuple[str, str]:
    year, q = r.choice((2025, 2026)), r.randint(1, 4)
    last_month = 3 * q
    end_day = calendar.monthrange(year, last_month)[1]
    return date(year, last_month - 2, 1).isoformat(), date(year, last_month, end_day).isoformat()


def _days(start: str, end: str) -> list[str]:
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    return [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


def _build_fx(w: World, r: random.Random, currencies: list[str]) -> None:
    lo = (date.fromisoformat(w.start) - timedelta(days=21)).isoformat()
    hi = (date.fromisoformat(w.end) + timedelta(days=21)).isoformat()
    business_days = [d for d in _days(lo, hi) if date.fromisoformat(d).weekday() < 5]
    for cur in currencies:
        level = profiles.USD_ANCHOR[w.base] / profiles.USD_ANCHOR[cur] * r.uniform(0.9, 1.1)
        for day in business_days:
            level *= math.exp(r.gauss(0, 0.006))
            w.fx_rows.append(
                {
                    "date": day,
                    "source_currency": cur,
                    "target_currency": w.base,
                    "rate": _sig_rate(level),
                }
            )
    w.fx = FxTable(w.fx_rows)


def _vendors(w: World, r: random.Random, n: int) -> None:
    foreign = [c for c in FOREIGN_POOL if c != w.base]
    fmts = ("INV-{n:05d}", "{p}/{y}/{n:04d}", "SF-{n}", "{p}-{y}-{n:05d}", "No.{n:06d}")
    for i in range(n):
        currency = w.base if i in (2, 3) or (i >= 4 and r.random() < 0.55) else r.choice(foreign)
        name = f"{r.choice(profiles.VENDOR_WORDS)} {r.choice(profiles.VENDOR_SUFFIX)}"
        w.vendors.append(
            {
                "entity_id": w.new_id(r, "V-", 4),
                "name": name,
                "currency": currency,
                "offset": r.choice(profiles.VENDOR_OFFSETS),
                "fmt": r.choice(fmts),
                "prefix": "".join(ch for ch in name if ch.isupper())[:3] or "VN",
                "next_no": r.randint(10, 9000),
            }
        )


def invoice_number(w: World, vendor: dict[str, Any]) -> str:
    vendor["next_no"] += 1
    return vendor["fmt"].format(n=vendor["next_no"], p=vendor["prefix"], y=w.start[:4])


def express(dt: datetime, offset: str) -> str:
    return fmt_ts(dt.astimezone(parse_offset(offset)))


def make_invoice(
    w: World,
    r: random.Random,
    vendor: dict[str, Any],
    issued: datetime,
    lines: list[tuple[dict[str, Any], str]] | None = None,
    tags: tuple[str, ...] = (),
    issued_offset: str | None = None,
) -> dict[str, Any]:
    """Create (not post) an invoice. `lines` reuses existing line items (duplicates, reissues)."""
    if lines is None:
        lines = []
        po = f"PO-{r.randint(1000, 9999)}"
        exp = CURRENCY_EXPONENTS[vendor["currency"]]
        for desc, account, (lo, hi) in r.sample(
            profiles.CATALOG[w.config.industry], r.randint(1, 3)
        ):
            qty = r.randint(1, 3) if hi > 5000 else r.randint(1, 20)
            unit = round(r.uniform(lo, hi) * profiles.USD_ANCHOR[vendor["currency"]], 2)
            unit_minor = int(Decimal(str(unit)).scaleb(exp).quantize(Decimal(1)))
            lines.append(
                (
                    {
                        "description": f"{desc} ({po})",
                        "quantity": qty,
                        "unit_price_minor": unit_minor,
                        "amount_minor": qty * unit_minor,
                    },
                    account,
                )
            )
    items = [dict(item) for item, _ in lines]
    inv = {
        "doc_id": w.new_id(r, "DOC-", 8),
        "invoice_id": invoice_number(w, vendor),
        "entity_id": vendor["entity_id"],
        "issued_at": express(issued, issued_offset or vendor["offset"]),
        "due_at": express(issued + timedelta(days=r.choice((15, 30, 45, 60))), vendor["offset"]),
        "currency": vendor["currency"],
        "total_minor": sum(i["amount_minor"] for i in items),
        "line_items": items,
    }
    w.invoices.append(inv)
    w.meta[inv["doc_id"]] = {
        "accounts": [a for _, a in lines],
        "tags": set(tags),
        "vendor": vendor["entity_id"],
    }
    return inv


def invoice_lines(w: World, inv: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
    return list(zip(inv["line_items"], w.meta[inv["doc_id"]]["accounts"], strict=True))


def make_payment(
    w: World,
    r: random.Random,
    entity: str,
    currency: str,
    when: datetime,
    refs: list[tuple[str, int]],
    amount: int | None = None,
) -> dict[str, Any]:
    pay = {
        "doc_id": w.new_id(r, "DOC-", 8),
        "payment_id": w.new_id(r, "PAY-", 6),
        "timestamp": express(when, r.choice((w.tz, "+00:00"))),
        "currency": currency,
        "amount_minor": amount if amount is not None else sum(a for _, a in refs),
        "invoice_refs": [{"invoice_id": i, "amount_minor": a} for i, a in refs],
    }
    w.payments.append(pay)
    w.meta[pay["doc_id"]] = {"tags": set()}
    w.post_payment(pay, entity)
    return pay


def post_regular(w: World, r: random.Random, inv: dict[str, Any]) -> None:
    issued_local = parse_ts(inv["issued_at"]).astimezone(parse_offset(w.tz))
    post = issued_local + timedelta(hours=r.randint(1, 6))
    if post.date() != issued_local.date():
        post = issued_local + timedelta(minutes=r.randint(1, 20))
    # Distractor: entered a few days later, same period, still valued at the issue-date rate.
    if r.random() < 0.15:
        later = post + timedelta(days=r.randint(1, 6))
        if later.date().isoformat() <= w.end:
            post = later
    if post.date().isoformat() > w.end:  # issued in the last minutes of the period
        post = issued_local
    w.post_invoice(inv, post)


def _random_issue(w: World, r: random.Random) -> datetime:
    return w.local_dt(r.choice(_days(w.start, w.end)), r.randint(8 * 3600, 19 * 3600))


def _distractors(w: World, r: random.Random) -> None:
    base_vendors = [v for v in w.vendors if v["currency"] == w.base]
    # Recurring monthly service: same amount, same vendor, different service month.
    desc, account = profiles.RECURRING[w.config.industry]
    vendor = r.choice(base_vendors)
    amount = (
        int(r.uniform(800, 4000) * profiles.USD_ANCHOR[w.base])
        * 10 ** CURRENCY_EXPONENTS[w.base]
        // 100
        * 100
    )
    for month_start in _days(w.start, w.end):
        if not month_start.endswith("-01"):
            continue
        label = date.fromisoformat(month_start).strftime("%B %Y")
        item = {
            "description": f"{desc} - {label}",
            "quantity": 1,
            "unit_price_minor": amount,
            "amount_minor": amount,
        }
        inv = make_invoice(
            w,
            r,
            vendor,
            w.local_dt(month_start, r.randint(9, 12) * 3600),
            [(item, account)],
            ("recurring",),
        )
        post_regular(w, r, inv)
    # Credit note cancels an invoice; the reissue looks like a duplicate but is legitimate.
    vendor = r.choice(base_vendors)
    issued = w.local_dt(r.choice(_days(w.start, w.end)[:45]), r.randint(9, 17) * 3600)
    original = make_invoice(w, r, vendor, issued, tags=("cn_set",))
    post_regular(w, r, original)
    negated = [
        ({**it, "quantity": -it["quantity"], "amount_minor": -it["amount_minor"]}, acc)
        for it, acc in invoice_lines(w, original)
    ]
    cn = make_invoice(
        w, r, vendor, issued + timedelta(days=r.randint(2, 6)), negated, ("cn_set", "credit_note")
    )
    post_regular(w, r, cn)
    reissue = make_invoice(
        w,
        r,
        vendor,
        issued + timedelta(days=r.randint(7, 12)),
        invoice_lines(w, original),
        ("cn_set", "reissue"),
    )
    post_regular(w, r, reissue)
    # Timezone boundary: local date is inside the period, the vendor's printed date is not.
    late = w.local_dt(w.end, r.randint(21 * 3600, 23 * 3600 + 1800))
    inv = make_invoice(
        w,
        r,
        r.choice(w.vendors),
        late,
        tags=("tz_boundary",),
        issued_offset=r.choice(("+08:00", "+09:00")),
    )
    post_regular(w, r, inv)
    early = w.local_dt(w.start, r.randint(600, 5400))
    inv = make_invoice(
        w,
        r,
        r.choice(w.vendors),
        early,
        tags=("tz_boundary",),
        issued_offset=r.choice(("-05:00", "-03:00")),
    )
    post_regular(w, r, inv)
    # Next-period invoices received early: in invoices.jsonl, correctly not in the ledger.
    for _ in range(r.randint(1, 2)):
        day = (date.fromisoformat(w.end) + timedelta(days=r.randint(1, 10))).isoformat()
        make_invoice(
            w, r, r.choice(w.vendors), w.local_dt(day, r.randint(9, 17) * 3600), tags=("unposted",)
        )


def _payments(w: World, r: random.Random, distractors: bool) -> None:
    payable = [
        i
        for i in w.invoices
        if not w.meta[i["doc_id"]]["tags"] & {"unposted", "credit_note"}
        and not (
            "cn_set" in w.meta[i["doc_id"]]["tags"] and "reissue" not in w.meta[i["doc_id"]]["tags"]
        )
    ]
    r.shuffle(payable)
    split_pool: dict[str, list[dict[str, Any]]] = {}
    for inv in sorted(payable, key=lambda i: i["doc_id"]):
        issued = parse_ts(inv["issued_at"]).astimezone(parse_offset(w.tz))
        when = issued + timedelta(days=r.randint(3, 50), seconds=r.randint(0, 20000))
        if when.date().isoformat() > w.end:
            continue  # paid after the period: still open at period end (not an error)
        roll = r.random()
        foreign = inv["currency"] != w.base
        if roll < 0.45 or (foreign and roll < 0.6):
            make_payment(
                w,
                r,
                inv["entity_id"],
                inv["currency"],
                when,
                [(inv["invoice_id"], inv["total_minor"])],
            )
            w.meta[inv["doc_id"]]["tags"].add("paid")
        elif not foreign and roll < 0.6:
            first = inv["total_minor"] * r.randint(30, 70) // 100
            make_payment(
                w, r, inv["entity_id"], inv["currency"], when, [(inv["invoice_id"], first)]
            )
            w.meta[inv["doc_id"]]["tags"].add("instalment")
            second = when + timedelta(days=r.randint(5, 25))
            if second.date().isoformat() <= w.end:
                make_payment(
                    w,
                    r,
                    inv["entity_id"],
                    inv["currency"],
                    second,
                    [(inv["invoice_id"], inv["total_minor"] - first)],
                )
        elif not foreign and roll < 0.75:
            split_pool.setdefault(inv["entity_id"], []).append(inv)
    for entity, invs in sorted(split_pool.items()):
        for k in range(0, len(invs) - 1, 2):  # one remittance settling two invoices
            pair = invs[k : k + 2]
            latest = max(parse_ts(i["issued_at"]) for i in pair)
            when = latest.astimezone(parse_offset(w.tz)) + timedelta(days=r.randint(2, 10))
            if when.date().isoformat() <= w.end:
                make_payment(
                    w, r, entity, w.base, when, [(i["invoice_id"], i["total_minor"]) for i in pair]
                )
                for i in pair:
                    w.meta[i["doc_id"]]["tags"].add("split")
    if distractors:  # advance payments with no remittance reference: legitimately unapplied
        for _ in range(r.randint(1, 2)):
            vendor = r.choice(w.vendors)
            amount = int(r.uniform(500, 3000) * profiles.USD_ANCHOR[vendor["currency"]]) * (
                10 ** CURRENCY_EXPONENTS[vendor["currency"]]
            )
            make_payment(
                w, r, vendor["entity_id"], vendor["currency"], _random_issue(w, r), [], amount
            )


def _background(w: World, r: random.Random) -> None:
    unit = 10 ** CURRENCY_EXPONENTS[w.base]
    months = [d for d in _days(w.start, w.end) if d.endswith("-01")]
    for m in months:
        payroll = int(r.uniform(40_000, 90_000) * profiles.USD_ANCHOR[w.base]) * unit
        last = date.fromisoformat(m).replace(day=25).isoformat()
        w.post_manual(
            r,
            w.local_dt(last, 18 * 3600),
            ACC_PAYROLL,
            ACC_PAYROLL_PAYABLE,
            payroll,
            f"man:payroll:{m}",
        )
        w.post_manual(
            r,
            w.local_dt(last, 19 * 3600),
            ACC_PAYROLL_PAYABLE,
            ACC_BANK,
            payroll,
            f"man:payout:{m}",
        )
        depr = int(r.uniform(3_000, 9_000) * profiles.USD_ANCHOR[w.base]) * unit
        w.post_manual(
            r, w.local_dt(last, 20 * 3600), ACC_DEPRECIATION, ACC_ACCUM_DEPR, depr, f"man:depr:{m}"
        )
    target = MIN_LEDGER_ROWS + r.randint(0, 40)
    n = 0
    while len(w.ledger()) < target:
        fee = int(r.uniform(5, 60) * profiles.USD_ANCHOR[w.base]) * unit
        w.post_manual(r, _random_issue(w, r), ACC_BANK_FEES, ACC_BANK, fee, f"man:fee:{n}")
        n += 1


def build_world(seed: int, config: ScenarioConfig, attempt: int = 0) -> World:
    w = World(seed=seed, attempt=attempt, config=config, base=config.base_currency)
    r = w.rng("world")
    w.start, w.end = _quarter(r)
    w.tz_name, w.tz = r.choice(profiles.TIMEZONES)
    w.episode_id = f"EP-{r.getrandbits(48):012x}"
    _vendors(w, r, r.randint(7, 12))
    _build_fx(w, r, sorted({v["currency"] for v in w.vendors if v["currency"] != w.base}))
    n = config.n_invoices or DEFAULT_INVOICES[config.difficulty]
    for _ in range(n):
        inv = make_invoice(w, r, r.choice(w.vendors), _random_issue(w, r))
        post_regular(w, r, inv)
    if config.distractors:
        _distractors(w, r)
    _payments(w, r, config.distractors)
    _background(w, r)
    return w
