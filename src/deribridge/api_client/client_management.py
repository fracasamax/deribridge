import logging
import os
from typing import Optional

from dotenv import load_dotenv

from .enhanced_api_client import EnhancedDeribitClient


def get_credentials(use_test_env: bool = True) -> tuple:
    """
    Retrieve API credentials from environment variables or configuration.
    This is a placeholder function. Replace with actual implementation.
    """
    # Example: Load from environment variables
    load_dotenv()
    client_id = os.getenv("DERIBIT_API_CLIENT_ID" + ("_TEST" if use_test_env else ""))
    client_secret = os.getenv("DERIBIT_API_SECRET" + ("_TEST" if use_test_env else ""))
    return client_id, client_secret


async def connect_deribit_client(
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        use_test_env: bool = True,
        authenticate: bool = True,
        custom_logger: Optional[logging.Logger] = None
) -> EnhancedDeribitClient:
    """
    Connect to Deribit API and optionally authenticate.

    Args:
        client_id: Deribit API client ID
        client_secret: Deribit API client secret
        use_test_env: Whether to use test environment (default: True)
        authenticate: Whether to authenticate (default: True)
        custom_logger: Custom logger to use (default: None, creates a new one)

    Returns:
        Connected and authenticated EnhancedDeribitClient

    Raises:
        ConnectionError: If connection fails
        ValueError: If authentication fails when requested
        Exception: For other errors
    """
    # Setup logger
    log = custom_logger or logging.getLogger("deribit_client")

    # try to retrieve credentials if not provided
    if not client_id or not client_secret:
        _client_id, _client_secret = get_credentials(use_test_env)
        if not client_id:
            client_id = _client_id
        if not client_secret:
            client_secret = _client_secret

    # Validate credentials if authentication is required
    if authenticate and (not client_id or not client_secret):
        raise ValueError("Authentication requested but client_id or client_secret is missing")

    try:
        # Log connection attempt
        log.info(f"Connecting to Deribit {'test' if use_test_env else 'production'} environment")

        # Create client instance
        client = EnhancedDeribitClient(
            client_id=client_id,
            client_secret=client_secret,
            use_test_env=use_test_env,
            auto_connect=False,
        )

        # Connect to WebSocket API
        await client.connect()
        if not client.connected:
            raise ConnectionError("Failed to connect to Deribit API")

        # Authenticate if requested
        if authenticate:
            log.info("Authenticating with Deribit API")
            await client.authenticate()
            if not client.authenticated:
                raise ValueError("Authentication failed")
            log.info("Authentication successful")

        return client

    except ConnectionError as e:
        log.error(f"Connection error: {str(e)}")
        raise
    except ValueError as e:
        log.error(f"Authentication error: {str(e)}")
        if client and client.connected:
            await client.close()
        raise
    except Exception as e:
        log.error(f"Unexpected error during connection: {str(e)}")
        if client and client.connected:
            await client.close()
        raise
