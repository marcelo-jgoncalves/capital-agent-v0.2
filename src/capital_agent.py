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
RESERVE_ASSETS_FILE = ROOT / "data" / "reserve_assets.json"
DECISIONS_DIR = ROOT / "journal" / "decisions"
ACTIVE_EXPERIMENTS_DIR = ROOT / "experiments" / "active"
ARCHIVE_EXPERIMENTS_DIR = ROOT / "experiments" / "archive"
SYSTEM_GOVERNANCE_FILE = ROOT / "config" / "system_governance.json"
SYSTEM_CHANGES_DIR = ROOT / "journal" / "system_changes"
APPROVALS_DIR = ROOT / "approvals"
APPROVALS_ARCHIVE_DIR = ROOT / "approvals" / "archive"
CONTEXT_DIR = ROOT / "context"
CURRENT_STATE_FILE = CONTEXT_DIR / "CURRENT_STATE.md"
INDEXES_DIR = CONTEXT_DIR / "indexes"

EXECUTION_DIR = ROOT / "execution"
HUMAN_REQUESTS_DIR = EXECUTION_DIR / "human_requests"
HR_PENDING_DIR = HUMAN_REQUESTS_DIR / "pending"
HR_COMPLETED_DIR = HUMAN_REQUESTS_DIR / "completed"
HR_EXPIRED_DIR = HUMAN_REQUESTS_DIR / "expired"
HR_CANCELLED_DIR = HUMAN_REQUESTS_DIR / "cancelled"

STATE_DIR = ROOT / "state"
SCHEDULER_STATE_FILE = STATE_DIR / "scheduler_state.json"
PENDING_JOBS_FILE = STATE_DIR / "pending_jobs.json"

# Custody invariant: the Capital Agent must never hold or exercise financial
# write authority. This is enforced in code, not just in prose, so a corrupted
# or maliciously edited config cannot silently flip it. See
# AI_OPERATING_MANUAL.md "Custody invariant" and SYSTEM_EVOLUTION.md Class D.
CUSTODY_INVARIANT_ERROR = (
    "Custody invariant violated: config/policy.json sets "
    "autonomous_financial_execution_permitted=true. This is a hard invariant "
    "that cannot be relaxed by editing configuration. See "
    "AI_OPERATING_MANUAL.md 'Custody invariant' and CRITICAL_DECISIONS.md."
)

ALLOWED_EXECUTION_ACTIONS = {"BUY", "SELL", "TRANSFER", "WITHDRAWAL", "PAYMENT", "OTHER"}
ACTIONS_REQUIRING_HUMAN_CONTROLLED_DESTINATION = {"TRANSFER", "WITHDRAWAL"}


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
    policy = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
    if policy.get("autonomous_financial_execution_permitted", False):
        raise RuntimeError(CUSTODY_INVARIANT_ERROR)
    return policy


def load_critical_policy() -> dict:
    return json.loads(CRITICAL_FILE.read_text(encoding="utf-8"))


def classify_critical(amount: float = 0.0, max_loss: float = 0.0, recurring: bool = False, new_business_model: bool = False, external_obligations: bool = False, legal_uncertainty: bool = False, public_representation: bool = False, new_financial_write_access: bool = False, policy_relaxation: bool = False, new_readonly_financial_adapter: bool = False):
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
    if new_readonly_financial_adapter and cfg.get("new_readonly_financial_adapter_is_always_critical"): reasons.append("new read-only financial data adapter")
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


def load_reserve_assets() -> list[dict]:
    if not RESERVE_ASSETS_FILE.exists():
        return []
    return json.loads(RESERVE_ASSETS_FILE.read_text(encoding="utf-8"))


def reserve_assets_value() -> float:
    """Conservative book value of low-price-risk reserve instruments (e.g.
    Tesouro Selic) held outside cash. Valued at cost/last confirmed execution
    total, never marked up -- accrued yield is intentionally not estimated,
    so this always understates rather than overstates true value. See
    record-reserve-asset / cmd_record_reserve_asset."""
    return round(sum(float(a["book_value_brl"]) for a in load_reserve_assets()), 2)


def current_equity_floor() -> float:
    # Phase 0: verified ledger cash plus conservatively booked reserve
    # instruments (data/reserve_assets.json). Market positions with real
    # price risk are still not marked -- only near-cash reserve instruments
    # recorded via record-reserve-asset, each tied to a completed Human
    # Execution Request so the value traces back to a real, human-confirmed
    # transaction rather than being asserted.
    return round(cash_balance() + reserve_assets_value(), 2)


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
        "autonomous_financial_execution_permitted": policy["autonomous_financial_execution_permitted"],
        "ledger_entries": len(ledger),
        "verified_cash_brl": cash_balance(),
        "reserve_assets_brl": reserve_assets_value(),
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


RECORD_BLOCKED_TYPES = {"buy", "sell", "capital_out"}


def cmd_record(args):
    allowed = {"capital_in", "revenue", "sell", "refund", "expense", "buy",
               "fee", "tax", "capital_out", "adjustment"}
    if args.type not in allowed:
        raise SystemExit(f"unsupported ledger type: {args.type}")
    if args.type in RECORD_BLOCKED_TYPES:
        raise SystemExit(
            f"refused: '{args.type}' represents a real financial execution "
            "(a market position change or money leaving custody) and may "
            "only enter the ledger through the Human Execution Request "
            "lifecycle: `request-execution` then `confirm-execution`. "
            "Direct `record` of this type would let it be entered without "
            "human confirmation, which the custody invariant "
            "(AI_OPERATING_MANUAL.md) does not permit. If this is the "
            "initial funding event or a non-execution bookkeeping entry, "
            "use a type outside {buy, sell, capital_out}."
        )
    if args.type in {"expense", "fee", "tax"}:
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


CUSTODY_RISK_KEYWORDS = (
    "place_order", "placeorder", "send_order", "sendorder", "auto-execute",
    "autoexecute", "autonomous execution", "broker api", "exchange api",
    "write access", "write-capable", "trading api", "withdraw(", "transfer(",
    "buy(", "sell(",
)


def cmd_propose_system_change(args):
    governance = load_system_governance()
    change_class = args.change_class.upper()
    allowed_classes = set(governance["autonomous_change_classes"])
    human_classes = set(governance["human_approval_change_classes"])
    prohibited_classes = set(governance["prohibited_change_classes"])

    if change_class not in allowed_classes | human_classes | prohibited_classes:
        raise SystemExit(f"unknown system change class: {change_class}")

    # Self-declaration safety net: the --enables-autonomous-financial-execution
    # flag only protects the custody invariant if the proposer sets it
    # honestly. As a second, independent check, scan the proposal text itself
    # for language suggesting financial write capability; if found without the
    # flag or an explicit acknowledgment, refuse rather than silently proceed.
    combined_text = f"{args.problem} {args.change} {args.benefit}".lower()
    matched_keywords = [kw for kw in CUSTODY_RISK_KEYWORDS if kw in combined_text]
    if matched_keywords and not args.enables_autonomous_financial_execution and not args.acknowledge_no_autonomous_financial_execution:
        raise SystemExit(
            "refused: this proposal's text matches custody-risk keyword(s) "
            f"{matched_keywords}. If this change would grant any financial "
            "write capability, re-run with "
            "--enables-autonomous-financial-execution (it will be rejected "
            "as Class D). If it does not, re-run with "
            "--acknowledge-no-autonomous-financial-execution to confirm that "
            "explicitly. This check cannot see intent, only text, so it "
            "errs toward asking rather than guessing."
        )

    # Custody invariant: no self-proposed change may grant autonomous financial
    # write authority, regardless of the class the proposer requested. This
    # cannot be bypassed by asking for class A/B/C instead of D.
    if args.enables_autonomous_financial_execution:
        change_class = "D"
        status = "REJECTED_PROHIBITED"
    elif change_class in prohibited_classes:
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
    critical, reasons = classify_critical(amount=args.amount, max_loss=args.max_loss, recurring=args.recurring, new_business_model=args.new_business_model, external_obligations=args.external_obligations, legal_uncertainty=args.legal_uncertainty, public_representation=args.public_representation, new_financial_write_access=args.new_financial_write_access, policy_relaxation=args.policy_relaxation, new_readonly_financial_adapter=args.new_readonly_financial_adapter)
    print(json.dumps({"critical": critical, "requires_human_authorization": critical, "reasons": reasons}, indent=2))


def cmd_request_approval(args):
    critical, reasons = classify_critical(amount=args.amount, max_loss=args.max_loss, recurring=args.recurring, new_business_model=args.new_business_model, external_obligations=args.external_obligations, legal_uncertainty=args.legal_uncertainty, public_representation=args.public_representation, new_financial_write_access=args.new_financial_write_access, policy_relaxation=args.policy_relaxation, new_readonly_financial_adapter=args.new_readonly_financial_adapter)
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

def _record_human_decision(approval_id: str, decision: str, human_statement: str) -> Path:
    """Write an APPROVED/REJECTED decision into approvals/pending/<id>.md,
    quoting the human's own words verbatim per the interactive-session
    approval-authentication convention (CRITICAL_DECISIONS.md 'Approval
    authentication'). This does not, and cannot, cryptographically prove the
    edit came from the human rather than the AI operator itself -- it only
    standardizes an auditable record of what the human was told was said,
    for a single-operator, interactive-session context. It must never be
    used to represent an unattended/scheduled session as human-authorized.
    """
    path = APPROVALS_PENDING_DIR / f"{approval_id}.md"
    if not path.exists():
        raise SystemExit(f"no pending approval: {approval_id}")
    text = path.read_text(encoding="utf-8")
    marker = "## Human decision"
    idx = text.find(marker)
    if idx == -1:
        raise SystemExit(f"approval record {approval_id} has no '## Human decision' section")
    header = text[:idx]
    record = (
        f"{marker}\n\n"
        f"{decision} (interactive session, single-operator machine)\n\n"
        f"- Captured at: {now_iso()}\n"
        f'- Human statement (verbatim): "{human_statement}"\n'
    )
    path.write_text(header + record, encoding="utf-8")
    # Move out of pending/ once a human decision is recorded, mirroring the
    # execution-request lifecycle (pending -> exactly one terminal location).
    # _approval_decision() checks both dirs, so anything already referencing
    # this approval by ID keeps working unaffected.
    APPROVALS_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archived_path = APPROVALS_ARCHIVE_DIR / path.name
    path.rename(archived_path)
    return archived_path


def cmd_approve_decision(args):
    path = _record_human_decision(args.approval_id, "APPROVED", args.human_statement)
    append_index("approvals", {
        "id": args.approval_id, "date": now_iso(), "status": "APPROVED",
        "path": f"approvals/archive/{path.name}",
    })
    print(json.dumps({"approval_id": args.approval_id, "status": "APPROVED", "path": str(path)}, indent=2))


def cmd_reject_decision(args):
    path = _record_human_decision(args.approval_id, "REJECTED", args.human_statement)
    append_index("approvals", {
        "id": args.approval_id, "date": now_iso(), "status": "REJECTED",
        "path": f"approvals/archive/{path.name}",
    })
    print(json.dumps({"approval_id": args.approval_id, "status": "REJECTED", "path": str(path)}, indent=2))


def _approval_decision(approval_id: str) -> str:
    """Return APPROVED / REJECTED / PENDING / UNKNOWN by reading the approval
    record's 'Human decision' section. Checks both pending and archive so an
    approval that was moved after a human decision is still found."""
    for directory in (APPROVALS_PENDING_DIR, APPROVALS_ARCHIVE_DIR):
        path = directory / f"{approval_id}.md"
        if path.exists():
            text = path.read_text(encoding="utf-8")
            marker = "## Human decision"
            idx = text.find(marker)
            if idx == -1:
                return "UNKNOWN"
            after = text[idx + len(marker):].strip()
            first_line = after.splitlines()[0].strip() if after else ""
            if first_line.upper().startswith("APPROVED"):
                return "APPROVED"
            if first_line.upper().startswith("REJECTED"):
                return "REJECTED"
            return "PENDING"
    return "UNKNOWN"


def cmd_request_execution(args):
    action = args.action.upper()
    if action not in ALLOWED_EXECUTION_ACTIONS:
        raise SystemExit(f"unsupported execution action: {action}. Allowed: {sorted(ALLOWED_EXECUTION_ACTIONS)}")
    if action in ACTIONS_REQUIRING_HUMAN_CONTROLLED_DESTINATION and not args.destination_controlled_by_human:
        raise SystemExit(
            "refused: TRANSFER/WITHDRAWAL requires --destination-controlled-by-human "
            "(INVESTMENT_POLICY.md section 3: no withdrawals to destinations not "
            "controlled by the human owner)."
        )

    issues = policy_check_proposal(args.max_total_capital)
    if issues:
        raise SystemExit("refused: policy check failed: " + "; ".join(issues))

    critical, reasons = classify_critical(
        amount=args.max_total_capital, max_loss=args.max_loss,
        recurring=args.recurring, new_business_model=args.new_business_model,
        external_obligations=args.external_obligations,
        legal_uncertainty=args.legal_uncertainty,
        public_representation=args.public_representation,
        new_financial_write_access=args.new_financial_write_access,
        policy_relaxation=args.policy_relaxation,
    )
    if critical:
        if not args.approval_id:
            raise SystemExit(
                "refused: this execution is classified critical "
                f"({'; '.join(reasons)}) and requires an approved "
                "approvals/pending (or archived) record. Pass --approval-id "
                "after the human authorizes it via `request-approval`."
            )
        decision = _approval_decision(args.approval_id)
        if decision != "APPROVED":
            raise SystemExit(
                f"refused: approval {args.approval_id} is not APPROVED "
                f"(current human decision: {decision}). Critical-decision "
                "authorization and financial execution are separate events; "
                "authorization must exist first."
            )

    request_id = f"HER-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    HR_PENDING_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "id": request_id,
        "created_at": now_iso(),
        "decision_id": args.decision_id,
        "approval_id": args.approval_id,
        "action": action,
        "asset": args.asset,
        "quantity": args.quantity,
        "max_price": args.max_price,
        "max_total_capital": round(args.max_total_capital, 2),
        "valid_until": args.valid_until,
        "reason": args.reason,
        "expected_upside": args.expected_upside,
        "maximum_plausible_loss": round(args.max_loss, 2),
        "critic_assessment": args.critic_assessment,
        "policy_status": "PASSED",
        "critical_decision": critical,
        "criticality_reasons": reasons,
        "status": "pending",
        "instructions": (
            "Execute this operation manually on the appropriate financial "
            "platform using your own credentials. The Capital Agent has no "
            "capability to execute it. Report the actual result with "
            "`confirm-execution`, or `cancel-execution` / `expire-execution` "
            "if it will not be executed."
        ),
        "confirmation": None,
    }
    path = HR_PENDING_DIR / f"{request_id}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    append_index("execution_requests", {
        "id": request_id,
        "created_at": data["created_at"],
        "action": action,
        "asset": args.asset,
        "max_total_capital_brl": data["max_total_capital"],
        "status": "pending",
        "path": f"execution/human_requests/pending/{request_id}.json",
    })
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _find_pending_request(request_id: str) -> Path:
    path = HR_PENDING_DIR / f"{request_id}.json"
    if not path.exists():
        raise SystemExit(f"no pending human execution request: {request_id}")
    return path


def cmd_confirm_execution(args):
    path = _find_pending_request(args.id)
    data = json.loads(path.read_text(encoding="utf-8"))

    executed_total = round(args.executed_quantity * args.executed_price + args.fees, 2)
    action = data["action"]
    if action == "BUY":
        ledger_type = "buy"
    elif action == "SELL":
        ledger_type = "sell"
    elif action in {"TRANSFER", "WITHDRAWAL"}:
        ledger_type = "capital_out"
    elif action == "PAYMENT":
        ledger_type = "expense"
    else:
        ledger_type = args.ledger_type or "adjustment"

    if ledger_type in {"buy", "expense", "fee", "tax", "capital_out"} and executed_total > cash_balance():
        raise SystemExit("refused: reported execution would exceed verified cash; investigate before recording")

    confirmation = {
        "confirmed_at": now_iso(),
        "executed_quantity": args.executed_quantity,
        "executed_price": args.executed_price,
        "fees_brl": round(args.fees, 2),
        "executed_total_brl": executed_total,
        "executed_timestamp": args.executed_timestamp or now_iso(),
        "notes": args.notes,
    }
    data["status"] = "completed"
    data["confirmation"] = confirmation

    append_ledger(
        ledger_type, args.category or "market", executed_total,
        f"Human-confirmed execution of {data['id']} ({action} {data.get('asset')})",
        data["id"],
    )

    HR_COMPLETED_DIR.mkdir(parents=True, exist_ok=True)
    (HR_COMPLETED_DIR / path.name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    path.unlink()
    append_index("execution_requests", {
        "id": data["id"], "date": confirmation["confirmed_at"], "action": action,
        "asset": data.get("asset"), "executed_total_brl": executed_total,
        "status": "completed", "path": f"execution/human_requests/completed/{path.name}",
    })
    print(json.dumps({"id": data["id"], "status": "completed", "verified_cash_brl": cash_balance()}, indent=2))


def cmd_cancel_execution(args):
    path = _find_pending_request(args.id)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = "cancelled"
    data["cancellation"] = {"cancelled_at": now_iso(), "reason": args.reason}
    HR_CANCELLED_DIR.mkdir(parents=True, exist_ok=True)
    (HR_CANCELLED_DIR / path.name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    path.unlink()
    append_index("execution_requests", {
        "id": data["id"], "date": data["cancellation"]["cancelled_at"], "status": "cancelled",
        "path": f"execution/human_requests/cancelled/{path.name}",
    })
    print(json.dumps({"id": data["id"], "status": "cancelled"}, indent=2))


def cmd_expire_execution(args):
    path = _find_pending_request(args.id)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = "expired"
    data["expiration"] = {"expired_at": now_iso(), "reason": args.reason or "validity window passed"}
    HR_EXPIRED_DIR.mkdir(parents=True, exist_ok=True)
    (HR_EXPIRED_DIR / path.name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    path.unlink()
    append_index("execution_requests", {
        "id": data["id"], "date": data["expiration"]["expired_at"], "status": "expired",
        "path": f"execution/human_requests/expired/{path.name}",
    })
    print(json.dumps({"id": data["id"], "status": "expired"}, indent=2))


def cmd_sweep_expired_executions(_args):
    """Deterministic check: move pending requests whose valid_until has passed
    to expired/. No AI reasoning required for this, per the 'deterministic
    computation first' principle (ARCHITECTURE.md)."""
    HR_PENDING_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).astimezone()
    swept = []
    for path in sorted(HR_PENDING_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        valid_until = data.get("valid_until")
        if not valid_until:
            continue
        try:
            deadline = datetime.fromisoformat(valid_until)
        except ValueError:
            continue
        if deadline.tzinfo is None:
            deadline = deadline.astimezone()
        if now > deadline:
            data["status"] = "expired"
            data["expiration"] = {"expired_at": now_iso(), "reason": "validity window passed (automatic sweep)"}
            HR_EXPIRED_DIR.mkdir(parents=True, exist_ok=True)
            (HR_EXPIRED_DIR / path.name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            path.unlink()
            swept.append(data["id"])
    print(json.dumps({"expired": swept}, indent=2))


def cmd_list_execution_requests(_args):
    requests = _list_json(HR_PENDING_DIR)
    print(json.dumps(requests, indent=2, ensure_ascii=False))


def cmd_record_reserve_asset(args):
    """Record a near-cash reserve instrument (e.g. Tesouro Selic) so
    current_equity_floor() stops understating patrimony after a confirmed
    purchase. Book value is derived from the referenced completed Human
    Execution Request, never taken as a free-form number, so it always
    traces back to something the human actually confirmed."""
    path = HR_COMPLETED_DIR / f"{args.execution_id}.json"
    if not path.exists():
        raise SystemExit(
            f"no completed execution request: {args.execution_id}. "
            "record-reserve-asset only accepts execution IDs that were "
            "actually confirmed via confirm-execution."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("action") != "BUY":
        raise SystemExit(f"execution {args.execution_id} is not a BUY; refusing to book it as a reserve asset")
    book_value = data["confirmation"]["executed_total_brl"]

    entry = {
        "id": f"RA-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
        "execution_id": args.execution_id,
        "asset": data.get("asset"),
        "category": args.category,
        "book_value_brl": book_value,
        "recorded_at": now_iso(),
        "note": args.note,
    }
    assets = load_reserve_assets()
    assets.append(entry)
    RESERVE_ASSETS_FILE.write_text(json.dumps(assets, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"recorded": entry, "verified_equity_floor_brl": current_equity_floor()}, indent=2))


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
    pending_execution_requests = _list_json(HR_PENDING_DIR)

    lines = []
    lines.append("# Current State")
    lines.append("")
    lines.append("Generated deterministically by `python src/capital_agent.py update-context`.")
    lines.append("Do not hand-edit; edit the underlying sources (ledger, config, experiments, journal) and regenerate.")
    lines.append("")
    lines.append(f"- Generated at: {now_iso()}")
    lines.append(f"- Repository/policy version: {policy.get('policy_version', 'unknown')}")
    lines.append("- Operating phase: 0 (research/proposals/simulations only; see `ROADMAP.md`)")
    lines.append("- Custody invariant: only the human owner may move real money; the Capital Agent has no financial write capability at any phase (`AI_OPERATING_MANUAL.md`).")
    lines.append("")
    lines.append("## Capital (verified from data/ledger.csv)")
    lines.append("")
    reserve_assets = load_reserve_assets()
    lines.append(f"- Initial capital: BRL {float(policy['initial_capital']):.2f}")
    lines.append(f"- Verified cash: BRL {cash:.2f}")
    lines.append(f"- Reserve instruments booked (data/reserve_assets.json, e.g. Tesouro Selic, conservatively valued at cost): BRL {reserve_assets_value():.2f}")
    lines.append(f"- Verified equity floor (cash + booked reserve instruments; other market positions still not marked): BRL {equity:.2f}")
    if reserve_assets:
        for a in reserve_assets:
            lines.append(f"  - {a.get('id')}: {a.get('asset')} — BRL {a.get('book_value_brl')} (execution {a.get('execution_id')})")
    lines.append(f"- Capital invested (market/experiment buckets): not yet implemented (no bucket-level ledger breakdown)")
    lines.append(f"- Capital committed (open experiment budgets not yet spent): not yet implemented")
    lines.append(f"- Drawdown from equity high-water mark: not yet implemented (no high-water-mark tracking yet)")
    lines.append(f"- Ledger entries: {len(ledger)}")
    lines.append("")
    lines.append("## Execution tier & limits (config/policy.json)")
    lines.append("")
    lines.append(f"- Execution tier (operating phase): {policy['execution_tier']}")
    lines.append(f"- Human Execution Requests in active use: {policy['live_execution_enabled']}")
    lines.append(f"- Autonomous financial execution permitted: {policy['autonomous_financial_execution_permitted']} (hard invariant, always False)")
    lines.append(f"- Max single live allocation: BRL {equity * float(policy['max_single_live_allocation_pct_equity']):.2f}")
    lines.append(f"- Min cash reserve: BRL {equity * float(policy['min_cash_reserve_pct_equity']):.2f}")
    lines.append(f"- Hard drawdown freeze: {float(policy['hard_drawdown_freeze_pct']) * 100:.0f}% of equity")
    lines.append("")
    lines.append("## Positions")
    lines.append("")
    lines.append("None recorded. No financial write adapter exists or ever will under this architecture; positions only change via confirmed Human Execution Requests.")
    lines.append("")
    lines.append("## Pending Human Execution Requests (execution/human_requests/pending/)")
    lines.append("")
    if pending_execution_requests:
        for r in pending_execution_requests:
            lines.append(
                f"- {r.get('id')}: {r.get('action')} {r.get('asset')} — "
                f"max_total_capital=BRL {r.get('max_total_capital')}, "
                f"critical={r.get('critical_decision')}, valid_until={r.get('valid_until')}"
            )
    else:
        lines.append("None. No financial execution is currently waiting on the human owner.")
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
    lines.append("- No historical equity high-water mark is tracked yet, so drawdown cannot be computed.")
    lines.append("- No scheduler run history yet; autonomous operation cadence is not yet exercised in production.")
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
    sc.add_argument("--enables-autonomous-financial-execution", action="store_true",
                     help="Must be set truthfully if the change would grant the system "
                          "any financial write capability. Forces REJECTED_PROHIBITED "
                          "(Class D) regardless of --class.")
    sc.add_argument("--acknowledge-no-autonomous-financial-execution", action="store_true",
                     help="Required when the proposal text matches a custody-risk keyword "
                          "but does not actually enable financial write capability.")
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
    cd.add_argument("--new-readonly-financial-adapter", action="store_true")
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
    ar.add_argument("--new-readonly-financial-adapter", action="store_true")
    ar.set_defaults(func=cmd_request_approval)

    ad = sub.add_parser("approve-decision", help="Record human APPROVED (interactive session convention; see CRITICAL_DECISIONS.md).")
    ad.add_argument("--approval-id", required=True)
    ad.add_argument("--human-statement", required=True, help="The human's own words, verbatim, authorizing this decision.")
    ad.set_defaults(func=cmd_approve_decision)

    rd = sub.add_parser("reject-decision", help="Record human REJECTED (interactive session convention; see CRITICAL_DECISIONS.md).")
    rd.add_argument("--approval-id", required=True)
    rd.add_argument("--human-statement", required=True, help="The human's own words, verbatim, rejecting this decision.")
    rd.set_defaults(func=cmd_reject_decision)

    uc = sub.add_parser("update-context")
    uc.set_defaults(func=cmd_update_context)

    re_ = sub.add_parser("request-execution")
    re_.add_argument("--action", required=True, help="BUY|SELL|TRANSFER|WITHDRAWAL|PAYMENT|OTHER")
    re_.add_argument("--asset", required=True)
    re_.add_argument("--quantity", type=float, required=True)
    re_.add_argument("--max-price", type=float, required=True)
    re_.add_argument("--max-total-capital", type=float, required=True)
    re_.add_argument("--valid-until", required=True, help="ISO 8601 timestamp")
    re_.add_argument("--reason", required=True)
    re_.add_argument("--expected-upside", required=True)
    re_.add_argument("--max-loss", type=float, required=True)
    re_.add_argument("--critic-assessment", required=True)
    re_.add_argument("--decision-id", default=None)
    re_.add_argument("--approval-id", default=None)
    re_.add_argument("--destination-controlled-by-human", action="store_true")
    re_.add_argument("--recurring", action="store_true")
    re_.add_argument("--new-business-model", action="store_true")
    re_.add_argument("--external-obligations", action="store_true")
    re_.add_argument("--legal-uncertainty", action="store_true")
    re_.add_argument("--public-representation", action="store_true")
    re_.add_argument("--new-financial-write-access", action="store_true")
    re_.add_argument("--policy-relaxation", action="store_true")
    re_.set_defaults(func=cmd_request_execution)

    ce = sub.add_parser("confirm-execution")
    ce.add_argument("--id", required=True)
    ce.add_argument("--executed-quantity", type=float, required=True)
    ce.add_argument("--executed-price", type=float, required=True)
    ce.add_argument("--fees", type=float, default=0.0)
    ce.add_argument("--executed-timestamp", default=None)
    ce.add_argument("--category", default=None)
    ce.add_argument("--ledger-type", default=None, help="override for OTHER actions")
    ce.add_argument("--notes", default="")
    ce.set_defaults(func=cmd_confirm_execution)

    xe = sub.add_parser("cancel-execution")
    xe.add_argument("--id", required=True)
    xe.add_argument("--reason", required=True)
    xe.set_defaults(func=cmd_cancel_execution)

    ee = sub.add_parser("expire-execution")
    ee.add_argument("--id", required=True)
    ee.add_argument("--reason", default=None)
    ee.set_defaults(func=cmd_expire_execution)

    se = sub.add_parser("sweep-expired-executions")
    se.set_defaults(func=cmd_sweep_expired_executions)

    le = sub.add_parser("execution-requests")
    le.set_defaults(func=cmd_list_execution_requests)

    rra = sub.add_parser("record-reserve-asset", help="Book a confirmed BUY (e.g. Tesouro Selic) as a reserve instrument so the equity floor reflects it.")
    rra.add_argument("--execution-id", required=True)
    rra.add_argument("--category", default="reserve")
    rra.add_argument("--note", default="")
    rra.set_defaults(func=cmd_record_reserve_asset)

    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
