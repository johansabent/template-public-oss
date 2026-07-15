#!/usr/bin/env python3
"""Validate the repository onboarding contract without third-party dependencies."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tomllib
from typing import Any


ONBOARDING_SCHEMA = "agent-project-onboarding/v1"
DOCS_SCHEMA = "project-docs-manifest/v1"
CAPABILITIES = (
    "browser",
    "wsl",
    "deploy",
    "production",
    "trackers",
    "plugins",
    "mcp_servers",
    "account_connectors",
)


class DuplicateJsonKey(ValueError):
    """Raised when JSON contains a duplicate object key."""


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKey(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_toml(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            value = tomllib.load(handle)
    except FileNotFoundError:
        errors.append("missing onboarding manifest: .agents/onboarding.toml")
        return {}
    except (OSError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"invalid onboarding TOML: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append("onboarding manifest must be a TOML table")
        return {}
    return value


def _read_codex_toml(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            value = tomllib.load(handle)
    except FileNotFoundError:
        errors.append("missing Codex onboarding overlay: .codex/onboarding.toml")
        return {}
    except (OSError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"invalid Codex onboarding TOML: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append("Codex onboarding overlay must be a TOML table")
        return {}
    return value


def _read_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_object_without_duplicates,
        )
    except FileNotFoundError:
        errors.append("missing docs manifest: docs/MANIFEST.json")
        return {}
    except (OSError, UnicodeError, json.JSONDecodeError, DuplicateJsonKey) as exc:
        errors.append(f"invalid docs manifest JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append("docs manifest must be a JSON object")
        return {}
    return value


def _table(value: Any, name: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{name} must be a table")
        return {}
    return value


def _nonempty_string(table: dict[str, Any], key: str, prefix: str, errors: list[str]) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{prefix}.{key} must be a non-empty string")
        return ""
    return value.strip()


def _safe_relative_path(value: Any, label: str, errors: list[str]) -> PurePosixPath | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty repository-relative path")
        return None
    if "\\" in value:
        errors.append(f"{label} must use forward slashes")
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        errors.append(f"{label} must stay inside the repository")
        return None
    return path


def _has_exact_case(root: Path, relative: PurePosixPath) -> bool:
    current = root
    for part in relative.parts:
        if not current.is_dir():
            return False
        try:
            names = {child.name for child in current.iterdir()}
        except OSError:
            return False
        if part not in names:
            return False
        current = current / part
    return current.exists()


def _resolved_inside(root: Path, relative: PurePosixPath) -> bool:
    try:
        (root / Path(*relative.parts)).resolve(strict=True).relative_to(root.resolve(strict=True))
    except (FileNotFoundError, OSError, RuntimeError, ValueError):
        return False
    return True


def _validate_onboarding(manifest: dict[str, Any], repository: str | None, errors: list[str]) -> None:
    if manifest.get("schema_version") != ONBOARDING_SCHEMA:
        errors.append(f"schema_version must be {ONBOARDING_SCHEMA}")

    mode = manifest.get("mode")
    if mode not in {"template", "project"}:
        errors.append("mode must be template or project")
        mode = ""

    template_repository = manifest.get("template_repository")
    if not isinstance(template_repository, str) or template_repository.count("/") != 1:
        errors.append("template_repository must be an OWNER/REPO slug")
        template_repository = ""

    identity = _table(manifest.get("identity"), "identity", errors)
    project = _nonempty_string(identity, "project", "identity", errors)
    owner = _nonempty_string(identity, "owner", "identity", errors)
    status = _nonempty_string(identity, "status", "identity", errors)

    taxonomy = _table(manifest.get("taxonomy"), "taxonomy", errors)
    node_type = _nonempty_string(taxonomy, "intended_node_type", "taxonomy", errors)
    context = _nonempty_string(taxonomy, "intended_context_boundary", "taxonomy", errors)
    workspace = _nonempty_string(taxonomy, "intended_workspace", "taxonomy", errors)
    registration = _nonempty_string(taxonomy, "registration", "taxonomy", errors)
    node_id = taxonomy.get("node_id", "")
    if not isinstance(node_id, str):
        errors.append("taxonomy.node_id must be a string")
        node_id = ""
    parent_id = taxonomy.get("parent_id", "")
    if not isinstance(parent_id, str):
        errors.append("taxonomy.parent_id must be a string")

    accounts = _table(manifest.get("accounts"), "accounts", errors)
    github = _nonempty_string(accounts, "github", "accounts", errors)

    capabilities = _table(manifest.get("capabilities"), "capabilities", errors)
    for key in CAPABILITIES:
        value = capabilities.get(key)
        if not isinstance(value, bool):
            errors.append(f"capabilities.{key} must be true or false")
        elif mode == "template" and value:
            errors.append(f"capabilities.{key} must be false in template mode")

    if node_type != "personal-project":
        errors.append("taxonomy.intended_node_type must be personal-project")
    if context != "personal":
        errors.append("taxonomy.intended_context_boundary must be personal")
    if project and workspace and project != workspace:
        errors.append("taxonomy.intended_workspace must equal identity.project")
    if github and github.count("/") != 1:
        errors.append("accounts.github must be an OWNER/REPO slug")
    elif github and owner and github.split("/", 1)[0] != owner:
        errors.append("accounts.github owner must equal identity.owner")

    if mode == "template":
        if registration != "deferred":
            errors.append("template mode requires taxonomy.registration = deferred")
        if status != "template":
            errors.append("template mode requires identity.status = template")
        if template_repository and github and github != template_repository:
            errors.append("template mode requires accounts.github to equal template_repository")
        if template_repository and project and template_repository.split("/", 1)[1] != project:
            errors.append("template mode requires identity.project to equal the template repository name")
        if repository and template_repository and repository != template_repository:
            errors.append(f"template mode is valid only in {template_repository}; initialize project mode")
    elif mode == "project":
        if registration not in {"pending", "registered"}:
            errors.append("project mode requires taxonomy.registration = pending or registered")
        if status == "template":
            errors.append("project mode cannot use identity.status = template")
        if repository and github and repository != github:
            errors.append(f"accounts.github must match the runtime repository: {repository}")

    if registration == "registered" and not node_id.strip():
        errors.append("taxonomy.node_id is required when registration is registered")


def _validate_codex_overlay(
    codex: dict[str, Any], onboarding: dict[str, Any], errors: list[str]
) -> None:
    identity = _table(onboarding.get("identity"), "identity", errors)
    taxonomy = _table(onboarding.get("taxonomy"), "taxonomy", errors)
    capabilities = _table(onboarding.get("capabilities"), "capabilities", errors)

    expected = {
        "mode": onboarding.get("mode"),
        "template_repository": onboarding.get("template_repository"),
        "project": identity.get("project"),
        "context_boundary": taxonomy.get("intended_context_boundary"),
        "intended_node_type": taxonomy.get("intended_node_type"),
        "workspace": taxonomy.get("intended_workspace"),
        "taxonomy_registration": taxonomy.get("registration"),
        "shared_manifest": ".agents/onboarding.toml",
    }
    if codex.get("schema_version") != "codex-project-onboarding/v1":
        errors.append("codex.schema_version must be codex-project-onboarding/v1")
    for key, value in expected.items():
        if codex.get(key) != value:
            target = {
                "project": "identity.project",
                "context_boundary": "taxonomy.intended_context_boundary",
                "intended_node_type": "taxonomy.intended_node_type",
                "workspace": "taxonomy.intended_workspace",
                "taxonomy_registration": "taxonomy.registration",
            }.get(key, key)
            errors.append(f"codex.{key} must equal {target}")
    if codex.get("git_required") is not True:
        errors.append("codex.git_required must be true")
    expected_wsl = capabilities.get("wsl")
    if not isinstance(codex.get("wsl_required"), bool):
        errors.append("codex.wsl_required must be true or false")
    elif isinstance(expected_wsl, bool) and codex.get("wsl_required") != expected_wsl:
        errors.append("codex.wsl_required must equal capabilities.wsl")


def _validate_docs(root: Path, manifest: dict[str, Any], errors: list[str]) -> None:
    if manifest.get("schema_version") != DOCS_SCHEMA:
        errors.append(f"docs schema_version must be {DOCS_SCHEMA}")

    canonical = _table(manifest.get("canonical"), "canonical", errors)
    categories = _table(manifest.get("categories"), "categories", errors)
    if not canonical:
        errors.append("canonical must contain at least one path")
    if not categories:
        errors.append("categories must contain at least one path")

    canonical_paths: list[str] = []
    for key, value in sorted(canonical.items()):
        relative = _safe_relative_path(value, f"canonical.{key}", errors)
        if relative is None:
            continue
        normalized = relative.as_posix()
        canonical_paths.append(normalized)
        if "archive" in {part.casefold() for part in relative.parts}:
            errors.append(f"canonical.{key} cannot point into archive: {normalized}")
        if not _has_exact_case(root, relative):
            errors.append(f"canonical.{key} does not exist: {normalized}")
        elif not _resolved_inside(root, relative):
            errors.append(f"canonical.{key} must stay inside the repository")
        elif not (root / relative).is_file():
            errors.append(f"canonical.{key} must be a regular file: {normalized}")

    if len(canonical_paths) != len(set(canonical_paths)):
        errors.append("canonical paths must be unique")

    registered_dirs: set[str] = set()
    for key, value in sorted(categories.items()):
        relative = _safe_relative_path(value, f"category.{key}", errors)
        if relative is None:
            continue
        normalized = relative.as_posix()
        registered_dirs.add(normalized)
        if len(relative.parts) != 2 or relative.parts[0] != "docs":
            errors.append(
                f"category {key} must be exactly one directory below docs/: {normalized}"
            )
            continue
        if normalized == "docs/archive":
            errors.append(f"category {key} must be an active directory under docs/: {normalized}")
            continue
        target = root / Path(*relative.parts)
        if not _has_exact_case(root, relative) or not target.is_dir():
            errors.append(f"category {key} does not exist: {normalized}")
            continue
        if not _resolved_inside(root, relative):
            errors.append(f"category {key} must stay inside the repository")
            continue
        try:
            has_files = any(path.is_file() for path in target.rglob("*"))
        except OSError:
            has_files = False
        if not has_files:
            errors.append(f"category {key} is empty: {normalized}")

    docs_root = root / "docs"
    if docs_root.is_dir():
        for child in docs_root.iterdir():
            if not child.is_dir() or child.name == "archive":
                continue
            relative = f"docs/{child.name}"
            if relative not in registered_dirs:
                errors.append(f"active docs directory is not registered: {relative}")


def _validate_project_docs(root: Path, manifest: dict[str, Any], errors: list[str]) -> None:
    project_docs = _table(manifest.get("project_docs"), "project_docs", errors)
    for key, value in sorted(project_docs.items()):
        relative = _safe_relative_path(value, f"project_docs.{key}", errors)
        if relative is None:
            continue
        if not _has_exact_case(root, relative):
            errors.append(f"project_docs.{key} does not exist: {relative.as_posix()}")
        elif not _resolved_inside(root, relative):
            errors.append(f"project_docs.{key} must stay inside the repository")
        elif not (root / relative).is_file():
            errors.append(
                f"project_docs.{key} must be a regular file: {relative.as_posix()}"
            )


def _validate_authority_alignment(
    onboarding: dict[str, Any], docs: dict[str, Any], errors: list[str]
) -> None:
    project_docs = _table(onboarding.get("project_docs"), "project_docs", errors)
    canonical = _table(docs.get("canonical"), "canonical", errors)
    pairs = {
        "agents_doc": "agents",
        "board_doc": "board",
        "context_doc": "context",
        "state_doc": "state",
    }
    for project_key, canonical_key in pairs.items():
        if project_docs.get(project_key) != canonical.get(canonical_key):
            errors.append(
                f"project_docs.{project_key} must equal canonical.{canonical_key}"
            )
    if project_docs.get("manifest") != "docs/MANIFEST.json":
        errors.append("project_docs.manifest must equal docs/MANIFEST.json")


def validate(root: Path, repository: str | None = None) -> list[str]:
    errors: list[str] = []
    try:
        root = root.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        return [f"repository root is not accessible: {exc}"]
    if not root.is_dir():
        return [f"repository root is not a directory: {root}"]

    if not repository or repository.count("/") != 1 or any(
        not part.strip() for part in repository.split("/", 1)
    ):
        errors.append(
            "repository identity is required; pass --repository OWNER/REPO or set GITHUB_REPOSITORY"
        )

    onboarding = _read_toml(root / ".agents/onboarding.toml", errors)
    codex = _read_codex_toml(root / ".codex/onboarding.toml", errors)
    docs = _read_json(root / "docs/MANIFEST.json", errors)
    if onboarding:
        _validate_onboarding(onboarding, repository, errors)
        _validate_project_docs(root, onboarding, errors)
        if codex:
            _validate_codex_overlay(codex, onboarding, errors)
    if docs:
        _validate_docs(root, docs, errors)
    if onboarding and docs:
        _validate_authority_alignment(onboarding, docs, errors)
    return sorted(set(errors))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    return parser


def main() -> int:
    args = _parser().parse_args()
    errors = validate(args.root, args.repository)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("onboarding validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
