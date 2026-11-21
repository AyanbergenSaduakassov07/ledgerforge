"""Local Streamlit workspace for investigating and scoring synthetic audits."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from html import escape
from typing import Any
from weakref import finalize

import streamlit as st

from ledgerforge.contracts.schemas import (
    DUPLICATE_WITH_ALLOCATION,
    ERROR_TYPES,
    MAX_EXPLANATION,
    MAX_FINDINGS,
    TABLE_KEYS,
    fx_id,
)
from ledgerforge.contracts.submission import MalformedSubmission, validate_submission
from ledgerforge.env.env import AuditEnv
from ledgerforge.web_strings import RUSSIAN

log = logging.getLogger(__name__)
TABLE_TITLES = {
    "invoices": "Invoices",
    "payments": "Payments",
    "ledger": "Ledger",
    "fx": "FX rates",
}
TABLE_COLUMNS = {
    "invoices": [
        "doc_id",
        "invoice_id",
        "total_minor",
        "currency",
        "issued_at",
        "due_at",
        "entity_id",
    ],
    "payments": ["doc_id", "payment_id", "amount_minor", "currency", "timestamp"],
    "ledger": [
        "row_id",
        "account",
        "debit_minor",
        "credit_minor",
        "currency",
        "timestamp",
        "invoice_id",
        "payment_id",
        "entity_id",
    ],
    "fx": ["fx_id", "rate", "date", "source_currency", "target_currency"],
}
DRAFT_KEYS = ("affected_ids", "amount", "evidence_ids", "explanation")
LOCALIZED_SELECTS = ("scenario", "evidence_table", "finding_type")
FIELD_LABELS = {
    "doc_id": "Document ID",
    "invoice_id": "Invoice ID",
    "payment_id": "Payment ID",
    "row_id": "Row ID",
    "fx_id": "FX ID",
    "entity_id": "Counterparty",
    "issued_at": "Issued",
    "due_at": "Due",
    "currency": "Currency",
    "total_minor": "Total",
    "amount_minor": "Amount",
    "account": "Account",
    "debit_minor": "Debit",
    "credit_minor": "Credit",
    "timestamp": "Timestamp",
    "date": "Date",
    "rate": "Rate",
    "source_currency": "Source currency",
    "target_currency": "Target currency",
}
TABLE_STYLE = """
<style>
.ledger-evidence { max-height: 20rem; overflow: auto; border: 1px solid #d5e0da;
                   border-radius: .5rem; }
.ledger-evidence table { width: 100%; border-collapse: separate; border-spacing: 0;
                         font-size: .875rem; white-space: nowrap; }
.ledger-evidence th { position: sticky; top: 0; background: #edf3ef; color: #172b26;
                      text-align: left; }
.ledger-evidence :is(td, th) { padding: .5rem .65rem; border-bottom: 1px solid #dce6e0; }
.ledger-evidence td[data-number] { text-align: right; font-variant-numeric: tabular-nums; }
</style>
"""


def t(message: str, **values: Any) -> str:
    if st.session_state.get("language") == "ru":
        message = RUSSIAN.get(message, message)
    return message.format(**values)


def select_key(field: str, language: str) -> str:
    return f"{field}_ru" if language == "ru" else field


def switch_language(previous: str) -> None:
    state = st.session_state
    # Streamlit keeps the old display value for an existing selectbox identity.
    for widget in LOCALIZED_SELECTS:
        old_key = select_key(widget, previous)
        if old_key in state:
            state[select_key(widget, state.language)] = state[old_key]


@dataclass
class Audit:
    env: AuditEnv
    observation: dict[str, Any]
    episode_id: str
    remaining: int
    findings: list[dict[str, Any]] = field(default_factory=list)
    pages: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    page_indexes: dict[str, int] = field(default_factory=dict)
    record: tuple[str, str, dict[str, Any]] | None = None
    report: dict[str, Any] | None = None
    truncated: bool = False
    error: str = ""
    draft_error: str = ""

    def run(self, tool: str, **args: Any) -> Any:
        if self.env.done:
            return None
        try:
            obs, _, _, self.truncated, info = self.env.step({"tool": tool, "args": args})
        except RuntimeError:
            log.exception("Audit evaluator failed")
            self.env.close()
            self.error = "The evaluator stopped. Load a new episode to try again."
            return None
        self.remaining = obs["steps_remaining"]
        self.error = "The evaluator could not complete this action." if "error" in obs else ""
        self.report = info.get("report")
        if self.env.done:
            self.env.close()
        return None if self.truncated else obs.get("result")


def load_audit(seed: int, scenario: str) -> None:
    # A person can take time to read evidence. Keep the evaluator's inspection-step limit.
    env = AuditEnv(time_limit_s=float("inf"))
    try:
        interactions = {DUPLICATE_WITH_ALLOCATION: 1} if scenario == "Mixed audit" else {}
        obs, info = env.reset(
            seed, {"industry": "construction", "difficulty": "basic", "interactions": interactions}
        )
    except RuntimeError:
        log.exception("Could not load audit episode")
        env.close()
        st.error(t("The evaluator could not load this episode. Try again."))
        return
    finalize(env, env.evaluator.close)

    if "audit" in st.session_state:
        st.session_state.audit.env.close()
    st.session_state.audit = Audit(env, obs, info["episode_id"], obs["steps_remaining"])
    finding_key = select_key("finding_type", st.session_state.language)
    for key in (*DRAFT_KEYS, "record_id", finding_key, "evidence_filter"):
        st.session_state.pop(key, None)


def page_controls(audit: Audit, table: str, index: int, can_advance: bool) -> None:
    previous, position, following = st.columns([1, 1, 1])
    previous.button(
        t("Previous"),
        key="previous_page",
        disabled=index == 0,
        on_click=audit.page_indexes.update,
        args=({table: index - 1},),
        width="stretch",
    )
    position.caption(t("Page {number}", number=index + 1))
    following.button(
        t("Next"),
        key="next_page",
        disabled=not can_advance,
        on_click=audit.page_indexes.update,
        args=({table: index + 1},),
        width="stretch",
    )


def inspect_record(audit: Audit, table: str, rows: list[dict[str, Any]]) -> None:
    ids = [row[TABLE_KEYS[table]] for row in rows]
    if st.session_state.get("record_id") not in ids:
        st.session_state.pop("record_id", None)
    record_id = st.selectbox(
        t("Record ID"), ids, index=None, placeholder=t("Select a record"), key="record_id"
    )
    if st.button(t("Open record"), key="open_record", disabled=audit.env.done or record_id is None):
        if (record := audit.run("get_record", table=table, id=record_id)) is not None:
            audit.record = (table, record_id, record)
    if audit.record is not None and audit.record[:2] == (table, record_id):
        st.json(audit.record[2], expanded=1)


def show_table(table: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    columns = TABLE_COLUMNS[table]
    query = (
        st.text_input(t("Filter this page"), key="evidence_filter", max_chars=128)
        .strip()
        .casefold()
    )
    visible = (
        [row for row in rows if any(query in str(row[key]).casefold() for key in columns)]
        if query
        else rows
    )
    if not visible:
        st.caption(t("No matching records on this page."))
        return visible
    headers = "".join(f'<th scope="col">{escape(t(FIELD_LABELS[key]))}</th>' for key in columns)
    body = []
    for row in visible:
        cells = []
        for key in columns:
            value = row[key]
            number = " data-number" if isinstance(value, int) else ""
            cells.append(f"<td{number}>{escape('' if value is None else str(value))}</td>")
        body.append(f"<tr>{''.join(cells)}</tr>")
    label = escape(t(TABLE_TITLES[table]), quote=True)
    st.html(
        TABLE_STYLE
        + f'<div class="ledger-evidence" role="region" aria-label="{label}" tabindex="0">'
        f"<table><thead><tr>{headers}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )
    return visible


def evidence(audit: Audit) -> None:
    st.subheader(t("Evidence"), anchor=False)
    labels = {key: t(title) for key, title in TABLE_TITLES.items()}
    table = st.selectbox(
        t("Evidence table"),
        tuple(TABLE_TITLES),
        format_func=labels.__getitem__,
        key=select_key("evidence_table", st.session_state.language),
    )
    pages = audit.pages.setdefault(table, [])
    index = audit.page_indexes.get(table, 0)
    if index == len(pages) and not audit.env.done:
        cursor = pages[-1]["next_cursor"] if pages else None
        if (page := audit.run("list_records", table=table, cursor=cursor)) is not None:
            pages.append(page)
    if index >= len(pages):
        st.caption(t("No inspected pages for this table."))
        return

    page = pages[index]
    rows = page["rows"]
    if table == "fx":
        rows = [
            {"fx_id": fx_id(row["date"], row["source_currency"], row["target_currency"]), **row}
            for row in rows
        ]
    count = audit.observation["tables"][table]["rows"]
    st.caption(
        t("{count:,} records · Amounts are in each row’s currency and minor units", count=count)
    )
    visible = show_table(table, rows)
    can_advance = index + 1 < len(pages) or (page["next_cursor"] is not None and not audit.env.done)
    if index > 0 or can_advance:
        page_controls(audit, table, index, can_advance)
    if visible:
        inspect_record(audit, table, visible)


def split_ids(value: str) -> list[str]:
    return [clean for part in value.split(",") if (clean := part.strip())]


def add_finding(audit: Audit) -> None:
    state = st.session_state
    try:
        amount = int(state.amount)
    except ValueError:
        audit.draft_error = "Enter a whole number for the amount in minor units."
        return
    finding = {
        "type": state[select_key("finding_type", state.language)],
        "affected_ids": split_ids(state.affected_ids),
        "claimed_amount_minor": amount,
        "currency": audit.observation["manifest"]["base_currency"],
        "evidence_ids": split_ids(state.evidence_ids),
        "explanation": state.explanation,
    }
    findings = [*audit.findings, finding]
    try:
        validate_submission(
            {"episode_id": audit.episode_id, "findings": findings}, audit.episode_id
        )
    except MalformedSubmission as exc:
        field = str(exc).split(" ", 1)[0]
        audit.draft_error = {
            "affected_ids": "Use 1–10 document IDs, each up to 64 characters.",
            "evidence_ids": "Use up to 10 evidence IDs, each up to 64 characters.",
        }.get(field, "Check the finding fields and try again.")
        return
    audit.findings = findings
    audit.draft_error = ""
    for key in DRAFT_KEYS:
        state[key] = ""


def score_audit(audit: Audit) -> None:
    if any(st.session_state[key].strip() for key in DRAFT_KEYS):
        add_finding(audit)
        if audit.draft_error:
            return
    audit.run("submit", episode_id=audit.episode_id, findings=audit.findings)


def findings_panel(audit: Audit) -> None:
    st.subheader(t("Findings"), anchor=False)
    currency = audit.observation["manifest"]["base_currency"]
    labels = {key: t(key.replace("_", " ").capitalize()) for key in ERROR_TYPES}
    if not audit.env.done:
        st.selectbox(
            t("Finding type"),
            ERROR_TYPES,
            format_func=labels.__getitem__,
            key=select_key("finding_type", st.session_state.language),
        )
        with st.form("finding"):
            st.text_input(
                t("Document IDs"),
                key="affected_ids",
                placeholder=t("Comma-separated IDs"),
                max_chars=700,
            )
            st.text_input(
                t("Amount in minor units ({currency})", currency=currency),
                key="amount",
                max_chars=21,
            )
            st.text_input(
                t("Evidence IDs"),
                key="evidence_ids",
                placeholder=t("Comma-separated IDs"),
                max_chars=700,
            )
            st.text_area(t("Explanation"), key="explanation", max_chars=MAX_EXPLANATION, height=90)
            st.form_submit_button(
                t("Add finding"),
                key="add_finding",
                on_click=add_finding,
                args=(audit,),
                disabled=len(audit.findings) >= MAX_FINDINGS,
                width="stretch",
            )
            st.form_submit_button(
                t("Score audit"),
                type="primary",
                key="submit_audit",
                width="stretch",
                on_click=score_audit,
                args=(audit,),
            )
        if audit.draft_error:
            st.error(t(audit.draft_error))
    st.caption(t("{count} of {limit} findings", count=len(audit.findings), limit=MAX_FINDINGS))
    for finding in audit.findings:
        category = labels[finding["type"]]
        amount = finding["claimed_amount_minor"]
        with st.expander(
            t(
                "{category} · {amount:,} {currency} minor units",
                category=category,
                amount=amount,
                currency=currency,
            )
        ):
            st.text(", ".join(finding["affected_ids"]))
            if finding["evidence_ids"]:
                st.text(", ".join(finding["evidence_ids"]))
            if finding["explanation"]:
                st.text(finding["explanation"])
    if audit.findings and not audit.env.done:
        st.button(t("Undo last finding"), on_click=audit.findings.pop)


def show_score(audit: Audit) -> None:
    if (report := audit.report) is None:
        return
    with st.container(border=True):
        st.subheader(t("Audit score"), anchor=False)
        if audit.truncated:
            st.warning(t("The step limit was reached. The evaluator scored an empty submission."))
        reward, f1, tp, fp, fn = st.columns(5)
        reward.metric(t("Reward"), f"{report['reward']:.3f}")
        f1.metric("F1", f"{report['f1']:.3f}")
        tp.metric(t("True positives"), report["tp"])
        fp.metric(t("False positives"), report["fp"])
        fn.metric(t("Missed findings"), report["fn"])
        st.caption(t("Inspection steps · {count}", count=report["inspection_steps"]))


def main() -> None:
    st.set_page_config(page_title="LedgerForge", layout="wide")
    with st.sidebar:
        previous = st.session_state.get("language", "en")
        language = st.selectbox(
            "Language / Язык",
            ("en", "ru"),
            format_func={"en": "English", "ru": "Русский"}.__getitem__,
            key="language",
            on_change=switch_language,
            args=(previous,),
        )
        st.header(t("Episode"), anchor=False)
        scenarios = {name: t(name) for name in ("Mixed audit", "Clean books")}
        scenario = st.selectbox(
            t("Scenario"),
            tuple(scenarios),
            format_func=scenarios.__getitem__,
            key=select_key("scenario", language),
        )
        with st.form("episode"):
            seed = st.number_input(
                t("Seed"), value=2006, min_value=0, max_value=2**31 - 1, step=1, key="seed"
            )
            load = st.form_submit_button(t("Load episode"), key="load_episode", width="stretch")
        if load or "audit" not in st.session_state:
            load_audit(seed, scenario)
        if "audit" not in st.session_state:
            st.stop()
        audit = st.session_state.audit
        remaining = st.empty()
        with st.expander(t("Accounting policy")):
            st.json(audit.observation["policy"], expanded=1)

    manifest = audit.observation["manifest"]
    st.title("LedgerForge", anchor=False)
    st.caption(
        t(
            "Construction audit · {start} to {end} · {currency} base currency",
            start=manifest["period_start"],
            end=manifest["period_end"],
            currency=manifest["base_currency"],
        )
    )
    score = st.container()
    evidence_col, findings_col = st.columns([3, 2], gap="medium")
    with evidence_col, st.container(border=True):
        evidence(audit)
    with findings_col, st.container(border=True):
        findings_panel(audit)
    if audit.error:
        st.error(t(audit.error))
    remaining.metric(t("Steps remaining"), audit.remaining)
    with score:
        show_score(audit)


if __name__ == "__main__":
    main()
