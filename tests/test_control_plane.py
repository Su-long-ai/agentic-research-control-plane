from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from research_control_plane.control import ResearchControlPlane


class ControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cp = ResearchControlPlane(self.root / "state")
        self.files = self.root / "files"
        self.files.mkdir()

    def f(self, name: str, content: str = "x") -> Path:
        p = self.files / name
        p.write_text(content, encoding="utf-8")
        return p

    def prepare_ready_candidate(self):
        impl = self.f("candidate.py", "print('ok')\n")
        self.cp.submit_candidate("c1", {"implementation": impl}, "candidate")
        self.cp.record_lead_decision("c1", "READY", "formal test justified")
        return impl

    def formal_artifacts(self):
        return {
            "protocol": self.f("protocol.json", "{}"),
            "runner": self.f("runner.py", "# runner"),
            "auditor": self.f("auditor.py", "# auditor"),
            "input": self.f("input.json", "[]"),
        }

    def test_non_ready_candidate_cannot_freeze(self):
        impl = self.f("candidate.py")
        self.cp.submit_candidate("c1", {"implementation": impl}, "candidate")
        self.cp.record_lead_decision("c1", "EVIDENCE_ONLY", "not enough evidence")
        with self.assertRaisesRegex(RuntimeError, "READY"):
            self.cp.freeze_experiment("e1", "c1", self.formal_artifacts())

    def test_candidate_drift_fails_closed(self):
        impl = self.prepare_ready_candidate()
        impl.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "drifted"):
            self.cp.freeze_experiment("e1", "c1", self.formal_artifacts())

    def test_frozen_protocol_drift_blocks_promotion(self):
        self.prepare_ready_candidate()
        artifacts = self.formal_artifacts()
        self.cp.freeze_experiment("e1", "c1", artifacts)
        artifacts["protocol"].write_text('{"changed":true}', encoding="utf-8")
        status = self.cp.promotion_status("e1")
        self.assertFalse(status["promotable"])
        self.assertIn("FROZEN_ARTIFACT_DRIFT", status["reasons"])

    def test_pass_audit_allows_promotion(self):
        self.prepare_ready_candidate()
        self.cp.freeze_experiment("e1", "c1", self.formal_artifacts())
        result = self.f("result.json", '{"value":1}')
        audit = self.f("audit.json", json.dumps({"verdict": "PASS"}))
        self.cp.bind_result("e1", result)
        self.cp.bind_audit("e1", audit)
        self.assertEqual(self.cp.promotion_status("e1"), {"promotable": True, "reasons": []})

    def test_fail_audit_denies_promotion(self):
        self.prepare_ready_candidate()
        self.cp.freeze_experiment("e1", "c1", self.formal_artifacts())
        result = self.f("result.json", '{"value":1}')
        audit = self.f("audit.json", json.dumps({"verdict": "FAIL"}))
        self.cp.bind_result("e1", result)
        self.cp.bind_audit("e1", audit)
        status = self.cp.promotion_status("e1")
        self.assertFalse(status["promotable"])
        self.assertIn("AUDIT_NOT_PASS", status["reasons"])

    def test_result_drift_denies_promotion(self):
        self.prepare_ready_candidate()
        self.cp.freeze_experiment("e1", "c1", self.formal_artifacts())
        result = self.f("result.json", '{"value":1}')
        audit = self.f("audit.json", json.dumps({"verdict": "PASS"}))
        self.cp.bind_result("e1", result)
        self.cp.bind_audit("e1", audit)
        result.write_text('{"value":2}', encoding="utf-8")
        status = self.cp.promotion_status("e1")
        self.assertFalse(status["promotable"])
        self.assertIn("RESULT_DRIFT", status["reasons"])

    def test_export_manifest_binds_control_records(self):
        self.prepare_ready_candidate()
        self.cp.freeze_experiment("e1", "c1", self.formal_artifacts())
        result = self.f("result.json", '{"value":1}')
        audit = self.f("audit.json", json.dumps({"verdict": "PASS"}))
        self.cp.bind_result("e1", result)
        self.cp.bind_audit("e1", audit)
        out = self.root / "promotion_manifest.json"
        manifest = self.cp.export_manifest("e1", out)
        self.assertTrue(out.exists())
        self.assertTrue(manifest["promotion"]["promotable"])
        self.assertEqual(set(manifest["state_records"]), {"freeze", "result", "audit"})
        self.assertTrue(all(len(v["sha256"]) == 64 for v in manifest["state_records"].values()))


if __name__ == "__main__":
    unittest.main()
