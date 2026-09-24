"""
Regression tests for real-world LangGraph and SQLAlchemy application analysis.

Tests cover:
1. Virtual environment structural exclusion (.viveka-venv).
2. Source project scanned while venvs are excluded.
3. LangGraph framework detection.
4. add_node resolving registered local callables.
5. persist_plan receiving DATABASE_WRITE capability.
6. Database write classified as privileged/mutating sink.
7. Unrelated arbitrary .commit() / .add() not misclassified as DB writes.
8. ORM reads distinguished from writes.
9. Capability graph connecting LangGraph workflow to callable and capability.
10. Candidate Property produced when Phase 5 strong interaction is satisfied.
11. No candidate produced when graph evidence is insufficient.
12. Generated VIVEKA evidence/backups (.viveka/properties-backup, etc.) excluded.
13. Human-approval semantics preserved for candidate properties.
"""

from __future__ import annotations

from pathlib import Path

from viveka.capabilities.boundaries import infer_trust_boundaries
from viveka.capabilities.classifier import classify_capabilities
from viveka.capabilities.graph import build_capability_graph
from viveka.capabilities.models import CapabilityAnalysisResult
from viveka.capabilities.vocabulary import CapabilityTag, SideEffect, TrustRole
from viveka.inspection.analyzer import analyze_python_repository
from viveka.inspection.models import Decision
from viveka.inspection.scanner import scan_repository
from viveka.properties.engine import infer_candidate_properties
from viveka.properties.vocabulary import PropertyStatus


def _create_real_world_fixture(root: Path) -> Path:
    """Create a minimal real-world LangGraph + SQLAlchemy project structure."""
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)

    # Agent with StateGraph, retrieve_documents, and persist_plan
    (src / "agent.py").write_text(
        '''"""Onboarding Agent with LangGraph and SQLAlchemy."""
from langgraph.graph import StateGraph, END
from sqlalchemy.orm import sessionmaker, Session
from src.db import SessionLocal, PlanRecord
from chromadb import Client

def retrieve_documents(query: str) -> list[str]:
    """Retrieve documents from vectorstore."""
    client = Client()
    results = client.similarity_search(query)
    return [r.text for r in results]

def synthesize_plan_node(state: dict) -> dict:
    """Pure reasoning node."""
    return {"plan": "Synthesized summary"}

def persist_plan(state: dict) -> dict:
    """Persist generated onboarding plan into database."""
    db = SessionLocal()
    try:
        record = PlanRecord(title=state.get("title", "Plan"), content=state.get("plan", ""))
        db.add(record)
        db.flush()
        db.commit()
        return {"status": "persisted", "id": record.id}
    finally:
        db.close()

def build_workflow():
    """Construct LangGraph StateGraph."""
    workflow = StateGraph(dict)
    workflow.add_node("retrieve", retrieve_documents)
    workflow.add_node("synthesize", synthesize_plan_node)
    workflow.add_node("persist", persist_plan)
    workflow.add_edge("retrieve", "synthesize")
    workflow.add_edge("synthesize", "persist")
    workflow.set_entry_point("retrieve")
    return workflow.compile()
''',
        encoding="utf-8",
    )

    # Database setup file
    (src / "db.py").write_text(
        '''"""SQLAlchemy database models and session factory."""
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class PlanRecord(Base):
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    content = Column(String)

engine = create_engine("sqlite:///app.db")
SessionLocal = sessionmaker(bind=engine)

def get_plan(plan_id: int):
    """Read-only ORM query."""
    db = SessionLocal()
    try:
        return db.query(PlanRecord).filter_by(id=plan_id).first()
    finally:
        db.close()
''',
        encoding="utf-8",
    )

    # Virtual environment with custom name .viveka-venv
    venv_dir = root / ".viveka-venv"
    venv_dir.mkdir(parents=True, exist_ok=True)
    (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\nversion = 3.12.0\n", encoding="utf-8")
    scripts_dir = venv_dir / "Scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "python.exe").write_bytes(b"\x00\x00")
    site_packages = venv_dir / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)
    (site_packages / "some_lib.py").write_text("# library code\n", encoding="utf-8")

    # VIVEKA generated and backup artifacts
    viveka_props = root / ".viveka" / "properties"
    viveka_props.mkdir(parents=True, exist_ok=True)
    (viveka_props / "VPROP-001.yaml").write_text("id: VPROP-001\n", encoding="utf-8")

    viveka_backup = root / ".viveka" / "properties-backup"
    viveka_backup.mkdir(parents=True, exist_ok=True)
    (viveka_backup / "VPROP-001.yaml.bak").write_text("id: VPROP-001\n", encoding="utf-8")

    viveka_worlds = root / ".viveka" / "worlds"
    viveka_worlds.mkdir(parents=True, exist_ok=True)
    (viveka_worlds / "VWORLD-001.yaml").write_text("id: VWORLD-001\n", encoding="utf-8")

    (root / ".viveka" / "config.yaml").write_text("version: 1\n", encoding="utf-8")

    return root


class TestRealWorldAnalysis:
    def test_virtualenv_structural_exclusion(self, tmp_path: Path) -> None:
        """Requirement 1 & 2: .viveka-venv is excluded structurally; source files remain selected."""
        _create_real_world_fixture(tmp_path)
        summary = scan_repository(tmp_path)

        # Selected files must contain src/agent.py and src/db.py
        selected_rel = {f.relative_path for f in summary.selected_files}
        assert "src/agent.py" in selected_rel
        assert "src/db.py" in selected_rel

        # Files inside .viveka-venv must NOT be selected
        for f in summary.selected_files:
            assert not f.relative_path.startswith(".viveka-venv")

        # .viveka-venv must be in all_files as EXCLUDE
        venv_files = [f for f in summary.all_files if ".viveka-venv" in f.relative_path]
        assert len(venv_files) > 0
        assert all(f.decision == Decision.EXCLUDE for f in venv_files)

    def test_viveka_artifact_exclusion(self, tmp_path: Path) -> None:
        """Requirement 12: Generated VIVEKA artifacts/backups do not pollute source inspection."""
        _create_real_world_fixture(tmp_path)
        summary = scan_repository(tmp_path)

        selected_rel = {f.relative_path for f in summary.selected_files}
        # Backups and worlds must NOT be selected
        assert ".viveka/properties-backup/VPROP-001.yaml.bak" not in selected_rel
        assert ".viveka/worlds/VWORLD-001.yaml" not in selected_rel
        assert ".viveka/config.yaml" not in selected_rel

    def test_langgraph_framework_and_node_resolution(self, tmp_path: Path) -> None:
        """Requirements 3 & 4: LangGraph detected and add_node resolves registered callables."""
        _create_real_world_fixture(tmp_path)
        summary = scan_repository(tmp_path)
        static_res = analyze_python_repository(tmp_path, summary)

        # Framework detection
        fw_names = {h.framework_name for h in static_res.framework_hints}
        assert "LangGraph" in fw_names

        # Entrypoint detection
        stategraph_eps = [
            ep for ep in static_res.entrypoint_candidates if ep.entrypoint_type == "stategraph"
        ]
        assert len(stategraph_eps) >= 1

        # Check call positional_args
        agent_mod = next(m for m in static_res.modules if m.path == "src/agent.py")
        build_fn = next(f for f in agent_mod.functions if f.name == "build_workflow")
        add_node_calls = [c for c in build_fn.calls if "add_node" in c.callee]
        assert len(add_node_calls) == 3
        persist_call = next(c for c in add_node_calls if "persist" in c.positional_args[0])
        assert "persist_plan" in persist_call.positional_args[1]

    def test_sqlalchemy_database_write_capability(self, tmp_path: Path) -> None:
        """Requirements 5 & 6: persist_plan gets DATABASE_WRITE capability and is privileged sink."""
        _create_real_world_fixture(tmp_path)
        summary = scan_repository(tmp_path)
        static_res = analyze_python_repository(tmp_path, summary)
        caps, _ = classify_capabilities(static_res)

        # persist_plan must receive DATABASE_WRITE
        persist_cap = next(
            (
                c
                for c in caps
                if c.source_symbol == "persist_plan" and CapabilityTag.DATABASE_WRITE in c.tags
            ),
            None,
        )
        assert persist_cap is not None
        assert persist_cap.side_effect == SideEffect.MUTATING
        assert persist_cap.trust_role == TrustRole.PRIVILEGED_SINK
        assert any(CapabilityTag.WRITE in persist_cap.tags for _ in [1])
        assert any(CapabilityTag.SIDE_EFFECT in persist_cap.tags for _ in [1])

        # Trust boundaries
        boundaries = infer_trust_boundaries(caps)
        priv_sinks = [tb for tb in boundaries if tb.boundary_type == "privileged_sink"]
        assert any("persist_plan" in tb.destination for tb in priv_sinks)

    def test_unrelated_commit_not_misclassified(self, tmp_path: Path) -> None:
        """Requirement 7: Unrelated arbitrary .commit() or .add() calls are not misclassified."""
        (tmp_path / "helper.py").write_text(
            '''"""Unrelated helper without DB context."""
def process_items(items: list) -> set:
    s = set()
    for item in items:
        s.add(item)
    return s

class GitRepo:
    def commit(self, message: str):
        return f"committed {message}"
''',
            encoding="utf-8",
        )
        summary = scan_repository(tmp_path)
        static_res = analyze_python_repository(tmp_path, summary)
        caps, _ = classify_capabilities(static_res)

        # No DATABASE_WRITE on process_items or GitRepo.commit
        db_writes = [c for c in caps if CapabilityTag.DATABASE_WRITE in c.tags]
        assert len(db_writes) == 0

    def test_orm_reads_distinguishable_from_writes(self, tmp_path: Path) -> None:
        """Requirement 8: Read-only ORM queries (db.query(...).filter_by(...).first()) are not writes."""
        _create_real_world_fixture(tmp_path)
        summary = scan_repository(tmp_path)
        static_res = analyze_python_repository(tmp_path, summary)
        caps, _ = classify_capabilities(static_res)

        # get_plan must have DATABASE_READ but NOT DATABASE_WRITE
        get_plan_caps = [c for c in caps if c.source_symbol == "get_plan"]
        assert any(CapabilityTag.DATABASE_READ in c.tags for c in get_plan_caps)
        assert not any(CapabilityTag.DATABASE_WRITE in c.tags for c in get_plan_caps)

    def test_capability_graph_connects_langgraph_nodes(self, tmp_path: Path) -> None:
        """Requirement 9: CapabilityGraph contains edges connecting workflow node to callable/capability."""
        _create_real_world_fixture(tmp_path)
        summary = scan_repository(tmp_path)
        static_res = analyze_python_repository(tmp_path, summary)
        caps, _ = classify_capabilities(static_res)
        graph = build_capability_graph(static_res, caps)

        # Check graph edges
        exposes_edges = [e for e in graph.edges if e.edge_type == "exposes"]
        assert any("retrieve_documents" in e.evidence for e in exposes_edges)
        assert any("persist_plan" in e.evidence for e in exposes_edges)

        # Check workflow edge retrieve -> persist (via synthesize)
        workflow_calls_edges = [e for e in graph.edges if "LangGraph workflow edge" in e.evidence]
        assert len(workflow_calls_edges) >= 2

    def test_property_inference_under_strong_interaction(self, tmp_path: Path) -> None:
        """Requirements 10 & 13: Candidate Property produced under strong interaction; status is CANDIDATE."""
        _create_real_world_fixture(tmp_path)
        summary = scan_repository(tmp_path)
        static_res = analyze_python_repository(tmp_path, summary)
        caps, stats = classify_capabilities(static_res)
        boundaries = infer_trust_boundaries(caps)
        graph = build_capability_graph(static_res, caps)

        analysis = CapabilityAnalysisResult(
            project_root=str(tmp_path),
            capabilities=caps,
            trust_boundaries=boundaries,
            graph=graph,
            statistics=stats,
        )

        candidates = infer_candidate_properties(analysis)
        assert len(candidates) >= 1

        # Must find untrusted-input-cannot-modify-database rule targeting persist_plan
        db_prop = next(
            (p for p in candidates if "persist_plan" in p.name or "persist_plan" in p.stable_key),
            None,
        )
        assert db_prop is not None
        # Human approval contract: status MUST be candidate
        assert db_prop.status == PropertyStatus.CANDIDATE
        assert db_prop.oracle.evaluator_kind == "flow_forbidden"

    def test_no_candidate_when_graph_evidence_insufficient(self, tmp_path: Path) -> None:
        """Requirement 11 & 12: No candidate property produced when no directed graph path exists."""
        # Two disconnected files without shared workflow or reachability
        src = tmp_path / "src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "search.py").write_text(
            '''"""Isolated search tool."""
from chromadb import Client
def search_docs(q: str):
    c = Client()
    return c.similarity_search(q)
''',
            encoding="utf-8",
        )
        (src / "admin.py").write_text(
            '''"""Isolated admin script."""
from sqlalchemy.orm import sessionmaker
def purge_db():
    SessionLocal = sessionmaker()
    db = SessionLocal()
    db.execute("DELETE FROM logs")
    db.commit()
''',
            encoding="utf-8",
        )

        summary = scan_repository(tmp_path)
        static_res = analyze_python_repository(tmp_path, summary)
        caps, stats = classify_capabilities(static_res)
        boundaries = infer_trust_boundaries(caps)
        graph = build_capability_graph(static_res, caps)

        analysis = CapabilityAnalysisResult(
            project_root=str(tmp_path),
            capabilities=caps,
            trust_boundaries=boundaries,
            graph=graph,
            statistics=stats,
        )

        # In pure isolation without graph connection between search.py and admin.py:
        # Cross-module interaction without graph edge or entrypoint reachability produces 0 cross-file flow properties
        candidates = infer_candidate_properties(analysis)
        cross_props = [
            p for p in candidates if "search" in p.stable_key and "purge" in p.stable_key
        ]
        assert len(cross_props) == 0

    def test_db_query_not_retrieval(self, tmp_path: Path) -> None:
        """Requirement 1: db.query in get_employee does not match RETRIEVAL."""
        (tmp_path / "emp.py").write_text(
            '''"""Employee repository."""
from sqlalchemy.orm import Session
from src.db import PlanRecord

def get_employee(db: Session, emp_id: int):
    return db.query(PlanRecord).filter_by(id=emp_id).first()
''',
            encoding="utf-8",
        )
        summary = scan_repository(tmp_path)
        static_res = analyze_python_repository(tmp_path, summary)
        caps, _ = classify_capabilities(static_res)
        emp_caps = [c for c in caps if c.source_symbol == "get_employee"]
        assert not any(CapabilityTag.RETRIEVAL in c.tags for c in emp_caps)
        assert any(CapabilityTag.DATABASE_READ in c.tags for c in emp_caps)

    def test_state_get_not_network_read(self, tmp_path: Path) -> None:
        """Requirement 2: state.get dictionary lookup is not NETWORK_READ."""
        (tmp_path / "node.py").write_text(
            '''"""Dictionary reading node."""
def read_state(state: dict) -> str:
    return state.get("key", "default")
''',
            encoding="utf-8",
        )
        summary = scan_repository(tmp_path)
        static_res = analyze_python_repository(tmp_path, summary)
        caps, _ = classify_capabilities(static_res)
        assert not any(CapabilityTag.NETWORK_READ in c.tags for c in caps)

    def test_config_get_main_option_not_network_read(self, tmp_path: Path) -> None:
        """Requirement 3: config.get_main_option does not match NETWORK_READ."""
        (tmp_path / "alembic_env.py").write_text(
            '''"""Alembic environment config."""
class Config:
    def get_main_option(self, name: str) -> str:
        return "/path"

def run_env():
    config = Config()
    return config.get_main_option("script_location")
''',
            encoding="utf-8",
        )
        summary = scan_repository(tmp_path)
        static_res = analyze_python_repository(tmp_path, summary)
        caps, _ = classify_capabilities(static_res)
        assert not any(CapabilityTag.NETWORK_READ in c.tags for c in caps)

    def test_context_run_migrations_not_shell(self, tmp_path: Path) -> None:
        """Requirement 4: context.run_migrations is not SHELL_EXECUTION."""
        (tmp_path / "env.py").write_text(
            '''"""Migration runner."""
class Context:
    def run_migrations(self):
        pass

def run_migrations_online():
    context = Context()
    context.run_migrations()
''',
            encoding="utf-8",
        )
        summary = scan_repository(tmp_path)
        static_res = analyze_python_repository(tmp_path, summary)
        caps, _ = classify_capabilities(static_res)
        assert not any(CapabilityTag.SHELL_EXECUTION in c.tags for c in caps)

    def test_subprocess_run_is_shell(self, tmp_path: Path) -> None:
        """Requirement 5: Genuine subprocess.run is correctly classified as SHELL_EXECUTION."""
        (tmp_path / "shell_tool.py").write_text(
            '''"""Process execution tool."""
import subprocess

def run_bash_cmd(cmd: str):
    return subprocess.run(cmd, shell=True, check=True)
''',
            encoding="utf-8",
        )
        summary = scan_repository(tmp_path)
        static_res = analyze_python_repository(tmp_path, summary)
        caps, _ = classify_capabilities(static_res)
        shell_caps = [c for c in caps if c.source_symbol == "run_bash_cmd"]
        assert any(CapabilityTag.SHELL_EXECUTION in c.tags for c in shell_caps)

    def test_get_notifications_db_read_only(self, tmp_path: Path) -> None:
        """Requirement 6: get_notifications has DATABASE_READ but NOT DATABASE_WRITE or PRIVILEGED_SINK."""
        (tmp_path / "notif.py").write_text(
            '''"""Notification service."""
from sqlalchemy.orm import Session
from src.db import PlanRecord

def get_notifications(db: Session, user_id: int):
    return db.query(PlanRecord).filter_by(id=user_id).order_by(PlanRecord.id.desc()).all()
''',
            encoding="utf-8",
        )
        summary = scan_repository(tmp_path)
        static_res = analyze_python_repository(tmp_path, summary)
        caps, _ = classify_capabilities(static_res)
        notif_caps = [c for c in caps if c.source_symbol == "get_notifications"]
        assert any(CapabilityTag.DATABASE_READ in c.tags for c in notif_caps)
        assert not any(CapabilityTag.DATABASE_WRITE in c.tags for c in notif_caps)
        assert not any(c.trust_role == TrustRole.PRIVILEGED_SINK for c in notif_caps)

    def test_sibling_stategraph_nodes_no_property(self, tmp_path: Path) -> None:
        """Requirement 8: Sibling LangGraph nodes without directed edge do NOT produce property."""
        src = tmp_path / "src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "graph_branch.py").write_text(
            '''"""LangGraph with branching sibling nodes."""
from langgraph.graph import StateGraph
from chromadb import Client
from sqlalchemy.orm import Session
from src.db import SessionLocal, PlanRecord

def fetch_a(query: str):
    return Client().similarity_search(query)

def fetch_b(query: str):
    return Client().similarity_search(query)

def persist_branch_a(state: dict):
    db = SessionLocal()
    try:
        db.add(PlanRecord(title="A", content="A"))
        db.commit()
    finally:
        db.close()

def build_workflow():
    workflow = StateGraph(dict)
    workflow.add_node("node_fetch_a", fetch_a)
    workflow.add_node("node_fetch_b", fetch_b)
    workflow.add_node("node_persist_a", persist_branch_a)
    # fetch_a -> persist_branch_a (directed edge)
    workflow.add_edge("node_fetch_a", "node_persist_a")
    # fetch_b is a sibling node that never connects to persist_branch_a
    return workflow.compile()
''',
            encoding="utf-8",
        )
        summary = scan_repository(tmp_path)
        static_res = analyze_python_repository(tmp_path, summary)
        caps, stats = classify_capabilities(static_res)
        boundaries = infer_trust_boundaries(caps)
        graph = build_capability_graph(static_res, caps)

        analysis = CapabilityAnalysisResult(
            project_root=str(tmp_path),
            capabilities=caps,
            trust_boundaries=boundaries,
            graph=graph,
            statistics=stats,
        )

        candidates = infer_candidate_properties(analysis)
        # fetch_a -> persist_branch_a MUST produce property
        assert any(
            "fetch_a" in p.stable_key and "persist_branch_a" in p.stable_key for p in candidates
        )
        # fetch_b -> persist_branch_a MUST NOT produce property (no directed path)
        assert not any(
            "fetch_b" in p.stable_key and "persist_branch_a" in p.stable_key for p in candidates
        )

    def test_reverse_path_no_property(self, tmp_path: Path) -> None:
        """Requirement 10: Reverse direction (sink -> src) does not satisfy property interaction."""
        src = tmp_path / "src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "reverse_graph.py").write_text(
            '''"""Reverse directed workflow."""
from langgraph.graph import StateGraph
from chromadb import Client
from sqlalchemy.orm import Session
from src.db import SessionLocal, PlanRecord

def write_db(state: dict):
    db = SessionLocal()
    try:
        db.add(PlanRecord(title="init", content="init"))
        db.commit()
    finally:
        db.close()

def read_vectorstore(state: dict):
    return Client().similarity_search("query")

def build_workflow():
    workflow = StateGraph(dict)
    workflow.add_node("first_write", write_db)
    workflow.add_node("second_read", read_vectorstore)
    # Directed edge: write_db -> read_vectorstore
    workflow.add_edge("first_write", "second_read")
    return workflow.compile()
''',
            encoding="utf-8",
        )
        summary = scan_repository(tmp_path)
        static_res = analyze_python_repository(tmp_path, summary)
        caps, stats = classify_capabilities(static_res)
        boundaries = infer_trust_boundaries(caps)
        graph = build_capability_graph(static_res, caps)

        analysis = CapabilityAnalysisResult(
            project_root=str(tmp_path),
            capabilities=caps,
            trust_boundaries=boundaries,
            graph=graph,
            statistics=stats,
        )

        candidates = infer_candidate_properties(analysis)
        # Flow rule: untrusted_ingress (read_vectorstore) -> privileged_sink (write_db)
        # Since the directed graph only has write_db -> read_vectorstore, no flow property from read to write should exist
        assert not any(
            "read_vectorstore" in p.stable_key and "write_db" in p.stable_key for p in candidates
        )

    def test_conditional_edges_routing_interaction(self, tmp_path: Path) -> None:
        """Requirement 9: LangGraph add_conditional_edges connects ingress through router to sink."""
        src = tmp_path / "src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "conditional_graph.py").write_text(
            '''"""LangGraph conditional routing."""
from langgraph.graph import StateGraph, END
from chromadb import Client
from src.db import SessionLocal, PlanRecord

def fetch_data(q: str):
    return Client().similarity_search(q)

def route_next(state: dict) -> str:
    return "persist"

def persist_data(state: dict):
    db = SessionLocal()
    try:
        db.add(PlanRecord(title="data", content="data"))
        db.commit()
    finally:
        db.close()

def build_workflow():
    wf = StateGraph(dict)
    wf.add_node("fetch", fetch_data)
    wf.add_node("persist", persist_data)
    wf.add_conditional_edges("fetch", route_next, {"persist": "persist", "end": END})
    return wf.compile()
''',
            encoding="utf-8",
        )
        summary = scan_repository(tmp_path)
        static_res = analyze_python_repository(tmp_path, summary)
        caps, stats = classify_capabilities(static_res)
        boundaries = infer_trust_boundaries(caps)
        graph = build_capability_graph(static_res, caps)

        analysis = CapabilityAnalysisResult(
            project_root=str(tmp_path),
            capabilities=caps,
            trust_boundaries=boundaries,
            graph=graph,
            statistics=stats,
        )

        candidates = infer_candidate_properties(analysis)
        prop = next(
            (
                p
                for p in candidates
                if "fetch_data" in p.stable_key and "persist_data" in p.stable_key
            ),
            None,
        )
        assert prop is not None
        assert prop.status == PropertyStatus.CANDIDATE
