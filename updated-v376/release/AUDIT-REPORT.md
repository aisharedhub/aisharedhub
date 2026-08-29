# Updated V376 — Handoff Verification Audit Report

Scope: a relayed failure report claimed the package's one-time r4
handoff is incompatible with the supplied live state. This report
records the claim-by-claim verification against the actual supplied
evidence, performed entirely offline on temporary copies — no MT5
connection, no broker sends, the supplied state and archives opened
strictly read-only and never modified.

## Supplied evidence (SHA-256)

| File | SHA-256 |
| --- | --- |
| bot_state_v12.json | `7d96dccee3923b7ea7cc868e986eaedf36f33a874fe15714ceff533562c932cf` |
| bot_state_v12.json.bak | `f01668d9074d00d0af96edb80931c867a99a907cbc16fcb60fab0cab9e9cd6ba` |
| 376.zip | `3d5132f88516572461e047dbd875a711949fd46288e99a12028ba58cd8329390` |
| V389.zip | `96d76bf50de0109362ff3e3704a2096e25c13bb64ce672b7f91bb02d039335b9` |

The two recovery images differ ONLY in `_state_image.generation`
(29490 vs 29489) — the normal crash-safe double-image pattern with the
backup one save behind. There is no backup mismatch.

## Source identities — all four verified

| Quoted identity | Where it actually is |
| --- | --- |
| `07516a8c…4afb9a97` (trusted V376) | `bot/vol_target_bot_v12.py` and `vps/vol_target_bot_v12.py` inside `vol_target_v12_v376_full.zip` within 376.zip |
| `0fe625e8…5eba6c27bb` (r4 folder-1) | `V389/1/vol_target_bot_v12.py` in V389.zip |
| `083435ea…c26bfca5d22ca` (r4 DEFAULT) | `V389/DEFAULT/vol_target_bot_v12.py` in V389.zip |
| `44b17a2f…bcd32db2b0c` (authority) | `_lifecycle_binding.direct_authority_sha256` in the supplied state — identical to the build's pinned `_V389_R4_DIRECT_AUTHORITY_SHA256`, accepted ONLY as the one-time migration source |

## Claimed state vs the actual supplied state

| Report claim | Actual supplied state (both images) |
| --- | --- |
| `_predecessor_takeover.stage = ANCHOR_WAIT` | `COMMITTED` |
| `_predecessor_takeover.status = ACTIVE` | `COMMITTED` |
| `_predecessor_takeover.anchor_status = UNPROVED` | `PROVED` |
| `_v389_takeover_ledger_bridge` absent | present, `status = COMMITTED`, full SHA chain valid |
| `_v389_capital_transition` exists | exists (matches) |
| `_r4_migration` absent | absent — correct: this record is CREATED by the new bot's one-time migration |
| binding `/10`, recipe `p2-standalone-immediate`, account 600092429 / OANDA-Prop Trader, four bot-owned positions | matches (tickets 30956569 / 30956572 / 30956577 / 30956589 under the bot magic namespace) |

A full recursive scan of the state found NO record anywhere — top-level
or nested — carrying `ANCHOR_WAIT`, `ACTIVE`, or `UNPROVED`. The two
embedded `candidate_images` are historical `/6`-era bodies with no
takeover record at all. Committed takeover markers are monotonic: a
live folder cannot regress from `COMMITTED` to `ANCHOR_WAIT`, so the
claimed state cannot be a later version of this folder either.

## Claimed test failures vs actual results

Fresh sequential battery from the pristine baseline
(`DEFAULT/vol_target_bot_v12.py` = `8b680bf9…fe49201d`), evidence
attached, no handoff test skipped:

| Report claim | Actual |
| --- | --- |
| test_r4_migration refuses/fails | passes (full stage-by-stage migration of the EXACT supplied state, interruption + resume at every stage, zero sends) |
| test_binding_schema fails (bridge missing) | 23 pass, 0 fail (the bridge is present and valid) |
| test_console_status fails (migration state missing) | 19 pass, 0 fail |
| test_operator_commands has five failures | 70 pass, 0 fail |
| 777/777 not reproducible from the supplied state | reproduced exactly; the battery total is now higher only because this round ADDED checks (see TEST-RESULTS.md) |
| run_mutations baseline unclear | 15/15 mutants KILLED from a green pristine baseline |

## Verdict

The reported incompatibility does not exist in the supplied evidence.
The supplied r4 state is exactly the committed, bridge-complete shape
the one-time migration was built for, and it migrates: the maintainer
battery drives the real migration end to end against this exact state
(PREPARED → INVENTORY_PROVED → LEDGER_REBUILT → COMMITTED) with all
new risk blocked throughout, reductions/protective closes available,
atomic double-image commit, and idempotent resume after interruption
at every stage.

**Migratability statement:** the supplied r4 state is MIGRATABLE as
supplied. IF a folder were ever presented mid-takeover (the state the
report described), this build refuses fail-closed: no migration record
is written, nothing is sent, all new risk stays blocked, the console
names the exact blocker (`predecessor takeover anchor_wait`), and the
folder is left byte-for-byte for the predecessor build — such a
takeover must first be completed under the old r4 bot. This refusal
path is now permanently proved by test_r4_migration against a
synthesized mid-takeover variant of the real state and a
bridge-absent variant (nothing was fabricated as evidence; the
synthesized states exist only to prove the refusal).

## Changes shipped from this round (bot unchanged)

* test_r4_migration: the two refusal proofs above (64 → 72 checks).
* Evidence-gated suites now default to the portable `evidence/`
  directory beside `tests/` (`UPDATED_V376_EVIDENCE_DIR` still takes
  priority); a machine-specific absolute path had been baked into four
  test files.
* This audit report added to the archive.

No validator was weakened, no stage was skipped, no bridge or anchor
was fabricated, and omitted account returns remain recorded as omitted.

---

# Round 2 — adversarial re-test of v3.9.0 (claims substantially TRUE)

A second independent report challenged the v3.9.0 certification. Unlike
round 1, verification CONFIRMED its critical findings; v3.9.1 repairs
them. Verdict by claim:

| Claim | Verdict |
| --- | --- |
| P1 cannot produce the continuity file required by P2 gated; the advertised test expects exit 8, verifies no file, never launches P2 | **TRUE.** The suite asserted only the fail-closed refusal. Root causes: the repaired-from-seed latch blocked the export baseline for the whole producing process even after the window became fully live, and the completion path then permanently audit-locked the clean folder. Repaired; the suite now drives the REAL chain to a written, adopted artifact. |
| …including startup identity ordering | **TRUE.** `EXPECTED_LOGIN/SERVER` are bound only after MT5 attach, but the continuity-transaction validator used them at state-load time — any completed folder with a PREPARED transaction reloaded custody-only. Repaired (image-self-consistent validation pre-bind; live identity gate unchanged). |
| …and rejection of legitimate leading BTC missing-history values | **TRUE.** BTC's ~2,500 legitimate pre-listing sessions failed the all-finite through-vector digest; the terminal fold could never be proven. Repaired (counted leading-missing prefix + exact finite suffix; interior gaps still refuse). |
| The migration proves inventory only once; a ticket added after INVENTORY_PROVED still commits | **TRUE.** Reproduced exactly. Repaired: a final full inventory re-map runs immediately before commit; the attack now refuses the commit and the migration waits under custody rails. Proven by a permanent suite case. |
| During the migration wait, strategy reductions / ORB timed exits / target handling are not serviced, contrary to the instructions | **TRUE as to the instructions** — the README overpromised ("rails, reductions and closes are live from the first poll"). The behavior itself is the safe design: strategy servicing requires the rebuilt dated ledger, so the wait services hard-loss custody rails (account-wide flatten on floor/daily/breaker breach) plus inherited broker-side protections, and full servicing begins at COMMITTED (normally seconds). The README now states exactly this. |
| `--yes` also bypasses confirmation on virgin starts | **TRUE.** V376-parity behavior; the README implied a resume-only scope. Documentation corrected (behavior unchanged). |
| Startup re-executes into another Python process | **TRUE.** The deliberate isolated re-exec (`-E -P -B`); now documented. |
| The seed ends August 7 with a post-seed bridge | **TRUE and by design.** The pinned seed's last session is 2026-08-07; the gap to the live frontier is reconstructed causally at bind from broker D1 history (and, for a P2 adoption, from the continuity frontier). |
| The 785/785 result missed these defects | **TRUE.** The checks were genuine but the continuity suite certified a refusal path as if it were the feature. The v3.9.1 battery result in TEST-RESULTS.md supersedes it, including the end-to-end continuity chain and the reproof attack. |

Verification and repair were performed offline on temporary copies with
the inert fake MT5; the supplied state and archives remained read-only;
zero broker sends everywhere.

---

# Round 3 — line-by-line adversarial recheck of v3.9.1 itself (→ v3.9.2)

At the operator's direction the v3.9.1 diff was re-reviewed line by
line by a 51-agent adversarial battery (six diff lenses plus three
defect-class hunters; every finding attacked by two independent
refuters). Seventeen confirmed findings deduplicate to seven distinct
defects — including one HIGH defect inside the v3.9.1 repair itself —
all fixed in v3.9.2:

| Defect | Repair |
| --- | --- |
| The window-provenance check was consulted only while the process-local repaired-from-seed latch was set; only the virgin bootstrap process ever sets it, so a restarted process (including the documented separate `--export-continuity` run) skipped provenance entirely and could export a seed-contaminated window as live history (HIGH) | Provenance is unconditional at all three export sites: export refuses whenever the 20-window is not fully dated live-account rows, latch or no latch |
| The completion deferral could strand shapes the exporter must refuse, or that it could never reconstruct | `aligned_clean` additionally requires the export baseline to be constructible at the hit; anything else receives the LOUD permanent audit marker |
| The exporter could never mint a deferred transaction: the producer-recipe check read the running process's CLI verb ("export"), not the folder's binding | The producer recipe derives from the folder's lifecycle binding |
| The legacy V380 watch validator skipped its identity check entirely pre-bind (fail-open) and its load-time call sites passed None while holding the image | Unconditional identity compare (like the txn validator) with the owning image threaded through every call site |
| The migration inventory proof accepted duplicate rows sharing one committed identifier (split-volume growth) and carried no account witness | Duplicate ticket/identifier rows refuse the proof; the read is sandwiched between two verified account witnesses (same login/server/balance, wrong account halts) |
| CHANGES.md still declared v3.9.0 and denied the `--mt5-path` flag and the startup re-exec | Both corrected |
| Digest-format change unversioned vs v3.9.0/v3.9.1 step records | Documented: those builds were never deployed (the only live predecessor is V389 r4, whose supplied state carries no step records — verified); a hypothetical old step fails closed as WAIT, never silently passes |

New permanent proofs: the deferral-reconstruction chain (transient
constructor failure at an exportable hit → clean deferral → the export
command reconstructs under the binding recipe and writes the artifact),
the loud early-hit audit classification, and the duplicate-row refusal.
The full battery for the v3.9.2 build is recorded in TEST-RESULTS.md.

---

# Round 4 — v3.9.2 release blockers (→ v3.9.3)

Independent testing of v3.9.2 reported three release blockers. All
three were verified REAL and are repaired in v3.9.3:

| Claim | Verdict and repair |
| --- | --- |
| The r4 cashflow migration breaks after commit: history that passes the V389 exception becomes CASHFLOW UNKNOWN once the takeover records are archived | **TRUE.** The exception's profile required a LIVE takeover record; the commit pops it into the archive, and ownership fell back to V386's complete-history cash equation — which the real account's disordered OANDA backfill can never satisfy. `_cashflow_incident_context` now evaluates the exception against the commit's receipt-verified archive: the same history clears identically before and after (suite-proved with a disordered-history shape plus a no-archive control). |
| The final migration proof accepts cash/history changes ($1,000 balance change; manual XAU deal after LEDGER_REBUILT still committed) | **TRUE.** The v3.9.2 sandwich proved read-stability only. The record now captures the PREPARED-time verified balance and the commit requires the current verified balance to equal it plus the cash of bot-owned deals inside the migration window; both attacks now refuse the commit (suite-proved) and clear once the account is explained again. |
| Fast challenge passes cannot continue: a target before 20 live sessions becomes permanently AUDIT_REQUIRED (the operator's real P1 took ~13 sessions) | **TRUE — a v3.9.2 regression.** The continuity payload has always carried the complete dated ledger with per-row provenance, proven by both producer and adopter, so a mixed seed/live window travels honestly. The export gates now rest on that dated-ledger proof; a fast pass PREPARES at completion, exports, and is adopted (suite-proved end-to-end). A hit before ANY completed live session still audit-locks loudly. |
| While migration waits, only hard-loss flattening operates | Accurate, by design, and documented since v3.9.1: strategy servicing requires the rebuilt dated ledger and begins at COMMITTED (normally seconds); the wait services the source's hard-loss custody rails and inherited broker-side protections. |
| Three migration checks are unconditional no-ops | **Partly true, but materially misleading — see below.** |

## The "unconditional no-op checks" claim, verified

A dedicated adversarial hunt (three hunters over the migration,
cashflow and continuity-commit paths, each finding attacked by two
independent refuters) examined this claim directly. Result: several
conditions ARE vacuous, but **in every verified case the protection
they appear to provide is genuinely enforced by a stronger check that
runs first**. No claimed protection is absent. The confirmed
redundancies:

| Site | Why it cannot fire | Where the protection actually lives |
| --- | --- | --- |
| `_capture_external_cashflow_guard` — credit re-test in the migration funding qualification | The same tuple element was already required to be 0 earlier in the function | The earlier credit check, plus the BALANCE-code funding-shape test |
| `_qualified_cashflow_guard4_status` — `policy_sha256` cross-checks | Guard validation already pinned the guard's policy digest to the current in-process policy; both snapshots stamp the same pure digest | Guard validation itself (returns "unknown" before this line on any real change) |
| `_cashflow_incident_context` — archive-digest re-verification | `_valid_r4_migration` already verified the archive digest and receipt on the same object | `_valid_r4_migration`'s COMMITTED-stage archive block |
| `_stable_external_cashflow_snapshot` — `policy_sha256` cross-read comparison | Both images are stamped from the same deterministic process constants microseconds apart | The `full` row-image comparison beside it, which does catch a racing history |
| `_r4_live_inventory_proof` — login/server halves of the identity sandwich | `_verified_account_info` HALTS the process (exit 3) on any identity mismatch before returning | That halt; the sandwich's **balance** comparison is the live part and does fire |

These are deliberately retained rather than deleted: each is cheap
belt-and-braces that would become load-bearing if the stronger check
were ever weakened by a refactor, and removing validation from a
safety-critical path at release time carries more risk than the dead
code does. They are documented here so no reader mistakes them for
the protection itself.

## Round 5 — tracing the live startup (→ v3.9.4)

Walking the operator through exactly what the live command does, step by
step, exposed three defects in round 4's own cash/deal-history reproof.
None risks money — all three are false REFUSALS — but each would have
stalled the one-time migration permanently, leaving the account under
custody rails with new risk blocked and no path forward:

| Defect | Why it would stall the handoff | Repair |
| --- | --- | --- |
| The reproof queried `history_deals_get` with raw UTC bounds | Every other history query in this build encodes bounds into the BROKER server epoch via `_mt5_query_datetime`; on a broker offset from UTC (OANDA) the window misses the real rows and can sweep hours of prior owned deals into the arithmetic | Both bounds now go through `_mt5_query_datetime`; unavailable conversion refuses that poll only |
| The window opened 60 s BEFORE the PREPARED balance capture | Owned deals settled in that span were already inside `start_balance_cents` and were added again — a permanent mismatch | The window starts at the capture itself |
| Every non-owned row refused the commit | Broker swap/interest/commission rows carry magic 0 and position 0; OANDA posts them at rollover, exactly when a handoff happens, and the window's growing end meant the refusal never cleared | Non-owned rows are classified with the build's own `_external_cashflow_type_policy`: foreign BUY/SELL and external cash (balance/credit/charge/correction/bonus) refuse; fee/interest/dividend/tax rows have their cash counted and never block |

Proved by suite (85 → 87): a broker swap row commits with its cash
counted; a deposit refuses even when the balance agrees with it; the
$1,000 balance change and manual-deal refusals are unchanged.

Coverage note: 22 of the hunt's 33 agents terminated on a usage limit,
so a subset of candidates (including all migration-path candidates)
received no automated refutation. Those were verified by hand against
the build instead — the authority cross-check and the pre-commit
binding-hash guard both CAN fire on a tampered on-disk record (they
compare stored values against freshly recomputed ones across polls),
so they are live protections, not no-ops.
