# Project Specification

Technical contract for this project — the requirements we must continuously obey while
developing. This is not a copy of the problem statement; see `docs/PROBLEM_STATEMENT.md`
/ `amazon_docs/problem_statement.md` (Level 1, authoritative) for full prose.

## Objective

Resolve business entities across Source 1 (reference), Source 2 and Source 3 (both
independent, noisy, no shared ID with Source 1 or each other). For every Source 1 test
entity, predict the set (possibly empty) of Source 2/Source 3 entities that refer to the
same real business.

## Schema (identical across all three source files)

| Column | Notes |
| --- | --- |
| `entity_id` | Prefix `S1-`/`S2-`/`S3-` indicates source; no separate source column |
| `business_name` | Free text; abbreviations, legal suffixes, typos, transliterations |
| `business_address` | Free text; partial, missing components, landmark refs |
| `country` | **Open-set string label.** Train = `{US, India}`. Test adds `France` (unseen in train). Never hard-code, filter, or one-hot to `{US, India}` only. |

`train_ground_truth.tsv`: `source1_entity_id`, `matched_entity_ids` (comma-separated
S2-/S3- IDs, empty = no match). One row per S1 entity — see `docs/DATA_CARD.md` for the
measured cardinality distribution (this is **not** a 1:1 problem).

## Outputs (both required, both TSV, both one row per test S1 entity)

- `matching_results.tsv` — `source1_entity_id`, `matched_entity_ids`. **Only file scored
  on the leaderboard.**
- `candidate_pairs.tsv` — `source1_entity_id`, `candidate_entity_ids`. The *final*
  candidate set fed to the matching model at inference — not an intermediate blocking
  pass. Every matched ID must appear in the corresponding candidate list. Not scored, but
  required in the submission package; used to audit blocking quality (candidate recall,
  reduction ratio).

## Evaluation

**F_0.5** (β = 0.5), macro-averaged per Source 1 entity across all S1 entities:

```
F_0.5 = (1.25 × Precision × Recall) / (0.25 × Precision + Recall)
```

Precision is weighted 2× over recall — a false merge (wrong match) costs more than a
missed match. Singletons count: predicting an empty list correctly for a true singleton
scores 1.0; predicting any match for a true singleton scores 0.0. See `docs/DECISIONS.md`
for the implication this has on threshold selection and on how we must treat singleton
performance as a first-class metric, not an edge case.

No ground truth exists for the test set — we must build and use our own held-out
validation split from training data (see `docs/DECISIONS.md`, Validation Strategy).

## Hard constraints (reject-on-violation)

1. Output format exactly as specified — see `docs/SUBMISSION_CHECKLIST.md`.
2. `matched_entity_ids` only references S2-/S3- IDs that exist in the test set. No
   self-matches to S1.
3. Every test S1 entity must appear exactly once.
4. No duplicate IDs within a list; no duplicate `source1_entity_id` rows.
5. Final model must be MIT/Apache-2.0 licensed, ≤ 8B parameters.

## Fair-play constraints (disqualification on violation)

- **No external entity lookup or data augmentation of any kind** — no commercial ER
  APIs/services, no government business-registry lookups, no geocoding APIs, no internet
  data augmentation. The solution must be derivable from the provided train/test data and
  local computation only. This applies to every stage: blocking, feature engineering,
  matching, and any pretrained-model usage (a pretrained model is fine only insofar as it
  was not fine-tuned/augmented with prohibited external business data for this task).

## Scale constraints

Total dataset ≈ 24.2M records across 7 files (measured — see `docs/DATA_CARD.md`; the
"~15M" figure in the initial task framing undercounts the actual corpus). Source 2 and
Source 3 alone are ~5M records each. Any O(S1 × S2) or O(S1 × S3) naive pairwise
comparison (up to ~11 trillion pairs against the full corpus) is computationally
infeasible and must never be implemented — see the Blocking Gate in `docs/WORKFLOW.md`.

## Open questions / not yet decided

These are explicitly **not** committed to by this document — see `docs/DECISIONS.md` for
what has been decided and why, and `docs/EXPERIMENT_LOG.md` for what has actually been
tested:

- Final blocking / candidate-generation strategy
- Final matching model architecture and feature set
- Final validation split design
