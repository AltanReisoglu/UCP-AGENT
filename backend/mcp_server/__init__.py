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
UCP MCP Server Package

This package implements the MCP (Model Context Protocol) transport binding
for UCP Checkout Capability as per https://ucp.dev/specification/checkout-mcp/

The MCP server provides the following UCP Checkout tools:
- create_checkout: Initiates a new checkout session
- get_checkout: Retrieves the current state of a checkout session
- update_checkout: Updates a checkout session
- complete_checkout: Finalizes the checkout and places the order
- cancel_checkout: Cancels a checkout session

Additional helper tools:
- search_products: Searches the product catalog
- get_product: Retrieves product details by ID
"""

from .streamable_http_server import mcp, create_checkout, get_checkout, update_checkout, complete_checkout, cancel_checkout

__all__ = [
    "mcp",
    "create_checkout",
    "get_checkout", 
    "update_checkout",
    "complete_checkout",
    "cancel_checkout",
]
