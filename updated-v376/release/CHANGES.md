# Updated V376 — Change Report

Base: the exact supplied V389 r4 DEFAULT build (`vol_target_bot_v12.py`,
BOT_BUILD `v3.8.9-fast-r4`, sha256 `083435ea…`), itself verified as V376
(`v3.7.6`) plus the V389 hardening. Strategy math is bit-identical to
the trusted V376 (`07516a8c…` archive) — proved by executed side-by-side
equivalence, not by inspection alone. Final build: BOT_BUILD
`v3.9.4-updated-v376` (v3.9.0 through v3.9.3 were internal, never
deployed).

## 1. V376-style startup (build order §1)

* Bare single-terminal `mt5.initialize()` auto-discovery by default; an
  OPTIONAL strictly validated `--mt5-path` pin (and the edit-once
  `DEFAULT_MT5_PATH` source default used by folders 1/ and 2/). No BAT
  wrapper, no watchdog. Startup performs ONE deliberate isolated
  re-exec (`-E -P -B`); on Windows this is a second python process of
  the same console.
* V376-style typed confirmation `I ACCEPT LIVE` for live starts;
  `--yes` skips the confirmation unconditionally (virgin starts
  included) — reserve it for unattended exact resume.
* New strict order-independent command parser: only the documented
  recipes parse; unknown, duplicate, contradictory or untested values
  are refused before any MT5 or state access; the interpreted recipe is
  printed and (not raw argv) binds to lifecycle state.

## 2. Lifecycle schema (§12)

* New binding schema `direct_lifecycle_binding/11` under a new direct
  authority hash. The exact supplied r4 binding (`/10`) is recognized
  solely as the one-time migration source; every strict authorization
  site requires `/11`, while custody/safety semantics accept the active
  pair so live exposure is never orphaned.

## 3. Dated controller ledger — defect-1 repair (§7)

* `controller_ledger/1`: every vol/dip observation carries session,
  provenance (`seed` / `shadow-backfill` / `shadow-live` /
  `live-account` / `standdown`), returns, dip, applied/requested
  leverage, per-sleeve fractions and flags. Sessions are strictly
  increasing with exact-successor chaining or bounded proven calendar
  gaps; an unchainable entry quarantines the dated authority loudly.
* Legacy undated return lists are refused as live economic authority;
  windows derive from the ledger. Omitted account returns are recorded
  as omitted (`account-return-omitted`) — never fabricated as zero.

## 4. Broker-proved applied exposure — defect-2 repair (§7)

* `applied_exposure/1` + `day_roll_txn/2`: after each clean reconcile,
  the applied daily leverage is re-proved from actual per-sleeve broker
  inventory; `_last_L` is only ever that proven value (matched requests
  prove the requested leverage; partial/blocked books prove the
  inventory-implied value). The day roll books the proven exposure and
  per-sleeve fractions into the dated ledger.

## 5. Full-or-hold sizing (§8)

* The V376 cold-start half-leverage is gone. An unproved anchor holds
  increases at zero with positions protected; when every proof clears,
  the full calculated controller target is authorized immediately.

## 6. One-time r4 migration (§13)

* `r4_final_migration/1`: PREPARED → INVENTORY_PROVED → LEDGER_REBUILT
  → COMMITTED. Requires the exact source binding/state identity, proves
  every live ticket (foreign or grown tickets refuse; reductions map),
  rebuilds the dated ledger from the supplied evidence (legacy 4.375
  applied flagged `applied-L-unverified-legacy`; the omitted 08-27
  return recorded as omitted), settles the clock-hold dip exactly once,
  archives the r4 takeover/transition/bridge records verbatim, rebinds
  the lifecycle and cashflow guard, forces the anchor cold
  (full-or-hold), and commits atomically to both recovery images.
  Permanently completed thereafter.
* The generic V383–V388 predecessor-takeover adoption machinery is
  removed (38 dead functions); its startup/poll sites fail closed into
  close-only custody.

## 7. Operator commands (§5, §18)

* `--diagnose` (strictly read-only report), `--pause-new-risk` /
  `--resume-paused` (durable sidecar requests; pause is immediate and
  double-saved, resume applies only after safety-record proof),
  `--flatten-and-stop --live` (managed close-everything with a durable
  pause; the folder stays resumable).

## 8. Console (§19)

* Two-line periodic [STATUS]: balance/equity, capital, target and
  amount remaining, daily-halt/breaker/floor distances, position count,
  requested vs broker-applied vs proven-gross leverage, gate progress,
  daily/ORB status, feed age, and the exact strongest blocker (shared
  with the no-new-risk latch line). Waiting-phase [GATE] lines carry
  the explicit full-history peak. Bounded rotating daily logs.

## 9. Poll-loop repairs found by the offline campaign (§20)

* Shadow-frontier alignment drain: when the account mark settles in the
  same poll its D1 bundle arrives, the strategy ledger's oldest fold
  had no owner and every later send failed its NY17 frontier reproof;
  the loop now drains exactly one oldest-first shadow step (mirroring
  the first-start bootstrap rule) before any signal code.
* Dated-ledger sleeve normalization: the live day-roll entry copied
  audit `{lots, frac}` rows where the ledger requires numeric
  fractions, quarantining the ledger on its first live booking; the
  construction site now normalizes to per-sleeve fractions.

## 10. Test seams (inert; production never defines them)

* `_TEST_MAIN_MAX_POLLS` (main poll bound), `_TEST_R4_MIGRATION_MAX_POLLS`,
  `_TEST_FLATTEN_STOP_MAX_POLLS` — same family as the existing bounded
  loop seams.

## 11. Suite strengthening driven by the mutation battery (§20)

The first battery pass left four mutants alive; each exposed a real
assertion gap (the bot itself needed no change), closed as follows:

* Gate boundary probes now use a dyadic threshold (2⁻⁵) where
  `g_dd == -START_MIN_DD` and `eq/low−1 == START_BOUNCE` are exactly
  representable: with 0.02/0.005 the equality itself is unreachable in
  IEEE-754, so inclusive-vs-exclusive comparisons were unobservable.
* The dated-ledger validator's omitted-vs-numeric contradiction (a row
  flagged `account-return-omitted` carrying a numeric return) now has a
  direct rejection case plus its honest-form control.
* The operator pause is proved SUFFICIENT alone by a full campaign: the
  same authorized folder places zero entries inside the lease while
  paused, never catches the missed lease up late, and places the four
  entries at the next session's lease after resume.

## 11b. Handoff-report verification round (tests/packaging only)

A relayed failure report claimed the supplied r4 state was mid-takeover
(`ANCHOR_WAIT/ACTIVE/UNPROVED`, ledger bridge absent) and that the
handoff suites fail against it. Verification against the actual
supplied evidence disproved every state claim (the real takeover is
`COMMITTED/COMMITTED/PROVED` with the bridge present and valid, in both
recovery images), and the full battery reproduced from the pristine
baseline with the evidence attached. The round still yielded two
improvements, with the bot unchanged:

* test_r4_migration adds the refusal proofs for the reported
  hypothetical: a synthesized mid-takeover source and a bridge-absent
  source are held fail-closed — no migration record, no sends, new risk
  blocked, exact blocker named, folder left for the predecessor build
  (64 -> 72 checks).
* The evidence-gated suites' default evidence directory is now the
  portable `evidence/` beside `tests/` (the env variable still takes
  priority); a machine-specific absolute path had been baked in.

## 12. Pinned-terminal variant folders (packaging only)

`DEFAULT/` remains the primary requested build (bare `mt5.initialize()`
auto-discovery). The archive additionally ships `1/` and `2/`,
generated at packaging time from the DEFAULT bytes with an asserted
single-line diff: the documented edit-once `DEFAULT_MT5_PATH` source
default pins `C:\Program Files\MetaTrader 5\terminal64.exe` (folder 1)
or `C:\Program Files\MetaTrader 5 - 2\terminal64.exe` (folder 2). The
pin is operational only — not part of the recipe, binding or resume —
and is validated before any attach or state access (a missing terminal
refuses with exit 5, fail closed). The bot itself is unchanged; the
pin uses the mechanism already in the build.

Verifying the pinned path also surfaced a documented strictness: the
live identity gate re-validates the configured pin and fails closed
(exit 5) if a pinned LIVE process somehow reached an account read
without first attaching through `mt5_init()` — impossible in the
shipped startup order, where every entry initializes first. The
offline harnesses now mirror that production attach order
(`_mt5_initialize()` immediately after installing the fake), which is
what made the full pinned battery representative.

## 13. v3.9.1 — continuity-chain repairs and the pre-commit reproof

Independent adversarial testing proved four real defects that the
earlier battery missed (its continuity suite asserted only the
fail-closed refusal and never drove an export to success). Each is
repaired at root cause; no validator was weakened:

* **A clean P1 completion could never export continuity.** The
  process-wide repaired-from-seed latch — set at the virgin seed
  install — still blocked the export baseline after all 20 window rows
  had become dated live-account observations, and the completion path
  then wrote a PERMANENT `AUDIT_REQUIRED` marker onto the aligned,
  pending-free folder. Export sites now consult the window's own dated
  provenance (`_window_live_proven`), and an aligned clean completion
  defers continuity preparation to `--export-continuity` instead of
  poisoning the folder. Ambiguous completions still audit-lock.
* **Startup identity ordering.** The continuity-transaction validator
  (and the legacy V380 watch validator) compared stored identity
  against `EXPECTED_LOGIN/SERVER`, which bind only after MT5 attach —
  so a completed folder carrying a PREPARED transaction reloaded
  CUSTODY-ONLY on every restart. Load-time validation now judges the
  image against its own bound `mt5_identity`; the boot identity gate
  still refuses a wrong live account before any order.
* **Legitimate leading BTC missing history was rejected.** BTC's
  through-vector legitimately begins ~2,500 sessions into the master
  calendar; the all-finite digest refused it, so the terminal fold
  could never be proven. The digest now binds the counted
  leading-missing prefix plus the exact finite suffix; interior or
  trailing gaps still refuse.
* **The r4 migration proved inventory only once.** The commit now
  re-maps every live ticket into the committed takeover inventory
  IMMEDIATELY before committing: a new, grown, reversed or foreign
  ticket refuses the commit and the migration waits under custody
  rails; pure reductions remain acceptable.
* Target completion now double-saves, landing the permanent hit in
  BOTH recovery images at commit time (previously the second image
  relied on incidental later saves).
* Documentation corrected: `--yes` skips confirmation unconditionally
  (virgin starts included); the deliberate isolated startup re-exec is
  documented; the migration-wait custody semantics are stated
  precisely (hard-loss rails and broker-side protections during the
  wait; strategy servicing after COMMITTED).

test_continuity_chain now proves the REAL end-to-end chain (campaign →
aligned completion with a PREPARED transaction → export writes the
hash-enveloped artifact → re-export non-destructive → tampered envelope
refused → fresh P2-gated adoption with the continuity identity sealed
and rearm consumed once). test_r4_migration adds the pre-commit
reproof attack (a 5th apparently-bot-owned ticket after
INVENTORY_PROVED refuses the commit; removal commits cleanly).

## 14. v3.9.2 — adversarial re-review of the v3.9.1 repairs

A 51-agent adversarial review of the v3.9.1 diff (every finding
attacked by two independent refuters) confirmed that two of the
repairs were themselves incomplete, plus latent gaps; all fixed:

* **Window provenance is now UNCONDITIONAL.** v3.9.1 consulted
  `_window_live_proven` only while the process-local repaired-from-seed
  latch was set — but only the virgin bootstrap process ever sets the
  latch, so a restarted process (including the documented separate
  `--export-continuity` run) skipped provenance entirely and could have
  exported a window still containing seed rows as live history. All
  three export sites now refuse whenever the 20-window is not fully
  dated live-account provenance, latch or no latch.
* **Completion deferral is provably reconstructible.** `aligned_clean`
  now additionally requires the export baseline to be constructible at
  the hit (which includes full live provenance); an early hit whose
  window still contains seed rows receives the permanent audit marker
  loudly instead of deferring to an export that must refuse.
* **The exporter can actually reconstruct a deferred handoff.** The
  continuity transaction's producer recipe now derives from the
  FOLDER's lifecycle binding, never the running process's CLI verb —
  the export process runs as recipe "export" and could previously never
  mint the transaction the deferral promised.
* **The legacy V380 watch validator is now fail-closed and
  image-self-consistent**: the identity comparison is unconditional
  (like the export-transaction validator), and every load-time call
  site threads the owning image through instead of None.
* **The r4 inventory proof is identity/cash-bound and
  duplicate-safe**: the read is sandwiched between two verified
  account witnesses (same login/server/balance or the proof refuses;
  a wrong account halts), and duplicate ticket/identifier rows refuse
  the proof (split-volume growth can no longer slip the per-row cap).
* Digest-format note: v3.9.2's through-history digests differ from
  v3.9.0/v3.9.1 byte layouts. No upgrade path is required — those
  builds were never deployed (the only live predecessor is the V389 r4
  build, whose supplied state carries no step records; verified), and
  a hypothetical old-format step record fails closed as a WAIT, never
  silently passes.

## 15. v3.9.3 — post-commit cashflow survival, commit cash reproof, fast passes

Independent testing of v3.9.2 found three release blockers; all
verified real and repaired:

* **The V389 cashflow exception now survives the migration commit.**
  The exception's profile required a LIVE `_predecessor_takeover`, but
  the commit archives that record — so the exact broker history that
  qualified before the commit (the real account's disordered OANDA
  backfill, which V386's complete-history cash equation cannot explain)
  became CASHFLOW UNKNOWN forever after the handoff.
  `_cashflow_incident_context` now evaluates the exception against the
  committed migration's receipt-verified archive: the same history
  clears identically before and after the commit, proven by a suite
  case with a disordered-history shape plus a control showing the
  archive view is exactly what preserves tradability.
* **The commit re-proves cash and deal history, not just tickets.**
  The migration record captures the PREPARED-time verified balance;
  the commit requires the CURRENT verified balance to equal it plus
  the cash of bot-owned deals inside the migration window. An
  unexplained $1,000 balance change or a manual deal after
  LEDGER_REBUILT now refuses the commit (both suite-proved); custody
  rail closes remain explained.
* **Fast challenge passes continue (v3.9.2 regression).** The
  all-live-window export requirement audit-locked any completion
  before 20 live sessions — a real P1 pass takes ~13. The continuity
  payload has always carried the complete dated ledger with per-row
  provenance, and BOTH producer and adopter prove the windows against
  it, so a mixed seed/live window travels honestly. The export gates
  now rest on that dated-ledger proof; nothing is relabeled as live; a
  fast pass PREPARES at completion, exports, and is adopted by a fresh
  P2-gated folder (suite-proved end-to-end). A hit before ANY
  completed live session still audit-locks loudly.

## 16. v3.9.4 — the commit cash reproof made sound

Tracing the exact live startup for the operator exposed three defects in
the v3.9.3 cash/deal-history reproof. Each causes a FALSE refusal —
fail-closed, no money risk — but each would stall the one-time migration
permanently, leaving the account under custody rails with new risk
blocked and no way forward:

* **Wrong time base.** The reproof queried `history_deals_get` with raw
  UTC bounds while every other history query in this build encodes its
  bounds into the BROKER server epoch via `_mt5_query_datetime`. On a
  broker whose server time is offset from UTC (OANDA is), the window
  does not align with the deal timestamps at all and can sweep hours of
  prior owned deals into the arithmetic — refusing forever.
* **Double-counted pre-baseline deals.** The window opened 60 seconds
  BEFORE the PREPARED balance capture, so an owned deal settled in that
  span sat inside `start_balance_cents` AND was added again to the
  expected total.
* **Broker fee rows blocked the commit.** Every non-owned row refused,
  but swap/interest/commission rows carry magic 0 and position 0. OANDA
  posts them at rollover — exactly when an operator may hand off — and
  because the window's end grows with the clock, the refusal never
  cleared.

The reproof now encodes both bounds through `_mt5_query_datetime`,
starts at the PREPARED capture itself, and classifies non-owned rows
with the build's own `_external_cashflow_type_policy`: foreign BUY/SELL
trades and external cash (balance, credit, charge, correction, bonus)
refuse the commit; broker fee/interest/dividend/tax rows have their cash
counted and never block. Suite 85 → 87: a broker swap row commits
(counted), a deposit still refuses even when the balance agrees with it,
and the $1,000 balance change and manual-deal refusals are unchanged.

## Retained unchanged

The complete V389 safety engine: crash-safe double-image state with
digest-verified recovery, exactly-once order/close intents, account
singleton and identity gates, external-cashflow guard, broker-epoch
qualification, Prague anchor proofs and rails (floor/daily/breaker),
NY17 session calendar and day-roll transactions, pinned full-history
seed authority, target watch/hit machinery, continuity export/import,
ORB engine, and the magic namespace `v380-final-380371300/1` (the live
tickets carry it).
