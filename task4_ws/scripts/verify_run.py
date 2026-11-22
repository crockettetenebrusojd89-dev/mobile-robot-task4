#!/usr/bin/env python3
"""Verify saved run directory artifacts for read-back integrity."""

import argparse
import json
from pathlib import Path

from task4_bringup.result_io import verify_run_directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="Path to results/runs/<task_id>")
    args = parser.parse_args()

    report = verify_run_directory(args.run_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
