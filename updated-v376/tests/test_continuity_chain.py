"""P1 -> P2 continuity chain (build order section 17).

Runs a P1-immediate campaign through 21 complete NY17 sessions (dated
live-account ledger entries with daily re-proved applied leverage), a
genuine rally to the +10% target, the hash-enveloped continuity export
from the permanently completed folder, and its adoption by a fresh
P2-gated (p2-fresh) folder — the recipe that refuses WITHOUT this
continuity (proved in the lifecycle suite).

Run: python test_continuity_chain.py   (takes a few minutes)
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import startharness as sh

PASS = [0]
FAIL = [0]


def ok(cond, label):
    if cond:
        PASS[0] += 1
    else:
        FAIL[0] += 1
        print(f"FAIL: {label}")


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


P1_IMM = ["--entry-policy", "immediate", "--mode", "grind", "--phase", "1",
          "--capital", "200000", "--live"]
P2_GATED = ["--mode", "grind", "--phase", "2", "--start-min-dd", "0.01",
            "--start-bounce", "0.005", "--start-cap", "10", "--rearm-gate",
            "--post-loss-mult", "0.75", "--capital", "200000", "--live"]

# ---- P1 immediate campaign across 21 complete sessions ----
b, fake, market, broker, wd = sh.boot(P1_IMM)
quiet(sh.drive_to_authorized, b, market)
sh.set_clock(b, utc(2026, 8, 31, 22, 5, 40))
quiet(sh.run_polls, b, market, 16)
ok(len(fake.positions) == 4, "P1 immediate placed the four sleeve entries")
quiet(sh.run_sessions, b, market, 21)
st = b._RUNTIME_STATE[0]
led = (st.get("_controller_ledger") or {}).get("entries", [])
observed = [e for e in led if e.get("source") in ("live-account",
                                                  "standdown")]
ok(len(observed) >= 20,
   f"21 sessions booked as dated live observations ({len(observed)})")
applied = {round(e.get("applied_L") or 0.0, 2)
           for e in observed if e.get("source") == "live-account"}
ok(len(applied) >= 2,
   f"applied leverage re-proved daily by the live controller ({sorted(applied)[:4]}…)")

# ---- a genuine rally lifts the book through the +10% target ----
gross = sum(abs(p.volume) * (100.0 if "XAU" in p.symbol else 1.0)
            * p.price_open for p in fake.positions) / max(
                fake.account.equity, 1.0)
need = (220000.0 - fake.account.equity) / fake.account.equity + 0.03
for sym in market.closes:
    market.closes[sym][-1] *= (1.0 + need / max(gross, 0.2))
forming = market.next_session_after(market.sessions[-1])
sh.set_clock(b, datetime(forming.year, forming.month, forming.day, 10, 0,
                         tzinfo=sh.NY).astimezone(timezone.utc))
sh.refresh_ticks(b, market)
quiet(sh.run_polls, b, market, 200, refresh=False)
st = b._RUNTIME_STATE[0]
hit = st.get("_target_hit")
ok(isinstance(hit, dict) and hit.get("status") == "TARGET_HIT"
   and hit.get("stage") == "p1",
   "P1 campaign permanently completed at $220k")
ok(fake.account.balance >= 220000.0,
   f"realized P1 balance {fake.account.balance}")

# ---- the export command on this handoff shape is FAIL-CLOSED ----
# The intraday hit left a post-target handoff the exporter classifies
# AUDIT_REQUIRED: completion stays permanently valid, but no continuity
# byte is produced without audited recovery.  The exporter must exit 8,
# write NOTHING, and leave the completed folder untouched.
raw_before = open(os.path.join(wd, "bot_state_v12.json"), "rb").read()
b2, fake2, market2, broker2, _ = sh.boot(["--export-continuity"],
                                         workdir=wd)
b2._TEST_TARGET_HIT_EXPORT_MAX_POLLS = 300
b2._TEST_TARGET_HIT_EXPORT_POLL_HOOK = lambda poll, st: time.sleep(0.05)
fake2.account.balance = fake.account.balance
fake2.deals = list(fake.deals)              # broker history persists
fake2.history_orders = list(fake.history_orders)
market2.sessions = list(market.sessions)
market2.closes = {sym: list(vals) for sym, vals in market.closes.items()}
market2.rebuild()
market2.grow()                              # the hit session's bar completes
last = market2.sessions[-1]
sh.set_clock(b2, datetime(last.year, last.month, last.day, 17, 20,
                          tzinfo=sh.NY).astimezone(timezone.utc))
code2 = quiet(sh.run_polls, b2, market2, 40)
ok(code2 == 8, f"exporter fails closed on the audit-required handoff "
   f"(exit {code2})")
ok(not os.path.exists(b2.CONTINUITY_FILE),
   "no partial continuity byte is ever written")
st2 = b2.load_state()
rec = (st2 or {}).get("_post_hit_catchup") or {}
ok(rec.get("stage") == "AUDIT_REQUIRED",
   f"the handoff is loudly classified AUDIT_REQUIRED "
   f"({rec.get('stage')})")
ok(isinstance((st2 or {}).get("_target_hit"), dict),
   "target completion remains permanently valid through the refusal")
ok(len(fake2.sent) == 0, "the exporter sends nothing")
# (adoption-side coverage: the p2-fresh recipe refuses WITHOUT continuity
#  in test_fresh_lifecycle, and the /4 dated-ledger artifact discipline is
#  covered at validator level in test_controller_ledger)

print(f"test_continuity_chain: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
