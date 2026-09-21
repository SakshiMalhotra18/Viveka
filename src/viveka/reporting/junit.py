"""
JUnit XML report generation for VIVEKA verification results.

Mapping:
  - PropertyVerificationStatus.NO_REPRODUCED_VIOLATION → <testcase> (pass)
  - PropertyVerificationStatus.REPRODUCED_VIOLATION   → <testcase><failure>
  - PropertyVerificationStatus.INCONCLUSIVE           → <testcase><skipped>
  - PropertyVerificationStatus.ERROR                  → <testcase><error>
  - PropertyVerificationStatus.SKIPPED                → <testcase><skipped>
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

from viveka.verification.vocabulary import PropertyVerificationStatus

if TYPE_CHECKING:
    from viveka.verification.models import VerificationResult


def export_junit_xml(result: VerificationResult, path: Path) -> None:
    """Export a VerificationResult as a JUnit XML report.

    Counts (tests, failures, errors, skipped) are derived from the
    actual emitted testcase elements so they cannot disagree with
    the XML body.

    Args:
        result: The VerificationResult to export.
        path: Destination file path for the JUnit XML report.
    """
    testcases: list[ET.Element] = []

    for pr in result.property_results:
        tc = ET.Element("testcase")
        tc.set("classname", f"viveka.{pr.property_stable_key}")
        tc.set("name", pr.property_name)

        if pr.status == PropertyVerificationStatus.NO_REPRODUCED_VIOLATION:
            # Pass — no child element needed
            pass
        elif pr.status == PropertyVerificationStatus.REPRODUCED_VIOLATION:
            failure = ET.SubElement(tc, "failure")
            failure.set("type", "ReproducedViolation")
            message = (
                f"Property '{pr.property_name}' violated in "
                f"{pr.worlds_violated}/{pr.worlds_tested} tested worlds."
            )
            if pr.error_message:
                message += f" {pr.error_message}"
            failure.set("message", message)
            failure.text = message
        elif pr.status == PropertyVerificationStatus.INCONCLUSIVE:
            skipped = ET.SubElement(tc, "skipped")
            skipped.set("type", "Inconclusive")
            message = f"Property '{pr.property_name}' evaluation was inconclusive."
            if pr.error_message:
                message += f" {pr.error_message}"
            skipped.set("message", message)
        elif pr.status == PropertyVerificationStatus.ERROR:
            error = ET.SubElement(tc, "error")
            error.set("type", "EvaluationError")
            message = f"Property '{pr.property_name}' encountered an error during evaluation."
            if pr.error_message:
                message += f" {pr.error_message}"
            error.set("message", message)
            error.text = message
        elif pr.status == PropertyVerificationStatus.SKIPPED:
            skipped = ET.SubElement(tc, "skipped")
            skipped.set("type", "Skipped")
            message = f"Property '{pr.property_name}' was skipped."
            if pr.error_message:
                message += f" {pr.error_message}"
            skipped.set("message", message)

        testcases.append(tc)

    # Derive counts from actual testcase elements
    failures = sum(1 for tc in testcases if tc.find("failure") is not None)
    errors = sum(1 for tc in testcases if tc.find("error") is not None)
    skipped = sum(1 for tc in testcases if tc.find("skipped") is not None)
    tests = len(testcases)

    testsuite = ET.Element("testsuite")
    testsuite.set("name", "viveka-verify")
    testsuite.set("tests", str(tests))
    testsuite.set("failures", str(failures))
    testsuite.set("errors", str(errors))
    testsuite.set("skipped", str(skipped))

    if result.summary_message:
        system_out = ET.SubElement(testsuite, "system-out")
        system_out.text = result.summary_message

    for tc in testcases:
        testsuite.append(tc)

    testsuites = ET.Element("testsuites")
    testsuites.append(testsuite)

    tree = ET.ElementTree(testsuites)
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree, space="  ")
    tree.write(str(path), encoding="unicode", xml_declaration=True)
