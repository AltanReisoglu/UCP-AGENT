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

import asyncio
import functools
import json
import logging
import os

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard
import click
from dotenv import load_dotenv
import httpx
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, JSONResponse
from starlette.requests import Request
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
import uvicorn

from .agent import root_agent as business_agent
from .agent_executor import ADKAgentExecutor
from ..store import RetailStore

load_dotenv()

# Initialize store for API access
store = RetailStore()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


# ============ EP API Handlers ============

async def get_checkout_api(request: Request) -> JSONResponse:
    """GET /api/checkout/{checkout_id} - Returns checkout data for embedded checkout page."""
    checkout_id = request.path_params.get('checkout_id')
    checkout = store.get_checkout(checkout_id)
    if checkout is None:
        return JSONResponse({"error": "Checkout not found"}, status_code=404)
    return JSONResponse(checkout.model_dump(mode='json'),status_code=200)

async def complete_checkout_api(request: Request) -> JSONResponse:
    """POST /api/checkout/{checkout_id}/complete - Places order and returns confirmation."""
    checkout_id = request.path_params.get('checkout_id')
    
    try:
        checkout = store.place_order(checkout_id)
        checkout.status = "completed"
        checkout_data = checkout.model_dump(mode='json')
        return JSONResponse(checkout_data)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


def make_sync(func):
  @functools.wraps(func)
  def wrapper(*args, **kwargs):
    return asyncio.run(func(*args, **kwargs))

  return wrapper


@click.command()
@click.option("--host", default="localhost")
@click.option("--port", default=10999)
@make_sync
async def run(host, port):  
  if not os.getenv("GOOGLE_API_KEY"):
    logger.error("GOOGLE_API_KEY must be set")
    exit(1)

  card_path = os.path.join(os.path.dirname(__file__), "..", "mock_datas", "agent_card.json")
  with open(card_path, "r", encoding="utf-8") as f:
    data = json.load(f)
  agent_card = AgentCard.model_validate(data)

  task_store = InMemoryTaskStore()

  request_handler = DefaultRequestHandler(
      agent_executor=ADKAgentExecutor(
          agent=business_agent,
          extensions=agent_card.capabilities.extensions or [],
          
      ),
      task_store=task_store,
      push_notifier=InMemoryPushNotifier(httpx_client)
  
  )

  a2a_app = A2AStarletteApplication(
      agent_card=agent_card, http_handler=request_handler
  )
  routes = a2a_app.routes()
  routes.extend([
      Route(
          "/.well-known/ucp",
          lambda _: FileResponse(
              os.path.join(os.path.dirname(__file__), "..", "mock_datas", "ucp.json")
          ),
      ),
      Route(
          "/embedded-checkout/{checkout_id}",
          lambda _: FileResponse(
              os.path.join(os.path.dirname(__file__), "..", "mock_datas", "embedded-checkout.html")
          ),
      ),
      # API endpoints for embedded checkout
      Route(
          "/api/checkout/{checkout_id}",
          get_checkout_api,
          methods=["GET"],
      ),
      Route(
          "/api/checkout/{checkout_id}/complete",
          complete_checkout_api,
          methods=["POST"],
      ),
      Mount(
          "/images",
          app=StaticFiles(
              directory=os.path.join(os.path.dirname(__file__), "..", "mock_datas", "images")
          ),
          name="images",
      ),
  ])
  
  # Add CORS middleware for browser access
  middleware = [
      Middleware(
          CORSMiddleware,
          allow_origins=["*"],
          allow_methods=["*"],
          allow_headers=["*"],
      )
  ]
  app = Starlette(routes=routes, middleware=middleware)

  config = uvicorn.Config(app, host=host, port=port, log_level="info")
  server = uvicorn.Server(config)
  await server.serve()


if __name__ == "__main__":
  run()