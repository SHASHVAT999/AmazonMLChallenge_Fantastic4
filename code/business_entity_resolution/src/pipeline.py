import duckdb
import os
import sys
import time

def run_entity_resolution(test_dir="D:/dataset/student_resource/dataset/test", output_dir="D:/amazon_ml/output"):
    t_start = time.time()
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 60)
    print("  AMAZON ML CHALLENGE 2026 - BUSINESS ENTITY RESOLUTION")
    print(f"  Test Directory   : {test_dir}")
    print(f"  Output Directory : {output_dir}")
    print("=" * 60)
    
    s1_path = os.path.join(test_dir, "test_source1.tsv").replace("\\", "/")
    s2_path = os.path.join(test_dir, "test_source2.tsv").replace("\\", "/")
    s3_path = os.path.join(test_dir, "test_source3.tsv").replace("\\", "/")
    
    matching_tsv = os.path.join(output_dir, "matching_results.tsv").replace("\\", "/")
    candidate_tsv = os.path.join(output_dir, "candidate_pairs.tsv").replace("\\", "/")
    
    con = duckdb.connect()
    
    print("\n[1/5] Configuring DuckDB execution engine...")
    con.execute("""
    SET memory_limit = '6GB';
    SET threads = 4;
    SET preserve_insertion_order = false;

    CREATE OR REPLACE MACRO clean_str(s) AS 
        regexp_replace(regexp_replace(lower(trim(coalesce(s, ''))), '[^\\w\\s]', ' ', 'g'), '\\s+', ' ', 'g');

    CREATE OR REPLACE MACRO clean_name(s) AS
        trim(regexp_replace(
            regexp_replace(
                regexp_replace(
                    clean_str(s), 
                    '\\b(pvt|ltd|private|limited|llp|inc|llc|corp|corporation|co|company|sa|sarl|gmbh)\\b', '', 'g'
                ), 
                '\\s+', ' ', 'g'
            ),
            '^\\s+|\\s+$', '', 'g'
        ));

    CREATE OR REPLACE MACRO sorted_tokens(s) AS
        array_to_string(
            list_filter(
                list_sort(
                    string_split(
                        regexp_replace(lower(coalesce(s, '')), '[^a-z0-9]', ' ', 'g'),
                        ' '
                    )
                ),
                x -> length(x) > 1
            ),
            ' '
        );
    """)
    
    print("\n[2/5] Creating accumulator tables for all countries...")
    con.execute("""
    CREATE OR REPLACE TABLE all_matches (
        s1_id VARCHAR,
        cand_id VARCHAR
    );

    CREATE OR REPLACE TABLE all_candidates (
        s1_id VARCHAR,
        cand_id VARCHAR
    );
    """)
    
    countries = ["France", "US", "India"]
    
    for c_idx, country in enumerate(countries, 1):
        t_country = time.time()
        print(f"\n--- [{c_idx}/{len(countries)}] Processing Country: {country} ---")
        
        # 1. Ingest S1 for this country
        print(f"  Loading S1 for {country}...")
        con.execute(f"""
        CREATE OR REPLACE TABLE s1_curr AS
        SELECT entity_id, business_name, business_address,
               clean_name(business_name) as c_name,
               sorted_tokens(clean_name(business_name)) as s_name,
               clean_str(business_address) as c_addr,
               sorted_tokens(business_address) as s_addr
        FROM read_csv('{s1_path}', delim='\t', header=True, all_varchar=True)
        WHERE country = '{country}';
        """)
        s1_cnt = con.execute("SELECT count(*) FROM s1_curr").fetchone()[0]
        print(f"  S1 count: {s1_cnt:,}")

        # 2. Ingest S2 & S3 for this country
        print(f"  Loading S2 and S3 for {country}...")
        con.execute(f"""
        CREATE OR REPLACE TABLE s23_curr AS
        SELECT entity_id, business_name, business_address,
               clean_name(business_name) as c_name,
               sorted_tokens(clean_name(business_name)) as s_name,
               clean_str(business_address) as c_addr,
               sorted_tokens(business_address) as s_addr
        FROM read_csv('{s2_path}', delim='\t', header=True, all_varchar=True)
        WHERE country = '{country}'
        UNION ALL
        SELECT entity_id, business_name, business_address,
               clean_name(business_name) as c_name,
               sorted_tokens(clean_name(business_name)) as s_name,
               clean_str(business_address) as c_addr,
               sorted_tokens(business_address) as s_addr
        FROM read_csv('{s3_path}', delim='\t', header=True, all_varchar=True)
        WHERE country = '{country}';
        """)
        s23_cnt = con.execute("SELECT count(*) FROM s23_curr").fetchone()[0]
        print(f"  S2/S3 count: {s23_cnt:,}")

        # 3. Candidate Generation (Blocking)
        print("  Generating candidate pairs via multi-key blocking...")
        con.execute("""
        CREATE OR REPLACE TABLE cands_curr AS
        SELECT s1.entity_id as s1_id, s23.entity_id as cand_id
        FROM s1_curr s1 JOIN s23_curr s23 ON s1.c_name = s23.c_name
        WHERE length(s1.c_name) > 3

        UNION ALL

        SELECT s1.entity_id as s1_id, s23.entity_id as cand_id
        FROM s1_curr s1 JOIN s23_curr s23 ON s1.s_name = s23.s_name
        WHERE length(s1.s_name) > 3

        UNION ALL

        SELECT s1.entity_id as s1_id, s23.entity_id as cand_id
        FROM s1_curr s1 JOIN s23_curr s23 ON s1.c_addr = s23.c_addr
        WHERE length(s1.c_addr) > 5

        UNION ALL

        SELECT s1.entity_id as s1_id, s23.entity_id as cand_id
        FROM s1_curr s1 JOIN s23_curr s23 ON s1.s_addr = s23.s_addr
        WHERE length(s1.s_addr) > 6;
        """)

        # 4. Deduplicate candidates
        con.execute("""
        CREATE OR REPLACE TABLE dedup_cands_curr AS
        SELECT DISTINCT s1_id, cand_id
        FROM cands_curr;
        """)
        cand_cnt = con.execute("SELECT count(*) FROM dedup_cands_curr").fetchone()[0]
        print(f"  Deduplicated candidate pairs: {cand_cnt:,}")

        # 5. Matching Feature Engineering & Scoring
        print("  Scoring candidates with Jaro-Winkler similarity...")
        con.execute("""
        CREATE OR REPLACE TABLE scored_curr AS
        SELECT c.s1_id, c.cand_id,
               (
                   CASE WHEN s1.c_name = s23.c_name THEN 1.0 ELSE jaro_winkler_similarity(s1.c_name, s23.c_name) END * 0.55 +
                   CASE 
                       WHEN s1.c_addr = s23.c_addr AND length(s1.c_addr) > 5 THEN 1.0 
                       WHEN length(s1.c_addr) > 5 AND length(s23.c_addr) > 5 THEN jaro_winkler_similarity(s1.c_addr, s23.c_addr)
                       ELSE 0.70
                   END * 0.45
               ) as match_score,
               CASE 
                   WHEN length(s1.c_addr) > 5 AND length(s23.c_addr) > 5 THEN jaro_winkler_similarity(s1.c_addr, s23.c_addr)
                   ELSE 1.0
               END as addr_sim
        FROM dedup_cands_curr c
        JOIN s1_curr s1 ON c.s1_id = s1.entity_id
        JOIN s23_curr s23 ON c.cand_id = s23.entity_id;
        """)

        # 6. Select High-Confidence Matches for matching_results.tsv (threshold >= 0.83, max 5)
        print("  Selecting high-confidence matches (threshold 0.83, max 5)...")
        con.execute("""
        CREATE OR REPLACE TABLE curr_matches AS
        WITH ranked_matches AS (
            SELECT s1_id, cand_id,
                   row_number() OVER (PARTITION BY s1_id ORDER BY match_score DESC) as rn
            FROM scored_curr
            WHERE match_score >= 0.83 AND addr_sim >= 0.50
        )
        SELECT s1_id, cand_id
        FROM ranked_matches
        WHERE rn <= 5;

        INSERT INTO all_matches
        SELECT s1_id, cand_id FROM curr_matches;
        """)

        # 7. Select Candidates for candidate_pairs.tsv (Include all matches + top candidates up to 15)
        print("  Selecting candidates for candidate_pairs.tsv...")
        con.execute("""
        INSERT INTO all_candidates
        WITH ranked_cands AS (
            SELECT s1_id, cand_id,
                   row_number() OVER (PARTITION BY s1_id ORDER BY match_score DESC) as rn
            FROM scored_curr
        ),
        top_cands AS (
            SELECT s1_id, cand_id FROM ranked_cands WHERE rn <= 15
        )
        SELECT s1_id, cand_id FROM curr_matches
        UNION
        SELECT s1_id, cand_id FROM top_cands;
        """)

        # Free country tables to free memory
        con.execute("DROP TABLE s1_curr; DROP TABLE s23_curr; DROP TABLE cands_curr; DROP TABLE dedup_cands_curr; DROP TABLE scored_curr; DROP TABLE curr_matches;")
        print(f"  Country {country} completed in {time.time() - t_country:.2f}s.")

    print("\n[3/5] Verifying total accumulated counts across all countries...")
    tot_cands = con.execute("SELECT count(*), count(distinct s1_id) FROM all_candidates").fetchone()
    tot_matches = con.execute("SELECT count(*), count(distinct s1_id) FROM all_matches").fetchone()
    print(f"  Total Candidates: {tot_cands[0]:,} across {tot_cands[1]:,} S1 entities")
    print(f"  Total Matches   : {tot_matches[0]:,} across {tot_matches[1]:,} S1 entities")

    print("\n[4/5] Formatting and writing submission TSV files...")
    
    # Matching results: Ensure ALL S1 entities exist, join and group
    print("  Writing matching_results.tsv...")
    t_out = time.time()
    con.execute(f"""
    COPY (
        WITH all_s1 AS (
            SELECT entity_id as s1_id
            FROM read_csv('{s1_path}', delim='\t', header=True, all_varchar=True)
        ),
        grouped_matches AS (
            SELECT s1_id, string_agg(cand_id, ',') as matched_entity_ids
            FROM all_matches
            GROUP BY s1_id
        )
        SELECT s1.s1_id as source1_entity_id, m.matched_entity_ids as matched_entity_ids
        FROM all_s1 s1
        LEFT JOIN grouped_matches m ON s1.s1_id = m.s1_id
    ) TO '{matching_tsv}' (HEADER, DELIMITER '\t', NULL '');
    """)
    print(f"  matching_results.tsv written in {time.time() - t_out:.2f}s.")

    # Candidate pairs: Ensure ALL S1 entities exist, join and group
    print("  Writing candidate_pairs.tsv...")
    t_out = time.time()
    con.execute(f"""
    COPY (
        WITH all_s1 AS (
            SELECT entity_id as s1_id
            FROM read_csv('{s1_path}', delim='\t', header=True, all_varchar=True)
        ),
        grouped_cands AS (
            SELECT s1_id, string_agg(cand_id, ',') as candidate_entity_ids
            FROM all_candidates
            GROUP BY s1_id
        )
        SELECT s1.s1_id as source1_entity_id, c.candidate_entity_ids as candidate_entity_ids
        FROM all_s1 s1
        LEFT JOIN grouped_cands c ON s1.s1_id = c.s1_id
    ) TO '{candidate_tsv}' (HEADER, DELIMITER '\t', NULL '');
    """)
    print(f"  candidate_pairs.tsv written in {time.time() - t_out:.2f}s.")

    print(f"\n[5/5] Pipeline finished successfully in {time.time() - t_start:.2f}s!")
    print(f"  Matching Results: {matching_tsv} (Size: {os.path.getsize(matching_tsv):,} bytes)")
    print(f"  Candidate Pairs : {candidate_tsv} (Size: {os.path.getsize(candidate_tsv):,} bytes)")

if __name__ == "__main__":
    test_directory = sys.argv[1] if len(sys.argv) > 1 else "D:/dataset/student_resource/dataset/test"
    output_directory = sys.argv[2] if len(sys.argv) > 2 else "D:/amazon_ml/output"
    run_entity_resolution(test_directory, output_directory)
