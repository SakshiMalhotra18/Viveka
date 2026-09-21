# CI Integration Guide

Integrate VIVEKA verification into your CI pipeline.

## Exit Codes

### `viveka verify`

| Code | Meaning |
|------|------------------------------------------|
| 0    | No reproduced violations found           |
| 1    | Reproduced violations found              |
| 2    | Configuration error / no approved properties |
| 3    | Operational error                        |

### `viveka replay`

| Code | Meaning |
|------|------------------------------------------|
| 0    | Reproduction criterion NOT met           |
| 1    | Reproduction criterion MET               |
| 2    | Invalid or missing regression            |
| 3    | Operational error                        |

## Output Modes

- **stdout** with `--json`: Machine-readable JSON envelope only
- **stdout** without `--json`: Human-readable Rich console output
- **stderr**: Diagnostics and warnings
- **file** with `--junit path/to/report.xml`: JUnit XML report

`--json` and `--junit` can be used together. JSON goes to stdout,
JUnit XML goes to the specified file.

## JUnit XML Report

The `--junit` flag writes a standard JUnit XML report compatible with
most CI systems (GitHub Actions, GitLab CI, Jenkins, Azure DevOps).

```sh
viveka verify . --junit results/viveka-report.xml
```

Mapping:

| Property Status       | JUnit Element |
|-----------------------|---------------|
| NO_REPRODUCED_VIOLATION | `<testcase>` (pass) |
| REPRODUCED_VIOLATION  | `<testcase><failure>` |
| INCONCLUSIVE          | `<testcase><skipped>` |
| ERROR                 | `<testcase><error>` |

## GitHub Actions Example

```yaml
name: VIVEKA Verification
on: [push, pull_request]

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv python install 3.12
      - run: uv sync
      - run: uv run viveka verify . --json --junit results/report.xml
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: viveka-report
          path: results/report.xml
```

## GitLab CI Example

```yaml
viveka-verify:
  image: python:3.12
  script:
    - pip install viveka-engine
    - viveka verify . --junit report.xml
  artifacts:
    reports:
      junit: report.xml
```

## JSON + JUnit Coexistence

For CI pipelines that need both machine-readable JSON (for programmatic
processing) and JUnit XML (for CI test reporting):

```sh
viveka verify . --json --junit report.xml > result.json
```

- `result.json`: Full VerificationResult JSON envelope
- `report.xml`: JUnit XML for CI test tab
- stderr: Diagnostic warnings (if any)
