"""Exact V376 five-sleeve formula equivalence (build order section 20).

Imports the trusted V376 source (bot/vol_target_bot_v12.py from the
supplied 376.zip, byte-identical to vps/) as the oracle and EXECUTES both
implementations side by side: momentum ensemble (BTC/XAUM/XAUB incl. the
beta path), S8V tranche fraction and down-day, the full controller
(cushion/boost/lock/leverage with every guard), sleeve caps and signal
readiness — over the real seed closes and a seeded random sweep — plus
every frozen strategy constant, and the permanent ONF disable.

Skips when evidence is absent.  Zero broker anything: neither module
ever sees a terminal.  Run: python test_formula_equivalence.py
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import zipfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
BOT = os.path.join(HERE, "..", "build", "vol_target_bot_v12.py")
SEED = os.path.join(HERE, "..", "build", "shadow_seed.json")
EVDIR = os.environ.get(
    "UPDATED_V376_EVIDENCE_DIR",
    os.path.join(HERE, "..", "evidence"))

zip_path = os.path.join(EVDIR, "376.zip")
if not os.path.isfile(zip_path):
    print("test_formula_equivalence: evidence absent — SKIPPED")
    sys.exit(0)

PASS = [0]
FAIL = [0]


def ok(cond, label):
    if cond:
        PASS[0] += 1
    else:
        FAIL[0] += 1
        print(f"FAIL: {label}")


# ---- load the trusted V376 oracle from the supplied archive ----
outer = zipfile.ZipFile(zip_path)
inner = zipfile.ZipFile(io.BytesIO(outer.read("vol_target_v12_v376_full.zip")))
assert inner.read("bot/vol_target_bot_v12.py") == inner.read(
    "vps/vol_target_bot_v12.py"), "376.zip bot/ and vps/ copies must match"
tmpdir = tempfile.mkdtemp(prefix="v376oracle-")
oracle_path = os.path.join(tmpdir, "v376_oracle.py")
open(oracle_path, "wb").write(inner.read("bot/vol_target_bot_v12.py"))

sys.argv = ["vol_target_bot_v12.py"]
spec = importlib.util.spec_from_file_location("v376_oracle", oracle_path)
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)

spec2 = importlib.util.spec_from_file_location("updbot_formula", BOT)
U = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(U)
ok(V.BOT_BUILD == "v3.7.6", f"oracle is the trusted V376 ({V.BOT_BUILD})")

# ---- frozen strategy constants ----
for name in ("WEIGHTS", "SHADOW_W", "SLEEVE_SYMBOL", "MODES", "PHASE_TARGET",
             "MOME_SMAS"):
    ok(getattr(V, name) == getattr(U, name), f"{name} identical")
for name in ("S8V_BASE_FRAC", "S8V_TGT", "S8V_VOLFLOOR", "S8V_MAX_TRANCHES",
             "S8V_HOLD_DAYS", "BTC_TGTVOL", "BTC_MAXPOS", "XAUM_TGTVOL",
             "XAUM_MAXPOS", "XAUB_TGTVOL", "XAUB_MAXPOS", "VOL_LOOKBACK",
             "BREAKER_PCT", "GMULT", "THETA", "ALPHA", "MCAP", "MFLOOR",
             "LOCK_BAND", "LOCK_FLOOR", "MAX_LEVERAGE", "MIN_LEVERAGE",
             "FLOOR_PCT", "ONF_SIZE", "ONF_SMA"):
    ok(getattr(V, name, None) == getattr(U, name, None),
       f"{name} identical ({getattr(V, name, None)})")
ok(U.MAX_SLEEVE_FRAC == 0.60, "sleeve cap frozen at 0.60")
ok(V.WEIGHTS == dict(ORB=0.40, S8V=0.10, ONF=0.15, BTC=0.20,
                     XAUM=0.10, XAUB=0.05), "book weights are the V376 book")
ok(U.ENABLE_ONF is False, "ONF permanently disabled")
ok(U._direct_match_recipe(["--enable-onf", "--mode", "grind", "--phase", "1",
                           "--live"]) is None,
   "no accepted recipe can enable ONF")

# ---- real market data: the pinned seed closes ----
seed = json.load(open(SEED))
CLOSES = {k: np.array(seed["closes"][k], float) for k in ("nas", "xau",
                                                          "btc")}

SLEEVE_ARGS = (("BTC", "btc", V.BTC_TGTVOL, V.BTC_MAXPOS, False),
               ("XAUM", "xau", V.XAUM_TGTVOL, V.XAUM_MAXPOS, False),
               ("XAUB", "xau", V.XAUB_TGTVOL, V.XAUB_MAXPOS, True))

mismatch = 0
checked = 0
for name, key, tv, mp, beta in SLEEVE_ARGS:
    series = CLOSES[key]
    for end in range(max(V.MOME_SMAS) + V.VOL_LOOKBACK + 1, len(series), 7):
        window = series[:end]
        a = V.mome_signal(window, tv, mp, beta=beta)
        bmod = U.mome_signal(window, tv, mp, beta=beta)
        checked += 1
        if not (a == bmod or (np.isnan(a) and np.isnan(bmod))):
            mismatch += 1
ok(mismatch == 0,
   f"momentum ensemble bit-identical over {checked} real-seed windows "
   f"({mismatch} mismatches)")

s_mis = 0
s_chk = 0
for end in range(V.VOL_LOOKBACK + 2, len(CLOSES["nas"]), 11):
    window = CLOSES["nas"][:end]
    if V.s8v_tranche_fraction(window) != U.s8v_tranche_fraction(window):
        s_mis += 1
    if V.is_down_day(window) != U.is_down_day(window):
        s_mis += 1
    if V.onf_regime_ok(window) != U.onf_regime_ok(window):
        s_mis += 1
    s_chk += 3
ok(s_mis == 0, f"S8V fraction / down-day / ONF regime bit-identical over "
   f"{s_chk} real-seed windows")

# ---- random sweep (seeded) for the same functions ----
rng = np.random.default_rng(376389)
r_mis = 0
for _ in range(300):
    n = int(rng.integers(V.VOL_LOOKBACK + 2, 400))
    walk = 100.0 * np.cumprod(1 + rng.normal(0, 0.012, n))
    for tv, mp, beta in ((V.BTC_TGTVOL, V.BTC_MAXPOS, False),
                         (V.XAUB_TGTVOL, V.XAUB_MAXPOS, True)):
        if n > max(V.MOME_SMAS) + V.VOL_LOOKBACK:
            if V.mome_signal(walk, tv, mp, beta=beta) != U.mome_signal(
                    walk, tv, mp, beta=beta):
                r_mis += 1
    if V.s8v_tranche_fraction(walk) != U.s8v_tranche_fraction(walk):
        r_mis += 1
ok(r_mis == 0, "random-walk sweep bit-identical (300 seeded walks)")

# ---- the full controller: cushion/boost/lock/leverage with all guards ----
# V376 CFG binds from --mode/--phase at import; compare per-mode by
# rebinding both modules' CFG to the same frozen dicts.
c_mis = 0
c_chk = 0
for mode in ("GRIND",):
    for phase in (1, 2):
        V.CFG = V.MODES[mode][phase]
        U.CFG = U.MODES[mode][phase]
        V.TARGET = V.PHASE_TARGET[phase]
        U.TARGET = U.PHASE_TARGET[phase]
        for er in np.linspace(0.85, 1.12, 14):
            for vol in (0.0004, 0.0005, 0.0017732027554917184, 0.0034967,
                        0.006, 0.012, 0.02):
                for dip in (0.0, 0.004, 0.006, 0.0122, 0.03):
                    for age in (0, 3, 8, 15, 20, 40):
                        for pl in (0.75, 1.0):
                            a = V.book_leverage(er, vol, dip, age, pl)
                            bmod = U.book_leverage(er, vol, dip, age, pl)
                            c_chk += 1
                            if a != bmod:
                                c_mis += 1
        for er in np.linspace(0.80, 1.15, 36):
            if (V.cushion_mult(er) != U.cushion_mult(er)
                    or V.target_lock(er) != U.target_lock(er)):
                c_mis += 1
        for age in range(0, 41):
            if V.age_boost(age) != U.age_boost(age):
                c_mis += 1
ok(c_mis == 0,
   f"controller bit-identical over {c_chk} leverage grid points "
   f"(both phases, incl. the defect vol values 0.17732%/0.34967%)")
ok(V.book_leverage(1.0, 0.0034967, 0.0122, 40, 1.0)
   == U.book_leverage(1.0, 0.0034967, 0.0122, 40, 1.0),
   "reconstructed-defect operating point identical")

# ---- sleeve caps and signal readiness ----
cap_mis = 0
for _ in range(200):
    fr = {"ORB": float(rng.uniform(-0.5, 0.5)),
          "S8V": float(rng.uniform(0, 0.4)),
          "ONF": 0.0,
          "BTC": float(rng.uniform(-0.6, 0.6)),
          "XAUM": float(rng.uniform(0, 0.7)),
          "XAUB": float(rng.uniform(0, 0.5))}
    for xa in (True, False):
        for bt in (True, False):
            if V._cap_fracs(dict(fr), xa, bt) != U._cap_fracs(dict(fr),
                                                              xa, bt):
                cap_mis += 1
ok(cap_mis == 0, "sleeve-cap fractions bit-identical (800 random books)")
for series, want in ((CLOSES["xau"], True), (CLOSES["xau"][:5], False),
                    (None, False)):
    ok(V._sig_ready(series) == U._sig_ready(series) == want,
       f"signal readiness identical ({want})")

print(f"test_formula_equivalence: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
