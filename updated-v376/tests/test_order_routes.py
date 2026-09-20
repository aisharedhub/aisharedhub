"""Order-route matrix: full, partial, rejected, timeout and unknown orders
(build order sections 11 and 20) through the REAL exactly-once engine.

Every scenario drives _send -> _submit_new_risk (durable PREPARED intent,
persisted fill policy, one order_send) and then _resolve_order_intent
against scripted broker evidence.  DONE is only ever an acknowledgement;
execution and non-execution are proved from positions/deals/terminal
order history, never from the send response.

Run: python test_order_routes.py
"""
import contextlib
import io
import json
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


def ack(fake, retcode, order=0, deal=0, price=0.0, volume=0.0):
    return fakemt5._Obj(retcode=retcode, order=order, deal=deal,
                        request_id=1, price=price, volume=volume,
                        comment="scripted")


def quiet_send(b, fake, st, **kw):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        res = oh.send_daily(b, fake, st, **kw)
    return res, out.getvalue()


def resolve(b, st, rounds=4):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        for _ in range(rounds):
            b._resolve_order_intent(st)
            if "_order_intent" not in st:
                break
    return out.getvalue()


def fill_evidence(b, fake, intent, price, lots, state, remaining,
                  position_lots=None):
    """Script the broker's causal evidence for the sent intent."""
    magic = intent["magic"]
    symbol = intent["symbol"]
    token = intent["token"]
    sent_at = float(intent["sent_at"])
    deal_rows = []
    if lots > 0:
        deal_rows.append(fakemt5._Obj(
            ticket=456, order=123, position_id=777, magic=magic,
            symbol=symbol, type=fake.DEAL_TYPE_BUY, entry=fake.DEAL_ENTRY_IN,
            time=int(sent_at) + 1, time_msc=(int(sent_at) + 1) * 1000,
            volume=lots, price=price, comment=token, profit=0.0,
            commission=0.0, swap=0.0, fee=0.0))
    fake.deals = deal_rows
    fake.history_orders = [fakemt5._Obj(
        ticket=123, magic=magic, symbol=symbol, comment=token,
        type=fake.ORDER_TYPE_BUY, type_time=fake.ORDER_TIME_GTC,
        type_filling=intent.get("fill_mode"), state=state,
        time_setup=int(sent_at) + 1,
        time_setup_msc=(int(sent_at) + 1) * 1000,
        time_done=int(sent_at) + 2,
        volume_initial=float(intent["volume"]), volume_current=remaining)]
    fake.positions = []
    real_pos = lots if position_lots is None else position_lots
    if real_pos > 0:
        fake.positions.append(fakemt5._Obj(
            ticket=777, identifier=777, magic=magic, symbol=symbol,
            volume=real_pos, type=fake.POSITION_TYPE_BUY, price_open=price,
            time=int(sent_at) + 1))


# =============== 1. FULL FILL: DONE ack -> proved execution ===============
b, fake, st, wd = oh.boot()
fake.send_result = lambda req: ack(fake, fake.TRADE_RETCODE_DONE, order=123,
                                   deal=456, price=req["price"],
                                   volume=req["volume"])
res, log_text = quiet_send(b, fake, st)
ok(len(fake.sent) == 1, "exactly one order_send")
intent = st.get("_order_intent")
ok(isinstance(intent, dict) and intent["status"] == "ACK_PENDING",
   "DONE is an acknowledgement, never execution (ACK_PENDING)")
ok(fake.sent[0]["comment"] == intent["token"],
   "request carries the durable intent token")
disk = json.load(open(os.path.join(wd, "bot_state_v12.json")))
ok(disk.get("_order_intent", {}).get("status") in ("PREPARED",
                                                   "ACK_PENDING",
                                                   "UNKNOWN_RESPONSE"),
   "intent durably persisted before/at the send")
ok(b._new_risk_blocked(), "pending intent blocks all new risk")
price = fake.sent[0]["price"]
lots = float(intent["volume"])
fill_evidence(b, fake, intent, price, lots, fake.ORDER_STATE_FILLED, 0.0)
resolve(b, st)
ok("_order_intent" not in st, "full fill proved and released")
ok("_close_only_halt" not in st, "clean execution latches nothing")
ok(json.load(open(os.path.join(wd, "bot_state_v12.json"))).get(
    "_order_intent") is None, "release persisted durably")

# ambiguity discipline: a second send while unresolved never happens
b2, fake2, st2, _ = oh.boot()
fake2.send_result = lambda req: ack(fake2, fake2.TRADE_RETCODE_DONE,
                                    order=123, deal=456, price=req["price"],
                                    volume=req["volume"])
quiet_send(b2, fake2, st2)
sends_before = len(fake2.sent)
res2, _ = quiet_send(b2, fake2, st2)
ok(len(fake2.sent) == sends_before,
   "an unresolved intent refuses any further send (never resend)")

# ============ 2. PARTIAL FILL: proved at the implied volume ============
b3, fake3, st3, _ = oh.boot()
fake3.send_result = lambda req: ack(fake3, fake3.TRADE_RETCODE_DONE,
                                    order=123, deal=456, price=req["price"],
                                    volume=req["volume"])
quiet_send(b3, fake3, st3)
intent3 = st3["_order_intent"]
lots3 = float(intent3["volume"])
part = round(lots3 - 0.03, 2)
fill_evidence(b3, fake3, intent3, fake3.sent[0]["price"], part,
              fake3.ORDER_STATE_PARTIAL, round(lots3 - part, 2))
resolve(b3, st3)
ok("_order_intent" not in st3,
   f"partial fill ({part}/{lots3}) proved from deals+terminal order")
ok(len(fake3.positions) == 1 and fake3.positions[0].volume == part,
   "partial inventory stands; no chase, no resend")

# ===== 3. EXPLICIT REJECTION: zero-id reject releases durably =====
b4, fake4, st4, wd4 = oh.boot()
fake4.send_result = lambda req: ack(fake4, 10016)      # invalid stops
res4, _ = quiet_send(b4, fake4, st4)
ok(len(fake4.sent) == 1, "rejection: one send")
ok("_order_intent" not in st4,
   "explicit zero-id rejection released durably at the send edge")
ok("_close_only_halt" not in st4, "clean rejection latches nothing")
ok(not fake4.positions, "no inventory after rejection")

# ====== 4. TIMEOUT: UNKNOWN until proved; zero-fill releases ======
b5, fake5, st5, wd5 = oh.boot()
fake5.send_result = lambda req: ack(fake5, fake5.TRADE_RETCODE_TIMEOUT)
quiet_send(b5, fake5, st5)
intent5 = st5.get("_order_intent")
ok(isinstance(intent5, dict) and intent5["status"] == "UNKNOWN_RESPONSE",
   "timeout stays UNKNOWN")
resolve(b5, st5)
ok("_order_intent" in st5,
   "UNKNOWN never releases without broker proof")
# terminal zero-fill discovery by unique token
fill_evidence(b5, fake5, intent5, fake5.sent[0]["price"], 0.0,
              fake5.ORDER_STATE_CANCELED, float(intent5["volume"]))
resolve(b5, st5)
ok("_order_intent" not in st5,
   "proved zero-fill (canceled, full remainder) releases the timeout")
ok(not fake5.positions, "no phantom exposure after zero fill")

# ========= 5. None RESPONSE: UNKNOWN; never guessed executed =========
b6, fake6, st6, _ = oh.boot()
fake6.send_result = None                                # inert no-answer
quiet_send(b6, fake6, st6)
intent6 = st6.get("_order_intent")
ok(isinstance(intent6, dict) and intent6["status"] == "UNKNOWN_RESPONSE",
   "None response stays UNKNOWN")
resolve(b6, st6)
ok("_order_intent" in st6, "no evidence: UNKNOWN holds forever")
ok(b6._new_risk_blocked(), "UNKNOWN keeps all new risk blocked")

# ========= 6. INVALID_FILL: alternate policy tried exactly once =========
b7, fake7, st7, _ = oh.boot()
calls = [0]


def invalid_then_done(req):
    calls[0] += 1
    if calls[0] == 1:
        return ack(fake7, fake7.TRADE_RETCODE_INVALID_FILL)
    return ack(fake7, fake7.TRADE_RETCODE_DONE, order=123, deal=456,
               price=req["price"], volume=req["volume"])


fake7.send_result = invalid_then_done
quiet_send(b7, fake7, st7)
ok(len(fake7.sent) == 2, "INVALID_FILL retries the alternate policy once")
ok(fake7.sent[0]["type_filling"] != fake7.sent[1]["type_filling"],
   "second attempt uses the other advertised immediate mode")
ok(st7["_order_intent"]["status"] == "ACK_PENDING",
   "second-mode DONE acknowledged")

# INVALID_FILL carrying execution ids is a contradiction -> halt
b8, fake8, st8, _ = oh.boot()
fake8.send_result = lambda req: ack(fake8, fake8.TRADE_RETCODE_INVALID_FILL,
                                    order=123, deal=456)
quiet_send(b8, fake8, st8)
ok("_close_only_halt" in st8,
   "INVALID_FILL with broker execution ids latches close-only")

# ============ 7. MALFORMED RECEIPT: UNKNOWN + close-only ============
b9, fake9, st9, _ = oh.boot()
fake9.send_result = lambda req: fakemt5._Obj(
    retcode=fake9.TRADE_RETCODE_DONE, order="junk", deal=None, request_id=1)
quiet_send(b9, fake9, st9)
ok(st9.get("_order_intent", {}).get("status") == "UNKNOWN_RESPONSE",
   "malformed receipt stays UNKNOWN")
ok("_close_only_halt" in st9, "malformed receipt latches close-only halt")

# ======= 8. OVERFILL: broker inventory beyond the request -> halt =======
b10, fake10, st10, _ = oh.boot()
fake10.send_result = lambda req: ack(fake10, fake10.TRADE_RETCODE_DONE,
                                     order=123, deal=456, price=req["price"],
                                     volume=req["volume"])
quiet_send(b10, fake10, st10)
intent10 = st10["_order_intent"]
lots10 = float(intent10["volume"])
fill_evidence(b10, fake10, intent10, fake10.sent[0]["price"], lots10,
              fake10.ORDER_STATE_FILLED, 0.0, position_lots=lots10 * 3)
resolve(b10, st10)
ok("_close_only_halt" in st10,
   "grown inventory beyond the causal fill latches close-only")

# ================= zero unscripted sends double-check =================
total_sends = sum(len(f.sent) for f in (fake, fake2, fake3, fake4, fake5,
                                        fake6, fake7, fake8, fake9, fake10))
ok(total_sends == 1 + 1 + 1 + 1 + 1 + 1 + 2 + 1 + 1 + 1,
   f"every send accounted for exactly once ({total_sends})")

print(f"test_order_routes: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
