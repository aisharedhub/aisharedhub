"""Full startup-campaign harness: real _main_impl runs on the inert fake.

Drives complete recipe lifecycles offline — virgin bind, NY17 session
roll, Prague-midnight anchor pairing, the 18:05-18:35 NY daily-increase
lease, real sends resolved by a scripted executing broker — with a
MOVING pinned clock.  The only stubbed control decision is the time-feed
health check (its acceptance machinery has dedicated suites); every
economic, lifecycle, rail and order decision is the real code.
"""
import importlib.util
import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fakemt5

BOT = os.path.join(HERE, "..", "build", "vol_target_bot_v12.py")
NY = ZoneInfo("America/New_York")
LOGIN = 600092429
SERVER = "OANDA-Prop Trader"
T0 = datetime(2026, 8, 31, 15, 30, tzinfo=timezone.utc)   # Mon 11:30 NY

_SEQ = [0]


def weekday_sessions(end_day, count):
    """`count` NY17 session dates ending at `end_day` (a weekday)."""
    out = []
    day = end_day
    while len(out) < count:
        if day.weekday() < 5:
            out.append(day)
        day -= timedelta(days=1)
    return list(reversed(out))


def session_open_epoch(session_day):
    """A session's D1 open: 17:00 NY on the prior calendar day."""
    prev = session_day - timedelta(days=1)
    return int(datetime(prev.year, prev.month, prev.day, 17, 0,
                        tzinfo=NY).timestamp())


class MarketData:
    """Seed-consistent daily book + flat M5 grids per session.

    The daily authority requires broker D1 history to overlap the pinned
    seed exactly, so closes derive from the shipped seed tail (300
    sessions through 2026-08-07) extended with small deterministic
    returns across the 2026-08-10..2026-08-28 gap.  The genuine seed
    signals at this frontier are positive for XAUM/XAUB/BTC and S8V sees
    real down days, so entry demand is authentic.
    """

    BASES = {"US100.sim": "nas", "XAUUSD.sim": "xau", "BTCUSD.sim": "btc"}
    GAP_RETS = [0.0005, 0.0006, -0.0004, 0.0005, 0.0007,
                -0.0003, 0.0006, 0.0004, -0.0005, 0.0007,
                0.0005, -0.0002, 0.0006, 0.0005, 0.0004]
    GROW_RET = 0.0005
    SEED_TAIL = 300

    def __init__(self, fake, last_completed=date(2026, 8, 28)):
        self.fake = fake
        seed = json.load(open(os.path.join(HERE, "..", "build",
                                           "shadow_seed.json")))
        seed_days = [date.fromisoformat(d) for d in seed["dates"]]
        self.sessions = seed_days[-self.SEED_TAIL:]
        self.closes = {sym: [float(c) for c in
                             seed["closes"][key][-self.SEED_TAIL:]]
                       for sym, key in self.BASES.items()}
        k = 0
        while self.sessions[-1] < last_completed:
            new_day = self.next_session_after(self.sessions[-1])
            self.sessions.append(new_day)
            ret = self.GAP_RETS[k % len(self.GAP_RETS)]
            k += 1
            for sym in self.BASES:
                self.closes[sym].append(self.closes[sym][-1] * (1.0 + ret))
        self.rebuild()

    def next_session_after(self, day):
        day = day + timedelta(days=1)
        while day.weekday() >= 5:
            day += timedelta(days=1)
        return day

    def grow(self, ret=None):
        """Complete the forming session with a fresh close."""
        new_day = self.next_session_after(self.sessions[-1])
        self.sessions.append(new_day)
        for sym in self.BASES:
            px = self.closes[sym][-1] * (1.0 + (self.GROW_RET
                                                if ret is None else ret))
            self.closes[sym].append(px)
        self.rebuild()
        return new_day

    def snapshot_base(self):
        """Per-symbol D1 snapshot for the bot's _TEST_D1_SNAPSHOT hook."""
        forming_day = self.next_session_after(self.sessions[-1])
        forming_open = session_open_epoch(forming_day)
        ords = [d.toordinal() for d in self.sessions]
        snap = {}
        for sym in self.BASES:
            snap[sym] = {
                "ords": list(ords),
                "closes": [float(c) for c in self.closes[sym]],
                "request_complete": True,
                "dropped_time": forming_open,
                "raw_rows": len(ords) + 1,
            }
        return snap

    def rebuild(self):
        forming_day = self.next_session_after(self.sessions[-1])
        forming_open = session_open_epoch(forming_day)
        for sym in self.BASES:
            rows = []
            for day, close in zip(self.sessions, self.closes[sym]):
                epoch = session_open_epoch(day)
                rows.append((epoch, close * 0.999, close * 1.004,
                             close * 0.996, close))
            last = self.closes[sym][-1]
            rows.append((forming_open, last, last * 1.002, last * 0.998,
                         last * 1.0005))
            self.fake.rates_d1[sym] = rows
        # complete flat M5 grids (sub-0.1% range -> ORB books EXACT 0.0)
        # for every post-seed session: the proved gap replay re-derives
        # each session's ORB from the full strict grid
        rows = []
        px = self.closes["US100.sim"][-1]
        post_seed = [d for d in self.sessions if d > date(2026, 8, 7)]
        for day in post_seed + [forming_day]:
            base = int(datetime(day.year, day.month, day.day,
                                tzinfo=timezone.utc).timestamp())
            for minute in range(870, 1256, 5):
                rows.append((base + minute * 60, px, px, px, px))
        self.fake.rates_m5["US100.sim"] = rows


class ExecBroker:
    """Executes DEAL/REMOVE requests against the fake's books."""

    def __init__(self, b, fake):
        self.b = b
        self.fake = fake
        self.next_id = [5000]
        self.enabled = True

    def _now(self):
        return int(self.b._TEST_WALL_TS)

    def __call__(self, req):
        fake = self.fake
        if not self.enabled:
            return None
        if req.get("action") == fake.TRADE_ACTION_REMOVE:
            fake.orders = [o for o in fake.orders
                           if o.ticket != req.get("order")]
            return fakemt5._Obj(retcode=fake.TRADE_RETCODE_DONE,
                                order=req.get("order", 0), deal=0,
                                request_id=1, price=0.0, volume=0.0,
                                comment="removed")
        if req.get("action") != fake.TRADE_ACTION_DEAL:
            return None
        self.next_id[0] += 10
        order_id = self.next_id[0]
        deal_id = order_id + 1
        volume = float(req["volume"])
        price = float(req["price"])
        symbol = req["symbol"]
        magic = req.get("magic", 0)
        comment = req.get("comment", "")
        buy = req.get("type") == fake.ORDER_TYPE_BUY
        now = self._now()
        profit = 0.0
        if "position" in req:                      # exact-ticket close/reduce
            pos_id = req["position"]
            for p in list(fake.positions):
                if p.ticket == pos_id:
                    contract = fakemt5.DEFAULT_SPECS[p.symbol][
                        "trade_contract_size"]
                    side = 1.0 if p.type == fake.POSITION_TYPE_BUY else -1.0
                    profit = round(
                        (price - p.price_open) * side * contract * volume, 2)
                    p.volume = round(p.volume - volume, 8)
                    if p.volume <= 1e-9:
                        fake.positions.remove(p)
            fake.account.balance = round(fake.account.balance + profit, 2)
            entry = fake.DEAL_ENTRY_OUT
            position_id = pos_id
        else:                                      # new exposure
            position_id = order_id + 2
            fake.positions.append(fakemt5._Obj(
                ticket=position_id, identifier=position_id, magic=magic,
                symbol=symbol, volume=volume,
                type=(fake.POSITION_TYPE_BUY if buy
                      else fake.POSITION_TYPE_SELL),
                price_open=price, time=now,
                sl=float(req.get("sl", 0.0) or 0.0),
                tp=float(req.get("tp", 0.0) or 0.0)))
            entry = fake.DEAL_ENTRY_IN
        fake.deals.append(fakemt5._Obj(
            ticket=deal_id, order=order_id, position_id=position_id,
            magic=magic, symbol=symbol,
            type=(fake.DEAL_TYPE_BUY if buy else fake.DEAL_TYPE_SELL),
            entry=entry, time=now, time_msc=now * 1000, volume=volume,
            price=price, comment=comment, profit=profit, commission=0.0,
            swap=0.0, fee=0.0))
        fake.history_orders.append(fakemt5._Obj(
            ticket=order_id, magic=magic, symbol=symbol, comment=comment,
            type=req.get("type"), type_time=req.get(
                "type_time", fake.ORDER_TIME_GTC),
            type_filling=req.get("type_filling"),
            state=fake.ORDER_STATE_FILLED, time_setup=now,
            time_setup_msc=now * 1000, time_done=now,
            volume_initial=volume, volume_current=0.0))
        return fakemt5._Obj(retcode=fake.TRADE_RETCODE_DONE, order=order_id,
                            deal=deal_id, request_id=1, price=price,
                            volume=volume, comment="done")


def grid_tick(sym, px, now):
    """A fresh two-sided quote aligned to the broker price grid."""
    digits = fakemt5.DEFAULT_SPECS[sym]["digits"]
    tick_size = fakemt5.DEFAULT_SPECS[sym]["point"]
    steps = max(1, int(round(px * 0.00003 / tick_size)))
    bid = round(round(px / tick_size) * tick_size, digits)
    ask = round(bid + steps * tick_size, digits)
    return fakemt5._Obj(time=now - 1, time_msc=(now - 1) * 1000,
                        bid=bid, ask=ask)


def set_clock(b, now_utc):
    b._TEST_WALL_TS = now_utc.timestamp()
    b._TEST_NOW_UTC = now_utc
    b._TEST_NOW_NY = now_utc.astimezone(NY)
    b._TEST_PRAGUE_RAIL_NOW = now_utc
    fake = b.mt5
    now = int(now_utc.timestamp())
    for sym, tick in list(fake.ticks.items()):
        fake.ticks[sym] = grid_tick(sym, tick.bid, now)


def refresh_ticks(b, market):
    fake = b.mt5
    now = int(b._TEST_WALL_TS)
    for sym in MarketData.BASES:
        fake.ticks[sym] = grid_tick(sym, market.closes[sym][-1], now)


def boot(argv, workdir=None, balance=200000.0):
    """Load one bot process image: module + fake + market, clock at T0."""
    _SEQ[0] += 1
    workdir = workdir or tempfile.mkdtemp(prefix="lifec-")
    sys.argv = ["vol_target_bot_v12.py"] + argv
    spec = importlib.util.spec_from_file_location(
        f"updbot_lifec_{_SEQ[0]}", BOT)
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    b._DIRECT_PROFILE = b._direct_match_recipe(argv)
    assert b._DIRECT_PROFILE is not None, argv
    b.RELEASE_RECIPE_ID = b._DIRECT_PROFILE["recipe"]
    b.ENTRY_POLICY_ID = b._DIRECT_PROFILE.get("entry_policy")
    if b._DIRECT_PROFILE.get("capital_cents"):
        b._capital_cli = b._DIRECT_PROFILE["capital_cents"] / 100.0
    # the guarded __main__ parse never runs under importlib: replay every
    # recipe-derived mode flag exactly as import-time code does
    recipe = b.RELEASE_RECIPE_ID
    b.SELFCHECK = recipe == "selfcheck"
    b.LIST_SYMS = recipe == "list-symbols"
    b.DIAGNOSE = recipe == "diagnose"
    b.PAUSE_NEW_RISK_CMD = recipe == "pause"
    b.RESUME_PAUSED_CMD = recipe == "resume"
    b.FLATTEN_AND_STOP = recipe == "flatten-stop"
    b.EXPORT_CONTINUITY = recipe == "export"
    b.RECOVER_SAFETY = recipe == "recover"
    fake = fakemt5.install(b)
    b._mt5_initialize()  # production order: validate/attach any pin
                         # before the first account or identity read
    fake.account.login = LOGIN
    fake.account.server = SERVER
    fake.account.balance = balance
    fake.account.equity = balance
    fake.account.margin_free = balance
    b.STATE_FILE = os.path.join(workdir, "bot_state_v12.json")
    b.CONTINUITY_FILE = os.path.join(workdir, "shadow_continuity.json")
    b.ASSUME_YES = True
    b._TEST_NO_SLEEP = True
    b._TEST_MONO = 1000.0
    b.POLL_SECONDS = 0.05        # shrink raw poll sleeps for offline runs
    b.TARGET_FLAT_WATCH_S = 3.0  # scale the real-monotonic quiet holds to
                                 # the fast offline poll cadence
    b._TEST_SINGLETON_ACQUIRE = lambda key: True
    # every bounded-loop seam: no harness run may spin forever
    b._TEST_VIRGIN_WAIT_MAX_POLLS = 40
    b._TEST_RECOVERY_MAX_POLLS = 40
    b._TEST_INTERRUPT_MAX_POLLS = 40
    b._TEST_MIGRATION_HALT_MAX_POLLS = 40
    b._TEST_TAKEOVER_HOLD_MAX_POLLS = 40
    b._TEST_TARGET_HIT_EXPORT_MAX_POLLS = 40
    b._TEST_FLATTEN_STOP_MAX_POLLS = 40
    b._TEST_R4_MIGRATION_MAX_POLLS = 40
    market = MarketData(fake)
    broker = ExecBroker(b, fake)
    fake.send_result = broker

    # the health/epoch acceptance machinery has its own suites: pin the
    # frame and keep the witness fresh against the moving pinned clock
    b._BROKER_EPOCH_MODE[0] = "raw-utc"
    b._BROKER_EPOCH_OFFSET_S[0] = 0

    def fresh_health(where="poll"):
        # each health sample advances the pinned clock a little, exactly
        # like real polling cadence, so advancing-tick proofs can mature
        wall = float(b._TEST_WALL_TS) + 2.0
        now_utc = datetime.fromtimestamp(wall, tz=timezone.utc)
        # broker-consistent marks: equity = balance + floating P/L
        floating = 0.0
        try:
            for p in fake.positions:
                tick = fake.ticks.get(p.symbol)
                if tick is None:
                    continue
                mark = tick.bid if p.type == fake.POSITION_TYPE_BUY \
                    else tick.ask
                side = 1.0 if p.type == fake.POSITION_TYPE_BUY else -1.0
                contract = fakemt5.DEFAULT_SPECS[p.symbol][
                    "trade_contract_size"]
                floating += (mark - p.price_open) * side * contract * p.volume
            fake.account.equity = round(fake.account.balance + floating, 2)
            fake.account.margin_free = fake.account.equity
        except Exception:
            pass
        b._TEST_WALL_TS = wall
        b._TEST_NOW_UTC = now_utc
        b._TEST_NOW_NY = now_utc.astimezone(NY)
        b._TEST_PRAGUE_RAIL_NOW = now_utc
        b._TEST_MONO = float(b._TEST_MONO) + 2.0
        for sym, tick in list(fake.ticks.items()):
            tick.time = int(wall) - 1
            tick.time_msc = (int(wall) - 1) * 1000
        b._UTC_EPOCH_QUALIFIED[0] = True
        b._HEALTH_BAD[0] = False
        b._UTC_EPOCH_WITNESS[0] = {
            "mode": "raw-utc", "offset_s": 0, "health_status": "ok",
            "poll_total": int(b._POLL_TOTAL[0]), "wall_epoch": wall,
            "mono_epoch": float(b._TEST_MONO), "max_delta_s": 2.0,
            "raw_ticks": {sym: int(wall) - 1 for sym in MarketData.BASES},
            "ticks": {sym: wall - 1.0 for sym in MarketData.BASES}}
        snap = market.snapshot_base()
        b._TEST_D1_SNAPSHOT = {
            sym: {**snap[sym], "tick_time": int(wall)} for sym in snap}
        return "ok"

    b._time_feed_health_check = fresh_health
    orig_nsk = b.ny_session_key
    b.ny_session_key = lambda now=None: orig_nsk(now or b._TEST_NOW_NY)
    orig_pdk = b.prague_day_key
    b.prague_day_key = lambda now=None: orig_pdk(
        now or b._TEST_NOW_UTC.astimezone(b.RESET_TZ))
    set_clock(b, T0)
    refresh_ticks(b, market)
    fresh_health("boot")
    return b, fake, market, broker, workdir


def run_polls(b, market, polls, refresh=True):
    """Run _main_impl until `polls` more poll iterations complete."""
    if refresh:
        refresh_ticks(b, market)
    b._time_feed_health_check("pre-run")
    b._TEST_MAIN_MAX_POLLS = int(b._POLL_TOTAL[0]) + int(polls)
    code = None
    try:
        b._main_impl()
    except SystemExit as exc:
        code = exc.code
    return code


def state_on_disk(b):
    try:
        return json.load(open(b.STATE_FILE))
    except Exception:
        return None


def run_sessions(b, market, count, run=run_polls, ret=None):
    """Advance `count` complete NY17 sessions with genuine boundary physics:
    the process observes both sides of the 17:00-NY cut (durable mark),
    receives the completed D1 minutes later (both ledgers fold), and
    witnesses both sides of Prague midnight (paired anchor proof)."""
    for _ in range(count):
        forming = market.next_session_after(market.sessions[-1])
        day = datetime(forming.year, forming.month, forming.day, tzinfo=NY)
        cut = day.replace(hour=17, minute=0, second=30)
        set_clock(b, (cut - timedelta(minutes=2)).astimezone(timezone.utc))
        run(b, market, 2)
        set_clock(b, cut.astimezone(timezone.utc))
        run(b, market, 3)
        set_clock(b, (cut + timedelta(minutes=5)).astimezone(timezone.utc))
        market.grow(ret)
        run(b, market, 6)
        midnight = day.replace(hour=18, minute=0, second=20)   # 00:00 Prague
        set_clock(b, (midnight - timedelta(seconds=50)).astimezone(
            timezone.utc))
        run(b, market, 2)
        set_clock(b, midnight.astimezone(timezone.utc))
        run(b, market, 3)


def drive_to_authorized(b, market, run=run_polls):
    """Monday bind -> NY17 roll -> Prague anchor: a fully authorized live
    process with both ledgers on session 2026-09-01 (before any entry)."""
    run(b, market, 6)
    set_clock(b, datetime(2026, 8, 31, 21, 0, 30, tzinfo=timezone.utc))
    run(b, market, 3)
    set_clock(b, datetime(2026, 8, 31, 21, 5, 0, tzinfo=timezone.utc))
    market.grow()
    run(b, market, 6)
    set_clock(b, datetime(2026, 8, 31, 22, 0, 20, tzinfo=timezone.utc))
    run(b, market, 6)
    st = b._RUNTIME_STATE[0]
    dc = (st.get("_daycount") or {}).get("session")
    sh_sess = (st.get("shadow") or {}).get("session")
    cold = (st.get("breaker") or {}).get("cold_start")
    assert dc == sh_sess == "2026-09-01" and cold is False, (
        dc, sh_sess, cold)
    return st
