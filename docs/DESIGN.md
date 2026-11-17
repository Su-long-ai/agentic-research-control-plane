# Design Notes

## System goal

The control plane separates **research evidence** from **promotion authority**.

Its purpose is not to decide whether a scientific idea is true. Its purpose is to make it difficult to silently change the experiment after seeing the outcome.

## Core invariants

### Candidate artifacts are bound before review

A research candidate is represented by artifact paths plus SHA-256 hashes.

A Lead decision applies to those exact bytes. If the implementation changes after submission, the candidate must be reviewed again.

### Formal evaluation is prospectively frozen

Before formal execution, the control plane binds:

- candidate artifacts;
- protocol;
- runner;
- independent auditor;
- input.

The freeze happens before the result exists.

This blocks a common failure mode: adapting the metric, runner or audit logic after observing a disappointing result.

### Audit implementation is part of the freeze

The auditor is treated as an artifact, not an informal post-hoc opinion.

That matters because an audit can otherwise drift toward the same assumptions as the implementation it is checking.

### Results are immutable inputs to promotion

The result artifact is hash-bound before audit binding.

If it changes later, promotion fails closed even if a previous audit said PASS.

### PASS is necessary, not sufficient by itself

Promotion requires a conjunction:

- frozen artifacts still match;
- a result is bound and unchanged;
- an audit is bound and unchanged;
- audit verdict is PASS.

No single positive metric or audit file can bypass the rest of the chain.

## State-path safety

Candidate and experiment IDs are validated before they are interpolated into state paths. The public implementation accepts only bounded alphanumeric/underscore/hyphen identifiers, so an untrusted logical ID cannot become a path-traversal primitive.

## Why SHA-256 instead of copying everything

The public extraction keeps original files in place and records their hashes.

This demonstrates **identity binding** without forcing a storage policy.

A production system could additionally place every artifact in content-addressed immutable storage. The promotion logic would stay the same.

## Promotion manifest

`export_manifest()` creates a compact record that binds the control records themselves:

- `freeze.json`;
- `result.json`;
- `audit.json`;
- current promotion verdict.

This is useful for archival, handoff and independent verification.

## Failure modes

| Failure | Promotion behavior |
| --- | --- |
| Lead decision is not READY | formal freeze denied |
| candidate changes before freeze | freeze denied |
| protocol/runner/auditor/input changes | promotion denied |
| result changes after binding | promotion denied |
| audit report changes | promotion denied |
| audit verdict is FAIL | promotion denied |
| all bindings intact + PASS | promotable |

## Deliberate non-goals

The control plane does not prove:

- that a metric measures the right construct;
- that the dataset is unbiased;
- that the auditor is logically correct;
- that a promoted result generalizes;
- that a domain-specific system is safe to deploy.

Those remain scientific/domain responsibilities.

## What I would add next

For a larger research platform:

- content-addressed artifact storage;
- signed manifests;
- immutable event log;
- reviewer identity / RBAC;
- protocol versioning;
- reproducible execution containers;
- blinded evaluation support;
- CI integration for deterministic auditors.
