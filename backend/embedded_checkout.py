# Copyright 2026 UCP Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
UCP Embedded Checkout Protocol (EP Binding) Implementation

This module implements the EP (Embedded Protocol) transport binding for
UCP Checkout Capability as per https://ucp.dev/specification/embedded-checkout/

The Embedded Checkout Protocol enables a host application to embed a business's
checkout interface in an iframe/webview and communicate via JSON-RPC 2.0 messages.

Core Messages:
- ec.ready: Handshake initiation from embedded checkout
- ec.start: Checkout is visible and ready
- ec.complete: Checkout completed successfully
- ec.line_items.change: Line items modified
- ec.buyer.change: Buyer information updated
- ec.payment.change: Payment details changed
- ec.fulfillment.change: Fulfillment details changed

Delegation Messages:
- ec.payment.instruments_change_request: Request payment instrument selection
- ec.payment.credential_request: Request payment credential
- ec.fulfillment.address_change_request: Request address selection
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from uuid import uuid4
import json
import logging

logger = logging.getLogger(__name__)


EP_VERSION = "2026-01-11"


EP_DELEGATE_PAYMENT_INSTRUMENTS = "payment.instruments_change"
EP_DELEGATE_PAYMENT_CREDENTIAL = "payment.credential"
EP_DELEGATE_FULFILLMENT_ADDRESS = "fulfillment.address_change"


SUPPORTED_DELEGATIONS = [
    EP_DELEGATE_PAYMENT_INSTRUMENTS,
    EP_DELEGATE_PAYMENT_CREDENTIAL,
    EP_DELEGATE_FULFILLMENT_ADDRESS,
]


class JsonRpcMessage(BaseModel):
    """Base JSON-RPC 2.0 message."""
    jsonrpc: str = "2.0"


class JsonRpcRequest(JsonRpcMessage):
    """JSON-RPC 2.0 request (with id, expects response)."""
    id: str = Field(default_factory=lambda: uuid4().hex)
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)


class JsonRpcNotification(JsonRpcMessage):
    """JSON-RPC 2.0 notification (without id, no response expected)."""
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)


class JsonRpcResponse(JsonRpcMessage):
    """JSON-RPC 2.0 success response."""
    id: str
    result: Dict[str, Any] = Field(default_factory=dict)


class JsonRpcErrorData(BaseModel):
    """JSON-RPC 2.0 error data."""
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


class JsonRpcErrorResponse(JsonRpcMessage):
    """JSON-RPC 2.0 error response."""
    id: str
    error: JsonRpcErrorData



class EPMessageType(str, Enum):
    """Embedded Checkout Protocol message types."""
    # Handshake
    READY = "ec.ready"
    
    # Lifecycle
    START = "ec.start"
    COMPLETE = "ec.complete"
    
    # State Changes
    LINE_ITEMS_CHANGE = "ec.line_items.change"
    BUYER_CHANGE = "ec.buyer.change"
    PAYMENT_CHANGE = "ec.payment.change"
    MESSAGES_CHANGE = "ec.messages.change"
    FULFILLMENT_CHANGE = "ec.fulfillment.change"
    
    # Payment Extension Delegations
    PAYMENT_INSTRUMENTS_CHANGE_REQUEST = "ec.payment.instruments_change_request"
    PAYMENT_CREDENTIAL_REQUEST = "ec.payment.credential_request"
    
    # Fulfillment Extension Delegations
    FULFILLMENT_ADDRESS_CHANGE_REQUEST = "ec.fulfillment.address_change_request"



class EcReadyParams(BaseModel):
    """Parameters for ec.ready message."""
    delegate: List[str] = Field(
        default_factory=list,
        description="List of delegation identifiers accepted by the Embedded Checkout"
    )


class EcReadyResponseResult(BaseModel):
    """Result for ec.ready response from host."""
    upgrade: Optional[Dict[str, Any]] = Field(
        None,
        description="Communication channel upgrade information"
    )
    checkout: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional display-only state for the checkout"
    )


class EcCheckoutParams(BaseModel):
    """Parameters containing checkout state (used by multiple message types)."""
    checkout: Dict[str, Any] = Field(
        ...,
        description="The latest state of the checkout"
    )


class EcPaymentInstrumentsChangeResult(BaseModel):
    """Result for payment instruments change delegation response."""
    selected_instrument_id: Optional[str] = None
    instruments: List[Dict[str, Any]] = Field(default_factory=list)


class EcPaymentCredentialResult(BaseModel):
    """Result for payment credential delegation response."""
    credential: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class EcAddressChangeResult(BaseModel):
    """Result for address change delegation response."""
    address: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class EPErrorCode(int, Enum):
    """Standard JSON-RPC 2.0 error codes for EP Binding."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # EP-specific errors (-32000 to -32099)
    USER_CANCELLED = -32001
    DELEGATION_FAILED = -32002
    CHECKOUT_NOT_FOUND = -32003
    INVALID_STATE = -32004



class EmbeddedCheckoutSession:
    """
    Manages an embedded checkout session.
    
    Tracks the state of the session including:
    - Requested and accepted delegations
    - Communication channel state
    - Pending requests awaiting responses
    """
    
    def __init__(
        self,
        checkout_id: str,
        ec_version: str,
        requested_delegations: List[str] = None,
        ec_auth: Optional[str] = None,
    ):
        """
        Initialize an embedded checkout session.
        
        Args:
            checkout_id: ID of the checkout being embedded
            ec_version: UCP version for this session
            requested_delegations: Delegations requested by host
            ec_auth: Optional authentication token
        """
        self.id = uuid4().hex
        self.checkout_id = checkout_id
        self.ec_version = ec_version
        self.ec_auth = ec_auth
        
        
        self.requested_delegations = requested_delegations or []
        self.accepted_delegations: List[str] = []
        
       
        self.is_ready = False
        self.is_started = False
        self.is_completed = False
        
        # Pending requests (id -> callback)
        self._pending_requests: Dict[str, Any] = {}
        
        # Message history for debugging
        self._message_history: List[Dict[str, Any]] = []
    
    def accept_delegation(self, delegation: str) -> bool:
        """
        Accept a delegation if it was requested and is supported.
        
        Args:
            delegation: Delegation identifier to accept
            
        Returns:
            True if delegation was accepted
        """
        if delegation in self.requested_delegations and delegation in SUPPORTED_DELEGATIONS:
            if delegation not in self.accepted_delegations:
                self.accepted_delegations.append(delegation)
            return True
        return False
    
    def accept_all_supported_delegations(self) -> List[str]:
        """Accept all requested delegations that are supported."""
        for delegation in self.requested_delegations:
            self.accept_delegation(delegation)
        return self.accepted_delegations
    
    def is_delegation_active(self, delegation: str) -> bool:
        """Check if a delegation is active."""
        return delegation in self.accepted_delegations
    
    def log_message(self, direction: str, message: Dict[str, Any]) -> None:
        """Log a message for debugging."""
        self._message_history.append({
            "direction": direction,
            "message": message,
        })



class EPMessageFactory:
    """Factory for creating EP Binding messages."""
    
    @staticmethod
    def create_ready_request(accepted_delegations: List[str]) -> JsonRpcRequest:
        """Create ec.ready request message."""
        return JsonRpcRequest(
            method=EPMessageType.READY.value,
            params=EcReadyParams(delegate=accepted_delegations).model_dump()
        )
    
    @staticmethod
    def create_ready_response(
        request_id: str,
        upgrade: Optional[Dict[str, Any]] = None,
        checkout: Optional[Dict[str, Any]] = None,
    ) -> JsonRpcResponse:
        """Create ec.ready response message."""
        result = {}
        if upgrade:
            result["upgrade"] = upgrade
        if checkout:
            result["checkout"] = checkout
        return JsonRpcResponse(id=request_id, result=result)
    
    @staticmethod
    def create_start_notification(checkout: Dict[str, Any]) -> JsonRpcNotification:
        """Create ec.start notification message."""
        return JsonRpcNotification(
            method=EPMessageType.START.value,
            params=EcCheckoutParams(checkout=checkout).model_dump()
        )
    
    @staticmethod
    def create_complete_notification(checkout: Dict[str, Any]) -> JsonRpcNotification:
        """Create ec.complete notification message."""
        return JsonRpcNotification(
            method=EPMessageType.COMPLETE.value,
            params=EcCheckoutParams(checkout=checkout).model_dump()
        )
    
    @staticmethod
    def create_state_change_notification(
        message_type: EPMessageType,
        checkout: Dict[str, Any]
    ) -> JsonRpcNotification:
        """Create a state change notification."""
        return JsonRpcNotification(
            method=message_type.value,
            params=EcCheckoutParams(checkout=checkout).model_dump()
        )
    
    @staticmethod
    def create_payment_instruments_change_request(
        checkout: Dict[str, Any]
    ) -> JsonRpcRequest:
        """Create ec.payment.instruments_change_request delegation request."""
        return JsonRpcRequest(
            method=EPMessageType.PAYMENT_INSTRUMENTS_CHANGE_REQUEST.value,
            params=EcCheckoutParams(checkout=checkout).model_dump()
        )
    
    @staticmethod
    def create_payment_credential_request(
        checkout: Dict[str, Any]
    ) -> JsonRpcRequest:
        """Create ec.payment.credential_request delegation request."""
        return JsonRpcRequest(
            method=EPMessageType.PAYMENT_CREDENTIAL_REQUEST.value,
            params=EcCheckoutParams(checkout=checkout).model_dump()
        )
    
    @staticmethod
    def create_fulfillment_address_change_request(
        checkout: Dict[str, Any]
    ) -> JsonRpcRequest:
        """Create ec.fulfillment.address_change_request delegation request."""
        return JsonRpcRequest(
            method=EPMessageType.FULFILLMENT_ADDRESS_CHANGE_REQUEST.value,
            params=EcCheckoutParams(checkout=checkout).model_dump()
        )
    
    @staticmethod
    def create_error_response(
        request_id: str,
        code: EPErrorCode,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> JsonRpcErrorResponse:
        """Create an error response."""
        return JsonRpcErrorResponse(
            id=request_id,
            error=JsonRpcErrorData(code=code.value, message=message, data=data)
        )



class EmbeddedCheckoutHandler:
    """
    Handles EP Binding message processing for embedded checkout.
    
    This class is used by the embedded checkout frontend to:
    1. Parse incoming messages from the host
    2. Generate appropriate response messages
    3. Create delegation requests when needed
    """
    
    def __init__(self, session: EmbeddedCheckoutSession):
        """
        Initialize the handler.
        
        Args:
            session: The embedded checkout session
        """
        self.session = session
        self.factory = EPMessageFactory()
    
    def parse_message(self, raw_message: str) -> Dict[str, Any]:
        """
        Parse a raw JSON-RPC message.
        
        Args:
            raw_message: JSON string message
            
        Returns:
            Parsed message as dict
            
        Raises:
            ValueError: If message is not valid JSON-RPC 2.0
        """
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        
        if message.get("jsonrpc") != "2.0":
            raise ValueError("Not a valid JSON-RPC 2.0 message")
        
        self.session.log_message("received", message)
        return message
    
    def handle_ready_response(self, response: Dict[str, Any]) -> EcReadyResponseResult:
        """
        Handle ec.ready response from host.
        
        Args:
            response: The response message
            
        Returns:
            Parsed response result
        """
        result = response.get("result", {})
        self.session.is_ready = True
        
        logger.info(f"Embedded checkout ready, delegations: {self.session.accepted_delegations}")
        
        return EcReadyResponseResult.model_validate(result)
    
    def create_ready_request(self) -> str:
        """
        Create the ec.ready request to send to host.
        
        Returns:
            JSON string of the ec.ready request
        """
        # Accept all supported delegations that were requested
        self.session.accept_all_supported_delegations()
        
        request = self.factory.create_ready_request(self.session.accepted_delegations)
        message = request.model_dump()
        
        self.session.log_message("sent", message)
        return json.dumps(message)
    
    def create_start_notification(self, checkout: Dict[str, Any]) -> str:
        """
        Create ec.start notification.
        
        Args:
            checkout: Current checkout state
            
        Returns:
            JSON string of the notification
        """
        notification = self.factory.create_start_notification(checkout)
        message = notification.model_dump()
        
        self.session.is_started = True
        self.session.log_message("sent", message)
        return json.dumps(message)
    
    def create_complete_notification(self, checkout: Dict[str, Any]) -> str:
        """
        Create ec.complete notification.
        
        Args:
            checkout: Final checkout state with order
            
        Returns:
            JSON string of the notification
        """
        notification = self.factory.create_complete_notification(checkout)
        message = notification.model_dump()
        
        self.session.is_completed = True
        self.session.log_message("sent", message)
        return json.dumps(message)
    
    def create_state_change_notification(
        self,
        change_type: str,
        checkout: Dict[str, Any]
    ) -> str:
        """
        Create a state change notification.
        
        Args:
            change_type: Type of change (line_items, buyer, payment, fulfillment)
            checkout: Current checkout state
            
        Returns:
            JSON string of the notification
        """
        # Map change type to message type
        type_map = {
            "line_items": EPMessageType.LINE_ITEMS_CHANGE,
            "buyer": EPMessageType.BUYER_CHANGE,
            "payment": EPMessageType.PAYMENT_CHANGE,
            "fulfillment": EPMessageType.FULFILLMENT_CHANGE,
            "messages": EPMessageType.MESSAGES_CHANGE,
        }
        
        message_type = type_map.get(change_type)
        if not message_type:
            raise ValueError(f"Unknown change type: {change_type}")
        
        notification = self.factory.create_state_change_notification(message_type, checkout)
        message = notification.model_dump()
        
        self.session.log_message("sent", message)
        return json.dumps(message)
    
    def create_payment_credential_request(self, checkout: Dict[str, Any]) -> Optional[str]:
        """
        Create ec.payment.credential_request if delegation is active.
        
        Args:
            checkout: Current checkout state
            
        Returns:
            JSON string of the request, or None if delegation not active
        """
        if not self.session.is_delegation_active(EP_DELEGATE_PAYMENT_CREDENTIAL):
            return None
        
        request = self.factory.create_payment_credential_request(checkout)
        message = request.model_dump()
        
        self.session.log_message("sent", message)
        return json.dumps(message)
    
    def create_address_change_request(self, checkout: Dict[str, Any]) -> Optional[str]:
        """
        Create ec.fulfillment.address_change_request if delegation is active.
        
        Args:
            checkout: Current checkout state
            
        Returns:
            JSON string of the request, or None if delegation not active
        """
        if not self.session.is_delegation_active(EP_DELEGATE_FULFILLMENT_ADDRESS):
            return None
        
        request = self.factory.create_fulfillment_address_change_request(checkout)
        message = request.model_dump()
        
        self.session.log_message("sent", message)
        return json.dumps(message)


# ============================================================================
# Utility Functions
# ============================================================================

def parse_ep_query_params(
    ec_version: Optional[str],
    ec_delegate: Optional[str],
    ec_auth: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Parse EP query parameters from URL.
    
    Args:
        ec_version: Version parameter (required)
        ec_delegate: Comma-separated delegation identifiers
        ec_auth: Authentication token
        
    Returns:
        Dict with parsed parameters
        
    Raises:
        ValueError: If required parameters are missing or invalid
    """
    if not ec_version:
        raise ValueError("ec_version parameter is required")
    
    # Parse version (format: YYYY-MM-DD)
    if not ec_version.count("-") == 2:
        raise ValueError("ec_version must be in YYYY-MM-DD format")
    
    # Parse delegations
    delegations = []
    if ec_delegate:
        delegations = [d.strip() for d in ec_delegate.split(",") if d.strip()]
    
    return {
        "version": ec_version,
        "delegations": delegations,
        "auth": ec_auth,
    }


def create_embedded_checkout_session(
    checkout_id: str,
    ec_version: str,
    ec_delegate: str = "",
    ec_auth: Optional[str] = None,
) -> EmbeddedCheckoutSession:
    """
    Create a new embedded checkout session from query parameters.
    
    Args:
        checkout_id: ID of the checkout
        ec_version: UCP version
        ec_delegate: Comma-separated delegations
        ec_auth: Authentication token
        
    Returns:
        New EmbeddedCheckoutSession instance
    """
    params = parse_ep_query_params(ec_version, ec_delegate, ec_auth)
    
    return EmbeddedCheckoutSession(
        checkout_id=checkout_id,
        ec_version=params["version"],
        requested_delegations=params["delegations"],
        ec_auth=params["auth"],
    )
