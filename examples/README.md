# Examples

Runnable examples for `deribridge`. Importing the package has no side effects;
these scripts are kept here (rather than in `__main__` blocks inside the package)
so the library stays import-safe.

| Script | Network? | Credentials? | Notes |
|---|---|---|---|
| [`parse_instrument.py`](parse_instrument.py) | no | no | Parse instrument names into typed objects. |
| [`build_order.py`](build_order.py) | no | no | Build `Order` objects and inspect API params. |
| [`connect_client.py`](connect_client.py) | yes | yes | Connect a low-level client (uses test env by default). |
| [`run_api_interface.py`](run_api_interface.py) | yes | yes | **Can place a REAL order** — gated, testnet only. |

## Running

```bash
# No-credentials examples
python examples/parse_instrument.py
python examples/build_order.py

# Credentialed examples (see the project README for .env setup)
python examples/connect_client.py

# Order-placing example is gated behind an explicit flag — use TESTNET keys
DERIBRIDGE_ALLOW_EXAMPLE_ORDERS=1 python examples/run_api_interface.py
```
