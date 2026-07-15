# Public Open-Source Project Template

A language-agnostic Apache-2.0 foundation for public open-source projects. It provides durable project context, deny-first agent overlays, typed documentation, community files, and fail-closed onboarding validation without choosing an implementation stack.

## Initialize A Generated Repository

The copied repository intentionally fails `onboarding / validate` until initialization is complete.

1. In `.agents/onboarding.toml`, set `mode = "project"`.
2. Set `identity.project`, `identity.owner`, and a non-template `identity.status`.
3. Set `taxonomy.intended_workspace` to the project name and `taxonomy.registration = "pending"`.
4. Set `accounts.github` to the actual `OWNER/REPOSITORY` slug.
5. In `.codex/onboarding.toml`, mirror every validated identity field: set `mode` to `project`; keep `template_repository` equal to the source template slug; set `project`, `context_boundary`, `intended_node_type`, `workspace`, and `taxonomy_registration` to the corresponding shared-manifest values; keep `shared_manifest` set to `.agents/onboarding.toml` and `git_required` set to `true`; and make `wsl_required` equal `.agents/onboarding.toml`'s `capabilities.wsl` value.
6. Replace template framing in `README.md`, `CONTEXT.md`, `STATE.md`, and `BOARD.md`.
7. Validate locally:

   ```text
   python scripts/validate_onboarding.py --root . --repository OWNER/REPOSITORY
   ```

8. Push the initialization change and wait for `onboarding / validate` to succeed.
9. Review branch rules only after that first successful run. Choose either signed direct pushes without a required check, or a check-gated pull-request/pre-tested-branch flow; do not combine unrestricted direct-to-`main` pushes with this push-triggered check.
10. Review the license, contribution, conduct, and security policies for the real project before inviting contributions.

Taxonomy registration remains a separate action after the real clone path is known.

This template's onboarding contract is intentionally opinionated for Johan-managed personal projects. Other adopters may replace or remove `.agents/onboarding.toml`, `.codex/onboarding.toml`, the validator, its tests, and the onboarding workflow together before establishing their own project contract.

After the first successful check, review the generated repository's description, topics, visibility, feature toggles, security settings, private vulnerability reporting, and branch rules. Those settings are not inherited from the template repository.

## Included Surfaces

- Shared agent contract and thin project cockpit
- Tool-neutral onboarding metadata
- Minimal Codex and Claude overlays
- Typed documentation manifest and schema
- Standard-library validator and unit tests
- Read-only, immutable-SHA GitHub Actions validation
- Monthly GitHub Actions dependency updates
- Apache-2.0 license and concise contribution, conduct, security, issue, and pull-request guidance

## Security Posture

No account connector, MCP server, plugin, browser, WSL, deploy, production, or tracker capability is enabled by the template. Add only the narrow capability needed for an approved project milestone.

## License

Apache License 2.0. See `LICENSE`.
