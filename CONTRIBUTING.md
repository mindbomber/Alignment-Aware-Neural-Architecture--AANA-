# Contributing

Thanks for considering a contribution. This repository is intended to be understandable to beginners while still useful for evaluation research.

## Good first contributions

- Improve setup or workflow documentation.
- Add small reproducible examples.
- Add tests for scoring, parsing, and deterministic constraint checks.
- Improve error messages when input files or environment variables are missing.
- Add comments only where the logic is genuinely hard to follow.

## Development workflow

1. Fork the repository.
2. Create a feature branch.
3. Make a focused change.
4. Run the relevant scripts with a small `--limit` or `--dry-run`.
5. Run focused tests for the changed surface.
6. Before committing or pushing code changes, run the full regression suite:

```powershell
python -m pytest -q
```

7. Open a pull request explaining what changed and how you checked it.

GitHub CI also runs the full pytest regression suite on pushes and pull requests. Treat local tests as the fast feedback loop and CI as the required independent check.

## Style

- Keep scripts simple and readable.
- Prefer standard-library Python unless a dependency clearly improves reproducibility.
- Do not commit generated `eval_outputs/` files unless there is a specific reason and the data has been reviewed.
- Do not commit secrets, private prompts, or unpublished data.

## Reporting problems

When opening an issue, include:

- The command you ran.
- Your Python version.
- The error message or unexpected output.
- Whether the run used `--dry-run` or made live API calls.
