"""Operator maintenance commands (build order section 5).

--diagnose (read-only), --pause-new-risk / --resume-paused (durable
sidecar requests + poll-head consumption), --flatten-and-stop --live
(managed close-everything with durable pause, never Ctrl+C).

Part A runs standalone with the inert fake MT5.  Part B replays the exact
supplied r4 evidence state via r4harness (skipped when evidence absent).

Run: python test_operator_commands.py
"""
import contextlib
import copy
import importlib.util
import io
import json
import os
import shutil
import signal
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fakemt5

BOT = os.path.join(HERE, "..", "build", "vol_target_bot_v12.py")
SCRATCH = tempfile.mkdtemp(prefix="opcmd-")

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
    # the guarded __main__ parse never runs under importlib: replay it
    b._DIRECT_PROFILE = b._direct_match_recipe(argv)
    assert b._DIRECT_PROFILE is not None, argv
    b.RELEASE_RECIPE_ID = b._DIRECT_PROFILE["recipe"]
    b.ENTRY_POLICY_ID = b._DIRECT_PROFILE.get("entry_policy")
    b.DIAGNOSE = b.RELEASE_RECIPE_ID == "diagnose"
    b.PAUSE_NEW_RISK_CMD = b.RELEASE_RECIPE_ID == "pause"
    b.RESUME_PAUSED_CMD = b.RELEASE_RECIPE_ID == "resume"
    b.FLATTEN_AND_STOP = b.RELEASE_RECIPE_ID == "flatten-stop"
    return b


@contextlib.contextmanager
def deadline(seconds, label):
    """A misrouted maintenance verb must fail loudly, never hang."""
    def boom(signum, frame):
        raise AssertionError(f"deadline: {label} did not return")
    prev = signal.signal(signal.SIGALRM, boom)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev)


# =================== Part A: standalone (no evidence) ===================

# ---- parser: maintenance verbs are exact and order-independent ----
b0 = load(["--diagnose"], "updbot_op_diag")
ok(b0.DIAGNOSE and b0._DIRECT_PROFILE["recipe"] == "diagnose",
   "--diagnose resolves the diagnose recipe")
ok(b0._direct_match_recipe(["--flatten-and-stop"]) is None,
   "--flatten-and-stop without --live refused")
prof = b0._direct_match_recipe(["--live", "--flatten-and-stop"])
ok(prof is not None and prof["recipe"] == "flatten-stop",
   "--flatten-and-stop --live order-independent")
ok(b0._direct_match_recipe(["--diagnose", "--live"]) is None,
   "--diagnose rejects extra flags")
ok(b0._direct_match_recipe(["--pause-new-risk", "--phase", "2"]) is None,
   "--pause-new-risk rejects strategy flags")

# ---- --diagnose routes terminal-free from _main_impl ----
fake0 = fakemt5.install(b0)
empty = os.path.join(SCRATCH, "virgin")
os.makedirs(empty, exist_ok=True)
b0.STATE_FILE = os.path.join(empty, "bot_state_v12.json")
out = io.StringIO()
with deadline(120, "--diagnose"), contextlib.redirect_stdout(out):
    b0._main_impl()
text = out.getvalue()
ok("no readable state image" in text, "virgin folder diagnosed read-only")
ok(not fake0.initialized and len(fake0.sent) == 0,
   "--diagnose never touches the terminal")
ok(os.listdir(empty) == [], "--diagnose writes no file")

# ---- pause/resume verbs write durable sidecar requests, nothing else ----
for argv, name, attr, req_name in (
        (["--pause-new-risk"], "updbot_op_pause",
         "PAUSE_REQUEST_FILE", "pause_new_risk.request"),
        (["--resume-paused"], "updbot_op_resume",
         "RESUME_REQUEST_FILE", "resume_new_risk.request")):
    bx = load(argv, name)
    fx = fakemt5.install(bx)
    reqdir = os.path.join(SCRATCH, name)
    os.makedirs(reqdir, exist_ok=True)
    bx.PAUSE_REQUEST_FILE = os.path.join(reqdir, "pause_new_risk.request")
    bx.RESUME_REQUEST_FILE = os.path.join(reqdir, "resume_new_risk.request")
    with deadline(120, argv[0]), contextlib.redirect_stdout(io.StringIO()):
        bx._main_impl()
    path = getattr(bx, attr)
    ok(os.path.isfile(path), f"{argv[0]} writes {req_name}")
    req = json.load(open(path))
    ok(req.get("schema") == "operator_request/1"
       and isinstance(req.get("requested_at"), float),
       f"{argv[0]} request is a valid operator_request/1")
    ok(os.listdir(reqdir) == [req_name],
       f"{argv[0]} writes nothing besides the request")
    ok(not fx.initialized and len(fx.sent) == 0,
       f"{argv[0]} never touches the terminal")
    with deadline(120, argv[0]), contextlib.redirect_stdout(io.StringIO()):
        bx._main_impl()          # idempotent re-request overwrites atomically
    ok(os.path.isfile(path), f"{argv[0]} re-request is idempotent")

# ---- pause record validator ----
rec = {"schema": b0._PAUSE_NEW_RISK_SCHEMA, "since": 1.0}
ok(b0._valid_pause_new_risk(rec), "valid pause record accepted")
for label, bad in (
        ("wrong schema", {**rec, "schema": "pause_new_risk/999"}),
        ("extra key", {**rec, "note": "x"}),
        ("missing since", {"schema": b0._PAUSE_NEW_RISK_SCHEMA}),
        ("nonpositive since", {**rec, "since": 0.0}),
        ("nonfinite since", {**rec, "since": float("nan")}),
        ("non-dict", None)):
    ok(not b0._valid_pause_new_risk(bad), f"pause record refused: {label}")


# =================== Part B: exact r4 evidence state ===================
import r4harness

if not os.path.isfile(os.path.join(r4harness.EVDIR, "bot_state_v12.json")):
    print(f"test_operator_commands: {PASS[0]} pass, {FAIL[0]} fail "
          "(evidence part SKIPPED)")
    sys.exit(1 if FAIL[0] else 0)


def rebind_requests(b, workdir):
    b.PAUSE_REQUEST_FILE = os.path.join(workdir, "pause_new_risk.request")
    b.RESUME_REQUEST_FILE = os.path.join(workdir, "resume_new_risk.request")


def disk_body(workdir):
    return json.load(open(os.path.join(workdir, "bot_state_v12.json")))


# ---- pause request consumed at the poll head, durable, double-saved ----
b1, fake1, st1, wd1 = r4harness.boot()
rebind_requests(b1, wd1)
gen_before = disk_body(wd1)["_state_image"]["generation"]
ok(b1._write_operator_request(b1.PAUSE_REQUEST_FILE), "pause request placed")
b1._consume_operator_pause_requests(st1)
ok(b1._valid_pause_new_risk(st1.get("_pause_new_risk")),
   "pause durably recorded in state")
ok(not os.path.isfile(b1.PAUSE_REQUEST_FILE), "pause request consumed")
body = disk_body(wd1)
ok(b1._valid_pause_new_risk(body.get("_pause_new_risk")),
   "pause record persisted to the primary image")
ok(body["_state_image"]["generation"] >= gen_before + 2,
   "pause committed with a double save")
bak = json.load(open(os.path.join(wd1, "bot_state_v12.json.bak")))
ok(b1._valid_pause_new_risk(bak.get("_pause_new_risk")),
   "pause record persisted to the backup image")
ok(b1._new_risk_blocked(), "new risk blocked while paused")

# the loud once-per-poll cause line names the operator pause
b1._NNR_POLL[0] = False
out = io.StringIO()
with contextlib.redirect_stdout(out):
    b1._nnr_block("test")
ok("operator pause (--resume-paused to clear)" in out.getvalue(),
   "operator pause named in the no-new-risk cause line")

# pause request while already paused: request simply consumed
b1._write_operator_request(b1.PAUSE_REQUEST_FILE)
gen_mid = disk_body(wd1)["_state_image"]["generation"]
b1._consume_operator_pause_requests(st1)
ok(not os.path.isfile(b1.PAUSE_REQUEST_FILE)
   and disk_body(wd1)["_state_image"]["generation"] == gen_mid,
   "re-pause while paused consumes the request without a rewrite")

# ---- resume applies only after proof ----
# On the unmigrated r4 folder the pending one-time migration is a
# STRONGER halt: resume must refuse to clear the pause outright.
b1._write_operator_request(b1.RESUME_REQUEST_FILE)
with contextlib.redirect_stdout(io.StringIO()):
    b1._consume_operator_pause_requests(st1)
ok("_pause_new_risk" in st1,
   "resume held while the one-time r4 migration is pending")
os.path.isfile(b1.RESUME_REQUEST_FILE) and os.remove(
    b1.RESUME_REQUEST_FILE)
# Complete the migration; the remaining resume proofs run on the
# committed lifecycle.
with contextlib.redirect_stdout(io.StringIO()):
    for _ in range(4):
        b1._advance_r4_migration(st1)
ok((st1.get("_r4_migration") or {}).get("stage") == "COMMITTED",
   "migration committed for the resume-proof scenarios")
saved_rec = copy.deepcopy(st1["_pause_new_risk"])
st1["_pause_new_risk"] = {"schema": "bogus/1", "since": 1.0}
b1._write_operator_request(b1.RESUME_REQUEST_FILE)
with contextlib.redirect_stdout(io.StringIO()):
    b1._consume_operator_pause_requests(st1)
ok("_pause_new_risk" in st1, "resume held on a malformed pause record")
ok(os.path.isfile(b1.RESUME_REQUEST_FILE),
   "held resume request stays pending")

st1["_pause_new_risk"] = saved_rec
st1["_applied_exposure"] = {"schema": "broken"}
with contextlib.redirect_stdout(io.StringIO()):
    b1._consume_operator_pause_requests(st1)
ok("_pause_new_risk" in st1,
   "resume held while a safety record is invalid")
del st1["_applied_exposure"]
with contextlib.redirect_stdout(io.StringIO()):
    b1._consume_operator_pause_requests(st1)
ok("_pause_new_risk" not in st1, "resume clears the pause after proof")
ok(not os.path.isfile(b1.RESUME_REQUEST_FILE), "resume request consumed")
ok("_pause_new_risk" not in disk_body(wd1),
   "resume persisted to the primary image")

# resume request with no pause: request consumed, state untouched
gen_end = disk_body(wd1)["_state_image"]["generation"]
b1._write_operator_request(b1.RESUME_REQUEST_FILE)
b1._consume_operator_pause_requests(st1)
ok(not os.path.isfile(b1.RESUME_REQUEST_FILE)
   and disk_body(wd1)["_state_image"]["generation"] == gen_end,
   "resume with no pause consumes the request without a rewrite")
ok(len(fake1.sent) == 0, "pause/resume machinery sends nothing")

# ---- pause survives a hard restart (durable, not process-local) ----
b1b, fake1b, st1b, wd1b = r4harness.boot()
rebind_requests(b1b, wd1b)
b1b._write_operator_request(b1b.PAUSE_REQUEST_FILE)
b1b._consume_operator_pause_requests(st1b)
b1c, fake1c = r4harness.load_bot(wd1b)
st1c = b1c.load_state()
ok(b1c._valid_pause_new_risk(st1c.get("_pause_new_risk")),
   "durable pause survives a hard restart")
ok(len(fake1b.sent) == 0 and len(fake1c.sent) == 0,
   "restart under pause sends nothing")

# ---- flatten-and-stop: refusal without identity-bound authority ----
b2, fake2, st2, wd2 = r4harness.boot()
with contextlib.redirect_stdout(io.StringIO()):
    refused = b2._run_flatten_and_stop({"not": "a lifecycle"})
ok(refused is False, "flatten-and-stop refuses an unbound state")
ok(len(fake2.sent) == 0, "refusal sends nothing")

# ---- flatten-and-stop on the live r4 inventory: managed closes ----
b2._TEST_FLATTEN_STOP_MAX_POLLS = 2
with contextlib.redirect_stdout(io.StringIO()):
    res = b2._run_flatten_and_stop(st2)
ok(res is False,
   "flatten cannot claim completion while positions persist (bounded)")
ok(b2._valid_pause_new_risk(st2.get("_pause_new_risk")),
   "durable pause committed before any broker request")
ok(b2._valid_pause_new_risk(disk_body(wd2).get("_pause_new_risk")),
   "flatten pause persisted to disk")
ok(len(fake2.sent) > 0, "close requests actually issued")
only_reductions = all(
    (req.get("action") == fake2.TRADE_ACTION_DEAL and "position" in req)
    or req.get("action") == fake2.TRADE_ACTION_REMOVE
    for req in fake2.sent)
ok(only_reductions,
   "every flatten request is an exact-ticket close or cancel, never entry")
close_tickets = {req.get("position") for req in fake2.sent
                 if req.get("action") == fake2.TRADE_ACTION_DEAL}
live_tickets = {p.ticket for p in fake2.positions}
ok(close_tickets and close_tickets <= live_tickets,
   f"unanswered closes stay one-in-flight, exact-ticket "
   f"({sorted(close_tickets)})")

# ---- flatten-and-stop completes when the broker executes the closes ----
b2b, fake2b, st2b, wd2b = r4harness.boot()
all_tickets = {p.ticket for p in fake2b.positions}


def exec_close(req):
    if (req.get("action") == fake2b.TRADE_ACTION_DEAL
            and "position" in req):
        fake2b.positions = [p for p in fake2b.positions
                            if p.ticket != req["position"]]
        return fakemt5._Obj(
            retcode=fake2b.TRADE_RETCODE_DONE, order=req["position"] + 1,
            deal=req["position"] + 2, volume=req.get("volume", 0.0),
            price=fake2b.ticks[req["symbol"]].bid, comment="closed",
            request_id=1)
    return None


fake2b.send_result = exec_close
b2b._TEST_FLATTEN_STOP_MAX_POLLS = 12
with contextlib.redirect_stdout(io.StringIO()):
    res2b = b2b._run_flatten_and_stop(st2b)
ok(res2b is True,
   "managed flatten completes once the broker proves every close")
ok(fake2b.positions == [], "all four r4 positions closed")
closed = {req.get("position") for req in fake2b.sent
          if req.get("action") == fake2b.TRADE_ACTION_DEAL}
ok(closed == all_tickets,
   f"every r4 ticket closed exact-ticket ({sorted(closed)})")
ok(b2b._valid_pause_new_risk(disk_body(wd2b).get("_pause_new_risk")),
   "completion pause persisted after live-inventory flatten")

# ---- flatten-and-stop completes on a flat, orderless account ----
b3, fake3, st3, wd3 = r4harness.boot()
fake3.positions = []
fake3.orders = []
b3._TEST_FLATTEN_STOP_MAX_POLLS = 4
with contextlib.redirect_stdout(io.StringIO()):
    res3 = b3._run_flatten_and_stop(st3)
ok(res3 is True, "flat orderless account completes flatten-and-stop")
ok(b3._valid_pause_new_risk(st3.get("_pause_new_risk")),
   "durable pause holds after completion (resumable folder)")
ok(b3._valid_pause_new_risk(disk_body(wd3).get("_pause_new_risk")),
   "completion pause persisted")
ok(len(fake3.sent) == 0, "no sends needed on an already-flat account")

# the flattened r4 folder still carries its pending one-time migration:
# --resume-paused is HELD by that stronger halt (never overridden)
rebind_requests(b3, wd3)
b3._write_operator_request(b3.RESUME_REQUEST_FILE)
with contextlib.redirect_stdout(io.StringIO()):
    b3._consume_operator_pause_requests(st3)
ok("_pause_new_risk" in st3,
   "flattened r4 folder holds the pause while the migration is pending")

print(f"test_operator_commands: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
