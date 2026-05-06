# NeurIPS-Style Submission Checklist

## Scope and claims
- [x] Theoretical claims are separated from empirical claims.
- [x] Alignment dynamics equation is labeled as a modeling abstraction.
- [x] The limitations section warns against overclaiming.
- [ ] Replace illustrative results with real evaluation outputs before empirical submission.

## Reproducibility
- [ ] Include task JSONL.
- [ ] Include exact prompts for low/high pressure conditions.
- [ ] Include baseline/prompt/AANA/hybrid correction conditions.
- [ ] Include model versions and inference parameters.
- [ ] Include raw generations and grader outputs.
- [ ] Include scripts used for scoring and plotting.

## Figures
- [x] All figures are native TikZ/PGFPlots.
- [x] No external image dependencies.
- [x] Figures compile under pdfLaTeX.

## NeurIPS formatting
- [x] Uses a NeurIPS-like clean single-file style.
- [ ] For official submission, replace custom formatting with official `neurips_2026.sty` when available.
- [ ] For anonymous review, remove author information.
- [ ] For camera-ready, restore author information and acknowledgments.

## Ethics
- [x] Includes societal impact and limitation language.
- [ ] Add dataset/model-specific ethics notes after running real experiments.
