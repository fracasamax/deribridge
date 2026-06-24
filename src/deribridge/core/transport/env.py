"""Generic credential loading from the environment.

Reads ``{EXCHANGE}_API_KEY`` / ``{EXCHANGE}_API_SECRET`` / ``{EXCHANGE}_API_PASSPHRASE``
(e.g. ``DERIBIT_API_KEY``, ``BINANCE_API_SECRET``), optionally loading a
``.env`` file first. This generalizes the Deribit-specific credential helper so
every adapter can source credentials uniformly.
"""
from __future__ import annotations

import os
from typing import Optional

from .auth import Credentials


def load_credentials(exchange: str, *, load_dotenv_file: bool = True) -> Credentials:
    """Build :class:`Credentials` for ``exchange`` from environment variables.

    Args:
        exchange: adapter name, e.g. ``"deribit"`` -> reads ``DERIBIT_API_*``.
        load_dotenv_file: if True, load a ``.env`` file into the environment
            first (best-effort; a no-op when python-dotenv is unavailable).
    """
    if load_dotenv_file:
        _maybe_load_dotenv()

    prefix = exchange.upper()
    return Credentials(
        key=os.getenv(f"{prefix}_API_KEY"),
        secret=os.getenv(f"{prefix}_API_SECRET"),
        passphrase=os.getenv(f"{prefix}_API_PASSPHRASE"),
    )


def _maybe_load_dotenv() -> Optional[bool]:
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv is a core dep, but stay defensive
        return None
    return load_dotenv()
