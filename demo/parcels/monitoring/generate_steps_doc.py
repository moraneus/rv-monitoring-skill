"""Render monitoring/STEPS.md from the live step registry.

Run after every change to steps.py:

    python monitoring/generate_steps_doc.py

The output is the user's policy-authoring surface: every phrasing and alias,
its parameters, the event it observes, and ready-to-copy example scenarios.
Generated so it cannot drift from the code; do not edit STEPS.md by hand.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from steps import build_registry  # noqa: E402

OUT = Path(__file__).parent / "STEPS.md"

TRIGGERED_FORMS = [
    ("precedence", "When {phrase}\n    Then {phrase2} before"),
    ("deadline", "When {phrase}\n    Then {phrase2} within \"30\" seconds"),
]
SELF_FORMS = [
    ("prohibition", "Then {phrase} never happens"),
    ("eventuality", "Then {phrase} has happened"),
    ("scoped prohibition", "Given {phrase}\n    Then {phrase2} never happens"),
]


def _example_phrase(phrasing: str) -> str:
    """Fill placeholders with visible example values."""
    return re.sub(r"\{(\w+)(?::\w+)?\}", lambda m: f'<{m.group(1)}>', phrasing)


def _observed_values() -> dict:
    """Map (event_type, field) -> sorted distinct values seen in a
    representative recorded trace, so authors write real status strings
    instead of guessing. Placeholder values that never appear in the real
    stream compile fine but silently never match at runtime -- listing the
    observed values is the guard against that silent-dormancy gap."""
    import json
    seen: dict = {}
    traces = Path(__file__).parent / "traces"
    files = sorted(traces.glob("*.jsonl")) if traces.is_dir() else []
    # prefer a file named representative*, else use all
    rep = [f for f in files if f.name.startswith("representative")] or files
    for f in rep:
        for line in f.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            etype = ev.get("type")
            for field, value in (ev.get("payload") or {}).items():
                if isinstance(value, (str, int, float, bool)):
                    seen.setdefault((etype, field), set()).add(str(value))
    return {k: sorted(v) for k, v in seen.items()}


def main() -> int:
    registry = build_registry()
    aliases = getattr(registry, "_aliases", {})
    observed = _observed_values()
    lines = [
        "# The policy vocabulary (generated - do not edit)",
        "",
        "Every phrasing below can be used in a `.feature` policy under",
        "`monitoring/policies/`. Quoted `<placeholders>` take concrete values -",
        "use the exact strings listed under each step (a value the app never",
        "emits will compile but silently never match).",
        "Regenerate this file with `python monitoring/generate_steps_doc.py`.",
        "",
    ]
    for entry in registry.entries():
        signature = entry.signature
        phrase = _example_phrase(entry.phrasing)
        lines += [
            f"## `{entry.phrasing}`",
            "",
            f"- **identity**: `{entry.step_id}` ({entry.kind})",
            f"- **observes**: event `{signature.event_type}`, "
            f"entity key `{', '.join(signature.correlation_key)}`",
        ]
        params = sorted(signature.referenced_fields)
        if params:
            lines.append(f"- **parameters**: {', '.join(f'`{p}`' for p in params)}")
            for field in params:
                vals = observed.get((signature.event_type, field))
                if vals:
                    shown = ", ".join(f"`{v}`" for v in vals)
                    lines.append(f"  - `{field}` values seen in the recorded "
                                 f"trace: {shown}")
                else:
                    lines.append(f"  - `{field}`: no values recorded yet - "
                                 f"confirm the exact string the app emits, or "
                                 f"a policy may compile but silently never match")
        step_aliases = aliases.get(entry.step_id, [])
        if step_aliases:
            lines.append("- **also writable as**: "
                         + "; ".join(f"`{a}`" for a in step_aliases))
        lines += ["", "Example scenarios:", "", "```gherkin"]
        for title, template in SELF_FORMS[:2] + TRIGGERED_FORMS:
            body = template.format(phrase=phrase, phrase2=phrase)
            lines += [f"  Scenario: <your policy name>  # {title}",
                      f"    {body}", ""]
        lines += ["```", ""]
    lines += [
        "## Combining steps",
        "",
        "Any trigger phrasing can be the `When`, the `Then` operand, or the",
        "`Given` scope of the temporal forms - see the operator reference in",
        "the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms",
        "and their exact semantics. One correlation key per scenario.",
        "",
    ]
    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT} ({len(registry.entries())} step(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
