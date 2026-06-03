# Contributing to decroche-mcp

Thanks for your interest in contributing! This guide explains how to get set up and submit changes.

## Code of Conduct

This project follows the [Contributor Covenant](./CODE_OF_CONDUCT.md). By participating you agree to
uphold it.

## Development setup

We pin tool versions with [mise](https://mise.jdx.dev/) and provide a devcontainer for a
one-command environment.

```bash
# Option A: devcontainer (VS Code / GitHub Codespaces) — opens a ready-made environment.
# Option B: local with mise
mise install            # installs pinned runtimes
mise run setup          # install project dependencies

# Option C: direct uv
uv venv
uv sync --extra dev
```

## Workflow

1. Fork and create a branch: `git checkout -b feat/short-description` (or `fix/...`).
2. Make your change with tests.
3. Run the full local gate before pushing:
   ```bash
   uv run ruff check .
   uv run ruff format --check .
   uv run pytest --cov --cov-fail-under=80
   ```
4. Commit using **[Conventional Commits](https://www.conventionalcommits.org/)**
   (`feat:`, `fix:`, `docs:`, ...). This drives automated versioning and the changelog.
5. **Sign your commits** (`git commit -S`, or configure SSH/Sigstore signing). Signed commits are
   required by branch rules.
6. Open a pull request; fill in the PR template, including a test plan.

## Quality bar

- Tests required for new behavior and bug fixes; **coverage must stay >= 80%**.
- Lint/format (`ruff`), and CI must be green.
- Keep functions small (< 50 lines) and files focused (< 800 lines).
- No secrets, credentials, or PII in commits or history.

## Reporting bugs / requesting features

Use the issue forms. For **security vulnerabilities**, do NOT open a public issue — see
[SECURITY.md](./SECURITY.md).

## License

By contributing, you agree your contributions are licensed under the project's
[MIT](./LICENSE) license.
