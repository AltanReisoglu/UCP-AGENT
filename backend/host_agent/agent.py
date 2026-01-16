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

"""UCP."""

import logging
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


store = RetailStore()
mpp = MockPaymentProcessor()
constants = Constants()

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

root_agent = Agent(
    name="shopper_agent",
    model="gemini-2.5-flash",
    description="Agent to help with shopping",
    instruction=(
        "You are a helpful agent who can help user with shopping actions such"
        " as searching the catalog, add to checkout session, complete checkout"
        " and handle order placed event.Given the user ask, plan ahead and"
        " invoke the tools available to complete the user's ask. Always make"
        " sure you have completed all aspects of the user's ask. If the user"
        " says add to my list or remove from the list, add or remove from the"
        " cart, add the product or remove the product from the checkout"
        " session. If the user asks to add any items to the checkout session,"
        " search for the products and then add the matching products to"
        " checkout session.If the user asks to replace products,"
        " use remove_from_checkout and add_to_checkout tools to replace the"
        " products to match the user request"
    ),
    tools=[
        search_shopping_catalog,
        add_to_checkout,
        remove_from_checkout,
        update_checkout,
        get_checkout,
        start_payment,
        update_customer_details,
        complete_checkout,
    ],
    after_tool_callback=after_tool_modifier,
    after_agent_callback=modify_output_after_agent,
)