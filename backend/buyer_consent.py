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
Buyer Consent Extension Implementation

This module implements the Buyer Consent Extension for UCP Checkout Capability
as per https://ucp.dev/specification/buyer-consent/

The extension enables platforms to transmit buyer consent choices to businesses
regarding data usage and communication preferences, helping with GDPR/CCPA compliance.

Consent Categories:
- analytics: Consent for analytics/tracking
- preferences: Consent for preference cookies/storage
- marketing: Consent for marketing communications
- sale_of_data: Consent for sale/sharing of personal data

Usage:
    Consent is included in the buyer object during create_checkout and update_checkout:
    
    buyer = {
        "email": "user@example.com",
        "consent": {
            "analytics": True,
            "preferences": True,
            "marketing": False,
            "sale_of_data": False
        }
    }
"""

from typing import Optional
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


BUYER_CONSENT_VERSION = "2026-01-11"
BUYER_CONSENT_CAPABILITY_NAME = "dev.ucp.shopping.buyer_consent"


class BuyerConsent(BaseModel):
    """
    Consent object representing buyer's privacy preferences.
    
    All fields are optional - absence means consent state is unknown/not provided.
    Businesses should handle missing consent according to their default policies.
    """
    analytics: Optional[bool] = Field(
        None,
        description="Consent for analytics and tracking (e.g., Google Analytics)"
    )
    preferences: Optional[bool] = Field(
        None,
        description="Consent for preference cookies and personalization"
    )
    marketing: Optional[bool] = Field(
        None,
        description="Consent for marketing communications (email, SMS, etc.)"
    )
    sale_of_data: Optional[bool] = Field(
        None,
        description="Consent for sale or sharing of personal data (CCPA)"
    )
    
    def has_any_consent(self) -> bool:
        """Check if any consent has been explicitly provided."""
        return any([
            self.analytics is not None,
            self.preferences is not None,
            self.marketing is not None,
            self.sale_of_data is not None,
        ])
    
    def to_dict(self) -> dict:
        """Convert to dict, excluding None values."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class BuyerWithConsent(BaseModel):
    """
    Extended Buyer object with consent field.
    
    This model extends the base Buyer model to include consent preferences.
    """
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    consent: Optional[BuyerConsent] = Field(
        None,
        description="Buyer's privacy consent preferences"
    )


class BuyerConsentCapability(BaseModel):
    """Buyer Consent capability declaration for UCP profile."""
    name: str = BUYER_CONSENT_CAPABILITY_NAME
    version: str = BUYER_CONSENT_VERSION
    extends: str = "dev.ucp.shopping.checkout"


def create_buyer_consent_capability() -> dict:
    """Create Buyer Consent capability for UCP profile."""
    return {
        "name": BUYER_CONSENT_CAPABILITY_NAME,
        "version": BUYER_CONSENT_VERSION,
        "extends": "dev.ucp.shopping.checkout"
    }


def extract_consent_from_buyer(buyer: dict) -> Optional[BuyerConsent]:
    """
    Extract consent object from buyer data.
    
    Args:
        buyer: Buyer dictionary that may contain consent
        
    Returns:
        BuyerConsent object or None if no consent provided
    """
    consent_data = buyer.get("consent")
    if consent_data:
        return BuyerConsent.model_validate(consent_data)
    return None


def apply_consent_to_buyer(buyer: dict, consent: BuyerConsent) -> dict:
    """
    Add consent to a buyer object.
    
    Args:
        buyer: Buyer dictionary
        consent: BuyerConsent object
        
    Returns:
        Updated buyer dictionary with consent
    """
    result = buyer.copy()
    if consent and consent.has_any_consent():
        result["consent"] = consent.to_dict()
    return result


def validate_consent_request(consent_data: dict) -> tuple[bool, Optional[str]]:
    """
    Validate consent data from a request.
    
    Args:
        consent_data: Raw consent dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        consent = BuyerConsent.model_validate(consent_data)
        return True, None
    except Exception as e:
        return False, f"Invalid consent data: {e}"


def is_buyer_consent_active(platform_capabilities: list[str]) -> bool:
    """Check if Buyer Consent is in the capability intersection."""
    return BUYER_CONSENT_CAPABILITY_NAME in platform_capabilities


def get_consent_defaults() -> BuyerConsent:
    """
    Get default consent values.
    
    Note: Default behavior when consent is not provided is business-specific.
    This provides a conservative default (all False).
    """
    return BuyerConsent(
        analytics=False,
        preferences=False,
        marketing=False,
        sale_of_data=False,
    )


def merge_consent(existing: Optional[BuyerConsent], update: BuyerConsent) -> BuyerConsent:
    """
    Merge consent updates with existing consent.
    
    Only updates fields that are explicitly set in the update.
    
    Args:
        existing: Existing consent or None
        update: New consent values
        
    Returns:
        Merged consent object
    """
    if existing is None:
        return update
    
    merged_data = existing.model_dump()
    update_data = update.model_dump()
    
    for key, value in update_data.items():
        if value is not None:
            merged_data[key] = value
    
    return BuyerConsent.model_validate(merged_data)
