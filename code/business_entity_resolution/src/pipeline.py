import duckdb
import os
import sys
import time

def run_entity_resolution(test_dir="D:/dataset/student_resource/dataset/test", output_dir="D:/amazon_ml/output"):
    t_start = time.time()
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 70)
    print("  AMAZON ML CHALLENGE 2026 - HIGH-PERFORMANCE ENTITY RESOLUTION")
    print(f"  Test Directory   : {test_dir}")
    print(f"  Output Directory : {output_dir}")
    print("=" * 70)
    
    s1_path = os.path.join(test_dir, "test_source1.tsv").replace("\\", "/")
    s2_path = os.path.join(test_dir, "test_source2.tsv").replace("\\", "/")
    s3_path = os.path.join(test_dir, "test_source3.tsv").replace("\\", "/")
    
    matching_tsv = os.path.join(output_dir, "matching_results.tsv").replace("\\", "/")
    candidate_tsv = os.path.join(output_dir, "candidate_pairs.tsv").replace("\\", "/")
    
    con = duckdb.connect()
    
    print("\n[1/5] Configuring DuckDB execution engine and string normalization macros...")
    con.execute("""
    SET memory_limit = '6GB';
    SET threads = 4;
    SET preserve_insertion_order = false;

    CREATE OR REPLACE MACRO clean_str(s) AS 
        regexp_replace(regexp_replace(lower(trim(coalesce(s, ''))), '[^\\w\\s]', ' ', 'g'), '\\s+', ' ', 'g');

    -- Deep corporate & legal cleaner: strips metadata in parentheses, salutations, and generic entity tokens
    CREATE OR REPLACE MACRO clean_name(s) AS
        trim(regexp_replace(
            regexp_replace(
                regexp_replace(
                    clean_str(regexp_replace(coalesce(s, ''), '\\([^)]*\\)', ' ', 'g')),
                    '\\b(smt|shri|sh|sri|ms|m\\s*s|dr|mr|mrs|the)\\b', '', 'g'
                ),
                '\\b(pvt|ltd|private|limited|llp|inc|incorporated|llc|corp|corporation|co|company|sa|sarl|sas|sasu|eurl|sci|snc|gmbh|societe|pllc|lp|pa|pc|center|centre|services|service|group|holdings|holding|enterprises|enterprise|association|industries|industry|solutions|solution|technologies|technology|tech|international|global|consultants|consultant|consultancy|associates|associate|partners|partner|trading|brothers)\\b', '', 'g'
            ),
            '\\s+', ' ', 'g'
        ));

    -- Deduplicated and sorted tokens of clean name
    CREATE OR REPLACE MACRO sorted_dedup_name(s) AS
        array_to_string(
            list_filter(
                list_distinct(
                    list_sort(
                        string_split(clean_name(s), ' ')
                    )
                ),
                x -> length(x) > 1
            ),
            ' '
        );

    -- Compact name (alphanumeric only, no domains)
    CREATE OR REPLACE MACRO compact_name(s) AS
        regexp_replace(regexp_replace(lower(coalesce(s, '')), '\\.(com|in|org|net|co|io|fr)\\b', '', 'g'), '[^a-z0-9]', '', 'g');

    -- Address cleaner stripping address prefixes: HN 123, DOOR NO, ##12, PLOT 123, FLAT NO, etc.
    CREATE OR REPLACE MACRO clean_addr_noprefix(s) AS
        trim(regexp_replace(
            regexp_replace(
                clean_str(s),
                '^(hn\\s*\\d+|door\\s*no\\s*\\d*|plot\\s*no\\s*\\d*|plot\\s*\\d+|room\\s*no\\s*\\d*|cabin\\s*no\\s*\\d*|flat\\s*no\\s*\\d*|shop\\s*no\\s*\\d*|#+\\s*\\d+)\\s*',
                '', 'g'
            ),
            '\\s+', ' ', 'g'
        ));

    -- Sorted tokens of address
    CREATE OR REPLACE MACRO sorted_addr(s) AS
        array_to_string(
            list_filter(
                list_distinct(
                    list_sort(
                        string_split(clean_addr_noprefix(s), ' ')
                    )
                ),
                x -> length(x) > 1
            ),
            ' '
        );

    -- First three tokens of cleaned address without prefix
    CREATE OR REPLACE MACRO addr_3tok(s) AS
        array_to_string(list_slice(string_split(clean_addr_noprefix(s), ' '), 1, 3), ' ');

    -- 2-token prefix of sorted name
    CREATE OR REPLACE MACRO name_2tok(s) AS
        array_to_string(list_slice(string_split(sorted_dedup_name(s), ' '), 1, 2), ' ');

    -- Street number + last word (city/state)
    CREATE OR REPLACE MACRO num_city(s) AS
        concat(
            coalesce(nullif(regexp_extract(clean_str(s), '\\b([0-9]{2,6})\\b', 1), ''), '0'),
            '_',
            coalesce(nullif(regexp_extract(clean_str(s), '([a-z]{4,})$', 1), ''), 'none')
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
               sorted_dedup_name(business_name) as s_name,
               compact_name(business_name) as cp_name,
               name_2tok(business_name) as n_2tok,
               clean_addr_noprefix(business_address) as c_addr,
               sorted_addr(business_address) as s_addr,
               addr_3tok(business_address) as a_3tok,
               num_city(business_address) as n_city
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
               sorted_dedup_name(business_name) as s_name,
               compact_name(business_name) as cp_name,
               name_2tok(business_name) as n_2tok,
               clean_addr_noprefix(business_address) as c_addr,
               sorted_addr(business_address) as s_addr,
               addr_3tok(business_address) as a_3tok,
               num_city(business_address) as n_city,
               regexp_matches(business_name, '[^\\x00-\\x7F]') as is_transliterated
        FROM read_csv('{s2_path}', delim='\t', header=True, all_varchar=True)
        WHERE country = '{country}'
        UNION ALL
        SELECT entity_id, business_name, business_address,
               clean_name(business_name) as c_name,
               sorted_dedup_name(business_name) as s_name,
               compact_name(business_name) as cp_name,
               name_2tok(business_name) as n_2tok,
               clean_addr_noprefix(business_address) as c_addr,
               sorted_addr(business_address) as s_addr,
               addr_3tok(business_address) as a_3tok,
               num_city(business_address) as n_city,
               regexp_matches(business_name, '[^\\x00-\\x7F]') as is_transliterated
        FROM read_csv('{s3_path}', delim='\t', header=True, all_varchar=True)
        WHERE country = '{country}';
        """)
        s23_cnt = con.execute("SELECT count(*) FROM s23_curr").fetchone()[0]
        print(f"  S2/S3 count: {s23_cnt:,}")

        # 3. Candidate Generation (8-Channel Blocking Union)
        print("  Generating candidate pairs via high-recall 8-channel blocking...")
        con.execute("""
        CREATE OR REPLACE TABLE cands_curr AS
        -- Channel 1: Clean Name
        SELECT s1.entity_id as s1_id, s23.entity_id as cand_id,
               s1.c_name as s1_cname, s23.c_name as t_cname,
               s1.s_name as s1_sname, s23.s_name as t_sname,
               s1.cp_name as s1_cpname, s23.cp_name as t_cpname,
               s1.c_addr as s1_caddr, s23.c_addr as t_caddr,
               s1.s_addr as s1_saddr, s23.s_addr as t_saddr,
               s23.is_transliterated
        FROM s1_curr s1 JOIN s23_curr s23 ON s1.c_name = s23.c_name
        WHERE length(s1.c_name) > 3

        UNION ALL

        -- Channel 2: Sorted Dedup Name
        SELECT s1.entity_id as s1_id, s23.entity_id as cand_id,
               s1.c_name as s1_cname, s23.c_name as t_cname,
               s1.s_name as s1_sname, s23.s_name as t_sname,
               s1.cp_name as s1_cpname, s23.cp_name as t_cpname,
               s1.c_addr as s1_caddr, s23.c_addr as t_caddr,
               s1.s_addr as s1_saddr, s23.s_addr as t_saddr,
               s23.is_transliterated
        FROM s1_curr s1 JOIN s23_curr s23 ON s1.s_name = s23.s_name
        WHERE length(s1.s_name) > 3

        UNION ALL

        -- Channel 3: Compact Name (No Spaces / Domains)
        SELECT s1.entity_id as s1_id, s23.entity_id as cand_id,
               s1.c_name as s1_cname, s23.c_name as t_cname,
               s1.s_name as s1_sname, s23.s_name as t_sname,
               s1.cp_name as s1_cpname, s23.cp_name as t_cpname,
               s1.c_addr as s1_caddr, s23.c_addr as t_caddr,
               s1.s_addr as s1_saddr, s23.s_addr as t_saddr,
               s23.is_transliterated
        FROM s1_curr s1 JOIN s23_curr s23 ON s1.cp_name = s23.cp_name
        WHERE length(s1.cp_name) >= 6

        UNION ALL

        -- Channel 4: Clean Full Address (No Prefix)
        SELECT s1.entity_id as s1_id, s23.entity_id as cand_id,
               s1.c_name as s1_cname, s23.c_name as t_cname,
               s1.s_name as s1_sname, s23.s_name as t_sname,
               s1.cp_name as s1_cpname, s23.cp_name as t_cpname,
               s1.c_addr as s1_caddr, s23.c_addr as t_caddr,
               s1.s_addr as s1_saddr, s23.s_addr as t_saddr,
               s23.is_transliterated
        FROM s1_curr s1 JOIN s23_curr s23 ON s1.c_addr = s23.c_addr
        WHERE length(s1.c_addr) > 5

        UNION ALL

        -- Channel 5: Sorted Address Tokens
        SELECT s1.entity_id as s1_id, s23.entity_id as cand_id,
               s1.c_name as s1_cname, s23.c_name as t_cname,
               s1.s_name as s1_sname, s23.s_name as t_sname,
               s1.cp_name as s1_cpname, s23.cp_name as t_cpname,
               s1.c_addr as s1_caddr, s23.c_addr as t_caddr,
               s1.s_addr as s1_saddr, s23.s_addr as t_saddr,
               s23.is_transliterated
        FROM s1_curr s1 JOIN s23_curr s23 ON s1.s_addr = s23.s_addr
        WHERE length(s1.s_addr) > 6

        UNION ALL

        -- Channel 6: Address 3-Tokens (Frequency <= 200)
        SELECT s1.entity_id as s1_id, s23.entity_id as cand_id,
               s1.c_name as s1_cname, s23.c_name as t_cname,
               s1.s_name as s1_sname, s23.s_name as t_sname,
               s1.cp_name as s1_cpname, s23.cp_name as t_cpname,
               s1.c_addr as s1_caddr, s23.c_addr as t_caddr,
               s1.s_addr as s1_saddr, s23.s_addr as t_saddr,
               s23.is_transliterated
        FROM s1_curr s1 
        JOIN s23_curr s23 ON s1.a_3tok = s23.a_3tok
        JOIN (SELECT a_3tok FROM s23_curr GROUP BY a_3tok HAVING count(*) <= 200) af 
          ON s1.a_3tok = af.a_3tok
        WHERE length(s1.a_3tok) > 6

        UNION ALL

        -- Channel 7: 2-Token Name Prefix (Frequency <= 100)
        SELECT s1.entity_id as s1_id, s23.entity_id as cand_id,
               s1.c_name as s1_cname, s23.c_name as t_cname,
               s1.s_name as s1_sname, s23.s_name as t_sname,
               s1.cp_name as s1_cpname, s23.cp_name as t_cpname,
               s1.c_addr as s1_caddr, s23.c_addr as t_caddr,
               s1.s_addr as s1_saddr, s23.s_addr as t_saddr,
               s23.is_transliterated
        FROM s1_curr s1 
        JOIN s23_curr s23 ON s1.n_2tok = s23.n_2tok
        JOIN (SELECT n_2tok FROM s23_curr GROUP BY n_2tok HAVING count(*) <= 100) nf 
          ON s1.n_2tok = nf.n_2tok
        WHERE length(s1.n_2tok) > 5

        UNION ALL

        -- Channel 8: Number + City (Frequency <= 50)
        SELECT s1.entity_id as s1_id, s23.entity_id as cand_id,
               s1.c_name as s1_cname, s23.c_name as t_cname,
               s1.s_name as s1_sname, s23.s_name as t_sname,
               s1.cp_name as s1_cpname, s23.cp_name as t_cpname,
               s1.c_addr as s1_caddr, s23.c_addr as t_caddr,
               s1.s_addr as s1_saddr, s23.s_addr as t_saddr,
               s23.is_transliterated
        FROM s1_curr s1
        JOIN s23_curr s23 ON s1.n_city = s23.n_city
        JOIN (SELECT n_city FROM s23_curr WHERE n_city != '0_none' GROUP BY n_city HAVING count(*) <= 50) ncf
          ON s1.n_city = ncf.n_city
        WHERE s1.n_city != '0_none';
        """)

        # 4. Deduplicate candidates
        con.execute("""
        CREATE OR REPLACE TABLE dedup_cands_curr AS
        SELECT DISTINCT * FROM cands_curr;
        """)
        cand_cnt = con.execute("SELECT count(*) FROM dedup_cands_curr").fetchone()[0]
        print(f"  Deduplicated candidate pairs: {cand_cnt:,} ({cand_cnt/max(s1_cnt, 1):.1f} per S1)")

        # 5. Multi-Evidence Scoring & Transliteration Awareness
        print("  Scoring candidates with multi-evidence similarity & transliteration awareness...")
        con.execute("""
        CREATE OR REPLACE TABLE scored_curr AS
        SELECT s1_id, cand_id, is_transliterated,
               greatest(
                   CASE WHEN s1_cname = t_cname THEN 1.0 ELSE jaro_winkler_similarity(s1_cname, t_cname) END,
                   CASE WHEN s1_sname = t_sname THEN 1.0 ELSE jaro_winkler_similarity(s1_sname, t_sname) END,
                   CASE WHEN length(s1_cpname) >= 6 AND s1_cpname = t_cpname THEN 0.98 ELSE 0.0 END
               ) as name_sim,
               CASE 
                   WHEN length(s1_caddr) > 5 AND length(t_caddr) > 5 
                   THEN greatest(
                       CASE WHEN s1_caddr = t_caddr THEN 1.0 ELSE jaro_winkler_similarity(s1_caddr, t_caddr) END,
                       CASE WHEN s1_saddr = t_saddr THEN 1.0 ELSE jaro_winkler_similarity(s1_saddr, t_saddr) END
                   )
                   ELSE 0.0
               END as addr_sim,
               (s1_cname = t_cname OR s1_sname = t_sname OR (length(s1_cpname) >= 6 AND s1_cpname = t_cpname)) as is_exact_name,
               (s1_caddr = t_caddr OR s1_saddr = t_saddr) as is_exact_addr
        FROM dedup_cands_curr;

        CREATE OR REPLACE TABLE scored_composite AS
        SELECT s1_id, cand_id, name_sim, addr_sim, is_exact_name, is_exact_addr, is_transliterated,
               CASE 
                   WHEN is_transliterated AND addr_sim > 0.60 THEN addr_sim
                   WHEN addr_sim > 0.0 THEN (name_sim * 0.55 + addr_sim * 0.45)
                   ELSE (name_sim * 0.95)
               END as composite_score
        FROM scored_curr;
        """)

        # 6. Select Matches with Adaptive Score-Gap Logic (Variable Matches, max 6)
        print("  Selecting high-confidence corroborated matches (adaptive score-gap, variable max 6)...")
        con.execute("""
        CREATE OR REPLACE TABLE curr_matches AS
        WITH filtered_cands AS (
            SELECT s1_id, cand_id, composite_score,
                   max(composite_score) OVER (PARTITION BY s1_id) as top_score,
                   row_number() OVER (PARTITION BY s1_id ORDER BY composite_score DESC) as rn
            FROM scored_composite
            WHERE (addr_sim >= 0.55 AND composite_score >= 0.88)
               OR (is_exact_name AND addr_sim >= 0.50)
               OR (is_exact_addr AND (name_sim >= 0.65 OR is_transliterated))
               OR (is_transliterated AND addr_sim >= 0.72)
        )
        SELECT s1_id, cand_id
        FROM filtered_cands
        WHERE composite_score >= (top_score - 0.08)
          AND rn <= 6;

        INSERT INTO all_matches
        SELECT s1_id, cand_id FROM curr_matches;
        """)
        m_cnt = con.execute("SELECT count(*) FROM curr_matches").fetchone()[0]
        print(f"  Predicted matches: {m_cnt:,} for {country}")

        # 7. Select Candidates for candidate_pairs.tsv (Include all matches + top scored candidates up to 20)
        print("  Selecting candidates for candidate_pairs.tsv...")
        con.execute("""
        INSERT INTO all_candidates
        WITH ranked_cands AS (
            SELECT s1_id, cand_id,
                   row_number() OVER (PARTITION BY s1_id ORDER BY composite_score DESC) as rn
            FROM scored_composite
        ),
        top_cands AS (
            SELECT s1_id, cand_id FROM ranked_cands WHERE rn <= 20
        )
        SELECT s1_id, cand_id FROM curr_matches
        UNION
        SELECT s1_id, cand_id FROM top_cands;
        """)

        # Free country tables to manage RAM
        con.execute("DROP TABLE s1_curr; DROP TABLE s23_curr; DROP TABLE cands_curr; DROP TABLE dedup_cands_curr; DROP TABLE scored_curr; DROP TABLE scored_composite; DROP TABLE curr_matches;")
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
