
from dataclasses import dataclass
@dataclass
class Constants:

    ADK_USER_CHECKOUT_ID = "user:checkout_id"
    ADK_PAYMENT_STATE = "__payment_data__"
    ADK_UCP_METADATA_STATE = "__ucp_metadata__"
    ADK_EXTENSIONS_STATE_KEY = "__session_extensions__"
    ADK_LATEST_TOOL_RESULT = "temp:LATEST_TOOL_RESULT"

    A2A_UCP_EXTENSION_URL = "https://ucp.dev/specification/reference?v=2026-01-11"

    UCP_AGENT_HEADER = "UCP-Agent"
    UCP_FULFILLMENT_EXTENSION = "dev.ucp.shopping.fulfillment"
    UCP_BUYER_CONSENT_EXTENSION = "dev.ucp.shopping.buyer_consent"
    UCP_DISCOUNT_EXTENSION = "dev.ucp.shopping.discount"

    UCP_CHECKOUT_KEY = "a2a.ucp.checkout"
    UCP_PAYMENT_DATA_KEY = "a2a.ucp.checkout.payment_data"
    UCP_RISK_SIGNALS_KEY = "a2a.ucp.checkout.risk_signals"
    
    # EP Binding (Embedded Checkout Protocol) Constants
    EP_VERSION = "2026-01-11"
    EP_DELEGATE_PAYMENT_INSTRUMENTS = "payment.instruments_change"
    EP_DELEGATE_PAYMENT_CREDENTIAL = "payment.credential"
    EP_DELEGATE_FULFILLMENT_ADDRESS = "fulfillment.address_change"
    
    # AP2 Mandates Extension Constants
    AP2_VERSION = "2026-01-11"
    AP2_CAPABILITY_NAME = "dev.ucp.shopping.ap2_mandate"
    AP2_SPEC_URL = "https://ucp.dev/specification/ap2-mandates"

