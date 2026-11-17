from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Mapping

from .hashing import sha256_file
from .store import JsonStore


class ResearchControlPlane:
    ALLOWED_DECISIONS = {"READY", "REJECT", "EVIDENCE_ONLY"}
    _SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

    def __init__(self, root: Path):
        self.store = JsonStore(root)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _validate_id(cls, value: str, field: str) -> str:
        if not cls._SAFE_ID.fullmatch(value):
            raise ValueError(f"unsafe {field}: {value!r}")
        return value

    @staticmethod
    def _bind(paths: Mapping[str, Path]) -> dict[str, dict[str, str]]:
        bound = {}
        for role, path in paths.items():
            p = Path(path).resolve()
            if not p.is_file():
                raise FileNotFoundError(p)
            bound[role] = {"path": str(p), "sha256": sha256_file(p)}
        return bound

    def submit_candidate(
        self,
        candidate_id: str,
        artifact_paths: Mapping[str, Path],
        summary: str,
    ) -> dict:
        self._validate_id(candidate_id, "candidate_id")
        if not artifact_paths:
            raise ValueError("candidate must bind at least one artifact")
        payload = {
            "candidate_id": candidate_id,
            "summary": summary,
            "submitted_at": self._now(),
            "artifacts": self._bind(artifact_paths),
        }
        self.store.write(f"candidates/{candidate_id}/submission.json", payload)
        return payload

    def verify_candidate(self, candidate_id: str) -> bool:
        self._validate_id(candidate_id, "candidate_id")
        data = self.store.read(f"candidates/{candidate_id}/submission.json")
        return self._verify_bound(data["artifacts"])

    def record_lead_decision(
        self,
        candidate_id: str,
        decision: str,
        rationale: str,
    ) -> dict:
        self._validate_id(candidate_id, "candidate_id")
        decision = decision.upper()
        if decision not in self.ALLOWED_DECISIONS:
            raise ValueError(f"unsupported decision: {decision}")
        if not self.verify_candidate(candidate_id):
            raise RuntimeError("candidate artifacts drifted before Lead decision")
        payload = {
            "candidate_id": candidate_id,
            "decision": decision,
            "rationale": rationale,
            "decided_at": self._now(),
        }
        self.store.write(f"candidates/{candidate_id}/lead_decision.json", payload)
        return payload

    def freeze_experiment(
        self,
        experiment_id: str,
        candidate_id: str,
        artifacts: Mapping[str, Path],
    ) -> dict:
        self._validate_id(experiment_id, "experiment_id")
        self._validate_id(candidate_id, "candidate_id")
        decision = self.store.read(f"candidates/{candidate_id}/lead_decision.json")
        if decision["decision"] != "READY":
            raise RuntimeError("formal experiment requires Lead READY")
        if not self.verify_candidate(candidate_id):
            raise RuntimeError("candidate artifacts drifted before freeze")

        required = {"protocol", "runner", "auditor", "input"}
        missing = required - set(artifacts)
        if missing:
            raise ValueError(f"missing formal artifacts: {sorted(missing)}")

        payload = {
            "experiment_id": experiment_id,
            "candidate_id": candidate_id,
            "frozen_at": self._now(),
            "candidate_artifacts": self.store.read(
                f"candidates/{candidate_id}/submission.json"
            )["artifacts"],
            "formal_artifacts": self._bind(artifacts),
        }
        self.store.write(f"experiments/{experiment_id}/freeze.json", payload)
        return payload

    @staticmethod
    def _verify_bound(bound: Mapping[str, Mapping[str, str]]) -> bool:
        for item in bound.values():
            path = Path(item["path"])
            if not path.is_file() or sha256_file(path) != item["sha256"]:
                return False
        return True

    def verify_frozen(self, experiment_id: str) -> bool:
        self._validate_id(experiment_id, "experiment_id")
        freeze = self.store.read(f"experiments/{experiment_id}/freeze.json")
        return self._verify_bound(freeze["candidate_artifacts"]) and self._verify_bound(
            freeze["formal_artifacts"]
        )

    def bind_result(self, experiment_id: str, result_path: Path) -> dict:
        self._validate_id(experiment_id, "experiment_id")
        if not self.verify_frozen(experiment_id):
            raise RuntimeError("frozen artifacts drifted before result binding")
        p = Path(result_path).resolve()
        payload = {
            "experiment_id": experiment_id,
            "bound_at": self._now(),
            "result": {"path": str(p), "sha256": sha256_file(p)},
        }
        self.store.write(f"experiments/{experiment_id}/result.json", payload)
        return payload

    def bind_audit(self, experiment_id: str, audit_report_path: Path) -> dict:
        self._validate_id(experiment_id, "experiment_id")
        if not self.verify_frozen(experiment_id):
            raise RuntimeError("frozen artifacts drifted before audit binding")
        if not self.store.exists(f"experiments/{experiment_id}/result.json"):
            raise RuntimeError("result must be bound before audit")
        result = self.store.read(f"experiments/{experiment_id}/result.json")
        if not self._verify_bound({"result": result["result"]}):
            raise RuntimeError("result artifact drifted before audit binding")

        p = Path(audit_report_path).resolve()
        import json

        report = json.loads(p.read_text(encoding="utf-8"))
        verdict = str(report.get("verdict", "")).upper()
        if verdict not in {"PASS", "FAIL"}:
            raise ValueError("audit report verdict must be PASS or FAIL")
        payload = {
            "experiment_id": experiment_id,
            "bound_at": self._now(),
            "verdict": verdict,
            "audit_report": {"path": str(p), "sha256": sha256_file(p)},
        }
        self.store.write(f"experiments/{experiment_id}/audit.json", payload)
        return payload

    def export_manifest(self, experiment_id: str, output_path: Path | None = None) -> dict:
        """Build a compact, independently checkable manifest of the promotion chain."""
        self._validate_id(experiment_id, "experiment_id")
        records = {}
        for name in ("freeze", "result", "audit"):
            relative = f"experiments/{experiment_id}/{name}.json"
            if self.store.exists(relative):
                path = self.store.root / relative
                records[name] = {
                    "path": relative,
                    "sha256": sha256_file(path),
                }

        manifest = {
            "experiment_id": experiment_id,
            "generated_at": self._now(),
            "state_records": records,
            "promotion": self.promotion_status(experiment_id),
        }
        if output_path is not None:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                __import__("json").dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return manifest

    def promotion_status(self, experiment_id: str) -> dict:
        self._validate_id(experiment_id, "experiment_id")
        reasons = []
        if not self.store.exists(f"experiments/{experiment_id}/freeze.json"):
            reasons.append("NO_FREEZE")
            return {"promotable": False, "reasons": reasons}

        if not self.verify_frozen(experiment_id):
            reasons.append("FROZEN_ARTIFACT_DRIFT")

        result_rel = f"experiments/{experiment_id}/result.json"
        if not self.store.exists(result_rel):
            reasons.append("NO_BOUND_RESULT")
        else:
            result = self.store.read(result_rel)
            if not self._verify_bound({"result": result["result"]}):
                reasons.append("RESULT_DRIFT")

        audit_rel = f"experiments/{experiment_id}/audit.json"
        if not self.store.exists(audit_rel):
            reasons.append("NO_BOUND_AUDIT")
        else:
            audit = self.store.read(audit_rel)
            if not self._verify_bound({"audit": audit["audit_report"]}):
                reasons.append("AUDIT_REPORT_DRIFT")
            if audit["verdict"] != "PASS":
                reasons.append("AUDIT_NOT_PASS")

        return {"promotable": not reasons, "reasons": reasons}
