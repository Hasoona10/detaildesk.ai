"""
FastAPI main application for the AI Detailing Receptionist.

Wires up all routes:
- Phone call endpoints (/api/twilio/voice/*)
- Web chat endpoints (/api/chat/*)
- Lead Inbox APIs (/api/leads, /api/business)
- Owner dashboard redirect (/owner/orders, /inbox)
- Widget assets (/widget/*)

This is the entry point for the entire backend.
"""
import os
from pathlib import Path
from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from dotenv import load_dotenv
import json

from .utils.logger import setup_logger, logger
from pathlib import Path

# Setup file logging for easier debugging
log_file = Path(__file__).parent.parent / "server.log"
logger = setup_logger(log_file=log_file)
from .twilio_handler import handle_incoming_call, handle_voice_input, handle_call_status
from .twilio_sms_handler import handle_incoming_sms
from .rag import RAGSystem, get_rag_system
from .call_flow import TURN_LOG_PATH, BUSINESS_DATA
from .lead_store import list_leads, get_lead, update_lead_status, VALID_STATUSES

# Load environment variables
load_dotenv()

# Initialize FastAPI app
# DEMO: This creates the FastAPI application - it's a modern Python web framework
# that's super fast and has automatic API documentation
app = FastAPI(
    title="AI Detailing Receptionist API",
    description="AI missed-call assistant for auto detailers — captures leads, answers questions, and texts the owner.",
    version="1.0.0",
)

DEFAULT_BUSINESS_ID = BUSINESS_DATA.get("business_id", "oc_elite_detailing")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to bypass ngrok browser warning for Twilio webhooks
@app.middleware("http")
async def bypass_ngrok_warning(request: Request, call_next):
    """Bypass ngrok browser warning for API requests."""
    response = await call_next(request)
    # Add header to bypass ngrok warning (works for some ngrok versions)
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting AI Detailing Receptionist API...")

    # Load business data and initialize RAG
    business_id = os.getenv("DEFAULT_BUSINESS_ID", DEFAULT_BUSINESS_ID)
    business_data_path = Path(__file__).parent / "business_data.json"
    
    if business_data_path.exists():
        # Use the new chunking and seeding system
        try:
            from .rag import seed_vectordb
            
            # Check if vector DB is already seeded (has documents)
            rag = get_rag_system(business_id)
            collection_count = rag.collection.count()
            
            if collection_count == 0:
                logger.info("Vector database is empty, seeding from business_data.json...")
                try:
                    seed_vectordb(business_data_path, business_id, clear_existing=False)
                except Exception as e:
                    logger.warning(f"Could not seed vector database (may be quota issue): {str(e)}")
                    logger.info("Server will continue without RAG seeding - phone calls will still work")
            else:
                logger.info(f"Vector database already seeded ({collection_count} documents)")
                # Optionally re-seed if data has changed (uncomment if needed)
                # seed_vectordb(business_data_path, business_id, clear_existing=True)
        
        except Exception as e:
            logger.warning(f"Error seeding RAG with new system, falling back to old method: {str(e)}")
            # Fallback to old method
            with open(business_data_path, 'r') as f:
                business_data = json.load(f)
            
            # Initialize RAG system
            rag = get_rag_system(business_id)
            
            # Convert business data to documents for RAG (old method)
            documents = []
            # Check if business_data is a dict with business_id key (old format) or direct dict (new format)
            if business_id in business_data:
                biz = business_data[business_id]
            else:
                biz = business_data  # New format
            
            # Hours document
            hours = biz.get("hours", {})
            if hours:
                if isinstance(list(hours.values())[0], dict):
                    # Old format: {"monday": {"open": "11:00", "close": "22:00"}}
                    hours_text = "Business Hours:\n"
                    for day, times in hours.items():
                        hours_text += f"{day.capitalize()}: {times.get('open')} - {times.get('close')}\n"
                else:
                    # New format: {"monday": "11:00 am – 9:00 pm"}
                    hours_text = "Business Hours:\n"
                    for day, time in hours.items():
                        hours_text += f"{day.capitalize()}: {time}\n"
                documents.append({"text": hours_text, "metadata": {"type": "hours"}})
            
            # Menu document
            menu_sections = biz.get("menu_sections", biz.get("menu", {}))
            if menu_sections:
                menu_text = "Menu:\n"
                if isinstance(menu_sections, list):
                    # New format: list of menu sections
                    for section in menu_sections:
                        menu_text += f"\n{section.get('name', '')}:\n"
                        for item in section.get("items", []):
                            price = item.get("price", "")
                            if isinstance(price, (int, float)):
                                price = f"${price:.2f}"
                            menu_text += f"- {item.get('name')}: {price} - {item.get('description')}\n"
                else:
                    # Old format: dict of categories
                    for category, items in menu_sections.items():
                        menu_text += f"\n{category.capitalize()}:\n"
                        for item in items:
                            menu_text += f"- {item.get('name')}: {item.get('price')} - {item.get('description')}\n"
                documents.append({"text": menu_text, "metadata": {"type": "menu"}})
            
            # Address document
            address = biz.get("address", {})
            if isinstance(address, dict):
                addr = address
                address_text = f"Address: {addr.get('street', '')}, {addr.get('city', '')}, {addr.get('state', '')} {addr.get('zip', '')}. Phone: {addr.get('phone', '')}"
            else:
                address_text = f"Address: {address}"
            documents.append({"text": address_text, "metadata": {"type": "contact"}})
            
            # Description
            desc_text = biz.get("description", "")
            if desc_text:
                documents.append({"text": desc_text, "metadata": {"type": "description"}})
            
            # Add documents to RAG
            if documents:
                try:
                    rag.add_documents(documents)
                    logger.info(f"Initialized RAG with {len(documents)} documents for business {business_id}")
                except Exception as e:
                    logger.warning(f"Could not add documents to RAG (may be quota issue): {str(e)}")
                    logger.info("Server will continue - phone calls will still work with basic responses")
        
    else:
        logger.warning(f"Business data file not found: {business_data_path}")
        logger.info("  → Run 'python scripts/seed_data.py' to seed the database")
    
    logger.info("AI Receptionist API started successfully")


@app.get("/")
async def root():
    """Root endpoint - serves the website."""
    website_path = Path(__file__).parent.parent / "website" / "index.html"
    if website_path.exists():
        with open(website_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return {
        "message": "AI Receptionist API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/website")
async def website():
    """Serve the main website."""
    website_path = Path(__file__).parent.parent / "website" / "index.html"
    if website_path.exists():
        with open(website_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return {"error": "Website not found"}


@app.get("/website/styles.css")
async def website_css():
    """Serve website CSS."""
    css_path = Path(__file__).parent.parent / "website" / "styles.css"
    if css_path.exists():
        with open(css_path, 'r', encoding='utf-8') as f:
            return Response(content=f.read(), media_type="text/css")
    return {"error": "CSS not found"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/owner/orders", response_class=HTMLResponse)
async def owner_orders():
    redirect_target = os.getenv("OWNER_DASHBOARD_URL", 'http://localhost:3002/inbox')
    return RedirectResponse(url=redirect_target, status_code=307)


@app.get("/inbox")
async def inbox_redirect():
    redirect_target = os.getenv("OWNER_DASHBOARD_URL", 'http://localhost:3002/inbox')
    return RedirectResponse(url=redirect_target, status_code=307)


@app.get("/_legacy/kitchen", response_class=HTMLResponse)
async def _legacy_kitchen_orders():
    """Legacy restaurant kitchen view - kept as a stub so old links don't 404."""
    return HTMLResponse(
        "<h1>Kitchen view retired</h1>"
        "<p>This product is now an AI receptionist for auto detailers. "
        "See the Lead Inbox in the owner dashboard.</p>"
    )


# ============================================================================
# Phone Call System - API Endpoints
# ============================================================================
# These endpoints handle incoming phone calls from Twilio
@app.post("/api/twilio/voice/incoming")
async def twilio_incoming(request: Request):
    """
    Handle incoming Twilio calls.
    
    Called when someone calls the shop's Twilio number. We respond with TwiML
    to start the detailing receptionist conversation.
    """
    return await handle_incoming_call(request)


@app.post("/api/twilio/voice/process")
async def twilio_process(request: Request):
    """
    Process voice input from Twilio.
    
    DEMO: This processes what the customer said! It takes the speech-to-text result,
    runs it through the AI system, and returns a response that Twilio converts to speech.
    """
    return await handle_voice_input(request)


@app.post("/api/twilio/voice/status")
async def twilio_status(request: Request):
    """
    Handle Twilio call status updates.
    
    This is called when a call ends - we clean up the conversation state.
    """
    return await handle_call_status(request)


@app.post("/api/twilio/sms/incoming")
async def twilio_sms_incoming(request: Request):
    """Handle inbound SMS from a customer.

    Twilio sends this webhook when someone texts the shop's number. We process
    the message through the same conversation engine as the phone/web channels
    and respond with TwiML so Twilio delivers the reply by SMS.

    Twilio console setup:
      Phone Numbers → your number → Messaging → "A MESSAGE COMES IN" → webhook
      → POST https://<your-domain>/api/twilio/sms/incoming
    """
    return await handle_incoming_sms(request)


# ============================================================================
# DEMO SECTION: Web Chat Widget - API Endpoints
# ============================================================================
@app.post("/api/chat/message")
async def chat_message(request: Request):
    """
    Handle chat message via HTTP (fallback).
    
    DEMO: This handles chat messages sent via HTTP (non-WebSocket).
    The web chat widget can use this as a fallback if WebSocket isn't available.
    It uses the same process_customer_message function as phone calls!
    """
    try:
        from .call_flow import process_customer_message
        data = await request.json()
        text = data.get("text", "")
        business_id = data.get("business_id", DEFAULT_BUSINESS_ID)

        # Use a session ID for web chat (different from call SID)
        session_id = request.headers.get("X-Session-ID", "web_session_default")

        response = await process_customer_message(text, session_id, business_id)

        return JSONResponse({"response": response})
        
    except Exception as e:
        logger.error(f"Error handling chat message: {str(e)}")
        return JSONResponse({"error": "Internal server error"}, status_code=500)


@app.websocket("/api/chat/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time chat.
    
    DEMO: This is the WebSocket endpoint for the chat widget! It maintains a persistent
    connection so messages can be sent back and forth in real-time. Much better than
    polling HTTP requests.
    """
    from .websocket_handler import websocket_chat_endpoint
    import uuid
    
    session_id = f"ws_{uuid.uuid4().hex[:12]}"
    business_id = DEFAULT_BUSINESS_ID

    await websocket_chat_endpoint(websocket, session_id, business_id)


# ============================================================================
# DEMO SECTION: Web Chat Widget - Static Assets
# ============================================================================
# These endpoints serve the widget files that websites can embed
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

@app.get("/widget/widget.js")
async def serve_widget_js():
    """
    Serve widget JavaScript.
    
    DEMO: This serves the JavaScript file for the chat widget. Websites can include
    this script tag to add the chat widget to their page.
    """
    widget_path = Path(__file__).parent.parent / "widget" / "widget.js"
    return FileResponse(widget_path)


@app.get("/widget/widget.css")
async def serve_widget_css():
    """
    Serve widget CSS.
    
    DEMO: This serves the CSS styling for the chat widget.
    """
    css_path = Path(__file__).parent.parent / "widget" / "widget.css"
    return FileResponse(css_path)



# ============================================================================
# Lead Inbox APIs (used by the Next.js owner dashboard)
# ============================================================================


@app.get("/api/leads")
async def api_list_leads(business_id: str | None = None):
    """Return all leads (newest first) for the dashboard inbox."""
    try:
        return list_leads(business_id or DEFAULT_BUSINESS_ID)
    except Exception as e:
        logger.error(f"Error listing leads: {e}")
        return JSONResponse({"error": "failed to list leads"}, status_code=500)


@app.get("/api/leads/{lead_id}")
async def api_get_lead(lead_id: str):
    lead = get_lead(lead_id)
    if not lead:
        return JSONResponse({"error": "lead not found"}, status_code=404)
    return lead


@app.post("/api/leads/{lead_id}/status")
async def api_update_lead_status(lead_id: str, request: Request):
    """Update the status of a lead (new | contacted | booked | lost | resolved)."""
    try:
        data = await request.json()
        status = (data.get("status") or "").strip()
        if status not in VALID_STATUSES:
            return JSONResponse(
                {"error": f"invalid status. Must be one of {sorted(VALID_STATUSES)}"},
                status_code=400,
            )
        updated = update_lead_status(lead_id, status)
        if updated is None:
            return JSONResponse({"error": "lead not found"}, status_code=404)
        return updated
    except Exception as e:
        logger.error(f"Error updating lead status: {e}")
        return JSONResponse({"error": "failed to update lead"}, status_code=500)


@app.get("/api/business")
async def api_get_business():
    """Return the active business profile (read-only for MVP)."""
    return BUSINESS_DATA


# Backwards-compatible alias so old dashboard builds keep working until they
# switch to /api/leads. Returns the per-turn log (newest first).
@app.get("/api/owner/orders")
async def owner_orders_json():
    try:
        if TURN_LOG_PATH.exists():
            with TURN_LOG_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return list(reversed(data))
        return []
    except Exception as e:
        logger.error(f"Error reading turn log: {e}")
        return JSONResponse({"error": "failed to read turn log"}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

