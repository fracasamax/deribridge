# Security Policy

`deribridge` is a client for a live trading venue: it can authenticate with real
Deribit accounts and **place, amend, and cancel real orders**. Security issues
are treated seriously.

## Supported versions

`deribridge` is pre-1.0 beta software. Security fixes are applied to the latest
`0.x` release only.

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |
| < 0.1   | ❌        |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report privately to **dev@elnc.eu**. Include:

- a description of the issue and its impact,
- steps to reproduce or a proof of concept,
- affected version(s) and environment.

You can expect an initial acknowledgement within **5 business days** and a more
detailed response (including a remediation plan or a request for more
information) within **15 business days**. Please allow reasonable time for a fix
before any public disclosure.

## Scope

Areas of particular interest:

- **Authentication & credentials** — credential handling, token refresh, leakage
  of secrets into logs or exceptions.
- **Order submission & lifecycle** — anything that could cause an unintended,
  duplicated, or mis-sized order, or that mishandles the indeterminate-outcome
  contract (timeouts/disconnects on order-mutating calls).
- **Order-state reconciliation** — incorrect tracking that could mislead a
  caller about live orders/positions.
- **Market-data integrity** — dispatching the wrong subscription data to a
  callback.

## A note on trading risk

This is security reporting, not trading advice. Even a perfectly secure release
can place orders that lose money. Always test against the Deribit **testnet**
first and review the [Disclaimer](README.md#️-disclaimer) in the README.
