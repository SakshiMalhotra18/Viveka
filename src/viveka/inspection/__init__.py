"""
viveka.inspection — Safe repository scanner and structural static analysis.
"""

from __future__ import annotations

from viveka.inspection.analyzer import analyze_python_repository
from viveka.inspection.models import Decision, Reason, ScannedFile, ScanSummary
from viveka.inspection.python_models import (
    Confidence,
    EntryPointCandidate,
    FrameworkHint,
    LocalImportEdge,
    ParseFailure,
    PythonCall,
    PythonClass,
    PythonFunction,
    PythonImport,
    PythonModule,
    PythonParameter,
    StaticAnalysisResult,
    ToolCandidate,
)
from viveka.inspection.scanner import scan_repository

__all__ = [
    "Confidence",
    "Decision",
    "EntryPointCandidate",
    "FrameworkHint",
    "LocalImportEdge",
    "ParseFailure",
    "PythonCall",
    "PythonClass",
    "PythonFunction",
    "PythonImport",
    "PythonModule",
    "PythonParameter",
    "Reason",
    "ScanSummary",
    "ScannedFile",
    "StaticAnalysisResult",
    "ToolCandidate",
    "analyze_python_repository",
    "scan_repository",
]
