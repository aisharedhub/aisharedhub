"""Account-ownership, cashflow, persistence and rail protections
(build order sections 6, 9, 12, 14, 15, 20) on the authorized harness.

Each scenario proves a specific fail-closed property of the real code:
foreign/wrong-symbol/pending-order blocks, UNKNOWN inventory, deposits,
save-failure latch, duplicate process, account switch, daily/breaker/
floor rails, the daily-increase lease with no late catch-up, and
reduction/reversal discipline.

Run: python test_protections.py
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


def quiet_send(b, fake, st, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return oh.send_daily(b, fake, st, **kw)


def foreign(fake, ticket=901, magic=12345, symbol="XAUUSD.sim"):
    return fakemt5._Obj(ticket=ticket, identifier=ticket, magic=magic,
                        symbol=symbol, volume=0.10,
                        type=fake.POSITION_TYPE_BUY, price_open=4600.0,
                        time=0)


# ---- 1. manual/foreign position blocks new risk ----
b, fake, st, wd = oh.boot()
fake.positions = [foreign(fake)]
res, _, _ = quiet_send(b, fake, st)
ok(len(fake.sent) == 0, "foreign position: zero sends")
ok(b._ACCOUNT_CONFLICT[0], "foreign position latches the account conflict")
ok("_order_intent" not in st, "foreign position: no intent prepared")

# ---- 2. wrong-symbol bot-magic position blocks new risk ----
b2, fake2, st2, _ = oh.boot()
fake2.positions = [foreign(fake2, magic=b2.MAGIC["XAUM"],
                           symbol="US100.sim")]
quiet_send(b2, fake2, st2)
ok(len(fake2.sent) == 0 and b2._ACCOUNT_CONFLICT[0],
   "wrong-symbol magic position blocks new risk")

# ---- 3. broker pending order blocks new risk ----
b3, fake3, st3, _ = oh.boot()
fake3.orders = [fakemt5._Obj(ticket=911, magic=b3.MAGIC["XAUM"],
                             symbol="XAUUSD.sim", volume=0.05, type=2)]
quiet_send(b3, fake3, st3)
ok(len(fake3.sent) == 0, "pending broker order: zero sends")

# ---- 4. orders_get() failure means UNKNOWN, never empty ----
b4, fake4, st4, _ = oh.boot()
fake4.orders_get = lambda **kw: None
quiet_send(b4, fake4, st4)
ok(len(fake4.sent) == 0, "unreadable pending-order inventory: zero sends")
ok(b4._ORDERS_UNKNOWN[0], "orders UNKNOWN latched")

# ---- 5. positions_get() failure blocks ----
b5, fake5, st5, _ = oh.boot()
fake5.positions_get = lambda **kw: None
quiet_send(b5, fake5, st5)
ok(len(fake5.sent) == 0, "unreadable position inventory: zero sends")

# ---- 6. a deposit after the baseline can never feed strategy ----
b6, fake6, st6, _ = oh.boot()
fake6.deals = [fakemt5._Obj(
    ticket=5001, order=0, position_id=0, magic=0, symbol="", comment="",
    type=fake6.DEAL_TYPE_BALANCE, entry=fake6.DEAL_ENTRY_IN,
    time=int(oh.WALL) - 300, time_msc=(int(oh.WALL) - 300) * 1000,
    volume=0.0, price=0.0, profit=25000.0, commission=0.0, swap=0.0,
    fee=0.0)]
fake6.account.balance = 225000.0
with contextlib.redirect_stdout(io.StringIO()):
    status6 = b6._enforce_external_cashflow_guard(st6, where="test deposit")
ok(status6 != "clear", f"deposit detected ({status6}); strategy held")
quiet_send(b6, fake6, st6)
ok(len(fake6.sent) == 0, "deposit: zero sends")

# ---- 7. save failure latches no-new-risk; next success clears ----
b7, fake7, st7, wd7 = oh.boot()
b7.STATE_FILE = os.path.join(wd7, "missing-dir", "bot_state_v12.json")
quiet_send(b7, fake7, st7)
ok(len(fake7.sent) == 0, "PREPARED save failure: request never sent")
retained = st7.get("_order_intent")
ok(retained is None or retained.get("status") == "PREPARED",
   "an unpersistable prepare is only ever retained conservatively")
b7.STATE_FILE = os.path.join(wd7, "bot_state_v12.json")
with contextlib.redirect_stdout(io.StringIO()):
    b7._rollback_process_known_unsent_intents(st7)
ok("_order_intent" not in st7,
   "process-proved KNOWN-NOT-SENT intent rolls back durably once "
   "persistence recovers")
with contextlib.redirect_stdout(io.StringIO()):
    saved = b7.save_state(st7)
ok(saved is True and not b7._SAVE_FAILED[0],
   "next successful save clears the latch")

# ---- 8. duplicate process refusal (account singleton) ----
b8, fake8, st8, _ = oh.boot()
b8b, fake8b, _, _ = oh.boot()
with contextlib.redirect_stdout(io.StringIO()):
    first = b8._acquire_account_singleton(fake8.account)
    second = b8b._acquire_account_singleton(fake8b.account)
ok(first is True, "first process acquires the account singleton")
ok(second is False, "second process on the same account is refused")

# ---- 9. mid-session account switch halts within one poll ----
b9, fake9, st9, _ = oh.boot()
fake9.account.login = 999999999
halted = False
try:
    with contextlib.redirect_stdout(io.StringIO()):
        b9._verified_account_info("poll head")
except SystemExit as exc:
    halted = exc.code == 3
ok(halted, "account switch halts with exit 3")

# ---- 10. daily rail: send refused below the daily line ----
b10, fake10, st10, _ = oh.boot()
fake10.account.equity = 189000.0          # line: 200000 - 5% of 200k = 190k
fake10.account.margin_free = 189000.0
quiet_send(b10, fake10, st10)
ok(len(fake10.sent) == 0, "equity below the $10k daily line: zero sends")

# ---- 11. breaker: fire flattens, stands down today+next day ----
b11, fake11, st11, _ = oh.boot()
pos = fakemt5._Obj(ticket=921, identifier=921, magic=b11.MAGIC["XAUM"],
                   symbol="XAUUSD.sim", volume=0.08,
                   type=fake11.POSITION_TYPE_BUY, price_open=4610.0, time=0)
fake11.positions = [pos]


def exec_close(req):
    if (req.get("action") == fake11.TRADE_ACTION_DEAL
            and "position" in req):
        fake11.positions = [p for p in fake11.positions
                            if p.ticket != req["position"]]
        return fakemt5._Obj(retcode=fake11.TRADE_RETCODE_DONE,
                            order=req["position"] + 1,
                            deal=req["position"] + 2,
                            volume=req.get("volume", 0.0),
                            price=fake11.ticks[req["symbol"]].bid,
                            comment="closed", request_id=1)
    return None


fake11.send_result = exec_close
fake11.account.equity = 192900.0          # breaker line: 200k - 3.5% = 193k
fake11.account.margin_free = 192900.0
with contextlib.redirect_stdout(io.StringIO()):
    fired = b11.check_breaker(st11, 200000.0)
ok(bool(fired), "breaker fires below the $7k line")
ok(st11["breaker"].get("tripped") is True, "breaker tripped recorded")
ok(isinstance(st11["breaker"].get("standdown_until"), str)
   and st11["breaker"]["standdown_until"] >= "2026-09-01",
   f"stand-down covers the next trading day "
   f"({st11['breaker'].get('standdown_until')})")
closes = [r for r in fake11.sent if "position" in r]
ok(len(closes) >= 1 and closes[0]["position"] == 921,
   "breaker flattened the exact ticket")
fake11.account.equity = 200000.0
fake11.account.margin_free = 200000.0
sends_before = len(fake11.sent)
quiet_send(b11, fake11, st11)
ok(len(fake11.sent) == sends_before,
   "tripped breaker refuses new risk even at recovered equity")

# ---- 12. static floor: send refused below $180k ----
b12, fake12, st12, _ = oh.boot()
fake12.account.equity = 179500.0
fake12.account.margin_free = 179500.0
quiet_send(b12, fake12, st12)
ok(len(fake12.sent) == 0, "equity below the $180k floor: zero sends")

# ---- 13. daily-increase lease: no late catch-up ----
b13, fake13, st13, _ = oh.boot()
magic13 = b13.MAGIC["XAUM"]
oh.install_plan(b13, st13, magic13, "XAUUSD.sim", 0.08)
st13["_daily_entry_plan"]["plans"][str(magic13)]["first_eval_epoch"] = (
    oh.WALL - 3600.0)
st13["_daily_entry_plan"]["plans"][str(magic13)]["expires_epoch"] = (
    oh.WALL - 1800.0)                     # lease expired 30 minutes ago
spec13 = b13._validated_trade_spec("XAUUSD.sim", "test sizing")
orig13 = oh.open_gate(b13)
try:
    with contextlib.redirect_stdout(io.StringIO()):
        b13._send("XAUUSD.sim", "buy", 0.08, magic13, "XAU-mom",
                  expected_spec=spec13,
                  max_total_notional=1.08 * 100.0 * 4700.0,
                  existing_abs_lots=0.0, equity_notional_fraction=0.25)
finally:
    b13._new_risk_blocked = orig13
ok(len(fake13.sent) == 0,
   "expired daily lease: the increase is never caught up late")

# ---- 14. reductions stay live while new risk is blocked ----
b14, fake14, st14, _ = oh.boot()
pos14 = fakemt5._Obj(ticket=931, identifier=931, magic=b14.MAGIC["XAUM"],
                     symbol="XAUUSD.sim", volume=0.30,
                     type=fake14.POSITION_TYPE_BUY, price_open=4610.0,
                     time=0)
fake14.positions = [pos14]


def exec_close14(req):
    if (req.get("action") == fake14.TRADE_ACTION_DEAL
            and "position" in req):
        vol = float(req.get("volume", 0.0))
        for p in list(fake14.positions):
            if p.ticket == req["position"]:
                p.volume = round(p.volume - vol, 2)
                if p.volume <= 1e-9:
                    fake14.positions.remove(p)
        return fakemt5._Obj(retcode=fake14.TRADE_RETCODE_DONE,
                            order=req["position"] + 1,
                            deal=req["position"] + 2, volume=vol,
                            price=fake14.ticks[req["symbol"]].bid,
                            comment="closed", request_id=1)
    return None


fake14.send_result = exec_close14
st14["_pause_new_risk"] = {"schema": b14._PAUSE_NEW_RISK_SCHEMA,
                           "since": float(oh.WALL)}
ok(b14._new_risk_blocked(), "no-new-risk latch is genuinely active")
with contextlib.redirect_stdout(io.StringIO()):
    b14.place_target("XAUUSD.sim", 0.10, 0.5, 1.0, b14.MAGIC["XAUM"],
                     "XAUM-mom")
reduces = [r for r in fake14.sent if "position" in r]
ok(len(reduces) >= 1,
   f"oversized sleeve reduced under the latch ({len(reduces)} closes)")
ok(all(r.get("position") == 931 for r in reduces),
   "reduction is exact-ticket")
opens = [r for r in fake14.sent if "position" not in r]
ok(len(opens) == 0, "no opening order under the latch")

# ---- 15. reversal never flips in the same poll ----
b15, fake15, st15, _ = oh.boot()
pos15 = fakemt5._Obj(ticket=941, identifier=941, magic=b15.MAGIC["XAUM"],
                     symbol="XAUUSD.sim", volume=0.10,
                     type=fake15.POSITION_TYPE_BUY, price_open=4610.0,
                     time=0)
fake15.positions = [pos15]
fake15.send_result = None
with contextlib.redirect_stdout(io.StringIO()):
    b15.place_target("XAUUSD.sim", 0.10, -0.5, 1.0, b15.MAGIC["XAUM"],
                     "XAUM-mom")
sells_open = [r for r in fake15.sent
              if "position" not in r
              and r.get("type") == fake15.ORDER_TYPE_SELL]
ok(len(sells_open) == 0,
   "sign flip closes first; the opposite side is never opened same-poll")

total = sum(len(f.sent) for f in (fake, fake2, fake3, fake4, fake5, fake6,
                                  fake7, fake13))
ok(total == 0, "all blocked scenarios produced zero sends")
print(f"test_protections: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
