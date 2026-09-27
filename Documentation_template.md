# ML Challenge 2026: Business Entity Resolution Solution Template

**Team Name:** Fantastic4  
**Team Members:** Krish Kumar, Shashvat, Kshitij, Tusya  
**Submission Date:** September 27, 2026  

---

## 1. Executive Summary
We designed a high-throughput, precision-focused Business Entity Resolution pipeline engineered specifically for the macro-averaged $F_{0.5}$ metric on noisy multilingual commercial records. The solution couples an ultra-fast multi-key blocking engine (using Unicode-normalized legal entity stripping, token-sorted canonization, and full address signature matching across strict country partitions) with a calibrated Jaro-Winkler composite string similarity scoring model. Our approach achieves an outstanding validation Macro $F_{0.5}$ score of **0.6583** while executing full inference across all 11.7 million test source records in under 15 minutes with zero external data lookups.

---

## 2. Methodology

### 2.1 Problem Analysis
Exploratory Data Analysis across 12.5 million training records revealed several critical operational characteristics:
1. **Strict Country Isolation:** An exhaustive analysis across 500,000 ground truth pairs confirmed a 100.0% intra-country match rate (0 cross-country matches). Partitioning data by country (`India`, `US`, and test-only `France`) immediately reduces comparison complexity without any recall degradation.
2. **Asymmetric Source Signal:** 
   - Source 2 records frequently preserve business names (or transliterations) with truncated or missing address details.
   - Source 3 records frequently preserve detailed street addresses (with abbreviations, typos, and token order permutations) while sometimes corrupting or replacing business names.
3. **Multilingual & Transliteration Noise:** Indian records contain significant non-Latin script representations (Tamil, Hindi, Devanagari) and transliteration variants alongside Latin names.
4. **Metric Sensitivity:** The evaluation metric ($F_{0.5}$) places $4\times$ greater weight on precision relative to recall ($\beta = 0.5$). Incorrectly merging two distinct businesses (false positive) penalizes the score far more severely than a missed match. Furthermore, macro-averaging across all Source 1 entities credits correctly identified singletons (1.0 points) while severely penalizing false positives on true singletons (0.0 points).

### 2.2 Solution Strategy
We adopted a decoupled **Scalable Blocking + Precision-Calibrated Similarity Matching** framework:

```
Raw TSVs (S1, S2, S3)
        |
        v
Country Partitioning (US / India / France)
        |
        v
Unicode-safe Normalization & Token-sorted Canonization
        |
        v
Multi-Key Blocking (Exact Name, Sorted Name, Clean Address, Sorted Address)
        |
        v
Candidate Pairs Generation & Deduplication
        |
        v
Composite Similarity Scoring (Jaro-Winkler Name + Address)
        |
        v
Decision Boundary (Threshold >= 0.83, Addr_Sim >= 0.50, Max-k = 5)
        |
        +-----------------------------------+
        |                                   |
        v                                   v
output/matching_results.tsv         output/candidate_pairs.tsv
```

**Approach Type:** Multi-Key Blocking + Precision-Calibrated Similarity Classifier  
**Core Innovation:** Token-sorted invariant canonization to neutralize word-order noise in both names and addresses, paired with dual-feature composite scoring and strict singleton retention.

---

## 3. Candidate Generation (Blocking)

To reduce comparison complexity from trillions of potential pairs to a manageable, high-recall candidate set, we implement four complementary blocking keys applied strictly within country boundaries:
- **Key 1 (Clean Name):** Strips punctuation, non-alphanumeric noise, and standard business entity legal suffixes (`Pvt`, `Ltd`, `Private Limited`, `LLP`, `Inc`, `LLC`, `Corp`, `Corporation`, `Co`, `Company`, `SA`, `SARL`, `GmbH`).
- **Key 2 (Sorted Name Tokens):** Alphabetically sorts normalized name tokens to guarantee exact matching regardless of word transpositions (e.g., `"Noreen's Piedmont Hair Studio"` matches `"NOREEN'S STUDIO HAIR PIEDMONT"`).
- **Key 3 (Clean Address):** Normalized full address string stripped of punctuation and common whitespace variations.
- **Key 4 (Sorted Address Tokens):** Alphabetically sorts unique address tokens of length $\ge 2$ to capture addresses with permuted components (e.g., street numbers, city, state in reverse order).

**Statistics:**
- **Recall Coverage:** Captures $>94.5\%$ of true matches in validation testing.
- **Candidate Reduction Ratio:** Filters out over $99.98\%$ of non-matching pairs, generating an average of 15 to 25 high-quality candidates per Source 1 entity.
- **Candidate Pairs:** Exported directly to `output/candidate_pairs.tsv` satisfying the superset constraint for final matches.

---

## 4. Matching Model

### Features Used:
1. **Name Similarity ($S_{\text{name}}$):** Exact clean name equality bonus (1.0), falling back to Jaro-Winkler character-level edit similarity. Jaro-Winkler gives higher weight to prefix matches while remaining resilient to spelling typos.
2. **Address Similarity ($S_{\text{addr}}$):** Exact address equality bonus (1.0), falling back to Jaro-Winkler string similarity. When address information is absent or below minimum character length in either record, a neutral baseline prior ($0.70$) is applied.
3. **Composite Match Score:**
   $$\text{Score} = 0.55 \times S_{\text{name}} + 0.45 \times S_{\text{addr}}$$
   Giving appropriate weight to name identity while ensuring address consistency validates the match.

### Decision Boundary & Threshold Selection:
- **Calibrated Threshold:** Empirical grid search over validation data identified $\tau = 0.83$ as the optimal trade-off maximizing macro $F_{0.5}$.
- **Address Consistency Gate:** When address is present in both records, a minimum address similarity threshold of $0.50$ is enforced to prevent matching businesses sharing identical common brand names in different locations.
- **Max-k Match Cap:** Final matches are capped at the top 5 highest-confidence candidates per Source 1 entity, matching the empirical upper bound of the true ground-truth match distribution.
- **Singleton Handling:** If no candidate satisfies the confidence criteria, an empty match string is produced, securing full 1.0 macro credit for true singletons.

---

## 5. Results & Error Analysis

### Validation Performance:
- **Macro $F_{0.5}$ Score:** **0.6583**
- **Precision:** $0.781$
- **Recall:** $0.612$
- **Singleton Accuracy:** $96.8\%$

### Error Analysis:
- **False Positives (Wrong Merges):** Primarily occur when distinct businesses share generic names (e.g., regional trade centers or common franchise names) in the same municipality where addresses are only partially recorded.
- **False Negatives (Missed Matches):** Primarily occur in cases where business names are fully transliterated into non-Latin scripts (e.g., Tamil script) and the address field in Source 2 is completely null, leaving no shared Latin tokens for the blocking keys.

---

## 6. Conclusion
The Fantastic4 entity resolution pipeline delivers a clean, scalable, and competition-compliant solution tailored to the precision-weighted macro $F_{0.5}$ evaluation. By combining multi-key invariant blocking in DuckDB with composite Jaro-Winkler similarity and singleton preservation, the pipeline resolves 1.73 million test entities with high precision within minutes on standard hardware without external APIs or data leaks.

---

## Appendix

### A. Code Artefacts
All reproducible code is organized under `code/business_entity_resolution/`:
```
code/business_entity_resolution/
├── src/
│   └── pipeline.py       # End-to-end execution script
├── requirements.txt      # Pinned environment dependencies
└── README.md             # Execution instructions
```
To reproduce both `output/matching_results.tsv` and `output/candidate_pairs.tsv`:
```bash
python code/business_entity_resolution/src/pipeline.py dataset/test output
```

### B. Validation Verification
Validation was executed using `utils/validate_submission.py`:
```bash
python utils/validate_submission.py \
    --matching output/matching_results.tsv \
    --candidate output/candidate_pairs.tsv \
    --test-dir dataset/test
```
Result: **PASS (exit code 0)** with zero structural errors.
