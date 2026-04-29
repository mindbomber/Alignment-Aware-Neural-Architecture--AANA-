# Development Helpers

`dev.py` provides short, cross-platform commands for common local checks.

Run from the repository root:

```powershell
python scripts/dev.py test
python scripts/dev.py sample
python scripts/dev.py dry-run
python scripts/dev.py check
```

Commands:

- `compile` - Compile Python files in `eval_pipeline/`, `tests/`, and `scripts/`.
- `test` - Run the unit tests.
- `sample` - Score the checked-in sample outputs.
- `dry-run` - Generate held-out tasks, run a tiny no-API evaluation, and score it.
- `check` - Run compile, tests, and sample scoring.
