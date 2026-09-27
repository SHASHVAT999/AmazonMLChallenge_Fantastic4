# Data Card

What the actual dataset contains, measured directly from the files under `dataset/`
(byte-identical to `amazon_docs/student_resource/dataset/` — see Provenance below).
Produced by `src/analysis/profile_source.py` and `src/analysis/profile_ground_truth.py`,
run against the **full corpus** (no sampling, except length percentiles which use a
100k-record reservoir sample per file). Re-run those scripts to reproduce every number
here.

## File inventory and scale

| File | Data rows | Size |
| --- | --- | --- |
| `train/train_source1.tsv` | 2,206,821 | 210 MB |
| `train/train_source2.tsv` | 5,034,616 | 489 MB |
| `train/train_source3.tsv` | 5,285,603 | 504 MB |
| `train/train_ground_truth.tsv` | 2,206,821 | 127 MB |
| `test/test_source1.tsv` | 1,732,544 | 175 MB |
| `test/test_source2.tsv` | 4,887,273 | 509 MB |
| `test/test_source3.tsv` | 5,082,316 | 506 MB |
| **Total** | **~26.4M rows incl. headers / ~24.2M data rows** | **~2.52 GB (~5.04 GB counting the duplicate copy)** |

The initial task framing's "~15M records" estimate **undercounts the actual corpus by
~60%** — treat "~15M" as wrong going forward; use the measured ~24.2M.

All files: UTF-8, tab-separated, 4 columns (`entity_id`, `business_name`,
`business_address`, `country`) for source files, 2 columns for ground truth. Header
present and correctly formed in every file checked. Zero malformed rows (wrong column
count) found in any file.

## Provenance / duplication

`amazon_docs/student_resource/dataset/` and the project-root `dataset/` are **byte-identical
duplicates** — every one of the 7 files matches exactly in size between the two locations.
Treat `dataset/` (project root) as the working copy; the `amazon_docs/` copy is the
untouched original distribution and should not be modified.

## Schema / missingness / duplicates (measured, full corpus)

| File | Empty `business_address` | Duplicate `entity_id` | Duplicate (name, address, country) |
| --- | --- | --- | --- |
| train_source1 | 0.0000% | 0 | 0 |
| train_source2 | 3.3561% | 0 | 0.5139% |
| train_source3 | 3.3282% | 0 | 0.3568% |
| test_source1 | 0.0000% | 0 | 0.0000% |
| test_source2 | 2.6479% | 0 | 0.4633% |
| test_source3 | 2.6779% | 0 | 0.3206% |

`business_name`, `country`, and `entity_id` are never empty in any file. `entity_id` is
unique within every file (no intra-file duplicate IDs anywhere). Source 1 (both
train/test) has **zero** exact full-record duplicates — consistent with it being the
"deduplicated reference source" per the problem statement. Source 2/3 have a small
(0.3–0.5%) but non-zero rate of exact duplicate (name, address, country) triples —
these are same-file duplicates and have not been checked for whether they map to the
same or different ground-truth matches.

Two additional noise patterns found that are **not** called out in the official
"Noise Patterns to Expect" list:

- **Literal `null` token inside `business_address`** (e.g. `"New Delhi, null, A-68"`) —
  measured at ~2.5% of train_source3 rows. This is distinct from an empty address field
  and should not be silently treated as if it were a normal address token.
- **`##` placeholder/masking markers** inside name or address (e.g. `"##8 Willow Oak
  Lane"`, `"OFFICE NO. ##70"`) — measured at ~2.6% of train_source3 rows. Likely a
  redaction or number-masking artifact from data generation; needs a decision on how (or
  whether) to normalize it before treating it as a real address-number token.

(Both measured only on train_source3 so far; expected to generalize to source2/3 given
their similar noise profiles, but not yet confirmed on every file — full-corpus
confirmation is a small follow-up, not yet done.)

## Country distribution (measured, full corpus)

| File | US | India | France |
| --- | --- | --- | --- |
| train_source1 | 59.98% | 40.02% | — (absent) |
| train_source2 | 59.92% | 40.08% | — (absent) |
| train_source3 | 59.98% | 40.02% | — (absent) |
| test_source1 | 38.27% | 46.75% | 14.98% |
| test_source2 | 38.29% | 47.32% | 14.39% |
| test_source3 | 38.28% | 47.32% | 14.40% |

**Important distribution shift**: the train/test country mix is not the same. Training
is exactly ~60/40 US/India with no France; test is ~38/47/15 US/India/France. A
validation split built naively (e.g. stratified only to match train's own distribution)
will not reflect the test distribution's country mix, and cannot cover France at all
since France has zero training examples — see `docs/DECISIONS.md`.

## Ground-truth cardinality (measured, full corpus, `train_ground_truth.tsv`)

**This is not a 1:1 or simple binary-classification problem.** Per-S1-entity match count:

| Match count | Share of S1 entities |
| --- | --- |
| 0 (singleton) | 5.58% |
| 1 | 5.40% |
| 2 | 17.00% |
| 3–5 | 60.58% |
| 6–10 | 11.43% |
| 11+ | 0.0017% (37 entities) |

Mean matches per S1 entity: **3.46**. The large majority (60.6%) of entities have
between 3 and 5 true matches. Only 5.6% are true singletons (no match at all) — small,
but non-trivial, and scored specially under F_0.5 (see `docs/PROJECT_SPEC.md`).

Among S1 entities with at least one match:

- Both S2 and S3 present: **85.24%**
- S2-only: 6.86%
- S3-only: 7.90%

So for a typical non-singleton S1 entity, the matching problem is "find several records
in **both** S2 and S3," not "find one record in either." The bucket distribution is
essentially identical between US and India (checked per-country; both distributions
match the aggregate to within 0.2 percentage points) — cardinality structure does **not**
appear to be country-dependent, at least between US/India in training. Unknown/unverified
for France (no training ground truth exists for France at all).

## Multilingual and Multiscript Characteristics

Method: every alphabetic character in `business_name + " " + business_address` is
classified by Unicode codepoint range into one script bucket (Latin_ASCII, Latin_Extended,
Devanagari, Bengali, Gurmukhi, Gujarati, Oriya, Tamil, Telugu, Kannada, Malayalam, or
Other). A record is "non-ASCII" if any character falls outside Latin_ASCII, and
"mixed-script" if it contains alphabetic characters from more than one bucket. See
`src/analysis/profile_source.py` for the exact ranges used. This detects *script*, not
*language* — a script can host multiple languages, and script alone cannot identify a
specific language.

### OBSERVED

- **Source 1 is almost entirely ASCII/Latin, in both train and test, for every country
  including India.** Non-ASCII rate: 0.025% (train), and the ~554 non-ASCII train records
  are Latin_Extended (accented), not Indic script — India-labeled Source-1 records do not
  contain Devanagari or other Indic scripts in any meaningfully observed quantity. Source
  1 behaves like a pre-normalized/pre-transliterated reference set regardless of country.
- **Source 2 and Source 3 are meaningfully multiscript, concentrated in India-labeled
  records.** Non-ASCII rate: train_source2 21.98%, train_source3 18.72%, test_source2
  29.19%, test_source3 25.42% (test is noticeably higher than train for both S2 and S3).
  Within India-labeled S2/S3 records specifically, ~19–24% contain Devanagari, with
  smaller but consistent shares of Kannada, Telugu, Tamil, Gujarati, Bengali, Malayalam,
  Gurmukhi, and Oriya (each roughly 1–3.5% of India rows, present in every S2/S3 file
  checked). This is a real, multi-script (not single-alternate-script) phenomenon — at
  least 8 distinct Indic scripts appear at measurable, non-trace frequency.
- **"Mixed-script" and "non-ASCII" are numerically almost identical in every file
  measured** (e.g. train_source2: 21.98% vs 21.98%). This means a script-tagged record
  is almost never *purely* non-Latin — it is overwhelmingly Latin text combined with one
  Indic (or Latin_Extended) script in the same field. Directly observed examples include
  Latin legal suffixes or brand fragments co-occurring with Devanagari business names in
  the same `business_name` string (e.g. a name containing both Devanagari characters and
  a Latin word in the same field). Treat "multiscript" here as **intra-record code-mixing**,
  not files split cleanly by script.
- **The apparent "accented Latin" signal in US-labeled records is not French and is very
  likely synthetic corruption, not genuine language content.** Spot-checked the actual
  characters behind the 6–7% "Latin_Extended" rate in US train records (which have zero
  France examples): the characters are drawn from a small, specific set — `á é í ó ú Á É
  Í Ó Ú Ñ` — each substituted in place of the corresponding plain Latin vowel/letter inside
  otherwise-English words (e.g. `"N**é**twork"` for `"Network"`, `"C**á**mpany"` for
  `"Company"`). This reads as a single-character substitution noise generator drawing
  from Spanish diacritics, not organic Spanish-language business names — words are
  English business vocabulary with one letter swapped, not Spanish vocabulary.
- **France-labeled records (test only) show much higher Latin_Extended rates (~38.6–39.0%)
  than US or India**, and the earlier manual sample showed genuine French diacritics and
  words (`Président`, `Nouvelle-Aquitaine`, `Rue`, `Frères`, `SARL`) — consistent with
  authentic French address/name content, not the same substitution-noise pattern seen in
  US records. These two "Latin_Extended" populations (US noise-substitution vs. France
  genuine-diacritics) are conflated by the script classifier alone; a feature/model that
  treats "Latin_Extended present" as one signal would be mixing two different phenomena.
- No CJK (Han/Kana/Hangul), Arabic, or Cyrillic script observed in any of the sampled
  script-presence counts across any file.

### INFERRED (plausible interpretation, not directly verified)

- The India-labeled Devanagari/Indic-script content in S2/S3 plausibly represents
  authentic native-script name/address variants of the same businesses that appear
  transliterated in Source 1 — this is the kind of cross-source script variation the
  problem statement's "transliteration variants" noise pattern describes — but this has
  **not** been confirmed by actually joining ground-truth-matched S1↔S2/S3 record pairs
  and comparing their scripts; that join is a natural next analysis, not yet done.
  See `docs/DECISIONS.md` open question.
- The `##` and literal-`null` address artifacts (above) plausibly come from the same
  synthetic-noise generation process as the accented-vowel substitution, given their
  similar order-of-magnitude frequency (~2.5–2.7%) — not confirmed by tracing a shared
  generation mechanism.

### UNKNOWN

- Whether Devanagari (or other Indic-script) business names in S2/S3 are transliterations
  of the *same* underlying entity as a Latin-script Source-1 record, versus independently
  romanized differently, has not been tested.
- Which specific language(s) the Devanagari-script text represents (Hindi vs. Marathi vs.
  others sharing the script) is not determined by script detection alone and has not been
  otherwise investigated.
- Whether the France test set contains any further noise patterns unique to it beyond
  higher Latin_Extended prevalence (no training data exists for France to compare against).

### Design implication (not yet a committed decision — see `docs/DECISIONS.md`)

Per the multilingual engineering principle in `docs/WORKFLOW.md` / `CLAUDE.md`: do not
strip, transliterate, or ASCII-fold any field in place. Any normalization must preserve
the raw field alongside it, and must be justified per-script rather than assumed globally
— the US "Latin_Extended" signal in particular should **not** be treated the same as
genuine French or Indic-script content given the evidence above.

## Length distributions (reservoir sample, n=100,000 per file, deterministic seed)

`business_name` length (chars), p50 / p95 / p99 across files: 24–25 / 36–42 / 42–50.
`business_address` length (chars), p50 / p95 / p99: 37–50 / 91–105 / 115–126. Test-set
addresses run slightly longer at the median than train (e.g. test_source1 p50=50 vs.
train_source1 p50=41). Max observed lengths (100k sample, not a true corpus max): names
up to ~103 chars, addresses up to ~231 chars — no extreme outliers (e.g. multi-KB
fields) found in the sampled records.

## Reproducing this data card

```bash
python3 src/analysis/profile_source.py dataset/train/train_source1.tsv
python3 src/analysis/profile_source.py dataset/train/train_source2.tsv
python3 src/analysis/profile_source.py dataset/train/train_source3.tsv
python3 src/analysis/profile_source.py dataset/test/test_source1.tsv
python3 src/analysis/profile_source.py dataset/test/test_source2.tsv
python3 src/analysis/profile_source.py dataset/test/test_source3.tsv
python3 src/analysis/profile_ground_truth.py dataset/train/train_ground_truth.tsv \
    --source1 dataset/train/train_source1.tsv
```

Each run streams its input file once (no full-file in-memory load beyond a bounded
100k-record reservoir and per-file hash sets for duplicate/entity-ID checks); runtime was
10–80 seconds per file on this machine.
