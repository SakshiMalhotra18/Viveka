"""
Unit and integration tests for VIVEKA Phase 15:
- Version single source of truth (importlib.metadata)
- VerificationResult schema_version: 1
- JUnit XML report generation and mapping
- CLI verify --junit and --json+--junit coexistence
- CLI replay exit codes (0/1/2/3) in human and JSON modes
- PEP 639 license metadata and entrypoint integrity
- Core vs MCP extra packaging isolation
- Repository secret sanity scan
"""

from __future__ import annotations

import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from viveka import __version__, get_version
from viveka.cli.app import app
from viveka.reporting.junit import export_junit_xml
from viveka.verification.models import (
    PropertyVerificationResult,
    VerificationResult,
)
from viveka.verification.vocabulary import (
    PropertyVerificationStatus,
    VerificationOutcome,
)

runner = CliRunner()


# ===========================================================================
# 1. Version Resolution Tests
# ===========================================================================


def test_version_is_string() -> None:
    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_get_version_function() -> None:
    v = get_version()
    assert isinstance(v, str)
    assert len(v) > 0


def test_get_version_fallback_on_package_not_found() -> None:
    from importlib.metadata import PackageNotFoundError

    with patch("viveka.version", side_effect=PackageNotFoundError):
        v = get_version()
        assert v == "0.0.0+unknown"


# ===========================================================================
# 2. Schema Version Tests
# ===========================================================================


def test_verification_result_has_schema_version() -> None:
    result = VerificationResult(outcome=VerificationOutcome.NO_REPRODUCED_VIOLATIONS)
    assert result.schema_version == 1


def test_verification_result_schema_version_in_json_dump() -> None:
    result = VerificationResult(outcome=VerificationOutcome.NO_REPRODUCED_VIOLATIONS)
    data = result.model_dump(mode="json")
    assert "schema_version" in data
    assert data["schema_version"] == 1


# ===========================================================================
# 3. JUnit XML Export Tests
# ===========================================================================


def _make_sample_result() -> VerificationResult:
    return VerificationResult(
        outcome=VerificationOutcome.REPRODUCED_VIOLATIONS_FOUND,
        properties_considered=4,
        properties_verified=4,
        properties_passed=1,
        properties_violated=1,
        properties_errored=1,
        total_worlds_tested=10,
        summary_message="Verification completed with reproduced violations.",
        property_results=[
            PropertyVerificationResult(
                property_id="PROP-001",
                property_name="No unauthorized financial action",
                property_stable_key="src/agent.py::order_tool",
                property_revision=1,
                status=PropertyVerificationStatus.NO_REPRODUCED_VIOLATION,
                worlds_tested=3,
                worlds_violated=0,
            ),
            PropertyVerificationResult(
                property_id="PROP-002",
                property_name="No untrusted egress to external sinks",
                property_stable_key="src/agent.py::email_tool",
                property_revision=1,
                status=PropertyVerificationStatus.REPRODUCED_VIOLATION,
                worlds_tested=3,
                worlds_violated=2,
                regression_id="VREG-001",
            ),
            PropertyVerificationResult(
                property_id="PROP-003",
                property_name="Failure gracefully handled",
                property_stable_key="src/agent.py::search_tool",
                property_revision=1,
                status=PropertyVerificationStatus.INCONCLUSIVE,
                worlds_tested=2,
                worlds_violated=0,
            ),
            PropertyVerificationResult(
                property_id="PROP-004",
                property_name="Audit log completeness",
                property_stable_key="src/agent.py::audit_tool",
                property_revision=1,
                status=PropertyVerificationStatus.ERROR,
                worlds_tested=2,
                worlds_violated=0,
                error_message="Runtime process crashed.",
            ),
        ],
    )


def test_junit_creates_valid_xml(tmp_path: Path) -> None:
    xml_file = tmp_path / "junit_report.xml"
    result = _make_sample_result()
    export_junit_xml(result, xml_file)

    assert xml_file.exists()
    tree = ET.parse(str(xml_file))
    root = tree.getroot()

    assert root.tag == "testsuites"
    suite = root.find("testsuite")
    assert suite is not None
    assert suite.get("name") == "viveka-verify"


def test_junit_counts_derived_from_actual_testcases(tmp_path: Path) -> None:
    xml_file = tmp_path / "counts_report.xml"
    result = _make_sample_result()
    export_junit_xml(result, xml_file)

    tree = ET.parse(str(xml_file))
    suite = tree.getroot().find("testsuite")
    assert suite is not None

    assert suite.get("tests") == "4"
    assert suite.get("failures") == "1"
    assert suite.get("skipped") == "1"
    assert suite.get("errors") == "1"


def test_junit_pass_element_has_no_children(tmp_path: Path) -> None:
    xml_file = tmp_path / "pass_report.xml"
    result = VerificationResult(
        outcome=VerificationOutcome.NO_REPRODUCED_VIOLATIONS,
        property_results=[
            PropertyVerificationResult(
                property_id="PROP-PASS",
                property_name="Clean Property",
                property_stable_key="mod::tool",
                property_revision=1,
                status=PropertyVerificationStatus.NO_REPRODUCED_VIOLATION,
                worlds_tested=3,
                worlds_violated=0,
            )
        ],
    )
    export_junit_xml(result, xml_file)

    tree = ET.parse(str(xml_file))
    testcase = tree.getroot().find(".//testcase")
    assert testcase is not None
    assert testcase.get("name") == "Clean Property"
    assert len(list(testcase)) == 0  # No failure, error, or skipped child


def test_junit_failure_element_structure(tmp_path: Path) -> None:
    xml_file = tmp_path / "fail_report.xml"
    result = VerificationResult(
        outcome=VerificationOutcome.REPRODUCED_VIOLATIONS_FOUND,
        property_results=[
            PropertyVerificationResult(
                property_id="PROP-FAIL",
                property_name="Violated Property",
                property_stable_key="mod::tool",
                property_revision=1,
                status=PropertyVerificationStatus.REPRODUCED_VIOLATION,
                worlds_tested=5,
                worlds_violated=3,
            )
        ],
    )
    export_junit_xml(result, xml_file)

    tree = ET.parse(str(xml_file))
    failure = tree.getroot().find(".//failure")
    assert failure is not None
    assert failure.get("type") == "ReproducedViolation"
    assert "3/5 tested worlds" in (failure.get("message") or "")


def test_junit_skipped_element_structure(tmp_path: Path) -> None:
    xml_file = tmp_path / "skip_report.xml"
    result = VerificationResult(
        outcome=VerificationOutcome.NO_REPRODUCED_VIOLATIONS,
        property_results=[
            PropertyVerificationResult(
                property_id="PROP-SKIP",
                property_name="Inconclusive Property",
                property_stable_key="mod::tool",
                property_revision=1,
                status=PropertyVerificationStatus.INCONCLUSIVE,
            )
        ],
    )
    export_junit_xml(result, xml_file)

    tree = ET.parse(str(xml_file))
    skipped = tree.getroot().find(".//skipped")
    assert skipped is not None
    assert skipped.get("type") == "Inconclusive"


def test_junit_error_element_structure(tmp_path: Path) -> None:
    xml_file = tmp_path / "err_report.xml"
    result = VerificationResult(
        outcome=VerificationOutcome.EXECUTION_ERROR,
        property_results=[
            PropertyVerificationResult(
                property_id="PROP-ERR",
                property_name="Errored Property",
                property_stable_key="mod::tool",
                property_revision=1,
                status=PropertyVerificationStatus.ERROR,
                error_message="Adapter timeout exceeded.",
            )
        ],
    )
    export_junit_xml(result, xml_file)

    tree = ET.parse(str(xml_file))
    error = tree.getroot().find(".//error")
    assert error is not None
    assert error.get("type") == "EvaluationError"
    assert "Adapter timeout exceeded" in (error.get("message") or "")


def test_junit_creates_parent_directories(tmp_path: Path) -> None:
    nested_file = tmp_path / "deep" / "nested" / "dir" / "report.xml"
    result = VerificationResult(outcome=VerificationOutcome.NO_REPRODUCED_VIOLATIONS)
    export_junit_xml(result, nested_file)
    assert nested_file.exists()


def test_junit_empty_property_results(tmp_path: Path) -> None:
    xml_file = tmp_path / "empty_report.xml"
    result = VerificationResult(outcome=VerificationOutcome.NO_APPROVED_PROPERTIES)
    export_junit_xml(result, xml_file)

    tree = ET.parse(str(xml_file))
    suite = tree.getroot().find("testsuite")
    assert suite is not None
    assert suite.get("tests") == "0"
    assert suite.get("failures") == "0"
    assert suite.get("errors") == "0"
    assert suite.get("skipped") == "0"


# ===========================================================================
# 4. CLI verify --junit and --json+--junit Coexistence Tests
# ===========================================================================


def test_cli_verify_with_junit_export(tmp_path: Path) -> None:
    # Initialize a demo project
    init_res = runner.invoke(app, ["init", str(tmp_path)])
    assert init_res.exit_code == 0

    junit_file = tmp_path / "artifacts" / "junit.xml"
    res = runner.invoke(
        app,
        [
            "verify",
            str(tmp_path),
            "--junit",
            str(junit_file),
            "--target",
            "viveka.demo.agent:run_demo_agent",
        ],
    )
    assert res.exit_code in (0, 1, 2)
    # The command should write the JUnit report
    assert junit_file.exists()
    tree = ET.parse(str(junit_file))
    assert tree.getroot().tag == "testsuites"


def test_cli_verify_json_and_junit_coexistence(tmp_path: Path) -> None:
    init_res = runner.invoke(app, ["init", str(tmp_path)])
    assert init_res.exit_code == 0

    junit_file = tmp_path / "coexist_junit.xml"
    res = runner.invoke(
        app,
        [
            "verify",
            str(tmp_path),
            "--json",
            "--junit",
            str(junit_file),
            "--target",
            "viveka.demo.agent:run_demo_agent",
        ],
    )
    # Stdout should be valid JSON
    import json

    output_data = json.loads(res.stdout)
    assert "outcome" in output_data
    assert "schema_version" in output_data
    assert output_data["schema_version"] == 1

    # JUnit file should be written separately
    assert junit_file.exists()
    tree = ET.parse(str(junit_file))
    assert tree.getroot().tag == "testsuites"


# ===========================================================================
# 5. CLI replay Exit Codes (0/1/2/3) Tests
# ===========================================================================


def test_cli_replay_missing_regression_exit_code_2(tmp_path: Path) -> None:
    # Missing regression in project
    res = runner.invoke(app, ["replay", "VREG-NONEXISTENT", "--path", str(tmp_path)])
    assert res.exit_code == 2


def test_cli_replay_missing_regression_json_mode_exit_code_2(tmp_path: Path) -> None:
    res = runner.invoke(app, ["replay", "VREG-NONEXISTENT", "--path", str(tmp_path), "--json"])
    assert res.exit_code == 2
    import json

    data = json.loads(res.stdout)
    assert "error" in data


def test_cli_replay_criterion_met_exit_code_1() -> None:
    from viveka.regression.models import ReplayReport

    fake_report = ReplayReport(
        regression_id="VREG-TEST-001",
        property_stable_key="test::key",
        property_revision=1,
        historical_violations=3,
        historical_no_observed_violations=0,
        historical_inconclusive=0,
        historical_not_applicable=0,
        historical_runs=3,
        historical_criterion_met=True,
        current_violations=3,
        current_no_observed_violations=0,
        current_inconclusive=0,
        current_not_applicable=0,
        current_runs=3,
        current_criterion_met=True,
        property_version_mismatch=False,
        property_mismatch_detail="",
        observations=["The configured reproduction criterion was met."],
    )

    with patch(
        "viveka.regression.store.RegressionStore.load",
        return_value=MagicMock(regression_id="VREG-TEST-001"),
    ):
        with patch("viveka.regression.replay.ReplayEngine.replay", return_value=fake_report):
            res = runner.invoke(app, ["replay", "VREG-TEST-001"])
            assert res.exit_code == 1

            # Also in JSON mode
            res_json = runner.invoke(app, ["replay", "VREG-TEST-001", "--json"])
            assert res_json.exit_code == 1


def test_cli_replay_criterion_not_met_exit_code_0() -> None:
    from viveka.regression.models import ReplayReport

    fake_report = ReplayReport(
        regression_id="VREG-TEST-002",
        property_stable_key="test::key",
        property_revision=1,
        historical_violations=3,
        historical_no_observed_violations=0,
        historical_inconclusive=0,
        historical_not_applicable=0,
        historical_runs=3,
        historical_criterion_met=True,
        current_violations=0,
        current_no_observed_violations=3,
        current_inconclusive=0,
        current_not_applicable=0,
        current_runs=3,
        current_criterion_met=False,
        property_version_mismatch=False,
        property_mismatch_detail="",
        observations=["The configured reproduction criterion was not met."],
    )

    with patch(
        "viveka.regression.store.RegressionStore.load",
        return_value=MagicMock(regression_id="VREG-TEST-002"),
    ):
        with patch("viveka.regression.replay.ReplayEngine.replay", return_value=fake_report):
            res = runner.invoke(app, ["replay", "VREG-TEST-002"])
            assert res.exit_code == 0

            # Also in JSON mode
            res_json = runner.invoke(app, ["replay", "VREG-TEST-002", "--json"])
            assert res_json.exit_code == 0


def test_cli_replay_operational_error_exit_code_3() -> None:
    with patch(
        "viveka.regression.store.RegressionStore.load",
        return_value=MagicMock(regression_id="VREG-TEST-003"),
    ):
        with patch(
            "viveka.regression.replay.ReplayEngine.replay",
            side_effect=RuntimeError("Subprocess failed"),
        ):
            res = runner.invoke(app, ["replay", "VREG-TEST-003"])
            assert res.exit_code == 3

            # Also in JSON mode
            res_json = runner.invoke(app, ["replay", "VREG-TEST-003", "--json"])
            assert res_json.exit_code == 3


# ===========================================================================
# 6. PEP 639 License & Packaging Metadata Tests
# ===========================================================================


def test_pyproject_pep639_license_metadata() -> None:
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    assert pyproject_path.exists()

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    project = data.get("project", {})
    # PEP 639 format: license is string "MIT", license-files is array ["LICENSE"]
    assert project.get("license") == "MIT"
    assert project.get("license-files") == ["LICENSE"]
    assert project.get("name") == "viveka-engine"


def test_license_file_exists_in_repository_root() -> None:
    root = Path(__file__).resolve().parent.parent
    license_file = root / "LICENSE"
    assert license_file.exists()
    content = license_file.read_text(encoding="utf-8")
    assert "MIT License" in content


def test_cli_entrypoint_is_declared_correctly() -> None:
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    scripts = data.get("project", {}).get("scripts", {})
    assert scripts.get("viveka") == "viveka.cli.app:app"


def test_optional_dependencies_mcp_bounded() -> None:
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    opt = data.get("project", {}).get("optional-dependencies", {})
    assert "mcp" in opt
    assert any("mcp>=2" in dep and "<3" in dep for dep in opt["mcp"])


# ===========================================================================
# 7. Secret Sanity Scan
# ===========================================================================


def test_no_sensitive_credential_files_in_source_tree() -> None:
    root = Path(__file__).resolve().parent.parent / "src"
    sensitive_markers = [
        "-----BEGIN RSA PRIVATE KEY-----",
        "-----BEGIN OPENSSH PRIVATE KEY-----",
        "-----BEGIN EC PRIVATE KEY-----",
        "-----BEGIN PRIVATE KEY-----",
    ]

    for py_file in root.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="replace")
        for marker in sensitive_markers:
            assert marker not in text, f"Found private key marker in {py_file}"
