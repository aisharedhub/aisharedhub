"""ORB behavior matrix (build order sections 10 and 20) on the REAL engine.

Each scenario drives _main_impl on an authorized live process (Monday
campaign via startharness) into Tuesday's opening range with crafted M5
evidence: six-bar range + first-breakout entry with exact SL/TP and
verified protection, one-event-per-day, EOD flat, missing/duplicate-bar
refusals, expired entry window, drift cap, and range-too-small.

Run: python test_orb_matrix.py   (takes several minutes)
"""
import contextlib
import io
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
D0 = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp())


def boot_authorized():
    b, fake, market, broker, wd = sh.boot(P2)
    quiet(sh.drive_to_authorized, b, market)
    return b, fake, market


def bar(minute, o, h, l, c):
    return (D0 + minute * 60, o, h, l, c)


def install_orb_day(b, fake, market, grid):
    rows = [r for r in fake.rates_m5["US100.sim"]
            if not (D0 <= r[0] < D0 + 86400)]
    fake.rates_m5["US100.sim"] = rows + grid


def range_grid(base, hi, lo, breakout=True, drop=None, dup=None):
    minutes = [870, 875, 880, 885, 890, 895]
    tmpl = [(base, hi, lo, base + 10), (base + 10, hi - 5, lo + 5, base),
            (base, hi - 2, lo + 2, base + 5), (base + 5, hi, lo + 10,
                                               base - 5),
            (base - 5, hi - 8, lo, base + 8), (base + 8, hi - 1, lo + 4,
                                               base + 2)]
    grid = []
    for minute, (o, h, l, c) in zip(minutes, tmpl):
        if drop is not None and minute == drop:
            continue
        grid.append(bar(minute, o, h, l, c))
    if dup is not None:
        grid.append(bar(dup, base, hi - 3, lo + 3, base + 1))
    if breakout:
        grid.append(bar(900, base + 2, hi + 25, base, hi + 20))
        grid.append(bar(905, hi + 20, hi + 22, hi + 18, hi + 21))
    return grid


def orb_sends(b, fake):
    return [r for r in fake.sent if r.get("magic") == b.MAGIC["ORB"]]


# ========== A. six-bar range, first breakout, exact SL/TP, 5R ==========
b, fake, market = boot_authorized()
base = round(market.closes["US100.sim"][-1], 1)
hi, lo = base + 60.0, base - 40.0
install_orb_day(b, fake, market, range_grid(base, hi, lo))
sh.set_clock(b, utc(2026, 9, 1, 15, 5, 6))
fake.ticks["US100.sim"] = sh.grid_tick("US100.sim", hi + 20.4,
                                       int(b._TEST_WALL_TS))
quiet(sh.run_polls, b, market, 4, refresh=False)
st = b._RUNTIME_STATE[0]
orb = st.get("orb") or {}
ok(orb.get("hi") == hi and orb.get("lo") == lo,
   f"six-bar opening range proved exactly (hi {orb.get('hi')} lo "
   f"{orb.get('lo')})")
sends = orb_sends(b, fake)
ok(len(sends) == 1, f"first valid breakout entered once ({len(sends)})")
req = sends[0] if sends else {}
ok(req.get("sl") == lo, "stop is the opposite side of the range, exactly")
entry = float(req.get("price", 0.0))
risk = entry - float(req.get("sl", 0.0))
ok(abs(float(req.get("tp", 0.0)) - (entry + 5.0 * risk)) < 1e-6,
   f"take profit is exactly entry + 5R (tp {req.get('tp')})")
pos = [p for p in fake.positions if p.magic == b.MAGIC["ORB"]]
ok(len(pos) == 1 and pos[0].sl == req.get("sl")
   and pos[0].tp == req.get("tp"),
   "fill carries the verified SL/TP protection")
notional = float(req.get("volume", 0.0)) * entry
ok(notional <= 5.0 * 200000.0 + 1e-6,
   f"5x ORB inner leverage cap holds ({notional/200000.0:.2f}x)")
ok(orb.get("done") is True, "day sealed before intent release")
ok("_order_intent" not in st, "ORB intent resolved with protection proof")

# one valid ORB event per day: later polls never re-enter
quiet(sh.run_polls, b, market, 3, refresh=False)
ok(len(orb_sends(b, fake)) == 1, "one ORB event per day (no re-entry)")

# ---------- B. EOD flat: the ORB ticket is closed by the cutoff ----------
sh.set_clock(b, utc(2026, 9, 1, 20, 56, 0))
fake.ticks["US100.sim"] = sh.grid_tick("US100.sim", hi + 30.0,
                                       int(b._TEST_WALL_TS))
quiet(sh.run_polls, b, market, 6, refresh=False)
still = [p for p in fake.positions if p.magic == b.MAGIC["ORB"]]
if still:
    sh.set_clock(b, utc(2026, 9, 1, 21, 0, 30))
    quiet(sh.run_polls, b, market, 6, refresh=False)
    still = [p for p in fake.positions if p.magic == b.MAGIC["ORB"]]
ok(not still, "EOD flat: the ORB ticket is closed at the session cutoff")
closes = [r for r in fake.sent
          if "position" in r and r.get("symbol") == "US100.sim"]
ok(len(closes) >= 1 and closes[-1].get("position") == pos[0].ticket,
   "EOD close is exact-ticket")

# ============== C. missing bar: no trade, loud stand-down ==============
b2, fake2, market2 = boot_authorized()
base2 = round(market2.closes["US100.sim"][-1], 1)
install_orb_day(b2, fake2, market2,
                range_grid(base2, base2 + 60, base2 - 40, drop=880))
sh.set_clock(b2, utc(2026, 9, 1, 15, 5, 6))
fake2.ticks["US100.sim"] = sh.grid_tick("US100.sim", base2 + 80.4,
                                        int(b2._TEST_WALL_TS))
quiet(sh.run_polls, b2, market2, 4, refresh=False)
ok(len(orb_sends(b2, fake2)) == 0,
   "a missing range bar can NEVER become a trade")

# ============ D. duplicate bar timestamp: no trade either ============
b3, fake3, market3 = boot_authorized()
base3 = round(market3.closes["US100.sim"][-1], 1)
install_orb_day(b3, fake3, market3,
                range_grid(base3, base3 + 60, base3 - 40, dup=875))
sh.set_clock(b3, utc(2026, 9, 1, 15, 5, 6))
fake3.ticks["US100.sim"] = sh.grid_tick("US100.sim", base3 + 80.4,
                                        int(b3._TEST_WALL_TS))
quiet(sh.run_polls, b3, market3, 4, refresh=False)
ok(len(orb_sends(b3, fake3)) == 0,
   "a duplicated range bar can NEVER become a trade")

# ====== E. expired entry window: no late chase after the ~30s grace ======
b4, fake4, market4 = boot_authorized()
base4 = round(market4.closes["US100.sim"][-1], 1)
hi4, lo4 = base4 + 60.0, base4 - 40.0
install_orb_day(b4, fake4, market4, range_grid(base4, hi4, lo4))
sh.set_clock(b4, utc(2026, 9, 1, 15, 8, 30))   # forming bar is 3.5min old
fake4.ticks["US100.sim"] = sh.grid_tick("US100.sim", hi4 + 20.4,
                                        int(b4._TEST_WALL_TS))
quiet(sh.run_polls, b4, market4, 4, refresh=False)
ok(len(orb_sends(b4, fake4)) == 0,
   "entry authority expires ~30s into the following bar (no late chase)")

# ============== F. drift cap: min(20 ticks, 0.15R), no chase ==============
b5, fake5, market5 = boot_authorized()
base5 = round(market5.closes["US100.sim"][-1], 1)
hi5, lo5 = base5 + 60.0, base5 - 40.0
install_orb_day(b5, fake5, market5, range_grid(base5, hi5, lo5))
sh.set_clock(b5, utc(2026, 9, 1, 15, 5, 6))
fake5.ticks["US100.sim"] = sh.grid_tick("US100.sim", hi5 + 30.0,
                                        int(b5._TEST_WALL_TS))   # 10 pts off
out5 = io.StringIO()
with contextlib.redirect_stdout(out5):
    sh.run_polls(b5, market5, 4, refresh=False)
ok(len(orb_sends(b5, fake5)) == 0,
   "a quote beyond min(20 ticks, 0.15R) of the persisted open never chases")
ok("moved too far" in out5.getvalue(),
   "drift refusal is loud (signal expired, not silently retried)")

# ================= G. range too small: no-trade session =================
b6, fake6, market6 = boot_authorized()
base6 = round(market6.closes["US100.sim"][-1], 1)
flat = [bar(m, base6, base6 + 1.0, base6 - 1.0, base6)
        for m in (870, 875, 880, 885, 890, 895)]
flat.append(bar(900, base6, base6 + 3.0, base6 - 1.0, base6 + 2.5))
flat.append(bar(905, base6 + 2.5, base6 + 3.0, base6 + 2.0, base6 + 2.6))
install_orb_day(b6, fake6, market6, flat)
sh.set_clock(b6, utc(2026, 9, 1, 15, 5, 6))
fake6.ticks["US100.sim"] = sh.grid_tick("US100.sim", base6 + 2.6,
                                        int(b6._TEST_WALL_TS))
out6 = io.StringIO()
with contextlib.redirect_stdout(out6):
    sh.run_polls(b6, market6, 4, refresh=False)
ok(len(orb_sends(b6, fake6)) == 0
   and (b6._RUNTIME_STATE[0].get("orb") or {}).get("done") is True,
   "a sub-minimum opening range stands the session down without a trade")
ok("too small" in out6.getvalue(), "range-too-small stand-down is loud")

print(f"test_orb_matrix: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
