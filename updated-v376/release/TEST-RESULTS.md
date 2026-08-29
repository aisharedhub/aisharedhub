# Updated V376 — Offline Test Campaign Results

Every suite runs OFFLINE against an inert fake MetaTrader5. No live MT5
connection is ever made and no broker send leaves any test: every suite
asserts its own send ledger (unscripted sends are impossible — the fake
records every `order_send` verbatim and answers only what a scenario
scripts). The supplied live state files were used strictly read-only.

## Final battery

Every suite below ran green, in one sequential battery, against the
exact shipped build (`DEFAULT/vol_target_bot_v12.py`, SHA-256
`8b680bf9734901063233ae1d623b4b6364f46da80e38258248295fe6fe49201d`).

| Suite | Result |
| --- | --- |
| test_cli | 304 pass, 0 fail |
| test_binding_schema | 23 pass, 0 fail |
| test_controller_ledger | 40 pass, 0 fail |
| test_applied_exposure | 20 pass, 0 fail |
| test_r4_migration | 72 pass, 0 fail |
| test_operator_commands | 70 pass, 0 fail |
| test_console_status | 19 pass, 0 fail |
| test_gate_history | 45 pass, 0 fail |
| test_formula_equivalence | 45 pass, 0 fail |
| test_order_routes | 30 pass, 0 fail |
| test_protections | 31 pass, 0 fail |
| test_fresh_lifecycle | 36 pass, 0 fail |
| test_orb_matrix | 18 pass, 0 fail |
| test_target_completion | 14 pass, 0 fail |
| test_interrupt | 8 pass, 0 fail |
| test_continuity_chain | 10 pass, 0 fail |
| **Total** | **785 checks, 0 failures** |
| run_mutations | **15/15 mutants KILLED, 0 survived** |

## Suites (maintainer/tests/)

| Suite | What it proves |
| --- | --- |
| test_cli | The strict order-independent parser: every documented recipe in every flag order; refusal of unknown/duplicate/contradictory/malformed commands; maintenance verbs; interpreted-recipe rendering. |
| test_binding_schema | direct_lifecycle_binding/11 polarity: strict sites require /11; custody/safety semantics accept the active pair; /10 only as the r4 migration source. |
| test_controller_ledger | The dated controller ledger: entry/provenance validation, strict session chaining, bounded proven gaps, quarantine, window derivation, refusal of undated legacy lists, omitted-return honesty. |
| test_applied_exposure | Broker-proved applied leverage: matched inventory proves the request; partial books prove the implied value; pending intents/unknown inventory/unpriceable exposure defer; day_roll_txn/2 audit fields. |
| test_r4_migration | The one-time r4 takeover against the EXACT supplied state and live positions: full pass, interruption + native resume at every stage, foreign/grown/reduced ticket matrix, tamper refusal, permanent completion, zero sends. |
| test_operator_commands | --diagnose (read-only), durable pause/resume (proof-gated), --flatten-and-stop (managed close-everything, resumable folder), request-file atomicity, restart durability. |
| test_console_status | The section-19 console: exact dollar distances on the committed r4 evidence, requested-vs-applied leverage, honest UNKNOWN/UNPROVED placeholders, exact-blocker naming. |
| test_gate_history | Full-history causal gate 1:1: the REAL _check_arm vs an independent causal walk across ALL 5,220 eligible launches (zero mismatches); census 5,220/5,181/279; July 24 crossing / July 31 bit-exact low / Aug 4 arm / Aug 5 first-eligible; a cold launch-seeded gate never crosses; IEEE-754 boundary probes; P2 cap force-release; rearm-exactly-once; and the exact 269/279 = 96.4157706093% reproduction from the V376 oracle arrays. |
| test_formula_equivalence | The trusted V376 bot EXECUTED side by side: momentum/S8V/ONF-regime bit-identical over every real seed window + seeded random walks; the full controller bit-identical over a two-phase grid including the reconstructed defect operating points; sleeve caps; every frozen constant; ONF permanently disabled. |
| test_order_routes | The exactly-once engine: DONE is only an acknowledgement; full/partial fills prove from causal deals + terminal order history; explicit rejections release durably; timeout/None stay UNKNOWN until a proved zero-fill; INVALID_FILL retries the alternate policy exactly once; malformed receipts and overfills latch close-only; an unresolved intent never resends. |
| test_protections | Foreign/wrong-symbol/pending-order blocks; UNKNOWN inventory; deposits can never feed strategy; save-failure latch + known-unsent rollback; duplicate-process refusal; account-switch halt; daily/breaker/floor rails (breaker flattens exact-ticket and stands down through the next day); expired daily lease never caught up late; reductions live under the latch; no same-poll reversal. |
| test_fresh_lifecycle | Complete campaigns through the real _main_impl: P2-immediate virgin bind → NY17 roll → Prague anchor → four genuine lease entries with requested 6.00x broker-PROVEN applied 6.00x → dated live-account ledger entry with per-sleeve fractions; identical-command resume with zero sends; wrong-recipe refusal without semantic mutation; closed-market Saturday startup binds/writes nothing; P1 gated waits and resumes waiting; virgin P2-gated refuses without P1 continuity. |
| test_orb_matrix | The real ORB engine: exact six-bar range; first-breakout entry with the stop on the far range side and TP at exactly entry+5R; verified SL/TP protection under the 5x inner cap; one event per day; EOD exact-ticket flat; missing/duplicate bars never trade; ~30s entry-window expiry; the min(20 ticks, 0.15R) drift cap; range-too-small stand-down. |
| test_target_completion | A genuine rally through $210k: durable watch → account-wide exact-ticket closes realize the profit → double flat/cash proof → permanent target_hit/2 in BOTH recovery images → restart permanently complete; a below-line realization NEVER passes falsely. |
| test_interrupt | Ctrl+C managed flatten: exact-ticket closes, the keyboard halt clears only after the 60s account-flat quiet proof, exposure is retained (never abandoned) under a silent broker. |
| test_continuity_chain | P1-immediate campaign to +10% → hash-enveloped continuity export carrying the dated ledger → adopted by a fresh p2-fresh gated folder with the continuity identity sealed and rearm consumed once. |
| run_mutations | Mutation battery over the critical protections — every mutant must be KILLED by its named suite, with hash-verified pristine restore. |

## Evidence-gated parts

Suites that replay the supplied live r4 state/archives
(test_r4_migration, test_console_status, parts of test_gate_history and
test_formula_equivalence, test_operator_commands part B) read the
evidence from `UPDATED_V376_EVIDENCE_DIR`, defaulting to an `evidence/`
directory beside `tests/` (place `bot_state_v12.json`, its `.bak`,
`376.zip` and `V389.zip` there), and SKIP cleanly when absent. The
evidence itself (account state) is never part of this archive. The
published battery numbers were produced WITH the evidence attached —
no handoff test was skipped.

The r4 suite also proves the fail-closed path for the states this
build must NOT migrate: a synthesized mid-takeover source (the real
state with its `COMMITTED/COMMITTED/PROVED` markers flipped to
`ANCHOR_WAIT/ACTIVE/UNPROVED`) and a bridge-absent source are refused
without writing any migration record or sending anything, all new risk
stays blocked, and the console names the exact blocker; the folder is
left byte-for-byte for the predecessor build.

## Release verification performed

* Deterministic double build: two independent packagings byte-identical.
* Clean double extraction: the archive extracted into two fresh
  directories; hash manifest verified and the fast suites re-run from
  each extraction.
* Pinned-terminal variants (`1/`, `2/`): the packager asserts each
  variant differs from the DEFAULT bot by EXACTLY the one documented
  `DEFAULT_MT5_PATH` line. The pinned code path was verified by the
  complete 16-suite battery run against a variant pinned to a sandbox
  `terminal64.exe` (identical except the literal path string), plus
  unit proofs that `mt5.initialize` receives the exact pinned path and
  that a missing pinned terminal refuses with exit 5 before any attach,
  send, or state access (both refusal causes exercised). The literal
  Windows paths themselves can only exist on the target machine; the
  first live start validates them and fails closed otherwise.

To run the maintainer suites from an extraction, first copy the live
folder to the layout the harnesses resolve
(`cp -r DEFAULT maintainer/build`, giving `build/` next to `tests/`
inside `maintainer/`), then run
each suite from inside `maintainer/tests/`. Suites that replay the live
r4 evidence skip cleanly unless `UPDATED_V376_EVIDENCE_DIR` points at
the (never-distributed) evidence files.
