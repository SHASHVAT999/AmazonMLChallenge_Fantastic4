# Amazon ML Challenge --- Business Entity Resolution

## Current Solution Plan

### 1. Problem Understanding

The task is to identify which records in **Source 2** and **Source 3**
represent the same real-world business as each record in **Source 1**.

Source 1 is the deduplicated reference source. Each Source 1 entity may
have:

-   zero matching records,
-   one matching record, or
-   multiple matching records

from Source 2 and/or Source 3.

The data contains noisy business names and addresses, including
abbreviations, spelling variations, punctuation differences, word-order
changes, transliterations, partial addresses, missing address
components, and landmark-based references.

The final evaluation uses **F0.5**, which places more weight on
precision than recall. Therefore, avoiding incorrect business merges is
especially important.

------------------------------------------------------------------------

## 2. Dataset Scale

Current dataset inspection shows:

  Dataset                     Rows
  -------------------- -----------
  Train Source 1         2,206,821
  Train Source 2         5,034,616
  Train Source 3         5,285,603
  Train Ground Truth     2,206,821
  Test Source 1          1,732,544
  Test Source 2          4,887,273
  Test Source 3          5,082,316

The combined dataset is large enough that brute-force pairwise
comparison is not practical.

For example, comparing every Source 1 record against every Source 2/3
record would result in tens of trillions of comparisons.

Therefore, **candidate generation / blocking is the central optimization
of the solution**.

------------------------------------------------------------------------

## 3. Overall Architecture

``` text
Raw TSV Data
      |
      v
Efficient Data Layer
(DuckDB / Polars / Parquet)
      |
      v
Unicode-safe Normalization
(Name + Address)
      |
      v
Candidate Generation / Blocking
      |
      v
Candidate Pairs
      |
      v
Similarity & Matching Features
      |
      v
ML Matching Model
      |
      v
Probability / Match Score
      |
      v
F0.5-based Threshold Selection
      |
      v
Multiple-Match + Singleton Handling
      |
      v
Final Test Predictions
      |
      +-------------------------+
      |                         |
      v                         v
matching_results.tsv      candidate_pairs.tsv
```

------------------------------------------------------------------------

# 4. Phase 1 --- Data Understanding

Before expensive processing, inspect:

-   row counts
-   column structure
-   missing values
-   country distribution
-   number of true matches per Source 1 entity
-   examples of matching and non-matching records
-   duplicate and repeated patterns where useful

This phase will guide the blocking and feature-engineering strategy.

The current data structure contains:

``` text
entity_id
business_name
business_address
country
```

The Source 1, Source 2, and Source 3 files use the same four fields.

The ground-truth file contains:

``` text
source1_entity_id
matched_entity_ids
```

------------------------------------------------------------------------

# 5. Phase 2 --- Efficient Data Layer

Because the dataset contains millions of records, we will avoid
unnecessarily loading entire TSV files into pandas memory.

The planned approach is to evaluate:

-   DuckDB
-   Polars
-   Parquet
-   chunked processing

A likely workflow is:

``` text
Large TSV
   |
   v
One-time efficient conversion / processing
   |
   v
Parquet or queryable representation
   |
   v
Fast filtering and candidate generation
```

The exact choice will be finalized after measuring the dataset and Colab
environment.

------------------------------------------------------------------------

# 6. Phase 3 --- Text Normalization

We will create normalized versions of the business name and address
while retaining the original values.

### Business-name normalization

Potential operations:

-   Unicode normalization
-   lowercase normalization where appropriate
-   whitespace normalization
-   punctuation normalization
-   common abbreviation normalization
-   legal-suffix normalization
-   `&` / `and` normalization
-   tokenization

Example:

``` text
"Sharma Electronics Pvt. Ltd."
        |
        v
"sharma electronics pvt ltd"
```

### Address normalization

Potential operations:

-   Unicode normalization
-   case normalization
-   punctuation normalization
-   whitespace normalization
-   common address abbreviation normalization
-   tokenization
-   preservation/extraction of useful address components

Example:

``` text
"12, M.G. Road, Mumbai"
        |
        v
"12 mg road mumbai"
```

### Important multilingual consideration

The sample data already contains business names using non-Latin scripts.

Therefore, normalization must be **Unicode-safe** and must not simply
remove all non-English characters.

------------------------------------------------------------------------

# 7. Phase 4 --- Candidate Generation / Blocking

This is the most important scalability component.

We will NOT compare every Source 1 record against every Source 2/Source
3 record.

Instead, multiple blocking strategies will generate plausible
candidates.

Potential blocking signals include:

### Block A --- Exact normalized business name

Use normalized business names to retrieve records with the same
normalized representation.

### Block B --- Strong name tokens

Use informative business-name tokens to retrieve likely candidates
despite formatting differences.

### Block C --- Address signals

Potential signals:

-   postal/PIN code where available
-   city
-   street number
-   strong address tokens

### Block D --- Character n-grams

Useful for spelling variation and minor corruption.

Example:

``` text
electronics
electornics
```

### Block E --- Country

Country can be used as a supporting signal/blocking feature, while
treating country as an open set rather than assuming only the training
countries.

### Candidate union

Candidates from multiple blocking methods will be combined:

``` text
Name candidates
      +
Address candidates
      +
Character/token candidates
      +
Other safe blocking candidates
      |
      v
Deduplicated candidate set
```

The goal is to keep the candidate set small while retaining true
matches.

------------------------------------------------------------------------

# 8. Phase 5 --- Matching Feature Engineering

For every candidate pair:

``` text
Source 1 <-> Source 2
Source 1 <-> Source 3
```

we will compute features.

### Name features

Potential features:

-   exact normalized-name match
-   edit similarity
-   Levenshtein-based similarity
-   token similarity
-   Jaccard similarity
-   TF-IDF cosine similarity
-   character n-gram similarity
-   token overlap
-   length differences

### Address features

Potential features:

-   exact normalized-address match
-   edit similarity
-   token similarity
-   Jaccard similarity
-   TF-IDF cosine similarity
-   character n-gram similarity
-   number overlap
-   postal/PIN overlap
-   address-token overlap

### Other features

Potential features:

-   country equality
-   missing-field indicators
-   name/address length differences
-   combined name + address signals

Features will be selected and validated based on actual training
performance rather than automatically including everything.

------------------------------------------------------------------------

# 9. Phase 6 --- ML Matching Model

The candidate-pair features will be used to train a binary matching
model:

``` text
1 = same real-world business
0 = different business
```

A gradient-boosted tabular model such as:

-   LightGBM
-   XGBoost
-   another suitable compatible model

will be evaluated.

The model should learn how combinations of name, address, country, and
other similarity features indicate a genuine entity match.

Example:

``` text
Name similarity      = 0.94
Address similarity   = 0.87
Country match        = 1
Token overlap        = 0.82

                |
                v

P(same business) = high
```

The final model choice will be based on validation results and
computational practicality.

------------------------------------------------------------------------

# 10. Phase 7 --- Validation

A validation strategy will be created from the training data.

The model will be evaluated using the challenge's actual metric:

**F0.5**

The validation process will measure:

-   precision
-   recall
-   F0.5
-   false merges
-   missed matches
-   singleton performance

We will not optimize for ordinary accuracy alone.

------------------------------------------------------------------------

# 11. Phase 8 --- Match Threshold Optimization

The model will produce a match score/probability.

We will evaluate multiple thresholds on validation data.

Example:

``` text
Threshold    F0.5
0.50         ...
0.60         ...
0.70         ...
0.80         ...
0.90         ...
```

The threshold will be selected based on validation performance.

Because F0.5 is precision-heavy, the system will be conservative about
uncertain matches.

------------------------------------------------------------------------

# 12. Phase 9 --- Multiple Matches and Singletons

The model must support the actual challenge structure.

A Source 1 entity can have:

``` text
0 matches
1 match
multiple matches
```

Therefore, the pipeline will NOT simply select one best candidate.

Instead:

``` text
S1
 |
 +--> candidate S2 A -> score
 +--> candidate S2 B -> score
 +--> candidate S3 A -> score
 +--> candidate S3 B -> score
 |
 v
keep sufficiently confident matches
```

### Singleton handling

If no candidate is sufficiently confident, the output should contain an
empty match list.

This is important because incorrectly assigning a match to a true
singleton is penalized by the evaluation.

------------------------------------------------------------------------

# 13. Phase 10 --- Test Inference

Once the pipeline is finalized and validated:

``` text
Test Source 1
      |
      v
Normalization
      |
      v
Blocking against Test Source 2 + Source 3
      |
      v
Candidate pairs
      |
      v
Feature generation
      |
      v
Trained matching model
      |
      v
Optimized threshold
      |
      v
Final matches
```

Every Source 1 test entity must receive exactly one output row.

------------------------------------------------------------------------

# 14. Required Output

## matching_results.tsv

Required structure:

``` text
source1_entity_id    matched_entity_ids
```

Example:

``` text
S1-00001    S2-00047,S2-00193,S3-00812
S1-00002    S3-00004
S1-00003
```

Requirements include:

-   every Source 1 test entity appears exactly once
-   matched IDs come only from Source 2/Source 3
-   no duplicate IDs within a list
-   empty list for no-match entities

## candidate_pairs.tsv

Required structure:

``` text
source1_entity_id    candidate_entity_ids
```

This must represent the final candidate set actually passed into the
matching model.

Every final match must be present in this candidate set.

------------------------------------------------------------------------

# 15. Validation Before Submission

The challenge provides:

``` text
utils/validate_submission.py
```

We will run the validator before submission to catch structural errors.

The validation command is:

``` bash
python3 utils/validate_submission.py \
    --matching output/matching_results.tsv \
    --candidate output/candidate_pairs.tsv \
    --test-dir dataset/test
```

------------------------------------------------------------------------

# 16. Submission Package

Final package:

``` text
<team_name>_submission.zip
|
+-- output/
|   +-- matching_results.tsv
|   +-- candidate_pairs.tsv
|
+-- code/
|   +-- business_entity_resolution/
|       +-- src/
|       +-- README.md
|       +-- requirements.txt
|
+-- Documentation_template.md
```

The pipeline should be reproducible from the submitted code and data
inputs.

------------------------------------------------------------------------

# 17. Competition Compliance / Fair Play

The solution will use **only the provided challenge data and permitted
local computation**.

We will NOT use:

-   commercial entity-resolution APIs
-   government business-registration databases
-   geocoding APIs
-   Google Maps/business lookup
-   external business databases
-   internet-based business identity resolution
-   external data augmentation

The challenge explicitly prohibits external data lookup and
augmentation.

All entity matching will be learned or inferred from the supplied
training/test data and our locally computed features.

We will also respect the challenge's model licensing and parameter
constraints when selecting the final model.

------------------------------------------------------------------------

# 18. Current Status

Completed:

-   [x] Uploaded dataset to Google Drive
-   [x] Connected Google Drive to Colab
-   [x] Verified dataset paths
-   [x] Verified TSV structure
-   [x] Inspected sample records
-   [x] Counted all dataset rows
-   [x] Confirmed dataset scale

Current next step:

-   [ ] Analyze ground-truth match-count distribution
-   [ ] Analyze missing values
-   [ ] Analyze country distribution
-   [ ] Inspect matching patterns
-   [ ] Finalize blocking architecture

------------------------------------------------------------------------

# 19. Guiding Principle

The main objective is not to build the largest or most complicated
model.

The objective is to build a pipeline that is:

``` text
Fast
+
Memory-efficient
+
High-precision
+
High candidate recall
+
Scalable to millions of records
+
Reproducible
+
Competition-compliant
```

The central optimization is:

> **Reduce millions of possible comparisons to a small, high-quality
> candidate set before applying expensive matching features and the ML
> model.**
