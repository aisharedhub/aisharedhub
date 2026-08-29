"""Applied-exposure recorder (build order section 7, defect-2 repair).

Offline with the inert fake MT5.  Run: python test_applied_exposure.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fakemt5

BOT = os.path.join(HERE, "..", "build", "vol_target_bot_v12.py")
sys.argv = ["vol_target_bot_v12.py"]
spec = importlib.util.spec_from_file_location("updbot_applied", BOT)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

PASS = [0]
FAIL = [0]


def ok(cond, label):
    if cond:
        PASS[0] += 1
    else:
        FAIL[0] += 1
        print(f"FAIL: {label}")


fake = fakemt5.install(b)
b.LIVE = True
b.DRY = False
import copy
BINDING = {
    "schema": "direct_lifecycle_binding/11", "stage": "p2",
    "recipe": "p2-standalone-immediate", "entry_policy": "immediate-v1",
    "login": 600092429, "server": "OANDA-Prop Trader",
    "direct_authority_sha256": b.DIRECT_RECIPE_AUTHORITY_SHA256,
    "magic_namespace": "v380-final-380371300/1",
    "continuity_sha256": None, "expected_start_cents": None,
    "observed_start_cents": 20_000_000, "declared_capital_cents": 20_000_000,
    "sizing_cents": 20_000_000, "breaker_bps": 350, "target_bps": 500,
    "capital_policy": "campaign-base-real-mark-v1",
    "anchor_risk_policy": "proved-anchor-full-or-hold-v1",
}
assert b._valid_current_lifecycle_binding(BINDING), "test binding invalid"


def fresh_st(**kw):
    st = {"_lifecycle_binding": copy.deepcopy(BINDING)}
    st.update(kw)
    return st


EQ = 200000.0
fake.account.equity = EQ
for sym, px in (("US100.sim", 29500.0), ("XAUUSD.sim", 4600.0),
                ("BTCUSD.sim", 78000.0)):
    fake.ticks[sym] = fakemt5._Obj(time=1, time_msc=1000, bid=px, ask=px)


def pos(ticket, magic, symbol, volume, buy=True):
    return fakemt5._Obj(ticket=ticket, identifier=ticket, magic=magic,
                        symbol=symbol, volume=volume,
                        type=(fake.POSITION_TYPE_BUY if buy
                              else fake.POSITION_TYPE_SELL),
                        time=0)


M = b.MAGIC
# targets: XAUM 0.10*0.5, XAUB 0.05*0.4, BTC 0.20*0.25, S8V 0.10*0.3 at L=4
TARGETS = {"XAUM": (0.10, 0.5, True), "XAUB": (0.05, 0.4, True),
           "BTC": (0.20, 0.25, True), "S8V": (0.10, 0.3, True)}
REQ = 4.0


def lots_for(frac, symbol):
    spec_row = fakemt5.DEFAULT_SPECS[symbol]
    px = fake.ticks[symbol].bid
    return frac * EQ / (spec_row["trade_contract_size"] * px)


def matching_positions():
    rows = []
    tick = 1000
    for name, (w, t, _r) in TARGETS.items():
        frac = w * t * REQ
        sym = b.SLEEVE_SYMBOL[name]
        rows.append(pos(tick, M[name], sym, lots_for(frac, sym)))
        tick += 1
    return rows


# --- matched inventory proves the requested leverage ---
fake.positions = matching_positions()
st = fresh_st()
proven = b._record_applied_exposure(st, fake.account, TARGETS, REQ,
                                    "2026-08-31")
ok(proven == REQ, f"matched inventory proves requested ({proven})")
ok(st["_last_L"] == REQ, "_last_L = proven")
ok(st["_requested_L"] == REQ, "_requested_L recorded")
rec = st["_applied_exposure"]
ok(b._valid_applied_exposure(rec), "record validates")
ok(rec["matched"] is True and rec["proven_L"] == REQ, "record matched")
ok(set(rec["sleeves"]) == {"XAUM", "XAUB", "BTC", "S8V", "ORB"},
   "all sleeves recorded incl ORB")

# --- half-filled inventory yields the implied leverage, not the request ---
fake.positions = [pos(p.ticket, p.magic, p.symbol, p.volume / 2.0)
                  for p in matching_positions()]
st2 = fresh_st()
proven2 = b._record_applied_exposure(st2, fake.account, TARGETS, REQ,
                                     "2026-08-31")
ok(proven2 is not None and abs(proven2 - REQ / 2.0) < 0.05,
   f"half fill proves ~{REQ/2:.2f} ({proven2})")
ok(st2["_last_L"] == proven2, "stale requested value never persisted")
ok(st2["_applied_exposure"]["matched"] is False, "recorded as unmatched")

# --- flat inventory with zero targets proves the requested value ---
fake.positions = []
zero_targets = {k: (w, 0.0, True) for k, (w, _t, _r) in TARGETS.items()}
st3 = fresh_st()
proven3 = b._record_applied_exposure(st3, fake.account, zero_targets, REQ,
                                     "2026-08-31")
ok(proven3 == REQ, "flat+zero-targets matches (requested carried)")

# --- pending intent blocks the proof (prior value retained) ---
st4 = fresh_st(_order_intent={"status": "PREPARED"}, _last_L=1.25)
ok(b._record_applied_exposure(st4, fake.account, TARGETS, REQ,
                              "2026-08-31") is None,
   "pending intent defers proof")
ok(st4["_last_L"] == 1.25, "prior proven value retained")

# --- unreadable inventory blocks the proof ---
fake.positions = matching_positions()
orig = fake.positions_get
fake.positions_get = lambda **kw: None
st5 = fresh_st(_last_L=2.0)
ok(b._record_applied_exposure(st5, fake.account, TARGETS, REQ,
                              "2026-08-31") is None,
   "unknown inventory defers proof")
fake.positions_get = orig
b._POSITIONS_UNKNOWN[0] = False

# --- unpriceable live exposure blocks the proof ---
fake.ticks["XAUUSD.sim"] = None
st6 = fresh_st(_last_L=2.0)
ok(b._record_applied_exposure(st6, fake.account, TARGETS, REQ,
                              "2026-08-31") is None,
   "unpriceable exposure defers proof")
fake.ticks["XAUUSD.sim"] = fakemt5._Obj(time=1, time_msc=1000,
                                        bid=4600.0, ask=4600.0)

# --- DRY records requested without touching the broker ---
b.DRY = True
sends_before = len(fake.sent)
st7 = fresh_st()
ok(b._record_applied_exposure(st7, fake.account, TARGETS, 3.5,
                              "2026-08-31") == 3.5, "DRY keeps requested")
b.DRY = False

# --- day_roll_txn/2 carries the audit fields ---
audit = b._day_roll_audit_fields(st)
ok(audit["requested_L"] == REQ and isinstance(audit["sleeves"], dict),
   "audit fields derived")
pend = {
    "schema": b._DAY_ROLL_TXN_SCHEMA, "stage": "WAIT_FINALITY",
    "session": "2026-08-31", "next_session": "2026-09-01",
    "last_eq": 200000.0, "end_eq": 199000.0, "applied_L": REQ,
    "sess_dip": -0.001, "standdown": False, **audit,
}
ok(b._valid_day_roll_txn(pend, None), "day_roll_txn/2 validates")
legacy = {k: v for k, v in pend.items()
          if k not in ("requested_L", "sleeves")}
legacy["schema"] = "day_roll_txn/1"
ok(b._valid_day_roll_txn(legacy, None), "day_roll_txn/1 (r4) still valid")
bad = dict(pend)
bad["requested_L"] = float("inf")
ok(not b._valid_day_roll_txn(bad, None), "nonfinite requested refused")

# --- zero broker sends throughout ---
ok(len(fake.sent) == sends_before == 0, "zero order_send calls")

print(f"test_applied_exposure: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
