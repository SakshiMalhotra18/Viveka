"""
Shared fixtures for capability tests.

Provides factory helpers for constructing minimal Phase 3 model objects
without touching the real AST parser or filesystem.
"""

from __future__ import annotations

from viveka.inspection.python_models import (
    DecoratorInfo,
    PythonCall,
    PythonFunction,
    PythonImport,
    PythonModule,
    StaticAnalysisResult,
    ToolCandidate,
)


def make_import(module: str, line: int = 1) -> PythonImport:
    return PythonImport(
        module=module,
        imported_name="",
        line=line,
        is_from_import=False,
    )


def make_call(callee: str, line: int = 5, symbol: str | None = None) -> PythonCall:
    return PythonCall(
        callee=callee,
        line=line,
        containing_symbol=symbol,
        argument_count=1,
        keyword_names=[],
    )


def make_decorator(name: str, line: int = 2) -> DecoratorInfo:
    return DecoratorInfo(name=name, raw_text=f"@{name}", line=line)


def make_function(
    name: str,
    qualified_name: str | None = None,
    line_start: int = 3,
    line_end: int = 10,
    calls: list[PythonCall] | None = None,
    decorators: list[DecoratorInfo] | None = None,
    is_async: bool = False,
) -> PythonFunction:
    return PythonFunction(
        name=name,
        qualified_name=qualified_name or name,
        line_start=line_start,
        line_end=line_end,
        parameters=[],
        decorators=decorators or [],
        is_async=is_async,
        calls=calls or [],
    )


def make_module(
    path: str,
    module_name: str,
    functions: list[PythonFunction] | None = None,
    imports: list[PythonImport] | None = None,
) -> PythonModule:
    return PythonModule(
        path=path,
        module_name=module_name,
        parse_status="ok",
        functions=functions or [],
        imports=imports or [],
    )


def make_static_result(
    modules: list[PythonModule] | None = None,
    tool_candidates: list[ToolCandidate] | None = None,
) -> StaticAnalysisResult:
    mods = modules or []
    total_funcs = sum(len(m.functions) for m in mods)
    total_imports = sum(len(m.imports) for m in mods)
    return StaticAnalysisResult(
        project_root="/fake/repo",
        files_analyzed=len(mods),
        modules=mods,
        tool_candidates=tool_candidates or [],
        total_functions=total_funcs,
        total_classes=0,
        total_imports=total_imports,
        total_calls=0,
    )
