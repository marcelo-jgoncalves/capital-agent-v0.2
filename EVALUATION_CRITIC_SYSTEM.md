# Evaluation & Critic System

Version: 0.2

## Purpose

The Evaluation & Critic System evaluates outcomes, forecasts, decisions, process quality and the Capital Agent itself. Self-criticism is mandatory.

## Principles

1. Profit does not prove a decision was good.
2. Loss does not prove a decision was bad.
3. Forecasts are persisted before outcomes are known.
4. Criticism uses recorded evidence, not reconstructed hindsight.
5. Critic records are append-only; corrections create new records.
6. Repeated failure patterns generate system-improvement proposals.
7. Rejected opportunities are reviewed to detect excessive caution.
8. Results are compared with simple counterfactual alternatives.
9. The critic cannot authorize or execute critical actions.
10. Model diversity is preferred for high-impact reviews when practical.

## Level 1 — Pre-decision critique

Before a material decision, challenge the thesis, identify missing evidence and failure modes, compare alternatives including inaction, estimate maximum plausible loss, evaluate reversibility and classify criticality. Critical decisions require a critic assessment before human approval.

## Level 2 — Outcome post-mortem

At a review condition, compare expected and actual outcomes; separate analysis, execution, process and randomness; identify ignored evidence; check kill/scale conditions; persist lessons; and propose system changes when justified.

## Level 3 — System audit

Periodically evaluate equity growth, benchmark-relative return, drawdown, calibration, capital efficiency, turnover/activity bias, concentration drift, recurring failure modes, opportunity cost, complexity cost, policy compliance, critical-decision compliance and whether system changes improved outcomes.

## Prediction and calibration

Material decisions should record confidence, downside/base/upside cases, success/failure conditions, maximum plausible loss and review condition. Persistent overconfidence or underconfidence should generate a model/process adjustment proposal.

## Counterfactual review

Where reliable data exists, compare against simple alternatives such as a low-risk BRL benchmark, broad Brazilian equities, broad international equities, Bitcoin, simple passive allocations and doing nothing. The purpose is to test whether added complexity, risk and operating effort create value.

## Critic independence

The critic has no transaction authority, cannot approve its own critical decision, cannot delete original records, may recommend stricter policy, may propose system changes and must distinguish facts, estimates and judgments.

## Required artifacts

- `journal/predictions/`
- `journal/postmortems/`
- `journal/audits/`
- `evaluation/calibration/`
- `evaluation/benchmarks/`
- `evaluation/attribution/`
- `context/knowledge/`

## Mandatory triggers

Post-mortem after an experiment closes, thesis invalidation, maximum-loss condition, unexpected material outcome, policy breach or execution anomaly — including whenever a Human Execution Request is confirmed (`execution/human_requests/completed/`) with results materially different from what was requested. System audit monthly during live operation, after a hard drawdown freeze, after three related failures, and before a material relaxation of risk authority or any proposal touching the custody invariant (`AI_OPERATING_MANUAL.md`).
