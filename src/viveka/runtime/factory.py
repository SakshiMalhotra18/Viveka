"""
Adapter factory for VIVEKA Phase 13 runtime execution.

Resolves and instantiates appropriate BaseRuntimeAdapter implementation based on TargetSpec.
"""

from __future__ import annotations

from viveka.runtime.adapter import BaseRuntimeAdapter
from viveka.runtime.http_adapter import HttpJsonRuntimeAdapter
from viveka.runtime.mcp_adapter import McpRuntimeAdapter
from viveka.runtime.models import TargetSpec
from viveka.runtime.python_adapter import AdapterError, PythonCallableAdapter
from viveka.runtime.vocabulary import RuntimeAdapterType


def create_adapter(spec: TargetSpec) -> BaseRuntimeAdapter:
    """Factory function to create and load a BaseRuntimeAdapter for the given TargetSpec.

    Args:
        spec: Target specification detailing adapter type and options.

    Returns:
        A loaded :class:`BaseRuntimeAdapter` instance ready for execution.

    Raises:
        AdapterError: If adapter_type is unsupported or target loading fails.
    """
    adapter_type_str = str(spec.adapter_type).lower()

    if adapter_type_str in (RuntimeAdapterType.PYTHON_CALLABLE.value, "python_callable", "python"):
        adapter: BaseRuntimeAdapter = PythonCallableAdapter()
    elif adapter_type_str in (RuntimeAdapterType.HTTP.value, "http", "http_json"):
        adapter = HttpJsonRuntimeAdapter()
    elif adapter_type_str in (RuntimeAdapterType.MCP.value, "mcp"):
        adapter = McpRuntimeAdapter()
    else:
        raise AdapterError(
            f"Unsupported runtime adapter type '{spec.adapter_type}'. "
            "Supported adapter types: 'python_callable', 'http', 'mcp'."
        )

    adapter.load_target(spec)
    return adapter
