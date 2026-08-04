"""Run the monitor kill-rate harness over every demo and write the report.

    uv run --no-project --with behave-rv==0.5.0 python tools/run_kill_rates.py
"""
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, "tools")
from monitor_kill_rate import run  # noqa: E402


def app_files(catalog_path: str) -> list[str]:
    c = json.load(open(catalog_path))
    mods = sorted({s["module"] for s in c["app_surface"]})
    return [f"app/{m}.py" for m in mods]


def main() -> int:
    results = []
    for cat in sorted(glob.glob("demo/*/monitoring/catalog.json")):
        demo = str(Path(cat).parents[1])
        name = Path(demo).name
        try:
            r = run(demo, app_files(cat))
        except AssertionError as e:
            r = {"demo": name, "error": str(e), "kill_rate": None}
        results.append(r)
        if r.get("kill_rate") is None:
            print(f"{name:13} ERROR: {r.get('error')}")
        else:
            print(f"{name:13} mutants={r['mutants']:3} killed={r['killed']:3} "
                  f"survived={r['survived']:3} kill-rate={r['kill_rate']:5.1f}%")
    Path("tools/kill_rates.json").write_text(json.dumps(results, indent=1))
    rated = [r for r in results if r.get("kill_rate") is not None]
    if rated:
        avg = sum(r["kill_rate"] for r in rated) / len(rated)
        print(f"\nmean runtime kill rate across {len(rated)} demos: {avg:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
