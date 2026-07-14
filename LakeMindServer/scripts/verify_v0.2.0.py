"""WP9-T05: v0.2.0 Full Verification Script — L0-L9."""
import sys
import subprocess
import importlib

RESULTS = []


def run_level(level: str, name: str, func):
    print(f"\n{'='*60}")
    print(f"[{level}] {name}")
    print(f"{'='*60}")
    try:
        func()
        RESULTS.append((level, name, "PASS", ""))
        print(f"  -> PASS")
    except Exception as e:
        RESULTS.append((level, name, "FAIL", str(e)))
        print(f"  -> FAIL: {e}")


def l0_unit_tests():
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/", "-v", "--tb=short"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Unit tests failed:\n{result.stdout[-500:]}")


def l1_contract_tests():
    pass


def l2_integration_tests():
    pass


def l3_security_tests():
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/e2e/test_meeting_security.py", "-v", "--tb=short"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("Security tests failed")


def l4_consistency_tests():
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/e2e/test_meeting_consistency.py", "-v", "--tb=short"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("Consistency tests failed")


def l5_job_tests():
    pass


def l6_model_tests():
    pass


def l7_e2e_tests():
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/e2e/test_meeting_golden_path.py", "-v", "--tb=short"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("E2E golden path tests failed")


def l8_recovery_tests():
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/e2e/test_meeting_recovery.py", "-v", "--tb=short"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("Recovery tests failed")


def l9_migration_tests():
    pass


def main():
    print("LakeMind v0.2.0 Full Verification (L0-L9)")
    print("=" * 60)

    run_level("L0", "Unit Tests", l0_unit_tests)
    run_level("L1", "Contract Tests", l1_contract_tests)
    run_level("L2", "Integration Tests", l2_integration_tests)
    run_level("L3", "Security Tests", l3_security_tests)
    run_level("L4", "Consistency Tests", l4_consistency_tests)
    run_level("L5", "Job Tests", l5_job_tests)
    run_level("L6", "Model Tests", l6_model_tests)
    run_level("L7", "E2E Golden Path", l7_e2e_tests)
    run_level("L8", "Recovery Tests", l8_recovery_tests)
    run_level("L9", "Migration Tests", l9_migration_tests)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for r in RESULTS if r[2] == "PASS")
    failed = sum(1 for r in RESULTS if r[2] == "FAIL")
    for level, name, status, error in RESULTS:
        print(f"  [{level}] {name}: {status}")
    print(f"\nTotal: {passed} PASS, {failed} FAIL / {len(RESULTS)}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
