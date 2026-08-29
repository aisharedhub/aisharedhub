"""Deterministic release packaging (build order sections 20 and 21).

Assembles UpdatedV376.zip:
    DEFAULT/                 the live working folder, essentials only
        vol_target_bot_v12.py
        shadow_seed.json
        shadow_seed_manifest.json
        README.md            exact commands + one-time r4 handoff
    CHANGES.md               change report
    TEST-RESULTS.md          test summary
    MANIFEST.sha256          SHA-256 of every member
    maintainer/tests/        the full offline campaign (kept out of the
                             live folder)

The archive is deterministic: fixed timestamps, sorted member order,
fixed permissions and compression. The script builds it twice and
requires the two builds to be byte-identical before publishing.

Run: python build_release.py [output-dir]
"""
import hashlib
import io
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STAMP = (2026, 1, 1, 0, 0, 0)

MEMBERS = [
    ("DEFAULT/vol_target_bot_v12.py",
     os.path.join(ROOT, "build", "vol_target_bot_v12.py")),
    ("DEFAULT/shadow_seed.json",
     os.path.join(ROOT, "build", "shadow_seed.json")),
    ("DEFAULT/shadow_seed_manifest.json",
     os.path.join(ROOT, "build", "shadow_seed_manifest.json")),
    ("DEFAULT/README.md", os.path.join(HERE, "README.md")),
    ("CHANGES.md", os.path.join(HERE, "CHANGES.md")),
    ("TEST-RESULTS.md", os.path.join(HERE, "TEST-RESULTS.md")),
]

TEST_FILES = [
    "fakemt5.py", "orderharness.py", "r4harness.py", "startharness.py",
    "test_cli.py", "test_binding_schema.py", "test_controller_ledger.py",
    "test_applied_exposure.py", "test_r4_migration.py",
    "test_operator_commands.py", "test_console_status.py",
    "test_gate_history.py", "test_formula_equivalence.py",
    "test_order_routes.py", "test_protections.py",
    "test_fresh_lifecycle.py", "test_orb_matrix.py",
    "test_target_completion.py", "test_interrupt.py",
    "test_continuity_chain.py", "run_mutations.py",
]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def collect():
    members = []
    for arcname, path in MEMBERS:
        members.append((arcname, open(path, "rb").read()))
    for name in TEST_FILES:
        path = os.path.join(ROOT, "tests", name)
        members.append((f"maintainer/tests/{name}",
                        open(path, "rb").read()))
    members.sort(key=lambda item: item[0])
    manifest_lines = [f"{sha256(data)}  {arcname}"
                      for arcname, data in members]
    manifest = ("\n".join(manifest_lines) + "\n").encode("utf-8")
    members.append(("MANIFEST.sha256", manifest))
    members.sort(key=lambda item: item[0])
    return members


def build_bytes():
    members = collect()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for arcname, data in members:
            info = zipfile.ZipInfo(arcname, date_time=STAMP)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with archive.open(info, "w") as stream:
                stream.write(data)
    return buffer.getvalue()


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else HERE
    first = build_bytes()
    second = build_bytes()
    if first != second:
        print("FATAL: rebuild is not byte-identical")
        return 1
    out = os.path.join(out_dir, "UpdatedV376.zip")
    with open(out, "wb") as stream:
        stream.write(first)
    print(f"UpdatedV376.zip  {len(first)} bytes  sha256 {sha256(first)}")
    with zipfile.ZipFile(io.BytesIO(first)) as archive:
        bad = archive.testzip()
        names = archive.namelist()
    print(f"members: {len(names)}  integrity: "
          f"{'OK' if bad is None else f'CORRUPT {bad}'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
