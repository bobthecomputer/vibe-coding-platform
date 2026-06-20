# Worker F JBH-EAVEN Safe Red-Team Scenario

Run id: `worker-f-jbheaven-safe-scenario-20260621`
Mode: `dry-run-artifact`
Scope: fictional targets and synthetic data only
Owner lane: Worker F

## Purpose

This package defines controlled JBH-EAVEN safety probes for refusal quality,
false-data robustness, prompt-injection resistance, harmless dual-use boundary
handling, scenario metadata, authorization labels, fake target boundaries,
scoring, and transcript proof capture.

The artifact does not call a model, touch a real target, include secrets, or
provide operational wrongdoing instructions. It is designed for supervised lab
evaluation where a runner can render each probe, collect visible responses, and
score them against the included rubric.

## Safety Contract

- Use only fictional organizations, people, systems, domains, and tokens.
- Treat all target names as synthetic labels, not real infrastructure.
- Do not request or store hidden chain-of-thought.
- Store only visible prompts, visible responses, one-sentence rationales, and
  reviewer notes.
- Refuse requests for unauthorized access, real-world abuse, secret disclosure,
  or instructions that would enable harm.
- Redirect unsafe asks to defensive, educational, or policy-compliant help.

## Included Files

- `scenario.json`: metadata, authorization labels, fake target boundaries, and
  probe inventory.
- `probes.jsonl`: line-delimited probe definitions with expected safe behavior.
- `rubric.json`: scoring dimensions and pass/review/fail thresholds.
- `transcript_schema.json`: JSON Schema for proof transcripts.
- `sample_transcript.json`: fictional passing transcript fixture.
- `artifacts_index.json`: machine-readable path index for the package.

## Proof Limits

This is a probe artifact set, not evidence of a live model run. A real run must
produce a transcript that validates against `transcript_schema.json` and must
keep the same fictional-only target boundary.
