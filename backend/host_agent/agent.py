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


def search_shopping_catalog(tool_context: ToolContext, query: str) -> dict:
  """Searches the product catalog for products that match the given query.

  Args:
      query (str): query for performing product search

  Returns:
      dict: Returns the response from the tool with success or error status.
  """

  try:
    product_results = store.search_products(query)
    return {"a2a.product_results": product_results.model_dump(mode="json")}
  except Exception:
    logging.exception("There was an error searching the product catalog.")
    return _create_error_response("Sorry, there was an error searching the product catalog, please try again later.")


def add_to_checkout(
    tool_context: ToolContext, product_id: str, quantity: int = 1
) -> dict:
  """Adds a product to the checkout session.

  Args:
      product_id (str): product id or sku
      quantity (int): quantity; defaults to 1 if not specified
      additional_info (str): Provide additional grouping information for an item
        in the cart e.g. 'Regular Grocery', 'For Birthday party'

  Returns:
      dict: Returns the response from the tool with success or error status.
  """
  checkout_id = (
      tool_context.state[constants.ADK_USER_CHECKOUT_ID]
      if constants.ADK_USER_CHECKOUT_ID in tool_context.state
      else None
  )
  ucp_metadata = (
      tool_context.state[constants.ADK_UCP_METADATA_STATE]
      if constants.ADK_UCP_METADATA_STATE in tool_context.state
      else None
  )

  if not ucp_metadata:
    return _create_error_response("There was an error creating UCP metadata")

  try:
    checkout = store.add_to_checkout(
        ucp_metadata, product_id, quantity, checkout_id
    )
    if not checkout_id:
      tool_context.state[constants.ADK_USER_CHECKOUT_ID] = checkout.id

    return {
        constants.UCP_CHECKOUT_KEY: checkout.model_dump(mode="json"),
        "status": "success",
    }
  except ValueError:
    logging.exception(
        "There was an error adding item to checkout, please retry later."
    )
    return _create_error_response(
        "There was an error adding item to checkout, please retry later."
    )


def remove_from_checkout(tool_context: ToolContext, product_id: str) -> dict:
  """Removes a product from the checkout session.

  Args:
      product_id (str): product id or sku
      quantity (int): quantity; defaults to 1 if not specified

  Returns:
      dict: Returns the response from the tool with success or error status.
  """
  checkout_id = _get_current_checkout_id(tool_context)

  if not checkout_id:
    return _create_error_response("A Checkout has not yet been created.")

  try:
    return {
        constants.UCP_CHECKOUT_KEY: (
            store.remove_from_checkout(checkout_id, product_id).model_dump(
                mode="json"
            )
        ),
        "status": "success",
    }
  except ValueError:
    logging.exception(
        "There was an error removing item from checkout, please retry later."
    )
    return _create_error_response(
        "There was an error removing item from checkout, please retry later."
    )


def update_checkout(
    tool_context: ToolContext, product_id: str, quantity: int
) -> dict:
  """Updates the quantity of a product in the checkout session.

  Args:
      product_id (str): product id or sku
      quantity (int): quantity;

  Returns:
      dict: Returns the response from the tool with success or error status.
  """

  checkout_id = _get_current_checkout_id(tool_context)
  if not checkout_id:
    return _create_error_response("A Checkout has not yet been created.")

  try:
    return {
        constants.UCP_CHECKOUT_KEY: (
            store.update_checkout(checkout_id, product_id, quantity).model_dump(
                mode="json"
            )
        ),
        "status": "success",
    }
  except ValueError:
    logging.exception(
        "There was an error updating item in the cart, please retry later."
    )
    return _create_error_response(
        "There was an error updating item in the cart, please retry later."
    )


def get_checkout(tool_context: ToolContext) -> dict:
  """Retrieves a Checkout Session.

  Args: None

  Returns:
      dict: Returns the response from the tool with success or error status.
  """
  checkout_id = _get_current_checkout_id(tool_context)

  if not checkout_id:
    return _create_error_response("A Checkout has not yet been created.")

  checkout = store.get_checkout(checkout_id)
  if checkout is None:
    return _create_error_response("Checkout not found with the given ID.")

  return {
      constants.UCP_CHECKOUT_KEY: checkout.model_dump(mode="json"),
      "status": "success",
  }


def update_customer_details(
    tool_context: ToolContext,
    first_name: str,
    last_name: str,
    street_address: str,
    address_locality: str,
    address_region: str,
    postal_code: str,
    address_country: Optional[str],
    extended_address: Optional[str] = None,
    email: Optional[str] = None,
) -> dict:
  """Adds delivery address to the checkout.

  Args:
      first_name: First name of the recipient.
      last_name: Last name of the recipient.
      street_address: The street address. For example, 1600 Amphitheatre Pkwy.
      address_locality: The locality in which the street address is, and which
        is in the region. For example, Mountain View.
      address_region: The region in which the locality is, and which is in the
        country. For example, CA.
      postal_code: The postal code. For example, 94043.
      address_country: The country. For example, US. You can use the two-letter
        ISO 3166-1 alpha-2 country code.
      extended_address: The extended address of the postal address. For example,
        a suite number
      email: The email address of the recipient.

  Returns:
      dict: Returns the response from the tool with success or error status.
  """
  checkout_id = _get_current_checkout_id(tool_context)

  if not checkout_id:
    return _create_error_response("A Checkout has not yet been created.")

  if not address_country:
    address_country = "US"

  address = PostalAddress(
      street_address=street_address,
      extended_address=extended_address,
      address_locality=address_locality,
      address_region=address_region,
      address_country=address_country,
      postal_code=postal_code,
      first_name=first_name,
      last_name=last_name,
  )

  checkout = store.add_delivery_address(checkout_id, address)

  if email:
    checkout.buyer = Buyer(email=email)

  # invoke start payment tool once the user details are added
  return start_payment(tool_context)


async def complete_checkout(tool_context: ToolContext) -> dict:
  """Processes the payment data to complete checkout

  Returns:
      dict: Returns the response from the tool with success or error status.
  """

  checkout_id = _get_current_checkout_id(tool_context)

  if not checkout_id:
    return _create_error_response("A Checkout has not yet been created.")

  checkout = store.get_checkout(checkout_id)

  if checkout is None:
    return _create_error_response("Checkout not found for the current session.")

  payment_data: dict[str, Any] = tool_context.state.get(constants.ADK_PAYMENT_STATE)

  if payment_data is None:
    return {
        "message": (
            "Payment Data is missing. Click 'Confirm Purchase' to complete the"
            " purchase."
        ),
        "status": "requires_more_info",
    }

  try:
    task = mpp.process_payment(
        payment_data[constants.UCP_PAYMENT_DATA_KEY], payment_data[constants.UCP_RISK_SIGNALS_KEY]
    )

    if task is None:
      return _create_error_response(
          "Failed to receive a valid response from MPP"
      )

    if task.status is not None and task.status.state == TaskState.completed:
      payment_instrument = payment_data.get(constants.UCP_PAYMENT_DATA_KEY)
      checkout.payment.selected_instrument_id = payment_instrument.root.id
      checkout.payment.instruments = [payment_instrument]

      response = store.place_order(checkout_id)
      # clear completed checkout from state
      tool_context.state[constants.ADK_USER_CHECKOUT_ID] = None
      return {
          constants.UCP_CHECKOUT_KEY: response.model_dump(mode="json"),
          "status": "success",
      }
    else:
      return _create_error_response(get_message_text(task.status.message))  # type: ignore
  except Exception:
    logging.exception("There was an error completing the checkout.")
    return _create_error_response(
        "Sorry, there was an error completing the checkout, please try again."
    )


def start_payment(tool_context: ToolContext) -> dict:
  """Asks for required information to proceed with the payment.

  Args: None

  Returns:
      dict: checkout object
  """
  checkout_id = _get_current_checkout_id(tool_context)

  if not checkout_id:
    return _create_error_response("A Checkout has not yet been created.")

  result = store.start_payment(checkout_id)
  if isinstance(result, str):
    return {"message": result, "status": "requires_more_info"}
  else:
    tool_context.actions.skip_summarization = True
    return {
        constants.UCP_CHECKOUT_KEY: result.model_dump(mode="json"),
        "status": "success",
    }


def _get_current_checkout_id(tool_context: ToolContext) -> str | None:
  return (
      tool_context.state[constants.ADK_USER_CHECKOUT_ID]
      if constants.ADK_USER_CHECKOUT_ID in tool_context.state
      else None
  )


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