"""Inert fake MetaTrader5 for the offline test campaign.

Every broker mutation is recorded, never executed.  `sent` collects each
order_send request; suites assert `len(FAKE.sent) == 0` (or drive explicit
scripted results when testing the order engine).  No network, no terminal.
"""


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __repr__(self):
        return f"_Obj({self.__dict__!r})"


DEFAULT_SPECS = {
    "US100.sim": dict(trade_contract_size=1.0, volume_min=0.1,
                      volume_max=1000.0, volume_step=0.1, point=0.1,
                      digits=1, trade_stops_level=0, trade_tick_size=0.1,
                      filling_mode=3, trade_exemode=2),
    "XAUUSD.sim": dict(trade_contract_size=100.0, volume_min=0.01,
                       volume_max=100.0, volume_step=0.01, point=0.01,
                       digits=2, trade_stops_level=0, trade_tick_size=0.01,
                       filling_mode=3, trade_exemode=2),
    "BTCUSD.sim": dict(trade_contract_size=1.0, volume_min=0.01,
                       volume_max=100.0, volume_step=0.01, point=0.01,
                       digits=2, trade_stops_level=0, trade_tick_size=0.01,
                       filling_mode=3, trade_exemode=2),
}


class FakeMT5:
    # constants used by the bot
    TIMEFRAME_M5 = 5
    TIMEFRAME_D1 = 1440
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_REMOVE = 8
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2
    SYMBOL_FILLING_FOK = 1
    SYMBOL_FILLING_IOC = 2
    SYMBOL_TRADE_EXECUTION_MARKET = 2
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_PLACED = 10008
    TRADE_RETCODE_DONE_PARTIAL = 10010
    TRADE_RETCODE_TIMEOUT = 10012
    TRADE_RETCODE_INVALID_FILL = 10030
    ACCOUNT_MARGIN_MODE_RETAIL_HEDGING = 2
    ORDER_STATE_STARTED = 0
    ORDER_STATE_PLACED = 1
    ORDER_STATE_CANCELED = 2
    ORDER_STATE_PARTIAL = 3
    ORDER_STATE_FILLED = 4
    ORDER_STATE_REJECTED = 5
    ORDER_STATE_EXPIRED = 6
    DEAL_ENTRY_IN = 0
    DEAL_ENTRY_OUT = 1
    DEAL_ENTRY_INOUT = 2
    DEAL_ENTRY_OUT_BY = 3
    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1
    DEAL_TYPE_BALANCE = 2
    DEAL_TYPE_CREDIT = 3
    DEAL_TYPE_CHARGE = 4
    DEAL_TYPE_CORRECTION = 5
    DEAL_TYPE_BONUS = 6
    DEAL_TYPE_BUY_CANCELED = 13
    DEAL_TYPE_SELL_CANCELED = 14
    DEAL_TYPE_COMMISSION = 7
    DEAL_TYPE_INTEREST = 12
    DEAL_TYPE_DIVIDEND = 15
    DEAL_TYPE_TAX = 17

    def __init__(self, login=600092429, server="OANDA-Prop Trader",
                 balance=200000.0, equity=200000.0, currency="USD"):
        self.account = _Obj(login=login, server=server, balance=balance,
                            equity=equity, currency=currency,
                            margin_mode=self.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
                            margin_free=equity, credit=0.0)
        self.specs = {name: dict(spec) for name, spec in
                      DEFAULT_SPECS.items()}
        self.ticks = {}          # symbol -> _Obj(time, time_msc, bid, ask)
        self.positions = []      # list of _Obj
        self.orders = []         # list of _Obj (pending orders)
        self.deals = []          # list of _Obj (history deals)
        self.history_orders = []  # list of _Obj (inactive/terminal orders)
        self.rates_m5 = {}       # symbol -> list of tuples/np rows
        self.rates_d1 = {}
        self.sent = []           # every order_send request, verbatim
        self.checked = []        # every order_check request
        self.send_result = None  # scripted next order_send result (or callable)
        self.initialized = False
        self.shutdown_calls = 0
        self.margin_per_lot = 10.0

    # ---- lifecycle ----
    def initialize(self, *args, **kw):
        self.initialized = True
        return True

    def shutdown(self):
        self.shutdown_calls += 1
        return True

    def last_error(self):
        return (0, "fake")

    # ---- account / symbols ----
    def account_info(self):
        return self.account

    def symbol_info(self, symbol):
        spec = self.specs.get(symbol)
        if spec is None:
            return None
        return _Obj(name=symbol, **spec)

    def symbol_info_tick(self, symbol):
        return self.ticks.get(symbol)

    def symbol_select(self, symbol, enable=True):
        return symbol in self.specs

    def symbols_get(self):
        return [_Obj(name=name) for name in self.specs]

    # ---- inventory / history ----
    def positions_get(self, **kw):
        rows = list(self.positions)
        if "ticket" in kw:
            rows = [p for p in rows if p.ticket == kw["ticket"]]
        if "symbol" in kw:
            rows = [p for p in rows if p.symbol == kw["symbol"]]
        return tuple(rows)

    def orders_get(self, **kw):
        rows = list(self.orders)
        if "ticket" in kw:
            rows = [o for o in rows if o.ticket == kw["ticket"]]
        return tuple(rows)

    def history_deals_get(self, *span, **kw):
        rows = list(self.deals)
        if "position" in kw:
            rows = [d for d in rows if d.position_id == kw["position"]]
        return tuple(rows)

    def history_orders_get(self, *span, **kw):
        rows = list(self.history_orders)
        if "ticket" in kw:
            rows = [o for o in rows if o.ticket == kw["ticket"]]
        return tuple(rows)

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        book = (self.rates_m5 if timeframe == self.TIMEFRAME_M5
                else self.rates_d1)
        rows = book.get(symbol)
        if rows is None:
            return None
        import numpy as np
        arr = np.array(rows, dtype=[("time", "i8"), ("open", "f8"),
                                    ("high", "f8"), ("low", "f8"),
                                    ("close", "f8")])
        return arr[-count:] if count else arr

    # ---- trading (recorded, never executed) ----
    def order_calc_margin(self, order_type, symbol, volume, price):
        return float(volume) * self.margin_per_lot

    def order_check(self, request):
        self.checked.append(dict(request))
        return _Obj(retcode=0)

    def order_send(self, request):
        self.sent.append(dict(request))
        result = self.send_result
        if callable(result):
            return result(dict(request))
        if result is not None:
            return result
        return None   # inert: an unscripted send is an ambiguous no-answer


def install(bot_module, fake=None):
    """Point an imported bot module at a fake terminal; returns the fake."""
    fake = fake or FakeMT5()
    bot_module.mt5 = fake
    return fake
