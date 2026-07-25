# behave-rv in one page

Package: `behave-rv` (PyPI, >= 0.3.1), Python 3.10+. Import root: `behave_rv`.
Full documentation ships with the install: `python -m behave_rv docs [name]`.

## The event

```python
from behave_rv.events.event import Event

Event(
    type="order.status",          # stable identity, dotted lowercase
    event_time=clock(),           # float seconds, EVENT time (never receipt time)
    bindings={"order_id": oid},   # correlation key values (entity identity)
    payload={"status": "paid"},   # the observable fields
    source="order-service",       # provenance label
)
```

## Steps (the vocabulary policies bind to)

```python
from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

def build_registry() -> StepRegistry:          # side-effect-free factory
    registry = StepRegistry()

    @registry.trigger('an order is "{status}"', step_id="order.status.is",
                      event_type="order.status", correlation_key="order_id")
    def order_is(ctx, event, status):          # PURE: read event, return bool
        return (event.type == "order.status"
                and event.payload.get("status") == status)

    return registry

# rephrasing stays compatible when the old wording remains:
registry.alias("order.status.is", 'the order reaches "{status}"')
```

Placeholder names bind BY NAME to parameters - renaming the parameter while
keeping `{status}` in the phrasing is a contract break the catalog reports.
`step_id` is permanent identity: never reuse, never rename casually.

## Compile and run (replay)

```python
policies = compile_feature(feature_text, registry)          # refuses loudly
from behave_rv.engine.loop import Engine
from behave_rv.events.sources.replay import ReplaySource, record_events

engine = Engine(policies, terminal_event_types={"order.done"},
                grace=5.0)                    # reorder window (event time)
verdicts = engine.run(ReplaySource("trace.jsonl"), emit_pending=True)
# Verdict: policy_id, entity_key, verdict in {satisfied, violated, pending},
#          trigger_event, witnessing_trace, at
```

Explanations: `from behave_rv.verdict.explain import explain_verdict` -
renders the authored scenario with the failing step marked and the deciding
events listed.

## Live wiring

```python
# entry point at the project root: make monitoring/ importable first
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "monitoring"))
from steps import build_registry, load_policies

from behave_rv.events.sources.subscription import QueueSource
from behave_rv.events.sources.replay import TraceRecorder
from behave_rv.dashboard import Dashboard

start = time.time()                            # service-relative clock (optional
                                               # since 0.3.0; raw time.time() works)
source = QueueSource()
dashboard = Dashboard(policies, registry=registry,
                      catalog="monitoring/catalog.json",
                      app=["app/service.py"])  # two-sided stability strip
clock = lambda: time.time() - start
recorder = TraceRecorder("monitoring/traces/live_session.jsonl", clock=clock)
# on recorder.close(): a clock-horizon marker makes wall-fired deadline
# verdicts reproducible on replay instead of replaying as pending
service = Service(lambda e: source.push(dashboard.tap(recorder(e))),
                  clock=clock)
url = dashboard.start(port=7007)               # port=0 lets the OS pick one
print("live monitor:", url)                    # always tell the user this URL
engine.run(source, sink=dashboard.sink)        # live verdict delivery
```

## Attaching to an existing service (no in-process emits)

When the target is ALREADY instrumented, or only writes structured JSON logs,
monitor it without adding any emit calls to its code. Both sources feed the
same `engine.run(...)`; the mapping (not the code) says which field is the
event type, the correlation key, and the payload.

```python
# OpenTelemetry: register as a span processor on the running provider
from opentelemetry.sdk.trace import TracerProvider          # needs behave-rv[otel]
from behave_rv.events.sources.otel import OTelSpanSource, SpanMapping

source = OTelSpanSource(SpanMapping(key_attributes={"order.id": "order_id"}))
provider.add_span_processor(source)            # span.name -> type,
engine.run(source, sink=dashboard.sink)        # attributes -> bindings/payload

# Structured JSON logs: map a foreign log schema (batch, like replay)
from behave_rv.events.sources.logs import StructuredLogSource, LogMapping

source = StructuredLogSource("var/log/orders.jsonl",
    LogMapping(type_field="event", time_field="ts",
               key_fields={"order_id": "order_id"}))
verdicts = engine.run(source, emit_pending=True)
```

A span or record missing the correlation key is dropped and COUNTED
(`source.dropped`, plus `source.malformed` for unparseable log lines), never
merged silently - a rising count means the mapping does not match the real
stream. Use these for a service you did not write; when you ARE writing the
instrumentation, prefer the in-process emit path above. Both sources require
behave-rv >= 0.4.0 (the OTel one also needs the `[otel]` extra); the core
in-process, queue, and replay paths do not.

## Engine facts that matter

- Verdicts are decided on EVENT time; equal timestamps are ordered
  canonically (by content), so two actions whose order matters must carry
  distinct timestamps - tick the clock between them.
- `within` deadlines fire on absence (timer), including on wall time for
  quiet live streams; on replay, event time drives them.
- The default reorder grace (5.0s) is sized for laggy telemetry. On a
  fast LIVE stream (sub-second game/UI dynamics) use a small grace - a
  large grace delays verdict delivery by up to the grace window. (The
  false-timeout that grace > deadline used to cause was an engine bug,
  fixed in behave-rv 0.3.1; correctness no longer depends on the grace
  sizing.) Never drive a live source with simulated or compressed
  timestamps - live mode assumes event time progresses at wall rate.
- Terminal events settle an entity: prohibitions → satisfied, unfulfilled
  obligations → violated; configure `terminal_event_types` or the engine
  warns for operators that need settlement.
- `emit_pending=True` reports honest pending verdicts at end of replay.
- Per-entity memory is bounded; entities are reclaimed at terminal or by
  quiescence TTL.

## The CLI

```bash
python -m behave_rv --steps steps.py --policy p.feature --trace t.jsonl
python -m behave_rv catalog save --steps monitoring/steps.py \
    --catalog monitoring/catalog.json --app app/service.py
python -m behave_rv catalog diff --steps monitoring/steps.py \
    --catalog monitoring/catalog.json --policies monitoring/policies \
    --app app/service.py --fail-on-app-risk [--trace traces/last_week.jsonl]
```

Exit codes: 0 clean, 1 breaks (CI gate), 2 usage/compile errors.
