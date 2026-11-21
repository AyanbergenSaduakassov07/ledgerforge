"""Scripted demo of the eight pitch points (MASTER_SPEC §21). Offline, deterministic.

    uv run python -m ledgerforge.walkthrough [--seed 2006]

The truth shown in step 4 is the trusted-runner view (regenerated from the seed), never the agent's.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from typing import Any

from ledgerforge.agents.flag_all import FlagAllPolicy
from ledgerforge.agents.oracle import OraclePolicy
from ledgerforge.agents.reconciler import ReconcilerPolicy
from ledgerforge.benchmark.trajectory import run_episode
from ledgerforge.contracts.schemas import ScenarioConfig
from ledgerforge.env.env import AuditEnv
from ledgerforge.sim.episode import generate_episode

log = logging.getLogger("ledgerforge.walkthrough")
CONFIG = {"interactions": {"duplicate_with_allocation": 1}, "industry": "construction"}


def _say(title: str, *lines: str) -> None:
    log.info("\n== %s", title)
    for line in lines:
        log.info("   %s", line)


def _run(env: AuditEnv, policy: Any, seed: int, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    return run_episode(env, policy, seed, cfg)


def _score(records: list[dict[str, Any]]) -> str:
    r = records[-1]["report"]
    return (
        f"reward={records[-1]['reward']:+.3f}  tp={r['tp']} fp={r['fp']} fn={r['fn']}  "
        f"F1={r['f1']:.2f}  inspection_steps={r['inspection_steps']}"
    )


def _relationship(public: Any) -> list[str]:
    pay = next(p for p in public.payments if p["invoice_refs"])
    inv_id = pay["invoice_refs"][0]["invoice_id"]
    inv = next(i for i in public.invoices if i["invoice_id"] == inv_id)
    rows = [r for r in public.ledger if r["invoice_id"] == inv_id]
    out = [
        f"invoice {inv['doc_id']} ({inv_id}) {inv['entity_id']} "
        f"{inv['total_minor']} {inv['currency']} issued {inv['issued_at']}",
    ]
    out += [
        f"  ledger {r['row_id']} acct {r['account']} Dr {r['debit_minor']} Cr {r['credit_minor']}"
        f"{'  (payment ' + r['payment_id'] + ')' if r['payment_id'] else ''}"
        for r in rows
    ]
    out.append(
        f"payment {pay['doc_id']} ({pay['payment_id']}) {pay['amount_minor']} {pay['currency']} "
        f"refs {[ref['invoice_id'] for ref in pay['invoice_refs']]}"
    )
    return out


def walkthrough(seed: int) -> int:
    public, truth = generate_episode(seed, ScenarioConfig.from_dict(CONFIG))
    m = public.manifest
    _say(
        "1. A fictional company is generated",
        f"episode {m['episode_id']}  industry={CONFIG['industry']}  base={m['base_currency']}",
        f"period {m['period_start']}..{m['period_end']}  counts {json.dumps(m['counts'])}",
        "amounts are integer minor units; every journal balances",
        "an independent auditor re-derived all labels before release",
    )
    _say("2. Records and their business relationships", *_relationship(public))

    env = AuditEnv("train")
    try:
        rec = _run(env, ReconcilerPolicy(), seed, CONFIG)
        tools = Counter(r["action"]["tool"] for r in rec)
        findings = rec[-1]["action"]["args"]["findings"]
        _say(
            "3. A rule-based agent investigates through the 5 tools only",
            f"policy=reconciler  steps={len(rec)}  tool use {dict(tools)}",
        )
        _say(
            "4. The injected interacting discrepancy (trusted-runner view)",
            *(
                f"{i.type}: {list(i.affected_ids)} {i.expected_amount_minor} {i.currency}"
                for i in truth.issues
            ),
        )
        _say(
            "5. Evidence-backed submission",
            *(
                f"{f['type']}: ids={f['affected_ids']} amount={f['claimed_amount_minor']} "
                f"{f['currency']} evidence={f['evidence_ids']}"
                for f in findings
            )
            or ("(no findings submitted)",),
        )
        _say("6. Reward computed by the separate evaluator process", _score(rec))

        flag = _run(env, FlagAllPolicy(), seed, CONFIG)
        oracle = _run(env, OraclePolicy(truth), seed, CONFIG)
        _say(
            "7. Attack and upper bound on the same episode",
            f"flag-all : {_score(flag)}",
            f"oracle   : {_score(oracle)}  (submits the truth; not an ordinary agent)",
        )

        salted = {**CONFIG, "id_salt": "demo", "order_salt": "demo"}
        twin = _run(env, ReconcilerPolicy(), seed, salted)
        same = twin[-1]["reward"] == rec[-1]["reward"]
        _say(
            "8. Same problem after renaming every id and shuffling every table",
            f"episode {twin[0]['episode_id']} (was {m['episode_id']})",
            f"reconciler: {_score(twin)}",
            f"reward identical to step 6: {same}",
        )
    finally:
        env.close()
    return 0 if same else 1


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="LedgerForge eight-point demo walkthrough")
    ap.add_argument("--seed", type=int, default=2006)
    return walkthrough(ap.parse_args(argv).seed)


if __name__ == "__main__":
    raise SystemExit(main())
