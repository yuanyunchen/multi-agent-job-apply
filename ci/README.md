# Continuous integration

`github-actions-ci.yml` is the GitHub Actions workflow for this project: it
installs the package on Python 3.10-3.12, runs the full test suite, the
sanitize scan (personal data, machine paths, non-English text), the bot
template check, and the fresh-clone migration check.

It lives here instead of `.github/workflows/` because the account that
published this version could not create workflow files. To turn it on, copy it
into place and commit:

```bash
mkdir -p .github/workflows
cp ci/github-actions-ci.yml .github/workflows/ci.yml
git add .github/workflows/ci.yml && git commit -m "Enable CI"
```

You can run the same checks locally at any time with `make test sanitize` or
`scripts/migration_check.sh`.
