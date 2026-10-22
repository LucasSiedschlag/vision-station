"""V9: two runs in two processes give the same answers, scores to 1e-9 (architecture §15.3). Not between machines:
CI runs Windows and Linux separately."""

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

from validation.registry import entries

TESTS = Path(__file__).resolve().parents[1]
TOLERANCE = 1e-9


def _process() -> dict:
    env = {**os.environ, "PYTHONPATH": str(TESTS), "PYTHONHASHSEED": "random"}
    done = subprocess.run([sys.executable, "-m", "validation.probe"], cwd=TESTS, env=env, capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)


@pytest.fixture(scope="module")
def two_runs():
    return _process(), _process()


def _same(a, b, where):
    if isinstance(a, float) and isinstance(b, float):
        assert math.isclose(a, b, rel_tol=0, abs_tol=TOLERANCE), f"{where}: {a} != {b}"
    elif isinstance(a, dict) and isinstance(b, dict):
        assert a.keys() == b.keys(), f"{where}: not the same fields"
        for k in a:
            _same(a[k], b[k], f"{where}.{k}")
    elif isinstance(a, list) and isinstance(b, list):
        assert len(a) == len(b), f"{where}: not the same length"
        for i, (x, y) in enumerate(zip(a, b)):
            _same(x, y, f"{where}[{i}]")
    else:
        assert a == b, f"{where}: {a!r} != {b!r}"


@pytest.mark.parametrize("kind,name,version", entries("V9"))
def test_two_processes_give_the_same_answers(two_runs, kind, name, version):
    first, second = two_runs
    prefix = f"{kind}-{name}-v{version}/"
    mine = [k for k in first if k.startswith(prefix)]
    assert mine, "the probe gave nothing for this type"
    for key in mine:
        _same(first[key], second[key], key)
