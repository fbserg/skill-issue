#!/usr/bin/env python3
"""Run each standalone Herdr package's tests in its own Python process."""

from pathlib import Path
import subprocess
import sys


def main() -> int:
    failed = []
    for directory in sorted(Path(__file__).resolve().parent.iterdir()):
        if directory.is_dir() and list(directory.glob("test_*.py")):
            print(f"\nHerdr package: {directory.name}", flush=True)
            result = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", str(directory), "-p", "test_*.py", "-v"],
                check=False,
            )
            if result.returncode:
                failed.append(directory.name)
    if failed:
        print("Failed Herdr packages: " + ", ".join(failed), file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
