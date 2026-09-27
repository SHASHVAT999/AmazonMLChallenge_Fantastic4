# Submission Checklist

Derived from `amazon_docs/student_resource/utils/validate_submission.py` (Level 1,
authoritative for what the validator actually enforces), cross-checked against
`amazon_docs/problem_statement.md` (Level 1, authoritative for what the scorer/portal
enforces — the validator is a local approximation of this, not a replacement).

## HARD SUBMISSION REQUIREMENTS

These cause **rejection** by the validator and/or the portal scorer. All are enforced
by `validate_submission.py` as errors (exit code 1) unless noted otherwise.

- [ ] `matching_results.tsv` exists, is valid UTF-8, and is genuinely **tab**-separated
      (a comma-separated file with a tab-free header is explicitly detected and rejected).
- [ ] Header is exactly `source1_entity_id\tmatched_entity_ids`.
- [ ] Every `entity_id` in `test_source1.tsv` appears as a row exactly **once**
      (missing S1 entities → rejected; duplicate `source1_entity_id` rows → rejected).
- [ ] No row uses an S1 ID that isn't in the test set.
- [ ] No duplicate IDs within a single `matched_entity_ids` list.
- [ ] `matched_entity_ids` contains only `S2-`/`S3-` prefixed IDs — no `S1-` self-matches,
      no IDs with any other prefix. (Problem statement, Constraint 2.)
- [ ] `matched_entity_ids` empty (not omitted — an empty string after the tab) for
      entities with no match.
- [ ] Final model: MIT/Apache-2.0 licensed, ≤ 8B parameters. (Problem statement,
      Constraint 5 — **not checked by the validator script**; verified separately in the
      submission-package review.)

## DIAGNOSTIC / WARNING CHECKS (never fail the run, but should not be ignored)

- `candidate_pairs.tsv` — optional for a local validator run, but **required in the
  final submission zip**. If absent, the validator only warns.
- ID-existence check (`--check-ids`, off by default): verifies every matched/candidate
  ID actually exists in `test_source2.tsv`/`test_source3.tsv`. Off by default because it
  loads all S2/S3 IDs into memory (a few GB on the full ~1.7M-entity test set,
  more with `--candidate`). A nonexistent ID **lowers the score but does not reject the
  submission** — treat this as a pre-submission diagnostic, not a gate. Drop `--candidate`
  if `--check-ids` runs out of memory.
- Matched IDs not present in `candidate_pairs.tsv` for the same S1 entity — usually a
  pipeline bug (final matches should be a subset of candidates) but only warned, never
  rejected.

## Final submission package structure (Level 1: problem statement, "Final Submission Package")

```
<team_name>_submission.zip
├── output/
│   ├── matching_results.tsv
│   └── candidate_pairs.tsv
├── code/
│   └── business_entity_resolution/
│       ├── src/
│       ├── README.md            # exact reproduce instructions, data → blocking → matching → output
│       └── requirements.txt     # pinned deps
└── Documentation_template.md    # filled in (methodology, blocking strategy, model/features)
```

- [ ] `output/matching_results.tsv` and `output/candidate_pairs.tsv` both present.
- [ ] `code/business_entity_resolution/src/` contains a runnable, self-contained pipeline —
      "anyone should be able to regenerate both output files ... using only what is in
      this folder."
- [ ] `code/business_entity_resolution/README.md` gives exact run instructions.
- [ ] `code/business_entity_resolution/requirements.txt` pins versions.
- [ ] `Documentation_template.md` filled in with methodology, blocking strategy, model
      architecture/features, and other relevant approach detail (no page limit).
- [ ] No external data lookup anywhere in the pipeline (Academic Integrity section) —
      this is verified by manual review of the submitted code, not by the validator script.

## Running the validator

```bash
cd amazon_docs/student_resource   # validator expects to run from student_resource/
python3 utils/validate_submission.py \
    --matching output/matching_results.tsv \
    --candidate output/candidate_pairs.tsv \
    --test-dir dataset/test
```

Exit 0 + `PASS` = safe to upload. Exit 1 = fix the numbered issues first. The validator
never computes your F_0.5 score — that only happens on the portal (public leaderboard)
or in your own held-out validation (see `docs/DECISIONS.md`).

## Note: `dataset/test` vs `amazon_docs/student_resource/dataset/test`

The project root's `dataset/` and `amazon_docs/student_resource/dataset/` are byte-identical
duplicate copies (verified by matching file sizes across all 7 files). The validator's
`--test-dir` default (`dataset/test`) is relative to wherever you invoke it from — point
it at whichever copy matches your working directory. See `docs/DATA_CARD.md` for the
duplication note.
