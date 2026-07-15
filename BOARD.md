# Project Board

## Current Milestone

Initialize the generated repository before implementation begins.

## Ordered Work

1. Set project identity, owner, GitHub slug, and taxonomy intent in `.agents/onboarding.toml`.
2. Mirror project identity in `.codex/onboarding.toml`.
3. Replace the template framing in `README.md`, `CONTEXT.md`, and `STATE.md` with the real project contract.
4. Run `python scripts/validate_onboarding.py --root . --repository OWNER/REPOSITORY`.
5. Push the initialization change and confirm `onboarding / validate` succeeds.
6. Add implementation tooling only for the first accepted open-source milestone.

## Human Gates

- External accounts and connectors
- Production, deployment, and remote runtime access
- Repository settings, rulesets, releases, and destructive actions
- Public API, compatibility, support, and release commitments
