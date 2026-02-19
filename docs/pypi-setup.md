# PyPI Publishing Setup

This package uses **Trusted Publishing** (OIDC) for secure PyPI uploads — no API tokens needed.

## How It Works

1. `release-please.yml` creates GitHub releases when commits land on `main`
2. `publish.yml` triggers on `release: published` events
3. GitHub Actions OIDC token authenticates directly with PyPI

## First-Time Setup

### Configure PyPI Trusted Publishing

Go to https://pypi.org/manage/account/publishing/ and add a new publisher:

| Field | Value |
|-------|-------|
| PyPI Project Name | `atlas-session-lifecycle` |
| Owner | `anombyte93` |
| Repository | `anombyte93/atlas-session-lifecycle` |
| Workflow name | `publish.yml` |
| Environment name | (leave empty) |

### Verify Workflow

Check `.github/workflows/publish.yml` has:
```yaml
permissions:
  id-token: write  # Required for trusted publishing
```

### Test Build Locally

```bash
cd src
python -m build
twine check dist/*
```

## Creating a Release

1. Commit with conventional commit format:
   - `feat: add new feature` → minor bump
   - `fix: bug fix` → patch bump

2. Push to `main`:
   ```bash
   git checkout main
   git pull
   git merge feature-branch
   git push
   ```

3. `release-please` bot creates a PR titled `chore(main): release X.Y.Z`

4. Merge the release PR → GitHub release created → PyPI publishes automatically

## Version Bumping

`release-please` handles versioning automatically based on commit types:
- `feat:` → minor version bump (4.1.0 → 4.2.0)
- `fix:` → patch version bump (4.1.0 → 4.1.1)
- `BREAKING CHANGE:` → major version bump

## Optional Dependencies

To install with Stripe support:
```bash
pip install atlas-session-lifecycle[stripe]
```

## Troubleshooting

### Build fails locally
```bash
pip install --upgrade build twine
```

### PyPI publish fails
- Verify trusted publishing is configured in PyPI account
- Check `id-token: write` permission in workflow
- Ensure workflow name matches exactly (`publish.yml`)

### Release PR not created
- Check `release-please.yml` runs on `main` branch
- Verify GitHub Actions has `contents: write` permission
