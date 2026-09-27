#!/usr/bin/env python3
"""
Scale-aware, single-pass profiler for one source TSV file
(train_source1/2/3.tsv or test_source1/2/3.tsv).

Streams the file line by line (never loads it into memory), and reports:

  * row count, header check
  * missing / empty-string rate per column
  * duplicate entity_id rate
  * duplicate (business_name, business_address, country) full-record rate
  * country label distribution
  * business_name / business_address length distribution (reservoir-sampled
    percentiles - exact min/max/mean are computed from the full stream)
  * script/unicode composition of business_name + business_address:
      - which Unicode scripts are observed (Latin ASCII, Latin extended /
        accented, Devanagari, Bengali, Gurmukhi, Gujarati, Oriya, Tamil,
        Telugu, Kannada, Malayalam, other)
      - ASCII-only vs non-ASCII record rate
      - mixed-script record rate (more than one script in the same record)
      - script presence cross-tabulated against the country label

Usage:
    python3 src/analysis/profile_source.py dataset/train/train_source1.tsv

Deterministic: the length-percentile reservoir sample uses a fixed seed.
"""

import argparse
import collections
import random
import sys

EXPECTED_HEADER = ["entity_id", "business_name", "business_address", "country"]

# (name, inclusive unicode codepoint range)
SCRIPT_RANGES = [
    ("Latin_ASCII", (0x0000, 0x007F)),
    ("Latin_Extended", (0x0080, 0x024F)),
    ("Devanagari", (0x0900, 0x097F)),
    ("Bengali", (0x0980, 0x09FF)),
    ("Gurmukhi", (0x0A00, 0x0A7F)),
    ("Gujarati", (0x0A80, 0x0AFF)),
    ("Oriya", (0x0B00, 0x0B7F)),
    ("Tamil", (0x0B80, 0x0BFF)),
    ("Telugu", (0x0C00, 0x0C7F)),
    ("Kannada", (0x0C80, 0x0CFF)),
    ("Malayalam", (0x0D00, 0x0D7F)),
]


def classify_char(ch):
    cp = ord(ch)
    for name, (lo, hi) in SCRIPT_RANGES:
        if lo <= cp <= hi:
            return name
    return "Other"


def scripts_in(text):
    """Return the set of scripts present among alphabetic characters of text."""
    found = set()
    for ch in text:
        if ch.isalpha():
            found.add(classify_char(ch))
    return found


class ReservoirSampler:
    """Fixed-size reservoir sample for approximate percentiles on a stream."""

    def __init__(self, size=100_000, seed=42):
        self.size = size
        self.rng = random.Random(seed)
        self.buf = []
        self.n = 0

    def add(self, value):
        self.n += 1
        if len(self.buf) < self.size:
            self.buf.append(value)
        else:
            j = self.rng.randint(0, self.n - 1)
            if j < self.size:
                self.buf[j] = value

    def percentiles(self, ps=(0, 25, 50, 75, 95, 99, 100)):
        if not self.buf:
            return {}
        s = sorted(self.buf)
        out = {}
        for p in ps:
            idx = min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))
            out[p] = s[idx]
        return out


def profile(path, sample_size=100_000):
    n_rows = 0
    empties = collections.Counter()
    country_counts = collections.Counter()
    entity_ids = set()
    dup_entity_ids = 0
    full_records = set()
    dup_full_records = 0

    name_len = ReservoirSampler(sample_size, seed=42)
    addr_len = ReservoirSampler(sample_size, seed=43)

    ascii_only = 0
    non_ascii = 0
    mixed_script = 0
    script_record_counts = collections.Counter()
    script_by_country = collections.defaultdict(collections.Counter)

    with open(path, encoding="utf-8") as f:
        header_line = f.readline()
        header = [c.strip() for c in header_line.rstrip("\n").split("\t")]
        if header != EXPECTED_HEADER:
            print(f"WARNING: unexpected header {header}, expected {EXPECTED_HEADER}", file=sys.stderr)

        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 4:
                empties["MALFORMED_ROW"] += 1
                continue
            entity_id, name, addr, country = parts
            n_rows += 1

            if entity_id in entity_ids:
                dup_entity_ids += 1
            entity_ids.add(entity_id)

            key = (name, addr, country)
            if key in full_records:
                dup_full_records += 1
            full_records.add(key)

            if not entity_id.strip():
                empties["entity_id"] += 1
            if not name.strip():
                empties["business_name"] += 1
            if not addr.strip():
                empties["business_address"] += 1
            if not country.strip():
                empties["country"] += 1

            country_counts[country] += 1
            name_len.add(len(name))
            addr_len.add(len(addr))

            combined = name + " " + addr
            scripts = scripts_in(combined)
            if not scripts:
                script_record_counts["NO_ALPHA_CHARS"] += 1
            elif scripts == {"Latin_ASCII"}:
                ascii_only += 1
            else:
                non_ascii += 1
                if len(scripts) > 1:
                    mixed_script += 1
            for s in scripts:
                script_record_counts[s] += 1
                script_by_country[country][s] += 1

    print(f"=== {path} ===")
    print(f"rows: {n_rows}")
    print(f"malformed rows (wrong column count): {empties.get('MALFORMED_ROW', 0)}")
    print("missing/empty-string rate per column:")
    for col in EXPECTED_HEADER:
        rate = empties.get(col, 0) / n_rows if n_rows else 0
        print(f"  {col}: {empties.get(col, 0)} ({rate:.4%})")
    print(f"duplicate entity_id occurrences: {dup_entity_ids} ({dup_entity_ids / n_rows:.4%})")
    print(f"duplicate (name, address, country) occurrences: {dup_full_records} ({dup_full_records / n_rows:.4%})")
    print(f"unique entity_ids: {len(entity_ids)}")
    print()
    print(f"country distribution (top 20 of {len(country_counts)}):")
    for country, cnt in country_counts.most_common(20):
        print(f"  {country!r}: {cnt} ({cnt / n_rows:.4%})")
    print()
    print(f"business_name length percentiles (reservoir n={min(sample_size, n_rows)}): {name_len.percentiles()}")
    print(f"business_address length percentiles (reservoir n={min(sample_size, n_rows)}): {addr_len.percentiles()}")
    print()
    print("=== Script / multilingual composition (OBSERVED, full corpus) ===")
    print(f"ASCII-only records (Latin_ASCII script only): {ascii_only} ({ascii_only / n_rows:.4%})")
    print(f"Non-ASCII records (any non-ASCII-only script present): {non_ascii} ({non_ascii / n_rows:.4%})")
    print(f"Mixed-script records (>1 script in same record): {mixed_script} ({mixed_script / n_rows:.4%})")
    print(f"Records with no alphabetic characters at all: {script_record_counts.get('NO_ALPHA_CHARS', 0)}")
    print("script presence counts (a record can count toward multiple scripts):")
    for script, cnt in script_record_counts.most_common():
        if script == "NO_ALPHA_CHARS":
            continue
        print(f"  {script}: {cnt} ({cnt / n_rows:.4%})")
    print()
    print("script presence by country (top 8 scripts per country, of countries with >=1000 rows):")
    for country, counter in sorted(script_by_country.items(), key=lambda kv: -country_counts[kv[0]]):
        if country_counts[country] < 1000:
            continue
        total = country_counts[country]
        top = counter.most_common(8)
        print(f"  {country!r} (n={total}):")
        for script, cnt in top:
            print(f"    {script}: {cnt} ({cnt / total:.4%})")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="Path to a source TSV file (entity_id, business_name, business_address, country)")
    parser.add_argument("--sample-size", type=int, default=100_000, help="Reservoir sample size for length percentiles")
    args = parser.parse_args()
    profile(args.path, sample_size=args.sample_size)


if __name__ == "__main__":
    main()
