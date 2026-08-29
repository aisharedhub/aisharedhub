"""Ctrl+C managed flatten (build order sections 18 and 20).

The first interrupt becomes a managed close-only service that stays
attached until the account proves flat/orderless — never an exposed
process exit.  With an unresponsive broker the service refuses to call
shutdown safe and retains exposure authority.

Run: python test_interrupt.py
"""
import contextlib
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fakemt5
import orderharness as oh

PASS = [0]
FAIL = [0]


def ok(cond, label):
    if cond:
        PASS[0] += 1
    else:
        FAIL[0] += 1
        print(f"FAIL: {label}")


def owned(fake, b, ticket, name, symbol, lots):
    return fakemt5._Obj(ticket=ticket, identifier=ticket,
                        magic=b.MAGIC[name], symbol=symbol, volume=lots,
                        type=fake.POSITION_TYPE_BUY, price_open=100.0,
                        time=0)


# ---- 1. managed interrupt closes everything, then shutdown is safe ----
b, fake, st, wd = oh.boot()
fake.positions = [owned(fake, b, 801, "XAUM", "XAUUSD.sim", 0.10),
                  owned(fake, b, 802, "BTC", "BTCUSD.sim", 0.50)]


def exec_close(req):
    if req.get("action") == fake.TRADE_ACTION_DEAL and "position" in req:
        fake.positions = [p for p in fake.positions
                          if p.ticket != req["position"]]
        return fakemt5._Obj(retcode=fake.TRADE_RETCODE_DONE,
                            order=req["position"] + 10,
                            deal=req["position"] + 20,
                            volume=req.get("volume", 0.0),
                            price=fake.ticks[req["symbol"]].bid,
                            comment="closed", request_id=1)
    return None


fake.send_result = exec_close
b._TEST_INTERRUPT_MAX_POLLS = 12
_mono = [5000.0]


def _quiet_clock():
    _mono[0] += 35.0          # two flat passes span the 60s quiet proof
    return _mono[0]


b._TEST_INTERRUPT_MONO = _quiet_clock
with contextlib.redirect_stdout(io.StringIO()):
    done = b._interrupt_close_until_flat(st)
ok(done is True, "managed interrupt proves flat and authorizes shutdown")
ok(fake.positions == [], "every owned ticket closed")
closed = {r.get("position") for r in fake.sent if "position" in r}
ok(closed == {801, 802}, f"closes are exact-ticket ({sorted(closed)})")
ok("_close_only_halt" not in st,
   "keyboard close-only halt clears only after authoritative flat proof")
opens = [r for r in fake.sent if "position" not in r
         and r.get("action") == fake.TRADE_ACTION_DEAL]
ok(len(opens) == 0, "interrupt service never opens exposure")

# ---- 2. unresponsive broker: shutdown stays UNSAFE, exposure retained ----
b2, fake2, st2, _ = oh.boot()
fake2.positions = [owned(fake2, b2, 811, "XAUM", "XAUUSD.sim", 0.10)]
fake2.send_result = None                     # broker never answers
b2._TEST_INTERRUPT_MAX_POLLS = 4
with contextlib.redirect_stdout(io.StringIO()):
    done2 = b2._interrupt_close_until_flat(st2)
ok(done2 is False,
   "unproved flatness NEVER reports a safe shutdown")
ok(len(fake2.positions) == 1,
   "exposure is retained, not abandoned, while the broker is silent")
ok("_close_only_halt" in st2,
   "the close-only halt persists for the native resume to reconcile")

print(f"test_interrupt: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
