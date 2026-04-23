"""Fixture for e2e_metrics tests. Expected counts (verified in test_e2e_metrics.py):

- except_exception_pass_count: 2
- orm_query_count: 0
- status_code_assertion_count: 0
- test_skip_call_count: 0
"""


def a():
    try:
        pass
    except Exception:
        pass


def b():
    try:
        pass
    except:
        pass


def c_specific_type_does_not_count():
    try:
        pass
    except ValueError:
        pass


def d_not_just_pass_does_not_count():
    try:
        pass
    except Exception as exc:
        raise RuntimeError("chained") from exc


def e_logs_is_not_pass():
    import logging

    try:
        pass
    except Exception:
        logging.getLogger(__name__).warning("oops")


# except Exception: pass  <-- comment text, must not count
# The line above should NOT be counted by an AST-based metric.
