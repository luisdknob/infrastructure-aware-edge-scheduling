import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCEN = os.path.join(ROOT, "data", "scenarios")


class ScenarioTest(unittest.TestCase):

    def load(self, name):
        with open(os.path.join(SCEN, name)) as f:
            return json.load(f)

    def test_all_scenarios(self):
        expected = {
            "kube-scheduler.json": ("KubeScheduler", None),
            "image-locality.json": ("KubeScheduler", "ImageLocalityPriority"),
            "layer-locality.json": ("KubeScheduler", "LayerLocalityPriority"),
            "infrastructure-aware.json": ("KubeScheduler", "LeastCongestedNodePriority"),
        }
        for name, (sched, priority) in expected.items():
            d = self.load(name)
            self.assertEqual(len(d["applications"]), 350, name)
            self.assertEqual(len(d["images"]), 24, name)
            self.assertEqual(len(d["nodes"]), 197, name)
            cfg = d["infrastructure"]["scheduler"]
            self.assertEqual(cfg["name"], sched, name)
            if priority:
                names = [p["name"] for p in cfg["config"]["priorities"]]
                self.assertEqual(names, [
                    "LeastRequestedPriority", "SelectorSpreadPriority", priority
                ], name)
                self.assertEqual(cfg["config"]["priorities"][-1]["weight"], 30, name)


if __name__ == "__main__":
    unittest.main()
