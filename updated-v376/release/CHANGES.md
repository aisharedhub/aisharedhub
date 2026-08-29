# Updated V376 — Change Report

Base: the exact supplied V389 r4 DEFAULT build (`vol_target_bot_v12.py`,
BOT_BUILD `v3.8.9-fast-r4`, sha256 `083435ea…`), itself verified as V376
(`v3.7.6`) plus the V389 hardening. Strategy math is bit-identical to
the trusted V376 (`07516a8c…` archive) — proved by executed side-by-side
equivalence, not by inspection alone. Final build: BOT_BUILD
`v3.9.0-updated-v376`.

## 1. V376-style startup (build order §1)

* Bare single-terminal `mt5.initialize()` auto-discovery. No
  `--mt5-path` flag, no BAT wrapper, no watchdog, no re-exec.
* V376-style typed confirmation `I ACCEPT LIVE` for live starts;
  `--yes` documents unattended exact resume.
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

## Retained unchanged

The complete V389 safety engine: crash-safe double-image state with
digest-verified recovery, exactly-once order/close intents, account
singleton and identity gates, external-cashflow guard, broker-epoch
qualification, Prague anchor proofs and rails (floor/daily/breaker),
NY17 session calendar and day-roll transactions, pinned full-history
seed authority, target watch/hit machinery, continuity export/import,
ORB engine, and the magic namespace `v380-final-380371300/1` (the live
tickets carry it).
