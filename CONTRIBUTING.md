# Contributing to deribridge

Thanks for your interest in improving **deribridge** — the async, typed Python
client and middleware for the [Deribit](https://docs.deribit.com/) API. It is the
open-source transport layer behind [deribook](https://deribook.com) (analytics for
derivatives portfolios on Deribit), and contributions of all sizes are welcome.

## Getting set up

deribridge uses [uv](https://docs.astral.sh/uv/) for environment and dependency
management. Python ≥ 3.12 is required.

```bash
git clone https://github.com/fracasamax/deribridge.git
cd deribridge
uv sync            # creates .venv and installs runtime + dev dependencies
```

Copy the example environment file if you want to run anything against Deribit's
**test** environment (never commit real credentials):

```bash
cp .env.example .env   # then fill in your test keys
```

## Development workflow

Before opening a pull request, make sure the following all pass locally — these are
the same checks CI runs:

```bash
uv run ruff check src tests     # lint
uv run pytest -q                # tests (must stay green, no new warnings)
```

Optional but encouraged:

```bash
uv run mypy src                 # static type checking
```

### Guidelines

- **Keep it typed.** The package ships `py.typed` (PEP 561). New public APIs should
  carry full type annotations and avoid introducing new `mypy` regressions.
- **No silent failures.** Surface errors (log with context or raise) rather than
  swallowing them — this is a financial client where a dropped error can mean a
  dropped order.
- **Add tests for behavior changes.** Put them under `tests/`; async tests run under
  `pytest-asyncio` in `auto` mode.
- **Match the surrounding style.** Run `ruff` and follow the existing module
  conventions (naming, docstrings, comment density).
- **Touch the test environment, not production.** When validating against Deribit,
  use `test.deribit.com` (`use_test_env=True`).

## Pull requests

1. Fork and create a topic branch off `main`.
2. Make focused commits with clear messages.
3. Ensure lint + tests pass and no new deprecation warnings appear.
4. Open a PR describing the change and the motivation. Reference any related issue.

Using `deribridge` in your own project? Open a PR adding it to the **Used by**
section of the README.

## Reporting issues & security

- **Bugs / feature requests:** open an issue at
  <https://github.com/fracasamax/deribridge/issues>.
- **Security concerns** (especially anything affecting order handling or auth):
  please email **Francesco Casamassima** at
  [dev@elnc.eu](mailto:dev@elnc.eu) rather than filing a public issue, so it can be
  addressed before disclosure.

## License

By contributing, you agree that your contributions are licensed under the project's
[MIT License](LICENSE).
