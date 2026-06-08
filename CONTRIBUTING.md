# Contributing

Thank you for your interest in improving this project.

## Getting Started

1. **Fork** the repository and create a branch from `main`.
2. Follow the [Quick Start](README.md#quick-start) guide to get the project running locally.
3. Make your changes with focused, well-scoped commits.
4. Open a pull request against `main`.

## Branch Naming

| Type | Pattern | Example |
|---|---|---|
| Feature | `feat/<short-description>` | `feat/rtsp-camera-support` |
| Bug fix | `fix/<short-description>` | `fix/face-match-threshold` |
| Docs | `docs/<short-description>` | `docs/deployment-guide` |
| Chore | `chore/<short-description>` | `chore/bump-dependencies` |

## Code Style

- **Python:** Follow PEP 8. Run `ruff check .` before committing.
- **Type hints:** All new functions must have type annotations.
- **Tests:** Add or update tests for any behaviour changes. Run `pytest tests/ -v` to confirm.
- **Comments:** Only when the *why* is non-obvious — not the *what*.

## Commit Messages

Use the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <short summary>

[optional body — explain why, not what]
```

Examples:
```
feat(ai-engine): load config from dotenv instead of hardcoded values
fix(decision): lower face cosine threshold to 0.45 for noisy captures
docs(readme): add RTSP camera configuration section
```

## Security

**Never commit secrets.** This includes API keys, passwords, JWT secrets, or face embeddings.

- Copy `.env.example` → `.env` locally and fill in your own values.
- Copy `config.env.example` → `config.env` locally.
- Both files are in `.gitignore` — double-check with `git status` before every commit.

If you discover a security vulnerability, please report it privately via [SECURITY.md](SECURITY.md) rather than opening a public issue.

## Pull Request Checklist

- [ ] My changes run without errors locally.
- [ ] I have added/updated tests where relevant.
- [ ] `pytest tests/ -v` passes.
- [ ] No secrets or personal data are included.
- [ ] The PR description explains *what* changed and *why*.

## Questions

Open a [GitHub Discussion](../../discussions) for design questions or feature ideas before starting large changes.
