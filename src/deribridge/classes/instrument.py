from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, field_serializer

from ..classes.option_type import OptionType
from ..classes.instrument_type import InstrumentType


class Instrument(BaseModel, ABC):
    instrument_name: str
    instrument_type: InstrumentType
    underlying: str
    expiry: Optional[datetime] = None
    strike: Optional[float] = None
    option_type: Optional[OptionType] = None
    is_perpetual: bool = False
    is_dvol: bool = False

    @classmethod
    @abstractmethod
    def parse_instrument(cls, instrument_name: str) -> "Instrument":
        """
        Abstract method to parse an instrument name.
        Subclasses should implement this method with their specific parsing logic.
        """
        pass

    def get_time_to_expiry_days(self, reference_date: Optional[datetime] = None) -> float:
        """
        Calculate time to expiry in days.

        Args:
            reference_date (datetime, optional): Reference date to calculate from.
                                               Defaults to current UTC time.

        Returns:
            float: Time to expiry in days. Returns 0.0 if:
                   - Instrument has no expiry (perpetuals)
                   - Already expired
                   - Invalid expiry date
        """
        # Return 0 for perpetuals or instruments without expiry
        if self.is_perpetual or self.expiry is None:
            return 0.0

        # Use current UTC time if no reference date provided
        if reference_date is None:
            reference_date = datetime.now(timezone.utc)

        # Ensure reference_date is timezone-aware
        if reference_date.tzinfo is None:
            reference_date = reference_date.replace(tzinfo=timezone.utc)

        # Ensure expiry is timezone-aware and set to 8:00 UTC on expiry date
        expiry_date = self.expiry
        if expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)

        # Set expiry time to 8:00 UTC on the expiry date
        expiry_date = expiry_date.replace(hour=8, minute=0, second=0, microsecond=0)

        # Calculate time difference
        time_delta = expiry_date - reference_date

        # Convert to days (including fractional days)
        days_to_expiry = time_delta.total_seconds() / (24 * 60 * 60)

        # Return 0 if already expired
        return max(0.0, days_to_expiry)

    @field_serializer("expiry")
    def _serialize_expiry(self, value: Optional[datetime], _info) -> Optional[str]:
        """Serialize the expiry datetime as an ISO 8601 string."""
        return value.isoformat() if value is not None else None
