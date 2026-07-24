# rv-monitoring-skill

[![CI](https://github.com/moraneus/rv-monitoring-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/moraneus/rv-monitoring-skill/actions/workflows/ci.yml)
[![behave-rv](https://img.shields.io/pypi/v/behave-rv?label=behave-rv)](https://pypi.org/project/behave-rv/)
[![License](https://img.shields.io/badge/license-BSD--2--Clause-green)](LICENSE)

**An agent skill that makes software *born monitorable*.** Loaded into a
coding agent (Claude Code and compatible harnesses), it changes how the
agent develops: the user's behavioural requirements become
[behave-rv](https://github.com/moraneus/behave-rv) runtime-verification
policies, instrumentation happens *while the code is written*, a two-sided
stability contract gates every change, and the software that leaves
development ships with a deterministic runtime monitor inside it.

The complete guide - how the skill is triggered and used by the agent, the
development loop, and how each part of behave-rv works inside it, with a
worked example - is [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

## What the agent does with this skill

- **Understands requirements as policies.** When a prompt contains
  behavioural requirements - lifecycles, deadlines, prohibitions, SLAs -
  the agent maps them to behave-rv's temporal Gherkin fragment and drafts
  policies. Anything outside the fragment is declared honestly, never
  approximated silently.
- **Instruments as it codes.** Every state transition, lifecycle boundary,
  and external interaction emits an event, following the conventions the
  stability analysis anchors on. Additive only - business logic is never
  reshaped to be observable.
- **Suggests, never imposes.** Draft policies land in
  `monitoring/SUGGESTED_POLICIES.md` with rationale. The user owns
  `monitoring/policies/`; the trust model is the skill's hardest rule: the
  agent proposes, the human owns the spec, the deterministic engine decides.
- **Keeps the user able to author.** `monitoring/STEPS.md` - generated from
  the live step registry, never hand-written - documents every phrasing,
  alias, parameter, and example scenario, so the user can write policies
  without reading Python.
- **Gates every change with the stability contract.** On each modification
  (including new prompts against existing code) the agent runs
  `catalog diff --app --fail-on-app-risk` and a deterministic replay check.
  Breaks stop the work and are reported verbatim; the catalog is
  regenerated only for intended contract changes, together with them.
- **`/rv` - interactive consultation.** A structured interview (entities
  and keys → lifecycles → prohibitions → deadlines → eventualities and
  terminal events) that produces a proposed event vocabulary, steps, and
  draft policies for the user's approval.

## Install

### As a Claude Code plugin (recommended)

```
/plugin marketplace add moraneus/rv-monitoring-skill
/plugin install rv-monitoring@rv-monitoring-skill
```

### Manually (Claude Code and compatible harnesses)

```bash
git clone https://github.com/moraneus/rv-monitoring-skill.git
cd rv-monitoring-skill
./install.sh              # user-level:  ~/.claude/skills/rv
./install.sh --project    # this project only: ./.claude/skills/rv
```

### On other coding platforms

The skill is plain files: markdown instructions, templates, and the
behave-rv CLI. Nothing in it runs only under Claude Code, so any coding
agent that can read files can follow it. What changes per platform is how
the instructions get loaded:

- **Harnesses that support the SKILL.md skills layout** - point them at
  `skills/rv/`, or run `./install.sh --project` to copy it into
  `.claude/skills/rv` inside your repository, a path several harnesses
  read.
- **AGENTS.md-based tools** (Codex CLI, Cursor, and others) - commit the
  skill into the repository (`./install.sh --project`) and add one line to
  `AGENTS.md`: "When working on monitoring, behavioural requirements, or
  any change to instrumented code, read `.claude/skills/rv/SKILL.md` and
  follow it."
- **GitHub Copilot** - the same line, in
  `.github/copilot-instructions.md`.
- **Gemini CLI** - the same line, in `GEMINI.md`.
- **Anything else** - paste `SKILL.md` into the platform's system prompt
  or rules file, and keep `references/` and `templates/` in the repo so
  the agent can open them.

Two Claude Code conveniences degrade gracefully elsewhere: automatic
triggering (the frontmatter description) becomes the one instruction line
you add to the platform's rules file, and `/rv` becomes asking the agent
to "run the rv consultation". The gates, the templates, the dashboard, and
`python -m behave_rv docs` behave identically everywhere, because they are
ordinary Python tooling.

Either way, target projects need `pip install behave-rv` (>= 0.3.0,
Python 3.10+) - the package ships the complete behave-rv documentation
(`python -m behave_rv docs`), which the skill reads as its authoritative
offline knowledge source. After installing, the agent
picks the skill up automatically when monitoring is relevant, and `/rv`
starts the interactive consultation.

## What's in the box

```
.claude-plugin/               plugin + marketplace manifests for
                              /plugin install
skills/rv/SKILL.md            the skill: workflow, guardrails, /rv
skills/rv/references/         condensed behave-rv knowledge (operators,
                              instrumentation, authoring, stability, files,
                              questionnaire, cheatsheet)
skills/rv/templates/          the monitoring/ scaffold installed into
                              projects: steps.py, example policy, replay
                              gate, STEPS.md generator, CI snippet
docs/HOW_IT_WORKS.md          the complete guide to the skill and the
                              behave-rv machinery behind it
demo/                         nine projects built end-to-end BY agents
                              using this skill (prompts included) - four
                              services and five browser games with live
                              RV dashboards; all gates run in CI
test/e2e.sh                   end-to-end validation of the templates and
                              gates against the published behave-rv package
```

The demos are also the proof: [demo/README.md](demo/README.md) indexes
nine projects, each testing a different part of the skill - four services
(the full development loop and break protocol, brownfield instrumentation
and the alias flow, the /rv consultation, and conflict detection with a
user-driven policy repair) and five browser games (snake, blackjack,
minesweeper, tic-tac-toe, memory) that ship with live RV dashboards and
in-browser cheat injection, covering the terminal-window, at-most-once,
history-stamping, and counting-projection patterns. Each project's
PROMPTS.md holds the exact human prompts that produced every file in it.

CI runs the end-to-end validation against the real PyPI `behave-rv` on every
push and weekly - including a check that the stability gate actually catches
an application-side change - so a behave-rv release that breaks the skill's
mechanics turns the badge red.

## The idea, in one paragraph

Runtime verification is usually retrofitted. This skill inverts that: the
agent performs the instrumentation while it writes the code, the catalog is
committed from the first commit, and every regeneration-happy rewrite is
held to the contract by machine-checked gates - which is precisely what
makes it safe to let an agent develop aggressively. The full framework,
its measured evidence (a 619-mutant campaign with zero missed behaviour
changes, among others), and its documentation live in the
[behave-rv repository](https://github.com/moraneus/behave-rv).

## License

BSD 2-Clause. See [LICENSE](LICENSE).
