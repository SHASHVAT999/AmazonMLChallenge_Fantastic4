# Decisions

Important architectural/research decisions and their rationale. Only decisions actually
made go here — proposals under consideration are marked as such and are not binding.

---

## D1 — Validation strategy: recommended, NOT YET IMPLEMENTED

**Status:** Recommendation only. Awaiting user sign-off before implementation (Gate 2 in
`docs/WORKFLOW.md`).

**Context.** The test set has no ground truth (`docs/PROJECT_SPEC.md`); we must build our
own held-out split from `train_ground_truth.tsv`. `docs/DATA_CARD.md` establishes the
structure a naive split would ignore:

- Ground truth is **not** 1:1 — mean 3.46 matches/entity, 60.6% of entities have 3–5
  matches, and 85.2% of non-singleton entities have matches in **both** S2 and S3.
  Splitting at the (S1, S2/S3-candidate) pair level rather than the S1-entity level would
  leak: pairs from the same S1 entity would land in both train and validation folds,
  letting a model implicitly learn "this S1 already has 2 confirmed matches in my
  training fold, so a 3rd candidate is likely" in a way it cannot know at real inference
  time.
- Singletons are 5.6% of entities and are scored specially under F_0.5 (a correct empty
  prediction = 1.0; any predicted match = 0.0) — under-sampling them in a validation fold
  would bias validation F_0.5 upward or downward versus what the leaderboard will show.
- Country mix **shifts between train and test** (~60/40 US/India in train vs.
  ~38/47/15 US/India/France in test), and France has **zero** training examples at all.
  A random split of training data cannot validate France performance by construction —
  that is a hard limitation, not something a smarter split can fix.
- Source 2/3 have a small (0.3–0.5%) exact-duplicate-record rate within each file
  (`docs/DATA_CARD.md`); if a duplicated S2/S3 record and its near-identical twin land on
  opposite sides of a split, that is weak information leakage (near-duplicate content
  seen during "training" reappearing in "validation"). Not yet quantified.

**Recommendation.**

1. Split at the **Source-1-entity level** (never at the pair/candidate level) — hold out
   entire S1 entities and everything genuinely matched to them.
2. **Stratify the split by ground-truth match-count bucket** (0 / 1 / 2 / 3–5 / 6–10 /
   11+, per `docs/DATA_CARD.md`) so the validation fold's cardinality mix matches the
   full training set's, keeping singleton performance measurable and representative
   rather than diluted or over/under-weighted.
3. Also stratify by `country` (US/India) so both are proportionally represented in the
   validation fold — this does not solve the France gap, which should instead be treated
   explicitly: report validation metrics only for US/India, and treat France as an
   **untested extrapolation risk** to flag in the methodology writeup, not something the
   internal validation score can speak to.
4. Do not yet decide the exact fold size/count (e.g. single hold-out vs. k-fold) — that
   is a Gate-2 implementation detail to settle when validation is actually built, and
   should itself be recorded here once decided.

**Why not a plain random split:** it would silently mix the leakage/imbalance risks
above into the score, giving a validation F_0.5 that overstates real performance
(pair-level leakage) or misrepresents singleton/rare-cardinality behavior (no
stratification).

**Not decided:** whether to use a single stratified hold-out or repeated/k-fold
validation; how to handle the small duplicate-record leakage risk; whether additional
stratification (e.g. by observed script-mix per entity) is warranted once blocking work
begins.

---

## D2 — F_0.5 interpretation and its consequence for threshold/error-cost decisions

**Status:** Decided (this is a direct, non-optional consequence of the official metric,
not a project choice — recorded here so later work doesn't silently drift from it).

- F_0.5 weights precision 2× recall and is macro-averaged **per S1 entity**, not
  micro-averaged over all pairs. A model that is very precise on high-cardinality
  entities but sloppy on singletons is punished disproportionately, because each S1
  entity — singleton or not — contributes equally to the average (`docs/PROJECT_SPEC.md`).
- Given 5.6% of entities are true singletons (`docs/DATA_CARD.md`), correctly predicting
  "no match" is worth real, measurable leaderboard credit, and a false merge on a
  singleton is a full 0.0 for that entity — not a small penalty. Any matching-threshold
  tuning must evaluate singleton accuracy as its own reported metric, not fold it into an
  aggregate the singleton contribution can be masked by.
- Consequence for future work: threshold/decision-boundary tuning for the final matcher
  should optimize macro F_0.5 directly on the (Gate 2) validation split — not a
  pair-level accuracy/AUC proxy — since those do not respect the macro-per-entity,
  precision-weighted structure of the real metric.

---

## D3 — Do not treat "Latin_Extended present" as a single feature/signal

**Status:** Decided, informs future feature-engineering work (not yet implemented).

`docs/DATA_CARD.md`'s multilingual analysis found that "Latin_Extended" script presence
conflates at least two different phenomena: synthetic accented-vowel substitution noise
in US records (not genuine language content) and authentic French diacritics in
France-labeled records. A feature that just flags "has Latin_Extended chars" would blur
these together. Any future feature engineering that uses script signals must condition on
`country` or otherwise separate these populations, not treat non-ASCII/Latin_Extended
presence as one undifferentiated signal.

---

## Open items intentionally deferred (not decisions yet)

- Final blocking / candidate-generation strategy (Gate 3, `docs/WORKFLOW.md`).
- Final matching model architecture and feature set (Gate 4).
- Whether/how to join ground-truth-matched S1↔S2/S3 pairs to empirically verify the
  "same entity, different script" hypothesis in `docs/DATA_CARD.md`'s multilingual
  section — a natural, cheap next analysis but not yet run.
