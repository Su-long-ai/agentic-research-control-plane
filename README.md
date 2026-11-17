# Agentic Research Control Plane

A small, domain-agnostic control plane for **multi-agent research workflows that need reproducible promotion gates**.

This repository is a sanitized public extraction of governance ideas used in a larger private research system. It deliberately contains **no trading strategy, broker integration, market data, user data, credentials, or private experiment artifacts**.

## Problem

Agentic research can produce lots of plausible-looking results while still being hard to trust:

- workers can overwrite shared state;
- evidence can drift after review;
- a protocol can change after results are visible;
- an auditor can accidentally reuse the same implementation assumptions;
- a positive metric can be promoted without a reproducible chain of custody.

The control plane makes those boundaries explicit.

```text
research candidate
      |
      v
artifact hashing
      |
      v
Lead decision gate
      |
      v
freeze protocol + runner + auditor + inputs
      |
      v
formal execution
      |
      v
bind result artifact
      |
      v
independent audit report
      |
      v
PROMOTABLE only if:
  frozen artifacts unchanged
  + Lead READY
  + result bound
  + audit verdict PASS
```

## Recruiter quick scan

- SHA-256 artifact binding
- explicit Lead promotion decisions
- prospective formal-experiment freezing
- independent audit-result binding
- fail-closed promotion checks
- atomic JSON state persistence
- negative paths covered by unit tests
- exportable promotion manifest that SHA-binds freeze/result/audit control records
- domain-agnostic design

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate

set PYTHONPATH=src
python -m unittest discover -s tests -v
python -m research_control_plane.demo
```

The public suite currently covers **7 promotion/control paths**, including non-READY candidates, candidate drift, frozen-protocol drift, result drift, audit FAIL, successful promotion, and manifest export.

## Minimal API

```python
from pathlib import Path
from research_control_plane.control import ResearchControlPlane

cp = ResearchControlPlane(Path("./state"))

cp.submit_candidate(
    candidate_id="candidate-001",
    artifact_paths={"implementation": Path("candidate.py")},
    summary="candidate implementation",
)

cp.record_lead_decision(
    candidate_id="candidate-001",
    decision="READY",
    rationale="bounded evidence is sufficient for a formal test",
)

cp.freeze_experiment(
    experiment_id="exp-001",
    candidate_id="candidate-001",
    artifacts={
        "protocol": Path("protocol.json"),
        "runner": Path("runner.py"),
        "auditor": Path("auditor.py"),
        "input": Path("input.json"),
    },
)
```

## Design principles

### Freeze before outcome

The formal protocol, runner, independent auditor and inputs are hashed before the result exists.

### Evidence and authority are separate

A worker can submit evidence, but only an explicit Lead decision can unlock a formal experiment.

### Audit is not promotion by itself

Promotion requires both an audit PASS and unchanged frozen artifacts.

### Fail closed on drift

If any frozen artifact changes after freeze, promotion is denied until a new experiment version is frozen.

### Export a verification manifest

After result + audit binding, `export_manifest()` produces a compact JSON record containing SHA-256 hashes for the freeze/result/audit control records plus the current promotion verdict. This makes the promotion chain easy to archive or independently re-check.

## What this repository does not claim

This is infrastructure for research governance. It does **not** prove that any model, strategy or experiment is scientifically valid merely because the workflow passes.

## License

MIT
