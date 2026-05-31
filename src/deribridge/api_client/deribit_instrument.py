import re
from datetime import datetime, timezone

from ..classes.instrument import Instrument
from ..classes.option_type import OptionType
from ..classes.instrument_type import InstrumentType


# Note: DeribitInstrument implements the abstract parse_instrument method
class DeribitInstrument(Instrument):

    @classmethod
    def parse_instrument(cls, instrument_name: str) -> "DeribitInstrument":
        """
        Parse an instrument name and extract its features.

        Expected formats:
        - Option:    BTC-25APR25-66000-P   (underlying-expiry-strike-optionType)
        - Perpetual: BTC-PERPETUAL          (underlying-PERPETUAL)
        - Future:    BTC-25SEP23            (underlying-expiry)
        - DVOL:      BTCDVOL_USDC-25JUN25   (underlying_currency-expiry)
        - Spot:      BTC                    (just underlying)

        Note: For options, futures, and DVOL, the expiry is set to 08:00 UTC.
        """
        # Pattern for options: underlying-expiry-strike-option letter
        option_pattern = re.compile(
            r"^(?P<underlying>[A-Z]+)-(?P<expiry>\d{1,2}[A-Z]{3}\d{2})-(?P<strike>\d+(\.\d+)?)-(?P<option>[CP])$"
        )
        # Pattern for perpetual futures: underlying-PERPETUAL or underlying_currency-PERPETUAL
        perpetual_pattern = re.compile(
            r"^(?P<underlying>[A-Z]+(?:_[A-Z]+)?)-PERPETUAL$"
        )
        # Pattern for DVOL instruments: underlying_currency-expiry (e.g., BTCDVOL_USDC-25JUN25)
        dvol_pattern = re.compile(
            r"^(?P<underlying>[A-Z]+DVOL_[A-Z]+)-(?P<expiry>\d{1,2}[A-Z]{3}\d{2})$"
        )
        # Pattern for futures with expiry: underlying-expiry (expiry in format like 25SEP23)
        future_pattern = re.compile(
            r"^(?P<underlying>[A-Z]+)-(?P<expiry>\d{1,2}[A-Z]{3}\d{2})$"
        )
        # Pattern for spot: just the underlying symbol
        spot_pattern = re.compile(
            r"^(?P<underlying>[A-Z]+)$"
        )

        if match := option_pattern.match(instrument_name):
            underlying = match.group("underlying")
            expiry_str = match.group("expiry")
            strike_str = match.group("strike")
            option_letter = match.group("option")
            try:
                expiry = datetime.strptime(expiry_str, "%d%b%y")
                # Set time to 08:00 UTC
                expiry = expiry.replace(hour=8, minute=0, second=0, tzinfo=timezone.utc)
            except ValueError as e:
                raise ValueError(f"Error parsing expiry date '{expiry_str}': {e}")
            strike = float(strike_str)
            option_type = OptionType(option_letter)
            return cls(
                instrument_name=instrument_name,
                instrument_type=InstrumentType.OPTION,
                underlying=underlying,
                expiry=expiry,
                strike=strike,
                option_type=option_type,
                is_perpetual=False,
                is_dvol=False
            )
        elif match := perpetual_pattern.match(instrument_name):
            underlying = match.group("underlying")
            return cls(
                instrument_name=instrument_name,
                instrument_type=InstrumentType.FUTURE,
                underlying=underlying,
                expiry=None,
                strike=None,
                option_type=None,
                is_perpetual=True,
                is_dvol=False
            )
        elif match := dvol_pattern.match(instrument_name):
            underlying = match.group("underlying")
            expiry_str = match.group("expiry")
            try:
                expiry = datetime.strptime(expiry_str, "%d%b%y")
                # Set time to 08:00 UTC
                expiry = expiry.replace(hour=8, minute=0, second=0, tzinfo=timezone.utc)
            except ValueError as e:
                raise ValueError(f"Error parsing expiry date '{expiry_str}': {e}")
            return cls(
                instrument_name=instrument_name,
                instrument_type=InstrumentType.FUTURE,  # DVOL is treated as a type of future
                underlying=underlying,
                expiry=expiry,
                strike=None,
                option_type=None,
                is_perpetual=False,
                is_dvol=True
            )
        elif match := future_pattern.match(instrument_name):
            underlying = match.group("underlying")
            expiry_str = match.group("expiry")
            try:
                expiry = datetime.strptime(expiry_str, "%d%b%y")
                # Set time to 08:00 UTC
                expiry = expiry.replace(hour=8, minute=0, second=0, tzinfo=timezone.utc)
            except ValueError as e:
                raise ValueError(f"Error parsing expiry date '{expiry_str}': {e}")
            return cls(
                instrument_name=instrument_name,
                instrument_type=InstrumentType.FUTURE,
                underlying=underlying,
                expiry=expiry,
                strike=None,
                option_type=None,
                is_perpetual=False,
                is_dvol=False
            )
        elif match := spot_pattern.match(instrument_name):
            underlying = match.group("underlying")
            return cls(
                instrument_name=instrument_name,
                instrument_type=InstrumentType.SPOT,
                underlying=underlying,
                expiry=None,
                strike=None,
                option_type=None,
                is_perpetual=False,
                is_dvol=False
            )
        else:
            raise ValueError(f"Instrument name '{instrument_name}' does not match any known pattern.")


# Example usage:
if __name__ == "__main__":
    # DVOL instrument example
    dvol = DeribitInstrument.parse_instrument("BTCDVOL_USDC-25JUN25")
    print("DVOL instrument:")
    print(dvol.model_dump_json(indent=2))
    print(f"Is DVOL: {dvol.is_dvol}")

    # Option instrument example
    option = DeribitInstrument.parse_instrument("BTC-25APR25-66000-P")
    print("\nOption instrument:")
    print(option.model_dump_json(indent=2))
    print(f"Is DVOL: {option.is_dvol}")

    # Future instrument example
    future = DeribitInstrument.parse_instrument("BTC-25SEP23")
    print("\nFuture instrument:")
    print(future.model_dump_json(indent=2))
    print(f"Is DVOL: {future.is_dvol}")

    # Perpetual instrument example
    perpetual = DeribitInstrument.parse_instrument("BTC-PERPETUAL")
    print("\nPerpetual instrument:")
    print(perpetual.model_dump_json(indent=2))
    print(f"Is DVOL: {perpetual.is_dvol}")

    # USDC Perpetual instrument example
    usdc_perpetual = DeribitInstrument.parse_instrument("BTC_USDC-PERPETUAL")
    print("\nUSDC Perpetual instrument:")
    print(usdc_perpetual.model_dump_json(indent=2))
    print(f"Is DVOL: {usdc_perpetual.is_dvol}")
