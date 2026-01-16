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
UCP MCP Binding Implementation

This module implements the MCP (Model Context Protocol) transport binding 
for UCP Checkout Capability as per https://ucp.dev/specification/checkout-mcp/

Tools implemented:
- create_checkout: Initiates a new checkout session
- get_checkout: Retrieves the current state of a checkout session
- update_checkout: Updates a checkout session
- complete_checkout: Finalizes the checkout and places the order
- cancel_checkout: Cancels a checkout session
"""

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
import logging
import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ucp_sdk.models.schemas.shopping.types.buyer import Buyer
from ucp_sdk.models.schemas.shopping.types.postal_address import PostalAddress
from ucp_sdk.models.schemas.shopping.types.line_item_create_req import LineItemCreateRequest
from ucp_sdk.models.schemas.shopping.types.item_create_req import ItemCreateRequest
from ucp_sdk.models.schemas.shopping.payment_create_req import PaymentCreateRequest
from ucp_sdk.models.schemas.ucp import ResponseCheckout as UcpMetadata

from ..constants import Constants
from ..payment_processor import MockPaymentProcessor
from ..store import RetailStore
from ..helpers import get_checkout_type

# Initialize store and services
store = RetailStore()
mpp = MockPaymentProcessor()
constants = Constants()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models for UCP MCP Binding
# ============================================================================

class UcpProfile(BaseModel):
    """UCP Platform Profile in _meta structure."""
    profile: str = Field(..., description="Platform profile URI for version compatibility")


class UcpMeta(BaseModel):
    """_meta.ucp structure for MCP requests."""
    ucp: UcpProfile


class LineItemInput(BaseModel):
    """Line item for create/update checkout."""
    item: Dict[str, Any] = Field(..., description="Item with id field")
    quantity: int = Field(1, description="Quantity of items")


class FulfillmentDestination(BaseModel):
    """Fulfillment destination address."""
    street_address: Optional[str] = None
    extended_address: Optional[str] = None
    address_locality: Optional[str] = None
    address_region: Optional[str] = None
    address_country: Optional[str] = None
    postal_code: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class FulfillmentMethod(BaseModel):
    """Fulfillment method configuration."""
    type: str = "shipping"
    destinations: Optional[List[FulfillmentDestination]] = None
    id: Optional[str] = None
    line_item_ids: Optional[List[str]] = None
    groups: Optional[List[Dict[str, Any]]] = None


class FulfillmentInput(BaseModel):
    """Fulfillment configuration for checkout."""
    methods: List[FulfillmentMethod] = []


class CheckoutError(BaseModel):
    """UCP Error structure for MCP binding."""
    code: str
    message: str
    severity: str = "recoverable"
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Error response following UCP error structure."""
    status: str = "error"
    errors: List[CheckoutError]


# ============================================================================
# MCP Server Configuration
# ============================================================================

mcp = FastMCP(
    "UCP_Merchant_MCP_Server",
    host="localhost",
    port=10999,
    stateless_http=True,
)


# ============================================================================
# Helper Functions
# ============================================================================

def _create_error_response(code: str, message: str, severity: str = "recoverable", details: Dict = None) -> Dict:
    """
    Creates a UCP-compliant error response for MCP binding.
    
    Error responses follow JSON-RPC 2.0 format with UCP error structure
    embedded in the data field.
    """
    return {
        "status": "error",
        "errors": [
            {
                "code": code,
                "message": message,
                "severity": severity,
                "details": details or {}
            }
        ]
    }


def _create_success_response(checkout) -> Dict:
    """Creates a successful checkout response."""
    return {
        "status": "success",
        constants.UCP_CHECKOUT_KEY: checkout.model_dump(mode="json")
    }


def _extract_ucp_profile(meta: Optional[Dict] = None) -> Optional[str]:
    """
    Extracts the UCP platform profile from _meta structure.
    
    MCP clients MUST include the UCP platform profile URI with every request.
    The platform profile is included in the _meta.ucp structure.
    """
    if meta and "ucp" in meta and "profile" in meta["ucp"]:
        return meta["ucp"]["profile"]
    return None


def _create_ucp_metadata(capabilities: List[str] = None) -> UcpMetadata:
    """Creates UCP metadata for checkout responses."""
    default_capabilities = [
        {
            "name": "dev.ucp.shopping.checkout",
            "version": "2026-01-11",
            "spec": "https://ucp.dev/specification/checkout",
            "schema": "https://ucp.dev/schemas/shopping/checkout.json"
        }
    ]
    return UcpMetadata(
        version="2026-01-11",
        capabilities=default_capabilities
    )


# In-memory session storage (for stateless HTTP, checkout_id is passed explicitly)
_checkout_sessions: Dict[str, str] = {}


# ============================================================================
# UCP MCP Tools - Checkout Capability
# ============================================================================

@mcp.tool("create_checkout")
def create_checkout(
    line_items: List[Dict[str, Any]],
    currency: str = "USD",
    buyer: Optional[Dict[str, Any]] = None,
    payment: Optional[Dict[str, Any]] = None,
    fulfillment: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
    ucp_meta: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Creates a new checkout session.
    
    Maps to the Create Checkout operation as per UCP MCP Binding specification.
    https://ucp.dev/specification/checkout-mcp/#create_checkout
    
    Args:
        line_items: List of line items being checked out. Each item should have
                   'item' (with 'id') and 'quantity' fields.
        currency: ISO 4217 currency code (default: USD)
        buyer: Optional buyer information (email, first_name, last_name)
        payment: Optional payment configuration
        fulfillment: Optional fulfillment configuration with shipping methods
        idempotency_key: UUID for retry safety
        ucp_meta: Metadata containing UCP platform profile
        
    Returns:
        dict: Checkout object with status "success" or error response
    """
    # Extract UCP profile for version compatibility
    ucp_profile = _extract_ucp_profile(ucp_meta)
    logger.info(f"create_checkout called with profile: {ucp_profile}")
    
    if not line_items:
        return _create_error_response(
            code="INVALID_REQUEST",
            message="At least one line item is required",
            severity="recoverable"
        )
    
    try:
        # Create UCP metadata
        ucp_metadata = _create_ucp_metadata()
        
        # Process the first line item to create checkout
        first_item = line_items[0]
        item_id = first_item.get("item", {}).get("id")
        quantity = first_item.get("quantity", 1)
        
        if not item_id:
            return _create_error_response(
                code="INVALID_LINE_ITEM",
                message="Line item must have an item.id field",
                severity="recoverable"
            )
        
        # Create checkout with first item
        checkout = store.add_to_checkout(ucp_metadata, item_id, quantity, None)
        
        # Add remaining line items
        for line_item in line_items[1:]:
            item_id = line_item.get("item", {}).get("id")
            quantity = line_item.get("quantity", 1)
            if item_id:
                checkout = store.add_to_checkout(ucp_metadata, item_id, quantity, checkout.id)
        
        # Set buyer if provided
        if buyer:
            checkout.buyer = Buyer(
                email=buyer.get("email"),
                first_name=buyer.get("first_name"),
                last_name=buyer.get("last_name"),
                full_name=buyer.get("full_name"),
                phone_number=buyer.get("phone_number")
            )
        
        # Handle fulfillment if provided
        if fulfillment and fulfillment.get("methods"):
            for method in fulfillment["methods"]:
                if method.get("destinations"):
                    dest = method["destinations"][0]
                    address = PostalAddress(
                        street_address=dest.get("street_address"),
                        extended_address=dest.get("extended_address"),
                        address_locality=dest.get("address_locality"),
                        address_region=dest.get("address_region"),
                        address_country=dest.get("address_country", "US"),
                        postal_code=dest.get("postal_code"),
                        first_name=dest.get("first_name"),
                        last_name=dest.get("last_name"),
                    )
                    checkout = store.add_delivery_address(checkout.id, address)
        
        logger.info(f"Checkout created with id: {checkout.id}")
        return _create_success_response(checkout)
        
    except ValueError as e:
        logger.exception("Error creating checkout")
        return _create_error_response(
            code="MERCHANDISE_NOT_AVAILABLE",
            message=str(e),
            severity="requires_buyer_input"
        )
    except Exception as e:
        logger.exception("Unexpected error creating checkout")
        return _create_error_response(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred while creating checkout",
            severity="recoverable"
        )


@mcp.tool("get_checkout")
def get_checkout(
    id: str,
    ucp_meta: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Retrieves the current state of a checkout session.
    
    Maps to the Get Checkout operation as per UCP MCP Binding specification.
    https://ucp.dev/specification/checkout-mcp/#get_checkout
    
    Args:
        id: The unique identifier of the checkout session
        ucp_meta: Metadata containing UCP platform profile
        
    Returns:
        dict: Checkout object with current state or error response
    """
    ucp_profile = _extract_ucp_profile(ucp_meta)
    logger.info(f"get_checkout called for id: {id}, profile: {ucp_profile}")
    
    if not id:
        return _create_error_response(
            code="INVALID_REQUEST",
            message="Checkout ID is required",
            severity="recoverable"
        )
    
    try:
        checkout = store.get_checkout(id)
        
        if checkout is None:
            return _create_error_response(
                code="CHECKOUT_NOT_FOUND",
                message=f"Checkout with ID {id} was not found",
                severity="recoverable"
            )
        
        return _create_success_response(checkout)
        
    except Exception as e:
        logger.exception("Error retrieving checkout")
        return _create_error_response(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred while retrieving checkout",
            severity="recoverable"
        )


@mcp.tool("update_checkout")
def update_checkout(
    id: str,
    line_items: Optional[List[Dict[str, Any]]] = None,
    currency: Optional[str] = None,
    buyer: Optional[Dict[str, Any]] = None,
    payment: Optional[Dict[str, Any]] = None,
    fulfillment: Optional[Dict[str, Any]] = None,
    ucp_meta: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Updates an existing checkout session.
    
    Maps to the Update Checkout operation as per UCP MCP Binding specification.
    Performs a full replacement of the checkout resource.
    https://ucp.dev/specification/checkout-mcp/#update_checkout
    
    Args:
        id: The unique identifier of the checkout session to update
        line_items: Updated list of line items
        currency: Updated ISO 4217 currency code
        buyer: Updated buyer information
        payment: Updated payment configuration
        fulfillment: Updated fulfillment configuration
        ucp_meta: Metadata containing UCP platform profile
        
    Returns:
        dict: Updated checkout object or error response
    """
    ucp_profile = _extract_ucp_profile(ucp_meta)
    logger.info(f"update_checkout called for id: {id}, profile: {ucp_profile}")
    
    if not id:
        return _create_error_response(
            code="INVALID_REQUEST",
            message="Checkout ID is required",
            severity="recoverable"
        )
    
    try:
        checkout = store.get_checkout(id)
        
        if checkout is None:
            return _create_error_response(
                code="CHECKOUT_NOT_FOUND",
                message=f"Checkout with ID {id} was not found",
                severity="recoverable"
            )
        
        # Update buyer if provided
        if buyer:
            checkout.buyer = Buyer(
                email=buyer.get("email"),
                first_name=buyer.get("first_name"),
                last_name=buyer.get("last_name"),
                full_name=buyer.get("full_name"),
                phone_number=buyer.get("phone_number")
            )
        
        # Update line items if provided (add/update quantities)
        if line_items:
            for line_item in line_items:
                item_id = line_item.get("item", {}).get("id")
                quantity = line_item.get("quantity", 1)
                if item_id:
                    # Check if item exists in checkout
                    found = False
                    for existing_item in checkout.line_items:
                        if existing_item.item.id == item_id:
                            checkout = store.update_checkout(id, item_id, quantity)
                            found = True
                            break
                    # If not found, add new item
                    if not found:
                        ucp_metadata = _create_ucp_metadata()
                        checkout = store.add_to_checkout(ucp_metadata, item_id, quantity, id)
        
        # Handle fulfillment updates
        if fulfillment and fulfillment.get("methods"):
            for method in fulfillment["methods"]:
                # Handle destination updates
                if method.get("destinations"):
                    dest = method["destinations"][0]
                    address = PostalAddress(
                        street_address=dest.get("street_address"),
                        extended_address=dest.get("extended_address"),
                        address_locality=dest.get("address_locality"),
                        address_region=dest.get("address_region"),
                        address_country=dest.get("address_country", "US"),
                        postal_code=dest.get("postal_code"),
                        first_name=dest.get("first_name"),
                        last_name=dest.get("last_name"),
                    )
                    checkout = store.add_delivery_address(id, address)
                
                # Handle fulfillment option selection
                if method.get("groups"):
                    for group in method["groups"]:
                        selected_option_id = group.get("selected_option_id")
                        if selected_option_id:
                            # Update fulfillment option selection in store
                            # (would need to add this functionality to store)
                            pass
        
        # Refresh checkout state
        checkout = store.get_checkout(id)
        
        logger.info(f"Checkout updated: {id}")
        return _create_success_response(checkout)
        
    except ValueError as e:
        logger.exception("Error updating checkout")
        return _create_error_response(
            code="UPDATE_FAILED",
            message=str(e),
            severity="recoverable"
        )
    except Exception as e:
        logger.exception("Unexpected error updating checkout")
        return _create_error_response(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred while updating checkout",
            severity="recoverable"
        )


@mcp.tool("complete_checkout")
def complete_checkout(
    id: str,
    idempotency_key: str,
    payment: Optional[Dict[str, Any]] = None,
    ucp_meta: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Finalizes the checkout and places the order.
    
    Maps to the Complete Checkout operation as per UCP MCP Binding specification.
    This is the final checkout placement call.
    https://ucp.dev/specification/checkout-mcp/#complete_checkout
    
    Args:
        id: The unique identifier of the checkout session
        idempotency_key: UUID for retry safety (required)
        payment: Payment instrument instance submitted by the buyer
        ucp_meta: Metadata containing UCP platform profile
        
    Returns:
        dict: Checkout object containing order with id and permalink_url,
              or error response
    """
    ucp_profile = _extract_ucp_profile(ucp_meta)
    logger.info(f"complete_checkout called for id: {id}, idempotency_key: {idempotency_key}")
    
    if not id:
        return _create_error_response(
            code="INVALID_REQUEST",
            message="Checkout ID is required",
            severity="recoverable"
        )
    
    if not idempotency_key:
        return _create_error_response(
            code="INVALID_REQUEST",
            message="Idempotency key is required for complete_checkout",
            severity="recoverable"
        )
    
    try:
        checkout = store.get_checkout(id)
        
        if checkout is None:
            return _create_error_response(
                code="CHECKOUT_NOT_FOUND",
                message=f"Checkout with ID {id} was not found",
                severity="recoverable"
            )
        
        # Check if checkout can be completed
        if checkout.status == "completed":
            return _create_error_response(
                code="CHECKOUT_ALREADY_COMPLETED",
                message="This checkout has already been completed",
                severity="recoverable"
            )
        
        if checkout.status == "canceled":
            return _create_error_response(
                code="CHECKOUT_CANCELED",
                message="This checkout has been canceled and cannot be completed",
                severity="recoverable"
            )
        
        # Validate checkout is ready
        start_result = store.start_payment(id)
        if isinstance(start_result, str):
            # Checkout requires more information
            return _create_error_response(
                code="CHECKOUT_INCOMPLETE",
                message=start_result,
                severity="requires_buyer_input"
            )
        
        # Process payment if provided
        if payment:
            # Handle payment instrument
            selected_instrument_id = payment.get("selected_instrument_id")
            instruments = payment.get("instruments", [])
            
            if selected_instrument_id and instruments:
                checkout.payment.selected_instrument_id = selected_instrument_id
                # Payment processing would happen here via MockPaymentProcessor
        
        # Place the order
        checkout = store.place_order(id)
        
        logger.info(f"Checkout completed, order created: {checkout.order.id if checkout.order else 'N/A'}")
        return _create_success_response(checkout)
        
    except ValueError as e:
        logger.exception("Error completing checkout")
        return _create_error_response(
            code="COMPLETE_FAILED",
            message=str(e),
            severity="recoverable"
        )
    except Exception as e:
        logger.exception("Unexpected error completing checkout")
        return _create_error_response(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred while completing checkout",
            severity="recoverable"
        )


@mcp.tool("cancel_checkout")
def cancel_checkout(
    id: str,
    idempotency_key: Optional[str] = None,
    ucp_meta: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Cancels a checkout session.
    
    Maps to the Cancel Checkout operation as per UCP MCP Binding specification.
    Any checkout session with a status not equal to completed or canceled 
    should be cancelable.
    https://ucp.dev/specification/checkout-mcp/#cancel_checkout
    
    Args:
        id: The unique identifier of the checkout session
        idempotency_key: UUID for retry safety
        ucp_meta: Metadata containing UCP platform profile
        
    Returns:
        dict: Checkout object with status: canceled, or error response
    """
    ucp_profile = _extract_ucp_profile(ucp_meta)
    logger.info(f"cancel_checkout called for id: {id}")
    
    if not id:
        return _create_error_response(
            code="INVALID_REQUEST",
            message="Checkout ID is required",
            severity="recoverable"
        )
    
    try:
        checkout = store.get_checkout(id)
        
        if checkout is None:
            return _create_error_response(
                code="CHECKOUT_NOT_FOUND",
                message=f"Checkout with ID {id} was not found",
                severity="recoverable"
            )
        
        # Cancel the checkout
        checkout = store.cancel_checkout(id)
        
        logger.info(f"Checkout canceled: {id}")
        return _create_success_response(checkout)
        
    except ValueError as e:
        # This handles the case where checkout is already completed/canceled
        logger.exception("Error canceling checkout")
        return _create_error_response(
            code="CANCEL_NOT_ALLOWED",
            message=str(e),
            severity="recoverable"
        )
    except Exception as e:
        logger.exception("Unexpected error canceling checkout")
        return _create_error_response(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred while canceling checkout",
            severity="recoverable"
        )


# ============================================================================
# Additional Helper Tools (Non-UCP Standard, but useful for agents)
# ============================================================================

@mcp.tool("search_products")
def search_products(
    query: str,
    ucp_meta: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Searches the product catalog for products matching the query.
    
    Note: This is a helper tool not part of the UCP Checkout Capability,
    but useful for agents to discover products before creating checkouts.
    
    Args:
        query: Search query string
        ucp_meta: Metadata containing UCP platform profile
        
    Returns:
        dict: Product search results or error response
    """
    logger.info(f"search_products called with query: {query}")
    
    if not query:
        return _create_error_response(
            code="INVALID_REQUEST",
            message="Search query is required",
            severity="recoverable"
        )
    
    try:
        product_results = store.search_products(query)
        return {
            "status": "success",
            "results": product_results.model_dump(mode="json")
        }
    except Exception as e:
        logger.exception("Error searching products")
        return _create_error_response(
            code="SEARCH_FAILED",
            message="An error occurred while searching products",
            severity="recoverable"
        )


@mcp.tool("get_product")
def get_product(
    product_id: str,
    ucp_meta: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Retrieves product details by ID.
    
    Note: This is a helper tool not part of the UCP Checkout Capability,
    but useful for agents to get product details before adding to checkout.
    
    Args:
        product_id: The product identifier
        ucp_meta: Metadata containing UCP platform profile
        
    Returns:
        dict: Product details or error response
    """
    logger.info(f"get_product called for id: {product_id}")
    
    if not product_id:
        return _create_error_response(
            code="INVALID_REQUEST",
            message="Product ID is required",
            severity="recoverable"
        )
    
    try:
        product = store.get_product(product_id)
        
        if product is None:
            return _create_error_response(
                code="PRODUCT_NOT_FOUND",
                message=f"Product with ID {product_id} was not found",
                severity="recoverable"
            )
        
        return {
            "status": "success",
            "product": product.model_dump(mode="json")
        }
    except Exception as e:
        logger.exception("Error retrieving product")
        return _create_error_response(
            code="INTERNAL_ERROR",
            message="An error occurred while retrieving product",
            severity="recoverable"
        )


# ============================================================================
# Server Entry Point
# ============================================================================

def _create_error_response_simple(message: str) -> Dict:
    """Simple error response for backward compatibility."""
    return {"message": message, "status": "error"}


if __name__ == "__main__":
    print("Starting UCP MCP Server on http://localhost:10999")
    print("Supported tools: create_checkout, get_checkout, update_checkout, complete_checkout, cancel_checkout")
    print("Helper tools: search_products, get_product")
    mcp.run(transport="streamable-http")
