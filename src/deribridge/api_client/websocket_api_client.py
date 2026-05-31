import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Dict, List, Optional, Union, Any, Callable
import websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed

from ..classes.currency import Currency
from ..classes.order import OrderType, TimeInForce
from ..classes.order_purpose import OrderPurpose
from .deribit_error_codes import get_error_message, get_short_message


class DeribitWebSocketError(Exception):
    """Custom exception for Deribit WebSocket API errors."""

    def __init__(self, code: int, message: str, data: Optional[Dict] = None):
        self.code = code
        self.message = message or get_error_message(code)
        self.short_message = get_short_message(code) or '-'
        self.data = data
        super().__init__(f"Deribit WebSocket Error (Code {code} [{self.short_message}]): {self.message}")


class DeribitWebSocketClient:
    """
    A production-grade WebSocket API client for the Deribit cryptocurrency exchange.

    This client provides real-time access to market data, trading operations, and account
    information using WebSockets for low-latency communication.
    """

    PRODUCTION_WS_URL = "wss://www.deribit.com/ws/api/v2"
    TEST_WS_URL = "wss://test.deribit.com/ws/api/v2"

    def __init__(
            self,
            client_id: Optional[str] = None,
            client_secret: Optional[str] = None,
            use_test_env: bool = False,
            auto_connect: bool = False,
            heartbeat_interval: int = 30,
    ):
        """
        Initialize the Deribit WebSocket API client.

        Args:
            client_id: Your Deribit API client ID (optional for public endpoints)
            client_secret: Your Deribit API client secret (optional for public endpoints)
            use_test_env: Whether to use the test environment (default: False)
            auto_connect: Whether to automatically connect on initialization
                (default: False). When True, schedules a background connect()
                task, which requires a running event loop; construction then
                performs implicit network I/O. Leave False and call connect()
                explicitly unless you are constructing from within a running loop.
            heartbeat_interval: Interval in seconds for sending heartbeats (default: 30)
        """
        self.client_id = str(client_id).strip() if client_id else ""
        self.client_secret = str(client_secret).strip() if client_secret else ""
        self.heartbeat_interval = heartbeat_interval
        self.logger = logging.getLogger(__name__)
        # Set the base URL based on environment
        self.ws_url = self.TEST_WS_URL if use_test_env else self.PRODUCTION_WS_URL
        self.is_test_env = use_test_env

        # WebSocket connection
        self.ws: Optional[ClientConnection] = None
        self.connected = False
        self.connecting = False
        self.authenticated = False

        # Connection management
        self.heartbeat_task: Optional[asyncio.Task[None]] = None
        self.message_handler_task: Optional[asyncio.Task[None]] = None
        self.auth_refresh_task: Optional[asyncio.Task[None]] = None
        self.reconnect_delay: float = 1  # Start with 1 second
        self.max_reconnect_delay = 60  # Max 60 seconds

        # Message handling
        self.message_id = 0
        self.pending_requests: Dict[int, "asyncio.Future[Any]"] = {}
        # Exact-match channel -> callback. Subscription dispatch does an O(1)
        # lookup here for the common case (concrete channels such as
        # "ticker.BTC-PERPETUAL.100ms").
        self.callback_handlers: Dict[str, Callable] = {}
        # Subset of handlers whose channel ends in "*" (suffix wildcard, matched
        # by prefix). Kept separate so dispatch only scans these few entries
        # instead of every handler. Mirrors entries in callback_handlers.
        self._wildcard_handlers: Dict[str, Callable] = {}
        self.subscription_channels: set[str] = set()

        # Authentication state
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        self._refresh_token: Optional[str] = None
        self._refresh_token_expiry: float = 0

        # Connection lock to prevent race conditions
        self._connection_lock = asyncio.Lock()

        # Connect automatically if required
        if auto_connect:
            asyncio.create_task(self.connect())

    def set_environment(self, use_test_env: bool = False) -> None:
        """
        Set the API environment (production or test).

        Args:
            use_test_env: Whether to use the test environment
        """
        self.ws_url = self.TEST_WS_URL if use_test_env else self.PRODUCTION_WS_URL
        self.is_test_env = use_test_env
        self.logger.info(f"Using {'test' if use_test_env else 'production'} environment")

    def next_message_id(self) -> int:
        """
        Get the next message ID for a request.

        Returns:
            The next message ID
        """
        self.message_id += 1
        return self.message_id

    async def connect(self) -> None:
        """
        Connect to the Deribit WebSocket API.

        The whole connect -> resubscribe -> authenticate sequence is performed
        while holding ``self._connection_lock``. This makes a reconnect atomic:
        a concurrent reconnect cannot interleave and observe a half-open,
        unauthenticated socket, and private requests (which acquire the same
        lock, see ``send_request``) cannot be sent during this window.

        Raises:
            Exception: If connection fails
        """
        async with self._connection_lock:
            if self.connected or self.connecting:
                return

            self.connecting = True

            try:
                self.logger.info(f"Connecting to Deribit WebSocket API at {self.ws_url}")
                self.ws = await websockets.connect(self.ws_url)
                self.connected = True
                self.reconnect_delay = 1  # Reset reconnect delay on successful connection

                # Start message handler
                self.message_handler_task = asyncio.create_task(self._message_handler())

                # Start heartbeat task
                self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

                # Resubscribe to channels if any. Safe to call send_request here:
                # self.connected is already True so it will not recurse into
                # connect(), and we hold the lock so no other connect/reconnect
                # can run concurrently.
                if self.subscription_channels:
                    await self._resubscribe()

                # Reauthenticate if needed, still under the lock so the
                # authenticated flag and the socket are published together.
                if self.client_id and self.client_secret:
                    await self._authenticate_credentials()

                self.logger.info("Successfully connected to Deribit WebSocket API")
            except Exception as e:
                self.logger.error(f"Failed to connect to Deribit WebSocket API: {str(e)}")
                self.connected = False
                self.authenticated = False
                asyncio.create_task(self._reconnect())
            finally:
                self.connecting = False

    async def close(self) -> None:
        """
        Close the WebSocket connection.
        """
        self.logger.info("Closing WebSocket connection")

        # Cancel tasks
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None

        if self.message_handler_task:
            self.message_handler_task.cancel()
            self.message_handler_task = None

        if self.auth_refresh_task:
            self.auth_refresh_task.cancel()
            self.auth_refresh_task = None

        # Close the WebSocket
        if self.ws and self.connected:
            await self.ws.close()
            self.connected = False
            self.authenticated = False
            
            # Cancel all pending requests
            for message_id, future in self.pending_requests.items():
                if not future.done():
                    future.set_exception(DeribitWebSocketError(-1, "Client closed"))
            self.pending_requests.clear()
            
            self.logger.info("WebSocket connection closed")

    async def _reconnect(self) -> None:
        """
        Attempt to reconnect to the WebSocket API with exponential backoff.
        """
        if self.connecting:
            return

        self.logger.info(f"Attempting to reconnect in {self.reconnect_delay} seconds")
        await asyncio.sleep(self.reconnect_delay)

        # Exponential backoff with jitter
        self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
        self.reconnect_delay += (self.reconnect_delay * 0.1 * (asyncio.get_event_loop().time() % 1))

        # Cancel existing tasks
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None

        if self.message_handler_task:
            self.message_handler_task.cancel()
            self.message_handler_task = None

        if self.auth_refresh_task:
            self.auth_refresh_task.cancel()
            self.auth_refresh_task = None

        # Try to reconnect
        await self.connect()

    async def _heartbeat_loop(self) -> None:
        """
        Send periodic heartbeat messages to keep the connection alive.
        """
        while self.connected:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                if self.connected:
                    await self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {str(e)}")
                if self.connected:
                    asyncio.create_task(self._reconnect())
                break

    async def _refresh_auth_loop(self) -> None:
        """
        Periodically refresh the authentication token before it expires.
        """
        try:
            while self.connected and self.authenticated:
                # Calculate time until token refresh (refresh at 70% of lifetime)
                current_time = time.time()
                token_lifetime = self._token_expiry - current_time
                refresh_time = token_lifetime * 0.7

                # Wait until it's time to refresh
                await asyncio.sleep(max(refresh_time, 60))  # At least 60 seconds

                # Check if we're still connected and authenticated
                if not (self.connected and self.authenticated):
                    break

                # Re-read the clock: current_time above was captured before the
                # sleep and is now stale, so the expiry comparison must use a
                # fresh timestamp.
                current_time = time.time()

                # Check if refresh token is still valid
                if current_time > self._refresh_token_expiry:
                    self.logger.warning("Refresh token expired, re-authenticating with credentials")
                    await self.authenticate()
                else:
                    await self._refresh_token_auth()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Error in refresh authentication loop: {str(e)}")
            if self.connected:
                # Try to re-authenticate if refresh fails
                asyncio.create_task(self.authenticate())

    async def _refresh_token_auth(self) -> None:
        """
        Refresh the authentication token using the refresh token.
        """
        if not self._refresh_token:
            self.logger.warning("No refresh token available, cannot refresh authentication")
            await self.authenticate()
            return

        self.logger.info("Refreshing authentication token")

        if self.ws is None or not self.connected:
            self.logger.warning("Cannot refresh token: not connected, re-authenticating")
            await self.authenticate()
            return

        message_id = self.next_message_id()
        message: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": "public/auth",
            "params": {
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token
            }
        }

        future: "asyncio.Future[Any]" = asyncio.get_event_loop().create_future()
        self.pending_requests[message_id] = future

        try:
            await self.ws.send(json.dumps(message))
            result = await asyncio.wait_for(future, timeout=30)

            # Update tokens
            self._access_token = result.get("access_token")
            if "refresh_token" in result:
                self._refresh_token = result.get("refresh_token")

            # Update expiry times
            expires_in = result.get("expires_in", 0) / 1000
            self._token_expiry = time.time() + expires_in

            if "refresh_token_expires_in" in result:
                refresh_expires_in = result.get("refresh_token_expires_in", 0) / 1000
                self._refresh_token_expiry = time.time() + refresh_expires_in

            self.authenticated = True
            self.logger.info("Successfully refreshed authentication token")
        except Exception as e:
            self.logger.error(f"Failed to refresh authentication token: {str(e)}")
            # If refresh fails, try re-authenticating
            await self.authenticate()

    async def _send_heartbeat(self) -> None:
        """
        Send a heartbeat message to the server.
        """
        if not self.connected or self.ws is None:
            return

        try:
            message_id = self.next_message_id()
            await self.ws.send(json.dumps({
                "jsonrpc": "2.0",
                "id": message_id,
                "method": "public/test",
                "params": {}
            }))
            self.logger.debug("Heartbeat sent")
        except Exception as e:
            self.logger.error(f"Failed to send heartbeat: {str(e)}")
            if self.connected:
                asyncio.create_task(self._reconnect())

    async def _message_handler(self) -> None:
        """
        Handle incoming WebSocket messages.
        """
        if self.ws is None:
            self.logger.error("Message handler started without an open WebSocket")
            return
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self._process_message(data)
                except json.JSONDecodeError:
                    self.logger.error(f"Failed to parse message: {message!r}")
                except Exception as e:
                    self.logger.error(f"Error processing message: {str(e)}")
        except ConnectionClosed:
            self.logger.warning("WebSocket connection closed")
            self.connected = False
            self.authenticated = False
            asyncio.create_task(self._reconnect())
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Unexpected error in message handler: {str(e)}")
            self.connected = False
            self.authenticated = False
            asyncio.create_task(self._reconnect())

    async def _process_message(self, data: Dict) -> None:
        """
        Process an incoming message from the WebSocket.

        Args:
            data: The message data
        """
        if "id" in data:
            # This is a response to a request
            message_id = data["id"]
            if message_id in self.pending_requests:
                future = self.pending_requests.pop(message_id)
                if "error" in data:
                    error = data["error"]
                    future.set_exception(DeribitWebSocketError(
                        error.get("code", -1),
                        error.get("message", "Unknown WebSocket error"),
                        error
                    ))
                else:
                    future.set_result(data.get("result"))
        elif "method" in data and data.get("method") == "subscription":
            # This is a subscription update
            params = data.get("params", {})
            channel = params.get("channel")
            if channel:
                # O(1) exact-match dispatch for the common case.
                callback = self.callback_handlers.get(channel)
                if callback is not None:
                    self._invoke_callback(callback, channel, params)
                # Suffix-wildcard handlers (channels ending in "*") are matched
                # by prefix. There are typically very few of these, so scanning
                # only this subset keeps dispatch effectively O(1) per message.
                for handler_channel, wildcard_callback in self._wildcard_handlers.items():
                    if channel.startswith(handler_channel[:-1]):
                        self._invoke_callback(wildcard_callback, channel, params)

    def _invoke_callback(self, callback: Callable, channel: str, params: Dict[str, Any]) -> None:
        """
        Invoke a subscription callback, scheduling coroutine callbacks as tasks.

        Errors are logged with the channel for context and never swallowed
        silently.
        """
        try:
            if asyncio.iscoroutinefunction(callback):
                asyncio.create_task(callback(params))
            else:
                callback(params)
        except Exception as e:
            self.logger.error(f"Error in callback handler for {channel}: {str(e)}")

    async def _resubscribe(self) -> None:
        """
        Resubscribe to channels after reconnection.
        """
        if not self.subscription_channels:
            return

        self.logger.info(f"Resubscribing to {len(self.subscription_channels)} channels")

        # Batch subscribe to multiple channels at once
        channels = list(self.subscription_channels)
        try:
            await self.send_request("public/subscribe", {
                "channels": channels
            })
            self.logger.info(f"Successfully resubscribed to {len(channels)} channels")
        except Exception as e:
            self.logger.error(f"Failed to resubscribe to channels: {str(e)}")

    async def send_request(
            self,
            method: str,
            params: Optional[Dict[str, Any]] = None,
            auth_required: bool = False
    ) -> Any:
        """
        Send a request to the Deribit WebSocket API.

        Args:
            method: The API method to call
            params: The parameters for the method
            auth_required: Whether authentication is required

        Returns:
            The API response

        Raises:
            DeribitWebSocketError: If the API returns an error
            ConnectionError: If not connected to the WebSocket
        """
        if not self.connected:
            await self.connect()
            if not self.connected:
                raise ConnectionError("Not connected to WebSocket")

        if auth_required:
            # Authenticate if needed, then re-check the auth state while holding
            # the connection lock. This closes the reconnect/re-auth window: a
            # private request can only be dispatched once a concurrent
            # connect/reconnect has fully completed and we are still
            # authenticated on the *current* socket.
            if not self.authenticated:
                await self.authenticate()
            async with self._connection_lock:
                if not (self.connected and self.authenticated):
                    raise DeribitWebSocketError(
                        -1,
                        f"Cannot send private request '{method}': "
                        "connection not authenticated (reconnect in progress)"
                    )

        if self.ws is None or not self.connected:
            raise ConnectionError("Not connected to WebSocket")

        message_id = self.next_message_id()
        message: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": method,
            "params": params or {}
        }
        future: "asyncio.Future[Any]" = asyncio.get_event_loop().create_future()
        self.pending_requests[message_id] = future

        try:
            await self.ws.send(json.dumps(message))
            return await asyncio.wait_for(future, timeout=30)
        except asyncio.TimeoutError:
            self.pending_requests.pop(message_id, None)
            raise DeribitWebSocketError(-1, f"Request timed out: {method}")
        except DeribitWebSocketError as e:
            self.logger.error(f"API Error: Code {e.code}, Message: {e.message}")
            raise
        except Exception as e:
            self.pending_requests.pop(message_id, None)
            self.logger.error(
                f"Unexpected error sending request '{method}' (id={message_id}): {e}")
            if self.connected:
                # Unexpected error, try to reconnect
                asyncio.create_task(self._reconnect())
            raise

    # Implementation in DeribitWebSocketClient class:
    async def authenticate_with_signature(self, data: str = "") -> Dict:
        """
        Authenticate with the Deribit API using client signature credentials.

        This method implements the signature-based authentication as described
        in the Deribit API documentation.

        Args:
            data: Optional data field for signature (default: "")

        Returns:
            Authentication result

        Raises:
            DeribitWebSocketError: If authentication fails
        """
        if not self.client_id or not self.client_secret:
            raise DeribitWebSocketError(401, "Authentication required but no credentials provided")

        if not self.connected:
            await self.connect()
            if not self.connected:
                raise ConnectionError("Not connected to WebSocket")

        # First cancel any existing refresh task
        if self.auth_refresh_task:
            self.auth_refresh_task.cancel()
            self.auth_refresh_task = None

        # Generate timestamp (milliseconds)
        timestamp = int(time.time() * 1000)

        # Generate nonce (random string) - use full UUID for maximum entropy
        nonce = str(uuid.uuid4())

        # Create the string to sign
        string_to_sign = f"{timestamp}\n{nonce}\n{data}"

        # Calculate HMAC-SHA256 signature
        signature = hmac.new(
            self.client_secret.encode(),
            string_to_sign.encode(),
            hashlib.sha256
        ).hexdigest()

        # Create authentication message
        if self.ws is None or not self.connected:
            raise ConnectionError("Not connected to WebSocket")

        message_id = self.next_message_id()
        message: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": "public/auth",
            "params": {
                "grant_type": "client_signature",
                "client_id": self.client_id,
                "timestamp": timestamp,
                "nonce": nonce,
                "data": data,
                "signature": signature
            }
        }

        # Set up future for response
        future: "asyncio.Future[Any]" = asyncio.get_event_loop().create_future()
        self.pending_requests[message_id] = future

        try:
            # Send authentication request
            await self.ws.send(json.dumps(message))
            # Wait for response
            result = await asyncio.wait_for(future, timeout=30)

            # Store tokens
            self._access_token = result.get("access_token")
            self._refresh_token = result.get("refresh_token")

            # Calculate expiry time (convert from milliseconds to seconds)
            expires_in = result.get("expires_in", 0) / 1000
            self._token_expiry = time.time() + expires_in

            # Calculate refresh token expiry (usually 7 days)
            refresh_expires_in = result.get("refresh_token_expires_in", 0) / 1000
            self._refresh_token_expiry = time.time() + refresh_expires_in

            self.authenticated = True
            self.logger.info("Successfully authenticated with signature method")

            # Start refresh token task
            self.auth_refresh_task = asyncio.create_task(self._refresh_auth_loop())

            return result
        except asyncio.TimeoutError:
            self.pending_requests.pop(message_id, None)
            raise DeribitWebSocketError(-1, "Authentication request timed out")
        except Exception as e:
            self.pending_requests.pop(message_id, None)
            if self.connected:
                # Unexpected error, try to reconnect
                asyncio.create_task(self._reconnect())
            raise DeribitWebSocketError(-1, f"Authentication failed: {str(e)}")

    async def authenticate(self) -> Dict:
        """
        Authenticate with the Deribit API using client credentials.

        Public entry point. Acquires the connection lock so that authentication
        cannot interleave with a concurrent connect/reconnect, then delegates to
        ``_authenticate_credentials``.

        Returns:
            Authentication result

        Raises:
            DeribitWebSocketError: If authentication fails
        """
        async with self._connection_lock:
            return await self._authenticate_credentials()

    async def _authenticate_credentials(self) -> Dict:
        """
        Core client-credentials authentication. Assumes the caller holds (or is
        intentionally bypassing) ``self._connection_lock``; it does NOT acquire
        the lock itself so it can be reused from inside ``connect``.

        Returns:
            Authentication result

        Raises:
            DeribitWebSocketError: If authentication fails
        """
        if not self.client_id or not self.client_secret:
            raise DeribitWebSocketError(401, "Authentication required but no credentials provided")

        # If we already have a valid token, use it
        current_time = time.time()
        if self._access_token and current_time < (self._token_expiry - 60):
            self.authenticated = True
            return {"access_token": self._access_token}

        # First cancel any existing refresh task
        if self.auth_refresh_task:
            self.auth_refresh_task.cancel()
            self.auth_refresh_task = None

        if self.ws is None or not self.connected:
            raise ConnectionError("Not connected to WebSocket")

        # Authenticate with credentials
        message_id = self.next_message_id()
        message: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": "public/auth",
            "params": {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
        }

        future: "asyncio.Future[Any]" = asyncio.get_event_loop().create_future()
        self.pending_requests[message_id] = future

        try:
            await self.ws.send(json.dumps(message))
            result = await asyncio.wait_for(future, timeout=30)

            # Validate the response actually carries a usable token before
            # marking ourselves authenticated. Otherwise a malformed/expired
            # response would let private order requests proceed unauthenticated.
            access_token = result.get("access_token")
            expires_in = result.get("expires_in", 0) / 1000
            if not access_token or expires_in <= 0:
                self.authenticated = False
                raise DeribitWebSocketError(
                    -1, "Authentication response missing a valid access token")

            # Store tokens
            self._access_token = access_token
            self._refresh_token = result.get("refresh_token")

            # Calculate expiry time (convert from milliseconds to seconds)
            self._token_expiry = time.time() + expires_in

            # Calculate refresh token expiry (usually 7 days)
            refresh_expires_in = result.get("refresh_token_expires_in", 0) / 1000
            self._refresh_token_expiry = time.time() + refresh_expires_in

            self.authenticated = True
            self.logger.info("Successfully authenticated with Deribit API")

            # Start refresh token task
            self.auth_refresh_task = asyncio.create_task(self._refresh_auth_loop())

            return result
        except asyncio.TimeoutError:
            self.pending_requests.pop(message_id, None)
            raise DeribitWebSocketError(-1, "Authentication request timed out")
        except DeribitWebSocketError as e:
            # Credential / validation failure: do NOT auto-reconnect (it would
            # loop forever on bad credentials). Surface it to the caller.
            self.pending_requests.pop(message_id, None)
            self.authenticated = False
            self.logger.error(f"Authentication failed: {e.message}")
            raise
        except Exception as e:
            self.pending_requests.pop(message_id, None)
            self.authenticated = False
            self.logger.error(f"Unexpected error during authentication: {e}")
            if self.connected:
                # Transport-level error, try to reconnect
                asyncio.create_task(self._reconnect())
            raise

    # Public API methods
    async def get_funding_rate_value(
            self,
            instrument_name: str,
            start_timestamp: int,
            end_timestamp: int
    ) -> float:
        """
        Retrieves interest rate value for requested period.
        Applicable only for PERPETUAL instruments.

        Args:
            instrument_name: Instrument name
            start_timestamp: The earliest timestamp to return result from (milliseconds since the UNIX epoch)
            end_timestamp: The most recent timestamp to return result from (milliseconds since the UNIX epoch)

        Returns:
            The funding rate value as a float

        Raises:
            DeribitWebSocketError: If the API returns an error
        """
        params = {
            "instrument_name": instrument_name,
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp
        }

        return await self.send_request("public/get_funding_rate_value", params)

    async def get_instruments(
            self,
            currency: str,
            kind: Optional[str] = None,
            expired: bool = False
    ) -> List[Dict]:
        """
        Get available trading instruments.

        Args:
            currency: The currency (e.g., "BTC", "ETH")
            kind: Instrument kind (e.g., "future", "option", "spot", "future_combo", "option_combo", or None for all)
            expired: Whether to include expired instruments

        Returns:
            A list of instrument details
        """
        params = {
            "currency": currency,
            "expired": str(expired).lower()
        }

        if kind:
            params["kind"] = kind

        return await self.send_request("public/get_instruments", params)

    async def get_instrument(self, instrument_name: str) -> Dict[str, Any]:
        """
        Retrieve information about a specific instrument.

        Args:
            instrument_name: The name of the instrument.

        Returns:
            A dictionary containing the instrument details.

        Raises:
            DeribitWebSocketError: If the API returns an error.
        """
        try:
            response = await self.send_request(
                method="public/get_instrument",
                params={"instrument_name": instrument_name},
                auth_required=False
            )
            return response
        except Exception as e:
            raise DeribitWebSocketError(-1, f"Failed to retrieve instrument: {str(e)}")

    async def get_contract_size(self, instrument_name: str) -> Dict:
        """
        Retrieve the contract size of a provided instrument.

        Args:
            instrument_name: The name of the instrument.

        Returns:
            A dictionary containing the contract size.

        Raises:
            DeribitWebSocketError: If the API returns an error.
        """
        params = {"instrument_name": instrument_name}
        return await self.send_request("public/get_contract_size", params)

    async def get_historical_volatility(self, currency: Union[str, Currency]) -> Dict:
        """
        Retrieve historical volatility information for a given cryptocurrency.

        Args:
            currency: The currency symbol as a string or Currency enum (e.g., "BTC", Currency.BTC).

        Returns:
            A dictionary containing historical volatility data.

        Raises:
            ValueError: If the currency is not valid.
            DeribitWebSocketError: If the API returns an error.
        """
        valid_currencies = [c.value for c in Currency]
        currency_value = currency.value if isinstance(currency, Currency) else currency

        if currency_value not in valid_currencies:
            raise ValueError(f"Invalid currency: {currency_value}. Must be one of {valid_currencies}.")

        params = {"currency": currency_value}
        return await self.send_request("public/get_historical_volatility", params)

    async def get_index_price(
            self,
            index_name: str,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the index price for a given index.
        Args:
            index_name: The name of the index (e.g., "btc_usd", "eth_usd").

        Returns:
            A dictionary containing the index price.
        """
        params = {"index_name": index_name}

        return await self.send_request("public/get_index_price", params)

    async def get_book_summary_by_currency(
            self,
            currency: str,
            kind: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the summary information for all instruments for the given currency.

        Args:
            currency: The currency symbol (e.g., "BTC", "ETH").
            kind: Optional. Instrument kind (e.g., "future", "option", "spot").

        Returns:
            A list of instrument summary details.

        Raises:
            DeribitWebSocketError: If the API returns an error.
        """
        params = {"currency": currency}
        if kind:
            params["kind"] = kind

        return await self.send_request("public/get_book_summary_by_currency", params)

    async def get_book_summary_by_instrument(
            self,
            instrument_name: str
    ) -> Dict[str, Any]:
        """
        Retrieve the summary information for a specific instrument.

        Args:
            instrument_name: The name of the instrument.

        Returns:
            A dictionary containing the instrument summary details.

        Raises:
            DeribitWebSocketError: If the API returns an error.
        """
        params = {"instrument_name": instrument_name}
        return await self.send_request("public/get_book_summary_by_instrument", params)

    async def get_order_book(
            self,
            instrument_name: str,
            depth: int = 10
    ) -> Dict:
        """
        Get the order book for an instrument.

        Args:
            instrument_name: The name of the instrument
            depth: The number of price levels to include (default: 10)

        Returns:
            Order book data
        """
        params = {
            "instrument_name": instrument_name,
            "depth": depth
        }

        return await self.send_request("public/get_order_book", params)

    async def get_historical_prices(
            self,
            instrument_name: str,
            resolution: str = "1D",
            start_timestamp: Optional[int] = None,
            end_timestamp: Optional[int] = None,
            count: Optional[int] = None
    ) -> Dict:
        """
        Get historical price data for an instrument.

        Args:
            instrument_name: The name of the instrument
            resolution: The time resolution (e.g., "1M", "1D", "4H", "1H", "5m")
            start_timestamp: Start time in milliseconds since epoch (optional)
            end_timestamp: End time in milliseconds since epoch (optional)
            count: Number of candles to return (optional)

        Returns:
            Historical price data
        """
        resolution_map = {
            "1m": "1", "3m": "3", "5m": "5", "10m": "10", "15m": "15", "30m": "30",
            "1h": "60", "1H": "60", "2h": "120", "2H": "120", 
            "3h": "180", "3H": "180", "6h": "360", "6H": "360",
            "12h": "720", "12H": "720", "1D": "1D", "1W": "1W", "1M": "1M"
        }
        
        # Use mapped value if available, otherwise use original (assuming it's already correct)
        api_resolution = resolution_map.get(resolution, resolution)

        params: Dict[str, Any] = {
            "instrument_name": instrument_name,
            "resolution": api_resolution
        }

        if start_timestamp:
            params["start_timestamp"] = start_timestamp

        if end_timestamp:
            params["end_timestamp"] = end_timestamp

        if count:
            params["count"] = count

        return await self.send_request("public/get_tradingview_chart_data", params)

    # Trading API methods
    async def submit_order(
            self,
            instrument_name: str,
            amount: float,
            purpose: Union[str, OrderPurpose],
            order_type: Union[str, OrderType] = "limit",
            price: Optional[float] = None,
            time_in_force: Union[str, TimeInForce] = "good_til_cancelled",
            **kwargs: Any
    ) -> Dict:
        """
        Submit a new order.

        Args:
            instrument_name: The name of the instrument
            amount: Order amount (in contracts for futures/options)
            purpose: Order side ("buy" or "sell"), as a string or OrderPurpose
            order_type: Order type ("limit", "market", "stop_limit", "stop_market"),
                as a string or OrderType
            price: Order price (required for limit orders)
            time_in_force: Time in force policy ("good_til_cancelled", "fill_or_kill",
                "immediate_or_cancel"), as a string or TimeInForce
            **kwargs: Additional parameters for the order

        Returns:
            Order details
        """
        # Normalise enum-or-string inputs to their wire (string) representation.
        # Callers pass either the str/TimeInForce/OrderType/OrderPurpose enums
        # (e.g. via Order.api_params(), which serialises purpose to a string but
        # leaves order_type/time_in_force as enum members) or plain strings.
        order_type_str: str = getattr(order_type, "value", order_type)
        time_in_force_str: str = getattr(time_in_force, "value", time_in_force)
        purpose_str: str = getattr(purpose, "value", purpose)

        # Validate required parameters
        if order_type_str.lower() in ["limit", "stop_limit"] and price is None:
            raise ValueError("Price is required for limit orders")

        params: Dict[str, Any] = {
            "instrument_name": instrument_name,
            "amount": amount,
            # "contracts": amount,
            "type": order_type_str,
            "time_in_force": time_in_force_str,
            **kwargs
        }

        if price is not None:
            params["price"] = price

        # enforce the required parameter direction [buy, sell]
        params["direction"] = purpose_str.lower()

        # Use the private order API endpoint
        method = f"private/{purpose_str.lower()}"
        return await self.send_request(method, params, auth_required=True)

    async def get_account_summary(self,
                                  currency: str,
                                  subaccount_id: Optional[int] = None,
                                  extended: bool = False) -> Dict:
        """
        Get account summary information.

        Args:
            currency: The currency (e.g., "BTC", "ETH")
            subaccount_id: The ID of the subaccount (optional)
            extended: Whether to include additional fields (default: False)

        Returns:
            Account summary data
        """
        params: Dict[str, Any] = {"currency": currency, }
        if subaccount_id is not None:
            params["subaccount_id"] = subaccount_id
        if extended:
            params["extended"] = extended

        return await self.send_request("private/get_account_summary", params, auth_required=True)

    async def get_account_summaries(
            self,
            subaccount_id: Optional[int] = None,
            extended: bool = False
    ) -> Dict:
        """
        Get account summaries for all currencies.

        Args:
            subaccount_id: The ID of the subaccount (optional)
            extended: Whether to include extended information (default: False)

        Returns:
            Account summaries data
        """
        params = {}
        if subaccount_id is not None:
            params["subaccount_id"] = subaccount_id
        if extended:
            params["extended"] = extended

        return await self.send_request("private/get_account_summaries", params, auth_required=True)

    async def get_positions(self, currency: Optional[str] = None) -> List[Dict]:
        """
        Get open positions.

        Args:
            currency: Filter by currency (optional)

        Returns:
            List of open positions
        """
        params = {}
        if currency:
            params["currency"] = currency

        return await self.send_request("private/get_positions", params, auth_required=True)

    async def cancel_order(self, order_id: str) -> Dict:
        """
        Cancel an order by its ID.

        Args:
            order_id: The ID of the order to cancel

        Returns:
            Canceled order details
        """
        params = {"order_id": order_id}
        return await self.send_request("private/cancel", params, auth_required=True)

    async def cancel_all_orders(self, instrument_name: str) -> Dict:
        """
        Cancel all orders for a specific instrument.

        Args:
            instrument_name: The name of the instrument

        Returns:
            Canceled orders details
        """
        # params = {"detailed": False, 'freeze_quotes': False} both are default, chosen not to set them
        params: Dict[str, Any] = {}
        return await self.send_request("private/cancel_all", params, auth_required=True)

    async def cancel_all_orders_by_currency(self, currency: str) -> Dict:
        """
        Cancel all orders for a specific currency.
        :param currency:
        :return:
        """
        params = {"currency": currency}
        return await self.send_request("private/cancel_all_by_currency", params, auth_required=True)

    async def cancel_all_orders_by_currency_pair(self, currency_pair: str):
        """
        Cancel all orders for a specific currency pair.

        Args:
            currency_pair: The currency pair (e.g., "BTC-USD")

        Returns:
            Canceled orders details
        """
        params = {"currency_pair": currency_pair}
        return await self.send_request("private/cancel_all_by_currency_pair", params, auth_required=True)

    async def cancel_all_orders_by_instrument(self, instrument_name: str) -> Dict:
        """
        Cancel all orders for a specific instrument.

        Args:
            instrument_name: The name of the instrument

        Returns:
            Canceled orders details
        """
        params = {"instrument_name": instrument_name}
        return await self.send_request("private/cancel_all_by_instrument", params, auth_required=True)

    async def cancel_all_orders_by_kind_or_type(self, currency: str,
                                                kind: Optional[str] = None,
                                                order_type: Optional[str] = None) -> Dict:
        """
        Cancel all orders by kind or type.

        Args:
            currency: The currency (e.g., "BTC", "ETH")
            kind: The kind of orders to cancel (e.g., "future", "option") [Optional]
            order_type: The type of orders to cancel (e.g., "limit", "market") [Optional]

        Returns:
            Canceled orders details
        """

        # validate kind in [future, option, spot, future_combo, option_combo, combo, any]
        valid_kinds = ["future", "option", "spot", "future_combo", "option_combo", "combo", "any"]
        if kind not in valid_kinds:
            raise ValueError(f"Invalid kind: {kind}. Must be one of {valid_kinds}.")

        # validate order_type in [all, limit, trigger_all, stop, take, trailing_stop]
        valid_order_types = ["all", "limit", "trigger_all", "stop", "take", "trailing_stop"]
        if order_type not in valid_order_types:
            raise ValueError(f"Invalid order_type: {order_type}. Must be one of {valid_order_types}.")

        params = {"currency": currency, }
        if kind is not None:
            params["kind"] = kind
        if order_type is not None:
            params["order_type"] = order_type

        return await self.send_request("private/cancel_all_by_kind_or_type", params, auth_required=True)

    async def cancel_all_orders_by_label(self, label: str, currency: Optional[str] = None) -> Dict:
        """
        Cancel all orders by label.

        Args:
            label: The label of the orders to cancel
            currency: The currency (optional)

        Returns:
            Canceled orders details
        """
        params = {"label": label}

        if currency:
            params["currency"] = currency

        return await self.send_request("private/cancel_by_label", params, auth_required=True)

    async def get_order_state(self, order_id: str) -> Dict:
        """
        Get the state of an order.

        Args:
            order_id: The ID of the order

        Returns:
            Order state details
        """
        params = {"order_id": order_id}
        return await self.send_request("private/get_order_state", params, auth_required=True)

    async def simulate_pme(
            self,
            currency: str,
            add_positions: bool = True,
            simulated_positions: Optional[Dict[str, float]] = None
    ) -> Dict:
        """
        Calculates the Extended Risk Matrix and margin information for the selected currency
        or against the entire Cross-Collateral portfolio.

        Args:
            currency: The currency for which the Extended Risk Matrix will be calculated
                     (BTC, ETH, USDC, USDT or CROSS for Cross Collateral simulation)
            add_positions: If true, adds simulated positions to current positions,
                          otherwise uses only simulated positions (default: True)
            simulated_positions: Dictionary of positions to simulate in form
                                {instrument_name: size, ...}, e.g. {"BTC-PERPETUAL": -1.0}

        Returns:
            Extended Risk Matrix data and margin information

        Requires authentication with scope: account:read
        """
        params: Dict[str, Any] = {"currency": currency}

        if add_positions is not None:
            params["add_positions"] = add_positions

        if simulated_positions:
            params["simulated_positions"] = simulated_positions

        return await self.send_request(
            "private/pme/simulate",
            params,
            auth_required=True
        )

    # =====================================================
    # Real-time subscription helpers

    async def subscribe_orderbook(
            self,
            instrument_name: str,
            interval: str = "100ms",
            callback: Optional[Callable] = None
    ) -> Dict:
        """
        Subscribe to order book updates for an instrument.

        Args:
            instrument_name: The name of the instrument
            interval: Update interval ("100ms" or "raw")
            callback: Function to call when an update is received

        Returns:
            Subscription result
        """
        channel = f"book.{instrument_name}.{interval}"
        return await self.subscribe(channel, callback)

    async def subscribe_orderbook_grouped(
            self,
            instrument_name: str,
            group: str,
            depth: int,
            interval: str = "100ms",
            callback: Optional[Callable] = None
    ) -> Dict:
        """
        Subscribe to detailed order book updates for an instrument with specified grouping and depth.

        Args:
            instrument_name: The name of the instrument
            group: Group prices (by rounding). Use "none" for no grouping.
                   For BTC: "none", "1", "2", "5", "10"
                   For ETH: "none", "5", "10", "25", "100", "250"
            depth: Number of price levels to be included (1, 10, or 20)
            interval: Update interval ("100ms" or "agg2")
            callback: Function to call when an update is received

        Returns:
            Subscription result
        """
        # Validate parameters
        valid_depths = [1, 10, 20]
        if depth not in valid_depths:
            raise ValueError(f"Depth must be one of {valid_depths}")

        valid_intervals = ["100ms", "agg2"]
        if interval not in valid_intervals:
            raise ValueError(f"Interval must be one of {valid_intervals}")

        # For BTC, valid groups are: none, 1, 2, 5, 10
        # For ETH, valid groups are: none, 5, 10, 25, 100, 250
        # This validation would ideally check the instrument currency

        channel = f"book.{instrument_name}.{group}.{depth}.{interval}"
        return await self.subscribe(channel, callback)

    async def subscribe_trades(
            self,
            instrument_name: str,
            callback: Optional[Callable] = None
    ) -> Dict:
        """
        Subscribe to trade updates for an instrument.

        Args:
            instrument_name: The name of the instrument
            callback: Function to call when an update is received

        Returns:
            Subscription result
        """
        channel = f"trades.{instrument_name}.100ms"
        return await self.subscribe(channel, callback)

    async def subscribe_ticker(
            self,
            instrument_name: str,
            callback: Optional[Callable] = None
    ) -> Dict:
        """
        Subscribe to ticker updates for an instrument.

        Args:
            instrument_name: The name of the instrument
            callback: Function to call when an update is received

        Returns:
            Subscription result
        """
        # ticker.{instrument_name}.{interval}
        # interval can be agg2, 100ms, raw
        channel = f"ticker.{instrument_name}.100ms"
        return await self.subscribe(channel, callback)

    async def subscribe_user_orders(
            self,
            instrument_name: Optional[str] = None,
            callback: Optional[Callable] = None
    ) -> Dict:
        """
        Subscribe to user order updates.

        Args:
            instrument_name: Filter by instrument name (optional)
            callback: Function to call when an update is received

        Returns:
            Subscription result
        """
        channel = (
            f"user.orders.{instrument_name}.raw"
            if instrument_name
            else "user.orders.any.any.raw"
        )
        return await self.subscribe(channel, callback)

    async def subscribe_user_trades(
            self,
            instrument_name: Optional[str] = None,
            callback: Optional[Callable] = None
    ) -> Dict:
        """
        Subscribe to user trade updates.

        Args:
            instrument_name: Filter by instrument name (optional)
            callback: Function to call when an update is received

        Returns:
            Subscription result
        """
        channel = (
            f"user.trades.{instrument_name}.raw"
            if instrument_name
            else "user.trades.any.any.raw"
        )
        return await self.subscribe(channel, callback)

    async def subscribe_user_portfolio(
            self,
            currency: Optional[str] = None,
            callback: Optional[Callable] = None
    ) -> Dict:
        """
        Subscribe to portfolio updates.

        Args:
            currency: Filter by currency (optional)
            callback: Function to call when an update is received

        Returns:
            Subscription result
        """
        channel = f"user.portfolio.{currency or '*'}"
        return await self.subscribe(channel, callback)

    async def subscribe_price_index(
            self,
            index_name: str,
            callback: Optional[Callable] = None
    ) -> Dict:
        """
        Subscribe to Deribit price index updates.

        Args:
            index_name: The name of the price index (e.g., "btc_usd", "eth_usd", "sol_usd")
            callback: Function to call when an index update is received

        Returns:
            Subscription result

        Available indices:
            - btc_usd: Bitcoin USD price index
            - eth_usd: Ethereum USD price index
            - sol_usd: Solana USD price index
            - ada_usd: Cardano USD price index
            - avax_usd: Avalanche USD price index
            - dot_usd: Polkadot USD price index
            - matic_usd: Polygon USD price index
            - uni_usd: Uniswap USD price index
            - link_usd: Chainlink USD price index
            - ltc_usd: Litecoin USD price index
            - bch_usd: Bitcoin Cash USD price index
            - xrp_usd: Ripple USD price index
        """
        channel = f"deribit_price_index.{index_name}"
        return await self.subscribe(channel, callback)

    async def subscribe_multiple_price_indices(
            self,
            index_names: List[str],
            callback: Optional[Callable] = None
    ) -> Dict:
        """
        Subscribe to multiple Deribit price indices at once.

        Args:
            index_names: List of price index names (e.g., ["btc_usd", "eth_usd"])
            callback: Function to call when any index update is received

        Returns:
            Subscription result
        """
        channels = [f"deribit_price_index.{index_name}" for index_name in index_names]
        return await self.subscribe(channels, callback)

    async def subscribe(
            self,
            channels: Union[str, List[str]],
            callback: Optional[Callable] = None
    ) -> Dict:
        """
        Subscribe to one or more channels.

        Args:
            channels: Channel or list of channels to subscribe to
            callback: Function to call when a message is received on these channels

        Returns:
            Subscription result
        """
        if isinstance(channels, str):
            channels = [channels]

        # Register callback handlers for each channel
        if callback:
            for channel in channels:
                self.callback_handlers[channel] = callback
                if channel.endswith("*"):
                    self._wildcard_handlers[channel] = callback

        result = await self.send_request("public/subscribe", {
            "channels": channels
        })

        # Add to subscription set for reconnection handling
        for channel in channels:
            self.subscription_channels.add(channel)

        return result

    async def unsubscribe(self, channels: Union[str, List[str]]) -> Dict:
        """
        Unsubscribe from one or more channels.

        Args:
            channels: Channel or list of channels to unsubscribe from

        Returns:
            Unsubscription result
        """
        if isinstance(channels, str):
            channels = [channels]

        result = await self.send_request("public/unsubscribe", {
            "channels": channels
        })

        # Remove from subscription set
        for channel in channels:
            self.subscription_channels.discard(channel)
            self.callback_handlers.pop(channel, None)
            self._wildcard_handlers.pop(channel, None)

        return result

    async def unsubscribe_all(self) -> Dict:
        """
        Unsubscribe from all channels.

        Returns:
            Unsubscription result
        """
        if not self.subscription_channels:
            return {"subscriptions": []}

        result = await self.send_request("public/unsubscribe_all")

        # Clear subscription set
        self.subscription_channels.clear()
        self.callback_handlers.clear()
        self._wildcard_handlers.clear()

        return result

    async def get_ticker(self, instrument_name: str) -> Dict:
        """
        Get ticker data for an instrument.

        Args:
            instrument_name: The name of the instrument

        Returns:
            Ticker data containing best bid/ask, mark price, funding rates, etc.
        """
        params = {"instrument_name": instrument_name}
        return await self.send_request("public/ticker", params)

    async def get_transaction_log(
            self,
            currency: str,
            start_timestamp: int,
            end_timestamp: int,
            query: Optional[str] = None,
            count: Optional[int] = None,
            continuation: Optional[int] = None,
    ) -> Dict:
        """
        Retrieve the transaction log for a currency within a time range.

        Args:
            currency: The currency symbol (BTC, ETH, USDC, USDT, etc.)
            start_timestamp: Start time in milliseconds since UNIX epoch
            end_timestamp: End time in milliseconds since UNIX epoch
            query: Optional filter keywords (trade, deposit, withdrawal, etc.)
            count: Number of results per request (max 250, default 100)
            continuation: Pagination token for fetching more results

        Returns:
            Transaction log data with logs array and continuation token

        Note:
            Rate limit: 1 request/second sustained
            Requires scope: account:read
        """
        params = {
            "currency": currency,
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
        }

        if query is not None:
            params["query"] = query
        if count is not None:
            params["count"] = min(count, 250)  # API max is 250
        if continuation is not None:
            params["continuation"] = continuation

        return await self.send_request(
            "private/get_transaction_log",
            params,
            auth_required=True
        )
