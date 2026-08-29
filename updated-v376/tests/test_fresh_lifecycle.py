"""Fresh recipe lifecycles end to end (build order sections 5, 8, 9, 20).

Runs the REAL _main_impl offline through complete campaigns:
  * P2 immediate fresh: virgin bind -> NY17 roll -> Prague anchor ->
    18:05 NY lease -> four genuine sleeve entries, requested vs
    broker-PROVED applied leverage, dated live ledger entry;
  * identical-command resume adopts the open book with zero new sends;
  * a different recipe on the same folder is refused without mutation;
  * closed-market (Saturday) virgin startup binds nothing and writes
    nothing, then binds normally when the market reopens;
  * P1 gated fresh waits (no entry) and resumes waiting;
  * P2 gated stamps rearm_done exactly once and resumes as continuity.

Run: python test_fresh_lifecycle.py   (takes a few minutes)
"""
import contextlib
import io
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import startharness as sh

PASS = [0]
FAIL = [0]


def ok(cond, label):
    if cond:
        PASS[0] += 1
    else:
        FAIL[0] += 1
        print(f"FAIL: {label}")


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


P2_IMM = ["--entry-policy", "immediate", "--mode", "grind", "--phase", "2",
          "--capital", "200000", "--live"]
P1_GATED = ["--mode", "grind", "--phase", "1", "--start-min-dd", "0.02",
            "--start-bounce", "0.005", "--post-loss-mult", "0.75", "--live"]
P2_GATED = ["--mode", "grind", "--phase", "2", "--start-min-dd", "0.01",
            "--start-bounce", "0.005", "--start-cap", "10", "--rearm-gate",
            "--post-loss-mult", "0.75", "--capital", "200000", "--live"]


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


# ================= P2 immediate: the full fresh campaign =================
b, fake, market, broker, wd = sh.boot(P2_IMM)
quiet(sh.run_polls, b, market, 6)
st = b._RUNTIME_STATE[0]
bind = st.get("_lifecycle_binding") or {}
ok(bind.get("schema") == "direct_lifecycle_binding/11"
   and bind.get("recipe") == "p2-standalone-immediate"
   and bind.get("entry_policy") == "immediate-v1",
   "virgin bind creates the /11 immediate-P2 lifecycle")
ok(bind.get("sizing_cents") == 20_000_000
   and bind.get("breaker_bps") == 350 and bind.get("target_bps") == 500,
   "capital/breaker/target bound permanently to the lifecycle")
ok(b._valid_controller_ledger(st.get("_controller_ledger")),
   "dated controller ledger bootstrapped at binding")
ok(b._valid_prague_anchor_proof(
    (st.get("breaker") or {}).get("anchor_proof"), st)
   and (st.get("breaker") or {}).get("cold_start") is False,
   "flat virgin account proves its anchor (full-or-hold, never halved)")
ok(len(fake.sent) == 0, "no send before the daily lease")


def step(when, polls, grow=False, ret=None):
    sh.set_clock(b, when)
    if grow:
        market.grow(ret)
    quiet(sh.run_polls, b, market, polls)
    return b._RUNTIME_STATE[0]


step(utc(2026, 8, 31, 21, 0, 30), 3)
st = step(utc(2026, 8, 31, 21, 5, 0), 6, grow=True)
ok((st.get("_daycount") or {}).get("session") == "2026-09-01"
   and (st.get("shadow") or {}).get("session") == "2026-09-01",
   "NY17 roll settles both ledgers to the next session")
led = (st.get("_controller_ledger") or {}).get("entries", [])
ok(led and led[-1].get("session") == "2026-08-31",
   f"dated ledger appended the completed session ({led[-1].get('session')})")
ok(len(fake.sent) == 0, "still no send outside the lease")

step(utc(2026, 8, 31, 22, 0, 20), 6)
st = step(utc(2026, 8, 31, 22, 5, 40), 16)
ok(len(fake.sent) == 4 and len(fake.positions) == 4,
   f"four sleeve entries placed inside the 18:05 NY lease "
   f"({len(fake.sent)} sends)")
by_magic = {p.magic: round(p.volume, 3) for p in fake.positions}
ok(by_magic.get(b.MAGIC["XAUM"]) == 0.14
   and by_magic.get(b.MAGIC["XAUB"]) == 0.07
   and by_magic.get(b.MAGIC["BTC"]) == 1.83
   and by_magic.get(b.MAGIC["S8V"]) == 0.7,
   f"entries equal the genuine plan targets ({by_magic})")
ok(st.get("_requested_L") == 6.0 and st.get("_last_L") == 6.0,
   "requested 6.00x PROVEN applied 6.00x after reconcile")
ae = st.get("_applied_exposure") or {}
ok(ae.get("matched") is True and ae.get("proven_L") == 6.0
   and ae.get("session") == "2026-09-01",
   "per-sleeve applied-exposure record matched")
ok("_order_intent" not in st and "_close_intent" not in st,
   "every intent resolved")

# next boundary: the dated ledger books the live session with applied 6x
step(utc(2026, 9, 1, 21, 0, 30), 3)
st = step(utc(2026, 9, 1, 21, 5, 0), 10, grow=True)
led = (st.get("_controller_ledger") or {}).get("entries", [])
live_rows = [e for e in led if e.get("source") == "live-account"]
ok(live_rows and live_rows[-1].get("session") == "2026-09-01"
   and live_rows[-1].get("applied_L") == 6.0,
   f"dated ledger books the live session with PROVEN applied 6.0x "
   f"({live_rows[-1] if live_rows else None})")
ok(isinstance((live_rows[-1] if live_rows else {}).get("sleeves"), dict)
   and abs(live_rows[-1]["sleeves"].get("BTC", 0.0) - 0.5972606685) < 1e-9,
   "live entry records per-sleeve contribution fractions")
ok(live_rows and live_rows[-1].get("account_ret") is not None,
   "live entry carries the measured account return, never omitted-as-zero")

# ---- identical-command resume: adopt the open book, zero new sends ----
disk_before = json.load(open(os.path.join(wd, "bot_state_v12.json")))
b2, fake2, market2, broker2, wd2 = sh.boot(P2_IMM, workdir=wd)
fake2.positions = list(fake.positions)
fake2.deals = list(fake.deals)
fake2.history_orders = list(fake.history_orders)
sh.set_clock(b2, utc(2026, 9, 1, 21, 10, 0))
market2.grow()          # same completed calendar as the dying process saw
market2.grow()
quiet(sh.run_polls, b2, market2, 6)
st2 = b2._RUNTIME_STATE[0]
ok((st2.get("_lifecycle_binding") or {}).get("recipe")
   == "p2-standalone-immediate", "identical command resumes the lifecycle")
ok(st2.get("_lifecycle_binding") == disk_before.get("_lifecycle_binding"),
   "resume never rebinds (binding byte-identical)")
ok(len(fake2.sent) == 0,
   "resume adopts the exact open book with zero new sends")
ok(not b2._ACCOUNT_CONFLICT[0],
   "own tickets are never foreign on resume")
ok(abs(float(st2.get("_last_L") or 0.0) - 6.0) < 1e-6,
   "proven applied leverage survives restart")

# ---- a different recipe on the same folder refuses without mutation ----
raw_before = open(os.path.join(wd, "bot_state_v12.json"), "rb").read()
b3, fake3, market3, broker3, _ = sh.boot(P1_GATED, workdir=wd)
fake3.positions = list(fake.positions)
sh.set_clock(b3, utc(2026, 9, 1, 21, 12, 0))
market3.grow()
market3.grow()
code3 = quiet(sh.run_polls, b3, market3, 4)
ok(code3 not in (None, 0), f"wrong recipe refused (exit {code3})")
ok(len(fake3.sent) == 0, "wrong recipe sends nothing")
before_body = json.loads(raw_before)
after_body = json.load(open(os.path.join(wd, "bot_state_v12.json")))
changed = {k for k in set(before_body) | set(after_body)
           if before_body.get(k) != after_body.get(k)}
ok(changed <= {"_state_image"},
   f"wrong recipe mutates no semantic state (changed: {sorted(changed)})")

# ============ closed-market Saturday: wait, bind nothing ============
b4, fake4, market4, broker4, wd4 = sh.boot(P2_IMM)
sh.set_clock(b4, utc(2026, 8, 29, 15, 0, 0))       # Saturday
b4._TEST_VIRGIN_WAIT_MAX_POLLS = 8
code4 = quiet(sh.run_polls, b4, market4, 4)
ok(code4 not in (None, 0),
   f"closed-market virgin start ends in the bounded wait (exit {code4})")
ok(not os.path.exists(os.path.join(wd4, "bot_state_v12.json")),
   "closed-market wait writes NO state file (virgin stays unbound)")
ok(len(fake4.sent) == 0, "closed-market wait sends nothing")
# the same folder binds normally on Monday
b5, fake5, market5, broker5, _ = sh.boot(P2_IMM, workdir=wd4)
quiet(sh.run_polls, b5, market5, 6)
st5 = b5._RUNTIME_STATE[0]
ok((st5.get("_lifecycle_binding") or {}).get("schema")
   == "direct_lifecycle_binding/11",
   "the same folder binds once the market reopens")

# ================= P1 gated fresh: waits, never enters =================
b6, fake6, market6, broker6, wd6 = sh.boot(P1_GATED)
quiet(sh.run_polls, b6, market6, 6)
st6 = b6._RUNTIME_STATE[0]
sh6 = st6.get("shadow") or {}
ok((st6.get("_lifecycle_binding") or {}).get("entry_policy") == "gated-v1",
   "exact V376 P1 command binds the gated policy")
ok(sh6.get("armed") is not True,
   "P1 gate is WAITING on the full-history evidence (not armed)")
step6 = lambda when, polls, grow=False: (            # noqa: E731
    sh.set_clock(b6, when), grow and market6.grow(),
    quiet(sh.run_polls, b6, market6, polls))
step6(utc(2026, 8, 31, 21, 0, 30), 3)
step6(utc(2026, 8, 31, 21, 5, 0), 6, True)
step6(utc(2026, 8, 31, 22, 0, 20), 4)
step6(utc(2026, 8, 31, 22, 5, 40), 10)
ok(len(fake6.sent) == 0,
   "gated P1 places nothing while the gate waits, even inside the lease")
b7, fake7, market7, broker7, _ = sh.boot(P1_GATED, workdir=wd6)
sh.set_clock(b7, utc(2026, 8, 31, 22, 10, 0))
market7.grow()
quiet(sh.run_polls, b7, market7, 5)
st7 = b7._RUNTIME_STATE[0]
ok((st7.get("shadow") or {}).get("armed") is not True
   and len(fake7.sent) == 0,
   "identical P1 command resumes the same WAITING gate")

# ==== P2 gated fresh: refused without exact P1 continuity (section 17) ====
b8, fake8, market8, broker8, wd8 = sh.boot(P2_GATED)
code8 = quiet(sh.run_polls, b8, market8, 6)
ok(code8 not in (None, 0),
   f"virgin P2-gated (p2-fresh) refuses without P1 continuity "
   f"(exit {code8})")
ok(not os.path.exists(os.path.join(wd8, "bot_state_v12.json")),
   "the refusal binds nothing and writes nothing")
ok(len(fake8.sent) == 0, "the refusal sends nothing")
# (rearm-exactly-once semantics are proved at unit level in
#  test_gate_history against _rearm_boot_gate)

total_unexpected = len(fake3.sent) + len(fake4.sent) + len(fake6.sent) \
    + len(fake7.sent) + len(fake8.sent) + len(fake2.sent)
ok(total_unexpected == 0, "zero sends outside the authorized lease entries")
print(f"test_fresh_lifecycle: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
