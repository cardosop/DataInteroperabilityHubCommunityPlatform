"""Fixture covering unittest-TestCase style assertions. Expected counts:

- except_exception_pass_count: 0
- orm_query_count: 0
- status_code_assertion_count: 4
    (assertEqual, assertNotEqual, assertIn, assertGreaterEqual each reference .status_code)
- test_skip_call_count: 1  (self.skipTest)
"""

import unittest


class StatusAssertionsCase(unittest.TestCase):
    def test_unittest_assert_equal(self):
        resp = type("R", (), {"status_code": 201})()
        self.assertEqual(resp.status_code, 201)

    def test_unittest_assert_not_equal(self):
        resp = type("R", (), {"status_code": 500})()
        self.assertNotEqual(resp.status_code, 500)

    def test_unittest_assert_in(self):
        resp = type("R", (), {"status_code": 200})()
        self.assertIn(resp.status_code, (200, 204))

    def test_unittest_assert_greater_equal(self):
        resp = type("R", (), {"status_code": 200})()
        self.assertGreaterEqual(resp.status_code, 200)

    def test_non_status_assert_does_not_count(self):
        resp = type("R", (), {"body": "ok"})()
        self.assertEqual(resp.body, "ok")

    def test_self_skip(self):
        self.skipTest("not wired")

    # self.assertEqual(resp.status_code, 201)  <-- comment, must not count
