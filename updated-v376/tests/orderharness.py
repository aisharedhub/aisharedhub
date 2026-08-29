"""Authorized-send harness for the exactly-once order engine tests.

Boots the bot offline on the inert fake with a fresh /11 lifecycle,
pinned Monday-session clocks, fresh ticks, and a valid daily entry plan,
so the REAL _send/_submit_new_risk/_resolve_order_intent stack runs end
to end.  Only the aggregate _new_risk_blocked() gate is stubbed open
(its own truth table is covered by the dedicated suites); every check
below it — request validation, intent persistence, fill policy, receipt
classification, deal/terminal-order reconciliation — is the real code.
"""
import importlib.util
import os
import sys
import tempfile
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fakemt5

BOT = os.path.join(HERE, "..", "build", "vol_target_bot_v12.py")
NY = ZoneInfo("America/New_York")
NOW_UTC = datetime(2026, 8, 31, 19, 30, tzinfo=timezone.utc)  # Mon 15:30 NY
WALL = NOW_UTC.timestamp()
LOGIN = 600092429
SERVER = "OANDA-Prop Trader"

_SEQ = [0]


def boot(require_guard=True):
    _SEQ[0] += 1
    workdir = tempfile.mkdtemp(prefix="ordeng-")
    sys.argv = ["vol_target_bot_v12.py", "--entry-policy", "immediate",
                "--mode", "grind", "--phase", "2",
                "--capital", "200000", "--live"]
    spec = importlib.util.spec_from_file_location(
        f"updbot_ordeng_{_SEQ[0]}", BOT)
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    b._DIRECT_PROFILE = b._direct_match_recipe(sys.argv[1:])
    assert b._DIRECT_PROFILE is not None
    b.RELEASE_RECIPE_ID = b._DIRECT_PROFILE["recipe"]
    b.ENTRY_POLICY_ID = b._DIRECT_PROFILE["entry_policy"]
    b.LIVE = True
    b.DRY = False
    fake = fakemt5.install(b)
    fake.account.login = LOGIN
    fake.account.server = SERVER
    fake.account.balance = 200000.0
    fake.account.equity = 200000.0
    fake.account.margin_free = 200000.0
    b.STATE_FILE = os.path.join(workdir, "bot_state_v12.json")
    b.CONTINUITY_FILE = os.path.join(workdir, "shadow_continuity.json")
    b._TEST_NO_SLEEP = True
    b._TEST_WALL_TS = WALL
    b._TEST_NOW_UTC = NOW_UTC
    b._TEST_NOW_NY = NOW_UTC.astimezone(NY)
    b._TEST_SESSION_KEY = "2026-08-31"
    b._TEST_MONO = 1000.0
    b._UTC_EPOCH_QUALIFIED[0] = True
    b._BROKER_EPOCH_MODE[0] = "raw-utc"
    b._BROKER_EPOCH_OFFSET_S[0] = 0
    b._HEALTH_BAD[0] = False
    b._EXTERNAL_CASHFLOW_UNKNOWN[0] = False
    b._UTC_EPOCH_WITNESS[0] = {
        "mode": "raw-utc", "offset_s": 0, "health_status": "ok",
        "poll_total": 0, "wall_epoch": WALL, "max_delta_s": 2.0,
        "ticks": {"US100.sim": WALL - 2.0, "XAUUSD.sim": WALL - 2.0,
                  "BTCUSD.sim": WALL - 2.0}}
    b._time_feed_health_check = lambda where="poll": "ok"
    b._nas_feed_live = lambda where=None: True
    b._BOOT_IDENT[0] = (LOGIN, SERVER)
    b.EXPECTED_LOGIN = LOGIN
    b.EXPECTED_SERVER = SERVER
    for sym, px in (("US100.sim", 29650.0), ("XAUUSD.sim", 4610.0),
                    ("BTCUSD.sim", 78500.0)):
        fake.ticks[sym] = fakemt5._Obj(
            time=int(WALL) - 1, time_msc=(int(WALL) - 1) * 1000,
            bid=px, ask=px + (0.5 if sym == "US100.sim" else 0.2))
    binding = {
        "schema": "direct_lifecycle_binding/11", "stage": "p2",
        "recipe": "p2-standalone-immediate",
        "entry_policy": "immediate-v1",
        "login": LOGIN, "server": SERVER,
        "direct_authority_sha256": b.DIRECT_RECIPE_AUTHORITY_SHA256,
        "magic_namespace": "v380-final-380371300/1",
        "continuity_sha256": None, "expected_start_cents": None,
        "observed_start_cents": 20_000_000,
        "declared_capital_cents": 20_000_000,
        "sizing_cents": 20_000_000, "breaker_bps": 350, "target_bps": 500,
        "capital_policy": "campaign-base-real-mark-v1",
        "anchor_risk_policy": "proved-anchor-full-or-hold-v1",
    }
    assert b._valid_current_lifecycle_binding(binding)
    b._TEST_PRAGUE_RAIL_NOW = NOW_UTC       # documented inert harness seam
    proof = {
        "schema": b._PRAGUE_ANCHOR_PROOF_SCHEMA,
        "kind": "paired-rollover", "date": "2026-08-31",
        "login": LOGIN, "server": SERVER, "currency": "USD",
        "midnight_balance_cents": 20_000_000, "anchor_cents": 20_000_000,
        "pre_balance_cents": 20_000_000, "pre_equity_cents": 20_000_000,
        "post_balance_cents": 20_000_000, "post_equity_cents": 20_000_000,
    }
    st = {"_lifecycle_binding": binding,
          "breaker": {"date": "2026-08-31", "anchor": 200000.0,
                      "tripped": False, "cold_start": False,
                      "anchor_proof": proof},
          "_daycount": {"session": "2026-08-31", "last_eq": 200000.0},
          "shadow": {"session": "2026-08-31", "eq": 1.0, "peak": 1.0,
                     "armed": True},
          "start_balance": 200000.0,
          "challenge_start_date": "2026-08-25"}
    assert b._valid_prague_anchor_proof(proof, st), "harness anchor proof"
    st["mt5_identity"] = {"login": LOGIN, "server": SERVER}
    b._RUNTIME_STATE[0] = st
    b._STATE_LOAD_STATUS[0] = "loaded"
    if require_guard:
        assert b._capture_external_cashflow_guard(st), "harness cashflow guard"
    return b, fake, st, workdir


def install_plan(b, st, magic, symbol, signed_lots):
    """A live 30-minute daily-increase lease for this sleeve."""
    st["_daily_entry_plan"] = {
        "schema": b._DAILY_ENTRY_PLAN_BOOK_SCHEMA,
        "plans": {str(int(magic)): {
            "schema": b._DAILY_ENTRY_PLAN_SCHEMA,
            "session": "2026-08-31", "symbol": symbol,
            "magic": int(magic), "target_signed_lots": float(signed_lots),
            "first_eval_epoch": WALL - 60.0,
            "expires_epoch": WALL + 29.0 * 60.0,
        }},
    }


def open_gate(b):
    """Stub ONLY the aggregate no-new-risk gate for a submission window."""
    orig = b._new_risk_blocked
    b._new_risk_blocked = lambda: False
    return orig


def send_daily(b, fake, st, symbol="XAUUSD.sim", magic=None, lots=0.08,
               side="buy"):
    """Drive the real _send for one daily sleeve increase."""
    magic = b.MAGIC["XAUM"] if magic is None else magic
    install_plan(b, st, magic, symbol, lots if side == "buy" else -lots)
    spec = b._validated_trade_spec(symbol, "test sizing")
    assert spec is not None
    tick = fake.ticks[symbol]
    price = tick.ask if side == "buy" else tick.bid
    cap = (lots + 1.0) * spec["trade_contract_size"] * (price + 50.0)
    orig = open_gate(b)
    try:
        result = b._send(symbol, side, lots, magic, "XAU-mom",
                         expected_spec=spec, max_total_notional=cap,
                         existing_abs_lots=0.0,
                         equity_notional_fraction=0.25)
    finally:
        b._new_risk_blocked = orig
    return result, spec, price
