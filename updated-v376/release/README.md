# Updated V376 — MT5 Vol-Targeted Bot v12 (final build v3.9.5-updated-v376)

The frozen V376 five-sleeve strategy (ORB 40% / S8V 10% / BTC 20% /
XAU-mom 10% / XAU-beta 5%, ONF permanently disabled) with V376-style
startup on the hardened V389 safety engine, plus the two verified r4
controller repairs:

* **Defect 1 — undated controller history**: every vol/dip observation
  lives in a dated, provenance-tagged controller ledger (strictly
  ordered sessions, bounded proven gaps, quarantine on any unchainable
  entry). Windows derive from the ledger; a stale parent-seed window can
  never bind again. Unknowable account returns are recorded as omitted —
  never fabricated as zero.
* **Defect 2 — stale applied leverage**: `_last_L` is only ever the
  broker-PROVEN applied daily leverage from a per-sleeve inventory
  reconcile, recorded beside the requested value with per-sleeve
  contribution fractions.

Sizing is **full-or-hold**: an unproved anchor holds increases at zero;
the engine never trades a halved size. The one supplied V389 r4 folder
is adopted exactly once through a dedicated migration (inventory proof,
dated-ledger rebuild, atomic commit, permanent completion); the generic
V383–V388 takeover machinery is removed.

## Requirements

Windows, MetaTrader 5 terminal (no BAT wrapper, no watchdog),
Python 3.11+:

    pip install MetaTrader5 numpy tzdata

Run the bot from its own dedicated folder (this DEFAULT folder). The
folder must contain `vol_target_bot_v12.py`, `shadow_seed.json` and
`shadow_seed_manifest.json` (the seed and its manifest are
hash-pinned in the bot; a missing or altered file is refused at boot).
Flags are accepted in any order; unknown, duplicate, contradictory or
untested values are refused before any MT5 or state access.

## Which terminal does the bot attach to?

This DEFAULT folder is the primary requested build: bare
`mt5.initialize()` — V376-style single-terminal auto-discovery. The
MetaTrader5 module finds the terminal itself: a terminal that is
already running wins; otherwise it launches the registered installed
terminal. With MORE THAN ONE MT5 installation on the machine the choice
belongs to the module, not the bot, so it is not guaranteed to be a
specific installation. The identity gate still refuses a wrong-account
terminal before any state or order access on a bound folder.

For a deterministic attach, the archive also ships two pinned variant
folders — identical to DEFAULT except the ONE documented
`DEFAULT_MT5_PATH` source line:

| Folder | Pinned terminal |
| --- | --- |
| `1/` | `C:\Program Files\MetaTrader 5\terminal64.exe` |
| `2/` | `C:\Program Files\MetaTrader 5 - 2\terminal64.exe` |

Use exactly ONE folder as the live working folder. All commands are
identical in every folder (the pin is not part of the recipe: binding
and resume are unchanged). A pinned path that does not exist refuses
with exit 5 before any attach (fail closed). A final command-line
`--mt5-path "<path>"` — strictly validated, higher priority than the
source default — can also pin any folder's start without editing it.

## Exact commands

Live recipes (each is separately tested and binds permanently to the
lifecycle state; the interpreted recipe is printed before any binding):

    # P1 gated (exact V376 command, real balance as base)
    python vol_target_bot_v12.py --mode grind --phase 1 --start-min-dd 0.02 --start-bounce 0.005 --post-loss-mult 0.75 --live

    # P1 gated with declared capital
    python vol_target_bot_v12.py --mode grind --phase 1 --start-min-dd 0.02 --start-bounce 0.005 --post-loss-mult 0.75 --capital 200000 --live

    # P1 immediate
    python vol_target_bot_v12.py --entry-policy immediate --mode grind --phase 1 --capital 200000 --live

    # P2 gated (requires the exact P1-produced shadow_continuity.json in the folder)
    python vol_target_bot_v12.py --mode grind --phase 2 --start-min-dd 0.01 --start-bounce 0.005 --start-cap 10 --rearm-gate --post-loss-mult 0.75 --capital 200000 --live

    # P2 immediate (standalone; no continuity)
    python vol_target_bot_v12.py --entry-policy immediate --mode grind --phase 2 --capital 200000 --live

A live start asks for the typed confirmation `I ACCEPT LIVE`.
`--yes` skips that confirmation UNCONDITIONALLY — on a virgin first
start as much as on a resume. Reserve it for unattended exact resume of
the identical command; a first start deserves the typed confirmation.

Startup note: the bot deliberately re-executes itself once into an
isolated Python child (`-E -P -B`) before doing anything else — one
extra python process belonging to the same console is normal. Closing
that console window stops the bot without flattening (the V376-style
abrupt stop; resume with the identical command).

Strictly read-only:

    python vol_target_bot_v12.py --diagnose
    python vol_target_bot_v12.py --selfcheck
    python vol_target_bot_v12.py --list-symbols

Durable operational commands:

    python vol_target_bot_v12.py --pause-new-risk      # durable pause at the running bot's next poll
    python vol_target_bot_v12.py --resume-paused       # lifts the pause only after safety-record proof
    python vol_target_bot_v12.py --flatten-and-stop --live   # managed close-everything, then exit (folder stays resumable)
    python vol_target_bot_v12.py --export-continuity   # after permanent P1 target completion;
                                                       # run it after the hit session's NY17 close
                                                       # so the terminal fold can prove a genuinely
                                                       # completed session

Destructive account-wide recovery (never a normal resume):

    python vol_target_bot_v12.py --recover-safety --live

## Capital economics (`--capital 200000`)

| Line | Value |
| --- | --- |
| P1 target | $220,000 |
| P2 target | $210,000 |
| Static floor | $180,000 |
| Daily loss allowance | $10,000 below the proved Prague anchor |
| Breaker (3.5%) | $7,000 below the proved Prague anchor |

`--capital` is the permanent economic base for sizing, target, floor,
daily line, breaker and virtual campaign equity. It never rewrites the
real broker balance, and a resume can never silently change it.

## Resume rules

* Normal resume: same folder, same exact economic command. Existing
  exact bot positions are adopted; every unresolved order/close intent
  reconciles before strategy; increases stay blocked until every proof
  clears, then FULL calculated sizing resumes.
* Fresh start: a flat, orderless account. Unexplained positions are
  never adopted.
* A different recipe on a bound folder is refused without mutation.

## One-time r4 handoff (perform exactly once)

Preconditions — all already verified by the shipped campaign: this
package's tests all pass, the running predecessor is the exact V389 r4
build with the supplied state, and the account is
600092429 @ OANDA-Prop Trader (USD, hedging).

1. **Do not flatten. Do not use Ctrl+C on the old process.** Stop the
   running r4 process with a plain console window close (the abrupt
   console X). The r4 build is designed to resume from that stop; its
   open positions remain untouched on the broker.
2. Verify no bot process remains (Task Manager: no python running
   `vol_target_bot_v12.py`). Only one instance may ever run; the
   account singleton refuses a second.
3. Keep every existing file in the working folder — state, backups and
   recovery evidence are the migration's inputs. Copy
   `vol_target_bot_v12.py`, `shadow_seed.json` and
   `shadow_seed_manifest.json` from this DEFAULT
   folder (or from `1/` or `2/` if the r4 terminal must be pinned — use
   the folder that names the terminal the r4 account runs on)
   over the old ones (replace the bot; keep
   `bot_state_v12.json`, `bot_state_v12.json.bak` and every other file
   in place).
4. Start the final bot with EXACTLY:

       python vol_target_bot_v12.py --entry-policy immediate --mode grind --phase 2 --capital 200000 --live

5. The new bot reconciles and commits the one-time r4 takeover BEFORE
   permitting any new order: it proves the exact source identity, maps
   every live ticket, rebuilds the dated controller ledger from the
   supplied evidence, re-proves the complete live inventory a FINAL
   time immediately before committing (a new, grown, reversed or
   foreign ticket refuses the commit), rebinds the lifecycle, and
   commits atomically to both recovery images. New risk stays blocked
   until the migration is COMMITTED and the anchor re-proves
   (full-or-hold). While the migration owns startup — normally a few
   seconds; longer only when a proof cannot complete — the custody
   rails re-read the account every pass and enforce the SOURCE's own
   hard-loss lines (floor/daily/breaker: a breach flattens
   account-wide), and each inherited position keeps its broker-side
   protections; ordinary strategy servicing (partial reductions, ORB
   timed exits, target handling) begins after COMMITTED, because it
   requires the rebuilt dated ledger. A migration that stays WAITING is
   loudly logged with its exact blocker and is the operator's cue to
   look.
6. The migration is permanently completed after its commit; every later
   restart is a native resume of the same command.

If any migration fact cannot be proved, the bot fails closed, reports
the exact reason, and touches nothing — the old folder remains fully
resumable by the old build.

## Release verification

`MANIFEST.sha256` (in the archive root) lists the SHA-256 of every
member; the archive is deterministic — rebuilding it from identical
inputs is byte-identical. Verify after extraction:

    python -c "import hashlib,sys; [print(hashlib.sha256(open(p,'rb').read()).hexdigest(), p) for p in sys.argv[1:]]" DEFAULT/vol_target_bot_v12.py DEFAULT/shadow_seed.json DEFAULT/shadow_seed_manifest.json

The console prints the bot and seed hashes at startup (informational);
this manifest is the release authority. Maintainer tests and evidence
live under `maintainer/` inside the archive — keep the live working
folder essentials-only (the DEFAULT folder contents).

Nothing here is investment advice.
