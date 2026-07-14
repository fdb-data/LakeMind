import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from verify_full import test_l0, test_l1, test_l2, results

test_l0()
test_l1()
test_l2()

passed = sum(1 for r in results if r['passed'] is True)
failed = sum(1 for r in results if r['passed'] is False)
skipped = sum(1 for r in results if r['passed'] is None)
print(f"\nL0-L2 Results: {passed} PASS, {failed} FAIL, {skipped} SKIP, {len(results)} total")

for r in results:
    if r['passed'] is not True:
        status = 'FAIL' if r['passed'] is False else 'SKIP'
        print(f"  {status}: {r['layer']}/{r['category']}/{r['name']} - {r['detail'][:120]}")
