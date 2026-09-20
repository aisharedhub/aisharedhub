"""Section-19 console: the periodic status names every required fact.

Replays the exact r4 evidence through the committed migration and checks
the two-line [STATUS] block plus the exact-blocker list.  Zero sends.

Run: python test_console_status.py   (skips if evidence absent)
"""
import contextlib
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r4harness

if not os.path.isfile(os.path.join(r4harness.EVDIR, "bot_state_v12.json")):
    print("test_console_status: evidence absent — SKIPPED")
    sys.exit(0)

PASS = [0]
FAIL = [0]


def ok(cond, label):
    if cond:
        PASS[0] += 1
    else:
        FAIL[0] += 1
        print(f"FAIL: {label}")


b, fake, st, wd = r4harness.boot()
for _ in range(4):
    with contextlib.redirect_stdout(io.StringIO()):
        b._advance_r4_migration(st)
assert st["_r4_migration"]["stage"] == "COMMITTED"

text = b._render_status_line(st, fake.account, st.get("start_balance"),
                             st.get("_last_L"), 77, 4)
lines = text.splitlines()
ok(len(lines) == 2 and all(l.startswith("[STATUS] ") for l in lines),
   "status renders as a two-line [STATUS] block")

# exact economics from the committed r4 state (anchor 197,167.35 balance,
# equity 197,566.98, campaign base $200k P2)
ok("eq 197,566.98" in text and "bal 197,167.35" in text,
   "balance and equity shown")
ok("to halt 10,399.63" in text, "daily halt distance exact ($10k line)")
ok("to breaker 7,399.63" in text, "breaker distance exact ($7k / 3.5% line)")
ok("to floor 17,566.98" in text, "static floor distance exact ($180k line)")
ok("target 210,000.00" in text and "amount remaining 12,832.65" in text,
   "target and amount remaining shown")
ok("virtual base 200,000.00 (declared)" in text, "declared capital shown")
ok("pos 4" in text, "position count shown")
ok("applied 4.38x" in text,
   "broker-applied leverage shown (retained legacy 4.375)")
ok("req UNKNOWN" in text,
   "requested leverage honestly UNKNOWN before the first controller pass")
ok("gross UNPROVED" in text,
   "gross leverage never displayed without a current-session proof")
ok("blocker " in lines[1] and "blocker none" not in lines[1],
   "exact blocker named while the anchor is unproved")
ok("Prague daily anchor unproved" in lines[1],
   "strongest blocker is the full-or-hold anchor proof")

causes = b._nnr_causes()
ok("unresolved account day-roll finality" in causes,
   "cause list includes the open day-roll")
ok(all(isinstance(c, str) and c for c in causes), "causes are plain text")

# requested/proven leverage present once the controller records it
st["_requested_L"] = 5.719659
st["_last_L"] = 4.375
text2 = b._render_status_line(st, fake.account, None, None, 78, 4)
ok("req 5.72x" in text2 and "applied 4.38x" in text2,
   "requested vs broker-applied leverage shown side by side")

# gate line: the r4 shadow is armed
ok(("gate armed" in text2) or ("gate immediate" in text2),
   f"gate status shown ({text2.splitlines()[1]})")

# fresh tick witness renders a finite feed age
b._UTC_EPOCH_WITNESS[0]["max_delta_s"] = 2.0
text3 = b._render_status_line(st, fake.account, None, None, 79, 4)
ok("tick age 2s" in text3, "feed age shown from the tick witness")

ok(len(fake.sent) == 0, "zero broker sends")
print(f"test_console_status: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
