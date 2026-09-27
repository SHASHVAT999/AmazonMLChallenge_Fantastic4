# Amazon ML Challenge 2026 - Business Entity Resolution Pipeline

Team: **Fantastic4**

## Overview
This package contains the complete, reproducible end-to-end Business Entity Resolution pipeline that generates:
1. `output/matching_results.tsv` (Leaderboard submission: final matched entities)
2. `output/candidate_pairs.tsv` (Blocking candidate set evaluated by matching model)

## Pipeline Architecture
1. **Unicode-safe Normalization:**
   - Legal entity suffix removal (Pvt Ltd, LLC, Inc, Corp, SARL, SA, etc.)
   - Alphanumeric text cleaning and token extraction
   - Token-sorted canonization for word order invariance
2. **Multi-Key Blocking (Candidate Generation):**
   - Exact Clean Name join
   - Token-sorted Name join
   - Clean Full Address join
   - Token-sorted Address join
   - Strict country-level isolation (US, India, France partitioned independently)
3. **Matching Feature Engineering & Scoring:**
   - Jaro-Winkler string similarity on normalized business names
   - Jaro-Winkler string similarity on normalized business addresses
   - Weighted composite similarity score: `0.55 * Name_Sim + 0.45 * Addr_Sim`
4. **Decision Boundary & Singleton Handling:**
   - Calibrated precision-oriented threshold (`Score >= 0.83`, `Addr_Sim >= 0.50`)
   - Max-k matching cap (top 5 matches) reflecting real-world match distribution
   - Singletons preserved with empty match list (F0.5 macro evaluation award)

## Setup & Requirements
```bash
pip install -r requirements.txt
```

## Running the Pipeline
To execute the pipeline from the workspace root:
```bash
python code/business_entity_resolution/src/pipeline.py <path_to_test_dataset> <path_to_output_dir>
```

Example:
```bash
python code/business_entity_resolution/src/pipeline.py dataset/test output
```

## Validating Outputs
To validate that the produced files adhere to all competition rules:
```bash
python utils/validate_submission.py \
    --matching output/matching_results.tsv \
    --candidate output/candidate_pairs.tsv \
    --test-dir dataset/test
```
