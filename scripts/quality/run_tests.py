#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Aggiungi root al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestration.session_manager import get_session_manager


def _now_ts():
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _ensure_tests_dir(sm):
    tests_dir = sm.get_subdir_path('tests')
    tests_dir.mkdir(parents=True, exist_ok=True)
    return tests_dir


def run_tests(pytest_args):
    sm = get_session_manager(script_name='run_tests')
    tests_dir = _ensure_tests_dir(sm)

    stamp = _now_ts()
    junit_path = tests_dir / f'pytest_junit_{stamp}.xml'
    stdout_path = tests_dir / f'pytest_stdout_{stamp}.txt'
    stderr_path = tests_dir / f'pytest_stderr_{stamp}.txt'
    summary_path = tests_dir / f'pytest_summary_{stamp}.json'

    cmd = [sys.executable, '-m', 'pytest'] + list(pytest_args) + [f'--junitxml={junit_path}']

    t0 = time.time()
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    t1 = time.time()

    stdout_path.write_text(proc.stdout or '', encoding='utf-8', errors='replace')
    stderr_path.write_text(proc.stderr or '', encoding='utf-8', errors='replace')

    summary = {
        'timestamp': stamp,
        'returncode': proc.returncode,
        'command': cmd,
        'duration_seconds': round(t1 - t0, 3),
        'artifacts': {
            'junitxml': str(junit_path),
            'stdout': str(stdout_path),
            'stderr': str(stderr_path),
        },
    }

    summary_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')

    print(f"Session: {sm.current_session}")
    print(f"Artifacts dir: {tests_dir}")
    print(f"Return code: {proc.returncode}")
    print(f"JUnit XML: {junit_path.name}")
    print(f"Stdout: {stdout_path.name}")
    print(f"Stderr: {stderr_path.name}")
    print(f"Summary: {summary_path.name}")

    return proc.returncode


def main():
    parser = argparse.ArgumentParser(description='Run pytest and save artifacts into current session')
    parser.add_argument('--pytest-args', nargs=argparse.REMAINDER, default=['-q'], help='Args passed to pytest (default: -q)')
    args = parser.parse_args()

    rc = run_tests(args.pytest_args)
    raise SystemExit(rc)


if __name__ == '__main__':
    main()
