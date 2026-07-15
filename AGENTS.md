# Project Agent Instructions

## Start Here

- Read `CONTEXT.md`, `STATE.md`, and `BOARD.md` before non-trivial work.
- Treat live Git, configuration, tests, trackers, and runtime state as evidence; orientation files do not override them.
- Preserve unrelated user changes and verify the current branch, worktree, and remotes before publishing.

## Project Boundaries

- Keep project identity and taxonomy intent current in `.agents/onboarding.toml`.
- Shared taxonomy registration is explicit and external to this repository; never edit the global taxonomy automatically.
- Browser, WSL, deploy, production, external tracker, plugin, MCP, and connector access are opt-in and require the correct account boundary.
- Keep secrets and runtime state out of the repository.

## Working Agreement

- Follow repository-local instructions and resolve optional tools or specialist workflows from the contributor's live environment; no private host module is a project prerequisite.
- Keep evergreen rules here, domain language in `CONTEXT.md`, current orientation in `STATE.md`, ordering in `BOARD.md`, and implementation detail under `docs/`.
- Use official vendor documentation for current platform behavior.
- Test changes in proportion to risk and provide fresh verification evidence before claiming completion.
- Commits, pushes, releases, deploys, destructive actions, external writes, and credential changes require explicit approval unless a narrower instruction grants it.
