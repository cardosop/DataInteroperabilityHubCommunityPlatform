"""Falsifiability probe (Phase Q.5.2) — the gate registry's mutation target.

Each scan-gate weakening appends its offender pattern to THIS file, re-runs
the gate scoped to this file, and the harness restores the file
byte-identical afterwards. This file contains ZERO gate violations by
design: if a weakening fails to bite, the gate cannot detect its own target
class (VACUOUS) and the registry run reports it.

DO NOT add gate-violating patterns here — the registry's weakenings are the
only mutation surface. This file is collected by the normal backend suite;
its single test is intentionally trivial.
"""

import unittest


class TestGateFalsifiabilityProbe(unittest.TestCase):
    def test_probe_sanity(self):
        self.assertEqual(1, 1)
