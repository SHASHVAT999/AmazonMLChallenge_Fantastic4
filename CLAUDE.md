# Amazon ML Challenge 2026 — Business Entity Resolution

## Project identity

Resolve business entities across three noisy, independently-sourced files (Source 1 =
deduplicated reference; Source 2 and Source 3 = noisy, no shared ID with S1 or each
other). For every Source 1 test entity, predict the set of S2/S3 records — zero, one, or
many — that refer to the same real business. Scored on **F_0.5** (precision weighted 2×
recall), macro-averaged per S1 entity.

## Authoritative documents (read before architectural decisions)

- **Level 1 (challenge rules, authoritative, do not reinterpret):**
  `amazon_docs/problem_statement.md`, `amazon_docs/guidlines.md`,
  `amazon_docs/student_resource/` (incl. `utils/validate_submission.py`,
  `Documentation_template.md`). If Level 1 documents conflict with each other or with
  anything below, say so explicitly — do not silently resolve it.
- **Level 2 (how we work, editable):** `docs/PROJECT_SPEC.md` (technical contract),
  `docs/WORKFLOW.md` (controlled research loop + gates), `docs/DATA_CARD.md` (measured
  dataset facts), `docs/EXPERIMENT_LOG.md` (real experiments only), `docs/DECISIONS.md`
  (recorded decisions + rationale), `docs/SUBMISSION_CHECKLIST.md` (mechanical
  requirements).
- **Level 3 (code/notebooks/scripts):** not authoritative just because it exists —
  existing implementation choices still need to be justified.

`docs/PROBLEM_STATEMENT.md` and `docs/GUIDELINES.md` are verified-identical copies of the
Level 1 originals for convenience; treat the `amazon_docs/` originals as the source of
truth if they ever diverge.

## Hard constraints

1. **No external entity lookup or data augmentation, ever** — no commercial ER APIs, no
   government registry lookups, no geocoding APIs, no internet-sourced business data, at
   any pipeline stage. This is a disqualification-level rule, not a style preference.
2. `country` is an **open-set** string label. Train = {US, India}; test adds France
   (unseen in train). Never hard-code, filter, or one-hot to {US, India}.
3. Final model: MIT/Apache-2.0 licensed, ≤ 8B parameters.
4. Output format, ID rules, and package structure: see `docs/SUBMISSION_CHECKLIST.md` —
   it distinguishes hard rejection rules from diagnostic-only warnings.

## Scale awareness

Measured full corpus ≈ **24.2M data rows** across 7 files (`docs/DATA_CARD.md` — the
original "~15M" estimate was wrong by ~60%; don't reuse it). Source 2/3 alone are ~5M
rows each. Before any full-corpus or pairwise operation: estimate comparisons, memory,
disk, and runtime first; prototype on a small sample; never write code that only works
because a dataset happened to fit in RAM on one run. Never generate the full S1×S2/S3
pair space (an O(n²)-shaped operation across millions of records) — candidate generation
(blocking) exists specifically to avoid this, and is a distinct stage from final
matching.

## Multilingual reality (measured, not assumed — see `docs/DATA_CARD.md`)

Source 1 is almost entirely Latin/ASCII in every country. Source 2/3 are meaningfully
multiscript (up to ~29% non-ASCII in test), concentrated in India-labeled records, with
at least 8 distinct Indic scripts observed, usually code-mixed with Latin text in the
same field. Do not assume English-only processing anywhere. Do not aggressively
transliterate, ASCII-fold, or strip scripts in place — preserve the raw field alongside
any normalized/derived representation, and read `docs/DATA_CARD.md`'s "OBSERVED / INFERRED
/ UNKNOWN" distinctions before building on any multilingual claim (in particular: the
"Latin_Extended" signal in US records is very likely synthetic noise, not genuine
language content — don't conflate it with the genuinely French Latin_Extended signal in
France records; see Decision D3).

## Controlled workflow (full detail in `docs/WORKFLOW.md`)

`DISCOVER → UNDERSTAND → HYPOTHESIZE → IMPLEMENT → VERIFY → RECORD → DECIDE NEXT STEP`,
gated (Data → Validation → Blocking → Matching → Submission). This is **not** an
autonomous "work until done" loop:

- Work only the explicitly authorized phase; stop at its gate.
- Verify with objective metrics (candidate recall, precision/recall/F_0.5, reduction
  ratio, runtime/memory) — never an LLM self-rating of output quality.
- Record real experiments in `docs/EXPERIMENT_LOG.md` (never fabricate entries) and real
  decisions in `docs/DECISIONS.md`, using the structures already established there.
- Major architectural choices (final blocking strategy, final model family, final
  validation design) are the user's call — present findings and one recommended next
  step, then wait.
- Never modify the evaluation methodology just to improve a single result.

## Working conventions

- Verify claims against the actual project files (data, code, docs) rather than
  recalling them — files in `docs/` and `dataset/` can and do change between sessions.
- After a meaningful decision, measurement, or experiment, update the relevant doc in the
  same session — don't let `docs/` drift out of sync with what was actually done.
- Prefer reproducible, streaming scripts (see `src/analysis/` for the profiling
  precedent) over manual/notebook-only, RAM-unbounded operations.
