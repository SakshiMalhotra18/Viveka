"""Tests for Python AST parser and extractor."""

from __future__ import annotations

import textwrap
from pathlib import Path

from viveka.inspection.python_ast import (
    infer_module_name,
    parse_python_module,
)
from viveka.inspection.python_models import ParameterKind


class TestInferModuleName:
    def test_standard_paths(self) -> None:
        assert infer_module_name("src/agent.py") == "src.agent"
        assert infer_module_name("src/tools/email.py") == "src.tools.email"
        assert infer_module_name("src/viveka/__init__.py") == "src.viveka"
        assert infer_module_name("app.py") == "app"


class TestDocstringSummary:
    def test_single_line_docstring(self, tmp_path: Path) -> None:
        code = '''"""Short summary."""\ndef foo(): pass\n'''
        p = tmp_path / "mod.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "mod.py")
        assert mod.docstring_summary == "Short summary."

    def test_multi_line_docstring_truncation(self, tmp_path: Path) -> None:
        long_line = "A" * 200
        code = f'"""{long_line}\nSecond line.\n"""\n'
        p = tmp_path / "mod.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "mod.py")
        assert mod.docstring_summary is not None
        assert len(mod.docstring_summary) == 120


class TestFunctionExtraction:
    def test_ordinary_and_async_functions(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            def sync_fn(a: int, b: str = "default", *args: int, kw_only: bool = True, **kwargs: str) -> bool:
                '''Sync function doc.'''
                return True

            async def async_fn(pos_only: int, /, standard: str) -> None:
                pass
        """)
        p = tmp_path / "funcs.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "funcs.py")

        assert len(mod.functions) == 2

        # sync_fn
        fn1 = mod.functions[0]
        assert fn1.name == "sync_fn"
        assert fn1.qualified_name == "sync_fn"
        assert fn1.is_async is False
        assert fn1.return_annotation == "bool"
        assert fn1.docstring_summary == "Sync function doc."
        assert len(fn1.parameters) == 5

        p0 = fn1.parameters[0]
        assert p0.name == "a"
        assert p0.kind == ParameterKind.POSITIONAL_OR_KEYWORD
        assert p0.has_default is False
        assert p0.type_annotation == "int"

        p1 = fn1.parameters[1]
        assert p1.name == "b"
        assert p1.has_default is True
        assert p1.type_annotation == "str"

        p2 = fn1.parameters[2]
        assert p2.name == "args"
        assert p2.kind == ParameterKind.VAR_POSITIONAL

        p3 = fn1.parameters[3]
        assert p3.name == "kw_only"
        assert p3.kind == ParameterKind.KEYWORD_ONLY
        assert p3.has_default is True

        p4 = fn1.parameters[4]
        assert p4.name == "kwargs"
        assert p4.kind == ParameterKind.VAR_KEYWORD

        # async_fn
        fn2 = mod.functions[1]
        assert fn2.name == "async_fn"
        assert fn2.is_async is True
        assert fn2.parameters[0].kind == ParameterKind.POSITIONAL_ONLY

    def test_complex_default_expressions_not_evaluated(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            import datetime
            def stamp(when=datetime.datetime.now()):
                pass
        """)
        p = tmp_path / "stamp.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "stamp.py")
        assert mod.parse_status == "ok"
        assert mod.functions[0].parameters[0].has_default is True


class TestClassExtraction:
    def test_classes_and_methods(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            class BaseAgent:
                pass

            class CustomAgent(BaseAgent, object):
                '''Custom agent class.'''
                def __init__(self, name: str):
                    self.name = name

                async def step(self) -> dict:
                    return {}
        """)
        p = tmp_path / "classes.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "classes.py")

        assert len(mod.classes) == 2
        cls2 = mod.classes[1]
        assert cls2.name == "CustomAgent"
        assert cls2.bases == ["BaseAgent", "object"]
        assert len(cls2.methods) == 2
        assert cls2.methods[0].qualified_name == "CustomAgent.__init__"
        assert cls2.methods[1].qualified_name == "CustomAgent.step"
        assert cls2.methods[1].is_async is True


class TestImportExtraction:
    def test_all_import_styles(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            import os
            import numpy as np
            from pathlib import Path, PurePosixPath as PPP
            from . import local_mod
            from ..tools.email import send_mail as send
        """)
        p = tmp_path / "imports.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "imports.py")

        assert len(mod.imports) == 6

        # import os
        assert mod.imports[0].module == "os"
        assert mod.imports[0].is_from_import is False

        # import numpy as np
        assert mod.imports[1].module == "numpy"
        assert mod.imports[1].alias == "np"

        # from pathlib import Path
        assert mod.imports[2].module == "pathlib"
        assert mod.imports[2].imported_name == "Path"

        # from pathlib import PurePosixPath as PPP
        assert mod.imports[3].imported_name == "PurePosixPath"
        assert mod.imports[3].alias == "PPP"

        # from . import local_mod
        assert mod.imports[4].relative_level == 1
        assert mod.imports[4].imported_name == "local_mod"

        # from ..tools.email import send_mail as send
        assert mod.imports[5].relative_level == 2
        assert mod.imports[5].module == "tools.email"
        assert mod.imports[5].imported_name == "send_mail"
        assert mod.imports[5].alias == "send"


class TestCallExtraction:
    def test_direct_attribute_and_chained_calls(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            def worker():
                direct_call(1, 2)
                client.service.execute("query", timeout=30)
                os.path.join("a", "b")
        """)
        p = tmp_path / "calls.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "calls.py")

        fn = mod.functions[0]
        assert len(fn.calls) == 3
        assert fn.calls[0].callee == "direct_call"
        assert fn.calls[0].argument_count == 2
        assert fn.calls[1].callee == "client.service.execute"
        assert fn.calls[1].keyword_names == ["timeout"]
        assert fn.calls[2].callee == "os.path.join"


class TestErrorAndEdgeCases:
    def test_syntax_error_handling(self, tmp_path: Path) -> None:
        code = "def broken(:\n    pass\n"
        p = tmp_path / "broken.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "broken.py")

        assert mod.parse_status == "parse_failed"
        assert mod.syntax_error is not None
        assert mod.syntax_error.error_type == "SyntaxError"
        assert mod.syntax_error.line == 1

    def test_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.py"
        p.write_text("   \n\n", encoding="utf-8")
        mod = parse_python_module(p, "empty.py")
        assert mod.parse_status == "empty"
        assert len(mod.functions) == 0

    def test_unicode_identifiers(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            def विवेक_कार्य(इनपुट: str) -> str:
                '''विवेक फंक्शन'''
                return इनपुट
        """)
        p = tmp_path / "unicode_mod.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "unicode_mod.py")
        assert mod.parse_status == "ok"
        assert mod.functions[0].name == "विवेक_कार्य"
        assert mod.functions[0].docstring_summary == "विवेक फंक्शन"
