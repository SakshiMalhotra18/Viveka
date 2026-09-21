# ADR-0001: Python, SQLite, local-first architecture

**Date:** 2026-09-18
**Status:** Accepted

---

## Context

VIVEKA is a local-first developer tool with a hard zero-cost constraint.
The architecture must support the full verification loop (inspect → verify
→ shrink → store → replay) without requiring any paid external service.

---

## Decisions

### Language: Python 3.12+

- Primary users are Python/LLM engineers who already work in Python.
- Python's AST module gives direct access to static analysis without external tools.
- All major LLM SDKs (LangChain, OpenAI, Anthropic) are Python-first.
- Python 3.12 provides structural pattern matching, improved typing, and performance improvements useful for the evaluation pipeline.

### Package manager: uv

- `uv` is the modern standard for Python project and package management.
- Provides deterministic lock files and fast dependency resolution.
- End-user install via `uv tool install viveka-engine` or `pipx install viveka-engine` requires no special setup.

### Local database: SQLite

- SQLite ships with Python's standard library — zero additional dependency.
- Adequate for the scale of verification runs, regressions, and traces produced locally.
- Database file lives in `~/.viveka/viveka.db` — never committed.
- If multi-user or team scenarios arise later, a migration path to Postgres exists via SQLAlchemy (same ORM).

### State model: two-level

| Level | Location | Version-controlled? | Contains |
|---|---|---|---|
| Project | `<repo>/.viveka/` | Yes | `config.yaml`, `properties/` |
| User | `~/.viveka/` | Never | `viveka.db`, traces, runs |

This separation allows teams to share approved properties via git while keeping
raw trace data and potential secrets out of the repository.

### Reasoning: deterministic-first, LLM-optional

All core verification logic (static analysis, rule matching, mutation, shrinking,
exact property checks) is deterministic and requires no LLM. LLMs are used only
where they add value that deterministic code cannot provide (semantic judgment,
ambiguous classification, diagnosis wording). The `ReasoningProvider` protocol
is designed so `DeterministicProvider` is always available as a fallback.

---

## Consequences

- VIVEKA will not have a web dashboard in V1.
- VIVEKA will not use a message queue, Redis, or Postgres in V1.
- All features must have a path that works in `--deterministic` mode.
- Cloud providers are opt-in and must never silently incur cost.
