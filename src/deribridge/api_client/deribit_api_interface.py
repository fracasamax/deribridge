import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple

from ..classes.order import Order, OrderType, TimeInForce
from .enhanced_api_client import EnhancedDeribitClient
from .deribit_response_models import OrderBook, Ticker, Position, Order as OrderModel, \
    OrderSubmitResponse, OrderCancelResponse


class OrderTracker:
    """Tracks the lifecycle of orders for performance and risk management."""

    def __init__(self, max_history: int = 1000):
        # Orders that are currently open
        self.active_orders: Dict[str, Dict[str, Any]] = {}
        self.order_history: List[Dict[str, Any]] = []  # Historical order data
        self.max_history = max_history
        # Lock to prevent race conditions during concurrent order updates
        self._lock = asyncio.Lock()

    async def add_order(self, order_id: str, order_data: Dict[str, Any]) -> None:
        """Add or update an order in the active orders map."""
        async with self._lock:
            # Record submission time if this is a new order
            if order_id not in self.active_orders:
                order_data["_submission_time"] = time.time()

            self.active_orders[order_id] = order_data

    async def update_order(self, order_id: str, order_data: Dict[str, Any]) -> None:
        """Update an existing order's data."""
        async with self._lock:
            if order_id in self.active_orders:
                # Preserve submission time and other tracking fields
                tracking_fields = {
                    k: v for k, v in self.active_orders[order_id].items() if k.startswith('_')}
                self.active_orders[order_id] = {**order_data, **tracking_fields}

    async def remove_order(self, order_id: str, final_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Remove an order from active orders and add to history."""
        async with self._lock:
            if order_id in self.active_orders:
                # Combine tracked data with final state
                tracked_data = self.active_orders.pop(order_id)

                # Calculate order lifetime
                if "_submission_time" in tracked_data:
                    final_state["_order_lifetime_seconds"] = time.time(
                    ) - tracked_data["_submission_time"]

                # Merge data and add to history
                complete_record = {**tracked_data, **final_state}
                self.order_history.append(complete_record)

                # Trim history if it gets too large
                if len(self.order_history) > self.max_history:
                    self.order_history = self.order_history[-self.max_history:]

                return complete_record
            return None

    async def get_active_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get data for an active order by ID."""
        async with self._lock:
            return self.active_orders.get(order_id)

    async def get_active_orders_for_instrument(self, instrument_name: str) -> List[Dict[str, Any]]:
        """Get all active orders for a specific instrument."""
        async with self._lock:
            return [
                order for order in self.active_orders.values()
                if order.get("instrument_name") == instrument_name
            ]

    async def get_active_order_ids(self) -> List[str]:
        """Get list of all active order IDs."""
        async with self._lock:
            return list(self.active_orders.keys())

    async def get_active_orders_count(self) -> int:
        """Get count of active orders."""
        async with self._lock:
            return len(self.active_orders)

    def get_order_metrics(self) -> Dict[str, Any]:
        """Get metrics about order performance."""
        if not self.order_history:
            return {
                "total_orders": 0,
                "avg_lifetime_seconds": 0,
                "fill_rate": 0,
                "cancellation_rate": 0
            }

        total = len(self.order_history)
        filled = sum(1 for o in self.order_history if o.get(
            "order_state") == "filled")
        cancelled = sum(1 for o in self.order_history if o.get(
            "order_state") == "cancelled")

        # Calculate average lifetime for completed orders
        lifetimes = [o.get("_order_lifetime_seconds", 0) for o in self.order_history
                     if "_order_lifetime_seconds" in o]
        avg_lifetime = sum(lifetimes) / len(lifetimes) if lifetimes else 0

        return {
            "total_orders": total,
            "avg_lifetime_seconds": avg_lifetime,
            "fill_rate": filled / total if total > 0 else 0,
            "cancellation_rate": cancelled / total if total > 0 else 0
        }


class RiskManager:
    """Manages trading risk parameters and circuit breakers."""

    def __init__(self):
        # Risk limits
        # max position size by instrument
        self.max_position_size: Dict[str, float] = {}
        # max order size by instrument
        self.max_order_size: Dict[str, float] = {}
        self.max_daily_loss: float = float(
            'inf')  # max allowed daily loss (USD)
        self.max_drawdown: float = float('inf')  # max allowed drawdown (%)

        # Circuit breakers
        self.sequential_loss_limit: int = 5  # max consecutive losing trades
        self.loss_per_trade_limit: float = float(
            'inf')  # max loss per trade (USD)
        self.market_volatility_limit: float = float(
            'inf')  # max allowed volatility

        # State tracking
        self.sequential_losses: int = 0  # current consecutive losing trades
        self.daily_pnl: float = 0  # running daily P&L
        self.initial_equity: float = 0  # initial equity value
        self.current_equity: float = 0  # current equity value
        self.trading_enabled: bool = True  # master enable/disable switch

    def configure(self, config: Dict[str, Any]) -> None:
        """Configure risk parameters from a config dictionary."""
        # Update risk limits
        self.max_position_size.update(config.get("max_position_size", {}))
        self.max_order_size.update(config.get("max_order_size", {}))
        self.max_daily_loss = config.get("max_daily_loss", self.max_daily_loss)
        self.max_drawdown = config.get("max_drawdown", self.max_drawdown)

        # Update circuit breakers
        self.sequential_loss_limit = config.get(
            "sequential_loss_limit", self.sequential_loss_limit)
        self.loss_per_trade_limit = config.get(
            "loss_per_trade_limit", self.loss_per_trade_limit)
        self.market_volatility_limit = config.get(
            "market_volatility_limit", self.market_volatility_limit)

    def update_equity(self, equity: float) -> None:
        """Update current equity value and check for drawdown circuit breaker."""
        if self.initial_equity == 0:
            self.initial_equity = equity

        self.current_equity = equity

        # Check for drawdown circuit breaker
        if self.initial_equity > 0:
            drawdown = (self.initial_equity - self.current_equity) / \
                       self.initial_equity * 100
            if drawdown > self.max_drawdown:
                self.trading_enabled = False

    def record_trade_pnl(self, pnl: float) -> None:
        """Record P&L from a completed trade and check circuit breakers."""
        self.daily_pnl += pnl

        # Check for daily loss circuit breaker
        if self.daily_pnl < -self.max_daily_loss:
            self.trading_enabled = False

        # Check for sequential loss circuit breaker
        if pnl < 0:
            self.sequential_losses += 1

            # Check loss per trade limit
            if abs(pnl) > self.loss_per_trade_limit:
                self.trading_enabled = False

            # Check sequential loss limit
            if self.sequential_losses >= self.sequential_loss_limit:
                self.trading_enabled = False
        else:
            # Reset sequential losses counter
            self.sequential_losses = 0

    def check_order_risk(self, order: Dict[str, Any]) -> bool:
        """
        Check if an order passes risk checks.

        Returns:
            bool: True if order passes risk checks, False otherwise
        """
        if not self.trading_enabled:
            return False

        instrument = order.get("instrument_name", "")
        amount = order.get("amount", 0)

        # Check order size limit
        max_size = self.max_order_size.get(instrument, float('inf'))
        if amount > max_size:
            return False

        # Additional risk checks can be added here

        return True

    def check_position_risk(self, position: Dict[str, Any], new_order_amount: float) -> bool:
        """
        Check if a new order would exceed position limits.

        Returns:
            bool: True if position would be within limits, False otherwise
        """
        if not self.trading_enabled:
            return False

        instrument = position.get("instrument_name", "")
        current_size = abs(position.get("size", 0))

        # Calculate projected size after order
        projected_size = current_size + abs(new_order_amount)

        # Check position size limit
        max_size = self.max_position_size.get(instrument, float('inf'))
        if projected_size > max_size:
            return False

        return True

    def reset_daily_stats(self) -> None:
        """Reset daily statistics. Should be called at the start of each trading day."""
        self.daily_pnl = 0
        self.trading_enabled = True


class MarketDataCache:
    """Caches market data for fast access."""

    def __init__(self, ttl_seconds: float = 1.0):
        # (timestamp, data)
        self.order_books: Dict[str, Tuple[float, OrderBook]] = {}
        self.tickers: Dict[str, Tuple[float, Ticker]] = {}  # (timestamp, data)
        self.ttl_seconds = ttl_seconds

    def update_order_book(self, instrument: str, order_book: OrderBook) -> None:
        """Update cached order book data."""
        self.order_books[instrument] = (time.time(), order_book)

    def update_ticker(self, instrument: str, ticker: Ticker) -> None:
        """Update cached ticker data."""
        self.tickers[instrument] = (time.time(), ticker)

    def get_order_book(self, instrument: str) -> Optional[OrderBook]:
        """Get cached order book if not expired."""
        if instrument in self.order_books:
            timestamp, data = self.order_books[instrument]
            if time.time() - timestamp <= self.ttl_seconds:
                return data
        return None

    def get_ticker(self, instrument: str) -> Optional[Ticker]:
        """Get cached ticker if not expired."""
        if instrument in self.tickers:
            timestamp, data = self.tickers[instrument]
            if time.time() - timestamp <= self.ttl_seconds:
                return data
        return None


class DeribitAPIInterface:
    """
    Enhanced interface to the Deribit API for algorithmic trading.

    This class provides a higher-level interface with features for professional
    algorithmic trading, including:

    - Market data caching for efficient access
    - Order lifecycle tracking
    - Risk management and circuit breakers
    - Rate limiting and backoff
    - Performance metrics collection
    """

    def __init__(
            self,
            client: Optional[EnhancedDeribitClient] = None,
            client_id: Optional[str] = None,
            client_secret: Optional[str] = None,
            use_test_env: bool = False,
            log_level: int = logging.INFO
    ):
        """
        Initialize the Enhanced Deribit API Interface.

        Args:
            client: Optional existing EnhancedDeribitClient instance to reuse
            client_id: Deribit API client ID (used if client not provided)
            client_secret: Deribit API client secret (used if client not provided)
            use_test_env: Whether to use test environment (default: False)
            log_level: Logging level (default: logging.INFO)
        """
        # Configure logging
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger("DeribitAPI")

        # Use provided client or create new one
        self.client = client or EnhancedDeribitClient(
            client_id=client_id,
            client_secret=client_secret,
            use_test_env=use_test_env,
            auto_connect=False
        )

        # Status management
        self.is_running = False

        # Enhanced trading features
        self.order_tracker = OrderTracker()
        self.risk_manager = RiskManager()
        self.market_data = MarketDataCache()

        # Callbacks
        self.on_order_update: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_position_update: Optional[Callable[[
            Dict[str, Any]], None]] = None
        self.on_ticker_update: Optional[Callable[[str, Ticker], None]] = None
        self.on_orderbook_update: Optional[Callable[[
            str, OrderBook], None]] = None

        # Track active subscriptions
        self.active_subscriptions: Dict[str, bool] = {}

        # Rate limiting settings
        self.request_timestamps: List[float] = []
        self.max_requests_per_second = 10
        self.rate_limit_window = 1.0  # seconds

        # Background task reference for proper cleanup and error handling
        self._monitoring_task: Optional[asyncio.Task] = None

    @classmethod
    def configure(
            cls,
            client: Optional[EnhancedDeribitClient] = None,
            client_id: Optional[str] = None,
            client_secret: Optional[str] = None,
            use_test_env: bool = True,
            log_level: int = logging.INFO,
            risk_config: Optional[Dict[str, Any]] = None
    ) -> 'DeribitAPIInterface':
        """
        Create and configure a new DeribitAPIInterface instance.

        Args:
            client: Optional existing EnhancedDeribitClient instance
            client_id: Deribit API client ID (used if client not provided)
            client_secret: Deribit API client secret (used if client not provided)
            use_test_env: Whether to use the test environment (default: True)
            log_level: Logging level (default: logging.INFO)
            risk_config: Risk management configuration (optional)

        Returns:
            A configured DeribitAPIInterface instance
        """
        if not client and not client_id:
            # Load API credentials from environment variables
            client_id = os.environ.get(
                "DERIBIT_API_CLIENT_ID" + ("_TEST" if use_test_env else ""))
            client_secret = os.environ.get(
                "DERIBIT_API_SECRET" + ("_TEST" if use_test_env else ""))

        instance = cls(
            client=client,
            client_id=client_id,
            client_secret=client_secret,
            use_test_env=use_test_env,
            log_level=log_level
        )

        # Configure risk management if provided
        if risk_config:
            instance.risk_manager.configure(risk_config)

        return instance

    async def start_client(self) -> bool:
        """
        Start the WebSocket client and authenticate.

        Returns:
            bool: True if started successfully, False otherwise
        """
        self.logger.info("Starting enhanced client")
        if self.client.connected:
            self.logger.info("Client already connected")
            return True

        try:
            self.logger.info("Connecting to Deribit WebSocket API...")
            await self.client.connect()

            # Wait for connection to establish
            timeout = 5.0
            start_time = datetime.now()
            while not self.client.connected:
                await asyncio.sleep(0.1)
                if (datetime.now() - start_time).total_seconds() > timeout:
                    self.logger.error("Connection timeout")
                    return False

            # Authenticate if credentials provided
            if self.client.client_id and self.client.client_secret:
                try:
                    self.logger.info("Authenticating with Deribit API...")
                    await self.client.authenticate()

                    # Set running state after successful authentication
                    self.is_running = True

                    # Start background tasks for order and position monitoring
                    self._monitoring_task = asyncio.create_task(
                        self._monitor_orders_and_positions()
                    )
                    # Add error callback to log if the task fails unexpectedly
                    self._monitoring_task.add_done_callback(self._handle_monitoring_task_done)

                    return True
                except Exception as e:
                    self.logger.error(f"Authentication failed: {str(e)}")
                    return False

            # Set running state after successful connection
            self.is_running = True
            return True

        except Exception as e:
            self.logger.error(f"Failed to start client: {str(e)}")
            return False

    async def stop_client(self) -> bool:
        """
        Stop the WebSocket client and clean up resources.

        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self.client.connected:
            self.logger.info("Client already disconnected")
            return True

        try:
            # Cancel monitoring task if running
            if self._monitoring_task and not self._monitoring_task.done():
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass  # Expected when cancelling
                self._monitoring_task = None

            # Unsubscribe from all active subscriptions
            for channel in list(self.active_subscriptions.keys()):
                try:
                    await self.client.unsubscribe(channel)
                    self.active_subscriptions.pop(channel, None)
                except Exception as e:
                    self.logger.warning(
                        f"Error unsubscribing from {channel}: {e}")

            self.logger.info("Disconnecting from Deribit WebSocket API...")
            await self.client.close()
            self.is_running = False
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop client: {str(e)}")
            return False

    async def _wait_for_rate_limit(self):
        """Apply rate limiting to API requests."""
        now = time.time()

        # Remove timestamps older than the rate limit window
        self.request_timestamps = [
            ts for ts in self.request_timestamps if now - ts <= self.rate_limit_window]

        # If we've reached the limit, wait
        if len(self.request_timestamps) >= self.max_requests_per_second:
            wait_time = self.rate_limit_window - \
                        (now - self.request_timestamps[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        # Record this request
        self.request_timestamps.append(time.time())

    def _handle_monitoring_task_done(self, task: asyncio.Task) -> None:
        """Handle completion or failure of the monitoring background task."""
        try:
            # Check if task raised an exception
            exc = task.exception()
            if exc is not None:
                self.logger.error(f"Monitoring task failed with exception: {exc}")
                # Optionally restart the monitoring task if still running
                if self.is_running and self.client.connected:
                    self.logger.info("Attempting to restart monitoring task...")
                    self._monitoring_task = asyncio.create_task(
                        self._monitor_orders_and_positions()
                    )
                    self._monitoring_task.add_done_callback(self._handle_monitoring_task_done)
        except asyncio.CancelledError:
            # Task was cancelled, this is expected during shutdown
            self.logger.debug("Monitoring task was cancelled")
        except asyncio.InvalidStateError:
            # Task is not done yet (shouldn't happen in done callback)
            pass

    async def _monitor_orders_and_positions(self):
        """
        Background task to monitor orders and positions updates.
        This keeps the order tracker and risk management up to date.
        """
        try:
            while self.is_running and self.client.connected:
                try:
                    # Check active orders status
                    order_ids = await self.order_tracker.get_active_order_ids()
                    if order_ids:
                        # Process in smaller batches to avoid rate limits
                        batch_size = 5
                        for i in range(0, len(order_ids), batch_size):
                            batch = order_ids[i:i + batch_size]
                            for order_id in batch:
                                await self._update_order_status(order_id)
                            # Small delay between batches
                            await asyncio.sleep(0.2)

                    # Update account and position information periodically
                    await self._update_account_summary()

                    # Wait before checking again
                    await asyncio.sleep(2.0)

                except Exception as e:
                    self.logger.error(
                        f"Error in order/position monitoring: {e}")
                    await asyncio.sleep(5.0)  # Wait longer after an error

        except asyncio.CancelledError:
            self.logger.info("Order and position monitoring task cancelled")
        except Exception as e:
            self.logger.error(f"Unexpected error in monitoring task: {e}")

    async def _update_order_status(self, order_id: str):
        """Update status for a single order."""
        try:
            await self._wait_for_rate_limit()
            order_state = await self.client.get_order_state(order_id)

            # Update order tracker
            current_state = await self.order_tracker.get_active_order(order_id)
            if current_state:
                # Check if order state has changed
                if current_state.get("order_state") != order_state.get("order_state"):
                    # Order has been filled, canceled, or rejected
                    if order_state.get("order_state") in ["filled", "cancelled", "rejected"]:
                        complete_record = await self.order_tracker.remove_order(
                            order_id, order_state)

                        # Record P&L for filled orders.
                        if order_state.get("order_state") == "filled":
                            # Placeholder: real P&L needs the position cost basis,
                            # i.e. (exit_price - entry_price) * size * direction.
                            # Until that is wired up, record a neutral 0 so the
                            # circuit breakers do not act on bogus numbers.
                            estimated_pnl = 0.0
                            self.risk_manager.record_trade_pnl(estimated_pnl)

                        # Call the order update callback if defined
                        if self.on_order_update:
                            self.on_order_update(complete_record)
                    else:
                        # Order is still active but state changed
                        await self.order_tracker.update_order(order_id, order_state)

                        # Call the order update callback if defined
                        if self.on_order_update:
                            self.on_order_update(order_state)
            else:
                # This order wasn't being tracked - add it
                await self.order_tracker.add_order(order_id, order_state)

        except Exception as e:
            self.logger.error(f"Error updating order {order_id}: {e}")

    async def _update_account_summary(self):
        """Update account summary and position information."""
        try:
            if self.client.authenticated:
                await self._wait_for_rate_limit()
                # Get account summary for BTC (primary currency)
                account_summary = await self.client.get_account_summary_model("BTC", extended=True)

                # Update risk manager with current equity
                self.risk_manager.update_equity(
                    account_summary.total_equity_usd)

                # Get positions
                await self._wait_for_rate_limit()
                positions = await self.client.get_positions_model()

                # Call position update callback if defined
                if self.on_position_update and positions:
                    for position in positions:
                        self.on_position_update(position)

                return account_summary, positions

        except Exception as e:
            self.logger.error(f"Error updating account summary: {e}")

        return None, []

    async def _handle_ticker_update(self, ticker: Ticker):
        """Handle ticker updates from subscriptions."""
        instrument = ticker.instrument_name

        # Update the market data cache
        self.market_data.update_ticker(instrument, ticker)

        # Call the ticker update callback if defined
        if self.on_ticker_update:
            self.on_ticker_update(instrument, ticker)

    async def _handle_orderbook_update(self, order_book: OrderBook):
        """Handle order book updates from subscriptions."""
        instrument = order_book.instrument_name

        # Update the market data cache
        self.market_data.update_order_book(instrument, order_book)

        # Call the order book update callback if defined
        if self.on_orderbook_update:
            self.on_orderbook_update(instrument, order_book)

    async def subscribe_to_ticker(self, instrument_name: str) -> bool:
        """
        Subscribe to ticker updates for an instrument.

        Args:
            instrument_name: The name of the instrument

        Returns:
            bool: True if subscription was successful
        """
        channel = f"ticker.{instrument_name}.100ms"

        if channel in self.active_subscriptions:
            return True

        try:
            await self.client.subscribe_ticker_model(
                instrument_name=instrument_name,
                callback=self._handle_ticker_update
            )
            self.active_subscriptions[channel] = True
            return True
        except Exception as e:
            self.logger.error(f"Error subscribing to ticker: {e}")
            return False

    async def subscribe_to_order_book(self, instrument_name: str, depth: int = 10) -> bool:
        """
        Subscribe to order book updates for an instrument.

        Args:
            instrument_name: The name of the instrument
            depth: The depth of the order book (default: 10)

        Returns:
            bool: True if subscription was successful
        """
        channel = f"book.{instrument_name}.100ms"

        if channel in self.active_subscriptions:
            return True

        try:
            await self.client.subscribe_orderbook_model(
                instrument_name=instrument_name,
                callback=self._handle_orderbook_update
            )
            self.active_subscriptions[channel] = True
            return True
        except Exception as e:
            self.logger.error(f"Error subscribing to order book: {e}")
            return False

    async def get_ticker(self, instrument_name: str) -> Optional[Ticker]:
        """
        Get ticker data for an instrument with caching.

        Args:
            instrument_name: The name of the instrument

        Returns:
            Ticker: The ticker data or None if error
        """
        # Check cache first
        cached = self.market_data.get_ticker(instrument_name)
        if cached:
            return cached

        # If not cached or expired, fetch from API
        try:
            await self._wait_for_rate_limit()
            ticker = await self.client.get_ticker_model(instrument_name)

            # Update cache
            self.market_data.update_ticker(instrument_name, ticker)

            return ticker
        except Exception as e:
            self.logger.error(f"Error getting ticker: {e}")
            return None

    async def get_order_book(self, instrument_name: str, depth: int = 10) -> Optional[OrderBook]:
        """
        Get order book data for an instrument with caching.

        Args:
            instrument_name: The name of the instrument
            depth: The depth of the order book (default: 10)

        Returns:
            OrderBook: The order book data or None if error
        """
        # Check cache first
        cached = self.market_data.get_order_book(instrument_name)
        if cached:
            return cached

        # If not cached or expired, fetch from API
        try:
            await self._wait_for_rate_limit()
            order_book = await self.client.get_order_book_model(instrument_name, depth)

            # Update cache
            self.market_data.update_order_book(instrument_name, order_book)

            return order_book
        except Exception as e:
            self.logger.error(f"Error getting order book: {e}")
            return None

    async def get_positions(self, currency: Optional[str] = None) -> List[Position]:
        """
        Get positions with model-based response.

        Args:
            currency: Filter positions by currency (optional)

        Returns:
            List[Position]: List of positions
        """
        try:
            if not self.client.connected:
                await self.start_client()

            await self._wait_for_rate_limit()
            return await self.client.get_positions_model(currency)
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return []

    async def get_open_orders(self, currency: Optional[str] = None) -> List[OrderModel]:
        """
        Get open orders.

        Args:
            currency: Filter orders by currency (optional)

        Returns:
            List[OrderModel]: List of open orders
        """
        try:
            if not self.client.connected:
                await self.start_client()

            params = {}
            if currency:
                params["currency"] = currency

            await self._wait_for_rate_limit()
            result = await self.client.send_request(
                "private/get_open_orders_by_currency",
                params,
                auth_required=True
            )

            # Convert to OrderModel objects
            return [OrderModel.from_dict(order) for order in result]
        except Exception as e:
            self.logger.error(f"Error getting open orders: {e}")
            return []

    async def submit_order(self, order: Order,
                           check_risk: bool = True) -> Optional[OrderSubmitResponse]:
        """
        Submit an order to the exchange with risk checks.

        Args:
            order: Order object containing order details
            check_risk: Whether to perform risk checks (default: True)

        Returns:
            Optional[OrderSubmitResponse]: Order result with typed response or None if error
        """
        try:
            if not self.client.connected:
                await self.start_client()

            # Convert order to dict for risk checks
            order_dict = order.to_dict()

            if check_risk:
                # Apply risk checks
                if not self.risk_manager.check_order_risk(order_dict):
                    self.logger.warning(
                        f"Order {order_dict.get('instrument_name')} rejected by risk manager")
                    return None

                """# Get current position for additional risk checks
                positions = await self.get_positions()
                matching_position = next(
                    (p for p in positions if p.instrument_name == order.instrument_name),
                    None
                )
    
                if matching_position and not self.risk_manager.check_position_risk(
                        matching_position, order_dict.get("amount", 0)
                ):
                    self.logger.warning(
                        f"Order would exceed position limits for {order.instrument_name}")
                    return None"""

            # Apply rate limiting
            await self._wait_for_rate_limit()

            # Submit the order
            result = await self.client.submit_order(**order.api_params())

            # Parse the response to the typed model
            response = OrderSubmitResponse.from_dict(result)

            # Track the order
            if response.order.order_id:
                self.logger.info(f"Order submitted with ID: {response.order.order_id}")
                await self.order_tracker.add_order(response.order.order_id, result["order"])

            return response
        except Exception as e:
            self.logger.error(f"Error submitting order: {e}")
            return None

    async def submit_limit_order(
            self,
            instrument_name: str,
            side: str,
            amount: float,
            price: float,
            post_only: bool = True,
            time_in_force: str = "good_til_cancelled",
            reduce_only: bool = False,
            client_id: Optional[str] = None
    ) -> Optional[OrderSubmitResponse]:
        """
        Submit a limit order with common parameters.

        Args:
            instrument_name: The name of the instrument
            side: "buy" or "sell"
            amount: Order size
            price: Order price
            post_only: Whether the order must be maker only (default: True)
            time_in_force: Time in force policy (default: "good_til_cancelled")
            reduce_only: Whether the order should only reduce position (default: False)
            client_id: Optional client order ID for tracking

        Returns:
            Optional[Dict[str, Any]]: Order result or None if error
        """
        if side.lower() not in ["buy", "sell"]:
            raise ValueError("Side must be 'buy' or 'sell'")

        from ..classes.order_purpose import OrderPurpose

        order = Order(
            instrument_name=instrument_name,
            purpose=OrderPurpose.BUY if side.lower() == "buy" else OrderPurpose.SELL,
            amount=amount,
            order_type=OrderType.LIMIT,
            price=price,
            time_in_force=TimeInForce(time_in_force),
            post_only=post_only,
            reduce_only=reduce_only,
            label=client_id
        )

        return await self.submit_order(order)

    async def cancel_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Cancel an order.

        Args:
            order_id: The ID of the order to cancel

        Returns:
            Optional[Dict[str, Any]]: Cancellation result or None if error
        """
        try:
            if not self.client.connected:
                await self.start_client()

            await self._wait_for_rate_limit()
            cancel_response: OrderCancelResponse = await self.client.cancel_order_model(order_id)

            # Update order tracker if cancellation was successful
            if cancel_response.is_successful:
                await self.order_tracker.remove_order(order_id, {
                    "order_state": "cancelled",
                    **cancel_response.to_dict()
                })

            return cancel_response
        except Exception as e:
            self.logger.error(f"Error cancelling order: {e}")
            return None

    async def cancel_all_orders(self, instrument_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Cancel all orders, optionally filtered by instrument.

        Args:
            instrument_name: Optional instrument name to filter

        Returns:
            Optional[Dict[str, Any]]: Cancellation result or None if error
        """
        try:
            if not self.client.connected:
                await self.start_client()

            params = {}
            if instrument_name:
                params["instrument_name"] = instrument_name

            await self._wait_for_rate_limit()
            result = await self.client.send_request(
                "private/cancel_all",
                params,
                auth_required=True
            )

            # Update order tracker for all cancelled orders
            cancelled = result.get("cancelled", [])
            for order_id in cancelled:
                await self.order_tracker.remove_order(order_id, {
                    "order_state": "cancelled"
                })

            return result
        except Exception as e:
            self.logger.error(f"Error cancelling all orders: {e}")
            return None

    async def replace_order(
            self,
            order_id: str,
            price: float,
            amount: Optional[float] = None,
            post_only: Optional[bool] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Replace an existing order with new parameters.

        Args:
            order_id: The ID of the order to replace
            price: New price
            amount: New amount (optional)
            post_only: New post_only flag (optional)

        Returns:
            Optional[Dict[str, Any]]: Replacement result or None if error
        """
        try:
            if not self.client.connected:
                await self.start_client()

            params = {
                "order_id": order_id,
                "price": price
            }

            if amount is not None:
                params["amount"] = amount

            if post_only is not None:
                params["post_only"] = post_only

            await self._wait_for_rate_limit()
            result = await self.client.send_request(
                "private/edit",
                params,
                auth_required=True
            )

            # Update order tracker
            if "order_id" in result:
                old_order_id = order_id
                new_order_id = result["order_id"]

                # Remove old order and add new one
                await self.order_tracker.remove_order(old_order_id, {
                    "order_state": "replaced",
                    "replaced_by": new_order_id
                })

                # Add the new order
                await self.order_tracker.add_order(new_order_id, result)

            return result
        except Exception as e:
            self.logger.error(f"Error replacing order: {e}")
            return None

    async def close_position(self, instrument_name: str, type: str = "market") -> Optional[Dict[str, Any]]:
        """
        Close a position.

        Args:
            instrument_name: The name of the instrument
            type: Order type for closing (default: "market")

        Returns:
            Optional[Dict[str, Any]]: Result or None if error
        """
        try:
            if not self.client.connected:
                await self.start_client()

            await self._wait_for_rate_limit()
            result = await self.client.send_request(
                "private/close_position",
                {
                    "instrument_name": instrument_name,
                    "type": type
                },
                auth_required=True
            )

            return result
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            return None

    async def close_all_positions(self, currency: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Close all positions, optionally filtered by currency.

        Args:
            currency: Optional currency to filter

        Returns:
            List[Dict[str, Any]]: Results for each position closure
        """
        results = []

        try:
            positions = await self.get_positions(currency)

            for position in positions:
                if position.size == 0:
                    continue

                instrument = position.instrument_name
                try:
                    result = await self.close_position(instrument)
                    results.append({
                        "instrument": instrument,
                        "success": True,
                        "result": result
                    })
                except Exception as e:
                    results.append({
                        "instrument": instrument,
                        "success": False,
                        "error": str(e)
                    })

            return results
        except Exception as e:
            self.logger.error(f"Error closing all positions: {e}")
            return results

    # Advanced algorithmic trading methods

    async def create_twap_orders(
            self,
            instrument_name: str,
            side: str,
            total_amount: float,
            duration_minutes: int,
            num_slices: int,
            initial_price: float,
            max_price_deviation_pct: float = 0.5,
            post_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Create TWAP (Time-Weighted Average Price) orders by slicing a large order into smaller pieces.

        Args:
            instrument_name: The name of the instrument
            side: "buy" or "sell"
            total_amount: Total order size
            duration_minutes: Duration of the TWAP execution
            num_slices: Number of order slices to create
            initial_price: Initial price for the first slice
            max_price_deviation_pct: Maximum allowed price deviation (%)
            post_only: Whether orders should be post-only

        Returns:
            List[Dict[str, Any]]: Results for each order slice
        """
        if num_slices <= 0:
            raise ValueError("Number of slices must be positive")

        # Calculate time interval and size per slice
        interval_seconds = (duration_minutes * 60) / num_slices
        amount_per_slice = total_amount / num_slices

        # Convert to proper decimal precision for the instrument
        # In a real implementation, you'd get the instrument precision from the API
        amount_per_slice = round(amount_per_slice, 4)  # Example precision

        results = []

        for i in range(num_slices):
            # Calculate order execution time
            execution_time = datetime.now() + timedelta(seconds=i * interval_seconds)

            # For simplicity, use the same price for all slices
            # In a real implementation, you might adjust based on market data
            price = initial_price

            # Create and submit the order
            result = await self.submit_limit_order(
                instrument_name=instrument_name,
                side=side,
                amount=amount_per_slice,
                price=price,
                post_only=post_only
            )

            if result:
                results.append({
                    "slice": i + 1,
                    "time": execution_time.isoformat(),
                    "amount": amount_per_slice,
                    "price": price,
                    "order_id": result.order.order_id if result.order else None,
                    "status": "submitted"
                })
            else:
                results.append({
                    "slice": i + 1,
                    "time": execution_time.isoformat(),
                    "amount": amount_per_slice,
                    "price": price,
                    "status": "failed"
                })

            # Wait for the next interval
            await asyncio.sleep(interval_seconds)

        return results

    async def create_iceberg_order(
            self,
            instrument_name: str,
            side: str,
            total_amount: float,
            visible_amount: float,
            price: float,
            price_step: float = 0,
            dynamic_pricing: bool = False,
            post_only: bool = True
    ) -> Dict[str, Any]:
        """
        Create an iceberg order that shows only a portion of the total size.

        Args:
            instrument_name: The name of the instrument
            side: "buy" or "sell"
            total_amount: Total order size
            visible_amount: Visible portion size
            price: Initial price
            price_step: Price change between filled portions
            dynamic_pricing: Whether to adjust price based on market
            post_only: Whether orders should be post-only

        Returns:
            Dict[str, Any]: Execution results
        """
        if visible_amount <= 0 or total_amount <= 0:
            raise ValueError("Amounts must be positive")

        if visible_amount > total_amount:
            visible_amount = total_amount

        remaining = total_amount
        filled = 0
        current_price = price
        results = []

        # Subscribe to order book for dynamic pricing
        if dynamic_pricing:
            await self.subscribe_to_order_book(instrument_name)

        while remaining > 0 and self.is_running:
            # Determine slice size for this iteration
            slice_size = min(visible_amount, remaining)

            # Adjust price if dynamic pricing is enabled
            if dynamic_pricing:
                order_book = await self.get_order_book(instrument_name)
                if order_book:
                    # Simple price adjustment logic based on order book
                    if side.lower() == "buy":
                        # For buy orders, use a price near the best bid
                        if order_book.best_bid_price:
                            current_price = order_book.best_bid_price
                    else:
                        # For sell orders, use a price near the best ask
                        if order_book.best_ask_price:
                            current_price = order_book.best_ask_price

            # Submit current slice
            order_result = await self.submit_limit_order(
                instrument_name=instrument_name,
                side=side,
                amount=slice_size,
                price=current_price,
                post_only=post_only
            )

            if not order_result:
                # Failed to place order
                results.append({
                    "status": "failed",
                    "remaining": remaining,
                    "price": current_price
                })
                # Wait before retrying
                await asyncio.sleep(1)
                continue

            # Track the order and wait for it to fill
            order_id = order_result.order.order_id if order_result.order else None
            results.append({
                "status": "placed",
                "order_id": order_id,
                "amount": slice_size,
                "price": current_price
            })

            # Wait for order to fill or get cancelled
            filled_amount = 0
            max_wait_time = 60  # Maximum time to wait for fill
            start_time = time.time()
            order_state: Dict[str, Any] = {}  # Initialize to avoid NameError if loop doesn't execute

            while time.time() - start_time < max_wait_time:
                order_state = await self.client.get_order_state(order_id)

                if order_state.get("order_state") == "filled":
                    filled_amount = order_state.get("filled_amount", 0)
                    break
                elif order_state.get("order_state") in ["cancelled", "rejected"]:
                    # Order was cancelled or rejected
                    break

                # Check for partial fills
                filled_amount = order_state.get("filled_amount", 0)
                if filled_amount > 0:
                    break

                await asyncio.sleep(1)

            # Update remaining amount
            filled += filled_amount
            remaining = remaining - filled_amount

            # Cancel if not completely filled
            if filled_amount < slice_size and order_state.get("order_state") not in ["cancelled", "rejected", "filled"]:
                await self.cancel_order(order_id)

            # Adjust price for next slice
            if price_step != 0:
                if side.lower() == "buy":
                    current_price -= price_step  # Decrease price for buys
                else:
                    current_price += price_step  # Increase price for sells

            # Brief pause between slices
            await asyncio.sleep(0.5)

        return {
            "total_amount": total_amount,
            "filled_amount": filled,
            "remaining": remaining,
            "slices": results
        }

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for the trading session.

        Returns:
            Dict[str, Any]: Performance metrics
        """
        # Order metrics
        order_metrics = self.order_tracker.get_order_metrics()

        # Add additional metrics
        metrics = {
            **order_metrics,
            "active_orders_count": await self.order_tracker.get_active_orders_count(),
            "trading_enabled": self.risk_manager.trading_enabled,
            "daily_pnl": self.risk_manager.daily_pnl,
            "sequential_losses": self.risk_manager.sequential_losses
        }

        return metrics


# Example usage
if __name__ == "__main__":
    from dotenv import load_dotenv

    # Load API credentials from environment variables
    load_dotenv()


    # Create an async main function

    async def main():
        # Whether to use test environment
        use_test_env = True

        # Risk configuration
        risk_config = {
            "max_position_size": {
                "BTC-PERPETUAL": 1.0,  # Max 1 BTC position
            },
            "max_order_size": {
                "BTC-PERPETUAL": 0.1,  # Max 0.1 BTC per order
            },
            "max_daily_loss": 100.0,  # Max $100 daily loss
            "sequential_loss_limit": 3  # Max 3 consecutive losses
        }

        # Initialize API interface
        api = DeribitAPIInterface.configure(
            use_test_env=use_test_env,
            risk_config=risk_config
        )

        # Example of how these functions would be called from an application
        print("Starting WebSocket API...")
        success = await api.start_client()
        if success:
            print("Connection successful")

            # Subscribe to BTC-PERPETUAL order book
            await api.subscribe_to_order_book("BTC-PERPETUAL")

            # Subscribe to ticker
            await api.subscribe_to_ticker("BTC-PERPETUAL")

            # Get current market data
            ticker = await api.get_ticker("BTC-PERPETUAL")
            if ticker:
                print(f"Current BTC-PERPETUAL price: {ticker.mark_price}")

            # Place a limit order
            order_result = await api.submit_limit_order(
                instrument_name="BTC-PERPETUAL",
                side="buy",
                amount=0.01,  # Small test amount
                price=ticker.mark_price * 0.99 if ticker else 20000,  # 1% below market
                post_only=True
            )

            if order_result and order_result.order and order_result.order.order_id:
                order_id = order_result.order.order_id
                print(f"Order placed successfully: {order_id}")

                # Wait a moment and cancel the order
                await asyncio.sleep(5)
                cancel_result = await api.cancel_order(order_id)
                print(f"Order cancelled: {cancel_result}")

            # Get performance metrics
            metrics = await api.get_performance_metrics()
            print(f"Performance metrics: {metrics}")

            # Disconnect
            print("\nStopping WebSocket API...")
            success = await api.stop_client()
            if success:
                print("Disconnection successful")
            else:
                print("Disconnection failed")
        else:
            print("Connection failed")


    # Run the async main function
    asyncio.run(main())
