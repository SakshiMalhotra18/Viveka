"""
Data models for Python static analysis in VIVEKA.

Represents AST structures, imports, functions, classes, calls,
heuristic framework hints, tool candidates, and entrypoint candidates.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ParameterKind(StrEnum):
    """Category of function parameter."""

    POSITIONAL_ONLY = "positional_only"
    POSITIONAL_OR_KEYWORD = "positional_or_keyword"
    VAR_POSITIONAL = "var_positional"
    KEYWORD_ONLY = "keyword_only"
    VAR_KEYWORD = "var_keyword"


class Confidence(StrEnum):
    """Confidence level for heuristic detections."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PythonImport(BaseModel):
    """An import statement in a Python module."""

    module: str = Field(description="Imported module path or base (e.g. 'langgraph.graph').")
    imported_name: str = Field(description="Name imported from the module, or empty string.")
    alias: str | None = Field(
        default=None, description="Import alias (e.g. 'np' in 'import numpy as np')."
    )
    relative_level: int = Field(
        default=0, ge=0, description="Relative import dot count (e.g. 1 for '.tools')."
    )
    line: int = Field(ge=1, description="Line number where the import occurs.")
    is_from_import: bool = Field(
        default=False, description="Whether this is a 'from ... import' statement."
    )


class PythonParameter(BaseModel):
    """A parameter of a Python function or method."""

    name: str = Field(description="Parameter name.")
    kind: ParameterKind = Field(description="Parameter kind.")
    has_default: bool = Field(default=False, description="Whether a default value is present.")
    type_annotation: str | None = Field(
        default=None, description="Statically recovered type annotation text."
    )


class DecoratorInfo(BaseModel):
    """A decorator applied to a function or class."""

    name: str = Field(
        description="Normalized decorator name (e.g. 'tool', 'app.post', 'mcp.tool')."
    )
    raw_text: str = Field(description="Decorator expression text.")
    line: int = Field(ge=1, description="Line number of the decorator.")


class PythonCall(BaseModel):
    """A statically referenced call expression."""

    callee: str = Field(
        description="Normalized callee representation (e.g. 'refund_order', 'client.send')."
    )
    line: int = Field(ge=1, description="Line number where call occurs.")
    containing_symbol: str | None = Field(
        default=None, description="Enclosing function or class name."
    )
    argument_count: int = Field(ge=0, description="Number of positional arguments.")
    keyword_names: list[str] = Field(
        default_factory=list, description="Names of keyword arguments."
    )


class PythonFunction(BaseModel):
    """A function or method definition."""

    name: str = Field(description="Function name.")
    qualified_name: str = Field(description="Scoped name (e.g. 'RefundService.create_refund').")
    line_start: int = Field(ge=1, description="Starting line number.")
    line_end: int = Field(ge=1, description="Ending line number.")
    parameters: list[PythonParameter] = Field(default_factory=list, description="Parameter list.")
    decorators: list[DecoratorInfo] = Field(default_factory=list, description="Decorators.")
    is_async: bool = Field(default=False, description="Whether this is an async function.")
    return_annotation: str | None = Field(default=None, description="Return type annotation text.")
    docstring_summary: str | None = Field(
        default=None, description="First line or brief docstring summary."
    )
    calls: list[PythonCall] = Field(
        default_factory=list, description="Calls made inside this function."
    )


class PythonClass(BaseModel):
    """A class definition."""

    name: str = Field(description="Class name.")
    qualified_name: str = Field(description="Scoped name.")
    line_start: int = Field(ge=1, description="Starting line number.")
    line_end: int = Field(ge=1, description="Ending line number.")
    bases: list[str] = Field(default_factory=list, description="Base class expressions.")
    decorators: list[DecoratorInfo] = Field(default_factory=list, description="Decorators.")
    methods: list[PythonFunction] = Field(
        default_factory=list, description="Methods defined in class."
    )


class ParseFailure(BaseModel):
    """A failure encountered while attempting to parse a Python file."""

    file_path: str = Field(description="Relative path of the malformed file.")
    error_type: str = Field(description="Error type (e.g. 'SyntaxError').")
    message: str = Field(description="Error description.")
    line: int | None = Field(default=None, description="Line number where syntax error occurred.")
    column: int | None = Field(
        default=None, description="Column number where syntax error occurred."
    )


class PythonModule(BaseModel):
    """Structural static analysis representation of a Python source file."""

    path: str = Field(description="Project-relative POSIX path (e.g. 'src/agent.py').")
    module_name: str = Field(description="Inferred Python dotted module name (e.g. 'src.agent').")
    parse_status: str = Field(description="'ok', 'parse_failed', or 'empty'.")
    syntax_error: ParseFailure | None = Field(
        default=None, description="Syntax error details if parse failed."
    )
    imports: list[PythonImport] = Field(default_factory=list, description="Imports in this module.")
    functions: list[PythonFunction] = Field(
        default_factory=list, description="Top-level functions."
    )
    classes: list[PythonClass] = Field(default_factory=list, description="Top-level classes.")
    calls: list[PythonCall] = Field(default_factory=list, description="Top-level module calls.")
    docstring_summary: str | None = Field(
        default=None, description="Module-level docstring summary."
    )


class FrameworkHint(BaseModel):
    """Heuristic evidence of an AI or web framework in the project."""

    framework_name: str = Field(description="Name of framework (e.g. 'LangGraph', 'FastAPI').")
    confidence: Confidence = Field(description="Confidence level.")
    evidence: list[str] = Field(
        default_factory=list, description="Concrete file:line evidence items."
    )


class ToolCandidate(BaseModel):
    """A statically detected symbol that looks like an agent tool."""

    symbol_name: str = Field(description="Function or symbol name.")
    qualified_name: str = Field(description="Scoped symbol name.")
    file_path: str = Field(description="Project-relative path.")
    line: int = Field(ge=1, description="Line number.")
    decorator_name: str | None = Field(
        default=None, description="Decorator name if tool decorator was found."
    )
    evidence: str = Field(description="Human-readable reason for detection.")
    confidence: Confidence = Field(description="Confidence level.")


class EntryPointCandidate(BaseModel):
    """A statically detected symbol or route that looks like an application entrypoint."""

    entrypoint_type: str = Field(
        description="'fastapi_route', 'stategraph', 'agent_runner', 'mcp_server', 'cli_main'."
    )
    symbol_or_path: str = Field(description="Function name, route string, or module name.")
    file_path: str = Field(description="Project-relative path.")
    line: int = Field(ge=1, description="Line number.")
    route_method: str | None = Field(
        default=None, description="HTTP method if route (e.g. 'POST')."
    )
    route_path: str | None = Field(default=None, description="HTTP route path (e.g. '/chat').")
    evidence: str = Field(description="Human-readable reason for detection.")
    confidence: Confidence = Field(description="Confidence level.")


class LocalImportEdge(BaseModel):
    """A directed static import edge between two project modules."""

    source_file: str = Field(description="Relative path of the importing module.")
    target_file: str = Field(description="Relative path of the imported module.")
    imported_symbol: str = Field(description="Symbol or submodule name imported.")


class StaticAnalysisResult(BaseModel):
    """Aggregated structural static analysis of a Python repository."""

    project_root: str = Field(description="Absolute path to inspected repository root.")
    files_analyzed: int = Field(ge=0, description="Total Python files parsed.")
    modules: list[PythonModule] = Field(
        default_factory=list, description="Per-module AST representations."
    )
    local_import_edges: list[LocalImportEdge] = Field(
        default_factory=list, description="Local intra-project import relationships."
    )
    external_imports: list[str] = Field(
        default_factory=list, description="Unique external packages imported."
    )
    framework_hints: list[FrameworkHint] = Field(
        default_factory=list, description="Detected framework hints."
    )
    tool_candidates: list[ToolCandidate] = Field(
        default_factory=list, description="Detected tool candidate symbols."
    )
    entrypoint_candidates: list[EntryPointCandidate] = Field(
        default_factory=list, description="Detected entrypoint candidates."
    )
    parse_failures: list[ParseFailure] = Field(
        default_factory=list, description="Files that failed syntax parsing."
    )
    total_functions: int = Field(ge=0, description="Total functions and methods discovered.")
    total_classes: int = Field(ge=0, description="Total classes discovered.")
    total_imports: int = Field(ge=0, description="Total import statements.")
    total_calls: int = Field(ge=0, description="Total static calls recorded.")
