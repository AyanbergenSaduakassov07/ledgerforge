"""ledgerforge CLI: generate episodes, audit public files, run the scripted demo."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from ledgerforge.agents.oracle import OraclePolicy
from ledgerforge.benchmark.trajectory import replay, run_episode, write_jsonl
from ledgerforge.contracts.schemas import ScenarioConfig
from ledgerforge.env.env import AuditEnv
from ledgerforge.sim.episode import generate_episode
from ledgerforge.sim.export import read_public, write_private, write_public
from ledgerforge.verification.auditor import audit

log = logging.getLogger("ledgerforge")
DEMO_CONFIG = {"faults": {"duplicate_invoice": 1}}


def _config(text: str | None) -> dict:
    return json.loads(text) if text else {}


def cmd_generate(a: argparse.Namespace) -> int:
    cfg = _config(a.config)
    for seed in range(a.seed, a.seed + a.count):
        public, truth = generate_episode(seed, ScenarioConfig.from_dict(cfg))
        name = public.manifest["episode_id"]
        write_public(public, Path(a.out) / name)
        write_private(truth, Path(a.private) / name)
        log.info(
            "%s seed=%d issues=%d ledger=%d", name, seed, len(truth.issues), len(public.ledger)
        )
    return 0


def cmd_audit(a: argparse.Namespace) -> int:
    result = audit(read_public(Path(a.path)).to_dict())
    json.dump({"issues": result.issues, "violations": result.violations}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 1 if result.violations else 0


def cmd_demo(a: argparse.Namespace) -> int:
    """Scripted oracle on duplicate-invoice episodes; logs and replays each trajectory."""
    cfg = _config(a.config) or DEMO_CONFIG
    out = Path(a.out)
    out.unlink(missing_ok=True)
    env = AuditEnv("train")
    try:
        for seed in range(a.seed, a.seed + a.count):
            _, truth = generate_episode(seed, ScenarioConfig.from_dict(cfg))
            records = run_episode(env, OraclePolicy(truth), seed, cfg)
            if replay(env, records) != records:
                log.error("replay mismatch for seed %d", seed)
                return 1
            write_jsonl(out, records)
            rep = records[-1]["report"]
            log.info(
                "seed=%d episode=%s reward=%.3f tp=%d fp=%d fn=%d replay=identical",
                seed,
                records[-1]["episode_id"],
                records[-1]["reward"],
                rep["tp"],
                rep["fp"],
                rep["fn"],
            )
    finally:
        env.close()
    log.info("trajectories -> %s", out)
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(prog="ledgerforge")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="write public + private episode files")
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--count", type=int, default=1)
    g.add_argument("--config", help="ScenarioConfig as JSON")
    g.add_argument("--out", default="episodes/generated")
    g.add_argument("--private", default="private/generated")
    g.set_defaults(fn=cmd_generate)
    au = sub.add_parser("audit", help="independent audit of a public episode directory")
    au.add_argument("path")
    au.set_defaults(fn=cmd_audit)
    d = sub.add_parser("demo", help="scripted oracle run with trajectory log and replay")
    d.add_argument("--seed", type=int, default=0)
    d.add_argument("--count", type=int, default=3)
    d.add_argument("--config")
    d.add_argument("--out", default="outputs/trajectories/demo.jsonl")
    d.set_defaults(fn=cmd_demo)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
