# Project Workflow

This is a **controlled** research/engineering loop, not an autonomous one. Claude Code
does not "keep working until the project is finished." Each session works one explicitly
authorized phase, produces measurable results, verifies and records them, then stops at
the relevant gate and waits for the user to choose the next step.

## The loop

```
DISCOVER  → UNDERSTAND → HYPOTHESIZE → IMPLEMENT → VERIFY → RECORD → DECIDE NEXT STEP
```

- **Discover / Understand**: read the actual data/code/docs before forming an opinion.
  Never assume an empty doc means "no requirements" — it means "not yet written."
- **Hypothesize**: state what you expect and why, before running anything expensive.
- **Implement**: the smallest change that tests the hypothesis. Prefer a script over a
  one-off notebook cell so it's rerunnable.
- **Verify**: with an objective metric (candidate recall, precision/recall/F_0.5,
  reduction ratio, runtime, memory) — never with an LLM self-rating of output quality.
- **Record**: log real experiments in `docs/EXPERIMENT_LOG.md`, real decisions in
  `docs/DECISIONS.md`. Do not fabricate entries for anything not actually run.
- **Decide next step**: stop, report findings, recommend exactly one next step, and wait.
  Major architectural choices (final blocking strategy, final model family, final
  validation split) are the user's call, not Claude's to make unilaterally.

## Gates

Each gate must be cleared — with real, recorded measurements — before the next phase of
work begins.

**Gate 1 — Data Gate.** Schemas, row counts, missingness, duplicate rates, country
distribution, multilingual/script characteristics, ground-truth cardinality structure,
and source-to-source differences are measured and documented in `docs/DATA_CARD.md`.

**Gate 2 — Validation Gate.** A reproducible validation split exists (built from training
data, since the test set has no ground truth), with its leakage risks and rationale
recorded in `docs/DECISIONS.md`, before any model comparison happens.

**Gate 3 — Blocking Gate.** Before final matching is built: candidate recall, candidate
volume, reduction ratio, and multilingual failure modes of the blocking strategy are
measured on the validation split; missed true matches are inspected, not just counted.

**Gate 4 — Matching Gate.** The final matcher is evaluated with precision, recall, F_0.5
(macro, per-S1), singleton performance, multi-match performance, and false-positive /
false-negative error analysis — not a single aggregate number.

**Gate 5 — Submission Gate.** See `docs/SUBMISSION_CHECKLIST.md` in full: output format
validated, every test S1 present, no duplicate rows/IDs, valid prefixes, matches ⊆
candidates, `validate_submission.py` passes, reproducibility verified from a clean
checkout, documentation complete.

## Experiment discipline

Every meaningful experiment recorded in `docs/EXPERIMENT_LOG.md` follows:

Hypothesis → Motivation → Data (exact split/sample used) → Method (exactly what changed)
→ Metrics (objective, stated in advance) → Result → Error Analysis → Interpretation →
Decision (keep / modify / reject / investigate further) → Next Experiment.

## Stopping conditions

Stop and report back to the user (rather than proceeding) when:

- A phase gate above has just been cleared.
- A measurement contradicts an assumption baked into `docs/PROJECT_SPEC.md` or a prior
  `docs/DECISIONS.md` entry.
- The next step requires a genuinely expensive operation (full-corpus O(n²)-shaped work,
  large model training, generating the full candidate graph) — estimate cost first, get
  it reviewed, then run it.
- The next step is a major architectural choice rather than an incremental one.

## Resource-awareness (mandatory before any expensive operation)

Before implementing anything over the full ~24M-record corpus (see `docs/DATA_CARD.md`
for the measured scale), estimate: expected comparisons, memory, disk, and runtime.
Prototype and validate correctness on a small representative sample first; never write a
profiling or pipeline script that only works because the full dataset happened to fit in
RAM on one machine. Prefer streaming/chunked I/O with explicit encoding (`utf-8`) for
anything touching a full source file.
