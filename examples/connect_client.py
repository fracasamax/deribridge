"""Connect a low-level EnhancedDeribitClient and print it.

Requires Deribit credentials in the environment (see the project README). Reads
test-environment credentials by default.
"""

import asyncio

from deribridge import configure_logging
from deribridge.api_client.client_management import connect_deribit_client


async def main() -> None:
    configure_logging()
    client = await connect_deribit_client()
    print(client)
    if client and hasattr(client, "close"):
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
