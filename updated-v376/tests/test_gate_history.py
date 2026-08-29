"""Full-history causal gate: 1:1 against the independent causal backtest
(build order sections 3 and 20).

Part A (always runs; needs only the shipped pinned seed):
  * drives the REAL bot gate (_check_arm, check-bounce-then-update-low)
    across EVERY eligible launch of the pinned full-history seed and
    compares each arm session 1:1 with an independently coded causal walk;
  * reproduces the audit census 5220 eligible / 5181 eventually armed /
    279 distinct arm events on the N=5250 horizon;
  * reproduces the July 24 crossing / July 31 true low / August 4 arm /
    August 5 first-eligible narrative from the bot's own session stamps;
  * proves the gate is FULL-HISTORY (seed carries a pre-window running
    peak), never the 40-session cold window;
  * exact threshold boundary probes (2%/1% crossing, 0.5% bounce,
    crossing-session-never-arms, cap force-arm, rearm-exactly-once,
    down-days streak with flat 0.0).

Part B (evidence-gated): loads the V376 oracle arrays from the supplied
376.zip and reproduces 269/279 = 96.4157706093% P1 passes for the exact
GRIND profile (causal arm+1 cohort, post-loss multiplier 0.75).

Run: python test_gate_history.py
"""
import importlib.util
import io
import json
import os
import sys
import zipfile
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
BOT = os.path.join(HERE, "..", "build", "vol_target_bot_v12.py")
SEED = os.path.join(HERE, "..", "build", "shadow_seed.json")
EVDIR = os.environ.get(
    "UPDATED_V376_EVIDENCE_DIR",
    "/tmp/claude-0/-home-user-aisharedhub/"
    "98eb14e8-29fe-5768-a7d5-491331594ddb/scratchpad/evidence")

PASS = [0]
FAIL = [0]


def ok(cond, label):
    if cond:
        PASS[0] += 1
    else:
        FAIL[0] += 1
        print(f"FAIL: {label}")


def load(argv, name):
    sys.argv = ["vol_target_bot_v12.py"] + argv
    spec = importlib.util.spec_from_file_location(name, BOT)
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    b._DIRECT_PROFILE = b._direct_match_recipe(argv)
    assert b._DIRECT_PROFILE is not None, argv
    return b


# The exact P1 gated profile: 2% crossing, 0.5% bounce, no cap.
b = load(["--mode", "grind", "--phase", "1", "--start-min-dd", "0.02",
          "--start-bounce", "0.005", "--post-loss-mult", "0.75", "--live"],
         "updbot_gate_p1")
ok(b.START_MIN_DD == 0.02 and b.START_BOUNCE == 0.005
   and b.START_CAP == 0, "P1 gated profile parameters bound")

seed = json.load(open(SEED))
DATES = seed["dates"]
EQ = [float(v) for v in seed["book_equity"]]
PEAK = [float(v) for v in seed["running_peak"]]
NFULL = len(EQ)
N = 5250                       # audit horizon (last 20 sessions withheld)


def oracle_arm(s, eq, peak_seed, horizon, X=0.02, Y=0.005):
    """Independent causal walk: crossing seeds the low at its own close;
    later sessions test the bounce BEFORE folding the new low."""
    peak = peak_seed[s - 1]
    crossed = None
    low = None
    low_at = None
    for t in range(s, horizon):
        e2 = eq[t]
        peak = max(peak, e2)
        if crossed is None:
            if e2 / peak - 1.0 <= -X:
                crossed, low, low_at = t, e2, t
        else:
            if e2 / low - 1.0 >= Y:
                return crossed, low, low_at, t
            if e2 < low:
                low, low_at = e2, t
    return crossed, low, low_at, None


def bot_arm(bmod, s, eq, peak_seed, horizon):
    """Drive the REAL _check_arm across the same launch."""
    sh = {"gate_eq": eq[s - 1], "gate_peak": peak_seed[s - 1],
          "eq": eq[s - 1], "peak": peak_seed[s - 1]}
    peak = peak_seed[s - 1]
    crossed_t = None
    for t in range(s, horizon):
        peak = max(peak, eq[t])
        sh["gate_eq"] = eq[t]
        sh["gate_peak"] = peak
        sh["eq"] = eq[t]
        sh["peak"] = peak
        bmod._GATE_EVENT_SESSION[0] = date.fromisoformat(
            DATES[t]).toordinal()
        armed = bmod._check_arm(sh)
        if crossed_t is None and sh.get("gate_crossed"):
            crossed_t = t
        if armed:
            return crossed_t, sh, t
    return crossed_t, sh, None


# ---- 1:1 sweep over every eligible launch on the audit horizon ----
starts = range(20, 5240)
eligible = 0
armed_count = 0
arm_events = set()
mismatches = 0
first_mismatch = None
for s in starts:
    eligible += 1
    o_cross, o_low, o_low_at, o_arm = oracle_arm(s, EQ, PEAK, N)
    b_cross, sh, b_arm = bot_arm(b, s, EQ, PEAK, N)
    if (o_arm != b_arm) or (o_cross != b_cross):
        mismatches += 1
        if first_mismatch is None:
            first_mismatch = (s, o_cross, b_cross, o_arm, b_arm)
    if b_arm is not None:
        armed_count += 1
        arm_events.add(b_arm)
ok(mismatches == 0,
   f"bot gate == causal oracle on every launch (first {first_mismatch})")
ok(eligible == 5220, f"eligible launches {eligible} == 5220")
ok(armed_count == 5181, f"eventually armed {armed_count} == 5181")
ok(len(arm_events) == 279, f"distinct arm events {len(arm_events)} == 279")

# ---- the recorded July/August narrative, from the bot's own stamps ----
i0 = DATES.index("2026-07-01")
b_cross, sh, b_arm = bot_arm(b, i0, EQ, PEAK, NFULL)
ok(DATES[b_cross] == "2026-07-24",
   f"crossing {DATES[b_cross]} == 2026-07-24")
ok(sh.get("gate_crossed_session") == "2026-07-24",
   "bot stamps the crossing session")
ok(sh.get("gate_low") == 2.6112726713577317,
   f"true post-crossing low bit-exact ({sh.get('gate_low')!r})")
ok(sh.get("gate_low_session") == "2026-07-31",
   f"low session {sh.get('gate_low_session')} == 2026-07-31")
ok(b_arm is not None and DATES[b_arm] == "2026-08-04",
   f"arm session {DATES[b_arm] if b_arm else None} == 2026-08-04")
ok(sh.get("armed_session") == "2026-08-04", "bot stamps the arm session")
ok(sh.get("armed") is True and sh.get("gate_armed_by") == "signal",
   "armed permanently by signal, not cap")
ok(DATES[b_arm + 1] == "2026-08-05",
   "first eligible earned session is the FOLLOWING session (2026-08-05)")
ok(sh.get("gate_cross_eq") == EQ[b_cross]
   and sh.get("gate_cross_dd") is not None,
   "crossing evidence recorded for the console")

# ---- full-history, never a cold launch-seeded gate ----
ok(PEAK[i0 - 1] > max(EQ[i0:b_cross + 1]),
   "the governing peak PREDATES the launch window (full-history seed)")


def cold_walk(peak0):
    """The same walk but with the peak seeded at launch (no pre-history)."""
    peak = peak0
    crossed = low = None
    for t in range(i0, NFULL):
        e = EQ[t]
        peak = max(peak, e)
        if crossed is None:
            if e / peak - 1.0 <= -0.02:
                crossed, low = t, e
        else:
            if e / low - 1.0 >= 0.005:
                return crossed, t
            low = min(low, e)
    return crossed, None


cold_cross, cold_arm = cold_walk(EQ[i0 - 1])
ok(cold_cross is None and cold_arm is None,
   "a cold gate seeded at the launch equity NEVER crosses — only the "
   "full-history peak produces the recorded 2026-07-24 crossing")

# ---- exact threshold boundary probes (P1: 2% / 0.5%) ----
b._TEST_SESSION_KEY = "2026-08-31"
b._GATE_EVENT_SESSION[0] = None
sh = {"gate_eq": 0.98, "gate_peak": 1.0}
ok(b._check_arm(sh) is False and sh.get("gate_crossed") is True,
   "dd exactly -2.000% crosses (inclusive) and can never arm same-session")
sh2 = {"gate_eq": 0.9800000001, "gate_peak": 1.0}
b._check_arm(sh2)
ok("gate_crossed" not in sh2, "dd one ulp above -2% does not cross")
# bounce boundary at the true IEEE-754 threshold: arm iff
# eq/low - 1 >= float("0.005"), measured off a low of exactly 1.0
import math
shb = {"gate_eq": 1.0, "gate_peak": 1.25}       # dd -20%: crossing, low=1.0
b._check_arm(shb)
assert shb["gate_low"] == 1.0
shb["gate_eq"] = math.nextafter(1.005, 2.0)      # first float >= +0.500%
ok(b._check_arm(shb) is True and shb["armed"] is True,
   "bounce at the exact +0.500% float boundary arms (inclusive >=)")
shb2 = {"gate_eq": 1.0, "gate_peak": 1.25}
b._check_arm(shb2)
shb2["gate_eq"] = 1.005                          # one ulp BELOW the boundary
ok(b._check_arm(shb2) is False and shb2.get("armed") is None,
   "bounce one ulp under +0.500% does not arm")
sh3 = {"gate_eq": 1.0, "gate_peak": 1.25}
b._check_arm(sh3)
sh3["gate_eq"] = 0.97
b._check_arm(sh3)
ok(sh3["gate_low"] == 0.97, "deeper close folds the low AFTER the test")
sh3["gate_eq"] = 0.97 * 1.0051
ok(b._check_arm(sh3) is True, "bounce re-measured off the true deeper low")

# down-days streak: a flat 0.0 session breaks it (backtest r<0 definition)
b.START_DOWN_DAYS = 2
sh4 = {"gate_eq": 1.0, "gate_peak": 1.0, "ret_hist": [-0.01, -0.02]}
ok(b._check_arm(sh4) is True, "two strictly-down sessions arm")
sh5 = {"gate_eq": 1.0, "gate_peak": 1.0, "ret_hist": [0.0, -0.02]}
ok(b._check_arm(sh5) is False, "flat 0.0 breaks the down-days streak")
b.START_DOWN_DAYS = 0

# ---- P2 gated profile: 1% crossing, cap 10, rearm exactly once ----
b2 = load(["--mode", "grind", "--phase", "2", "--start-min-dd", "0.01",
           "--start-bounce", "0.005", "--start-cap", "10", "--rearm-gate",
           "--post-loss-mult", "0.75", "--capital", "200000", "--live"],
          "updbot_gate_p2")
ok(b2.START_MIN_DD == 0.01 and b2.START_CAP == 10 and b2.REARM_GATE,
   "P2 gated profile parameters bound")
b2._TEST_SESSION_KEY = "2026-08-31"
sh6 = {"gate_eq": 0.99, "gate_peak": 1.0}
ok(b2._check_arm(sh6) is False and sh6.get("gate_crossed") is True,
   "P2 crossing at exactly -1.000%")
sh7 = {"gate_eq": 0.9900000001, "gate_peak": 1.0}
b2._check_arm(sh7)
ok("gate_crossed" not in sh7, "P2 no crossing one ulp above -1%")
sh8 = {"gate_eq": 1.0, "gate_peak": 1.0, "gate_cap_left": 0}
ok(b2._check_arm(sh8) is True and sh8["gate_armed_by"] == "cap",
   "expired ten-session cap force-releases")
sh9 = {"gate_eq": 1.0, "gate_peak": 1.0, "gate_cap_left": 1}
ok(b2._check_arm(sh9) is False, "cap 1 remaining still waits")

# rearm exactly once with a durable rearm_done record
st = {"shadow": {"armed": True, "gate_crossed": True, "gate_low": 0.9,
                 "gate_cap_left": 0}}
first = b2._rearm_boot_gate(st)
ok(first is True and st["rearm_done"] is True,
   "first --rearm-gate boot clears the arm and stamps rearm_done")
ok(st["shadow"].get("armed") is None
   and st["shadow"].get("gate_crossed") is None
   and st["shadow"].get("gate_low") is None
   and st["shadow"].get("gate_cap_left") == 10,
   "rearm reseeds a fresh crossing seek with the full cap")
st["shadow"]["armed"] = True
second = b2._rearm_boot_gate(st)
ok(second is False and st["shadow"]["armed"] is True,
   "identical P2 command on restart resumes; the arm is NEVER cleared twice")

# ============ Part B: V376 oracle arrays (evidence-gated) ============
zip_path = os.path.join(EVDIR, "376.zip")
if not os.path.isfile(zip_path):
    print(f"test_gate_history: {PASS[0]} pass, {FAIL[0]} fail "
          "(oracle-array part SKIPPED: evidence absent)")
    sys.exit(1 if FAIL[0] else 0)

outer = zipfile.ZipFile(zip_path)
inner = zipfile.ZipFile(io.BytesIO(outer.read("vol_target_v12_v376_full.zip")))
z = np.load(io.BytesIO(
    inner.read("analysis/entry_gate_edge/entry_gate_arrays.npz")))
rc, lo, gp, rv, mlo, dd = (z[k] for k in ("rc", "lo", "gp", "rv", "mlo",
                                          "dd"))
NZ = len(rc)
eq1 = np.cumprod(1 + rc)
ok(NZ == 5250, f"oracle horizon {NZ} == 5250")
ok(float(np.max(np.abs(dd - (eq1 / np.maximum.accumulate(eq1) - 1)))) == 0.0,
   "oracle dd is the exact full-history drawdown of its own equity")

GIDX = np.where(dd <= -0.02)[0]


def arm_hyst(s, Y=0.005):
    p = np.searchsorted(GIDX, s)
    if p >= len(GIDX):
        return -1
    c = int(GIDX[p])
    low = eq1[c]
    for t in range(c, NZ):
        if eq1[t] / low - 1 >= Y:
            return t
        low = min(low, eq1[t])
    return -1


all_days = np.arange(20, NZ - 10)
arms_all = np.array([arm_hyst(int(s)) for s in all_days])
armed_mask = arms_all >= 0
ua = np.array(sorted(set(arms_all[armed_mask])))
ok(len(all_days) == 5220, "oracle census: 5220 eligible launches")
ok(int(armed_mask.sum()) == 5181, "oracle census: 5181 eventually armed")
ok(len(ua) == 279, "oracle census: 279 distinct arm events")

P1 = dict(tv=2.0, D=15, B=1.75, T=10, tgt=0.10)
P2 = dict(tv=1.8, D=8, B=1.5, T=5, tgt=0.05)


def chain(arm, plm=1.0, brk=3.5, rec=0.0002, slip=0.25):
    arm = np.asarray(arm, int)
    ns = len(arm)
    eq = np.ones(ns)
    phase = np.ones(ns, int)
    alive = np.ones(ns, bool)
    res = np.zeros(ns, int)
    endd = np.full(ns, NZ - 1, int)
    age = np.zeros(ns, int)
    stand = np.zeros(ns, bool)
    pneg = np.zeros(ns, bool)
    p1res = np.zeros(ns, int)
    p1end = np.full(ns, -1, int)
    for d in range(int(arm.min()), NZ):
        act = alive & (arm <= d)
        if not act.any():
            continue
        idx = np.where(act)[0]
        e = eq[idx]
        ph = phase[idx]
        tv = np.where(ph == 1, P1["tv"], P2["tv"])
        tgt = np.where(ph == 1, P1["tgt"], P2["tgt"])

        def bo(cfg):
            D, Bv, Tt = cfg["D"], cfg["B"], cfg["T"]
            ag = age[idx]
            return np.where(ag < D, Bv,
                            np.where(ag < D + Tt,
                                     1 + (Bv - 1) * (D + Tt - ag) / Tt, 1.0))

        boost = np.where(ph == 1, bo(P1), bo(P2))
        mult = np.clip(np.clip((e - 0.90) / 0.10, 0, None) ** 1.5,
                       0.10, 1.5) * boost
        L = np.clip((tv / 100) / rv[d], 1.0, 10.0) * mult
        g_ = (1 + tgt) - e
        L = np.where(g_ < 0.02, L * np.maximum(0.35, g_ / 0.02), L)
        if plm < 1.0:
            L = np.where(pneg[idx], L * plm, L)
        L = np.minimum(np.minimum(L, 0.05 / (2.5 * rv[d])),
                       np.minimum(1.5 * (brk / 100) / mlo[d], 10.0))
        sdm = stand[idx]
        Ld = np.where(sdm, 0.0, L)
        r = rc[d] * Ld
        rl = lo[d] * Ld
        rg = gp[d] * Ld
        fired = (rl <= -brk / 100) & (Ld > 0)
        r = np.where(fired,
                     -brk / 100 - np.maximum(0, (-rl) - brk / 100) * slip, r)
        r = np.where(sdm, -rec, r)
        fday = (r <= -0.05) | (np.where(Ld <= 0, 0.0, rg) <= -0.05)
        en = e * (1 + r)
        fdd = (en <= 0.90) & ~fday
        ps = (en >= 1 + tgt) & ~fday & ~fdd
        eq[idx] = en
        age[idx] += 1
        stand[idx] = fired
        pneg[idx] = r < 0
        dead = fday | fdd
        if dead.any():
            j = idx[dead]
            res[j] = 2
            alive[j] = False
            endd[j] = d
            jp = j[phase[j] == 1]
            p1res[jp] = 2
            p1end[jp] = d
        adv = ps & (ph == 1)
        if adv.any():
            j = idx[adv]
            p1res[j] = 1
            p1end[j] = d
            phase[j] = 2
            eq[j] = 1.0
            age[j] = 0
            stand[j] = False
            pneg[j] = False
        win = ps & (ph == 2)
        if win.any():
            j = idx[win]
            res[j] = 1
            alive[j] = False
            endd[j] = d
    return res, endd, p1res, p1end


# causal cohort: the first EARNED session is arm+1 (never the arm day)
ua_c = ua + 1
ua_c = ua_c[ua_c < NZ]
ok(len(ua_c) == 279, "causal cohort keeps all 279 arm events")
res, endd, p1res, p1end = chain(ua_c, plm=0.75)
p1pass = int((p1res == 1).sum())
ratio = p1pass / len(ua_c) * 100
ok(p1pass == 269, f"P1 passes {p1pass} == 269 (plm=0.75, causal arm+1)")
ok(f"{ratio:.10f}" == "96.4157706093",
   f"269/279 == 96.4157706093% (got {ratio:.10f}%)")
res10, _, p1res10, _ = chain(ua_c, plm=1.0)
ok(int((p1res10 == 1).sum()) != p1pass,
   "post-loss multiplier is live in the physics (plm=1.0 differs)")

print(f"test_gate_history: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
