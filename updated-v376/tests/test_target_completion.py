"""Target completion (build order section 16) through the real engine.

T1: genuine rally -> equity touches $210k -> durable watch -> account-wide
    exact-ticket closes realize the profit -> flat/cash proofs -> permanent
    TARGET HIT on disk -> process exit -> a restart is permanently complete
    and cannot trade.
T2: touch followed by adverse closes (closed balance below the line) is
    NEVER a false pass: no TARGET HIT, and the temporary watch clears only
    through its paired proof.

Run: python test_target_completion.py   (takes several minutes)
"""
import contextlib
import io
import json
import os
import sys
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


P2 = ["--entry-policy", "immediate", "--mode", "grind", "--phase", "2",
      "--capital", "200000", "--live"]


def campaign_with_book():
    """Authorized process holding the four genuine Monday-lease entries."""
    b, fake, market, broker, wd = sh.boot(P2)
    quiet(sh.drive_to_authorized, b, market)
    sh.set_clock(b, utc(2026, 8, 31, 22, 5, 40))
    quiet(sh.run_polls, b, market, 16)
    assert len(fake.positions) == 4, len(fake.positions)
    return b, fake, market, broker, wd


# ================= T1: touch -> permanent TARGET HIT =================
b, fake, market, broker, wd = campaign_with_book()
for sym in market.closes:
    market.closes[sym][-1] *= 1.05
sh.set_clock(b, utc(2026, 9, 1, 14, 0, 0))
sh.refresh_ticks(b, market)
code = quiet(sh.run_polls, b, market, 60, refresh=False)
st = b._RUNTIME_STATE[0]
hit = st.get("_target_hit")
ok(isinstance(hit, dict) and hit.get("status") == "TARGET_HIT"
   and hit.get("schema") == "target_hit/2" and hit.get("stage") == "p2",
   f"permanent TARGET HIT committed "
   f"({(hit or {}).get('status')}/{(hit or {}).get('schema')})")
ok(isinstance(hit, dict)
   and hit.get("closed_balance_cents", 0) >= hit.get("target_line_cents", 1),
   "closed balance at/above the exact target line "
   f"({(hit or {}).get('closed_balance_cents')})")
ok(len(fake.positions) == 0 and len(fake.orders) == 0,
   "account proved flat and orderless before the lock")
closes = [r for r in fake.sent if "position" in r]
ok(len(closes) == 4 and {r["position"] for r in closes}
   == {5012, 5022, 5032, 5042},
   "every ticket closed exact-ticket by the watch")
ok(fake.account.balance >= 210000.0,
   f"realized cash {fake.account.balance} >= 210,000")
disk = json.load(open(os.path.join(wd, "bot_state_v12.json")))
bak = json.load(open(os.path.join(wd, "bot_state_v12.json.bak")))
ok("_target_hit" in disk and "_target_hit" in bak,
   "TARGET HIT committed to BOTH recovery images")
ok(code == 0 or code is None,
   f"completion path exits cleanly or holds its final watch ({code})")

# a restart is permanently completed and cannot trade
b2, fake2, market2, broker2, _ = sh.boot(P2, workdir=wd)
fake2.account.balance = fake.account.balance
sh.set_clock(b2, utc(2026, 9, 1, 15, 0, 0))
market2.grow()
code2 = quiet(sh.run_polls, b2, market2, 8)
st2 = b2._RUNTIME_STATE[0]
ok(isinstance((st2 or {}).get("_target_hit"), dict)
   or code2 not in (None,),
   "restart still carries the permanent completion")
ok(len(fake2.sent) == 0, "a completed campaign can never trade again")

# ============ T2: failed realization is never a false pass ============
b3, fake3, market3, broker3, wd3 = campaign_with_book()
# touch: a rally lifts floating equity just over the line
for sym in market3.closes:
    market3.closes[sym][-1] *= 1.045
sh.set_clock(b3, utc(2026, 9, 1, 14, 0, 0))
sh.refresh_ticks(b3, market3)
quiet(sh.run_polls, b3, market3, 2, refresh=False)
st3 = b3._RUNTIME_STATE[0]
touched = "_target_flat_watch" in st3 or "_target_hit" in st3
# adverse move while the watch closes: realization lands below the line
for sym in market3.closes:
    market3.closes[sym][-1] *= 0.97
sh.refresh_ticks(b3, market3)
quiet(sh.run_polls, b3, market3, 60, refresh=False)
st3 = b3._RUNTIME_STATE[0]
ok(touched, "equity touch persisted a durable watch before broker action")
ok("_target_hit" not in st3,
   f"closed balance {fake3.account.balance} below the line NEVER "
   "passes falsely")
ok(fake3.account.balance < 210000.0, "realization genuinely failed")
disk3 = json.load(open(os.path.join(wd3, "bot_state_v12.json")))
ok("_target_hit" not in disk3, "no false pass on disk either")
ok(len(fake3.positions) == 0,
   "the watch still flattened the book (protective close-out)")

print(f"test_target_completion: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
