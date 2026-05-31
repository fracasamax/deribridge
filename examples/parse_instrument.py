"""Parse Deribit instrument names into typed DeribitInstrument objects.

Pure parsing — no network or credentials required.
"""

from deribridge import DeribitInstrument

EXAMPLES = [
    "BTCDVOL_USDC-25JUN25",
    "BTC-25APR25-66000-P",
    "BTC-25SEP23",
    "BTC-PERPETUAL",
    "BTC_USDC-PERPETUAL",
]


def main() -> None:
    for name in EXAMPLES:
        inst = DeribitInstrument.parse_instrument(name)
        print(f"\n{name} (is_dvol={inst.is_dvol}):")
        print(inst.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
