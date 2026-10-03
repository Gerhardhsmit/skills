#!/usr/bin/env python3
"""Offline tests for the outreach engine libs. Synthetic data only (public repo)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
import batch_rank  # noqa: E402
import contact_finder as cf  # noqa: E402
import write_eml  # noqa: E402
import terrain_screen as ts  # noqa: E402
import site_workup  # noqa: E402


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


class WriteEml(unittest.TestCase):
    def test_loader_convention(self):
        import datetime as dt
        d = {"to": "a@x.co.za", "subject": "S", "body": "B", "attachments": ["Brief.pdf"],
             "prospect": "Alpha", "contact_name": "Anna Botha", "email_status": "INFERRED"}
        m = write_eml.build(d)
        self.assertEqual(m["X-CTTX-Attach"], "Brief.pdf")
        self.assertTrue(m["Subject"].startswith("[VERIFY ADDRESS]"))
        self.assertEqual(write_eml.eml_name("Alpha", "Anna Botha", dt.date(2026, 10, 3)),
                         "Alpha - DRAFT_Anna_Botha_Assessment_20261003.eml")


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

    def test_contacted_excluded_and_returned_warm(self):
        out = batch_rank.rank(self.ROWS, size=5, contacted=["beta.co.za", "Gamma Wind Farm"])
        urls = [b["url"] for b in out["batch"]]
        self.assertNotIn("u3", urls)
        self.assertNotIn("u5", urls)
        self.assertEqual(sorted(w["url"] for w in out["warm"]), ["u3", "u5"])

    def test_email_kind(self):
        self.assertEqual(batch_rank.email_kind("reservations@x.co.za"), "generic")
        self.assertEqual(batch_rank.email_kind("jan@x.co.za"), "named")
        self.assertEqual(batch_rank.email_kind(None), "none")


class TerrainScreenTest(unittest.TestCase):
    """Offline: synthetic terrain, no tile downloads."""
    A, B = (-33.0, 25.0), (-33.0, 25.06)  # ~5.6 km east-west

    def test_flat_ground_clear(self):
        r = ts.screen(self.A, self.B, 15, 15, elev_fn=lambda la, lo: 100.0)
        self.assertEqual(r["verdict"], "CLEAR")

    def test_ridge_blocks(self):
        ridge = lambda la, lo: 160.0 if 25.029 < lo < 25.031 else 100.0
        r = ts.screen(self.A, self.B, 15, 15, elev_fn=ridge)
        self.assertEqual(r["verdict"], "BLOCKED")
        self.assertAlmostEqual(r["at_km"], 2.8, delta=0.2)

    def test_earth_bulge_metres(self):
        # 5.6 km flat path, 1 m antennas: bulge ~0.46 m mid-path must not block outright
        r = ts.screen(self.A, self.B, 1, 1, elev_fn=lambda la, lo: 0.0)
        self.assertGreater(r["clear_m"], 0)

    def test_planning_budget(self):
        # 5.8 GHz, 2x25 dBi, 20 dBm, -75 dBm sens, 2 dB misc: ~20.7 dB fade at 5.35 km
        self.assertAlmostEqual(ts.budget(5.35)["fade_db"], 20.7, delta=0.2)
        self.assertGreater(ts.budget(7.2, {**ts.PLAN_CLASS, "gain_dbi": 29})["fade_db"], 20)



class SiteWorkupTest(unittest.TestCase):
    """Offline: a ridge hides one site; the workup must find a relay and connect everything."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self._elev, self._masts = ts.elev, site_workup.mast_index
        # flat 100 m with a 140 m ridge band at lon 25.045-25.05; a 200 m knoll at (−33.03, 25.04)
        def fake(la, lo):
            if abs(la + 33.03) < 0.003 and abs(lo - 25.04) < 0.003:
                return 200.0
            return 140.0 if 25.045 < lo < 25.05 and la > -33.025 else 100.0
        ts.elev = fake
        site_workup.mast_index = lambda: [{"id": "X1", "name": "pt", "lat": -33.03, "lon": 25.0, "service_level": "BRONZE"}]

    def tearDown(self):
        ts.elev, site_workup.mast_index = self._elev, self._masts

    def test_relay_found_and_all_connected(self):
        sites = {"Hub": {"lat": -33.0, "lon": 25.0, "role": "hub"},
                 "Near": {"lat": -33.01, "lon": 25.01, "role": "site"},
                 "Hidden": {"lat": -33.0, "lon": 25.09, "role": "site"}}
        out = site_workup.workup(sites, self.tmp, imagery=False)
        self.assertEqual(out["unreached"], [])
        self.assertTrue(out["relays"])
        self.assertTrue(out["all_hops_pass"])
        self.assertIsNotNone(out["carrier_primary"])
        for f in ("plan.json", "carrier.json", "plan.html", "screen.txt", "plan_out/links.kml"):
            self.assertTrue(os.path.exists(os.path.join(self.tmp, f)), f)


if __name__ == "__main__":
    unittest.main(verbosity=2)
