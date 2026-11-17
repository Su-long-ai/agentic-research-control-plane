from __future__ import annotations

import json
import shutil
from pathlib import Path

from .control import ResearchControlPlane


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    root = Path("demo_workspace")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir()

    files = root / "files"
    files.mkdir()
    candidate = write(files / "candidate.py", "def solve(xs): return sum(xs)\n")
    protocol = write(files / "protocol.json", '{"metric":"exact_sum"}\n')
    runner = write(files / "runner.py", "# frozen runner placeholder\n")
    auditor = write(files / "auditor.py", "# frozen independent auditor placeholder\n")
    input_file = write(files / "input.json", "[1,2,3]\n")

    cp = ResearchControlPlane(root / "state")
    cp.submit_candidate("candidate-001", {"implementation": candidate}, "sum implementation")
    cp.record_lead_decision("candidate-001", "READY", "ready for bounded formal test")
    cp.freeze_experiment(
        "exp-001",
        "candidate-001",
        {"protocol": protocol, "runner": runner, "auditor": auditor, "input": input_file},
    )

    result = write(files / "result.json", '{"value":6}\n')
    audit = files / "audit.json"
    audit.write_text(json.dumps({"verdict": "PASS", "recomputed_value": 6}), encoding="utf-8")

    cp.bind_result("exp-001", result)
    cp.bind_audit("exp-001", audit)
    print(cp.promotion_status("exp-001"))


if __name__ == "__main__":
    main()
