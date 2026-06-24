"""Base class and field types shared by all canonical models."""
from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from .._util import opt_decimal, to_decimal

# Annotated field types: prices, amounts, balances and fees are Decimal and
# coerced losslessly (strings, ints, floats all become exact Decimals).
Money = Annotated[Decimal, BeforeValidator(to_decimal)]
OptMoney = Annotated[Optional[Decimal], BeforeValidator(opt_decimal)]


class CanonicalModel(BaseModel):
    """Base for every exchange-agnostic data class.

    Carries a ``raw`` passthrough of the untouched wire payload so venue-only
    fields are never lost without bloating the canonical surface. Access them
    with :meth:`x`.
    """

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    raw: dict[str, Any] = Field(default_factory=dict, repr=False)

    def x(self, key: str, default: Any = None) -> Any:
        """Read a venue-specific field from the original wire payload."""
        return self.raw.get(key, default)
