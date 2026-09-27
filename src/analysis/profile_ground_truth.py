#!/usr/bin/env python3
"""
Scale-aware, single-pass profiler for dataset/train/train_ground_truth.tsv.

Streams the file line by line and reports the match-cardinality structure that
should drive the matching-problem formulation (NOT assumed to be 1:1
classification):

  * total Source 1 entities (rows)
  * singleton rate (zero matches)
  * distribution of match count per S1 entity (0, 1, 2, 3-5, 6-10, 11+)
  * S2-only / S3-only / both-sources match composition
  * cross-tab of match-count bucket against country (joined against
    train_source1.tsv on entity_id, streamed - not loaded as a DataFrame)

Usage:
    python3 src/analysis/profile_ground_truth.py \
        dataset/train/train_ground_truth.tsv \
        --source1 dataset/train/train_source1.tsv
"""

import argparse
import collections


def bucket(n):
    if n == 0:
        return "0 (singleton)"
    if n == 1:
        return "1"
    if n == 2:
        return "2"
    if 3 <= n <= 5:
        return "3-5"
    if 6 <= n <= 10:
        return "6-10"
    return "11+"


def load_country_map(source1_path):
    country = {}
    with open(source1_path, encoding="utf-8") as f:
        next(f, None)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 4:
                continue
            country[parts[0]] = parts[3]
    return country


def profile(gt_path, source1_path=None):
    country_map = load_country_map(source1_path) if source1_path else None

    n_rows = 0
    dup_s1 = 0
    seen_s1 = set()
    bucket_counts = collections.Counter()
    bucket_by_country = collections.defaultdict(collections.Counter)
    s2_only = s3_only = both = zero = 0
    total_match_count = 0
    unknown_country = 0

    with open(gt_path, encoding="utf-8") as f:
        header = f.readline()
        for line in f:
            line = line.rstrip("\n")
            s1, tab, rest = line.partition("\t")
            if not tab:
                continue
            n_rows += 1
            if s1 in seen_s1:
                dup_s1 += 1
            seen_s1.add(s1)

            ids = [x for x in rest.split(",") if x] if rest.strip() else []
            n_matches = len(ids)
            total_match_count += n_matches
            b = bucket(n_matches)
            bucket_counts[b] += 1

            has_s2 = any(i.startswith("S2-") for i in ids)
            has_s3 = any(i.startswith("S3-") for i in ids)
            if n_matches == 0:
                zero += 1
            elif has_s2 and has_s3:
                both += 1
            elif has_s2:
                s2_only += 1
            elif has_s3:
                s3_only += 1

            if country_map is not None:
                c = country_map.get(s1)
                if c is None:
                    unknown_country += 1
                else:
                    bucket_by_country[c][b] += 1

    print(f"=== {gt_path} ===")
    print(f"total Source 1 entities (rows): {n_rows}")
    print(f"duplicate source1_entity_id rows: {dup_s1}")
    print(f"total match relationships (sum of matched_entity_ids): {total_match_count}")
    print(f"mean matches per S1 entity: {total_match_count / n_rows:.4f}")
    print()
    print("match-count bucket distribution:")
    for b in ("0 (singleton)", "1", "2", "3-5", "6-10", "11+"):
        cnt = bucket_counts.get(b, 0)
        print(f"  {b}: {cnt} ({cnt / n_rows:.4%})")
    print()
    print("composition among entities WITH at least one match:")
    non_zero = n_rows - zero
    if non_zero:
        print(f"  S2-only: {s2_only} ({s2_only / non_zero:.4%})")
        print(f"  S3-only: {s3_only} ({s3_only / non_zero:.4%})")
        print(f"  both S2 and S3: {both} ({both / non_zero:.4%})")
    print()
    if country_map is not None:
        print(f"S1 entities with unknown country (not found in {source1_path}): {unknown_country}")
        print("match-count bucket distribution by country:")
        for c, counter in bucket_by_country.items():
            total = sum(counter.values())
            print(f"  {c!r} (n={total}):")
            for b in ("0 (singleton)", "1", "2", "3-5", "6-10", "11+"):
                cnt = counter.get(b, 0)
                print(f"    {b}: {cnt} ({cnt / total:.4%})")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("gt_path", help="Path to train_ground_truth.tsv")
    parser.add_argument("--source1", default=None, help="Path to train_source1.tsv (for country cross-tab)")
    args = parser.parse_args()
    profile(args.gt_path, source1_path=args.source1)


if __name__ == "__main__":
    main()
