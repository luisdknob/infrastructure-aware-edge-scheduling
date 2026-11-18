import csv
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts import validate  # noqa: E402


class MetricsTest(unittest.TestCase):

    def test_percentile_interpolates(self):
        values = [0, 1, 2, 3, 4]
        self.assertAlmostEqual(validate.percentile(values, 0.5), 2.0)
        self.assertAlmostEqual(validate.percentile(values, 0.99), 3.96)

    def test_table2_kube(self):
        p = validate.provision_metrics("kube")
        c = validate.cache_metrics("kube")
        s = validate.storage_metrics("kube")
        self.assertEqual(p["prov_n"], 1250)
        self.assertAlmostEqual(p["prov_avg"], 28.04, places=2)
        self.assertAlmostEqual(p["prov_p99"], 207.27, places=2)
        self.assertEqual(c["cache_hit"], 2042)
        self.assertEqual(c["cache_miss"], 8169)
        self.assertAlmostEqual(s["storage_avg"], 749.31, places=2)
        self.assertAlmostEqual(s["storage_max"], 1423.77, places=2)

    def test_table2_layer(self):
        p = validate.provision_metrics("layer")
        c = validate.cache_metrics("layer")
        s = validate.storage_metrics("layer")
        self.assertAlmostEqual(p["prov_avg"], 22.20, places=2)
        self.assertAlmostEqual(p["prov_p99"], 192.11, places=2)
        self.assertEqual(c["cache_hit"], 3638)
        self.assertEqual(c["cache_miss"], 6573)
        self.assertAlmostEqual(s["storage_avg"], 595.35, places=2)

    def test_table2_infra(self):
        p = validate.provision_metrics("infra")
        c = validate.cache_metrics("infra")
        s = validate.storage_metrics("infra")
        self.assertAlmostEqual(p["prov_avg"], 13.48, places=2)
        self.assertAlmostEqual(p["prov_p99"], 90.69, places=2)
        self.assertEqual(p["prov_max"], 136.04)
        # Archived final cache file differs from the paper's Table II.
        self.assertEqual(c["cache_hit"], 3776)
        self.assertEqual(c["cache_miss"], 6435)
        self.assertEqual(s["storage_min"], 0)
        self.assertAlmostEqual(s["storage_avg"], 584.31, places=2)
        self.assertAlmostEqual(s["storage_max"], 1490.30, places=2)


if __name__ == "__main__":
    unittest.main()
