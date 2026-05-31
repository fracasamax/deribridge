ERROR_CODES = {
    0: {
        "short_message": "",
        "description": "Success, No error."
    },
    10000: {
        "short_message": "authorization_required",
        "description": "Authorization issue, invalid or absent signature etc."
    },
    10001: {
        "short_message": "error",
        "description": "Some general failure, no public information available."
    },
    10002: {
        "short_message": "qty_too_low",
        "description": "Order quantity is too low."
    },
    10003: {
        "short_message": "order_overlap",
        "description": "Rejection, order overlap is found and self-trading is not enabled."
    },
    10004: {
        "short_message": "order_not_found",
        "description": "Attempt to operate with order that can't be found by specified id or label."
    },
    10005: {
        "short_message": "price_too_low",
        "description": "Price is too low, <Limit> defines current limit for the operation."
    },
    10006: {
        "short_message": "price_too_low4idx",
        "description": "Price is too low for current index, <Limit> defines current bottom limit for the operation."
    },
    10007: {
        "short_message": "price_too_high",
        "description": "Price is too high, <Limit> defines current up limit for the operation."
    },
    10009: {
        "short_message": "not_enough_funds",
        "description": "Account has not enough funds for the operation."
    },
    10010: {
        "short_message": "already_closed",
        "description": "Attempt of doing something with closed order."
    },
    10011: {
        "short_message": "price_not_allowed",
        "description": "This price is not allowed for some reason."
    },
    10012: {
        "short_message": "book_closed",
        "description": "Operation for an instrument which order book had been closed."
    },
    10013: {
        "short_message": "pme_max_total_open_orders",
        "description": "Total limit of open orders has been exceeded, it is applicable for PME users."
    },
    10014: {
        "short_message": "pme_max_future_open_orders",
        "description": "Limit of count of futures' open orders has been exceeded, it is applicable for PME users."
    },
    10015: {
        "short_message": "pme_max_option_open_orders",
        "description": "Limit of count of options' open orders has been exceeded, it is applicable for PME users."
    },
    10016: {
        "short_message": "pme_max_future_open_orders_size",
        "description": "Limit of size for futures has been exceeded, it is applicable for PME users."
    },
    10017: {
        "short_message": "pme_max_option_open_orders_size",
        "description": "Limit of size for options has been exceeded, it is applicable for PME users."
    },
    10018: {
        "short_message": "non_pme_max_future_position_size",
        "description": "Limit of size for futures has been exceeded, it is applicable for non-PME users."
    },
    10019: {
        "short_message": "locked_by_admin",
        "description": "Trading is temporary locked by the admin."
    },
    10020: {
        "short_message": "invalid_or_unsupported_instrument",
        "description": "Instrument name is not valid."
    },
    10021: {
        "short_message": "invalid_amount",
        "description": "Amount is not valid."
    },
    10022: {
        "short_message": "invalid_quantity",
        "description": "Quantity was not recognized as a valid number (for API v1)."
    },
    10023: {
        "short_message": "invalid_price",
        "description": "Price was not recognized as a valid number."
    },
    10024: {
        "short_message": "invalid_max_show",
        "description": "max_show parameter was not recognized as a valid number."
    },
    10025: {
        "short_message": "invalid_order_id",
        "description": "Order id is missing or its format was not recognized as valid."
    },
    10026: {
        "short_message": "price_precision_exceeded",
        "description": "Extra precision of the price is not supported."
    },
    10027: {
        "short_message": "non_integer_contract_amount",
        "description": "Futures contract amount was not recognized as integer."
    },
    10028: {
        "short_message": "too_many_requests",
        "description": "Allowed request rate has been exceeded."
    },
    10029: {
        "short_message": "not_owner_of_order",
        "description": "Attempt to operate with not own order."
    },
    10030: {
        "short_message": "must_be_websocket_request",
        "description": "REST request where Websocket is expected."
    },
    10031: {
        "short_message": "invalid_args_for_instrument",
        "description": "Some of the arguments are not recognized as valid."
    },
    10032: {
        "short_message": "whole_cost_too_low",
        "description": "Total cost is too low."
    },
    10033: {
        "short_message": "not_implemented",
        "description": "Method is not implemented yet."
    },
    10034: {
        "short_message": "trigger_price_too_high",
        "description": "Trigger price is too high."
    },
    10035: {
        "short_message": "trigger_price_too_low",
        "description": "Trigger price is too low."
    },
    10036: {
        "short_message": "invalid_max_show_amount",
        "description": "Max Show Amount is not valid."
    },
    10037: {
        "short_message": "non_pme_total_short_options_positions_size",
        "description": "Limit of total size for short options positions has been exceeded, it is applicable for non-PME users."
    },
    10038: {
        "short_message": "pme_max_risk_reducing_orders",
        "description": "Limit of open risk reducing orders has been reached, it is applicable for PME users."
    },
    10039: {
        "short_message": "not_enough_funds_in_currency",
        "description": "Returned when the user does not have sufficient spot reserves to complete the spot trade or when an option order would negatively impact the non-cross portfolio margin balance of Cross SM user."
    },
    10040: {
        "short_message": "retry",
        "description": "Request can't be processed right now and should be retried."
    },
    10041: {
        "short_message": "settlement_in_progress",
        "description": "Settlement is in progress. Every day at settlement time for several seconds, the system calculates user profits and updates balances. That time trading is paused for several seconds till the calculation is completed."
    },
    10043: {
        "short_message": "price_wrong_tick",
        "description": "Price has to be rounded to an instrument tick size."
    },
    10044: {
        "short_message": "trigger_price_wrong_tick",
        "description": "Trigger Price has to be rounded to an instrument tick size."
    },
    10045: {
        "short_message": "can_not_cancel_liquidation_order",
        "description": "Liquidation order can't be cancelled."
    },
    10046: {
        "short_message": "can_not_edit_liquidation_order",
        "description": "Liquidation order can't be edited."
    },
    10047: {
        "short_message": "matching_engine_queue_full",
        "description": "Reached limit of pending Matching Engine requests for user."
    },
    10048: {
        "short_message": "not_on_this_server",
        "description": "The requested operation is not available on this server."
    },
    10049: {
        "short_message": "cancel_on_disconnect_failed",
        "description": "Enabling Cancel On Disconnect for the connection failed."
    },
    10066: {
        "short_message": "too_many_concurrent_requests",
        "description": "The client has sent too many public requests that have not yet been executed."
    },
    10072: {
        "short_message": "disabled_while_position_lock",
        "description": "Spot trading is disabled for users in reduce only mode."
    },
    11008: {
        "short_message": "already_filled",
        "description": "This request is not allowed in regards to the filled order."
    },
    11013: {
        "short_message": "max_spot_open_orders",
        "description": "Total limit of open orders on spot instruments has been exceeded."
    },
    11021: {
        "short_message": "post_only_price_modification_not_possible",
        "description": "Price modification for post only order is not possible"
    },
    11022: {
        "short_message": "max_spot_order_quantity",
        "description": "Limit of quantity per currency for spot instruments has been exceeded."
    },
    11029: {
        "short_message": "invalid_arguments",
        "description": "Some invalid input has been detected."
    },
    11030: {
        "short_message": "other_reject",
        "description": "Some rejects which are not considered as very often, more info may be specified in <Reason>."
    },
    11031: {
        "short_message": "other_error",
        "description": "Some errors which are not considered as very often, more info may be specified in <Error>."
    },
    11035: {
        "short_message": "no_more_triggers",
        "description": "Allowed amount of trigger orders has been exceeded."
    },
    11036: {
        "short_message": "invalid_trigger_price",
        "description": "Invalid trigger price (too high or too low) in relation to the last trade, index or market price."
    },
    11037: {
        "short_message": "outdated_instrument_for_IV_order",
        "description": "Instrument already not available for trading."
    },
    11038: {
        "short_message": "no_adv_for_futures",
        "description": "Advanced orders are not available for futures."
    },
    11039: {
        "short_message": "no_adv_postonly",
        "description": "Advanced post-only orders are not supported yet."
    },
    11041: {
        "short_message": "not_adv_order",
        "description": "Advanced order properties can't be set if the order is not advanced."
    },
    11042: {
        "short_message": "permission_denied",
        "description": "Permission for the operation has been denied."
    },
    11043: {
        "short_message": "bad_argument",
        "description": "Bad argument has been passed."
    },
    11044: {
        "short_message": "not_open_order",
        "description": "Attempt to do open order operations with the not open order."
    },
    11045: {
        "short_message": "invalid_event",
        "description": "Event name has not been recognized."
    },
    11046: {
        "short_message": "outdated_instrument",
        "description": "At several minutes to instrument expiration, corresponding advanced implied volatility orders are not allowed."
    },
    11047: {
        "short_message": "unsupported_arg_combination",
        "description": "The specified combination of arguments is not supported."
    },
    11048: {
        "short_message": "wrong_max_show_for_option",
        "description": "Wrong Max Show for options."
    },
    11049: {
        "short_message": "bad_arguments",
        "description": "Several bad arguments have been passed."
    },
    11050: {
        "short_message": "bad_request",
        "description": "Request has not been parsed properly."
    },
    11051: {
        "short_message": "system_maintenance",
        "description": "System is under maintenance."
    },
    11052: {
        "short_message": "subscribe_error_unsubscribed",
        "description": "Subscription error. However, subscription may fail without this error, please check the list of subscribed channels returned, as some channels can be not subscribed due to wrong input or lack of permissions."
    },
    11053: {
        "short_message": "transfer_not_found",
        "description": "Specified transfer is not found."
    },
    11054: {
        "short_message": "post_only_reject",
        "description": "Request rejected due to reject_post_only flag."
    },
    11055: {
        "short_message": "post_only_not_allowed",
        "description": "Post only flag not allowed for given order type"
    },
    11056: {
        "short_message": "unauthenticated_public_requests_temporarily_disabled",
        "description": "Request rejected because of unauthenticated public requests were temporarily disabled"
    },
    11090: {
        "short_message": "invalid_addr",
        "description": "Invalid address."
    },
    11091: {
        "short_message": "invalid_transfer_address",
        "description": "Invalid address for the transfer."
    },
    11092: {
        "short_message": "address_already_exist",
        "description": "The address already exists."
    },
    11093: {
        "short_message": "max_addr_count_exceeded",
        "description": "Limit of allowed addresses has been reached."
    },
    11094: {
        "short_message": "internal_server_error",
        "description": "Some unhandled error on server. Please report to admin. The details of the request will help to locate the problem."
    },
    11095: {
        "short_message": "disabled_deposit_address_creation",
        "description": "Deposit address creation has been disabled by admin."
    },
    11096: {
        "short_message": "address_belongs_to_user",
        "description": "Withdrawal instead of transfer."
    },
    11097: {
        "short_message": "no_deposit_address",
        "description": "Deposit address not specified."
    },
    11098: {
        "short_message": "account_locked",
        "description": "Account locked."
    },
    12001: {
        "short_message": "too_many_subaccounts",
        "description": "Limit of subbacounts is reached."
    },
    12002: {
        "short_message": "wrong_subaccount_name",
        "description": "The input is not allowed as the name of subaccount."
    },
    12003: {
        "short_message": "login_over_limit",
        "description": "The number of failed login attempts is limited."
    },
    12004: {
        "short_message": "registration_over_limit",
        "description": "The number of registration requests is limited."
    },
    12005: {
        "short_message": "country_is_banned",
        "description": "The country is banned (possibly via IP check)."
    },
    12100: {
        "short_message": "transfer_not_allowed",
        "description": "Transfer is not allowed. Possible wrong direction or other mistake."
    },
    12998: {
        "short_message": "security_key_authorization_over_limit",
        "description": "Too many failed security key authorizations. The client should wait for wait seconds to try again."
    },
    13004: {
        "short_message": "invalid_credentials",
        "description": "Invalid credentials have been used."
    },
    13005: {
        "short_message": "pwd_match_error",
        "description": "Password confirmation error."
    },
    13006: {
        "short_message": "security_error",
        "description": "Invalid Security Code."
    },
    13007: {
        "short_message": "user_not_found",
        "description": "User's security code has been changed or wrong."
    },
    13008: {
        "short_message": "request_failed",
        "description": "Request failed because of invalid input or internal failure."
    },
    13009: {
        "short_message": "unauthorized",
        "description": "Wrong or expired authorization token or bad signature. For example, please check the scope of the token, 'connection' scope can't be reused for other connections."
    },
    13010: {
        "short_message": "value_required",
        "description": "Invalid input, missing value."
    },
    13011: {
        "short_message": "value_too_short",
        "description": "Input is too short."
    },
    13012: {
        "short_message": "unavailable_in_subaccount",
        "description": "Subaccount restrictions."
    },
    13013: {
        "short_message": "invalid_phone_number",
        "description": "Unsupported or invalid phone number."
    },
    13014: {
        "short_message": "cannot_send_sms",
        "description": "SMS sending failed -- phone number is wrong."
    },
    13015: {
        "short_message": "invalid_sms_code",
        "description": "Invalid SMS code."
    },
    13016: {
        "short_message": "invalid_input",
        "description": "Invalid input."
    },
    13018: {
        "short_message": "invalid_content_type",
        "description": "Invalid content type of the request."
    },
    13019: {
        "short_message": "orderbook_closed",
        "description": "Closed, expired order book."
    },
    13020: {
        "short_message": "not_found",
        "description": "Instrument is not found, invalid instrument name."
    },
    13021: {
        "short_message": "forbidden",
        "description": "Not enough permissions to execute the request, forbidden."
    },
    13025: {
        "short_message": "method_switched_off_by_admin",
        "description": "API method temporarily switched off by the administrator."
    },
    13028: {
        "short_message": "temporarily_unavailable",
        "description": "The requested service is not responding or processing the response takes too long."
    },
    13030: {
        "short_message": "mmp_trigger",
        "description": "Order has been rejected due to the MMP trigger."
    },
    13031: {
        "short_message": "verification_required",
        "description": "API method allowed only for verified users."
    },
    13032: {
        "short_message": "non_unique_order_label",
        "description": "Request allowed only for orders uniquely identified by given label, more than one match was found"
    },
    13034: {
        "short_message": "no_more_security_keys_allowed",
        "description": "Maximal number of tokens allowed reached"
    },
    13035: {
        "short_message": "active_combo_limit_reached",
        "description": "Limit of active combo books was reached. The client should wait some time before retrying the request."
    },
    13036: {
        "short_message": "unavailable_for_combo_books",
        "description": "Action is temporarily unavailable for combo books."
    },
    13037: {
        "short_message": "incomplete_KYC_data",
        "description": "KYC verification data is insufficient for external service provider."
    },
    13040: {
        "short_message": "mmp_required",
        "description": "User is not a MMP user."
    },
    13042: {
        "short_message": "cod_not_enabled",
        "description": "Cancel-on-Disconnect is not enabled for the connection."
    },
    13043: {
        "short_message": "quotes_frozen",
        "description": "Quotes are still frozen after previous cancel."
    },
    13403: {
        "short_message": "scope_exceeded",
        "description": "Error returned after the user tried to edit / delete an API key using an authorized key connection with insufficient scope"
    },
    13503: {
        "short_message": "unavailable",
        "description": "Method is currently not available."
    },
    13666: {
        "short_message": "request_cancelled_by_user",
        "description": "Request was cancelled by the user with other api request."
    },
    13777: {
        "short_message": "replaced",
        "description": "Edit request was replaced by other one."
    },
    13778: {
        "short_message": "raw_subscriptions_not_available_for_unauthorized",
        "description": "Raw subscriptions are not available for unauthorized requests."
    },
    13780: {
        "short_message": "move_positions_over_limit",
        "description": "The client cannot execute the request yet, and should wait for wait seconds to try again"
    },
    13781: {
        "short_message": "coupon_already_used",
        "description": "The coupon has already been used by current account"
    },
    13791: {
        "short_message": "KYC_transfer_already_initiated",
        "description": "Sharing of KYC data with a third party provider was already initiated."
    },
    13792: {
        "short_message": "incomplete_KYC_data",
        "description": "User's KYC data stored on the platform is insufficient for sharing according to third party provider."
    },
    13793: {
        "short_message": "KYC_data_inaccessible",
        "description": "User's KYC data is inaccessible at the moment. Client should try again later."
    },
    13888: {
        "short_message": "timed_out",
        "description": "Server did not manage to process request when it was valid (valid_until)"
    },
    13901: {
        "short_message": "no_more_oto_orders",
        "description": "Total limit of open \"one triggers other\" orders has been exceeded."
    },
    13902: {
        "short_message": "mass_quotes_disabled",
        "description": "Mass Quotes feature disabled for this user and currency."
    },
    13903: {
        "short_message": "too_many_quotes",
        "description": "Number of qoutes (in Mass Quotes requests) per second exceeded."
    },
    13904: {
        "short_message": "security_key_setup_required",
        "description": "Not allowed without a full security key setup."
    },
    -32602: {
        "short_message": "Invalid params",
        "description": "See JSON-RPC spec."
    },
    -32600: {
        "short_message": "request entity too large",
        "description": "Error thrown when body size in POST request or single frame in websocket connection frame exceeds the limit (32 kB)"
    },
    -32601: {
        "short_message": "Method not found",
        "description": "See JSON-RPC spec."
    },
    -32700: {
        "short_message": "Parse error",
        "description": "See JSON-RPC spec."
    },
    -32000: {
        "short_message": "Missing params",
        "description": "See JSON-RPC spec."
    }
}


def get_error_message(error_code: int) -> str:
    """Fetch the error message for a given error code."""
    error_info = ERROR_CODES.get(error_code)
    if not error_info:
        return "Unknown error code."
    return error_info["description"]


def get_short_message(error_code: int) -> str:
    """Fetch the short message for a given error code."""
    error_info = ERROR_CODES.get(error_code)
    if not error_info:
        return ""
    return error_info["short_message"]


def get_error_info(error_code: int) -> dict:
    """Fetch complete error information for a given error code."""
    return ERROR_CODES.get(error_code, {
        "short_message": "",
        "description": "Unknown error code."
    })


class DeribitError(Exception):
    """Base exception class for Deribit API errors."""

    def __init__(self, code: int, message: str = None, data: dict = None):
        self.code = code
        self.message = message or get_error_message(code)
        self.short_message = get_short_message(code) or '-'
        self.data = data
        super().__init__(
            f"Deribit Error (Code {code} [{self.short_message}]): {self.message}")


class DeribitAPIError(DeribitError):
    """Exception for Deribit API-related errors."""
    pass


class DeribitAuthenticationError(DeribitError):
    """Exception for authentication-related errors."""
    pass


class DeribitValidationError(DeribitError):
    """Exception for validation-related errors."""
    pass
