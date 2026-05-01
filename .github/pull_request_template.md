## Summary

<!-- What does this PR do? 1-2 sentences. -->

## Evidence

<!-- Link to passing tests, screenshots, or verification commands.
     Every checkbox in the task spec should have a corresponding
     evidence link (test file:line, CI run, or screenshot). -->

- [ ] Tests pass: <!-- e.g. `hub/apps/auth/tests/test_views.py::TestLogin` -->
- [ ] No new skips introduced (check `docs/SKIP_REGISTRY.md` if adding)
- [ ] Existing tests not broken: <!-- CI link or local run output -->

## Checklist

- [ ] I have read the task spec and all acceptance criteria are met
- [ ] New code has tests (or justification why not)
- [ ] No `except Exception: pass` added without logging
- [ ] No `window.alert/confirm/prompt` added (use ConfirmDialog/Modal)
- [ ] No bare `test.skip()` without reason string
- [ ] Security: no secrets in code, no new `innerHTML` without DOMPurify
- [ ] Documentation updated if behaviour changed
- [ ] **F2 scope guardrail (when touching the lineage editor):** PR does NOT re-introduce items from the v1 non-goals list at [docs/mvpdocs/concepts/lineage.md](docs/mvpdocs/concepts/lineage.md#field-level-lineage-editor--phase-228f2-v1-non-goals-req-lin-f2-006) without an explicit ADR + product sign-off. (Phase 228.F2.34)

## Related

<!-- Link to task spec, issue, or design doc -->
- Task: <!-- e.g. Phase 112.B.2 -->
