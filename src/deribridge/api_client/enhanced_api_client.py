import asyncio
from typing import List, Dict, Optional

from .websocket_api_client import DeribitWebSocketClient
from .deribit_response_models import (
    DeribitBaseResponse,
    OrderBook,
    Trade,
    Ticker,
    Instrument,
    Position,
    Order,
    AccountSummary,
    AccountSummaries,
    BookSummary,
    FundingRateValue,
    OrderCancelResponse,
    IndexPriceResponse,
    TransactionLogResponse,
)


class EnhancedDeribitClient(DeribitWebSocketClient):
    """
    Enhanced Deribit client that uses structured response models.
    """

    async def get_order_state_model(self, order_id: str) -> Order:
        """
        Retrieve the current state of an order with structured response.

        Args:
            order_id: The ID of the order to retrieve the state for

        Returns:
            Order object with properly typed fields and helper properties

        Raises:
            DeribitWebSocketError: If the API returns an error
        """
        raw_result = await self.get_order_state(order_id)
        response = DeribitBaseResponse.from_dict({"result": raw_result})
        return response.as_result().to_typed_result(Order)

    async def get_instruments_model(
            self,
            currency: str,
            kind: Optional[str] = None,
            expired: bool = False
    ) -> List[Instrument]:
        """
        Get available trading instruments with structured response.

        Returns:
            List of Instrument objects
        """
        raw_result = await self.get_instruments(currency, kind, expired)
        response = DeribitBaseResponse.from_dict({"result": raw_result})
        return response.as_result().to_typed_result(Instrument)

    async def get_contract_size(self, instrument_name: str) -> float:
        """
        Retrieve the contract size of a provided instrument.

        Args:
            instrument_name: The name of the instrument.

        Returns:
            The contract size as a float.

        Raises:
            ValueError: If the returned contract size is not a number.
        """
        raw_result = await super().get_contract_size(instrument_name)
        contract_size = raw_result.get("contract_size")

        if not isinstance(contract_size, (int, float)):
            raise ValueError(f"Invalid contract size returned: {contract_size}")

        return float(contract_size)

    async def get_book_summary_by_currency(
            self, currency: str, kind: str = None
    ) -> List[BookSummary]:
        """
        Retrieve the summary information for all instruments for the given currency.

        Args:
            currency: The currency symbol (e.g., "BTC", "ETH").
            kind: Optional. Instrument kind (e.g., "future", "option", "spot").

        Returns:
            A list of `BookSummary` objects.
        """
        params = {"currency": currency}
        if kind:
            params["kind"] = kind

        response = await self.send_request("public/get_book_summary_by_currency", params)
        return [BookSummary.from_dict(item) for item in response]

    async def get_book_summary_by_instrument(
            self, instrument_name: str
    ) -> BookSummary:
        """
        Retrieve the summary information for a specific instrument.

        Args:
            instrument_name: The name of the instrument.

        Returns:
            A `BookSummary` object.
        """
        params = {"instrument_name": instrument_name}
        response = await self.send_request("public/get_book_summary_by_instrument", params)
        return BookSummary.from_dict(response)

    async def get_order_book_model(
            self,
            instrument_name: str,
            depth: int = 10
    ) -> OrderBook:
        """
        Get the order book for an instrument with structured response.

        Returns:
            OrderBook object
        """
        raw_result = await self.get_order_book(instrument_name, depth)
        response = DeribitBaseResponse.from_dict({"result": raw_result})
        return response.as_result().to_typed_result(OrderBook)

    async def get_positions_model(
            self,
            currency: Optional[str] = None
    ) -> List[Position]:
        """
        Get open positions with structured response.

        Returns:
            List of Position objects
        """
        raw_result = await self.get_positions(currency)
        response = DeribitBaseResponse.from_dict({"result": raw_result})
        return response.as_result().to_typed_result(Position)

    async def get_account_summary_model(
            self,
            currency: str,
            subaccount_id: Optional[int] = None,
            extended: bool = False
    ) -> AccountSummary:
        """
        Get account summary with structured response.

        Args:
            currency: The currency for the account summary (e.g., "BTC", "ETH")
            subaccount_id: The ID of the subaccount (optional)
            extended: Whether to include extended information (default: False)

        Returns:
            AccountSummary object
        """
        raw_result = await self.get_account_summary(currency, subaccount_id=subaccount_id, extended=extended)
        response = DeribitBaseResponse.from_dict({"result": raw_result})
        return response.as_result().to_typed_result(AccountSummary)

    async def get_account_summaries_model(
            self,
            subaccount_id: Optional[int] = None,
            extended: bool = False
    ) -> AccountSummaries:
        """
        Get account summaries for all currencies with structured response.

        Args:
            subaccount_id: The ID of the subaccount (optional)
            extended: Whether to include extended information (default: False)

        Returns:
            AccountSummaries object containing all account-level info and list of currency summaries
        """
        raw_result = await self.get_account_summaries(subaccount_id=subaccount_id, extended=extended)
        response = DeribitBaseResponse.from_dict({"result": raw_result})
        return response.as_result().to_typed_result(AccountSummaries)

    async def simulate_pme_model(
            self,
            currency: str,
            add_positions: bool = True,
            simulated_positions: Optional[Dict[str, float]] = None
    ) -> AccountSummary:
        """
        Calculates the Extended Risk Matrix and margin information with structured response.

        The simulation can be run for a specific currency or against the entire Cross-Collateral portfolio.

        Args:
            currency: The currency for simulation (BTC, ETH, USDC, USDT or CROSS for Cross Collateral)
            add_positions: If true, adds simulated positions to current positions,
                          otherwise uses only simulated positions (default: True)
            simulated_positions: Dictionary of positions to simulate in form
                                {instrument_name: size, ...}, e.g. {"BTC-PERPETUAL": -1.0}

        Returns:
            AccountSummary object with simulated margin and risk data

        Requires authentication with scope: account:read
        """
        raw_result = await self.simulate_pme(currency, add_positions, simulated_positions)
        response = DeribitBaseResponse.from_dict({"result": raw_result})
        return response.as_result().to_typed_result(AccountSummary)

    async def subscribe_orderbook_model(
            self,
            instrument_name: str,
            interval: str = "100ms",
            callback=None
    ) -> Dict:
        """
        Subscribe to order book updates with structured model callback.

        Args:
            instrument_name: The instrument name
            interval: Update interval
            callback: Function to receive OrderBook objects

        Returns:
            Subscription result
        """

        # Define a wrapper to convert raw data to models
        async def orderbook_wrapper(params):
            data = params.get("data")
            orderbook = OrderBook.from_dict(data)

            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback(orderbook)
                else:
                    callback(orderbook)

        # Use the wrapper as the actual callback
        return await self.subscribe_orderbook(
            instrument_name,
            interval,
            orderbook_wrapper
        )

    async def subscribe_orderbook_grouped_model(
            self,
            instrument_name: str,
            group: str = "5",
            depth: int = 10,
            interval: str = "100ms",
            callback=None
    ) -> Dict:
        """
        Subscribe to order book updates with structured model callback.

        Args:
            instrument_name: The instrument name
            group: Grouping parameter
            depth: Depth of the order book to receive
            interval: Update interval
            callback: Function to receive OrderBook objects

        Returns:
            Subscription result
        """

        # Define a wrapper to convert raw data to models
        async def orderbook_wrapper(params):
            data = params.get("data")
            orderbook = OrderBook.from_dict(data)

            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback(orderbook)
                else:
                    callback(orderbook)

        # Use the wrapper as the actual callback
        return await self.subscribe_orderbook_grouped(
            instrument_name,
            group,
            depth,
            interval,
            orderbook_wrapper
        )

    async def subscribe_trades_model(
            self,
            instrument_name: str,
            callback=None
    ) -> Dict:
        """
        Subscribe to trade updates with structured model callback.

        Args:
            instrument_name: The instrument name
            callback: Function to receive Trade objects

        Returns:
            Subscription result
        """

        # Define a wrapper to convert raw data to models
        async def trades_wrapper(params):
            data = params.get("data")
            trades = [Trade.from_dict(trade) for trade in data]

            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback(trades)
                else:
                    callback(trades)

        # Use the wrapper as the actual callback
        return await self.subscribe_trades(
            instrument_name,
            trades_wrapper
        )

    async def subscribe_ticker_model(
            self,
            instrument_name: str,
            callback=None
    ) -> Dict:
        """
        Subscribe to ticker updates with structured model callback.

        Args:
            instrument_name: The instrument name
            callback: Function to receive Ticker objects

        Returns:
            Subscription result
        """

        # Define a wrapper to convert raw data to models
        async def ticker_wrapper(params):
            data = params.get("data")
            ticker = Ticker.from_dict(data)

            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback(ticker)
                else:
                    callback(ticker)

        # Use the wrapper as the actual callback
        return await self.subscribe_ticker(
            instrument_name,
            ticker_wrapper
        )

    async def subscribe_user_orders_model(
            self,
            instrument_name: Optional[str] = None,
            callback=None
    ) -> Dict:
        """
        Subscribe to user order updates with structured model callback.

        Args:
            instrument_name: Filter by instrument name (optional)
            callback: Function to receive Order objects

        Returns:
            Subscription result
        """

        # Define a wrapper to convert raw data to models
        async def orders_wrapper(params):
            data = params.get("data")
            order = Order.from_dict(data)

            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback(order)
                else:
                    callback(order)

        # Use the wrapper as the actual callback
        return await self.subscribe_user_orders(
            instrument_name,
            orders_wrapper
        )

    async def subscribe_user_trades_model(
            self,
            instrument_name: Optional[str] = None,
            callback=None
    ) -> Dict:
        """
        Subscribe to user trade updates with structured model callback.

        Args:
            instrument_name: Filter by instrument name (optional)
            callback: Function to receive Trade objects

        Returns:
            Subscription result
        """

        # Define a wrapper to convert raw data to models
        async def trades_wrapper(params):
            data = params.get("data")
            trades = [Trade.from_dict(trade) for trade in data]

            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback(trades)
                else:
                    callback(trades)

        # Use the wrapper as the actual callback
        return await self.subscribe_user_trades(
            instrument_name,
            trades_wrapper
        )

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
            ValueError: If the result is not a valid float
        """
        result = await super().get_funding_rate_value(instrument_name, start_timestamp, end_timestamp)

        if not isinstance(result, (int, float)):
            raise ValueError(f"Invalid funding rate value returned: {result}")

        return float(result)

    async def get_funding_rate_value_model(
            self,
            instrument_name: str,
            start_timestamp: int,
            end_timestamp: int
    ) -> FundingRateValue:
        """
        Retrieves interest rate value for the requested period with structured response.
        Applicable only for PERPETUAL instruments.

        Args:
            instrument_name: Instrument name
            start_timestamp: The earliest timestamp to return result from (milliseconds since the UNIX epoch)
            end_timestamp: The most recent timestamp to return result from (milliseconds since the UNIX epoch)

        Returns:
            FundingRateValue object with context (instrument name and timestamps)
        """
        value = await self.get_funding_rate_value(instrument_name, start_timestamp, end_timestamp)
        return FundingRateValue.from_dict(
            value,
            instrument_name=instrument_name,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp
        )

    async def get_ticker_model(self, instrument_name: str) -> Ticker:
        """
        Get ticker data for an instrument with structured response.

        Args:
            instrument_name: The name of the instrument

        Returns:
            Ticker object with properly typed fields and additional helper properties
        """
        raw_result = await self.get_ticker(instrument_name)
        response = DeribitBaseResponse.from_dict({"result": raw_result})
        return response.as_result().to_typed_result(Ticker)

    # In the EnhancedDeribitClient class
    async def cancel_order_model(self, order_id: str) -> OrderCancelResponse:
        """
        Cancel an order with structured response.

        Args:
            order_id: The ID of the order to cancel

        Returns:
            OrderCancelResponse object
        """
        try:
            raw_result = await self.cancel_order(order_id)
            return OrderCancelResponse.from_dict(raw_result)
        except Exception as e:
            # Handle exceptions by creating an error response
            error_info = {"code": -1, "message": str(e)}
            return OrderCancelResponse(order=None, error=error_info)

    async def get_index_price_model(self, index_name: str) -> IndexPriceResponse:
        """
        Get the index price for a given index name with structured response.

        Args:
            index_name: The name of the index (e.g., "BTC-USD")

        Returns:
            IndexPriceResponse object containing the index price and timestamp
        """
        raw_result = await self.get_index_price(index_name)
        response = DeribitBaseResponse.from_dict({"result": raw_result})
        return response.as_result().to_typed_result(IndexPriceResponse)

    async def get_transaction_log_model(
            self,
            currency: str,
            start_timestamp: int,
            end_timestamp: int,
            query: Optional[str] = None,
            count: Optional[int] = None,
            continuation: Optional[int] = None,
    ) -> TransactionLogResponse:
        """
        Retrieve the transaction log with structured response.

        Args:
            currency: The currency symbol (BTC, ETH, USDC, USDT, etc.)
            start_timestamp: Start time in milliseconds since UNIX epoch
            end_timestamp: End time in milliseconds since UNIX epoch
            query: Optional filter keywords (trade, deposit, withdrawal, etc.)
            count: Number of results per request (max 250, default 100)
            continuation: Pagination token for fetching more results

        Returns:
            TransactionLogResponse with typed log entries and pagination info
        """
        raw_result = await self.get_transaction_log(
            currency=currency,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            query=query,
            count=count,
            continuation=continuation,
        )
        return TransactionLogResponse.from_dict(raw_result)
