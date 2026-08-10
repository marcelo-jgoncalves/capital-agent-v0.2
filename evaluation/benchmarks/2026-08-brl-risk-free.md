# Benchmark: BRL risk-free rate

Per `INVESTMENT_POLICY.md` section 7 ("the system should maintain an
opportunity-cost benchmark representing a low-risk BRL alternative").

## Current reading

- Date captured: 2026-08-10
- Benchmark: Selic (target rate), proxied by Tesouro Selic for an actual
  investable instrument.
- Value: 14% a.a. (Selic).
- Source quality: `WebSearch`, cross-checked across 3 independent result
  sources (Investidor10, Nubank blog, Tesouro Direto's own site) that agreed
  on 14% a.a. A companion CDI figure in the same search was internally
  inconsistent (one blob said ~8.42% a.a., another ~13.90% a.a.) and is
  **not** relied upon — treated as `UNTRUSTED EXTERNAL CONTENT` per
  `ARCHITECTURE.md`. Sources:
  [Taxa Selic Hoje — Investidor10](https://investidor10.com.br/indices/selic/),
  [Taxa Selic 2026 — Nubank](https://blog.nubank.com.br/taxa-selic-2026/),
  [Rentabilidade dos Títulos — Tesouro Direto](https://www.tesourodireto.com.br/en/produtos/dados-sobre-titulos/rendimento-dos-titulos).
- Confidence: medium-high on the Selic figure itself (multi-sourced); low on
  precision to the decimal (web search summaries, not the primary
  Tesouro Direto/BCB data feed directly parsed).

## How this is used

This is the hurdle rate every other opportunity is compared against in
`journal/decisions/DEC-20260810-A032A0.md`: any strategy with real effort
or real risk needs to plausibly beat ~14% a.a. (risk/effort-adjusted) to be
worth pursuing over simply holding Tesouro Selic.

## Known limitation

No automated, repeatable data source is wired up yet (`ROADMAP.md` Phase 1
item: "Add current low-risk BRL benchmark," "Build quote cache with
timestamps/source provenance" — not yet implemented). This snapshot is
manual and will go stale; re-check before relying on it for a live decision
more than a few weeks old. The Yahoo Finance MCP added this session
(`SYS-20260810-C76D60`) covers US-listed equity data, not Brazilian
fixed-income/Selic data — a BCB (Banco Central) or B3 data source would be
needed to automate this specific benchmark.
