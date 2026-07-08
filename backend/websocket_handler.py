"""
WebSocket handler for the real-time chat widget.

Each web chat session opens a WebSocket and exchanges messages with the same
`process_customer_message` function that powers the phone channel, so the AI
behaves consistently across phone and web.
"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List
from .utils.logger import logger
from .call_flow import process_customer_message, get_conversation


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept a WebSocket connection."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected: {session_id}")
    
    def disconnect(self, session_id: str):
        """Remove a WebSocket connection."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected: {session_id}")
    
    async def send_personal_message(self, message: dict, session_id: str):
        """Send message to a specific connection."""
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to {session_id}: {str(e)}")
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connections."""
        for session_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {session_id}: {str(e)}")


manager = ConnectionManager()


async def websocket_chat_endpoint(websocket: WebSocket, session_id: str, business_id: str = "oc_elite_detailing"):
    """WebSocket endpoint for the chat widget.

    Maintains a persistent connection per chat window and proxies every customer
    message through `process_customer_message` so the AI behaves the same on web
    chat and phone.

    Args:
        websocket: WebSocket connection from the browser.
        session_id: Unique session id (one per chat window).
        business_id: Active business profile id (defaults to `oc_elite_detailing`).
    """
    await manager.connect(websocket, session_id)
    
    try:
        # Send welcome message
        await manager.send_personal_message({
            "type": "message",
            "text": "Hi — what vehicle are we helping you with today?",
            "role": "assistant"
        }, session_id)
        
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            if data.get("type") == "init":
                # Client initialized
                business_id = data.get("business_id", business_id)
                logger.info(f"Client initialized for business: {business_id}")
                continue
            
            if data.get("type") == "message":
                text = data.get("text", "")
                business_id = data.get("business_id", business_id)
                
                if not text:
                    continue
                
                logger.info(f"Received message from {session_id}: {text}")
                
                # Process message
                response = await process_customer_message(
                    text=text,
                    call_sid=session_id,
                    business_id=business_id
                )
                
                # Send response back
                await manager.send_personal_message({
                    "type": "message",
                    "text": response,
                    "role": "assistant"
                }, session_id)
            
    except WebSocketDisconnect:
        manager.disconnect(session_id)
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {str(e)}")
        manager.disconnect(session_id)


