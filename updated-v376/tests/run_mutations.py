"""Mutation battery against critical protections (build order section 20).

Each entry mutates ONE exact source anchor in the build and expects the
named suite to KILL the mutant (non-zero exit).  The pristine file is
restored and hash-verified after every mutant.

Run: python run_mutations.py
"""
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(HERE, "..", "build", "vol_target_bot_v12.py")

MUTANTS = [
    # -- full-history gate physics --
    ("gate crossing becomes exclusive",
     "if g_dd <= -START_MIN_DD:",
     "if g_dd < -START_MIN_DD:",
     "test_gate_history.py"),
    ("bounce threshold becomes exclusive",
     'if eq / max(low, 1e-9) - 1.0 >= START_BOUNCE:',
     'if eq / max(low, 1e-9) - 1.0 > START_BOUNCE:',
     "test_gate_history.py"),
    ("gate low folds BEFORE the bounce test",
     """                low = float(sh.get("gate_low", eq))
                if eq / max(low, 1e-9) - 1.0 >= START_BOUNCE:""",
     """                low = min(float(sh.get("gate_low", eq)), eq)
                sh["gate_low"] = low
                if eq / max(low, 1e-9) - 1.0 >= START_BOUNCE:""",
     "test_gate_history.py"),
    # -- controller formulas --
    ("post-loss multiplier neutralized",
     "* age_boost(age_days) * target_lock(lock_ratio) * pl",
     "* age_boost(age_days) * target_lock(lock_ratio) * 1.0",
     "test_formula_equivalence.py"),
    ("hard MAX_LEVERAGE cap removed",
     "return float(min(max(L, 0.0), MAX_LEVERAGE))",
     "return float(max(L, 0.0))",
     "test_formula_equivalence.py"),
    ("dip guard disabled",
     "if max_dip20 > 0: L = min(L, THETA*(BREAKER_PCT/100.0)/max_dip20)",
     "if False: L = min(L, THETA*(BREAKER_PCT/100.0)/max_dip20)",
     "test_formula_equivalence.py"),
    # -- dated controller ledger (defect-1 repair) --
    ("ledger accepts unbounded session gaps",
     "return bool(0 < gap_days <= 10 and gap_proven)",
     "return bool(0 < gap_days <= 10000)",
     "test_controller_ledger.py"),
    ("omitted account returns fabricated as zero",
     'if account_ret is not None and "account-return-omitted" in flags:',
     'if False and "account-return-omitted" in flags:',
     "test_controller_ledger.py"),
    # -- broker-proved applied exposure (defect-2 repair) --
    ("applied-exposure reconcile tolerance destroyed",
     'tolerance = max(0.02, 0.15 * max(abs(desired), abs(frac)))',
     'tolerance = max(99.0, 0.15 * max(abs(desired), abs(frac)))',
     "test_applied_exposure.py"),
    # -- operator pause --
    ("pause record schema check dropped",
     'and value.get("schema") == _PAUSE_NEW_RISK_SCHEMA',
     'and True',
     "test_operator_commands.py"),
    ("operator pause no longer blocks new risk",
     'operator_paused = isinstance(st, dict) and "_pause_new_risk" in st',
     'operator_paused = False',
     "test_operator_commands.py"),
    # -- exactly-once order engine --
    ("intent token no longer stamped on the request",
     'req["comment"] = intent["token"]',
     'req["comment"] = ""',
     "test_order_routes.py"),
    ("rejection id guard neutralized",
     "def _negative_receipt_ids_are_zero(result):",
     "def _negative_receipt_ids_are_zero(result):\n    return True",
     "test_order_routes.py"),
    ("terminal implied fill always full",
     "    implied_fill = initial - remaining\n"
     "    if not _terminal_fill_matrix_ok(",
     "    implied_fill = initial\n"
     "    if not _terminal_fill_matrix_ok(",
     "test_order_routes.py"),
    # -- account singleton --
    ("account singleton always acquires",
     "    key = _account_singleton_key(ai)",
     "    return True\n    key = _account_singleton_key(ai)",
     "test_protections.py"),
]


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def main():
    pristine = open(BOT, "rb").read()
    pristine_sha = hashlib.sha256(pristine).hexdigest()
    print(f"pristine build sha256 {pristine_sha[:16]}… "
          f"({len(MUTANTS)} mutants)")
    killed = 0
    survived = []
    try:
        for label, old, new, suite in MUTANTS:
            src = pristine.decode("utf-8")
            count = src.count(old)
            if count != 1:
                survived.append((label, f"anchor x{count}"))
                print(f"ANCHOR-ERROR ({count}x): {label}")
                continue
            open(BOT, "w", encoding="utf-8").write(src.replace(old, new, 1))
            proc = subprocess.run(
                [sys.executable, "-u", os.path.join(HERE, suite)],
                capture_output=True, text=True, timeout=1500, cwd=HERE)
            if proc.returncode != 0:
                killed += 1
                print(f"KILLED by {suite}: {label}")
            else:
                survived.append((label, "suite passed"))
                print(f"SURVIVED ({suite} still green): {label}")
            open(BOT, "wb").write(pristine)
            assert sha(BOT) == pristine_sha, "pristine restore failed"
    finally:
        open(BOT, "wb").write(pristine)
        assert sha(BOT) == pristine_sha, "pristine restore failed"
    print(f"run_mutations: {killed}/{len(MUTANTS)} killed, "
          f"{len(survived)} survived")
    for label, why in survived:
        print(f"  SURVIVOR: {label} ({why})")
    sys.exit(1 if survived else 0)


if __name__ == "__main__":
    main()
