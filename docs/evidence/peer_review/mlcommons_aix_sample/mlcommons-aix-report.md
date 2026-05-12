# AANA MLCommons AIx Report

Recommendation: `pilot_ready`

## Executive Summary

AANA converted MLCommons benchmark evidence into a deployment-facing AIx audit report with component scores, hard blockers, evidence quality, remediation, monitoring, and a regulated-industry boundary.

## MLCommons Source

- Source type: `modelbench`
- Benchmark: `ModelBench journal`
- SUT: `{}`
- Hazard count: `3`

## AIx Summary

- Overall AIx: `0.9652`
- Component scores: `{'P': 1.0, 'B': 0.975, 'C': 0.991, 'F': 0.85}`
- Risk tier: `regulated_industry_candidate`
- Hard blockers: `[]`

## Tested Hazards

| Hazard | Layer | Score | Violation Rate | Samples |
| --- | --- | --- | --- | --- |
| prv | C | 0.994 | 0.006 | 120 |
| spc_hlt | C | 0.988 | 0.012 | 120 |
| hte | B | 0.975 | 0.025 | 120 |

## Remediation Plan

- Attach domain-owner signoff, audit retention evidence, and incident-response routing for regulated pilots.

## Human Review

- Route hard blockers and specialized-advice hazards to domain-owner review.
- Require regulated-industry owner signoff before enforcement or go-live.

## Monitoring Plan

- Run AANA in shadow mode around the deployed system and compare live AIx drift against MLCommons benchmark evidence.
- Track hard blockers, top hazard failures, evidence freshness, and human-review outcomes.
- Regenerate this report after model, prompt, policy, connector, or dataset changes.

## Limitations

- MLCommons benchmark evidence plus AANA AIx reporting is production-candidate evidence only; it is not production certification or go-live approval for regulated industries.
- MLCommons benchmark results do not prove runtime behavior on private customer workflows.
- AANA AIx is a governance signal and must be paired with security, privacy, legal, and domain-owner review.
