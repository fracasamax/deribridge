# Release checklist

Run through this before tagging a release. Every command must pass; read the
output, don't assume.

## 1. Quality gate

```bash
uv sync
uv run ruff check src tests examples
uv run python -m pytest -q
uv run --with mypy -- mypy src
uv run --with build python -m build
uv run --with pip-audit -- pip-audit
uv lock --check
```

- [ ] `ruff` clean
- [ ] full test suite passes (record the count; it should not regress)
- [ ] `mypy src` passes
- [ ] sdist + wheel build
- [ ] `pip-audit` reports no known vulnerabilities
- [ ] lockfile is up to date (`uv lock --check`)

## 2. Docs & metadata

- [ ] `README.md` reviewed (install, quick start, order-safety note current)
- [ ] `CHANGELOG.md` updated; the release entry dated and breaking changes noted
- [ ] `pyproject.toml` version bumped (and `src/deribridge/__init__.py`
      `__version__` matches)
- [ ] classifiers / `Development Status` accurate

## 3. Live smoke check (Deribit testnet)

Using **testnet** credentials only:

- [ ] public endpoint read (e.g. fetch a ticker) — no credentials path
- [ ] authenticated read-only call (e.g. account summary / positions)
- [ ] (optional) a single gated test order placed and cancelled on testnet

## 4. Tag & publish

```bash
git tag v<version>
git push origin v<version>
```

- [ ] tag pushed
- [ ] build artifacts published (when publishing to PyPI)
