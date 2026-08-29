"""Dated controller ledger (build order section 7, defect-1 repair).

Offline; needs only the shipped seed.  Run: python test_controller_ledger.py
"""
import copy
import importlib.util
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(HERE, "..", "build", "vol_target_bot_v12.py")
SEED = os.path.join(HERE, "..", "build", "shadow_seed.json")

sys.argv = ["vol_target_bot_v12.py"]
spec = importlib.util.spec_from_file_location("updbot_ledger", BOT)
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


seed = json.load(open(SEED))

# --- bootstrap from seed tail: dated, provenance-tagged ---
st = {}
ok(b._controller_ledger_bootstrap_from_seed(st, seed), "bootstrap")
led = st["_controller_ledger"]
ok(b._valid_controller_ledger(led), "valid after bootstrap")
ok(len(led["entries"]) == 20, "20 entries")
ok(led["entries"][-1]["session"] == "2026-08-07", "frontier = seed end")
ok(all(e["source"] == "seed" for e in led["entries"]), "seed provenance")
ok(st["book_returns"] == seed["book_returns"][-20:], "window sync equals seed")

# --- live roll appends ---
ok(b._controller_ledger_append_roll(st, {
    "session": "2026-08-10", "source": "live-account", "book_ret": 0.001,
    "account_ret": 0.00875, "dip": 0.002, "applied_L": 8.75,
    "requested_L": 8.75, "sleeves": None, "flags": []}), "live append")
ok(st["book_returns"][-1] == 0.001 and len(st["book_returns"]) == 20,
   "window rolls")
ok(st["dip_hist"][-1] == 0.002, "dip recorded")

# --- standdown holds the chain but not the window ---
ok(b._controller_ledger_append_roll(st, {
    "session": "2026-08-11", "source": "standdown", "book_ret": None,
    "account_ret": -0.001, "dip": 0.001, "applied_L": 0.0,
    "requested_L": None, "sleeves": None, "flags": ["standdown"]}),
   "standdown append")
ok(st["book_returns"][-1] == 0.001, "standdown excluded from window")

# --- bounded proven gap ---
ok(b._controller_ledger_append_roll(st, {
    "session": "2026-08-19", "source": "live-account", "book_ret": -0.002,
    "account_ret": -0.0175, "dip": 0.003, "applied_L": 8.75,
    "requested_L": None, "sleeves": None, "flags": []}),
   "gap append (flag retry)")

# --- unbounded gap quarantines the ledger ---
st_q = copy.deepcopy(st)
ok(not b._controller_ledger_append_roll(st_q, {
    "session": "2026-09-15", "source": "live-account", "book_ret": 0.001,
    "account_ret": 0.00875, "dip": 0.0, "applied_L": 8.75,
    "requested_L": None, "sleeves": None, "flags": []}),
   "long gap refused")
ok("_controller_ledger" not in st_q, "ledger quarantined")

# --- rejection battery ---
def entry(**kw):
    base = {"session": "2026-08-20", "source": "live-account",
            "book_ret": 0.0, "account_ret": 0.0, "dip": 0.0,
            "applied_L": 1.0, "requested_L": None, "sleeves": None,
            "flags": []}
    base.update(kw)
    return base

ok(not b._valid_controller_ledger_entry(entry(session="2026-08-22")),
   "weekend session refused")
ok(not b._valid_controller_ledger_entry(entry(source="guess")),
   "unknown provenance refused")
ok(not b._valid_controller_ledger_entry(entry(book_ret=float("nan"))),
   "nan return refused")
ok(not b._valid_controller_ledger_entry(entry(applied_L=0.01)),
   "live entry with token applied_L refused")
ok(not b._valid_controller_ledger_entry(entry(source="seed")),
   "seed entry with applied_L refused")
bad = copy.deepcopy(st["_controller_ledger"])
bad["entries"][5], bad["entries"][6] = bad["entries"][6], bad["entries"][5]
ok(not b._valid_controller_ledger(bad), "out-of-order sessions refused")
bad = copy.deepcopy(st["_controller_ledger"])
bad["entries"][4]["session"] = bad["entries"][3]["session"]
ok(not b._valid_controller_ledger(bad), "duplicate session refused")

# --- LIVE vol authority requires the dated proof ---
b.LIVE = True
st_ok = {}
b._controller_ledger_bootstrap_from_seed(st_ok, seed)
ok(b.book_realized_vol(st_ok, None) is not None, "dated window yields vol")
ok(b.book_realized_vol({"book_returns": [0.001] * 20}, None) is None,
   "undated 20-list refused as live vol authority (defect-1)")
tampered = copy.deepcopy(st_ok)
tampered["book_returns"][-1] = 0.05     # list no longer matches the ledger
ok(b.book_realized_vol(tampered, None) is None,
   "window/ledger mismatch refused")
b.LIVE = False

# --- absorb backfill ---
st_a = {}
recs = [(date.fromisoformat("2026-08-10").toordinal(), 0.0005),
        (date.fromisoformat("2026-08-11").toordinal(), -0.0007)]
ok(b._controller_ledger_absorb_backfill(st_a, seed, recs), "absorb")
tail = st_a["_controller_ledger"]["entries"][-2:]
ok([e["session"] for e in tail] == ["2026-08-10", "2026-08-11"],
   "gap sessions dated")
ok(all(e["source"] == "shadow-backfill" for e in tail),
   "backfill provenance")
ok(st_a["book_returns"][-2:] == [0.0005, -0.0007], "windows absorb")
# absorb is idempotent past the frontier
before = copy.deepcopy(st_a["_controller_ledger"])
ok(b._controller_ledger_absorb_backfill(st_a, seed, recs), "re-absorb ok")
ok(st_a["_controller_ledger"] == before, "re-absorb is a no-op")

# --- _install_pinned_vol_history behavior matrix ---
class _A:  # minimal authority stub via the real loader path is heavy; use seed
    pass

b._ECONOMIC_INPUT_INVALID[0] = False
st_l = {"book_returns": [0.001] * 20}
orig_loader = b._load_shadow_seed
b._load_shadow_seed = lambda: seed
try:
    ok(b._install_pinned_vol_history(st_l) is False,
       "legacy undated state refused at boot")
    ok(b._ECONOMIC_INPUT_INVALID[0] is True, "NNR latched for legacy state")
    st_f = {}
    ok(b._install_pinned_vol_history(st_f) is True, "fresh state bootstraps")
    ok(b._valid_controller_ledger(st_f.get("_controller_ledger")),
       "fresh bootstrap ledger valid")
    ok(b._ECONOMIC_INPUT_INVALID[0] is False, "latch cleared on proof")
    st_m = {"_controller_ledger": {"schema": "controller_ledger/1",
                                   "entries": "junk"}}
    ok(b._install_pinned_vol_history(st_m) is False,
       "malformed ledger refused (no silent repair)")
    ok(b._ECONOMIC_INPUT_INVALID[0] is True, "NNR latched for malformed")
finally:
    b._load_shadow_seed = orig_loader

# --- safety records flag a malformed ledger ---
stx = {"_controller_ledger": {"schema": "controller_ledger/1",
                              "entries": []}}
ok(not b._validate_safety_records(stx, log_bad=False),
   "malformed ledger fails safety records")

print(f"test_controller_ledger: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
