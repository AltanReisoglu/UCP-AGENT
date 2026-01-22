# Copyright 2026 UCP Authors
# Single command launcher for UCP-AGENT system

"""
UCP-AGENT Unified Launcher

Usage:
    python run.py

This script:
1. Starts the MCP server in background
2. Opens agent chat interface
"""

import subprocess
import sys
import os
import time
import threading
import atexit

# Server process reference
server_process = None

def start_server():
    """Start MCP server in background."""
    global server_process
    
    print("[*] Starting MCP Server...")
    
    # Prepare environment with SDK path
    env = os.environ.copy()
    env['PYTHONPATH'] = f".;sdk/python/src;{env.get('PYTHONPATH', '')}"
    
    server_process = subprocess.Popen(
        [sys.executable, "-m", "backend.mcp_server.streamable_http_server"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    )
    
    # Wait for server to start
    time.sleep(2)
    
    if server_process.poll() is None:
        print("[OK] MCP Server started on http://localhost:10999")
        return True
    else:
        print("[ERROR] Failed to start MCP Server")
        return False

def stop_server():
    """Stop the MCP server."""
    global server_process
    if server_process:
        print("\n[*] Stopping MCP Server...")
        server_process.terminate()
        server_process.wait(timeout=5)
        print("[OK] Server stopped")

def run_agent():
    """Run agent chat."""
    print("[*] Starting Agent Chat...\n")
    print("=" * 50)
    print("  UCP Shopping Agent")
    print("  Type your message and press Enter")
    print("  Type 'quit' to exit")
    print("=" * 50 + "\n")
    
    # Prepare environment
    env = os.environ.copy()
    env['PYTHONPATH'] = f".;sdk/python/src;{env.get('PYTHONPATH', '')}"
    
    # Run agent chat
    subprocess.run(
        [sys.executable, "-m", "app", "chat", "--simple"],
        env=env
    )

def main():
    print("\n" + "=" * 50)
    print("  UCP-AGENT System Launcher")
    print("=" * 50 + "\n")
    
    # Register cleanup
    atexit.register(stop_server)
    
    # Start server
    if not start_server():
        print("[ERROR] Cannot start server. Check if port 10999 is available.")
        return
    
    print()
    
    try:
        # Run agent
        run_agent()
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted")
    finally:
        stop_server()

if __name__ == "__main__":
    main()
