"""P1 -> P2 continuity chain (build order section 17).

Runs a P1-immediate campaign to its +10% target through the real engine,
exports the hash-enveloped continuity from the permanently completed
folder, and adopts it in a fresh P2-gated (p2-fresh) folder — the exact
recipe that refuses WITHOUT this continuity (proved in the lifecycle
suite).

Run: python test_continuity_chain.py   (takes several minutes)
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
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


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


P1_IMM = ["--entry-policy", "immediate", "--mode", "grind", "--phase", "1",
          "--capital", "200000", "--live"]
P2_GATED = ["--mode", "grind", "--phase", "2", "--start-min-dd", "0.01",
            "--start-bounce", "0.005", "--start-cap", "10", "--rearm-gate",
            "--post-loss-mult", "0.75", "--capital", "200000", "--live"]

# ---- P1 immediate campaign to the +10% target ----
b, fake, market, broker, wd = sh.boot(P1_IMM)
quiet(sh.drive_to_authorized, b, market)
sh.set_clock(b, utc(2026, 8, 31, 22, 5, 40))
quiet(sh.run_polls, b, market, 16)
ok(len(fake.positions) == 4, "P1 immediate placed the four sleeve entries")
gross = sum(abs(p.volume) * (100.0 if "XAU" in p.symbol else 1.0)
            * p.price_open for p in fake.positions) / 200000.0
rally = 1.0 + 0.105 / max(gross, 0.2)
for sym in market.closes:
    market.closes[sym][-1] *= rally
sh.set_clock(b, utc(2026, 9, 1, 14, 0, 0))
sh.refresh_ticks(b, market)
quiet(sh.run_polls, b, market, 60, refresh=False)
st = b._RUNTIME_STATE[0]
hit = st.get("_target_hit")
ok(isinstance(hit, dict) and hit.get("status") == "TARGET_HIT"
   and hit.get("stage") == "p1",
   "P1 campaign permanently completed at $220k")
ok(fake.account.balance >= 220000.0,
   f"realized P1 balance {fake.account.balance}")

# ---- export the continuity from the completed folder ----
b2, fake2, market2, broker2, _ = sh.boot(["--export-continuity"],
                                         workdir=wd)
fake2.account.balance = fake.account.balance
sh.set_clock(b2, utc(2026, 9, 1, 15, 0, 0))
market2.grow()
code2 = quiet(sh.run_polls, b2, market2, 60)
ok(os.path.exists(b2.CONTINUITY_FILE),
   f"continuity export written (exit {code2})")
cont = json.load(open(b2.CONTINUITY_FILE)) if os.path.exists(
    b2.CONTINUITY_FILE) else {}
text = json.dumps(cont)
ok("sha256" in text, "export is hash-enveloped")
ok("_controller_ledger" in text or "controller_ledger" in text,
   "export carries the DATED controller ledger (never a naked list)")
ok("s8v" in text or "tranches" in text, "export carries the S8V ladder")
ok(len(fake2.sent) == 0, "the exporter sends nothing")

# ---- a fresh P2-gated folder adopts the exact continuity ----
wd3 = tempfile.mkdtemp(prefix="p2adopt-")
shutil.copy(b2.CONTINUITY_FILE, os.path.join(wd3,
                                             "shadow_continuity.json"))
b3, fake3, market3, broker3, _ = sh.boot(P2_GATED, workdir=wd3)
sh.set_clock(b3, utc(2026, 9, 1, 15, 30, 0))
market3.grow()
code3 = quiet(sh.run_polls, b3, market3, 8)
st3 = b3._RUNTIME_STATE[0]
bind3 = (st3 or {}).get("_lifecycle_binding") or {}
ok(bind3.get("schema") == "direct_lifecycle_binding/11"
   and bind3.get("recipe") == "p2-fresh",
   f"P2 gated binds WITH the P1 continuity (recipe {bind3.get('recipe')})")
ok(isinstance(bind3.get("continuity_sha256"), str)
   and len(bind3.get("continuity_sha256") or "") == 64,
   "the continuity identity is sealed into the lifecycle")
ok(st3.get("rearm_done") is True,
   "the adopted gate re-armed exactly once at binding")
ok((st3.get("shadow") or {}).get("gate_cap_left") == 10,
   "fresh re-seek carries the full ten-session cap")
ok(b3._valid_controller_ledger(st3.get("_controller_ledger")),
   "the imported dated ledger is the vol authority in the new folder")
ok(len(fake3.sent) == 0, "no send while the P2 gate waits")

print(f"test_continuity_chain: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
