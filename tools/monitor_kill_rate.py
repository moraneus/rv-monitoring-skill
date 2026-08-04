"""Monitor kill rate: mutation testing where the app is the subject and the
monitor is the test suite.

Mutate a demo's application code one edit at a time; for each mutant run the
demo's own runtime gate (`monitoring/replay_check.py`). A mutant is KILLED if
the gate goes red. The kill rate is the coverage-confidence metric: how much of
the app's behaviour the monitor actually catches. Survivors are the mutations
the monitor is blind to - candidate policy gaps.

    python tools/monitor_kill_rate.py <demo_dir> <app_file> [app_file ...] \
        [--json out.json]

Only single-token string literals (status values, keys) are mutated, not prose
or docstrings, so the signal stays behavioural and the run stays fast. The
stability contract (`catalog diff`) is a near-total catch-all by construction
(it flags any emit-path change), so the runtime kill rate reported here is the
metric that actually varies between monitors.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path

BV = sys.executable

_CMP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
        ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
_BIN = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv}
_BOOL = {ast.And: ast.Or, ast.Or: ast.And}


def _mutable_str(v) -> bool:
    # single tokens only: status values, keys, event types - not prose/docstrings
    return isinstance(v, str) and 0 < len(v) <= 24 and " " not in v and "\n" not in v


class _Mut(ast.NodeTransformer):
    """Mutate the target-th mutation opportunity, in a fixed traversal order."""

    def __init__(self, target: int):
        self.n = -1
        self.t = target
        self.hit = None

    def _try(self, kind, lineno, apply):
        self.n += 1
        if self.n == self.t and self.hit is None:
            apply()
            self.hit = (lineno, kind)

    def visit_Compare(self, node):
        for j, op in enumerate(list(node.ops)):
            if type(op) in _CMP:
                self._try("cmp", node.lineno,
                          lambda node=node, j=j, op=op: node.ops.__setitem__(j, _CMP[type(op)]()))
        return self.generic_visit(node)

    def visit_BinOp(self, node):
        if type(node.op) in _BIN:
            self._try("bin", node.lineno,
                      lambda node=node: setattr(node, "op", _BIN[type(node.op)]()))
        return self.generic_visit(node)

    def visit_BoolOp(self, node):
        if type(node.op) in _BOOL:
            self._try("bool", node.lineno,
                      lambda node=node: setattr(node, "op", _BOOL[type(node.op)]()))
        return self.generic_visit(node)

    def visit_Constant(self, node):
        v = node.value
        if isinstance(v, bool):
            self._try("boolconst", node.lineno,
                      lambda node=node, v=v: setattr(node, "value", not v))
        elif isinstance(v, int):
            self._try("int", node.lineno,
                      lambda node=node, v=v: setattr(node, "value", v + 1))
        elif _mutable_str(v):
            self._try("str", node.lineno,
                      lambda node=node, v=v: setattr(node, "value", v + "_MUT"))
        return node


def _count(src: str) -> int:
    m = _Mut(-1)
    m.visit(ast.parse(src))
    return m.n + 1


def _gate_red(demo: str) -> bool:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    for pyc in Path(demo).rglob("*.pyc"):
        pyc.unlink(missing_ok=True)
    try:
        r = subprocess.run([BV, "monitoring/replay_check.py"], cwd=demo,
                           capture_output=True, text=True, timeout=60, env=env)
    except subprocess.TimeoutExpired:
        return True   # a hang is a kind of failure -> killed
    return r.returncode != 0 or not r.stdout.strip()


def run(demo: str, app_files: list[str]) -> dict:
    demo_p = Path(demo)
    assert not _gate_red(demo), f"{demo_p.name}: clean gate is already red"
    killed = survived = 0
    survivors: list[str] = []
    for af in app_files:
        path = demo_p / af
        src = path.read_text()
        total = _count(src)
        for k in range(total):
            tree = ast.parse(src)
            mut = _Mut(k)
            new_tree = mut.visit(tree)
            if mut.hit is None:
                continue
            try:
                new_src = ast.unparse(ast.fix_missing_locations(new_tree))
            except Exception:
                continue
            path.write_text(new_src)
            try:
                if _gate_red(demo):
                    killed += 1
                else:
                    survived += 1
                    survivors.append(f"{af}:{mut.hit[0]} [{mut.hit[1]}]")
            finally:
                path.write_text(src)
    total = killed + survived
    return {
        "demo": demo_p.name,
        "mutants": total,
        "killed": killed,
        "survived": survived,
        "kill_rate": round(100.0 * killed / total, 1) if total else 0.0,
        "survivors": survivors,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("demo")
    ap.add_argument("app_files", nargs="+")
    ap.add_argument("--json")
    args = ap.parse_args()
    result = run(args.demo, args.app_files)
    print(f"{result['demo']:13} mutants={result['mutants']:3} "
          f"killed={result['killed']:3} survived={result['survived']:3} "
          f"kill-rate={result['kill_rate']:5.1f}%")
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
