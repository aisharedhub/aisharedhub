"""Lifecycle binding schema /11 + /10 predecessor recognition.

Requires the live r4 state evidence: set UPDATED_V376_EVIDENCE_DIR to a
directory containing bot_state_v12.json (and .bak).  Skips cleanly when
absent (the evidence is deliberately not committed to the repository).

Run: python test_binding_schema.py
"""
import copy
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(HERE, "..", "build", "vol_target_bot_v12.py")
EVDIR = os.environ.get(
    "UPDATED_V376_EVIDENCE_DIR",
    "/tmp/claude-0/-home-user-aisharedhub/"
    "98eb14e8-29fe-5768-a7d5-491331594ddb/scratchpad/evidence")
STATE = os.path.join(EVDIR, "bot_state_v12.json")

sys.argv = ["vol_target_bot_v12.py"]
spec = importlib.util.spec_from_file_location("updbot_schema", BOT)
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


ok(b._LIFECYCLE_BINDING_SCHEMA == "direct_lifecycle_binding/11",
   "current schema is /11")
ok(b._V389_LIFECYCLE_BINDING_SCHEMA == "direct_lifecycle_binding/10",
   "r4 predecessor schema is /10")
ok(b._V389_R4_DIRECT_AUTHORITY_SHA256
   == "44b17a2faf6f6ff461a3b4c59faf37f2f0136d06cb2e90c815c93bcd32db2b0c",
   "r4 authority sha pinned")
ok(b.DIRECT_RECIPE_AUTHORITY_SHA256 != b._V389_R4_DIRECT_AUTHORITY_SHA256,
   "new authority sha differs from r4")

if not os.path.isfile(STATE):
    print("test_binding_schema: evidence absent — structural checks only")
    print(f"test_binding_schema: {PASS[0]} pass, {FAIL[0]} fail")
    sys.exit(1 if FAIL[0] else 0)

st = json.load(open(STATE))
binding = st["_lifecycle_binding"]

ok(b._valid_v389_lifecycle_binding(binding), "r4 binding valid as /10")
ok(not b._valid_current_lifecycle_binding(binding),
   "r4 binding NOT valid as current /11")
ok(b._valid_lifecycle_binding(binding),
   "r4 binding valid under active (record) semantics")

new = dict(binding)
new["schema"] = b._LIFECYCLE_BINDING_SCHEMA
new["direct_authority_sha256"] = b.DIRECT_RECIPE_AUTHORITY_SHA256
ok(b._valid_current_lifecycle_binding(new), "rebound /11 binding valid")

# every r4 record family validates against the /10 binding
ok(b._valid_predecessor_takeover_txn(st["_predecessor_takeover"], st),
   "predecessor takeover txn")
ok(b._valid_external_cashflow_guard(st["_external_cashflow_guard"], st),
   "external cashflow guard")
ok(b._valid_v389_takeover_ledger_bridge(st["_v389_takeover_ledger_bridge"],
                                        st), "ledger bridge")
ok(b._valid_clock_hold_dip(st["_clock_hold_dip"], st), "clock-hold dip")
ok(b._valid_prague_anchor_proof(st["breaker"]["anchor_proof"], st),
   "anchor proof")
ok(b._valid_v389_capital_transition(st["_v389_capital_transition"],
                                    st["_predecessor_takeover"], st),
   "capital transition (reconstruction branch)")
ok(b._valid_day_roll_txn(st["_daycount"]["pending"], st.get("_daycount")),
   "pending day-roll txn")

# authorization must refuse the /10 state
ok(b._immediate_entry_authorized(st) is False,
   "immediate entry refused on /10 state")
ok(b._anchor_increase_authorized(st) is False,
   "anchor increase refused on /10 state")

# the /10 binding hash matches every receipt chain
sha = b._lifecycle_binding_sha256(binding)
ok(sha == "309f5e84e25e11a25fbf1b1f90b75edc2cbe7b0d9da4c1efef06aba16b93058b",
   "binding sha 309f5e84…")
ok(st["_external_cashflow_guard"]["lifecycle_sha256"] == sha,
   "guard chained to binding sha")

# the full evidence image self-validates under the new build
body = copy.deepcopy(st)
body.pop("_state_image")
ok(b._state_body_digest(body) == st["_state_image"]["sha256"],
   "state image digest")
ok(b._validate_safety_records(copy.deepcopy(st)), "safety records validate")
ok(b._state_recovery_semantically_valid(copy.deepcopy(st)),
   "state recovery-semantically valid")
ok(b._state_terminal_authority(copy.deepcopy(st)) == 290,
   "terminal authority rank 290 (COMMITTED takeover)")

print(f"test_binding_schema: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
