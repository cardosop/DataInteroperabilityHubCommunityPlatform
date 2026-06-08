# Code Review Test Quality Checklist

**Date:** 2026-05-22
**Phase:** 312.18.6 — OpenSpec Integration
**Purpose:** Mandatory test quality checks for every PR review.

---

## Quick Reference

```bash
# Pre-commit (runs automatically):
#   ruff check --fix + ruff format --check
#   GATE-01 through GATE-09 checks

# CI gates (runs on PR):
make test-ci-lint    # Lint + format
make test-unit       # Unit tests
make test-backend    # Backend tests
```

---

## Mandatory Checks

### ✅ 1. New Code Has Tests

- [ ] Every new function/method has at least one test
- [ ] Every new endpoint has at least one integration test
- [ ] Every new React component has at least one unit test
- [ ] Every new business rule has an E2E journey test

### ✅ 2. No Tautological Assertions

- [ ] No `assertTrue(True)` or `assert True`
- [ ] No `expect(true).toBe(true)` or `expect(null).toBeNull()`
- [ ] No `expect(document.body).toBeTruthy()` (always true in JSDOM)
- [ ] CI gate: GATE-01 (Python) + GATE-04 (Frontend)

### ✅ 3. assertRaises Uses Context Manager Correctly

- [ ] `with self.assertRaises(Exc) as cm:` must reference `cm.exception` in the body
- [ ] Exception message/type is asserted, not just that an exception was raised
- [ ] CI gate: GATE-02

### ✅ 4. API Tests Assert Response Body

- [ ] API tests assert specific response fields, not just status code
- [ ] No `assertIn(status_code, [200, 201, 204])` with >2 codes (GATE-03)
- [ ] Response body validation covers: type, required fields, error messages

### ✅ 5. Frontend Tests Use Real Assertions

- [ ] No `expect(container).toBeTruthy()` (guaranteed by render())
- [ ] No `expect(element).not.toBeNull()` (guaranteed by getBy* queries)
- [ ] Component tests verify DOM content, not just presence
- [ ] CI gate: GATE-04

### ✅ 6. No `time.sleep()` Without Justification

- [ ] No bare `time.sleep()` in test files
- [ ] If sleep is unavoidable, use `# noqa: sleep-needed` with documented reason
- [ ] Prefer `wait_for()` / `poll.until()` / `Event.wait()` / mock-time
- [ ] CI gate: GATE-05

### ✅ 7. New Specs Have `@pytest.mark.spec` Markers

- [ ] Every BDD scenario has a corresponding test with `@pytest.mark.spec("capability:req-id:scenario-name")`
- [ ] Coverage checked via `python scripts/spec_coverage_report.py --check 50`
- [ ] CI gate: GATE-15

### ✅ 8. Test File Follows Naming Convention

- [ ] Python: `test_<module>.py` or `<module>_test.py`
- [ ] Frontend: `<Component>.test.tsx` or `<feature>.spec.ts`
- [ ] Test class names start with `Test`
- [ ] Test function names start with `test_`

---

## Additional Checks

### Assertions

- [ ] No `pytest.skip()` inside test body — use `@pytest.mark.skipif` (GATE-07)
- [ ] No empty test methods (`def test_*(): pass`) — GATE-08
- [ ] No bare `mock.assert_called()` — use `assert_called_once_with(...)` (GATE-09)
- [ ] No `try/except NoReverseMatch` in tests — let URL bugs surface (GATE-06)
- [ ] No broad status code lists: `assertIn(status_code, [...])` with >2 codes (GATE-03)

### Mocks

- [ ] Mocks used only at external boundaries (third-party APIs, AWS, etc.)
- [ ] Prefer real services over mocks (Real Services Only principle)
- [ ] Mock assertions specify expected arguments, not just call count

### Fixtures

- [ ] Fixtures use `factory_boy` (`DjangoModelFactory`) not static methods
- [ ] Central `tests/factories.py` preferred over app-level factory files
- [ ] Fixtures are scoped appropriately (`function` vs `class` vs `session`)

### Performance

- [ ] New tests run in <5s (unit), <30s (integration), <5min (E2E)
- [ ] Test doesn't create unnecessary database rows in setup
- [ ] Test uses `--reuse-db` compatible fixtures (no DDL in tests)

---

## Pre-Commit Gate Summary

| Gate | Check | Automated? |
|---|---|---|
| GATE-01 | No tautological assertions | ✅ `check_assert_true_true.py` |
| GATE-02 | No unused assertRaises context | ✅ `check_unused_assert_raises.py` |
| GATE-03 | No broad status code lists | ✅ `check_broad_status_codes.py` |
| GATE-04 | No tautological frontend assertions | ✅ `check_tautological_frontend_assertions.py` |
| GATE-05 | No time.sleep() in tests | ✅ `check_time_sleep_in_tests.py` |
| GATE-06 | No try/except NoReverseMatch | ✅ `check_no_reverse_match.py` |
| GATE-07 | No pytest.skip() in body | ✅ `check_pytest_skip_in_body.py` |
| GATE-08 | No empty test methods | ✅ `check_empty_test_methods.py` |
| GATE-09 | No bare assert_called() | ✅ `check_bare_assert_called.py` |

## Related Documentation
- [docs/test-infrastructure/README.md](README.md) — Test infrastructure index
- [docs/TEST_EXECUTION_PLAN.md](../TEST_EXECUTION_PLAN.md) — Test execution guide
- [CLAUDE.md](../../CLAUDE.md) — Project conventions
