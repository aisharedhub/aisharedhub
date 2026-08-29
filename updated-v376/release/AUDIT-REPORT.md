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
