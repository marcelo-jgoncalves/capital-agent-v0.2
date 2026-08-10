#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_FILE = ROOT / "config" / "policy.json"
CRITICAL_FILE = ROOT / "config" / "critical_decisions.json"
APPROVALS_PENDING_DIR = ROOT / "approvals" / "pending"
LEDGER_FILE = ROOT / "data" / "ledger.csv"
DECISIONS_DIR = ROOT / "journal" / "decisions"
ACTIVE_EXPERIMENTS_DIR = ROOT / "experiments" / "active"
ARCHIVE_EXPERIMENTS_DIR = ROOT / "experiments" / "archive"
SYSTEM_GOVERNANCE_FILE = ROOT / "config" / "system_governance.json"
SYSTEM_CHANGES_DIR = ROOT / "journal" / "system_changes"
APPROVALS_DIR = ROOT / "approvals"
CONTEXT_DIR = ROOT / "context"
CURRENT_STATE_FILE = CONTEXT_DIR / "CURRENT_STATE.md"
INDEXES_DIR = CONTEXT_DIR / "indexes"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def append_index(index_name: str, entry: dict) -> None:
    """Append a summary entry to context/indexes/<index_name>.json.

    Indexes are a derived cache for fast lookup; the journal/experiment/approval
    files under journal/, experiments/ and approvals/ remain the source of truth.
    Missing index files are tolerated (context/ may not exist in older checkouts).
    """
    path = INDEXES_DIR / f"{index_name}.json"
    if not path.parent.exists():
        return
    try:
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except json.JSONDecodeError:
        existing = []
    existing.append(entry)
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_policy() -> dict:
    return json.loads(POLICY_FILE.read_text(encoding="utf-8"))


def load_critical_policy() -> dict:
    return json.loads(CRITICAL_FILE.read_text(encoding="utf-8"))


def classify_critical(amount: float = 0.0, max_loss: float = 0.0, recurring: bool = False, new_business_model: bool = False, external_obligations: bool = False, legal_uncertainty: bool = False, public_representation: bool = False, new_financial_write_access: bool = False, policy_relaxation: bool = False):
    cfg = load_critical_policy()
    reasons = []
    if amount > float(cfg["noncritical_live_money_threshold_brl"]): reasons.append("live amount exceeds non-critical threshold")
    if max_loss > float(cfg["noncritical_max_loss_threshold_brl"]): reasons.append("maximum plausible loss exceeds non-critical threshold")
    if recurring and cfg["recurring_commitment_is_always_critical"]: reasons.append("recurring commitment")
    if new_business_model and external_obligations and cfg["new_business_model_with_external_obligations_is_always_critical"]: reasons.append("new business model creates external obligations")
    if legal_uncertainty and cfg["legal_or_regulatory_uncertainty_is_always_critical"]: reasons.append("legal/regulatory uncertainty")
    if public_representation and cfg["public_representation_of_owner_is_always_critical"]: reasons.append("public representation of owner")
    if new_financial_write_access and cfg["new_write_financial_credentials_are_always_critical"]: reasons.append("new financial write authority")
    if policy_relaxation and cfg["policy_relaxation_is_always_critical"]: reasons.append("policy relaxation")
    return bool(reasons), reasons


def load_system_governance() -> dict:
    return json.loads(SYSTEM_GOVERNANCE_FILE.read_text(encoding="utf-8"))


def read_ledger() -> list[dict]:
    with LEDGER_FILE.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cash_balance() -> float:
    balance = 0.0
    for row in read_ledger():
        amount = float(row["amount_brl"])
        typ = row["type"]
        if typ in {"capital_in", "revenue", "sell", "refund"}:
            balance += amount
        elif typ in {"expense", "buy", "fee", "tax", "capital_out"}:
            balance -= amount
        elif typ == "adjustment":
            balance += amount
    return round(balance, 2)


def current_equity_floor() -> float:
    # Phase 0: only verified ledger cash is counted.
    # Later adapters may add marked positions/receivables.
    return cash_balance()


def append_ledger(typ: str, category: str, amount: float, description: str, reference: str):
    if amount < 0:
        raise ValueError("amount must be non-negative; direction is determined by type")
    with LEDGER_FILE.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([now_iso(), typ, category, f"{amount:.2f}", description, reference])


def policy_check_proposal(amount: float) -> list[str]:
    policy = load_policy()
    equity = current_equity_floor()
    cash = cash_balance()
    issues = []

    if amount <= 0:
        issues.append("amount must be greater than zero")
        return issues

    max_single = equity * float(policy["max_single_live_allocation_pct_equity"])
    if amount > max_single:
        issues.append(f"amount exceeds single-allocation limit ({max_single:.2f} BRL)")

    min_reserve = equity * float(policy["min_cash_reserve_pct_equity"])
    if cash - amount < min_reserve:
        issues.append(
            f"allocation would breach minimum cash reserve "
            f"({min_reserve:.2f} BRL)"
        )

    if policy["execution_tier"] == 0 and policy["live_execution_enabled"]:
        issues.append("invalid policy: tier 0 cannot have live execution enabled")

    return issues


def cmd_status(_args):
    policy = load_policy()
    ledger = read_ledger()
    print(json.dumps({
        "currency": policy["currency"],
        "execution_tier": policy["execution_tier"],
        "live_execution_enabled": policy["live_execution_enabled"],
        "ledger_entries": len(ledger),
        "verified_cash_brl": cash_balance(),
        "verified_equity_floor_brl": current_equity_floor(),
        "max_single_live_allocation_brl": round(
            current_equity_floor() * policy["max_single_live_allocation_pct_equity"], 2
        ),
        "minimum_cash_reserve_brl": round(
            current_equity_floor() * policy["min_cash_reserve_pct_equity"], 2
        ),
    }, indent=2))


def cmd_propose(args):
    issues = policy_check_proposal(args.amount)
    decision_id = f"DEC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = DECISIONS_DIR / f"{decision_id}.md"

    status = "POLICY_BLOCKED" if issues else "PROPOSAL_ONLY"
    body = f"""# Decision: {args.title}

- Date/time: {now_iso()}
- Decision ID: {decision_id}
- Category: {args.category}
- Capital requested: BRL {args.amount:.2f}
- Current verified equity floor: BRL {current_equity_floor():.2f}
- Status: {status}

## Opportunity

{args.title}

## Mechanism of return

{args.thesis}

## Evidence

To be completed before material execution.

## Why this could fail

To be completed.

## Alternatives considered

Must include doing nothing / low-risk benchmark before approval.

## Policy checks

"""
    if issues:
        for issue in issues:
            body += f"- [ ] BLOCKED: {issue}\n"
    else:
        body += "- [x] Initial numeric allocation checks passed.\n"
        body += "- [ ] Evidence review completed.\n"
        body += "- [ ] Human gate checked.\n"

    body += """
## Decision

Proposal only. Phase 0 does not permit live execution.

## Kill condition

Define before any live test.

## Review condition

Complete evidence and red-team review.
"""
    path.write_text(body, encoding="utf-8")
    append_index("decisions", {
        "id": decision_id,
        "date": now_iso(),
        "title": args.title,
        "category": args.category,
        "amount_brl": round(args.amount, 2),
        "status": status,
        "path": f"journal/decisions/{decision_id}.md",
    })
    print(json.dumps({
        "decision_id": decision_id,
        "status": status,
        "path": str(path),
        "issues": issues,
    }, indent=2))


def cmd_record(args):
    allowed = {"capital_in", "revenue", "sell", "refund", "expense", "buy",
               "fee", "tax", "capital_out", "adjustment"}
    if args.type not in allowed:
        raise SystemExit(f"unsupported ledger type: {args.type}")
    if args.type in {"buy", "expense", "fee", "tax", "capital_out"}:
        if args.amount > cash_balance():
            raise SystemExit("insufficient verified cash")
    append_ledger(args.type, args.category, args.amount, args.description, args.reference)
    print(f"recorded. verified cash: BRL {cash_balance():.2f}")


def cmd_new_experiment(args):
    exp_id = f"EXP-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    issues = policy_check_proposal(args.budget)
    status = "blocked" if issues else "planned"
    data = {
        "id": exp_id,
        "created_at": now_iso(),
        "title": args.title,
        "hypothesis": args.hypothesis,
        "budget_brl": round(args.budget, 2),
        "max_loss_brl": round(args.max_loss, 2),
        "success_metric": args.success_metric,
        "kill_condition": args.kill_condition,
        "status": status,
        "policy_issues": issues,
        "cash_flows": []
    }
    path = ACTIVE_EXPERIMENTS_DIR / f"{exp_id}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    append_index("experiments", {
        "id": exp_id,
        "created_at": data["created_at"],
        "title": args.title,
        "budget_brl": data["budget_brl"],
        "max_loss_brl": data["max_loss_brl"],
        "status": status,
        "path": f"experiments/active/{exp_id}.json",
    })
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_experiments(_args):
    exps = []
    for p in sorted(ACTIVE_EXPERIMENTS_DIR.glob("*.json")):
        exps.append(json.loads(p.read_text(encoding="utf-8")))
    print(json.dumps(exps, indent=2, ensure_ascii=False))




def cmd_system_policy(_args):
    print(json.dumps(load_system_governance(), indent=2))


def cmd_propose_system_change(args):
    governance = load_system_governance()
    change_class = args.change_class.upper()
    allowed_classes = set(governance["autonomous_change_classes"])
    human_classes = set(governance["human_approval_change_classes"])
    prohibited_classes = set(governance["prohibited_change_classes"])

    if change_class not in allowed_classes | human_classes | prohibited_classes:
        raise SystemExit(f"unknown system change class: {change_class}")

    if change_class in prohibited_classes:
        status = "REJECTED_PROHIBITED"
    elif change_class in human_classes:
        status = "PROPOSED_HUMAN_APPROVAL_REQUIRED"
    else:
        status = "PROPOSED_AUTONOMOUSLY_ALLOWED"

    change_id = f"SYS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    SYSTEM_CHANGES_DIR.mkdir(parents=True, exist_ok=True)
    path = SYSTEM_CHANGES_DIR / f"{change_id}.md"
    body = f"""# System Change: {args.title}\n\n- Date/time: {now_iso()}\n- Change ID: {change_id}\n- Change class: {change_class}\n- Status: {status}\n\n## Problem observed\n\n{args.problem}\n\n## Evidence\n\nTo be completed.\n\n## Proposed change\n\n{args.change}\n\n## Expected benefit\n\n{args.benefit}\n\n## New risks introduced\n\nTo be completed.\n\n## Authority impact\n\nMust be explicitly assessed before implementation.\n\n## Rollback plan\n\nRequired before implementation for material changes.\n\n## Validation plan\n\nRun relevant tests/checks and compare before/after behavior.\n\n## Human approval\n\n{'Required before activation.' if change_class in human_classes else 'Not required by class; still subject to canonical policy.'}\n"""
    path.write_text(body, encoding="utf-8")
    append_index("system-changes", {
        "id": change_id,
        "date": now_iso(),
        "title": args.title,
        "class": change_class,
        "status": status,
        "path": f"journal/system_changes/{change_id}.md",
    })
    print(json.dumps({"change_id": change_id, "class": change_class, "status": status, "path": str(path)}, indent=2))



def cmd_classify_decision(args):
    critical, reasons = classify_critical(amount=args.amount, max_loss=args.max_loss, recurring=args.recurring, new_business_model=args.new_business_model, external_obligations=args.external_obligations, legal_uncertainty=args.legal_uncertainty, public_representation=args.public_representation, new_financial_write_access=args.new_financial_write_access, policy_relaxation=args.policy_relaxation)
    print(json.dumps({"critical": critical, "requires_human_authorization": critical, "reasons": reasons}, indent=2))


def cmd_request_approval(args):
    critical, reasons = classify_critical(amount=args.amount, max_loss=args.max_loss, recurring=args.recurring, new_business_model=args.new_business_model, external_obligations=args.external_obligations, legal_uncertainty=args.legal_uncertainty, public_representation=args.public_representation, new_financial_write_access=args.new_financial_write_access, policy_relaxation=args.policy_relaxation)
    if not critical:
        raise SystemExit("Decision is not classified as critical by current machine rules.")
    approval_id = f"APR-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    APPROVALS_PENDING_DIR.mkdir(parents=True, exist_ok=True)
    path = APPROVALS_PENDING_DIR / f"{approval_id}.md"
    lines = ["# Critical Decision Approval Request", "", f"- Approval ID: {approval_id}", f"- Date: {now_iso()}", f"- Proposed action: {args.title}", f"- Category: {args.category}", f"- Capital required: BRL {args.amount:.2f}", f"- Maximum plausible loss: BRL {args.max_loss:.2f}", f"- Recurring commitment: {args.recurring}", "- Status: PENDING", "", "## Criticality reasons"]
    lines += [f"- {r}" for r in reasons]
    lines += ["", "## Why this action", "", args.thesis, "", "## Alternatives", "", "Must include doing nothing and the best known alternative.", "", "## Critic assessment", "", "REQUIRED BEFORE HUMAN AUTHORIZATION.", "", "## Policy checks", "", "REQUIRED BEFORE HUMAN AUTHORIZATION.", "", "## Exact authorization requested", "", "Authorize only the bounded action described above and only within the stated capital/loss limits.", "", "## Human decision", "", "PENDING", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    append_index("approvals", {
        "id": approval_id,
        "date": now_iso(),
        "title": args.title,
        "category": args.category,
        "amount_brl": round(args.amount, 2),
        "max_loss_brl": round(args.max_loss, 2),
        "status": "PENDING",
        "path": f"approvals/pending/{approval_id}.md",
    })
    print(json.dumps({"approval_id": approval_id, "status": "PENDING", "path": str(path), "criticality_reasons": reasons}, indent=2))

def _list_json(dir_path: Path) -> list[dict]:
    if not dir_path.exists():
        return []
    out = []
    for p in sorted(dir_path.glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def _list_md_ids(dir_path: Path) -> list[str]:
    if not dir_path.exists():
        return []
    return sorted(p.stem for p in dir_path.glob("*.md"))


def build_current_state() -> str:
    policy = load_policy()
    equity = current_equity_floor()
    cash = cash_balance()
    ledger = read_ledger()

    active_experiments = _list_json(ACTIVE_EXPERIMENTS_DIR)
    archived_experiments = _list_json(ARCHIVE_EXPERIMENTS_DIR)
    decision_ids = _list_md_ids(DECISIONS_DIR)
    system_change_ids = _list_md_ids(SYSTEM_CHANGES_DIR)
    pending_approval_ids = _list_md_ids(APPROVALS_PENDING_DIR)

    lines = []
    lines.append("# Current State")
    lines.append("")
    lines.append("Generated deterministically by `python src/capital_agent.py update-context`.")
    lines.append("Do not hand-edit; edit the underlying sources (ledger, config, experiments, journal) and regenerate.")
    lines.append("")
    lines.append(f"- Generated at: {now_iso()}")
    lines.append(f"- Repository/policy version: {policy.get('policy_version', 'unknown')}")
    lines.append("- Phase: 0 (research/proposals/simulations only; see `ROADMAP.md`)")
    lines.append("")
    lines.append("## Capital (verified from data/ledger.csv)")
    lines.append("")
    lines.append(f"- Initial capital: BRL {float(policy['initial_capital']):.2f}")
    lines.append(f"- Verified cash: BRL {cash:.2f}")
    lines.append(f"- Verified equity floor (cash only; Phase 0 does not mark other positions): BRL {equity:.2f}")
    lines.append(f"- Capital invested (market/experiment buckets): not yet implemented (no bucket-level ledger breakdown)")
    lines.append(f"- Capital committed (open experiment budgets not yet spent): not yet implemented")
    lines.append(f"- Drawdown from equity high-water mark: not yet implemented (no high-water-mark tracking yet)")
    lines.append(f"- Ledger entries: {len(ledger)}")
    lines.append("")
    lines.append("## Execution tier & limits (config/policy.json)")
    lines.append("")
    lines.append(f"- Execution tier: {policy['execution_tier']}")
    lines.append(f"- Live execution enabled: {policy['live_execution_enabled']}")
    lines.append(f"- Max single live allocation: BRL {equity * float(policy['max_single_live_allocation_pct_equity']):.2f}")
    lines.append(f"- Min cash reserve: BRL {equity * float(policy['min_cash_reserve_pct_equity']):.2f}")
    lines.append(f"- Hard drawdown freeze: {float(policy['hard_drawdown_freeze_pct']) * 100:.0f}% of equity")
    lines.append("")
    lines.append("## Positions")
    lines.append("")
    lines.append("None recorded. Phase 0 has no live execution adapter.")
    lines.append("")
    lines.append("## Active experiments")
    lines.append("")
    if active_experiments:
        for e in active_experiments:
            lines.append(f"- {e.get('id')}: {e.get('title')} — status={e.get('status')}, budget=BRL {e.get('budget_brl')}, max_loss=BRL {e.get('max_loss_brl')}")
    else:
        lines.append("None.")
    lines.append("")
    lines.append("## Archived experiments")
    lines.append("")
    lines.append(f"{len(archived_experiments)} archived." if archived_experiments else "None.")
    lines.append("")
    lines.append("## Pending critical-decision approvals (approvals/pending/)")
    lines.append("")
    if pending_approval_ids:
        for aid in pending_approval_ids:
            lines.append(f"- {aid} — see `approvals/pending/{aid}.md`")
    else:
        lines.append("None.")
    lines.append("")
    lines.append("## Recent decisions (journal/decisions/)")
    lines.append("")
    if decision_ids:
        for did in decision_ids[-10:]:
            lines.append(f"- {did}")
    else:
        lines.append("None recorded yet.")
    lines.append("")
    lines.append("## Recent system changes (journal/system_changes/)")
    lines.append("")
    if system_change_ids:
        for sid in system_change_ids[-10:]:
            lines.append(f"- {sid}")
    else:
        lines.append("None recorded yet.")
    lines.append("")
    lines.append("## Risks")
    lines.append("")
    lines.append("- No live execution adapter exists yet; Phase 0 caps exposure to zero live risk.")
    lines.append("- No historical equity high-water mark is tracked yet, so drawdown cannot be computed.")
    lines.append("")
    lines.append("## Hypotheses")
    lines.append("")
    lines.append("None recorded yet. See `context/knowledge/open-questions.md`.")
    lines.append("")
    lines.append("## Benchmarks")
    lines.append("")
    lines.append("Not yet implemented. See `INVESTMENT_POLICY.md` section 7.")
    lines.append("")
    lines.append("## Data limitations")
    lines.append("")
    lines.append("- No market/macro data feed connected yet (Phase 1 work).")
    lines.append("- Equity floor counts verified ledger cash only; no marked positions or receivables exist yet.")
    lines.append("")
    lines.append("## Next actions (from ROADMAP.md Phase 0)")
    lines.append("")
    lines.append("- Configure the chosen AI execution environment.")
    lines.append("- Run Phase 0 readiness audit (`PHASE0_READINESS_PROMPT.md`).")
    lines.append("- Run first opportunity research cycle.")
    lines.append("")
    lines.append("## References")
    lines.append("")
    lines.append("- `START_HERE.md`, `CONTEXT_MANAGEMENT.md`")
    lines.append("- `AI_OPERATING_MANUAL.md`, `INVESTMENT_POLICY.md`, `CRITICAL_DECISIONS.md`, `EVALUATION_CRITIC_SYSTEM.md`, `SYSTEM_EVOLUTION.md`, `HUMAN_GATES.md`, `ARCHITECTURE.md`, `ROADMAP.md`")
    lines.append("")
    return "\n".join(lines)


def cmd_update_context(_args):
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    content = build_current_state()
    CURRENT_STATE_FILE.write_text(content, encoding="utf-8")
    print(json.dumps({"updated": str(CURRENT_STATE_FILE)}, indent=2))


def build_parser():
    p = argparse.ArgumentParser(description="Capital Agent local control CLI")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("status")
    s.set_defaults(func=cmd_status)

    pr = sub.add_parser("propose")
    pr.add_argument("--title", required=True)
    pr.add_argument("--amount", type=float, required=True)
    pr.add_argument("--category", required=True)
    pr.add_argument("--thesis", required=True)
    pr.set_defaults(func=cmd_propose)

    rec = sub.add_parser("record")
    rec.add_argument("--type", required=True)
    rec.add_argument("--category", required=True)
    rec.add_argument("--amount", type=float, required=True)
    rec.add_argument("--description", required=True)
    rec.add_argument("--reference", required=True)
    rec.set_defaults(func=cmd_record)

    ne = sub.add_parser("new-experiment")
    ne.add_argument("--title", required=True)
    ne.add_argument("--budget", type=float, required=True)
    ne.add_argument("--max-loss", type=float, required=True)
    ne.add_argument("--hypothesis", required=True)
    ne.add_argument("--success-metric", required=True)
    ne.add_argument("--kill-condition", required=True)
    ne.set_defaults(func=cmd_new_experiment)

    ex = sub.add_parser("experiments")
    ex.set_defaults(func=cmd_experiments)

    sp = sub.add_parser("system-policy")
    sp.set_defaults(func=cmd_system_policy)

    sc = sub.add_parser("propose-system-change")
    sc.add_argument("--class", dest="change_class", required=True)
    sc.add_argument("--title", required=True)
    sc.add_argument("--problem", required=True)
    sc.add_argument("--change", required=True)
    sc.add_argument("--benefit", required=True)
    sc.set_defaults(func=cmd_propose_system_change)


    cd = sub.add_parser("classify-decision")
    cd.add_argument("--amount", type=float, default=0.0)
    cd.add_argument("--max-loss", type=float, default=0.0)
    cd.add_argument("--recurring", action="store_true")
    cd.add_argument("--new-business-model", action="store_true")
    cd.add_argument("--external-obligations", action="store_true")
    cd.add_argument("--legal-uncertainty", action="store_true")
    cd.add_argument("--public-representation", action="store_true")
    cd.add_argument("--new-financial-write-access", action="store_true")
    cd.add_argument("--policy-relaxation", action="store_true")
    cd.set_defaults(func=cmd_classify_decision)

    ar = sub.add_parser("request-approval")
    ar.add_argument("--title", required=True)
    ar.add_argument("--category", required=True)
    ar.add_argument("--amount", type=float, default=0.0)
    ar.add_argument("--max-loss", type=float, default=0.0)
    ar.add_argument("--thesis", required=True)
    ar.add_argument("--recurring", action="store_true")
    ar.add_argument("--new-business-model", action="store_true")
    ar.add_argument("--external-obligations", action="store_true")
    ar.add_argument("--legal-uncertainty", action="store_true")
    ar.add_argument("--public-representation", action="store_true")
    ar.add_argument("--new-financial-write-access", action="store_true")
    ar.add_argument("--policy-relaxation", action="store_true")
    ar.set_defaults(func=cmd_request_approval)

    uc = sub.add_parser("update-context")
    uc.set_defaults(func=cmd_update_context)

    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
