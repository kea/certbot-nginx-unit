# Releasing

Versioning is automatic via `setuptools_scm`: the version is derived from the
latest git tag. Do **not** hand-edit versions — `version.py` is generated and
git-ignored.

## Publish a new release to PyPI

1. Make sure `main` is up to date and green.
2. Create an annotated tag and push it together with the branch:

   ```bash
   git tag -a v1.2.0 -m "v1.2.0"
   git push origin main --follow-tags
   ```

   Use a `vX.Y.Z` tag matching the release you want.

Pushing the tag triggers the `publish-to-pypi` workflow, which runs the tests,
builds the distribution, publishes to **PyPI**, and creates a sigstore-signed
GitHub release.

## Test the pipeline first (TestPyPI)

Every push to `main` (without a tag) publishes a dev version
(`1.2.0.devN`) to **TestPyPI**. Use this to validate the build/publish
pipeline before cutting the real tag:

```bash
git push origin main
```

`skip-existing` is enabled, so re-pushing without new commits won't fail.

## Trigger routing

The single workflow routes by git ref:

| Push               | Publishes to |
|--------------------|--------------|
| branch (`main`)    | TestPyPI     |
| tag (`vX.Y.Z`)     | PyPI + GitHub release |

## One-time setup (already done per environment)

Both targets use PyPI trusted publishing — no API tokens.

- **PyPI**: trusted publisher + `pypi` GitHub environment.
- **TestPyPI**: trusted publisher + `testpypi` GitHub environment.

Register the repo/workflow as a trusted publisher on each index and create the
matching GitHub environment before the first publish.
