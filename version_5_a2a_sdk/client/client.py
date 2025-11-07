# =============================================================================
# client/client.py
# =============================================================================
# Purpose:
# This file defines a dynamic async client built on top of the official
# A2A Python SDK. It can:
# - Detect agent capabilities (streaming or not)
# - Send queries in a loop
# - Handle single-turn or multi-turn conversations
# - Automatically pick between streaming and non-streaming flows
# =============================================================================

# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------
import asyncio                      # Provides support for asynchronous programming and I/O operations
import json                         # Allows encoding and decoding JSON data
import traceback                    # Prints detailed tracebacks in case of errors
from uuid import uuid4              # Generates unique message IDs
from typing import Any              # Allows function arguments and variables to accept any type

import click                        # Library to easily create command-line interfaces
import httpx                        # Async HTTP client for sending requests to agents
from rich import print as rprint    # Enhanced print function to support colors and formatting
from rich.syntax import Syntax      # Used to highlight JSON output in the terminal

# Import the official A2A SDK client and related types
from a2a.client import ClientFactory, Client
from a2a.types import (
    AgentCard,                      # Metadata about the agent
    Message,                        # Message type for sending
    Part,                           # Message parts
    Role,                           # Message roles
    Task,                           # Task object representing the agent's work unit
    TaskState,                      # Enum describing current task state (working, complete, etc.)
)

# -----------------------------------------------------------------------------
# Helper: Create a message in expected A2A format
# -----------------------------------------------------------------------------
def build_message(text: str, task_id: str | None = None, context_id: str | None = None) -> Message:
    # Constructs a Message object that matches A2A message format
    return Message(
        role=Role.user,  # The role of the message sender
        parts=[Part(kind="text", text=text)],  # The actual message content
        messageId=uuid4().hex,  # Unique message ID for tracking
        taskId=task_id if task_id else None,  # Include taskId only if it's a follow-up
        contextId=context_id if context_id else None,  # Include contextId for continuity
    )

# -----------------------------------------------------------------------------
# Helper: Pretty print JSON objects using syntax coloring
# -----------------------------------------------------------------------------
def print_json_response(response: Any, title: str) -> None:
    # Displays a formatted and color-highlighted view of the response
    print(f"\n=== {title} ===")  # Section title for clarity
    try:
        # Handle different response types
        if hasattr(response, "root"):  # Check if response is wrapped by SDK
            data = response.root.model_dump(mode="json", exclude_none=True)
        elif hasattr(response, "model_dump"):  # Check if it's a Pydantic model
            data = response.model_dump(mode="json", exclude_none=True)
        else:
            # Already a regular dictionary or other JSON-serializable object
            data = response

        json_str = json.dumps(data, indent=2, ensure_ascii=False)  # Convert dict to pretty JSON string
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)  # Apply syntax highlighting
        rprint(syntax)  # Print it with color
    except Exception as e:
        # Print fallback text if something fails
        rprint(f"[red bold]Error printing JSON:[/red bold] {e}")
        rprint(repr(response))

# -----------------------------------------------------------------------------
# Handle sending a message and processing the response (unified streaming/non-streaming)
# -----------------------------------------------------------------------------
async def handle_message(client: Client, text: str, task_id: str | None = None, context_id: str | None = None):
    # Build and send the message
    message = build_message(text, task_id, context_id)
    
    # Send message and process responses
    try:
        response_count = 0
        async for item in client.send_message(message):
            response_count += 1
            if isinstance(item, tuple):
                # This is a (Task, Update) tuple for streaming updates
                task, update = item
                # Convert Pydantic models to dictionaries for JSON serialization
                task_dict = task.model_dump(mode="json", exclude_none=True) if hasattr(task, "model_dump") else task
                update_dict = update.model_dump(mode="json", exclude_none=True) if hasattr(update, "model_dump") else update
                print_json_response({"task": task_dict, "update": update_dict}, "Streaming Update")
                
                # Check if input is required
                if task.status.state == TaskState.input_required:
                    follow_up = input("\U0001F7E1 Agent needs more input. Your reply: ")
                    await handle_message(client, follow_up, task.id, task.context_id)
            else:
                # This is a Message response for non-streaming
                print_json_response(item, "Agent Reply")
        
        if response_count == 0:
            print("⚠️  No response received from agent")
            
    except RuntimeError as e:
        if "StopAsyncIteration" in str(e):
            print("⚠️  Agent connection ended unexpectedly. Please check if the agent is running correctly.")
        else:
            raise e

# -----------------------------------------------------------------------------
# Loop for querying the agent repeatedly
# -----------------------------------------------------------------------------
async def interactive_loop(client: Client, supports_streaming: bool):
    print("\nEnter your query below. Type 'exit' to quit.")  # Print instructions for user
    while True:
        query = input("\n\U0001F7E2 Your query: ").strip()  # Get user input
        if query.lower() in {"exit", "quit"}:
            print("\U0001F44B Exiting...")  # Say goodbye
            break
        
        await handle_message(client, query)

# -----------------------------------------------------------------------------
# Command-line entry point
# -----------------------------------------------------------------------------
@click.command()
@click.option("--agent-url", default="http://localhost:10000", help="URL of the A2A agent to connect to")
def main(agent_url: str):
    asyncio.run(run_main(agent_url))  # Launch async event loop with provided agent URL

# -----------------------------------------------------------------------------
# Async runner: sets up client, agent card, and launches the loop
# -----------------------------------------------------------------------------
async def run_main(agent_url: str):
    print(f"Connecting to agent at {agent_url}...")  # Let user know we're starting connection
    try:
        # Use ClientFactory to connect to the agent
        client = await ClientFactory.connect(agent_url)  # Create A2A client
        
        rprint(f"[green bold]✅ Connected to {agent_url}")  # Confirm success
        await interactive_loop(client, True)  # Start conversation loop (streaming support is auto-detected)

    except Exception:
        traceback.print_exc()  # Show full error trace
        print("❌ Failed to connect or run. Ensure the agent is live and reachable.")  # Friendly error message

# -----------------------------------------------------------------------------
# Execute main only when run as script
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    main()  # Run main CLI logic
