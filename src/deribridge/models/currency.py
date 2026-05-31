from enum import Enum


class Currency(Enum):
    """Enum for currencies supported by Deribit API."""
    BTC = "BTC"
    ETH = "ETH"
    USDC = "USDC"
    USDT = "USDT"
    EURR = "EURR"
    SOL = "SOL"
    XRP = "XRP"
    PAXG = "PAXG"
    BNB = "BNB"
    USDE = "USDE"
    STETH = "STETH"
    ETHW = "ETHW"
    USYC = "USYC"
    ANY = "any"  # Used for wildcard queries

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all currency values (excluding ANY)."""
        return [c.value for c in cls if c != cls.ANY]

    @classmethod
    def is_valid(cls, currency: str) -> bool:
        """Check if a currency string is valid."""
        return currency.upper() in cls.values() or currency.lower() == "any"
