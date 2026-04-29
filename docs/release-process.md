# Release Process

This project is early research software. Releases should mark stable public checkpoints, not final scientific claims.

## Before creating a release

1. Make sure the working tree is clean.

```powershell
git status --short --branch
```

2. Run local checks.

```powershell
python scripts/dev.py check
```

3. Review generated and ignored files.

```powershell
git status --ignored --short
```

Confirm that `.env`, API keys, private prompts, and unreviewed generated outputs are not being committed.

4. Update `CHANGELOG.md`.

Move unreleased notes into a versioned section such as:

```markdown
## v0.1.0 - 2026-04-28
```

5. Commit and push all release documentation changes.

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
