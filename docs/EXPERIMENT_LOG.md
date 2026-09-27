# Experiment Log

Only real, actually-run experiments go here, in the structure defined in
`docs/WORKFLOW.md`. This is a project log, not a template — do not pre-fill entries for
work that hasn't happened yet.

---

## Experiment 0 — Full-corpus data profiling (Data Gate)

### Hypothesis
The dataset's scale, schema quality, country distribution, and multilingual/multiscript
characteristics can be measured directly and cheaply (single-pass streaming) rather than
assumed, and the initial "~15M records, multilingual" framing needs to be checked against
the real files before any blocking/matching design work begins.

### Motivation
Gate 1 (`docs/WORKFLOW.md`) requires schemas, row counts, missingness, duplicates,
country distribution, multilingual/script characteristics, and ground-truth cardinality
to be known before serious model development. None of this was previously measured in
this project.

### Data
Full corpus: all 7 files under `dataset/train/` and `dataset/test/` (train_source1/2/3,
train_ground_truth, test_source1/2/3) — no sampling for counts/rates; a 100k-record
reservoir sample (fixed seed) used only for length percentiles.

### Method
Wrote two streaming, stdlib-only profiling scripts:
- `src/analysis/profile_source.py` — per-source-file row counts, missingness, duplicate
  entity_id / full-record rates, country distribution, length percentiles, and
  Unicode-script composition (via codepoint-range classification of alphabetic
  characters).
- `src/analysis/profile_ground_truth.py` — per-S1 match-count distribution, S2/S3
  composition, country cross-tab (joined against train_source1.tsv on entity_id, streamed).

Ran both against every file. Followed up manually (ad hoc `python3 -c` scripts, not yet
formalized into the profiling scripts) on two surprising signals: the accented-character
population in US records, and the frequency of literal `"null"` / `"##"` tokens in
addresses.

### Metrics
Row counts, missingness rate, duplicate rate, country distribution, script-presence rate
per file and per country, ground-truth match-count bucket distribution, S2/S3 match
composition.

### Result
Full numbers in `docs/DATA_CARD.md`. Highlights:
- Actual corpus is ~24.2M data rows, not ~15M (the initial estimate undercounted by ~60%).
- Ground truth is not 1:1: mean 3.46 matches/S1 entity, 60.6% of entities have 3–5
  matches, 85.2% of non-singleton entities have matches in both S2 and S3, 5.6% are true
  singletons.
- Source 1 is almost entirely ASCII/Latin in every country, including India, in both
  train and test — it behaves like a pre-normalized reference set.
- Source 2/3 are meaningfully multiscript (18.7–29.2% non-ASCII depending on file),
  concentrated in India-labeled rows, with at least 8 distinct Indic scripts each present
  at non-trace frequency, almost always co-occurring with Latin text in the same record
  (intra-record code-mixing, not clean per-record script separation).
- The "accented Latin" signal in US records is not French — it's a small, specific set of
  Spanish diacritic characters (á é í ó ú Á É Í Ó Ú Ñ) substituted for their plain-Latin
  counterparts inside otherwise-English words, most likely synthetic noise rather than
  genuine language content. France (test-only) shows a different, much higher rate of
  Latin_Extended characters that spot-checks show are genuine French diacritics/words.
- Country distribution differs between train (60/40 US/India, no France) and test
  (38/47/15 US/India/France).
- Two extra noise patterns not listed in the official "Noise Patterns to Expect": literal
  `"null"` tokens and `"##"` placeholder markers inside addresses, each ~2.5–2.7% of
  train_source3 rows.

### Error Analysis
Not applicable in the predictive-model sense — this was a measurement pass, not a
model evaluation. The main methodological risk is that the Unicode script classifier
detects *script*, not *language*, and cannot by itself distinguish "same entity written
in Devanagari" from "different entity that happens to also be in Devanagari," or confirm
the Spanish-diacritic-substitution hypothesis as deliberate noise generation versus a
genuine (if narrow) population of Spanish-named US businesses — both are flagged as
INFERRED, not OBSERVED, in `docs/DATA_CARD.md`.

### Interpretation
The dataset structure rules out two easy defaults: (1) treating matching as one-to-one
pair classification (cardinality is heavily multi-match), and (2) treating "multilingual"
as a uniform property to normalize away globally (the multiscript signal is concentrated
in S2/S3 + India, nearly absent in S1, and the accented-Latin signal in US vs. France is
two different phenomena that should not share a feature).

### Decision
**Keep** — this profiling establishes Gate 1 and directly informs `docs/DECISIONS.md`
D1–D3 (validation strategy, F_0.5 threshold-tuning consequences, and the caution against
a single undifferentiated "has non-ASCII" feature). No modeling decision was made or
implied by this experiment itself.

### Next Experiment
Join ground-truth-matched S1↔S2/S3 record pairs and directly compare their scripts /
name-address content, to empirically test whether India's Devanagari-script S2/S3 records
are script variants of the same entities that appear transliterated in Source 1 (currently
an untested INFERRED hypothesis in `docs/DATA_CARD.md`). This is a natural, cheap
follow-up before committing to any blocking strategy that assumes cross-script matching
is (or isn't) common.
