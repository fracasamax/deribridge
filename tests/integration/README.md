# Integration tests

These talk to the **live** Deribit API and are skipped by default. They run only
when `DERIBRIDGE_RUN_INTEGRATION=1` is set.

| File | Needs credentials? | Notes |
|---|---|---|
| `test_public_endpoints.py` | no | Public market data only. |
| `test_authenticated_readonly.py` | yes (testnet) | Read-only authenticated calls. Skipped if credentials are absent. |

Order placement is intentionally **not** covered here by default; any future
order-mutating integration test must sit behind a second explicit flag
(`DERIBRIDGE_RUN_INTEGRATION_ORDERS=1`) and use testnet credentials only.

```bash
# Public only
DERIBRIDGE_RUN_INTEGRATION=1 uv run python -m pytest tests/integration -q

# With testnet credentials in the environment (see project README)
DERIBRIDGE_RUN_INTEGRATION=1 uv run python -m pytest tests/integration -q
```
