"""Offline incident harness: the exact supplied r4 state + live positions.

Loads the bot with the inert fake MT5, points STATE_FILE at a scratch
folder seeded with the exact evidence bytes, pins the clock to the handoff
session (Monday 2026-08-31), and supplies seed-consistent D1 snapshots and
exact ORB pieces so the proved gap replay runs without a terminal.

Requires UPDATED_V376_EVIDENCE_DIR (bot_state_v12.json + .bak).
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fakemt5

BOT = os.path.join(HERE, "..", "build", "vol_target_bot_v12.py")
SEED_PATH = os.path.join(HERE, "..", "build", "shadow_seed.json")
EVDIR = os.environ.get(
    "UPDATED_V376_EVIDENCE_DIR",
    os.path.join(HERE, "..", "evidence"))

NY = ZoneInfo("America/New_York")
# Handoff moment: Monday 2026-08-31 15:30 NY (19:30Z, summer) — the r4
# pending 08-28 -> 08-31 boundary's own next session.
SCENARIO_NOW_UTC = datetime(2026, 8, 31, 19, 30, tzinfo=timezone.utc)
SCENARIO_WALL = SCENARIO_NOW_UTC.timestamp()

_GAP_RETS = [0.0004, -0.0006, 0.0003, -0.0002, 0.0005,
             -0.0004, 0.0002, 0.0006, -0.0003, 0.0001,
             -0.0005, 0.0004, -0.0001, 0.0003, -0.0002]


def gap_sessions():
    """Master weekday sessions 2026-08-10 .. 2026-08-28 (no NAS holidays)."""
    out = []
    day = date(2026, 8, 10)
    while day <= date(2026, 8, 28):
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def load_bot(workdir):
    """Fresh bot module bound to a scratch state folder + pinned clock."""
    sys.argv = ["vol_target_bot_v12.py", "--entry-policy", "immediate",
                "--mode", "grind", "--phase", "2",
                "--capital", "200000", "--live"]
    spec = importlib.util.spec_from_file_location(
        f"updbot_r4_{abs(hash(workdir))}", BOT)
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    b._DIRECT_PROFILE = b._direct_match_recipe(sys.argv[1:])
    assert b._DIRECT_PROFILE is not None
    b.RELEASE_RECIPE_ID = b._DIRECT_PROFILE["recipe"]
    b.ENTRY_POLICY_ID = b._DIRECT_PROFILE["entry_policy"]
    b.LIVE = True
    b.DRY = False
    fake = fakemt5.install(b)
    b._mt5_initialize()  # production order: validate/attach any pin
                         # before the first account or identity read
    b.STATE_FILE = os.path.join(workdir, "bot_state_v12.json")
    b.CONTINUITY_FILE = os.path.join(workdir, "shadow_continuity.json")
    # clock pins
    b._TEST_NO_SLEEP = True
    b._TEST_WALL_TS = SCENARIO_WALL
    b._TEST_NOW_UTC = SCENARIO_NOW_UTC
    b._TEST_NOW_NY = SCENARIO_NOW_UTC.astimezone(NY)
    b._TEST_SESSION_KEY = "2026-08-31"
    b._TEST_MONO = 1000.0
    # feed/epoch: unit-level control (the real qualification machinery is
    # covered by its own suites)
    b._UTC_EPOCH_QUALIFIED[0] = True
    b._BROKER_EPOCH_MODE[0] = "raw-utc"
    b._BROKER_EPOCH_OFFSET_S[0] = 0
    b._HEALTH_BAD[0] = False
    b._UTC_EPOCH_WITNESS[0] = {
        "mode": "raw-utc", "offset_s": 0, "health_status": "ok",
        "ticks": {"US100.sim": SCENARIO_WALL - 2.0,
                  "XAUUSD.sim": SCENARIO_WALL - 2.0,
                  "BTCUSD.sim": SCENARIO_WALL - 2.0}}
    b._time_feed_health_check = lambda where="poll": "ok"
    b._nas_feed_live = lambda where=None: True
    b._EXTERNAL_CASHFLOW_UNKNOWN[0] = False
    return b, fake


def wire_market_data(b, fake):
    """Seed-consistent D1 snapshots + exact ORB pieces + fresh ticks."""
    seed = json.load(open(SEED_PATH))
    seed_ords = [date.fromisoformat(d).toordinal() for d in seed["dates"]]
    tail_n = 300
    gaps = gap_sessions()
    gap_ords = [d.toordinal() for d in gaps]

    snapshots = {}
    for sym, key in (("US100.sim", "nas"), ("XAUUSD.sim", "xau"),
                     ("BTCUSD.sim", "btc")):
        ords = list(seed_ords[-tail_n:])
        closes = [float(c) for c in seed["closes"][key][-tail_n:]]
        last = closes[-1]
        for k, o in enumerate(gap_ords):
            last = last * (1.0 + _GAP_RETS[k % len(_GAP_RETS)])
            ords.append(o)
            closes.append(last)
        forming_open = int(datetime(2026, 8, 30, 21, 0,
                                    tzinfo=timezone.utc).timestamp())
        snapshots[sym] = {"ords": ords, "closes": closes,
                          "request_complete": True,
                          "dropped_time": forming_open,
                          "raw_rows": len(ords) + 1,
                          "tick_time": int(SCENARIO_WALL)}
    b._TEST_D1_SNAPSHOT = snapshots

    # Complete flat M5 grids for every gap session: the strict classifier
    # proves each grid and classifies a sub-0.10%-range day as EXACT 0.0
    # (no-trade), so the reconstructed gap book returns carry no ORB term.
    rows = []
    px = 29600.0
    for day in gaps + [date(2026, 8, 31)]:
        day_epoch = int(datetime(day.year, day.month, day.day,
                                 tzinfo=timezone.utc).timestamp())
        for minute in range(870, 1256, 5):
            rows.append((day_epoch + minute * 60, px, px, px, px))
    fake.rates_m5["US100.sim"] = rows

    for sym, px in (("US100.sim", 29650.0), ("XAUUSD.sim", 4610.0),
                    ("BTCUSD.sim", 78500.0)):
        fake.ticks[sym] = fakemt5._Obj(
            time=int(SCENARIO_WALL) - 2,
            time_msc=(int(SCENARIO_WALL) - 2) * 1000,
            bid=px, ask=px + (0.5 if sym == "US100.sim" else 0.2))
    return seed


def wire_r4_account(b, fake, st):
    """Live account/inventory exactly as the committed r4 takeover holds."""
    binding = st["_lifecycle_binding"]
    fake.account.login = binding["login"]
    fake.account.server = binding["server"]
    fake.account.balance = st["breaker"]["anchor"]        # 197167.35
    fake.account.equity = st["_daycount"]["last_eq"]      # 197566.98
    fake.account.margin_free = fake.account.equity
    b._BOOT_IDENT[0] = (binding["login"], binding["server"])
    b.EXPECTED_LOGIN = binding["login"]
    b.EXPECTED_SERVER = binding["server"]
    fake.positions = []
    for row in st["_predecessor_takeover"]["positions"]:
        fake.positions.append(fakemt5._Obj(
            ticket=row["ticket"], identifier=row["identifier"],
            magic=row["magic"], symbol=row["symbol"],
            volume=row["volume"],
            type=(fake.POSITION_TYPE_BUY if row["side"] == "buy"
                  else fake.POSITION_TYPE_SELL),
            time=int(SCENARIO_WALL) - 4 * 86400))
    fake.orders = []


def make_workdir():
    workdir = tempfile.mkdtemp(prefix="r4mig-")
    shutil.copy(os.path.join(EVDIR, "bot_state_v12.json"),
                os.path.join(workdir, "bot_state_v12.json"))
    shutil.copy(os.path.join(EVDIR, "bot_state_v12.json.bak"),
                os.path.join(workdir, "bot_state_v12.json.bak"))
    return workdir


def boot(workdir=None):
    """Full harness: (bot, fake, st, workdir) with the r4 state loaded."""
    workdir = workdir or make_workdir()
    b, fake = load_bot(workdir)
    seed_state = json.load(open(os.path.join(workdir, "bot_state_v12.json")))
    wire_r4_account(b, fake, seed_state)
    wire_market_data(b, fake)
    st = b.load_state()
    assert b._STATE_LOAD_STATUS[0] == "loaded", b._STATE_LOAD_STATUS[0]
    b._RUNTIME_STATE[0] = st
    return b, fake, st, workdir
