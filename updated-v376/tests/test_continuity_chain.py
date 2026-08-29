"""P1 -> P2 continuity chain END TO END (build order section 17).

The REAL chain, with no fail-closed shortcut standing in for success:
  * a P1-immediate campaign across 21 complete NY17 sessions (dated
    live-account ledger entries, daily re-proved applied leverage);
  * a genuine rally to the +10% target: the ALIGNED completion carries a
    PREPARED continuity transaction and NO audit marker (a clean
    completion must never be poisoned);
  * --export-continuity on the completed folder performs the terminal
    fold and WRITES the hash-enveloped shadow_continuity.json (exit 0);
  * a second export run is non-destructive (file byte-identical);
  * a TAMPERED envelope on a fresh P2-gated folder refuses before any
    binding or state write;
  * the pristine envelope on a fresh P2-gated folder (fresh $200k
    account) is adopted: /11 p2-fresh binding with the continuity
    identity sealed, rearm consumed exactly once, the gate re-seeking
    fresh, zero sends, and no spurious target completion.

Run: python test_continuity_chain.py   (takes a few minutes)
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
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

# ---- P1 immediate campaign across 21 complete sessions ----
b, fake, market, broker, wd = sh.boot(P1_IMM)
quiet(sh.drive_to_authorized, b, market)
sh.set_clock(b, utc(2026, 8, 31, 22, 5, 40))
quiet(sh.run_polls, b, market, 16)
ok(len(fake.positions) == 4, "P1 immediate placed the four sleeve entries")
quiet(sh.run_sessions, b, market, 21)
st = b._RUNTIME_STATE[0]
led = (st.get("_controller_ledger") or {}).get("entries", [])
observed = [e for e in led if e.get("source") in ("live-account",
                                                  "standdown")]
ok(len(observed) >= 20,
   f"21 sessions booked as dated live observations ({len(observed)})")
ok(b._window_live_proven(st),
   "the 20-observation window is proven fully live from its own ledger")

# ---- a genuine rally lifts the book through the +10% target ----
gross = sum(abs(p.volume) * (100.0 if "XAU" in p.symbol else 1.0)
            * p.price_open for p in fake.positions) / max(
                fake.account.equity, 1.0)
need = (220000.0 - fake.account.equity) / fake.account.equity + 0.03
for sym in market.closes:
    market.closes[sym][-1] *= (1.0 + need / max(gross, 0.2))
forming = market.next_session_after(market.sessions[-1])
sh.set_clock(b, datetime(forming.year, forming.month, forming.day, 10, 0,
                         tzinfo=sh.NY).astimezone(timezone.utc))
sh.refresh_ticks(b, market)
quiet(sh.run_polls, b, market, 200, refresh=False)
disk = json.load(open(os.path.join(wd, "bot_state_v12.json")))
hit = disk.get("_target_hit")
ok(isinstance(hit, dict) and hit.get("status") == "TARGET_HIT"
   and hit.get("stage") == "p1",
   "P1 campaign permanently completed at $220k")
ok(fake.account.balance >= 220000.0,
   f"realized P1 balance {fake.account.balance}")
txn = disk.get("_continuity_export_txn")
ok(isinstance(txn, dict) and txn.get("stage") == "PREPARED",
   f"ALIGNED completion carries a PREPARED continuity transaction "
   f"({(txn or {}).get('stage')})")
ok("_post_hit_catchup" not in disk,
   "a clean aligned completion is NEVER poisoned with an audit marker")

# ---- the export command performs the terminal fold and WRITES the file ----
carry = dict(deals=list(fake.deals), history=list(fake.history_orders),
             balance=fake.account.balance)


def export_boot(polls=80, ny_hhmm=(17, 20)):
    b2, fake2, market2, broker2, _ = sh.boot(["--export-continuity"],
                                             workdir=wd)
    b2._TEST_TARGET_HIT_EXPORT_MAX_POLLS = polls
    b2._TEST_TARGET_HIT_EXPORT_POLL_HOOK = lambda poll, stx: time.sleep(0.05)
    fake2.account.balance = carry["balance"]
    fake2.deals = list(carry["deals"])
    fake2.history_orders = list(carry["history"])
    market2.sessions = list(market.sessions)
    market2.closes = {sym: list(vals) for sym, vals in market.closes.items()}
    market2.rebuild()
    market2.grow()                     # the hit session's own bar completes
    last = market2.sessions[-1]
    sh.set_clock(b2, datetime(last.year, last.month, last.day, ny_hhmm[0],
                              ny_hhmm[1], tzinfo=sh.NY).astimezone(
                                  timezone.utc))
    code = quiet(sh.run_polls, b2, market2, polls)
    return b2, fake2, market2, code


b2, fake2, market2, code2 = export_boot()
ok(code2 == 0, f"exporter completes the terminal fold and exits 0 ({code2})")
ok(os.path.exists(b2.CONTINUITY_FILE),
   "shadow_continuity.json written beside the completed folder")
ok(len(fake2.sent) == 0, "the exporter sends nothing")
envelope = json.load(open(b2.CONTINUITY_FILE))
ok(envelope.get("schema") == "shadow_continuity_envelope/1"
   and isinstance(envelope.get("payload"), dict)
   and isinstance(envelope.get("payload_sha256"), str),
   "hash-enveloped continuity artifact")
ok(b2._load_continuity(b2.CONTINUITY_FILE) is not None,
   "the bot's own loader verifies the envelope")
st2 = b2.load_state()
ok((st2.get("_continuity_export_txn") or {}).get("stage")
   == "ARTIFACT_COMMITTED",
   "export transaction sealed ARTIFACT_COMMITTED in the images")

# ---- a second export run is non-destructive ----
before = open(b2.CONTINUITY_FILE, "rb").read()
b2b, fake2b, market2b, code2b = export_boot(polls=30, ny_hhmm=(17, 40))
after = open(b2b.CONTINUITY_FILE, "rb").read()
ok(before == after and len(fake2b.sent) == 0,
   "re-running the exporter never corrupts or duplicates the artifact")

# ---- a tampered envelope refuses before any binding or state write ----
b3, fake3, market3, broker3, wd3 = sh.boot(P2_GATED)
tampered = dict(envelope)
tampered["payload_sha256"] = "0" * 64
json.dump(tampered, open(os.path.join(wd3, "shadow_continuity.json"), "w"))
fake3.account.balance = 200000.0
market3.sessions = list(market2.sessions)
market3.closes = {sym: list(vals) for sym, vals in market2.closes.items()}
market3.rebuild()
last3 = market3.sessions[-1]
sh.set_clock(b3, datetime(last3.year, last3.month, last3.day, 17, 30,
                          tzinfo=sh.NY).astimezone(timezone.utc))
code3 = quiet(sh.run_polls, b3, market3, 8)
ok(code3 not in (None, 0),
   f"tampered continuity refuses the fresh folder outright (exit {code3})")
ok(not os.path.exists(os.path.join(wd3, "bot_state_v12.json")),
   "the tampered refusal binds nothing and writes nothing")
ok(len(fake3.sent) == 0, "the tampered refusal sends nothing")

# ---- the pristine envelope is ADOPTED by a fresh P2-gated folder ----
b4, fake4, market4, broker4, wd4 = sh.boot(P2_GATED)
shutil.copy(b2.CONTINUITY_FILE, os.path.join(wd4, "shadow_continuity.json"))
fake4.account.balance = 200000.0        # fresh phase-2 account: continuity
                                        # excludes account/cash by design
market4.sessions = list(market2.sessions)
market4.closes = {sym: list(vals) for sym, vals in market2.closes.items()}
market4.rebuild()
last4 = market4.sessions[-1]
sh.set_clock(b4, datetime(last4.year, last4.month, last4.day, 17, 30,
                          tzinfo=sh.NY).astimezone(timezone.utc))
quiet(sh.run_polls, b4, market4, 12)
st4 = b4._RUNTIME_STATE[0]
bind4 = (st4 or {}).get("_lifecycle_binding") or {}
ok(bind4.get("schema") == "direct_lifecycle_binding/11"
   and bind4.get("recipe") == "p2-fresh",
   "the exact P2-gated command binds the fresh folder from continuity")
ok(bool(bind4.get("continuity_sha256")),
   "the adopted continuity identity is sealed into the binding")
ok((st4 or {}).get("rearm_done") is True,
   "rearm consumed exactly once at adoption")
ok(((st4 or {}).get("shadow") or {}).get("armed") is not True,
   "the P2 gate re-seeks fresh (journey-table convention), not armed")
ok("_target_flat_watch" not in (st4 or {})
   and "_target_hit" not in (st4 or {}),
   "no spurious target completion on the fresh $200k account")
ok(len(fake4.sent) == 0, "adoption sends nothing")

print(f"test_continuity_chain: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
