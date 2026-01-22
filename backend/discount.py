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
Discount Extension Implementation

This module implements the Discount Extension for UCP Checkout Capability
as per https://ucp.dev/specification/discount/

The extension enables:
- Submit discount codes via create/update checkout
- Receive applied discounts with titles and amounts
- Handle rejected codes via messages
- Support automatic discounts

Schema:
- discounts.codes: Array of submitted discount codes
- discounts.applied: Array of applied discounts with amounts
- Applied discounts can have allocations to specific line items
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


DISCOUNT_VERSION = "2026-01-11"
DISCOUNT_CAPABILITY_NAME = "dev.ucp.shopping.discount"


class DiscountErrorCode(str, Enum):
    """Error codes for rejected discount codes."""
    DISCOUNT_CODE_EXPIRED = "discount_code_expired"
    DISCOUNT_CODE_INVALID = "discount_code_invalid"
    DISCOUNT_CODE_ALREADY_APPLIED = "discount_code_already_applied"
    DISCOUNT_CODE_COMBINATION_DISALLOWED = "discount_code_combination_disallowed"
    DISCOUNT_CODE_USER_NOT_LOGGED_IN = "discount_code_user_not_logged_in"
    DISCOUNT_CODE_USER_INELIGIBLE = "discount_code_user_ineligible"


class AllocationMethod(str, Enum):
    """How the discount was calculated."""
    EACH = "each"      # Applied to each unit
    ACROSS = "across"  # Distributed across items


class DiscountAllocation(BaseModel):
    """Allocation of discount to a specific target."""
    target: str = Field(
        ...,
        description="JSONPath to the target (e.g., $.line_items[0])"
    )
    amount: int = Field(
        ...,
        description="Amount allocated to this target in cents"
    )


class AppliedDiscount(BaseModel):
    """A discount that has been applied to the checkout."""
    id: Optional[str] = Field(None, description="Unique identifier")
    code: Optional[str] = Field(
        None,
        description="Discount code (absent for automatic discounts)"
    )
    title: str = Field(..., description="Human-readable discount name")
    amount: int = Field(..., description="Total discount amount in cents")
    automatic: bool = Field(
        False,
        description="True if applied automatically without code"
    )
    priority: Optional[int] = Field(
        None,
        description="Stacking order (lower = applied first)"
    )
    method: Optional[AllocationMethod] = Field(
        None,
        description="How discount was calculated"
    )
    allocations: Optional[List[DiscountAllocation]] = Field(
        None,
        description="Breakdown of where discount was applied"
    )


class DiscountsRequest(BaseModel):
    """Discounts object in checkout requests."""
    codes: List[str] = Field(
        default_factory=list,
        description="Discount codes to apply"
    )


class DiscountsResponse(BaseModel):
    """Discounts object in checkout responses."""
    codes: List[str] = Field(
        default_factory=list,
        description="Submitted discount codes"
    )
    applied: List[AppliedDiscount] = Field(
        default_factory=list,
        description="All active discounts"
    )


class DiscountMessage(BaseModel):
    """Message for rejected discount code."""
    type: str = "warning"
    code: DiscountErrorCode
    path: str = Field(..., description="JSONPath to the rejected code")
    content: str = Field(..., description="Human-readable error message")


def create_discount_capability() -> dict:
    """Create Discount capability for UCP profile."""
    return {
        "name": DISCOUNT_CAPABILITY_NAME,
        "version": DISCOUNT_VERSION,
        "extends": "dev.ucp.shopping.checkout",
        "spec": "https://ucp.dev/specification/discount",
        "schema": "https://ucp.dev/schemas/shopping/discount.json"
    }


def apply_discount_code(
    code: str,
    available_discounts: dict
) -> tuple[Optional[AppliedDiscount], Optional[DiscountMessage]]:
    """
    Attempt to apply a discount code.
    
    Args:
        code: The discount code to apply
        available_discounts: Dict of code -> discount info
        
    Returns:
        Tuple of (applied_discount, error_message)
    """
    code_upper = code.upper()
    
    if code_upper not in available_discounts:
        return None, DiscountMessage(
            code=DiscountErrorCode.DISCOUNT_CODE_INVALID,
            path=f"$.discounts.codes[0]",
            content=f"Code '{code}' is not valid"
        )
    
    discount_info = available_discounts[code_upper]
    
    # Check if expired
    if discount_info.get("expired"):
        return None, DiscountMessage(
            code=DiscountErrorCode.DISCOUNT_CODE_EXPIRED,
            path=f"$.discounts.codes[0]",
            content=f"Code '{code}' has expired"
        )
    
    return AppliedDiscount(
        code=code,
        title=discount_info.get("title", f"Discount: {code}"),
        amount=discount_info.get("amount", 0),
        priority=discount_info.get("priority", 1),
    ), None


def calculate_discount_amount(
    discount: AppliedDiscount,
    subtotal: int,
    line_items: list
) -> int:
    """
    Calculate the actual discount amount.
    
    Args:
        discount: The discount to calculate
        subtotal: Order subtotal in cents
        line_items: List of line items
        
    Returns:
        Discount amount in cents
    """
    return min(discount.amount, subtotal)


def create_automatic_discount(
    title: str,
    amount: int,
    priority: int = 99
) -> AppliedDiscount:
    """Create an automatic discount."""
    return AppliedDiscount(
        title=title,
        amount=amount,
        automatic=True,
        priority=priority,
    )


def is_discount_active(platform_capabilities: list[str]) -> bool:
    """Check if Discount is in the capability intersection."""
    return DISCOUNT_CAPABILITY_NAME in platform_capabilities


# Sample discount codes for demo
SAMPLE_DISCOUNTS = {
    "SAVE10": {"title": "$10 Off Your Order", "amount": 1000, "priority": 1},
    "SAVE20": {"title": "$20 Off Your Order", "amount": 2000, "priority": 1},
    "PERCENT10": {"title": "10% Off", "amount": 0, "percent": 10, "priority": 1},
    "WELCOME": {"title": "Welcome Discount", "amount": 500, "priority": 2},
    "EXPIRED": {"title": "Expired Code", "amount": 1000, "expired": True},
}
