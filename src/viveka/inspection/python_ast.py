"""
AST parser and structural extractor for Python source files.

Uses standard library ast.parse() to safely extract structural metadata
without executing or importing any target code.
"""

from __future__ import annotations

import ast
from pathlib import Path

from viveka.inspection.python_models import (
    DecoratorInfo,
    ParameterKind,
    ParseFailure,
    PythonCall,
    PythonClass,
    PythonFunction,
    PythonImport,
    PythonModule,
    PythonParameter,
)


def infer_module_name(rel_path: str) -> str:
    """Infer a dotted Python module name from a project-relative POSIX path."""
    clean = rel_path.replace("\\", "/").lstrip("./")
    if clean.endswith(".py"):
        clean = clean[:-3]
    parts = clean.split("/")
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) if parts else "root"


def extract_docstring_summary(node: ast.AST, max_length: int = 120) -> str | None:
    """Extract and truncate the first line of a docstring."""
    doc = ast.get_docstring(node)
    if not doc:
        return None
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:max_length]
    return None


def normalize_callee(node: ast.expr) -> str:
    """Normalize a function or method call expression to a readable string."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        value_str = normalize_callee(node.value)
        return f"{value_str}.{node.attr}"
    if isinstance(node, ast.Call):
        return normalize_callee(node.func)
    try:
        return ast.unparse(node)
    except Exception:
        return "<complex_call>"


def normalize_decorator(node: ast.expr) -> DecoratorInfo:
    """Normalize a decorator expression into structured DecoratorInfo."""
    line = getattr(node, "lineno", 1)
    try:
        raw_text = ast.unparse(node)
    except Exception:
        raw_text = "<decorator>"

    if isinstance(node, ast.Call):
        norm_name = normalize_callee(node.func)
    elif isinstance(node, (ast.Name, ast.Attribute)):
        norm_name = normalize_callee(node)
    else:
        norm_name = raw_text

    return DecoratorInfo(name=norm_name, raw_text=raw_text, line=line)


def extract_parameters(args_node: ast.arguments) -> list[PythonParameter]:
    """Extract structured parameter information from an ast.arguments node."""
    params: list[PythonParameter] = []

    # Positional-only parameters
    num_posonly = len(args_node.posonlyargs)
    num_pos_args = len(args_node.args)
    num_pos_defaults = len(args_node.defaults)

    # Defaults align to the end of (posonlyargs + args)
    default_offset = (num_posonly + num_pos_args) - num_pos_defaults

    # 1. Positional-only args
    for idx, arg in enumerate(args_node.posonlyargs):
        has_def = idx >= default_offset
        ann_text = None
        if arg.annotation is not None:
            try:
                ann_text = ast.unparse(arg.annotation)
            except Exception:
                ann_text = "<type>"
        params.append(
            PythonParameter(
                name=arg.arg,
                kind=ParameterKind.POSITIONAL_ONLY,
                has_default=has_def,
                type_annotation=ann_text,
            )
        )

    # 2. Positional or keyword args
    for idx, arg in enumerate(args_node.args):
        overall_idx = num_posonly + idx
        has_def = overall_idx >= default_offset
        ann_text = None
        if arg.annotation is not None:
            try:
                ann_text = ast.unparse(arg.annotation)
            except Exception:
                ann_text = "<type>"
        params.append(
            PythonParameter(
                name=arg.arg,
                kind=ParameterKind.POSITIONAL_OR_KEYWORD,
                has_default=has_def,
                type_annotation=ann_text,
            )
        )

    # 3. *args
    if args_node.vararg is not None:
        ann_text = None
        if args_node.vararg.annotation is not None:
            try:
                ann_text = ast.unparse(args_node.vararg.annotation)
            except Exception:
                ann_text = "<type>"
        params.append(
            PythonParameter(
                name=args_node.vararg.arg,
                kind=ParameterKind.VAR_POSITIONAL,
                has_default=False,
                type_annotation=ann_text,
            )
        )

    # 4. Keyword-only args
    for idx, arg in enumerate(args_node.kwonlyargs):
        has_def = False
        if idx < len(args_node.kw_defaults):
            has_def = args_node.kw_defaults[idx] is not None
        ann_text = None
        if arg.annotation is not None:
            try:
                ann_text = ast.unparse(arg.annotation)
            except Exception:
                ann_text = "<type>"
        params.append(
            PythonParameter(
                name=arg.arg,
                kind=ParameterKind.KEYWORD_ONLY,
                has_default=has_def,
                type_annotation=ann_text,
            )
        )

    # 5. **kwargs
    if args_node.kwarg is not None:
        ann_text = None
        if args_node.kwarg.annotation is not None:
            try:
                ann_text = ast.unparse(args_node.kwarg.annotation)
            except Exception:
                ann_text = "<type>"
        params.append(
            PythonParameter(
                name=args_node.kwarg.arg,
                kind=ParameterKind.VAR_KEYWORD,
                has_default=False,
                type_annotation=ann_text,
            )
        )

    return params


def extract_calls(
    body_nodes: list[ast.stmt], containing_symbol: str | None = None
) -> list[PythonCall]:
    """Find all Call expressions within a list of statements."""
    calls: list[PythonCall] = []

    for stmt in body_nodes:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                callee_str = normalize_callee(node.func)
                kw_names = [kw.arg for kw in node.keywords if kw.arg is not None]
                pos_args: list[str] = []
                for arg in node.args:
                    try:
                        pos_args.append(ast.unparse(arg))
                    except Exception:
                        pos_args.append("<arg>")
                line = getattr(node, "lineno", 1)
                calls.append(
                    PythonCall(
                        callee=callee_str,
                        line=line,
                        containing_symbol=containing_symbol,
                        argument_count=len(node.args),
                        keyword_names=kw_names,
                        positional_args=pos_args,
                    )
                )

    return calls


def parse_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    scope_prefix: str = "",
) -> PythonFunction:
    """Parse a FunctionDef or AsyncFunctionDef node into a PythonFunction model."""
    qual_name = f"{scope_prefix}.{node.name}" if scope_prefix else node.name
    line_start = node.lineno
    line_end = getattr(node, "end_lineno", line_start)

    decorators = [normalize_decorator(d) for d in node.decorator_list]
    params = extract_parameters(node.args)

    ret_ann = None
    if node.returns is not None:
        try:
            ret_ann = ast.unparse(node.returns)
        except Exception:
            ret_ann = "<type>"

    doc_summary = extract_docstring_summary(node)
    calls = extract_calls(node.body, containing_symbol=qual_name)

    return PythonFunction(
        name=node.name,
        qualified_name=qual_name,
        line_start=line_start,
        line_end=line_end,
        parameters=params,
        decorators=decorators,
        is_async=isinstance(node, ast.AsyncFunctionDef),
        return_annotation=ret_ann,
        docstring_summary=doc_summary,
        calls=calls,
    )


def parse_class(node: ast.ClassDef, scope_prefix: str = "") -> PythonClass:
    """Parse a ClassDef node into a PythonClass model."""
    qual_name = f"{scope_prefix}.{node.name}" if scope_prefix else node.name
    line_start = node.lineno
    line_end = getattr(node, "end_lineno", line_start)

    decorators = [normalize_decorator(d) for d in node.decorator_list]

    bases: list[str] = []
    for b in node.bases:
        try:
            bases.append(ast.unparse(b))
        except Exception:
            bases.append("<base>")

    methods: list[PythonFunction] = []
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(parse_function(item, scope_prefix=qual_name))

    return PythonClass(
        name=node.name,
        qualified_name=qual_name,
        line_start=line_start,
        line_end=line_end,
        bases=bases,
        decorators=decorators,
        methods=methods,
    )


def parse_python_module(file_path: Path, relative_path: str) -> PythonModule:
    """Safely parse a Python source file into a PythonModule model.

    Catches all syntax, encoding, and I/O errors and records them cleanly
    without throwing exceptions.
    """
    inferred_name = infer_module_name(relative_path)

    try:
        source_text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return PythonModule(
            path=relative_path,
            module_name=inferred_name,
            parse_status="parse_failed",
            syntax_error=ParseFailure(
                file_path=relative_path,
                error_type="OSError",
                message=str(exc),
            ),
        )

    if not source_text.strip():
        return PythonModule(
            path=relative_path,
            module_name=inferred_name,
            parse_status="empty",
        )

    try:
        tree = ast.parse(source_text, filename=str(file_path))
    except SyntaxError as exc:
        return PythonModule(
            path=relative_path,
            module_name=inferred_name,
            parse_status="parse_failed",
            syntax_error=ParseFailure(
                file_path=relative_path,
                error_type="SyntaxError",
                message=exc.msg or "SyntaxError",
                line=exc.lineno,
                column=exc.offset,
            ),
        )
    except Exception as exc:
        return PythonModule(
            path=relative_path,
            module_name=inferred_name,
            parse_status="parse_failed",
            syntax_error=ParseFailure(
                file_path=relative_path,
                error_type=type(exc).__name__,
                message=str(exc),
            ),
        )

    # Successful AST parse
    doc_summary = extract_docstring_summary(tree)
    imports: list[PythonImport] = []
    functions: list[PythonFunction] = []
    classes: list[PythonClass] = []
    top_level_calls: list[PythonCall] = []

    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                imports.append(
                    PythonImport(
                        module=alias.name,
                        imported_name="",
                        alias=alias.asname,
                        relative_level=0,
                        line=stmt.lineno,
                        is_from_import=False,
                    )
                )
        elif isinstance(stmt, ast.ImportFrom):
            mod = stmt.module or ""
            level = stmt.level or 0
            for alias in stmt.names:
                imports.append(
                    PythonImport(
                        module=mod,
                        imported_name=alias.name,
                        alias=alias.asname,
                        relative_level=level,
                        line=stmt.lineno,
                        is_from_import=True,
                    )
                )
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(parse_function(stmt))
        elif isinstance(stmt, ast.ClassDef):
            classes.append(parse_class(stmt))
        elif not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            top_level_calls.extend(extract_calls([stmt], containing_symbol=None))

    return PythonModule(
        path=relative_path,
        module_name=inferred_name,
        parse_status="ok",
        docstring_summary=doc_summary,
        imports=imports,
        functions=functions,
        classes=classes,
        calls=top_level_calls,
    )
