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
Combined UCP Server

This module starts a combined server that provides:
1. MCP Server for checkout tools (via FastMCP/Streamable HTTP)
2. HTTP endpoints for Embedded Checkout (EP Binding)

Usage:
    python -m backend.server
    
Or:
    uv run python -m backend.server
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the main FastAPI app
app = FastAPI(
    title="UCP Merchant Server",
    description="UCP MCP Binding and Embedded Checkout Protocol server",
    version="2026-01-11",
)

# Add CORS middleware for embedded checkout
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include embedded checkout routes
from .embedded_checkout_routes import router as embedded_checkout_router
app.include_router(embedded_checkout_router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "UCP Merchant Server"}


# UCP service discovery endpoint
@app.get("/.well-known/ucp")
async def ucp_discovery():
    """UCP service discovery endpoint."""
    return {
        "services": {
            "dev.ucp.shopping": {
                "version": "2026-01-11",
                "rest": {
                    "schema": "https://ucp.dev/services/shopping/rest.openapi.json",
                    "endpoint": "http://localhost:10999/ucp/v1"
                },
                "mcp": {
                    "schema": "https://ucp.dev/services/shopping/mcp.openrpc.json",
                    "endpoint": "http://localhost:10999/mcp"
                },
                "embedded": {
                    "schema": "https://ucp.dev/services/shopping/embedded.openrpc.json"
                }
            }
        }
    }


def run_server(host: str = "localhost", port: int = 10999):
    """Run the combined server."""
    logger.info(f"Starting UCP Merchant Server on http://{host}:{port}")
    logger.info("Available endpoints:")
    logger.info("  - GET  /.well-known/ucp - UCP service discovery")
    logger.info("  - GET  /health - Health check")
    logger.info("  - GET  /embedded-checkout/{checkout_id} - Embedded checkout UI")
    logger.info("  - POST /embedded-checkout/{checkout_id}/update - Update checkout")
    logger.info("  - POST /embedded-checkout/{checkout_id}/complete - Complete checkout")
    logger.info("")
    logger.info("For MCP tools, use the MCP server directly:")
    logger.info("  python -m backend.mcp_server.streamable_http_server")
    
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
