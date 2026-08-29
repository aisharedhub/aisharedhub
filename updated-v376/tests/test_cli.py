"""CLI grammar tests: strict order-independent parser (build order section 1/5).

Run: python test_cli.py  (offline; imports the bot as a module, no MT5).
"""
import importlib.util
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(HERE, "..", "build", "vol_target_bot_v12.py")

spec = importlib.util.spec_from_file_location("updbot_cli", BOT)
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


def match(argv):
    return b._direct_match_recipe(list(argv))


def accepts(argv, recipe, policy=None, capital=None, expected=None,
            label=None):
    p = match(argv)
    label = label or " ".join(argv)
    ok(p is not None, f"{label}: refused ({b._DIRECT_REFUSAL[0]})")
    if p is None:
        return None
    ok(p["recipe"] == recipe, f"{label}: recipe {p['recipe']!r} != {recipe!r}")
    ok(p["entry_policy"] == policy,
       f"{label}: policy {p['entry_policy']!r} != {policy!r}")
    ok(p["capital_cents"] == capital,
       f"{label}: capital {p['capital_cents']!r} != {capital!r}")
    ok(p["expected_cents"] == expected,
       f"{label}: expected {p['expected_cents']!r} != {expected!r}")
    return p


def refuses(argv, label=None):
    p = match(argv)
    label = label or " ".join(argv)
    ok(p is None, f"{label}: ACCEPTED but must refuse -> {p}")
    ok(b._DIRECT_REFUSAL[0] is not None or p is not None,
       f"{label}: refusal reason missing")


P1_GATED = ["--mode", "grind", "--phase", "1", "--start-min-dd", "0.02",
            "--start-bounce", "0.005", "--post-loss-mult", "0.75", "--live"]
P2_GATED = ["--mode", "grind", "--phase", "2", "--start-min-dd", "0.01",
            "--start-bounce", "0.005", "--start-cap", "10", "--rearm-gate",
            "--post-loss-mult", "0.75", "--capital", "200000", "--live"]
P1_IMM = ["--entry-policy", "immediate", "--mode", "grind", "--phase", "1",
          "--capital", "200000", "--live"]
P2_IMM = ["--entry-policy", "immediate", "--mode", "grind", "--phase", "2",
          "--capital", "200000", "--live"]
FUNDED = ["--funded", "--tv", "1.0", "--brk", "3.0", "--start-min-dd", "0.03",
          "--start-bounce", "0", "--post-loss-mult", "0.75",
          "--expected-start-balance", "200000", "--live"]

# --- the five exact commands from the build order (section 5) ---
accepts(P1_GATED, "p1", "gated-v1", label="exact V376 P1 command")
accepts(P1_GATED + ["--capital", "200000"], "p1", "gated-v1",
        capital=20_000_000, label="P1 gated with declared capital")
accepts(P1_IMM, "p1", "immediate-v1", capital=20_000_000,
        label="P1 immediate")
accepts(P2_GATED, "p2-fresh", "gated-v1", capital=20_000_000,
        label="P2 gated")
accepts(P2_IMM, "p2-standalone-immediate", "immediate-v1",
        capital=20_000_000, label="P2 immediate (live command)")
accepts(FUNDED, "funded", "funded-gate-v1", expected=20_000_000,
        label="funded")

# --- order independence: shuffle flag-pairs of each recipe ---
def pairs(argv):
    out = []
    i = 0
    while i < len(argv):
        if argv[i].startswith("--") and i + 1 < len(argv) \
                and not argv[i + 1].startswith("--"):
            out.append((argv[i], argv[i + 1]))
            i += 2
        else:
            out.append((argv[i],))
            i += 1
    return out


for name, argv, recipe, policy in [
        ("p1-gated", P1_GATED, "p1", "gated-v1"),
        ("p2-gated", P2_GATED, "p2-fresh", "gated-v1"),
        ("p2-imm", P2_IMM, "p2-standalone-immediate", "immediate-v1"),
        ("funded", FUNDED, "funded", "funded-gate-v1")]:
    base = pairs(argv)
    for k, perm in enumerate(itertools.permutations(base)):
        if k >= 40:  # bounded sample of orderings
            break
        flat = [tok for group in perm for tok in group]
        p = match(flat)
        ok(p is not None and p["recipe"] == recipe
           and p["entry_policy"] == policy,
           f"{name} permutation #{k} refused/misresolved: "
           f"{b._DIRECT_REFUSAL[0]} :: {' '.join(flat)}")

# explicit gated policy token allowed
accepts(["--entry-policy", "gated"] + P1_GATED, "p1", "gated-v1",
        label="P1 with explicit gated token")
# p2-adopt
accepts(P2_GATED + ["--expected-start-balance", "197167.35"], "p2-adopt",
        "gated-v1", capital=20_000_000, expected=19_716_735,
        label="P2 adopt")
# decimal-normalized equivalence
accepts(["--mode", "grind", "--phase", "1", "--start-min-dd", "0.020",
         "--start-bounce", "0.0050", "--post-loss-mult", "0.750", "--live"],
        "p1", "gated-v1", label="canonical-decimal equivalence")
# --yes and --mt5-path suffix anywhere
p = accepts(P2_IMM + ["--yes", "--mt5-path", r"C:\MT5\terminal64.exe"],
            "p2-standalone-immediate", "immediate-v1", capital=20_000_000,
            label="P2 immediate with --yes/--mt5-path")
if p:
    ok(p["assume_yes"] is True, "--yes not captured")
    ok(p["mt5_path"] == r"C:\MT5\terminal64.exe", "--mt5-path not captured")

# --- maintenance verbs ---
accepts(["--export-continuity"], "export", label="export")
accepts(["--recover-safety", "--live"], "recover", label="recover")
accepts(["--diagnose"], "diagnose", label="diagnose")
accepts(["--selfcheck"], "selfcheck", label="selfcheck")
accepts(["--list-symbols"], "list-symbols", label="list-symbols")
accepts(["--pause-new-risk"], "pause", label="pause")
accepts(["--resume-paused"], "resume", label="resume")
accepts(["--flatten-and-stop", "--live"], "flatten-stop", label="flatten")

# --- refusals ---
refuses(P1_GATED + ["--foo"], "unknown flag")
refuses(P1_GATED + ["stray"], "stray token")
refuses(P1_GATED + ["--phase", "1"], "duplicate flag")
refuses(["--mode", "grind", "--phase", "1", "--start-min-dd", "0.03",
         "--start-bounce", "0.005", "--post-loss-mult", "0.75", "--live"],
        "untested gate value")
refuses(P2_IMM + ["--post-loss-mult", "0.75"],
        "immediate + gate token contradiction")
refuses(P2_IMM + ["--start-min-dd", "0.01"], "immediate + dd token")
refuses(FUNDED + ["--capital", "200000"], "funded + capital contradiction")
refuses(["--entry-policy", "immediate"] + FUNDED, "funded + immediate")
refuses([tok if tok != "200000" else "0200000" for tok in P2_IMM],
        "leading-zero amount")
refuses([tok if tok != "200000" else "2e5" for tok in P2_IMM],
        "exponent amount")
refuses([tok if tok != "200000" else "nan" for tok in P2_IMM], "nan amount")
refuses([tok if tok != "200000" else "200000." for tok in P2_IMM],
        "trailing-dot amount")
refuses(["--entry-policy", "immediate", "--mode", "grind", "--phase", "2",
         "--live"], "P2 immediate without capital")
refuses(["--flatten-and-stop"], "flatten without --live")
refuses(["--diagnose", "--live"], "diagnose with --live")
refuses(["--diagnose", "--pause-new-risk"], "two maintenance verbs")
refuses(P1_GATED[:-1] + ["--capital"], "value flag missing value")
refuses([tok for tok in P2_GATED if tok != "--rearm-gate"],
        "P2 gated without --rearm-gate")
refuses(P1_GATED[:-1], "strategy recipe without --live")
refuses(P1_GATED + ["--start-cap", "10"], "P1 with start-cap")
refuses(P1_GATED + ["--expected-start-balance", "200000"],
        "P1 with expected balance")
refuses([tok if tok != "grind" else "balanced" for tok in P1_GATED],
        "untested mode")
refuses([tok if tok != "1" else "3" for tok in P1_GATED
         if True], "bad phase")
refuses(["--mt5-path", "--live"], "mt5-path flag-shaped value")
refuses([], "empty argv")
funded_missing = [tok for tok in FUNDED
                  if tok not in ("--expected-start-balance", "200000")]
refuses(funded_missing, "funded without expected balance")

print(f"test_cli: {PASS[0]} pass, {FAIL[0]} fail")
sys.exit(1 if FAIL[0] else 0)
