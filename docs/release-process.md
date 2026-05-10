# Release Process

This project is early research software. Releases should mark stable public checkpoints, not final scientific claims.

## Before creating a release

1. Make sure the working tree is clean.

```powershell
git status --short --branch
```

2. Run the hardened release gate.

```powershell
python scripts/dev.py release-gate
```

The release gate is aligned with CI around the hardened core:

- `api`: Python compile, unit tests, and public contract freeze.
- `platform`: the standard `python scripts/validate_aana_platform.py` CI gate.
- `catalog`: adapter gallery metadata, docs links, evidence requirements, and completeness.
- `adapter`: executable adapter examples and expected gate/action/AIx behavior.
- `docs`: public docs bundle and onboarding surfaces.
- `audit`: redacted audit write and audit redaction validation.
- `production_profile`: deployment, governance, observability, evidence, release, and audit-profile checks.

Failure annotations include the gate category so it is clear whether the issue is API, platform, adapter, catalog, audit, docs, or production-profile related.

3. Run the post-refactor stability pass before updating release docs.

```powershell
python scripts/dev.py test
python -m unittest tests.test_adapter_runner_golden_outputs
python scripts/adapters/compare_adapter_runner_baseline.py --ref HEAD
```

Use `--ref <pre-refactor-ref>` when the pre-refactor runner is not the current `HEAD`. The comparison checks representative adapter-runner decision surfaces before and after decomposition: gate decision, recommended action, AIx decision, candidate AIx decision, violations, and failed constraints. Do not update release docs or create the platform-core tag until the full suite and golden comparison pass.

4. Review generated and ignored files.

```powershell
git status --ignored --short
```

Confirm that `.env`, API keys, private prompts, and unreviewed generated outputs are not being committed.

5. Update `CHANGELOG.md`.

Move unreleased notes into a versioned section such as:

```markdown
## v0.1.0 - 2026-04-28
```

6. Commit and push all release documentation changes.

7. Tag the first clean platform-core baseline only after the baseline commit exists and the working tree is clean.

```powershell
git status --short --branch
git tag -a platform-core-baseline-v0.1 -m "First clean platform core baseline"
git push origin platform-core-baseline-v0.1
```

The tag should identify the committed platform-core state, not a dirty working tree or an earlier commit.

## Creating `v0.1.0` on GitHub

Because GitHub CLI may not be authenticated for repository management, the simplest path is the web UI:

1. Open the repository on GitHub.
2. Click **Releases**.
3. Click **Draft a new release**.
4. Choose **Create a new tag** and enter:

```text
v0.1.0
```

5. Target branch:

```text
master
```

6. Release title:

```text
v0.1.0 - Public open-source baseline
```

7. Release notes:

```markdown
Initial public release of the AANA evaluation pipeline.

Includes:
- Evaluation scripts for baseline, correction-prompt, AANA-loop, tool-assisted, and originality workflows.
- Beginner-facing README and documentation.
- Examples, tests, CI, contribution templates, citation metadata, and project metadata.
- MIT license.

This is early research software. Results should be reviewed before publication and should not be treated as a certified benchmark.
```

8. Leave **Set as a pre-release** unchecked unless you want GitHub to mark the release as unstable.
9. Click **Publish release**.

## After release

- Confirm the release page links to the correct tag.
- Confirm the README badges still render.
- Confirm the **Cite this repository** button appears from `CITATION.cff`.
- Start the next changelog section for future changes.
