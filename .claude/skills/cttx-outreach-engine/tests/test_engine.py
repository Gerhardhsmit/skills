#!/usr/bin/env python3
"""Offline tests for the outreach engine libs. Synthetic data only (public repo)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
import batch_rank  # noqa: E402
import contact_finder as cf  # noqa: E402


class ContactFinder(unittest.TestCase):
    def test_sa_particles(self):
        first, last = cf.split_name("Jan van der Merwe")
        self.assertEqual(first, "jan")
        self.assertEqual(cf.surname_forms(last)[0], "vandermerwe")
        self.assertIn("merwe", cf.surname_forms(last))

    def test_first_dot_last_evidence(self):
        r = cf.infer("example.co.za", "Anna Botha", ["piet.smit@example.co.za", "info@example.co.za",
                                                     "karin.nel@example.co.za"])
        self.assertEqual(r["pattern"], "first.last")
        self.assertEqual(r["email"], "anna.botha@example.co.za")
        self.assertEqual(r["email_status"], "INFERRED")
        self.assertEqual(r["evidence_addresses"], ["piet.smit@example.co.za", "karin.nel@example.co.za"])

    def test_no_evidence_uses_prior(self):
        r = cf.infer("example.co.za", "Anna Botha", ["info@example.co.za"])
        self.assertEqual(r["evidence_strength"], "none")
        self.assertEqual(r["email"], "anna@example.co.za")
        self.assertTrue(r["label"].startswith("INFERRED"))

    def test_published_exact(self):
        r = cf.infer("example.co.za", "Anna Botha", ["anna@example.co.za"])
        self.assertEqual(r["email_status"], "PUBLISHED")
        self.assertIsNone(r["label"])

    def test_other_domain_ignored(self):
        r = cf.infer("example.co.za", "Anna Botha", ["anna.botha@gmail.com"])
        self.assertEqual(r["evidence_addresses"], [])
        self.assertEqual(r["email_status"], "INFERRED")

    def test_accents(self):
        first, last = cf.split_name("Ané Müller")
        self.assertEqual((first, last), ("ane", ["muller"]))


class BatchRank(unittest.TestCase):
    ROWS = [
        {"Company": "Alpha Citrus (Pty) Ltd", "Province": "Western Cape", "Sector": "Farm / Agriculture",
         "Priority": "High", "Contact Person": "A Person (MD)", "Email": "a@alpha.co.za",
         "Website": "https://alpha.co.za", "Pain Signal": "x", "url": "u1"},
        {"Company": "Alpha Citrus", "Province": "Western Cape", "Sector": "Farm / Agriculture",
         "Priority": "High", "Contact Person": None, "Email": None, "url": "u2"},
        {"Company": "Beta Game Reserve", "Province": "Eastern Cape", "Sector": "Private Game Reserve",
         "Priority": "High", "Contact Person": None, "Email": "reservations@beta.co.za",
         "Website": "https://beta.co.za", "url": "u3"},
        {"Company": "Valley Agricultural Operations", "Province": "Eastern Cape",
         "Sector": "Farm / Agriculture", "Priority": "Medium", "Contact Person": "Farm Owner (TBC)",
         "url": "u4"},
        {"Company": "Gamma Wind Farm", "Province": "Eastern Cape", "Sector": "Wind Farm",
         "Priority": "Medium", "Contact Person": "C Person", "Email": None, "Website": "https://g.co.za",
         "url": "u5"},
    ]

    def test_dedupe_keeps_most_complete(self):
        out = batch_rank.rank(self.ROWS, size=5)
        d = out["duplicates"][0]
        self.assertEqual(d["keep"], "u1")
        self.assertEqual(d["duplicates"], ["u2"])

    def test_segment_becomes_prospecting_task(self):
        out = batch_rank.rank(self.ROWS, size=5)
        self.assertEqual([t["url"] for t in out["prospecting_tasks"]], ["u4"])
        self.assertNotIn("u4", [b["url"] for b in out["batch"]])

    def test_balance_alternates_provinces(self):
        out = batch_rank.rank(self.ROWS, size=2)
        self.assertEqual({b["province"] for b in out["batch"]}, {"Western Cape", "Eastern Cape"})

    def test_email_kind(self):
        self.assertEqual(batch_rank.email_kind("reservations@x.co.za"), "generic")
        self.assertEqual(batch_rank.email_kind("jan@x.co.za"), "named")
        self.assertEqual(batch_rank.email_kind(None), "none")


if __name__ == "__main__":
    unittest.main(verbosity=2)
