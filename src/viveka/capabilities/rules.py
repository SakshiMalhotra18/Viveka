"""
Deterministic, static-only capability classification rules for VIVEKA Phase 4.

Each :class:`CapabilityRule` defines:
  - Patterns to match against calls, imports, decorator names, and symbol names.
  - The tags, side-effect, externality, trust-role, and reversibility it produces.
  - A confidence level for this rule's classification.
  - An explanation of its detection rationale.

Rules are evaluated purely against static structural evidence from Phase 3
(:class:`~viveka.inspection.python_models.StaticAnalysisResult`).

No LLMs are used.  No target code is executed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from viveka.capabilities.vocabulary import (
    CapabilityTag,
    Externality,
    Reversibility,
    SideEffect,
    TrustRole,
)


@dataclass(frozen=True)
class CapabilityRule:
    """A single deterministic capability classification rule.

    Matching is performed by the :mod:`~viveka.capabilities.classifier` against
    Phase 3 evidence; this dataclass is **pure data** — no matching logic lives
    here.

    Attributes:
        id:               Unique rule identifier (e.g. ``"RULE-FS-READ-001"``).
        call_patterns:    Substrings to match against normalized call expressions.
        import_patterns:  Substrings to match against import module paths.
        name_patterns:    Substrings to match against function/symbol names.
        decorator_patterns: Substrings to match against decorator names.
        produced_tags:    Tags to assign when this rule fires.
        side_effect:      Side-effect classification produced by this rule.
        externality:      Externality classification produced by this rule.
        trust_role:       Trust role produced by this rule.
        reversibility:    Reversibility produced by this rule.
        confidence:       Confidence level for this rule.
        explanation:      Human-readable rationale for the rule.
    """

    id: str
    call_patterns: tuple[str, ...] = field(default_factory=tuple)
    import_patterns: tuple[str, ...] = field(default_factory=tuple)
    name_patterns: tuple[str, ...] = field(default_factory=tuple)
    decorator_patterns: tuple[str, ...] = field(default_factory=tuple)
    produced_tags: tuple[CapabilityTag, ...] = field(default_factory=tuple)
    side_effect: SideEffect = SideEffect.UNKNOWN
    externality: Externality = Externality.UNKNOWN
    trust_role: TrustRole = TrustRole.UNKNOWN
    reversibility: Reversibility = Reversibility.UNKNOWN
    confidence: str = "medium"
    explanation: str = ""


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------

RULES: tuple[CapabilityRule, ...] = (
    # ------------------------------------------------------------------
    # Filesystem
    # ------------------------------------------------------------------
    CapabilityRule(
        id="RULE-FS-READ-001",
        call_patterns=("open(", "read(", "readline", "readlines", "read_text", "read_bytes"),
        import_patterns=("pathlib", "io", "builtins"),
        name_patterns=("read_file", "load_file", "open_file", "read_document"),
        produced_tags=(CapabilityTag.FILESYSTEM_READ, CapabilityTag.READ),
        side_effect=SideEffect.READ_ONLY,
        externality=Externality.LOCAL,
        trust_role=TrustRole.TRUSTED_INTERNAL,
        reversibility=Reversibility.REVERSIBLE,
        confidence="high",
        explanation=(
            "Detected filesystem read via open(), read(), read_text(), or read_bytes(). "
            "Pathlib or io imports corroborate the classification."
        ),
    ),
    CapabilityRule(
        id="RULE-FS-WRITE-001",
        call_patterns=("write(", "write_text(", "write_bytes(", "writelines(", "open("),
        import_patterns=("pathlib", "io", "builtins", "shutil"),
        name_patterns=("write_file", "save_file", "write_document", "store_file"),
        produced_tags=(
            CapabilityTag.FILESYSTEM_WRITE,
            CapabilityTag.WRITE,
            CapabilityTag.SIDE_EFFECT,
        ),
        side_effect=SideEffect.MUTATING,
        externality=Externality.LOCAL,
        trust_role=TrustRole.PRIVILEGED_SINK,
        reversibility=Reversibility.POSSIBLY_REVERSIBLE,
        confidence="high",
        explanation=(
            "Detected filesystem write via write(), write_text(), or write_bytes(). "
            "File mutation is a side effect."
        ),
    ),
    CapabilityRule(
        id="RULE-FS-DEL-001",
        call_patterns=(
            "os.remove(",
            "os.unlink(",
            "shutil.rmtree(",
            "Path.unlink(",
            ".unlink(",
            "rmtree(",
            "remove(",
            "unlink(",
        ),
        import_patterns=("os", "shutil", "pathlib"),
        name_patterns=("delete_file", "remove_file", "delete_directory", "purge"),
        produced_tags=(
            CapabilityTag.FILESYSTEM_DELETE,
            CapabilityTag.DESTRUCTIVE_WRITE,
            CapabilityTag.SIDE_EFFECT,
        ),
        side_effect=SideEffect.DESTRUCTIVE,
        externality=Externality.LOCAL,
        trust_role=TrustRole.PRIVILEGED_SINK,
        reversibility=Reversibility.IRREVERSIBLE,
        confidence="high",
        explanation=(
            "Detected destructive filesystem operation: os.remove(), os.unlink(), "
            "shutil.rmtree(), or Path.unlink()."
        ),
    ),
    # ------------------------------------------------------------------
    # Process / Code Execution
    # ------------------------------------------------------------------
    CapabilityRule(
        id="RULE-PROC-SHELL-001",
        call_patterns=(
            "subprocess.run(",
            "subprocess.call(",
            "subprocess.Popen(",
            "os.system(",
            "os.popen(",
            "os.execv(",
            "os.execve(",
            "run(",
            "Popen(",
        ),
        import_patterns=("subprocess", "os"),
        name_patterns=("run_command", "execute_command", "run_shell", "shell_exec", "run_process"),
        produced_tags=(CapabilityTag.SHELL_EXECUTION, CapabilityTag.SIDE_EFFECT),
        side_effect=SideEffect.MUTATING,
        externality=Externality.LOCAL,
        trust_role=TrustRole.PRIVILEGED_SINK,
        reversibility=Reversibility.UNKNOWN,
        confidence="high",
        explanation=(
            "Detected shell/process execution via subprocess or os.system(). "
            "Shell execution is a highly privileged action."
        ),
    ),
    CapabilityRule(
        id="RULE-PROC-EVAL-001",
        call_patterns=("eval(", "exec(", "compile(", "__import__("),
        import_patterns=(),
        name_patterns=("eval_code", "execute_code", "run_code", "eval_expression"),
        produced_tags=(CapabilityTag.CODE_EXECUTION, CapabilityTag.SIDE_EFFECT),
        side_effect=SideEffect.MUTATING,
        externality=Externality.LOCAL,
        trust_role=TrustRole.PRIVILEGED_SINK,
        reversibility=Reversibility.UNKNOWN,
        confidence="high",
        explanation=(
            "Detected dynamic code execution via eval(), exec(), compile(), or __import__(). "
            "These constructs execute arbitrary Python code."
        ),
    ),
    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------
    CapabilityRule(
        id="RULE-NET-GET-001",
        call_patterns=(
            "requests.get(",
            "httpx.get(",
            "aiohttp.ClientSession(",
            "urllib.request",
            ".get(",
            "fetch(",
            "urlopen(",
        ),
        import_patterns=("requests", "httpx", "aiohttp", "urllib", "urllib.request"),
        name_patterns=("fetch_data", "get_data", "fetch_url", "http_get", "download"),
        produced_tags=(
            CapabilityTag.NETWORK_READ,
            CapabilityTag.EXTERNAL_READ,
            CapabilityTag.RETRIEVAL,
        ),
        side_effect=SideEffect.READ_ONLY,
        externality=Externality.EXTERNAL,
        trust_role=TrustRole.UNTRUSTED_INGRESS,
        reversibility=Reversibility.REVERSIBLE,
        confidence="medium",
        explanation=(
            "Detected outbound HTTP GET or network read. Data fetched from external "
            "sources is untrusted ingress."
        ),
    ),
    CapabilityRule(
        id="RULE-NET-POST-001",
        call_patterns=(
            "requests.post(",
            "httpx.post(",
            "requests.put(",
            "requests.patch(",
            "requests.delete(",
            "httpx.put(",
            "httpx.patch(",
            ".post(",
            ".put(",
            ".patch(",
        ),
        import_patterns=("requests", "httpx", "aiohttp"),
        name_patterns=("send_data", "post_data", "http_post", "upload_data", "submit"),
        produced_tags=(
            CapabilityTag.NETWORK_WRITE,
            CapabilityTag.EXTERNAL_WRITE,
            CapabilityTag.SIDE_EFFECT,
        ),
        side_effect=SideEffect.MUTATING,
        externality=Externality.EXTERNAL,
        trust_role=TrustRole.EXTERNAL_SINK,
        reversibility=Reversibility.UNKNOWN,
        confidence="medium",
        explanation=(
            "Detected outbound HTTP POST/PUT/PATCH/DELETE. Sending data to external "
            "systems is an external sink with side effects."
        ),
    ),
    # ------------------------------------------------------------------
    # Communication
    # ------------------------------------------------------------------
    CapabilityRule(
        id="RULE-COMM-EMAIL-001",
        call_patterns=(
            "smtplib.SMTP(",
            "sendmail(",
            "send_email(",
            "send_message(",
            "MIMEText(",
            "MIMEMultipart(",
        ),
        import_patterns=("smtplib", "email", "sendgrid", "mailchimp", "boto3"),
        name_patterns=(
            "send_email",
            "send_message",
            "send_notification",
            "notify_user",
            "email_user",
        ),
        produced_tags=(
            CapabilityTag.COMMUNICATION,
            CapabilityTag.EXTERNAL_WRITE,
            CapabilityTag.SIDE_EFFECT,
        ),
        side_effect=SideEffect.MUTATING,
        externality=Externality.EXTERNAL,
        trust_role=TrustRole.EXTERNAL_SINK,
        reversibility=Reversibility.IRREVERSIBLE,
        confidence="high",
        explanation=(
            "Detected email or messaging capability via smtplib, sendgrid, or similar. "
            "Sending communications is irreversible."
        ),
    ),
    # ------------------------------------------------------------------
    # Financial
    # ------------------------------------------------------------------
    CapabilityRule(
        id="RULE-FIN-REFUND-001",
        call_patterns=("refund(", "create_refund(", "reverse_charge(", "reverse_payment("),
        import_patterns=("stripe", "braintree", "paypal", "adyen"),
        name_patterns=(
            "refund",
            "refund_order",
            "create_refund",
            "process_refund",
            "reverse_payment",
        ),
        produced_tags=(
            CapabilityTag.FINANCIAL_WRITE,
            CapabilityTag.SIDE_EFFECT,
            CapabilityTag.DESTRUCTIVE_WRITE,
        ),
        side_effect=SideEffect.MUTATING,
        externality=Externality.EXTERNAL,
        trust_role=TrustRole.PRIVILEGED_SINK,
        reversibility=Reversibility.IRREVERSIBLE,
        confidence="high",
        explanation=(
            "Detected financial refund capability. Refund operations mutate external "
            "financial state irreversibly."
        ),
    ),
    CapabilityRule(
        id="RULE-FIN-PAY-001",
        call_patterns=("charge(", "create_payment(", "create_charge(", "payment_intent(", "pay("),
        import_patterns=("stripe", "braintree", "paypal", "adyen", "square"),
        name_patterns=("charge_card", "process_payment", "create_charge", "make_payment", "pay"),
        produced_tags=(
            CapabilityTag.FINANCIAL_WRITE,
            CapabilityTag.SIDE_EFFECT,
        ),
        side_effect=SideEffect.MUTATING,
        externality=Externality.EXTERNAL,
        trust_role=TrustRole.PRIVILEGED_SINK,
        reversibility=Reversibility.POSSIBLY_REVERSIBLE,
        confidence="high",
        explanation=(
            "Detected payment/charge capability. Financial write operations require "
            "privileged credentials and touch external payment systems."
        ),
    ),
    # ------------------------------------------------------------------
    # Retrieval / Vector Search
    # ------------------------------------------------------------------
    CapabilityRule(
        id="RULE-RET-SEARCH-001",
        call_patterns=(
            "similarity_search(",
            "search(",
            "query(",
            "retrieve(",
            "as_retriever(",
            "vectorstore.search(",
            "chroma",
            "pinecone",
        ),
        import_patterns=("chromadb", "pinecone", "weaviate", "qdrant", "faiss", "langchain"),
        name_patterns=("search", "retrieve", "lookup", "query_documents", "find_similar"),
        produced_tags=(
            CapabilityTag.RETRIEVAL,
            CapabilityTag.READ,
            CapabilityTag.UNTRUSTED_INPUT,
        ),
        side_effect=SideEffect.READ_ONLY,
        externality=Externality.LOCAL,
        trust_role=TrustRole.UNTRUSTED_INGRESS,
        reversibility=Reversibility.REVERSIBLE,
        confidence="medium",
        explanation=(
            "Detected retrieval / vector search capability. Retrieved data is untrusted "
            "ingress that flows into the agent context."
        ),
    ),
    # ------------------------------------------------------------------
    # Secrets / Environment
    # ------------------------------------------------------------------
    CapabilityRule(
        id="RULE-SEC-ENV-001",
        call_patterns=("os.environ[", "os.getenv(", "os.environ.get(", "environ["),
        import_patterns=("os", "dotenv", "decouple"),
        name_patterns=("get_secret", "load_secret", "get_api_key", "get_token", "get_credentials"),
        produced_tags=(
            CapabilityTag.SECRET_ACCESS,
            CapabilityTag.SENSITIVE_READ,
        ),
        side_effect=SideEffect.READ_ONLY,
        externality=Externality.LOCAL,
        trust_role=TrustRole.SENSITIVE_SOURCE,
        reversibility=Reversibility.REVERSIBLE,
        confidence="medium",
        explanation=(
            "Detected environment variable / secret access. Secret-reading functions "
            "are sensitive sources that supply credentials to other capabilities."
        ),
    ),
    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    CapabilityRule(
        id="RULE-DB-WRITE-001",
        call_patterns=(
            ".save(",
            ".create(",
            ".update(",
            ".delete(",
            ".insert(",
            "session.add(",
            "session.commit(",
            "cursor.execute(",
            "INSERT ",
            "UPDATE ",
            "DELETE ",
        ),
        import_patterns=("sqlalchemy", "sqlite3", "psycopg2", "pymongo", "motor", "django.db"),
        name_patterns=("save_record", "create_record", "update_record", "delete_record", "upsert"),
        produced_tags=(
            CapabilityTag.DATABASE_WRITE,
            CapabilityTag.WRITE,
            CapabilityTag.SIDE_EFFECT,
        ),
        side_effect=SideEffect.MUTATING,
        externality=Externality.LOCAL,
        trust_role=TrustRole.PRIVILEGED_SINK,
        reversibility=Reversibility.POSSIBLY_REVERSIBLE,
        confidence="medium",
        explanation=(
            "Detected database write/mutation operations via ORM session, cursor.execute(), "
            "or similar. DB writes are privileged sinks."
        ),
    ),
    CapabilityRule(
        id="RULE-DB-READ-001",
        call_patterns=(
            ".filter(",
            ".query(",
            ".find(",
            ".find_one(",
            ".fetchall(",
            ".fetchone(",
            "SELECT ",
            "cursor.execute(",
        ),
        import_patterns=("sqlalchemy", "sqlite3", "psycopg2", "pymongo", "motor", "django.db"),
        name_patterns=("get_record", "fetch_record", "query_db", "find_record", "lookup_record"),
        produced_tags=(
            CapabilityTag.DATABASE_READ,
            CapabilityTag.READ,
        ),
        side_effect=SideEffect.READ_ONLY,
        externality=Externality.LOCAL,
        trust_role=TrustRole.SENSITIVE_SOURCE,
        reversibility=Reversibility.REVERSIBLE,
        confidence="medium",
        explanation=(
            "Detected database read operations via ORM filter/query, cursor.execute(), "
            "or raw SELECT. DB reads are sensitive sources."
        ),
    ),
    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------
    CapabilityRule(
        id="RULE-FALLBACK-001",
        call_patterns=(),
        import_patterns=(),
        name_patterns=(),
        decorator_patterns=(),
        produced_tags=(CapabilityTag.UNKNOWN,),
        side_effect=SideEffect.UNKNOWN,
        externality=Externality.UNKNOWN,
        trust_role=TrustRole.UNKNOWN,
        reversibility=Reversibility.UNKNOWN,
        confidence="low",
        explanation=(
            "No specific capability rule matched. Capability is unknown based on "
            "available static evidence."
        ),
    ),
)

# Indexed by rule ID for fast lookup
RULES_BY_ID: dict[str, CapabilityRule] = {r.id: r for r in RULES}
