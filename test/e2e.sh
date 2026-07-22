#!/usr/bin/env bash
# End-to-end validation of the skill's mechanical layer against the REAL
# behave-rv package: scaffold a project from the templates, and run the full
# loop the skill prescribes -- compile the example policy, evaluate a trace,
# generate STEPS.md, save the two-sided catalog, and verify the diff gate.
set -euo pipefail
cd "$(dirname "$0")/.."

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
echo "scaffolding into $WORK"

mkdir -p "$WORK/app"
cp -r skills/rv/templates/monitoring "$WORK/monitoring"

# instantiate the placeholders the way the skill would for a ticket system
for f in "$WORK"/monitoring/steps.py "$WORK"/monitoring/policies/01_example.feature \
         "$WORK"/monitoring/replay_check.py; do
  sed -i.bak -e 's/__PROJECT__/ticketing/g' -e 's/__ENTITY__/ticket/g' \
             -e 's/__DOMAIN__/ticket/g' -e 's/__KEY__/ticket_id/g' "$f"
  rm "$f.bak"
done

# a minimal instrumented application, per the skill's conventions
cat > "$WORK/app/service.py" <<'EOF'
"""A minimal service instrumented per the rv skill's conventions."""

import time

from behave_rv.events.event import Event

EVENT_TYPE = "ticket.status"
TERMINAL_TYPE = "ticket.done"


class TicketService:
    def __init__(self, emit, clock=time.time):
        self._emit = emit
        self._clock = clock

    def _status(self, ticket_id, status):
        self._emit(Event(EVENT_TYPE, self._clock(), {"ticket_id": ticket_id},
                         {"status": status}, "ticketing"))

    def start(self, ticket_id):
        self._status(ticket_id, "started")

    def complete(self, ticket_id):
        self._status(ticket_id, "completed")
        self._emit(Event(TERMINAL_TYPE, self._clock() + 1e-3,
                         {"ticket_id": ticket_id}, {}, "ticketing"))
EOF

# templates must at least be valid Python before instantiation-specific bits
python -m py_compile "$WORK/monitoring/replay_check.py"

cd "$WORK"

echo "== 1. steps compile, the example policy compiles, verdicts are correct"
python - <<'EOF'
import sys
sys.path.insert(0, "monitoring")
sys.path.insert(0, "app")
from steps import build_registry, load_policies
from service import TicketService
from behave_rv.engine.loop import Engine
from behave_rv.events.sources.inprocess import InProcessSource

registry = build_registry()
policies = load_policies(registry)
assert len(policies) == 1, policies

class Clock:
    now = 0.0
    def __call__(self):
        return self.now

clock = Clock()
source = InProcessSource()
service = TicketService(source.emit, clock=clock)
service.start("T-1"); clock.now += 1; service.complete("T-1")
clock.now += 1
service.complete("T-2")                      # completed without start -> violation

engine = Engine(policies, terminal_event_types={"ticket.done"})
verdicts = engine.run(source, emit_pending=True)
outcomes = {(v.entity_key["ticket_id"], v.verdict) for v in verdicts}
assert ("T-1", "satisfied") in outcomes, outcomes
assert ("T-2", "violated") in outcomes, outcomes
print("verdicts OK:", sorted(outcomes))
EOF

echo "== 2. STEPS.md generates from the registry"
python monitoring/generate_steps_doc.py
grep -q 'a ticket is "{status}"' monitoring/STEPS.md
grep -q "ticket.status.is" monitoring/STEPS.md
echo "STEPS.md OK"

echo "== 3. the two-sided catalog saves and the diff gate passes"
python -m behave_rv catalog save \
  --steps monitoring/steps.py --catalog monitoring/catalog.json \
  --app app/service.py
python -m behave_rv catalog diff \
  --steps monitoring/steps.py --catalog monitoring/catalog.json \
  --policies monitoring/policies --app app/service.py --fail-on-app-risk

echo "== 4. the gate CATCHES an app-side change (guard added to an emit path)"
python - <<'EOF'
from pathlib import Path
p = Path("app/service.py")
t = p.read_text()
old = '    def start(self, ticket_id):\n        self._status(ticket_id, "started")'
new = '    def start(self, ticket_id):\n        if ticket_id:\n            self._status(ticket_id, "started")'
assert old in t
p.write_text(t.replace(old, new))
EOF
if python -m behave_rv catalog diff \
    --steps monitoring/steps.py --catalog monitoring/catalog.json \
    --policies monitoring/policies --app app/service.py --fail-on-app-risk \
    > diff_out.txt 2>&1; then
  echo "ERROR: the diff gate should have flagged the guard change"; cat diff_out.txt; exit 1
fi
grep -q "behavior-risk" diff_out.txt
grep -q "TicketService.start" diff_out.txt
echo "app-side change correctly flagged and named"

echo "== 5. the shipped documentation the skill relies on is available offline"
python -m behave_rv docs | grep -q "guide"
python -m behave_rv docs operators | grep -q "temporal vocabulary"
python -m behave_rv docs stability > /dev/null
echo "python -m behave_rv docs OK (requires behave-rv >= 0.2.0)"

echo
echo "e2e: all checks passed against $(python -c 'import behave_rv; print("behave-rv", behave_rv.__version__)')"
