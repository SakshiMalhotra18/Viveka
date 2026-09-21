# Releasing VIVEKA

Release checklist for maintainers.

## Pre-Release

1. Ensure all tests pass: `uv run pytest`
2. Ensure lint is clean: `uv run ruff check .`
3. Ensure format is clean: `uv run ruff format --check .`
4. Ensure build succeeds: `uv build`
5. Update version in `pyproject.toml` (single source of truth)
6. Update `CHANGELOG.md` with release date and changes
7. Commit version bump and changelog: `git commit -m "release: vX.Y.Z"`
8. Tag the release: `git tag vX.Y.Z`
9. Push with tags: `git push origin main --tags`

## Automated Release

The `release.yml` GitHub Actions workflow triggers on `v*` tag push:

1. Runs full test suite
2. Builds wheel and sdist
3. Validates tag matches package version
4. Publishes to PyPI via OIDC Trusted Publishing

## Manual Release (if needed)

1. Build: `uv build`
2. Inspect artifacts:
   - `unzip -l dist/viveka_engine-X.Y.Z-py3-none-any.whl`
   - `tar tzf dist/viveka_engine-X.Y.Z.tar.gz`
3. Verify no secrets, `.env`, or `.viveka/` directories in artifacts
4. Upload to PyPI: `uv publish` (requires PyPI API token)

## Post-Release

1. Verify installation: `pip install viveka-engine==X.Y.Z`
2. Verify CLI: `viveka version`
3. Add `## [Unreleased]` section to `CHANGELOG.md`

## PyPI Setup (First Release)

The distribution name is `viveka-engine`. No existing public PyPI project
named `viveka-engine` was found at audit time. Final name availability
is confirmed only when the project is actually created/published.

For OIDC Trusted Publishing setup:
1. Create a PyPI account and configure a Trusted Publisher for the GitHub repository
2. Set up the `pypi` environment in the GitHub repository settings
3. No API tokens needed — authentication uses GitHub's OIDC identity
