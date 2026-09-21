# Changelog

All notable changes to VIVEKA will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
VIVEKA uses [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

## [0.1.1] — 2026-09-21

### Fixed
- Release publication workflow: First successfully prepared public package release after initial v0.1.0 tag deployment issue.
- Resolved CLI replay test non-determinism in test suite.

## [0.1.0] — 2026-09-18

### Added
- Phase 0: Python 3.12+ project with `uv`, `src/` layout, Ruff, pytest.
- Phase 1: CLI shell with `viveka version`, `viveka init`, `viveka doctor`.
- Phase 2: Safe repository scanner (`viveka inspect PATH --dry-run` & `--json`).
  - Strict security policy: hard exclusions for secrets, credentials, certificates, private keys, `.env*`.
  - Pattern matching for `.gitignore`, `.vivekaignore`, and CLI `--include` / `--exclude` filters using `pathspec`.
  - Binary file detection via known extension classification and bounded null-byte content probing.
  - File size threshold safety enforcement (`max_file_size_kb`).
  - Path traversal protection, loop prevention, and symlink isolation (`is_inside` validation).
  - Pure JSON machine-readable output mode.
  - Zero-code-execution guarantee and non-mutation repository verification.
- Phase 3: Python static analysis (`viveka inspect PATH` with structural analysis).
  - AST parsing via Python standard library `ast.parse()` on Phase 2-approved Python files.
  - Structural extraction of functions, async functions, parameters, defaults, docstrings, classes, methods, imports, and calls.
  - Heuristic framework detection with concrete evidence (LangGraph, FastAPI, LangChain, MCP Python SDK, OpenAI Agents SDK, Flask, Pydantic AI).
  - Structural tool candidate detection (`@tool`, `@function_tool`, `@mcp.tool()`, tool file heuristics) and entrypoint candidate detection.
  - Intra-project local import graph construction and external package identification.
  - Resilience against malformed files (`ParseFailure`) and malicious top-level execution attempts.
  - Machine-readable JSON output envelope with `schema_version: 1`.
- Phase 4: Capability model, semantic classification, trust boundaries, and static capability graph.
  - Controlled vocabularies: `CapabilityTag`, `SideEffect`, `Externality`, `Reversibility`, `TrustRole` StrEnums.
  - Deterministic rule registry (15 rules) mapping static call, import, and decorator evidence to capabilities.
  - False-positive controls suppressing documentation/policy text, config variables, label operations, and execution plans.
  - Static capability graph construction with module, tool, entrypoint, symbol, and capability nodes and typed edges.
  - Trust boundary inference (`untrusted_ingress`, `sensitive_source`, `privileged_sink`, `external_sink`) with `static_only = True`.
  - Seamless integration into `viveka inspect` Rich CLI output and `capability_analysis` in `--json` output.
- Phase 5: Property engine with deterministic inference, YAML persistence, and CLI approval workflow.
  - Controlled vocabularies: `PropertyStatus`, `PropertySource`, `InvariantType`, `PropertyEvidenceType` StrEnums.
  - Property models: `Property`, `PropertyCatalog`, `AppliesWhen` with `source_capability_keys` / `sink_capability_keys`.
  - Discriminated union `PropertyOracle` (`FlowForbiddenOracle`, `FailureHandledOracle`) — typed, no open-ended dicts.
  - `PropertyEvidenceRef` with typed `PropertyEvidenceType` enum and optional `line` for synthetic evidence.
  - `PropertyRevisionRecord` with timezone-aware UTC timestamps and automatic revision history on approve/reject.
  - 7 deterministic property inference rules consuming `CapabilityAnalysisResult` as upstream contract.
  - Stable property keys derived from path-qualified capability keys (`{path}::{symbol}`).
  - Strong interaction check: graph edges, shared entrypoint reachability, trust-boundary flow (co-location alone insufficient).
  - `PROP-RULE-FAIL-SILENT-001` scoped to agent-callable/exposed tools only (not arbitrary internal helpers).
  - `PropertyStore` with YAML persistence in `.viveka/properties/`, deduplication by `stable_key`, merge-without-overwrite.
  - CLI subcommands: `viveka properties list`, `suggest`, `show`, `approve`, `reject` (no `edit` in V1).
  - `READONLY-PURPOSE` rule deferred until runtime/world context exists.
- Phase 6: World and mutation engine.
  - Controlled vocabularies: `WorldSlotKind`, `DocumentTrust`, `ToolBehavior`, `MutationFamily`, `MutationOperator` StrEnums.
  - Complete mutation family mapping (`MUTATION_FAMILIES`) binding 44 concrete mutation operators to 6 top-level families (§17.1-§17.6).
  - Domain models: `World`, `WorldUser`, `WorldInput`, `WorldRetrieval`, `WorldDocument`, `WorldToolConfig`, `WorldEnvironment`, `WorldState`, `WorldAuthorization`, `MutationRecord`.
  - Mutation registry: 21 deterministic operators (retrieval, input, tool-result, environment, authorization, state) and 23 LLM-requiring stubs.
  - Adversarial injection template library for deterministic poisoning and instruction embedding.
  - Deterministic `WorldGenerator` generating baseline and mutated worlds targeting approved properties with seed reproducibility.
  - `WorldStore` with YAML persistence in `.viveka/worlds/`, load by property stable key, and clearance.
  - CLI subcommands: `viveka worlds generate`, `list`, `show`.
- Phase 7: Demo target and runtime adapter.
  - Controlled vocabularies: `RuntimeAdapterType`, `ExecutionStatus`, `RawEventType` StrEnums.
  - Runtime models: `TargetSpec`, `AgentRuntimeContext` (with typed sub-models `AgentUserContext`, `AgentDocumentContext`, `AgentToolConfigContext`, `AgentEnvironmentContext`, `AgentStateContext`, `AgentAuthorizationContext`), `RuntimeRequest`, `RawEvent` (with 1-indexed `sequence` and `call_id` UUID correlation), `RuntimeResult` (`execution_id` with `VRUN` prefix).
  - Explicit lossless mapper (`map_world_to_context`) converting Phase 6 `World` to `AgentRuntimeContext` with `UnsupportedWorldFeatureError`.
  - Abstract base class `BaseRuntimeAdapter` defining execution interface.
  - `PythonCallableAdapter` executing Python targets in child processes using stdlib `multiprocessing` for process isolation and hard `timeout_seconds` enforcement (`proc.kill()`).
  - VIVEKA-owned `EventCollector` and `wrap_tool` wrappers emitting observable telemetry without target code participation.
  - Bundled Demo Customer Support Agent (`viveka.demo.agent:run_demo_agent`) with 5 in-memory fake tools (`knowledge.search`, `customer.read`, `refund.create`, `email.send`, `ticket.update`), fresh `DemoToolStore` per execution, committed side effect with lost ACK on uncertain timeout, and seeded stochastic vulnerability triggers (indirect prompt injection, unauthorized refund, PII exfiltration via `email.send`, false success after failure, duplicate side effect on retry).
  - CLI subcommands: `viveka demo run <WORLD_ID_OR_PATH>` and `viveka demo list`.
  - Zero target execution guarantee: `inspect`, `properties`, and `worlds` commands never import or execute target code.
- Phase 8: Trace, property evaluation, and reproduction engine.
  - Controlled vocabulary: `EvaluationVerdict` StrEnum (`VIOLATION`, `NO_OBSERVED_VIOLATION`, `INCONCLUSIVE`, `NOT_APPLICABLE`).
  - Domain models: `EvaluationEvidence` (using `RawEventType`), `EvaluationResult` (preserving `property_revision`), `ExecutionTrace` (preserving `ExecutionStatus`), `RuntimeCapabilityBinding`, `EvaluationContext`, `ReproductionPolicy` (enforcing `minimum_violations <= runs`), `ReproductionRun`, `ReproductionResult` (preserving `master_seed`, `seed_namespace`, `property_revision`, `criterion_met`).
  - Trace normalization (`normalize_trace`) converting `RuntimeResult` into `ExecutionTrace`, indexing tool calls and correlating results by `call_id`.
  - Property & world integrity checks (`PropertyNotApprovedError`, `PropertyWorldMismatchError`).
  - Deterministic exception resolvers (`resolve_allowed_exception`) for structured authorized exceptions (`explicit_user_authorization`, `human_approval`).
  - Output claim classifier interface (`OutputClaimClassifier`) and demo implementation (`DemoOutputClaimClassifier`).
  - Property evaluators: `FlowForbiddenEvaluator` (prohibited ordered sequence `sequence_source_result < sequence_sink_call`, sink invocation is violation, downstream denial attached as mitigating evidence) and `FailureHandledEvaluator` (uses classifier contract; free-form output returns `INCONCLUSIVE`).
  - Deterministic seed derivation (`derive_run_seed`) from `master_seed` + `seed_namespace` + `run_index` using SHA-256.
  - Reproduction engine (`execute_reproduction`) executing N runs, reporting raw K/N counts, and setting `criterion_met`.
  - Development CLI: `viveka evaluate <PROPERTY_ID> <WORLD_ID> [--runs INT] [--minimum-violations INT] [--seed INT] [--json]`.
- Phase 9: Counterexample shrinking & greedy world reduction.
  - Controlled vocabularies: `ReductionStepStatus`, `ReductionStrategy` StrEnums.
  - Domain models: `ReductionCandidate`, `ReductionStep`, `ReductionBudget`, `ReductionResult`.
  - Greedy shrinking engine (`ReductionEngine`) removing unnecessary documents, inputs, tool responses, environment vars, and state fields while preserving property violation.
  - Monotonicity and budget controls preventing unbounded search or expansion.
  - CLI command: `viveka reduce <PROPERTY_ID> <WORLD_ID> [--budget INT] [--json]`.
- Phase 10: Evidence-based diagnosis and behavioral regression memory.
  - Controlled vocabularies: `DiagnosisCategory`, `ConfidenceLevel`, `RegressionStatus` StrEnums.
  - Domain models: `DiagnosisEvidenceRef`, `Diagnosis`, `BehavioralRegression`, `ReplayReport`.
  - Deterministic diagnosis engine (`DiagnosisEngine`) mapping trace evidence to categorized failure causes without speculative commentary.
  - Durable behavioral regression storage (`RegressionStore`) with SHA-256 fingerprinting for replay integrity.
  - Replay engine (`ReplayEngine`) reproducing saved regressions using original seeds and policies with factual K/N reporting.
  - CLI subcommands: `viveka diagnose`, `viveka regression list/show`, `viveka replay <ID>`.
- Phase 11: Flagship verification orchestration engine.
  - Controlled vocabularies: `VerificationOutcome`, `PropertyVerificationStatus` StrEnums.
  - Domain models: `WorldVerificationDetail`, `PropertyVerificationResult`, `VerificationResult` with `schema_version: 1`.
  - End-to-end verification engine (`VerificationEngine`) orchestrating approved property filtering, test world derivation, runtime execution, property evaluation, failure reduction, root-cause diagnosis, and regression capture.
  - Standard exit code contract (0: clean, 1: violations reproduced, 2: config/no approved properties, 3: operational error).
  - Flagship CLI command: `viveka verify [PATH] [--property ID] [--no-regression] [--runs INT] [--minimum-violations INT] [--seed INT] [--max-worlds INT] [--target TARGET] [--json] [--junit PATH]`.
- Phase 12: Optional advisory intelligence & reasoning enrichment.
  - Protocol: `ReasoningProvider` supporting structured proposals and narrative enrichment.
  - Provider implementations: `OllamaProvider` (local), `OpenAICompatibleProvider` (API), and `FakeReasoningProvider` (offline testing).
  - Advisory call budget tracker (`AdvisoryBudgetTracker`) and prompt isolation separating untrusted target data from reasoning instructions.
  - Advisory assistants: `PropertySuggestionAdvisor`, `WorldSuggestionAdvisor`, `DiagnosisEnricher`.
  - Zero mandatory cost: `reasoning.mode = "none"` by default; all verification runs 100% offline and deterministic unless explicitly enabled.
  - CLI subcommands: `viveka suggest properties`, `viveka suggest worlds`, `viveka verify --enrich`.
- Phase 13: Generic HTTP / JSON runtime adapter.
  - `HttpJsonRuntimeAdapter` executing target agents over standard HTTP/JSON service boundaries.
  - Request payload structuring and JSON response parsing.
  - Strict HTTP status code mapping (2xx: OK/TARGET_ERROR based on payload, 3xx/4xx/5xx: `TARGET_ERROR`, network/serialization errors: `ADAPTER_ERROR`).
  - Security hardening: path traversal prevention, timeout enforcement, loopback isolation.
- Phase 14: Model Context Protocol (MCP) runtime adapter.
  - `McpRuntimeAdapter` executing targets via MCP stdio transport using official MCP Python SDK v2 (`mcp>=2.0.0,<3`).
  - Contained thread & private event loop bridge (`_run_async_in_contained_thread`) supporting synchronous execution from sync and active-event-loop contexts.
  - Exact single target invocation guarantee per `RuntimeRequest`.
  - Secure credential passing via `env_from_host` secret mapping without storing secrets in artifacts.
  - Proper mapping of interactive modes (elicitation/input-loops) to `UNSUPPORTED_FEATURE`.
- Phase 15: CI / JUnit / packaging / release hardening.
  - Modern PEP 639 license metadata (`license = "MIT"`, `license-files = ["LICENSE"]`).
  - Single source of truth versioning via `importlib.metadata` (distribution metadata driven).
  - Forward-compatible `schema_version: 1` in `VerificationResult`.
  - JUnit XML report generation (`viveka verify --junit path/to/report.xml`) with derived element counts and clean JSON+JUnit coexistence.
  - Standardized exit codes for `viveka replay` (0: criterion not met, 1: criterion met, 2: invalid/missing, 3: operational error).
  - GitHub Actions CI workflow (`ci.yml`) on Ubuntu/Windows with Python 3.12 and SHA-pinned actions.
  - GitHub Actions Release workflow (`release.yml`) with build-once architecture and PyPI OIDC Trusted Publishing.
  - Complete documentation suite (`RELEASING.md`, `docs/ci_integration.md`, updated `README.md`).
