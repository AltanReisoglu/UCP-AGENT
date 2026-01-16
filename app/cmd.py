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
UCP Agent CLI - Command line interface to interact with the shopping agent.

This CLI uses the ADKAgentExecutor for proper UCP protocol handling.

Usage:
    python -m app --help
    python -m app chat
    python -m app test
"""

import asyncio
import sys
import os
from uuid import uuid4
from typing import Optional

import click

# Add paths for imports
sys.path.insert(0, '.')
sys.path.insert(0, 'sdk/python/src')

# Fix Windows console encoding
if sys.platform == 'win32':
    os.system('chcp 65001 > nul 2>&1')
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def print_header(title: str):
    """Print a header with borders."""
    border = "=" * (len(title) + 4)
    print(f"\n{border}")
    print(f"| {title} |")
    print(f"{border}\n")


def print_success(msg: str):
    print(f"[OK] {msg}")


def print_error(msg: str):
    print(f"[ERROR] {msg}")


def print_info(msg: str):
    print(f"[INFO] {msg}")


async def run_agent_chat_with_executor(session_id: str):
    """Run interactive chat using ADKAgentExecutor for proper UCP handling."""
    from backend.host_agent.agent import build_agent
    from backend.host_agent.agent_executor import ADKAgentExecutor
    from backend.extensions.ucp_extension import UcpExtension
    from a2a.types import AgentExtension
    from a2a.server.events import EventQueue
    from a2a.server.agent_execution import RequestContext
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    
    print_header("UCP Shopping Agent (with Executor)")
    print(f"Session ID: {session_id}")
    print("Type 'quit' or ':q' to exit\n")
    
    try:
        # Build agent with MCP tools
        print_info("Loading agent and MCP tools...")
        agent = await build_agent()
        print_success(f"Agent loaded with {len(agent.tools)} tool(s)")
        
        # Create executor with UCP extension
        ucp_extension = AgentExtension(
            uri=UcpExtension.URI,
            description="UCP Shopping Extension"
        )
        executor = ADKAgentExecutor(agent, extensions=[ucp_extension])
        print_success("ADKAgentExecutor initialized")
        
        # Create session using executor's session service
        user_id = "cli_user"
        session = await executor.runner.session_service.create_session(
            app_name=agent.name,
            user_id=user_id,
            session_id=session_id,
        )
        print_success(f"Session created: {session.id}")
        
        print_success("Ready for chat!\n")
        
        while True:
            try:
                # Get user input
                user_input = input("You: ")
                
                if user_input.strip().lower() in ["quit", ":q", "exit"]:
                    print("Goodbye!")
                    break
                
                if not user_input.strip():
                    continue
                
                # Create user message and run via Runner directly
                # (ADKAgentExecutor requires A2A server context)
                user_message = types.Content(
                    parts=[types.Part(text=user_input)],
                    role="user"
                )
                
                print_info("Thinking...")
                
                # Run agent
                response_parts = []
                async for event in executor.runner.run_async(
                    session_id=session_id,
                    user_id="cli_user",
                    new_message=user_message,
                ):
                    if hasattr(event, 'content') and event.content:
                        if hasattr(event.content, 'parts'):
                            for part in event.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    response_parts.append(part.text)
                                elif hasattr(part, 'function_response'):
                                    if part.function_response and part.function_response.response:
                                        result = part.function_response.response.get('result')
                                        if result:
                                            response_parts.append(f"\n[Tool Result]: {result}")
                
                # Display response
                if response_parts:
                    response = "\n".join(response_parts)
                    print(f"\nAgent: {response}\n")
                else:
                    print("[INFO] Agent didn't respond with text.\n")
                    
            except KeyboardInterrupt:
                print("\n[INFO] Interrupted. Type 'quit' to exit.")
                continue
                
    except Exception as e:
        print_error(str(e))
        import traceback
        traceback.print_exc()


async def run_agent_chat_simple(session_id: str):
    """Run interactive chat with the agent (simple mode without executor)."""
    from backend.host_agent.agent import build_agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    
    print_header("UCP Shopping Agent (Simple Mode)")
    print(f"Session ID: {session_id}")
    print("Type 'quit' or ':q' to exit\n")
    
    try:
        # Build agent with MCP tools
        print_info("Loading agent and MCP tools...")
        agent = await build_agent()
        print_success(f"Agent loaded with {len(agent.tools)} tool(s)")
        
        # Create session service and runner
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="ucp_shopping_app",
            session_service=session_service,
        )
        
        # Create session
        session = await session_service.create_session(
            app_name="ucp_shopping_app",
            user_id="cli_user",
            session_id=session_id,
        )
        
        print_success("Session created\n")
        
        while True:
            try:
                # Get user input
                user_input = input("You: ")
                
                if user_input.strip().lower() in ["quit", ":q", "exit"]:
                    print("Goodbye!")
                    break
                
                if not user_input.strip():
                    continue
                
                # Create user message
                user_message = types.Content(
                    parts=[types.Part(text=user_input)],
                    role="user"
                )
                
                # Run agent
                print_info("Thinking...")
                
                response_parts = []
                async for event in runner.run_async(
                    session_id=session_id,
                    user_id="cli_user",
                    new_message=user_message,
                ):
                    if hasattr(event, 'content') and event.content:
                        if hasattr(event.content, 'parts'):
                            for part in event.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    response_parts.append(part.text)
                
                # Display response
                if response_parts:
                    response = "\n".join(response_parts)
                    print(f"\nAgent: {response}\n")
                else:
                    print("[INFO] Agent didn't respond with text.\n")
                    
            except KeyboardInterrupt:
                print("\n[INFO] Interrupted. Type 'quit' to exit.")
                continue
                
    except Exception as e:
        print_error(str(e))
        raise


async def run_test():
    """Run a quick test of the agent system."""
    from backend.host_agent.agent import build_agent
    from backend.host_agent.agent_executor import ADKAgentExecutor
    from backend.extensions.ucp_extension import UcpExtension
    from a2a.types import AgentExtension
    
    print_header("System Test")
    
    try:
        # Test 1: Build agent
        print_info("1. Building agent...")
        agent = await build_agent()
        print_success(f"Agent '{agent.name}' created")
        
        # Test 2: Check tools
        print_info("2. Checking tools...")
        print_success(f"{len(agent.tools)} tool(s) loaded")
        
        # Test 3: List MCP tools
        print_info("3. MCP Tools available:")
        for i, tool in enumerate(agent.tools, 1):
            tool_name = getattr(tool, 'name', str(tool))
            print(f"   {i}. {tool_name}")
        
        # Test 4: Create executor
        print_info("4. Creating ADKAgentExecutor...")
        ucp_extension = AgentExtension(
            uri=UcpExtension.URI,
            description="UCP Shopping Extension"
        )
        executor = ADKAgentExecutor(agent, extensions=[ucp_extension])
        print_success("Executor created successfully")
        
        print("\n[SUCCESS] All tests passed!")
        
    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()


async def run_mcp_test():
    """Test MCP server connection directly."""
    import httpx
    import json
    
    print_header("MCP Server Test")
    
    mcp_url = "http://localhost:10999/mcp"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test 1: List tools
            print_info("1. Listing MCP tools...")
            response = await client.post(
                mcp_url,
                json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
            )
            
            if response.status_code == 200:
                print_success("MCP Server responding")
                
                # Parse SSE response
                data = response.text.split("data: ")[1].split("\r")[0]
                result = json.loads(data)
                tools = result.get("result", {}).get("tools", [])
                
                print_success(f"Found {len(tools)} tools")
                for tool in tools:
                    print(f"   - {tool['name']}")
            else:
                print_error(f"Server returned {response.status_code}")
                
            # Test 2: Search products
            print_info("\n2. Testing search_products...")
            response = await client.post(
                mcp_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "search_products",
                        "arguments": {"query": "chips"}
                    },
                    "id": 2
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
            )
            
            if response.status_code == 200:
                print_success("search_products working")
            else:
                print_error("search_products failed")
                
        print("\n[SUCCESS] MCP Server is healthy!")
        
    except Exception as e:
        if "ConnectError" in str(type(e)):
            print_error("Cannot connect to MCP Server at localhost:10999")
            print("[TIP] Make sure the server is running:")
            print("      python -m app server")
        else:
            print_error(f"Error: {e}")


@click.group()
def cli():
    """UCP Shopping Agent CLI"""
    pass


@cli.command()
@click.option("--session", "-s", default=None, help="Session ID (auto-generated if not provided)")
@click.option("--simple", is_flag=True, help="Use simple mode without executor")
def chat(session: Optional[str], simple: bool):
    """Start interactive chat with the shopping agent."""
    session_id = session or uuid4().hex
    if simple:
        asyncio.run(run_agent_chat_simple(session_id))
    else:
        asyncio.run(run_agent_chat_with_executor(session_id))


@cli.command()
def test():
    """Run a quick test of the agent system."""
    asyncio.run(run_test())


@cli.command()
def mcp():
    """Test MCP server connection."""
    asyncio.run(run_mcp_test())


@cli.command()
def server():
    """Start the MCP server."""
    print_header("Starting MCP Server")
    print("URL: http://localhost:10999")
    print("Press Ctrl+C to stop\n")
    
    import subprocess
    subprocess.run([
        sys.executable, "-c",
        "import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'sdk/python/src'); "
        "from backend.mcp_server.streamable_http_server import mcp; "
        "mcp.run(transport='streamable-http')"
    ])


if __name__ == "__main__":
    cli()