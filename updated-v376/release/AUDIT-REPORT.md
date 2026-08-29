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
