from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
import tomllib


TEMPLATE_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = TEMPLATE_ROOT / "scripts" / "validate_onboarding.py"


class ValidatorFixture:
    def __init__(self, root: Path) -> None:
        self.root = root

    def write_text(self, relative: str, content: str) -> None:
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")

    def write_json(self, relative: str, payload: object) -> None:
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def make_valid_template(self) -> None:
        self.write_text(
            ".agents/onboarding.toml",
            """
            schema_version = "agent-project-onboarding/v1"
            mode = "template"
            template_repository = "johansabent/template-public-oss"

            [identity]
            project = "template-public-oss"
            owner = "johansabent"
            status = "template"

            [taxonomy]
            intended_node_type = "personal-project"
            intended_context_boundary = "personal"
            intended_workspace = "template-public-oss"
            registration = "deferred"
            node_id = ""
            parent_id = ""

            [accounts]
            github = "johansabent/template-public-oss"

            [project_docs]
            agents_doc = "AGENTS.md"
            board_doc = "BOARD.md"
            context_doc = "CONTEXT.md"
            state_doc = "STATE.md"
            manifest = "docs/MANIFEST.json"

            [capabilities]
            browser = false
            wsl = false
            deploy = false
            production = false
            trackers = false
            plugins = false
            mcp_servers = false
            account_connectors = false
            """,
        )
        self.write_text(
            ".codex/onboarding.toml",
            """
            schema_version = "codex-project-onboarding/v1"
            mode = "template"
            template_repository = "johansabent/template-public-oss"
            project = "template-public-oss"
            context_boundary = "personal"
            intended_node_type = "personal-project"
            workspace = "template-public-oss"
            taxonomy_registration = "deferred"
            shared_manifest = ".agents/onboarding.toml"
            git_required = true
            wsl_required = false
            """,
        )
        for name in ("AGENTS.md", "BOARD.md", "CONTEXT.md", "STATE.md"):
            self.write_text(name, f"# {name.removesuffix('.md')}\n")
        self.write_text("docs/README.md", "# Documentation\n")
        self.write_text("docs/schemas/docs-manifest.schema.json", "{}\n")
        self.write_json(
            "docs/MANIFEST.json",
            {
                "schema_version": "project-docs-manifest/v1",
                "canonical": {
                    "agents": "AGENTS.md",
                    "board": "BOARD.md",
                    "context": "CONTEXT.md",
                    "state": "STATE.md",
                    "docs_index": "docs/README.md",
                    "manifest_schema": "docs/schemas/docs-manifest.schema.json",
                },
                "categories": {"schemas": "docs/schemas"},
            },
        )

    def run(self, repository: str | None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.pop("GITHUB_REPOSITORY", None)
        command = [sys.executable, str(VALIDATOR), "--root", str(self.root)]
        if repository is not None:
            command.extend(["--repository", repository])
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )


class ValidateOnboardingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = ValidatorFixture(Path(self.temp.name))
        self.fixture.make_valid_template()

    def test_template_mode_passes_in_exact_template_repository(self) -> None:
        result = self.fixture.run("johansabent/template-public-oss")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("onboarding validation passed", result.stdout)

    def test_template_mode_fails_in_generated_repository(self) -> None:
        result = self.fixture.run("someone/generated-oss")

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "template mode is valid only in johansabent/template-public-oss",
            result.stdout,
        )

    def test_missing_runtime_repository_identity_fails_closed(self) -> None:
        result = self.fixture.run(None)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "repository identity is required; pass --repository OWNER/REPO",
            result.stdout,
        )

    def test_initialized_project_mode_passes_with_pending_registration(self) -> None:
        manifest = (self.fixture.root / ".agents/onboarding.toml").read_text(encoding="utf-8")
        manifest = manifest.replace('mode = "template"', 'mode = "project"')
        manifest = manifest.replace('project = "template-public-oss"', 'project = "sample-oss"')
        manifest = manifest.replace('status = "template"', 'status = "active"')
        manifest = manifest.replace(
            'intended_workspace = "template-public-oss"',
            'intended_workspace = "sample-oss"',
        )
        manifest = manifest.replace('registration = "deferred"', 'registration = "pending"')
        manifest = manifest.replace(
            'owner = "johansabent"',
            'owner = "someone"',
        )
        manifest = manifest.replace(
            'github = "johansabent/template-public-oss"',
            'github = "someone/sample-oss"',
        )
        (self.fixture.root / ".agents/onboarding.toml").write_text(manifest, encoding="utf-8")
        codex_path = self.fixture.root / ".codex/onboarding.toml"
        codex = codex_path.read_text(encoding="utf-8")
        codex = codex.replace('mode = "template"', 'mode = "project"')
        codex = codex.replace('project = "template-public-oss"', 'project = "sample-oss"')
        codex = codex.replace('workspace = "template-public-oss"', 'workspace = "sample-oss"')
        codex = codex.replace('taxonomy_registration = "deferred"', 'taxonomy_registration = "pending"')
        codex_path.write_text(codex, encoding="utf-8")

        result = self.fixture.run("someone/sample-oss")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_project_mode_rejects_stale_codex_identity(self) -> None:
        path = self.fixture.root / ".agents/onboarding.toml"
        manifest = path.read_text(encoding="utf-8")
        manifest = manifest.replace('mode = "template"', 'mode = "project"')
        manifest = manifest.replace('project = "template-public-oss"', 'project = "sample-oss"')
        manifest = manifest.replace('status = "template"', 'status = "active"')
        manifest = manifest.replace(
            'intended_workspace = "template-public-oss"',
            'intended_workspace = "sample-oss"',
        )
        manifest = manifest.replace('registration = "deferred"', 'registration = "pending"')
        manifest = manifest.replace('owner = "johansabent"', 'owner = "someone"')
        manifest = manifest.replace(
            'github = "johansabent/template-public-oss"',
            'github = "someone/sample-oss"',
        )
        path.write_text(manifest, encoding="utf-8")

        result = self.fixture.run("someone/sample-oss")

        self.assertEqual(result.returncode, 1)
        self.assertIn("codex.project must equal identity.project", result.stdout)

    def test_registered_taxonomy_requires_node_id(self) -> None:
        path = self.fixture.root / ".agents/onboarding.toml"
        manifest = path.read_text(encoding="utf-8").replace(
            'registration = "deferred"', 'registration = "registered"'
        )
        path.write_text(manifest, encoding="utf-8")

        result = self.fixture.run("johansabent/template-public-oss")

        self.assertEqual(result.returncode, 1)
        self.assertIn("taxonomy.node_id is required when registration is registered", result.stdout)

    def test_canonical_path_cannot_escape_repository(self) -> None:
        path = self.fixture.root / "docs/MANIFEST.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["canonical"]["state"] = "../outside.md"
        self.fixture.write_json("docs/MANIFEST.json", payload)

        result = self.fixture.run("johansabent/template-public-oss")

        self.assertEqual(result.returncode, 1)
        self.assertIn("canonical.state must stay inside the repository", result.stdout)

    def test_missing_canonical_path_fails(self) -> None:
        (self.fixture.root / "CONTEXT.md").unlink()

        result = self.fixture.run("johansabent/template-public-oss")

        self.assertEqual(result.returncode, 1)
        self.assertIn("canonical.context does not exist: CONTEXT.md", result.stdout)

    def test_canonical_authority_must_be_a_regular_file(self) -> None:
        (self.fixture.root / "CONTEXT.md").unlink()
        (self.fixture.root / "CONTEXT.md").mkdir()

        result = self.fixture.run("johansabent/template-public-oss")

        self.assertEqual(result.returncode, 1)
        self.assertIn("canonical.context must be a regular file: CONTEXT.md", result.stdout)
        self.assertIn("project_docs.context_doc must be a regular file: CONTEXT.md", result.stdout)

    def test_empty_registered_category_fails(self) -> None:
        (self.fixture.root / "docs/references").mkdir()
        path = self.fixture.root / "docs/MANIFEST.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["categories"]["references"] = "docs/references"
        self.fixture.write_json("docs/MANIFEST.json", payload)

        result = self.fixture.run("johansabent/template-public-oss")

        self.assertEqual(result.returncode, 1)
        self.assertIn("category references is empty: docs/references", result.stdout)

    def test_duplicate_canonical_paths_fail(self) -> None:
        path = self.fixture.root / "docs/MANIFEST.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["canonical"]["context"] = "STATE.md"
        self.fixture.write_json("docs/MANIFEST.json", payload)

        result = self.fixture.run("johansabent/template-public-oss")

        self.assertEqual(result.returncode, 1)
        self.assertIn("canonical paths must be unique", result.stdout)

    def test_project_docs_must_match_canonical_authorities(self) -> None:
        onboarding_path = self.fixture.root / ".agents/onboarding.toml"
        onboarding = onboarding_path.read_text(encoding="utf-8").replace(
            'context_doc = "CONTEXT.md"', 'context_doc = "ALT_CONTEXT.md"'
        )
        onboarding_path.write_text(onboarding, encoding="utf-8")
        self.fixture.write_text("ALT_CONTEXT.md", "# Alternate\n")

        result = self.fixture.run("johansabent/template-public-oss")

        self.assertEqual(result.returncode, 1)
        self.assertIn("project_docs.context_doc must equal canonical.context", result.stdout)

    def test_canonical_map_cannot_be_empty(self) -> None:
        path = self.fixture.root / "docs/MANIFEST.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["canonical"] = {}
        self.fixture.write_json("docs/MANIFEST.json", payload)

        result = self.fixture.run("johansabent/template-public-oss")

        self.assertEqual(result.returncode, 1)
        self.assertIn("canonical must contain at least one path", result.stdout)

    def test_category_must_be_one_segment_below_docs(self) -> None:
        self.fixture.write_text("docs/nested/deeper/item.md", "# Item\n")
        path = self.fixture.root / "docs/MANIFEST.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["categories"]["nested"] = "docs/nested/deeper"
        self.fixture.write_json("docs/MANIFEST.json", payload)

        result = self.fixture.run("johansabent/template-public-oss")

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "category nested must be exactly one directory below docs/: docs/nested/deeper",
            result.stdout,
        )


class TemplateSourceTests(unittest.TestCase):
    def test_template_source_tree_validates(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                "--root",
                str(TEMPLATE_ROOT),
                "--repository",
                "johansabent/template-public-oss",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_workflow_is_read_only_and_uses_immutable_action_revisions(self) -> None:
        workflow = (TEMPLATE_ROOT / ".github/workflows/onboarding.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn(
            "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7.0.0",
            workflow,
        )
        self.assertIn(
            "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6.3.0",
            workflow,
        )
        self.assertIn('python-version: "3.13"', workflow)
        self.assertIn("name: onboarding / validate", workflow)
        self.assertIn("if: github.event_name != 'push' || !github.event.repository.fork", workflow)
        self.assertIn("python -m unittest discover -s tests -v", workflow)
        self.assertIn(
            'python scripts/validate_onboarding.py --root . --repository "$GITHUB_REPOSITORY"',
            workflow,
        )
        self.assertNotIn("${{ github.event", workflow)

    def test_overlays_enable_no_account_scoped_capability(self) -> None:
        claude = json.loads(
            (TEMPLATE_ROOT / ".claude/settings.json").read_text(encoding="utf-8")
        )
        with (TEMPLATE_ROOT / ".codex/onboarding.toml").open("rb") as handle:
            codex = tomllib.load(handle)
        codex_config = (TEMPLATE_ROOT / ".codex/config.toml").read_text(encoding="utf-8")

        self.assertTrue(claude["disableClaudeAiConnectors"])
        self.assertFalse(claude["enableAllProjectMcpServers"])
        self.assertEqual(claude["enabledMcpjsonServers"], [])
        self.assertEqual(claude["enabledPlugins"], {})
        self.assertEqual(codex["capability_policy"]["account_connectors"], "approval-required")
        self.assertNotIn("[mcp_servers.", codex_config)
        self.assertNotIn("[plugins.", codex_config)

    def test_readme_names_every_codex_identity_mirror(self) -> None:
        readme = (TEMPLATE_ROOT / "README.md").read_text(encoding="utf-8")

        for field in (
            "mode",
            "template_repository",
            "project",
            "context_boundary",
            "intended_node_type",
            "workspace",
            "taxonomy_registration",
            "shared_manifest",
            "git_required",
            "wsl_required",
        ):
            self.assertIn(f"`{field}`", readme)

    def test_public_agent_routing_has_no_private_host_dependencies(self) -> None:
        with (TEMPLATE_ROOT / ".agents/onboarding.toml").open("rb") as handle:
            onboarding = tomllib.load(handle)

        self.assertEqual(onboarding["capability_policy"]["routing"], "project-local")
        self.assertEqual(onboarding["capability_policy"]["entrypoints"], [])

    def test_public_community_files_are_complete_without_service_level_promises(self) -> None:
        license_text = (TEMPLATE_ROOT / "LICENSE").read_text(encoding="utf-8")
        security = (TEMPLATE_ROOT / "SECURITY.md").read_text(encoding="utf-8")
        contributing = (TEMPLATE_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        conduct = (TEMPLATE_ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")

        self.assertIn("Apache License\nVersion 2.0, January 2004", license_text)
        self.assertIn("private vulnerability reporting", security.casefold())
        self.assertIsNone(re.search(r"\b\S+@\S+\.\S+\b", security))
        self.assertIsNone(re.search(r"\b(?:within|response in)\s+\d+\s+(?:hours?|days?)", security, re.I))
        self.assertIn("onboarding / validate", contributing)
        self.assertIn("## Enforcement", conduct)

    def test_public_issue_forms_are_structured(self) -> None:
        issue_root = TEMPLATE_ROOT / ".github/ISSUE_TEMPLATE"
        for name in ("bug-report.yml", "feature-request.yml"):
            text = (issue_root / name).read_text(encoding="utf-8")
            self.assertIn("name:", text)
            self.assertIn("description:", text)
            self.assertIn("body:", text)
            self.assertIn("validations:", text)
        config = (issue_root / "config.yml").read_text(encoding="utf-8")
        self.assertIn("blank_issues_enabled: false", config)


if __name__ == "__main__":
    unittest.main()
