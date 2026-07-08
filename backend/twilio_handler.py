"""
Twilio webhook handlers for inbound phone calls.

When a customer calls the shop's Twilio number we greet them, gather speech,
run it through the conversation flow (intent classification + lead extraction),
and respond using Twilio's neural TTS. The same `process_customer_message`
function backs the chat widget, so behavior is consistent across channels.
"""
from fastapi import Request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from .utils.logger import logger
from .call_flow import process_customer_message, clear_conversation, BUSINESS_DATA

DEFAULT_BUSINESS_ID = BUSINESS_DATA.get("business_id", "oc_elite_detailing")
GREETING = (
    f"Thanks for calling {BUSINESS_DATA.get('business_name', 'our shop')}. "
    "How can we help with your vehicle today?"
)


async def handle_incoming_call(request: Request) -> Response:
    """Handle an inbound Twilio call.

    Greets the customer, starts gathering speech, and returns the TwiML that
    drives the call. Subsequent speech results hit `handle_voice_input`.
    """
    try:
        # Try to get form data
        try:
            form_data = await request.form()
        except Exception as form_error:
            logger.error(f"Error getting form data: {str(form_error)}")
            raise

        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From")

        logger.info(f"Incoming call - SID: {call_sid}, From: {from_number}")

        # Build absolute URL for the action using request headers
        host = request.headers.get("host", "example.trycloudflare.com")
        scheme = "https"  # Cloudflare Tunnel always uses HTTPS
        base_url = f"{scheme}://{host}"
        process_url = f"{base_url}/api/twilio/voice/process"
        logger.info(f"Using action URL: {process_url}")

        # Create TwiML response
        response = VoiceResponse()

        response.say(GREETING, voice="Polly.Joanna")
        response.pause(length=1)

        gather = Gather(
            input="speech",
            action=process_url,
            method="POST",
            speech_timeout="auto",
            language="en-US",
            hints=(
                "detail, ceramic coating, paint correction, swirl marks, "
                "interior, exterior, full detail, maintenance wash, "
                "mobile, appointment, quote, Tesla, BMW, truck"
            ),
        )
        response.append(gather)

        # If no input, say goodbye and hang up
        response.say(
            "I didn't catch that. Please call back when you're ready. Goodbye!",
            voice="Polly.Joanna",
        )
        response.hangup()

        twiml = str(response)
        logger.info(f"Generated TwiML: {twiml[:200]}...")

        return Response(content=twiml, media_type="application/xml")

    except Exception as e:
        import traceback
        import sys

        error_trace = traceback.format_exc()

        # Force print to stderr (always visible)
        sys.stderr.write(f"\n{'='*60}\n")
        sys.stderr.write("ERROR in handle_incoming_call:\n")
        sys.stderr.write(f"Error: {str(e)}\n")
        sys.stderr.write(f"Error Type: {type(e).__name__}\n")
        sys.stderr.write("Traceback:\n")
        sys.stderr.write(f"{error_trace}\n")
        sys.stderr.write(f"{'='*60}\n\n")
        sys.stderr.flush()

        # Also print to stdout
        print(f"\n{'='*60}", flush=True)
        print("ERROR in handle_incoming_call:", flush=True)
        print(f"Error: {str(e)}", flush=True)
        print(f"Error Type: {type(e).__name__}", flush=True)
        print(f"Traceback:\n{error_trace}", flush=True)
        print(f"{'='*60}\n", flush=True)

        try:
            logger.error(f"Error handling incoming call: {str(e)}\n{error_trace}")
        except Exception as log_err:
            sys.stderr.write(f"Logger also failed: {str(log_err)}\n")
            sys.stderr.flush()

        # Create a simple error response
        response = VoiceResponse()
        response.say(
            "I'm sorry, there was an error. Please try calling again later.",
            voice="Polly.Joanna",
        )
        response.hangup()

        twiml = str(response)
        try:
            logger.info(f"Error TwiML: {twiml}")
        except Exception:
            pass

        return Response(content=twiml, media_type="application/xml")


async def handle_voice_input(request: Request) -> Response:
    """
    Process voice input from Twilio.
    
    DEMO: This processes what the customer said! It takes the speech-to-text result,
    sends it through the AI system (ML intent classification + RAG), and generates
    a response that gets converted back to speech. This is the main conversation loop!
    
    Args:
        request: FastAPI request object (contains the transcribed speech)
        
    Returns:
        TwiML response with generated speech (the AI's response)
    """
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        speech_result = form_data.get("SpeechResult")

        logger.info(f"Processing voice input for call {call_sid}: {speech_result}")

        if not speech_result:
            # If no speech detected, prompt again using the same neural voice
            host = request.headers.get("host", "example.trycloudflare.com")
            scheme = "https"
            base_url = f"{scheme}://{host}"
            process_url = f"{base_url}/api/twilio/voice/process"

            response = VoiceResponse()
            response.say(
                "I didn't catch that. Could you please repeat?",
                voice="Polly.Joanna",
            )
            gather = Gather(
                input="speech",
                action=process_url,
                method="POST",
                speech_timeout="auto",
                language="en-US",
            )
            response.append(gather)
            response.hangup()
            return Response(content=str(response), media_type="application/xml")
        ai_response = await process_customer_message(
            text=speech_result,
            call_sid=call_sid,
            business_id=DEFAULT_BUSINESS_ID,
        )

        twiml_response = VoiceResponse()
        twiml_response.say(ai_response, voice="Polly.Joanna")

        # Continue gathering input
        host = request.headers.get("host", "example.trycloudflare.com")
        scheme = "https"
        base_url = f"{scheme}://{host}"
        process_url = f"{base_url}/api/twilio/voice/process"
        
        gather = Gather(
            input="speech",
            action=process_url,
            method="POST",
            speech_timeout="auto",
            language="en-US"
        )
        twiml_response.append(gather)
        
        # Fallback if no input
        twiml_response.say("Thank you for calling. Have a great day!")
        twiml_response.hangup()
        
        return Response(content=str(twiml_response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error processing voice input: {str(e)}")
        response = VoiceResponse()
        response.say("I'm sorry, I encountered an error. Please try again.")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")


async def handle_call_status(request: Request):
    """
    Handle call status updates (e.g., call ended).
    
    Args:
        request: FastAPI request object
    """
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        call_status = form_data.get("CallStatus")
        
        logger.info(f"Call status update - SID: {call_sid}, Status: {call_status}")
        
        if call_status == "completed":
            # Clear conversation state when call ends
            clear_conversation(call_sid)
            
        return Response(content="OK", status_code=200)
        
    except Exception as e:
        logger.error(f"Error handling call status: {str(e)}")
        return Response(content="Error", status_code=500)


