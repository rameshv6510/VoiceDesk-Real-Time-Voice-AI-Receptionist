"""FastAPI application entrypoint and WebRTC signaling endpoints."""
import os
import sys
import uuid
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

# Ensure workspace root is in sys.path and PYTHONPATH when running `python app/main.py` directly
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(root_dir) not in os.environ.get("PYTHONPATH", ""):
    os.environ["PYTHONPATH"] = str(root_dir) + os.pathsep + os.environ.get("PYTHONPATH", "")

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.config import settings, clinic_config
from app.pipeline.runner import VoiceDeskPipeline

from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection, IceServer
from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCRequestHandler,
    SmallWebRTCRequest,
    SmallWebRTCPatchRequest,
)
from pipecat.transports.base_transport import TransportParams
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams

# SmallWebRTC Request Handler
webrtc_handler = SmallWebRTCRequestHandler(
    ice_servers=[IceServer(urls="stun:stun.l.google.com:19302")]
)

# Active call sessions
active_sessions = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    clinic_name = clinic_config.get("clinic", {}).get("name", "VoiceDesk Clinic")
    logger.info(f"Starting VoiceDesk Server for {clinic_name} on {settings.HOST}:{settings.PORT}")
    from app.db import seed_clinic_data_if_needed
    from app.rag import initialize_knowledge_base
    seed_clinic_data_if_needed()
    initialize_knowledge_base()
    yield
    await webrtc_handler.close()
    logger.info("Shutting down VoiceDesk Server.")

app = FastAPI(
    title="VoiceDesk AI Receptionist",
    description="Real-time Voice AI Receptionist for Small Clinics",
    version="1.0.0",
    lifespan=lifespan
)

# Static client files
static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_client():
    index_file = static_dir / "client" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return "<h1>VoiceDesk Web Client Not Found</h1>"

@app.get("/api/health")
async def health_check():
    has_llm = bool(
        (settings.GROQ_API_KEY and not settings.GROQ_API_KEY.startswith("your_"))
        or (settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("your_"))
    )
    has_stt_tts = bool(
        settings.DEEPGRAM_API_KEY and not settings.DEEPGRAM_API_KEY.startswith("your_")
    )
    active_llm_provider = "groq" if (settings.LLM_PROVIDER.lower() == "groq" or (settings.GROQ_API_KEY and not settings.OPENAI_API_KEY)) else "openai"
    return {
        "status": "healthy",
        "clinic": clinic_config.get("clinic", {}).get("name"),
        "api_keys_configured": bool(has_llm and has_stt_tts),
        "llm_provider": active_llm_provider,
        "stt_provider": settings.STT_PROVIDER,
        "tts_provider": settings.TTS_PROVIDER,
        "active_calls": len(active_sessions)
    }

@app.post("/api/offer")
async def handle_webrtc_offer(request: Request):
    """Handles browser WebRTC SDP offer and spawns a new Pipecat voice pipeline session."""
    data = await request.json()
    if not data.get("sdp"):
        raise HTTPException(status_code=400, detail="Missing SDP offer in request")

    # Check for valid API keys (Support 100% Zero-Cost Groq or OpenAI)
    has_llm = bool(
        (settings.GROQ_API_KEY and not settings.GROQ_API_KEY.startswith("your_"))
        or (settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("your_"))
    )
    has_deepgram = bool(
        settings.DEEPGRAM_API_KEY and not settings.DEEPGRAM_API_KEY.startswith("your_")
    )

    if not has_llm or not has_deepgram:
        missing = []
        if not has_llm:
            missing.append("GROQ_API_KEY (Free, no credit card) or OPENAI_API_KEY")
        if not has_deepgram:
            missing.append("DEEPGRAM_API_KEY ($200 free credit, no credit card)")
        raise HTTPException(
            status_code=400,
            detail=f"API Keys Missing: Please add {', '.join(missing)} to your .env file."
        )

    try:
        webrtc_request = SmallWebRTCRequest.from_dict(data)

        async def webrtc_connection_callback(connection: SmallWebRTCConnection):
            session_id = connection.pc_id
            logger.info(f"Connecting SmallWebRTCTransport for session {session_id}")
            transport = SmallWebRTCTransport(
                webrtc_connection=connection,
                params=TransportParams(
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                    vad_enabled=True,
                    vad_analyzer=SileroVADAnalyzer(
                        params=VADParams(
                            confidence=0.7,
                            start_secs=0.35,
                            stop_secs=0.8,
                            min_volume=0.4,
                        )
                    ),
                    vad_audio_passthrough=True,
                )
            )
            pipeline = VoiceDeskPipeline(transport=transport, session_id=session_id)
            active_sessions[session_id] = pipeline
            asyncio.create_task(pipeline.build_and_run())

        answer = await webrtc_handler.handle_web_request(
            request=webrtc_request,
            webrtc_connection_callback=webrtc_connection_callback
        )
        return JSONResponse(answer)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling WebRTC offer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/offer")
async def handle_webrtc_patch(request: Request):
    """Handles trickle ICE candidates."""
    data = await request.json()
    try:
        if "pc_id" in data and "candidates" in data:
            patch_req = SmallWebRTCPatchRequest(
                pc_id=data["pc_id"],
                candidates=data["candidates"]
            )
            await webrtc_handler.handle_patch_request(patch_req)
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.error(f"Error handling ICE patch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
