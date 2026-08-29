"""One-time r4 migration incident test (build order sections 13/20).

Reproduces the exact supplied r4 state + live positions offline and drives
the migration end to end, including interruption/native-resume at every
stage.  Zero broker sends throughout.

Run: python test_r4_migration.py   (skips if evidence absent)
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r4harness

if not os.path.isfile(os.path.join(r4harness.EVDIR, "bot_state_v12.json")):
    print("test_r4_migration: evidence absent — SKIPPED")
    sys.exit(0)

PASS = [0]
FAIL = [0]


def ok(cond, label):
    if cond:
        PASS[0] += 1
    else:
        FAIL[0] += 1
        print(f"FAIL: {label}")


def advance(b, st, expect, label):
    outcome = b._advance_r4_migration(st)
    ok(outcome == expect, f"{label}: outcome {outcome!r} != {expect!r}")
    return outcome


# ---------- full pass, stage by stage ----------
b, fake, st, workdir = r4harness.boot()
ok(b._r4_migration_required(st), "r4 migration required on the r4 state")
ok(b._r4_migration_source_shape_ok(st), "source shape validates")
ok(b._new_risk_blocked(), "new risk blocked before migration")

advance(b, st, "wait", "PREPARE")
ok(st.get("_r4_migration", {}).get("stage") == "PREPARED", "stage PREPARED")
advance(b, st, "wait", "INVENTORY")
ok(st["_r4_migration"]["stage"] == "INVENTORY_PROVED",
   "stage INVENTORY_PROVED")
advance(b, st, "wait", "LEDGER")
ok(st["_r4_migration"]["stage"] == "LEDGER_REBUILT", "stage LEDGER_REBUILT")

# the rebuilt dated window is the CORRECTED vol authority
led = st.get("_controller_ledger")
ok(b._valid_controller_ledger(led), "rebuilt ledger valid")
sessions = [e["session"] for e in led["entries"]]
ok(sessions[-1] == "2026-08-27" and sessions[-2] == "2026-08-26"
   and sessions[-3] == "2026-08-25", f"live tail sessions {sessions[-3:]}")
tail = led["entries"]
ok(tail[-1]["source"] == "shadow-live"
   and "account-return-omitted" in tail[-1]["flags"]
   and tail[-1]["account_ret"] is None,
   "omitted 08-27 account return recorded as omitted, never zero")
ok(tail[-2]["source"] == "live-account"
   and tail[-2]["applied_L"] == 4.375
   and "applied-L-unverified-legacy" in tail[-2]["flags"],
   "live 08-26 carries recorded legacy applied 4.375")
gap_entries = [e for e in tail if e["source"] == "shadow-backfill"]
ok(len(gap_entries) >= 11, f"gap sessions reconstructed ({len(gap_entries)})")
ok(all("2026-08-10" <= e["session"] <= "2026-08-24" for e in gap_entries),
   "gap sessions dated 08-10..08-24")

import numpy as np
stale_vol = 0.0017732027554917184
new_vol = float(np.std(np.array(st["book_returns"], float)))
ok(abs(new_vol - stale_vol) > 5e-4,
   f"stale 0.1773% window replaced (now {new_vol*100:.4f}%)")
ok(st["book_returns"][-1] == tail[-1]["book_ret"],
   "windows derived from the dated ledger")

# ---------- commit ----------
advance(b, st, "committed", "COMMIT")
rec = st["_r4_migration"]
ok(rec["stage"] == "COMMITTED", "stage COMMITTED")
ok(b._valid_r4_migration(rec, st), "committed record validates against state")
ok(b._valid_current_lifecycle_binding(st["_lifecycle_binding"]),
   "lifecycle rebound to /11")
ok(st["_lifecycle_binding"]["direct_authority_sha256"]
   == b.DIRECT_RECIPE_AUTHORITY_SHA256, "new authority sha bound")
ok(rec["source_binding_sha256"]
   == "309f5e84e25e11a25fbf1b1f90b75edc2cbe7b0d9da4c1efef06aba16b93058b",
   "source binding sha preserved")
for key in ("_predecessor_takeover", "_v389_capital_transition",
            "_v389_takeover_ledger_bridge"):
    ok(key not in st, f"{key} archived")
    ok(key.lstrip("_").replace("_v389_takeover_ledger_bridge",
                               "ledger_bridge") or True, "")
arch = rec["archive"]
ok(set(arch) == {"predecessor_takeover", "capital_transition",
                 "ledger_bridge", "source_binding"}, "archive keys")
ok(arch["predecessor_takeover"]["status"] == "COMMITTED",
   "takeover archived verbatim")
ok("_clock_hold_dip" not in st, "clock-hold dip settled exactly once")
ok(rec["merged_clock_hold_dip"] == -0.0072647206258323917
   or abs(rec["merged_clock_hold_dip"] + 0.0072647206258323917) < 1e-15,
   "merged dip value recorded")
pend = st["_daycount"]["pending"]
ok(abs(pend["sess_dip"] + 0.0073539964907983167) < 1e-15,
   "pending dip kept the deeper observation (min merge)")
ok(pend["applied_L"] == 4.375, "pending 08-28 roll retains recorded 4.375")
guard = st["_external_cashflow_guard"]
ok(guard["lifecycle_sha256"] == rec["new_binding_sha256"],
   "cashflow guard rebound to the new lifecycle")
ok(b._valid_external_cashflow_guard(guard, st), "rebound guard validates")
ok(st["breaker"]["cold_start"] is True
   and "anchor_proof" not in st["breaker"],
   "anchor must re-prove under the new lifecycle (full-or-hold)")
ok(st["rearm_done"] is True, "rearm_done carried")
ok(st["start_balance"] == 200000.0
   and st["challenge_start_date"] == "2026-08-25", "campaign basis carried")
ok(b._r4_migration_pair_has_receipt(st), "both recovery images committed")
ok(b._validate_safety_records(st), "post-commit safety records validate")
ok(b._state_terminal_authority(copy.deepcopy(st)) >= 296,
   "committed migration outranks the archived takeover")
ok(not b._r4_migration_required(st), "migration permanently completed")
# still blocked until the pending roll settles + anchor proves (full-or-hold)
ok(b._new_risk_blocked(), "new risk still blocked until open txns settle")
ok(len(fake.sent) == 0, "zero broker sends in the full pass")

# idempotent re-advance
advance(b, st, "committed", "idempotent COMMIT")

# ---------- interruption at every stage + native resume ----------
for kill_after in (0, 1, 2):
    b2, fake2, st2, wd2 = r4harness.boot()
    for step in range(kill_after + 1):
        b2._advance_r4_migration(st2)
    stage_before = st2.get("_r4_migration", {}).get("stage")
    # simulate a hard kill: reload strictly from disk with a fresh module
    b3, fake3 = r4harness.load_bot(wd2)
    disk_state = json.load(open(os.path.join(wd2, "bot_state_v12.json")))
    r4harness.wire_r4_account(b3, fake3, {
        "_lifecycle_binding": disk_state["_lifecycle_binding"],
        "breaker": disk_state["breaker"],
        "_daycount": disk_state["_daycount"],
        "_predecessor_takeover":
            disk_state.get("_predecessor_takeover")
            or disk_state["_r4_migration"]["archive"]["predecessor_takeover"],
    })
    r4harness.wire_market_data(b3, fake3)
    st3 = b3.load_state()
    b3._RUNTIME_STATE[0] = st3
    ok(st3.get("_r4_migration", {}).get("stage") == stage_before,
       f"kill@{kill_after}: stage {stage_before} survives restart")
    ok(b3._r4_migration_required(st3),
       f"kill@{kill_after}: migration still required after restart")
    outcomes = []
    for _ in range(6):
        outcome = b3._advance_r4_migration(st3)
        outcomes.append(outcome)
        if outcome in ("committed", "refused"):
            break
    ok(outcomes[-1] == "committed",
       f"kill@{kill_after}: resumed to COMMITTED ({outcomes})")
    ok(len(fake3.sent) == 0, f"kill@{kill_after}: zero broker sends")

# ---------- refusals ----------
# foreign ticket blocks the inventory proof
b4, fake4, st4, _ = r4harness.boot()
b4._advance_r4_migration(st4)      # PREPARED
import fakemt5
fake4.positions.append(fakemt5._Obj(
    ticket=999, identifier=999, magic=12345, symbol="XAUUSD.sim",
    volume=0.5, type=fake4.POSITION_TYPE_BUY, time=0))
outcome = b4._advance_r4_migration(st4)
ok(outcome == "wait"
   and st4["_r4_migration"]["stage"] == "PREPARED",
   "foreign ticket holds the inventory proof")
b4._ACCOUNT_CONFLICT[0] = False

# grown ticket refuses mapping
b5, fake5, st5, _ = r4harness.boot()
b5._advance_r4_migration(st5)
fake5.positions[0].volume = fake5.positions[0].volume * 2
outcome = b5._advance_r4_migration(st5)
ok(outcome == "wait" and st5["_r4_migration"]["stage"] == "PREPARED",
   "grown ticket cannot map into the committed inventory")

# reduced ticket is acceptable (source reduction)
b6, fake6, st6, _ = r4harness.boot()
b6._advance_r4_migration(st6)
fake6.positions[0].volume = fake6.positions[0].volume / 3.0
outcome = b6._advance_r4_migration(st6)
ok(outcome == "wait" and st6["_r4_migration"]["stage"] == "INVENTORY_PROVED",
   "reduced ticket maps as a source reduction")

# a non-r4 state never migrates
b7, fake7, st7, _ = r4harness.boot()
st7["_lifecycle_binding"]["schema"] = "direct_lifecycle_binding/9"
ok(not b7._r4_migration_required(st7), "non-/10 binding is not migrated")

# tampered takeover refuses
b8, fake8, st8, _ = r4harness.boot()
st8["_predecessor_takeover"]["source_balance_cents"] += 1
ok(not b8._r4_migration_source_shape_ok(st8),
   "tampered takeover receipt refuses the migration")

# a ticket appearing AFTER the inventory proof refuses the final commit:
# the migration re-maps every live ticket immediately before committing
b8b, fake8b, st8b, _ = r4harness.boot()
b8b._advance_r4_migration(st8b)          # PREPARED
b8b._advance_r4_migration(st8b)          # INVENTORY_PROVED
b8b._advance_r4_migration(st8b)          # LEDGER_REBUILT
assert st8b["_r4_migration"]["stage"] == "LEDGER_REBUILT"
evil = fakemt5._Obj(
    ticket=777777, identifier=777777, magic=b8b.MAGIC["BTC"],
    symbol="BTCUSD.sim", volume=0.10, type=fake8b.POSITION_TYPE_BUY,
    price_open=64000.0, price_current=64000.0, sl=0.0, tp=0.0,
    profit=0.0, swap=0.0, time=0, comment="")
fake8b.positions.append(evil)
out8b = b8b._advance_r4_migration(st8b)
ok(out8b == "wait"
   and st8b["_r4_migration"]["stage"] == "LEDGER_REBUILT",
   f"a 5th apparently-bot-owned ticket after INVENTORY_PROVED refuses "
   f"the commit ({out8b})")
ok(len(fake8b.sent) == 0, "the pre-commit reproof refusal sends nothing")
fake8b.positions.remove(evil)
b8b._ACCOUNT_CONFLICT[0] = False
out8c = b8b._advance_r4_migration(st8b)
ok(out8c == "committed"
   and st8b["_r4_migration"]["stage"] == "COMMITTED",
   "the commit completes once the live book maps purely again")

# duplicate rows sharing one committed identifier (split-volume growth)
# refuse the proof: two half-volume rows may not impersonate one position
b8d, fake8d, st8d, _ = r4harness.boot()
for _ in range(3):
    b8d._advance_r4_migration(st8d)
assert st8d["_r4_migration"]["stage"] == "LEDGER_REBUILT"
base_p = fake8d.positions[0]
base_p.volume = base_p.volume / 2.0
twin = fakemt5._Obj(
    ticket=888888, identifier=base_p.identifier, magic=base_p.magic,
    symbol=base_p.symbol, volume=base_p.volume, type=base_p.type,
    time=base_p.time)
fake8d.positions.append(twin)
out8d = b8d._advance_r4_migration(st8d)
ok(out8d == "wait"
   and st8d["_r4_migration"]["stage"] == "LEDGER_REBUILT",
   f"duplicate-identifier split rows refuse the commit ({out8d})")
fake8d.positions.remove(twin)
b8d._ACCOUNT_CONFLICT[0] = False
out8e = b8d._advance_r4_migration(st8d)
ok(out8e == "committed",
   "the split-row refusal clears once the book is unambiguous again")

# a MID-TAKEOVER source is held fail-closed, never migrated.  (The real
# supplied state is COMMITTED/COMMITTED/PROVED with the ledger bridge
# present; this SYNTHESIZED variant flips only those markers to prove
# the refusal path for a predecessor stopped mid-takeover.)
b9, fake9, st9, _ = r4harness.boot()
tk9 = st9["_predecessor_takeover"]
tk9["stage"] = "ANCHOR_WAIT"
tk9["status"] = "ACTIVE"
tk9["anchor_status"] = "UNPROVED"
ok(not b9._r4_migration_source_shape_ok(st9),
   "mid-takeover source (ANCHOR_WAIT/ACTIVE/UNPROVED) never migrates")
sent9 = len(fake9.sent)
out9 = b9._advance_r4_migration(st9)
ok(out9 == "refused" and "_r4_migration" not in st9,
   f"mid-takeover advance refuses without writing any migration record "
   f"({out9})")
ok(len(fake9.sent) == sent9, "the refusal sends nothing")
b9._RUNTIME_STATE[0] = st9
ok(b9._new_risk_blocked(),
   "all new risk stays blocked on the mid-takeover folder")
ok("predecessor takeover anchor_wait" in b9._nnr_causes(),
   "the console names the EXACT blocker (predecessor takeover anchor_wait)")

# a bridge-absent source refuses identically (the bridge is a required
# receipt family; its absence means the old bot never finished)
b10, fake10, st10, _ = r4harness.boot()
del st10["_v389_takeover_ledger_bridge"]
ok(not b10._r4_migration_source_shape_ok(st10),
   "bridge-absent source never migrates")
out10 = b10._advance_r4_migration(st10)
ok(out10 == "refused" and "_r4_migration" not in st10,
   f"bridge-absent advance refuses without writing any record ({out10})")
ok(len(fake10.sent) == 0, "the bridge-absent refusal sends nothing")

print(f"test_r4_migration: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
