"""Exchange adapters for deribridge.

Each subpackage under ``deribridge.exchanges`` is a self-contained adapter that
bridges one exchange's API shapes and protocols to deribridge's canonical
data model. Adapter code always ships with the package; only an adapter's
third-party dependencies are gated behind optional extras
(e.g. ``pip install deribridge[binance]``) and imported lazily.

This module is intentionally lightweight — importing it must not import any
adapter or pull any adapter's heavy dependencies.
"""
