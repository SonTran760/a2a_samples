#!/usr/bin/env python3
"""
Simple test to check basic client functionality
"""

import asyncio
from uuid import uuid4
from a2a.client import ClientFactory
from a2a.types import Message, Part, Role


async def simple_test():
    print("Connecting to agent...")
    try:
        client = await ClientFactory.connect("http://localhost:10000")
        
        print("Creating message...")
        message = Message(
            role=Role.user,
            parts=[Part(kind="text", text="What time is it?")],
            messageId=uuid4().hex,
        )
        
        print("Sending message...")
        async for item in client.send_message(message):
            print(f"Received item type: {type(item)}")
            print(f"Received item: {item}")
            break  # Just test the first response
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(simple_test())