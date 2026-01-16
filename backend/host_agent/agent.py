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

"""UCP Agent with MCP Tools Integration - Supports Ollama and Google Gemini."""

import logging
import os
from typing import Any, Dict, Optional
from a2a.types import TaskState
from a2a.utils import get_message_text
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from ucp_sdk.models.schemas.shopping.types.buyer import Buyer
from ucp_sdk.models.schemas.shopping.types.postal_address import PostalAddress
from ..extensions.ucp_extension import UcpExtension
from ..constants import Constants
from ..payment_processor import MockPaymentProcessor
from ..store import RetailStore
from ..mcp_server.mcp_adapter import MCPConnector


store = RetailStore()
mpp = MockPaymentProcessor()
constants = Constants()
connector = MCPConnector()

# Model configuration - supports Ollama via LiteLLM
# Set USE_OLLAMA=true in .env to use Ollama
USE_OLLAMA = os.getenv("USE_OLLAMA", "true").lower() == "true"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")  # or qwen2.5, mistral, etc.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def _create_error_response(message: str) -> dict:
    return {"message": message, "status": "error"}


def after_tool_modifier(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    tool_response: Dict,
) -> Optional[Dict]:
    extensions = tool_context.state.get(constants.ADK_EXTENSIONS_STATE_KEY, [])
    # add typed data responses to the state
    ucp_response_keys = [constants.UCP_CHECKOUT_KEY, "a2a.product_results"]
    if UcpExtension.URI in extensions and any(
        key in tool_response for key in ucp_response_keys
    ):
        tool_context.state[constants.ADK_LATEST_TOOL_RESULT] = tool_response

    return None


def modify_output_after_agent(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    # add the UCP tool responses as agent output
    if callback_context.state.get(constants.ADK_LATEST_TOOL_RESULT):
        return types.Content(
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        response={
                            "result": callback_context.state[constants.ADK_LATEST_TOOL_RESULT]
                        }
                    )
                )
            ],
            role="model",
        )

    return None


def get_model():
    """
    Get the appropriate model based on configuration.
    
    If USE_OLLAMA is true, uses LiteLLM to connect to Ollama.
    Otherwise, uses Google Gemini.
    """
    if USE_OLLAMA:
        try:
            from google.adk.models.lite_llm import LiteLlm
            
            # LiteLLM format for Ollama: "ollama/model_name"
            model_name = f"ollama/{OLLAMA_MODEL}"
            
            print(f"[INFO] Using Ollama model: {OLLAMA_MODEL}")
            print(f"[INFO] Ollama base URL: {OLLAMA_BASE_URL}")
            
            return LiteLlm(
                model=model_name,
                api_base=OLLAMA_BASE_URL,
            )
        except ImportError:
            print("[WARNING] LiteLlm not available, falling back to Gemini")
            return "gemini-2.0-flash"
        except Exception as e:
            print(f"[WARNING] Ollama setup failed: {e}, falling back to Gemini")
            return "gemini-2.0-flash"
    else:
        print("[INFO] Using Google Gemini model")
        return "gemini-2.0-flash"


async def build_agent():
    """
    Builds the shopper agent with MCP tools loaded dynamically.
    
    Returns:
        Agent: The configured shopper agent with MCP tools
    """
    mcp_tools = await connector.get_tools()
    
    model = get_model()
    
    root_agent = Agent(
        name="shopper_agent",
        model=model,
        description="Agent to help with shopping",
        instruction=(
            "You are a helpful shopping agent. You have access to these tools:\n"
            "- search_products: Search for products in the catalog\n"
            "- get_product: Get details of a specific product\n"
            "- create_checkout: Create a new checkout with items\n"
            "- get_checkout: Get current checkout status\n"
            "- update_checkout: Update checkout (add/remove items, change quantities)\n"
            "- complete_checkout: Complete the checkout and place order\n"
            "- cancel_checkout: Cancel the current checkout\n\n"
            "When user asks to search or find products, use search_products.\n"
            "When user wants to buy something, first search for it, then create_checkout.\n"
            "When user wants to add more items, use update_checkout.\n"
            "When user wants to see their cart, use get_checkout.\n"
            "When user wants to complete purchase, use complete_checkout.\n"
            "Always respond in the user's language."
        ),
        tools=[*mcp_tools],
        after_tool_callback=after_tool_modifier,
        after_agent_callback=modify_output_after_agent,
    )
    
    return root_agent


# For sync usage - create a wrapper
def get_agent():
    """
    Synchronous wrapper to get the agent.
    Use build_agent() for async contexts.
    """
    import asyncio
    return asyncio.run(build_agent())