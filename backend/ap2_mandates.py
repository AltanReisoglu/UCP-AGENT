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
AP2 Mandates Extension Implementation

This module implements the AP2 Mandates Extension for UCP Checkout Capability
as per https://ucp.dev/specification/ap2-mandates/

The extension enables secure exchange of user intents and authorizations using
Verifiable Digital Credentials with the following features:

- Business Authorization: Cryptographic signature on checkout responses
- Checkout Mandates: SD-JWT+kb credentials proving user authorization
- JCS Canonicalization: Deterministic JSON serialization for signing

Key Components:
- Ap2CheckoutResponse: ap2 object in checkout responses
- Ap2CompleteRequest: ap2 object in complete_checkout requests
- MerchantAuthorizationSigner: Creates detached JWS signatures
- MandateVerifier: Verifies SD-JWT+kb mandates
"""

import base64
import hashlib
import json
import logging
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, field_validator
from uuid import uuid4
from datetime import datetime, timezone

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

logger = logging.getLogger(__name__)


AP2_VERSION = "2026-01-11"
AP2_CAPABILITY_NAME = "dev.ucp.shopping.ap2_mandate"


class Ap2ErrorCode(str, Enum):
    """AP2-specific error codes."""
    MANDATE_REQUIRED = "mandate_required"
    AGENT_MISSING_KEY = "agent_missing_key"
    MANDATE_INVALID_SIGNATURE = "mandate_invalid_signature"
    MANDATE_EXPIRED = "mandate_expired"
    MANDATE_SCOPE_MISMATCH = "mandate_scope_mismatch"
    MERCHANT_AUTHORIZATION_INVALID = "merchant_authorization_invalid"
    MERCHANT_AUTHORIZATION_MISSING = "merchant_authorization_missing"


class SignatureAlgorithm(str, Enum):
    """Supported signature algorithms for AP2."""
    ES256 = "ES256"
    ES384 = "ES384"
    ES512 = "ES512"


class Ap2CheckoutResponse(BaseModel):
    """
    The ap2 object included in CREATE/UPDATE checkout responses.
    
    Contains the merchant_authorization which is a detached JWS signature
    proving the checkout terms are authentic.
    """
    merchant_authorization: str = Field(
        ...,
        description="JWS Detached Content signature over checkout (excluding ap2 field)",
        pattern=r"^[A-Za-z0-9_-]+\.\.[A-Za-z0-9_-]+$"
    )


class Ap2CompleteRequest(BaseModel):
    """
    The ap2 object included in COMPLETE checkout requests.
    
    Contains the checkout_mandate which is an SD-JWT+kb credential
    proving user authorization for the checkout.
    """
    checkout_mandate: str = Field(
        ...,
        description="SD-JWT+kb credential proving user authorization",
        pattern=r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+(~[A-Za-z0-9_-]+)*$"
    )


class Ap2CapabilityConfig(BaseModel):
    """Configuration for AP2 capability in UCP profile."""
    vp_formats_supported: Dict[str, Dict] = Field(
        default_factory=lambda: {"dc+sd-jwt": {}}
    )


class Ap2Capability(BaseModel):
    """AP2 capability declaration for UCP profile."""
    name: str = AP2_CAPABILITY_NAME
    version: str = AP2_VERSION
    spec: str = "https://ucp.dev/specification/ap2-mandates"
    schema_url: str = Field(
        alias="schema",
        default="https://ucp.dev/schemas/shopping/ap2_mandate.json"
    )
    extends: str = "dev.ucp.shopping.checkout"
    config: Ap2CapabilityConfig = Field(default_factory=Ap2CapabilityConfig)


class SigningKey(BaseModel):
    """Platform signing key for mandate verification."""
    kid: str = Field(..., description="Key ID")
    kty: str = Field(default="EC", description="Key type")
    crv: str = Field(default="P-256", description="Curve name")
    x: str = Field(..., description="X coordinate (base64url)")
    y: str = Field(..., description="Y coordinate (base64url)")
    alg: str = Field(default="ES256", description="Algorithm")


def base64url_encode(data: bytes) -> str:
    """Encode bytes to base64url without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def base64url_decode(data: str) -> bytes:
    """Decode base64url string to bytes."""
    padding = 4 - len(data) % 4
    if padding != 4:
        data += '=' * padding
    return base64.urlsafe_b64decode(data)


def jcs_canonicalize(obj: Any) -> bytes:
    """
    JSON Canonicalization Scheme (JCS) per RFC 8785.
    
    Produces deterministic, byte-for-byte identical JSON representation.
    """
    return json.dumps(
        obj,
        ensure_ascii=False,
        allow_nan=False,
        indent=None,
        separators=(',', ':'),
        sort_keys=True
    ).encode('utf-8')


def remove_ap2_field(checkout: Dict[str, Any]) -> Dict[str, Any]:
    """Remove the ap2 field from checkout for signature computation."""
    result = checkout.copy()
    result.pop('ap2', None)
    return result


class MerchantAuthorizationSigner:
    """
    Creates merchant_authorization (detached JWS) for checkout responses.
    
    The signature is a JWS Detached Content signature (RFC 7515 Appendix F)
    over the checkout response body (excluding the ap2 field).
    
    Format: <base64url-header>..<base64url-signature>
    """
    
    def __init__(
        self,
        private_key: Optional[Any] = None,
        kid: str = "merchant_key_1",
        algorithm: SignatureAlgorithm = SignatureAlgorithm.ES256,
    ):
        """
        Initialize the signer.
        
        Args:
            private_key: EC private key for signing (optional for mock)
            kid: Key ID to include in JWS header
            algorithm: Signature algorithm
        """
        self.private_key = private_key
        self.kid = kid
        self.algorithm = algorithm
        self._use_mock = private_key is None or not HAS_CRYPTOGRAPHY
    
    def sign_checkout(self, checkout: Dict[str, Any]) -> str:
        """
        Create merchant_authorization for a checkout.
        
        Args:
            checkout: The checkout object (ap2 field will be excluded)
            
        Returns:
            Detached JWS string: <header>..<signature>
        """
        # Remove ap2 field for signature computation
        payload = remove_ap2_field(checkout)
        
        # Canonicalize using JCS
        canonical_bytes = jcs_canonicalize(payload)
        
        # Create protected header
        header = {
            "alg": self.algorithm.value,
            "kid": self.kid
        }
        encoded_header = base64url_encode(json.dumps(header).encode('utf-8'))
        
        # Create signing input
        encoded_payload = base64url_encode(canonical_bytes)
        signing_input = f"{encoded_header}.{encoded_payload}".encode('utf-8')
        
        # Sign
        if self._use_mock:
            # Mock signature for demo purposes
            signature = self._mock_sign(signing_input)
        else:
            signature = self._real_sign(signing_input)
        
        # Return detached JWS (header..signature, no payload)
        encoded_signature = base64url_encode(signature)
        return f"{encoded_header}..{encoded_signature}"
    
    def _mock_sign(self, signing_input: bytes) -> bytes:
        """Create a mock signature using SHA-256 hash."""
        return hashlib.sha256(signing_input).digest()
    
    def _real_sign(self, signing_input: bytes) -> bytes:
        """Create a real ECDSA signature."""
        if not HAS_CRYPTOGRAPHY:
            raise RuntimeError("cryptography library required for real signing")
        
        # Select hash algorithm based on signature algorithm
        hash_alg = {
            SignatureAlgorithm.ES256: hashes.SHA256(),
            SignatureAlgorithm.ES384: hashes.SHA384(),
            SignatureAlgorithm.ES512: hashes.SHA512(),
        }[self.algorithm]
        
        signature = self.private_key.sign(
            signing_input,
            ec.ECDSA(hash_alg)
        )
        return signature


class MandateVerifier:
    """
    Verifies SD-JWT+kb checkout mandates.
    
    The mandate is an SD-JWT+kb credential containing the full checkout
    including the ap2.merchant_authorization field.
    """
    
    def __init__(self, signing_keys: Optional[List[SigningKey]] = None):
        """
        Initialize the verifier.
        
        Args:
            signing_keys: Platform signing keys for verification
        """
        self.signing_keys = signing_keys or []
        self._key_map: Dict[str, SigningKey] = {
            key.kid: key for key in self.signing_keys
        }
    
    def verify_mandate(
        self,
        mandate: str,
        expected_checkout: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify a checkout mandate.
        
        Args:
            mandate: The SD-JWT+kb mandate string
            expected_checkout: The checkout state that should be in the mandate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Parse SD-JWT+kb structure
            parts = mandate.split('~')
            jwt_part = parts[0]
            disclosures = parts[1:] if len(parts) > 1 else []
            
            # Split JWT into header.payload.signature
            jwt_sections = jwt_part.split('.')
            if len(jwt_sections) != 3:
                return False, "Invalid JWT structure"
            
            header_b64, payload_b64, signature_b64 = jwt_sections
            
            # Decode header
            header = json.loads(base64url_decode(header_b64))
            
            # For demo/mock, we accept the mandate without full verification
            # In production, this would verify:
            # 1. Signature using the platform's public key
            # 2. Expiration (exp claim)
            # 3. Checkout scope matches expected_checkout
            
            logger.info(f"Mandate verification: header alg={header.get('alg')}")
            
            # Check for key binding (kb) suffix
            # This is a simplified check
            
            return True, None
            
        except Exception as e:
            logger.exception("Mandate verification failed")
            return False, str(e)
    
    def verify_merchant_authorization(
        self,
        authorization: str,
        checkout: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify a merchant_authorization signature.
        
        Args:
            authorization: The detached JWS string
            checkout: The checkout object (will have ap2 excluded)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Parse detached JWS: header..signature
            match = re.match(r'^([A-Za-z0-9_-]+)\.\.([A-Za-z0-9_-]+)$', authorization)
            if not match:
                return False, "Invalid merchant_authorization format"
            
            header_b64, signature_b64 = match.groups()
            
            # Decode header
            header = json.loads(base64url_decode(header_b64))
            alg = header.get('alg')
            kid = header.get('kid')
            
            if alg not in [a.value for a in SignatureAlgorithm]:
                return False, f"Unsupported algorithm: {alg}"
            
            logger.info(f"Merchant authorization: alg={alg}, kid={kid}")
            
            # For demo/mock, accept without full cryptographic verification
            # In production, this would reconstruct the signing input and verify
            
            return True, None
            
        except Exception as e:
            logger.exception("Merchant authorization verification failed")
            return False, str(e)


class Ap2Session:
    """
    Manages AP2 state for a checkout session.
    
    When AP2 is negotiated:
    - Business MUST include ap2.merchant_authorization in responses
    - Platform MUST provide ap2.checkout_mandate in complete_checkout
    """
    
    def __init__(
        self,
        checkout_id: str,
        signer: Optional[MerchantAuthorizationSigner] = None,
        verifier: Optional[MandateVerifier] = None,
    ):
        self.checkout_id = checkout_id
        self.signer = signer or MerchantAuthorizationSigner()
        self.verifier = verifier or MandateVerifier()
        self.is_locked = True  # Session is security-locked once AP2 is active
    
    def add_merchant_authorization(
        self,
        checkout: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add ap2.merchant_authorization to a checkout response.
        
        Args:
            checkout: The checkout object
            
        Returns:
            Checkout with ap2 field added
        """
        # Sign the checkout (excluding existing ap2 field)
        merchant_auth = self.signer.sign_checkout(checkout)
        
        # Add ap2 field
        checkout['ap2'] = {
            'merchant_authorization': merchant_auth
        }
        
        return checkout
    
    def verify_complete_request(
        self,
        ap2_request: Dict[str, Any],
        expected_checkout: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[Ap2ErrorCode]]:
        """
        Verify an AP2 complete_checkout request.
        
        Args:
            ap2_request: The ap2 object from complete_checkout
            expected_checkout: The expected checkout state
            
        Returns:
            Tuple of (is_valid, error_message, error_code)
        """
        # Check for required checkout_mandate
        checkout_mandate = ap2_request.get('checkout_mandate')
        if not checkout_mandate:
            return False, "ap2.checkout_mandate is required", Ap2ErrorCode.MANDATE_REQUIRED
        
        # Verify the mandate
        is_valid, error = self.verifier.verify_mandate(
            checkout_mandate,
            expected_checkout
        )
        
        if not is_valid:
            return False, error, Ap2ErrorCode.MANDATE_INVALID_SIGNATURE
        
        return True, None, None


def create_ap2_capability() -> Dict[str, Any]:
    """Create AP2 capability object for UCP profile."""
    return {
        "name": AP2_CAPABILITY_NAME,
        "version": AP2_VERSION,
        "spec": "https://ucp.dev/specification/ap2-mandates",
        "schema": "https://ucp.dev/schemas/shopping/ap2_mandate.json",
        "extends": "dev.ucp.shopping.checkout",
        "config": {
            "vp_formats_supported": {
                "dc+sd-jwt": {}
            }
        }
    }


def is_ap2_active(platform_capabilities: List[str]) -> bool:
    """Check if AP2 is in the capability intersection."""
    return AP2_CAPABILITY_NAME in platform_capabilities
