"""Check completed, archived runs, including failures only in Xenia's log.

This is a crash/progress check. Pixel inspection remains a separate acceptance.
"""
import argparse
import json
from pathlib import Path
import re


def check(directory, minimum_race_age=None):
    guest = (directory / 'guest.log').read_text(encoding='utf-8', errors='replace')
    host = (directory / 'xenia.log').read_text(encoding='utf-8', errors='replace')
    patterns = {
        # A missing optional disc may be satisfied by extracted asset overrides.
        'startup_failures': r'\[boot\] (?:asset-validation|platform-init) FAILED\b|\[CTR Native\] (?:missing asset:|Missing or invalid assets|Failed to )',
        'guest_faults': r'\[fault\]',
        'packet_failures': r'invalid tag length|invalid-prim|invalid OT link|overshoot|OT walk[^\r\n]*(?:cycle|cap)',
        'gpu_link_failures': r'GPU link bridge (?:has no token|failed to register)',
        'asset_contract_failures': r'\[asset-contract\]',
    }
    counts = {key: len(re.findall(pattern, guest, re.I)) for key, pattern in patterns.items()}
    # Match actual calls / STOP lines, not the normal imported-symbol list.
    counts['kernel_crashes'] = len(re.findall(r'^.*(?:\*\*\* STOP:|\bKeBugCheck(?:Ex)?\()', host, re.M))
    counts['host_gpu_link_failures'] = len(re.findall(patterns['gpu_link_failures'], host, re.I))
    ages = [int(x) for x in re.findall(r'hb demo(?:-render)? f=\d+ age=(\d+)', guest)]
    last_age = max(ages, default=None)
    progress_ok = minimum_race_age is None or (last_age is not None and last_age >= minimum_race_age)
    return {'counts': counts, 'last_race_age': last_age,
            'minimum_race_age': minimum_race_age, 'progress_ok': progress_ok,
            'passed': not any(counts.values()) and progress_ok}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--minimum-race-age', type=int)
    args = parser.parse_args()
    report = check(args.directory, args.minimum_race_age)
    (args.directory / 'crash-check.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
