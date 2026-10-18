"""Voice pipeline runner with WebRTC transport, STT, LLM, TTS, VAD, and Latency Metrics."""
import os
import asyncio
from typing import Optional, Dict, Any
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_response import (
    LLMAssistantResponseAggregator,
    LLMUserResponseAggregator,
)
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.services.openai.llm import OpenAILLMService
import base64
import json
from pipecat.transports.base_transport import TransportParams
from pipecat.frames.frames import (
    EndFrame,
    LLMMessagesFrame,
    TextFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
)

from app.config import settings, clinic_config
from app.db import seed_clinic_data_if_needed
from app.rag import initialize_knowledge_base
from app.pipeline.prompts import generate_system_prompt
from app.pipeline.metrics import TurnLatencyTracker
from app.tools import ALL_VOICE_TOOLS, register_all_tools

# Defensive fix for Python 3.10 Enum stringification and sample_rate in DeepgramSTTService
_orig_dg_build_kwargs = DeepgramSTTService._build_connect_kwargs

def _safe_dg_build_kwargs(self):
    kwargs = _orig_dg_build_kwargs(self)
    if "language" in kwargs and hasattr(self._settings.language, "value"):
        kwargs["language"] = self._settings.language.value
    elif "language" in kwargs and str(kwargs["language"]).startswith("Language."):
        kwargs["language"] = str(kwargs["language"]).split(".", 1)[-1].lower()
    if kwargs.get("sample_rate") in ("0", 0, None):
        kwargs["sample_rate"] = "16000"
    if str(kwargs.get("model", "")).startswith("nova-3"):
        kwargs.pop("keywords", None)
    return kwargs

DeepgramSTTService._build_connect_kwargs = _safe_dg_build_kwargs

class ReliableSarvamTTSService(SarvamTTSService):
    """Low-latency Sarvam TTS that never drops frames when context is cleaned up."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_context_id: Optional[str] = None

    async def run_tts(self, text: str, context_id: str):
        self._last_context_id = context_id
        async for frame in super().run_tts(text, context_id):
            yield frame

    async def _receive_messages(self):
        """Receive and push audio without dropping frames."""
        async for message in self._get_websocket():
            if isinstance(message, str):
                try:
                    msg = json.loads(message)
                except Exception:
                    continue
                context_id = self.get_active_audio_context_id() or self._last_context_id or getattr(self, "_turn_context_id", None)
                if msg.get("type") == "audio":
                    await self.stop_ttfb_metrics()
                    audio = base64.b64decode(msg["data"]["audio"])
                    frame = TTSAudioRawFrame(audio, self.sample_rate, 1, context_id=context_id)
                    if context_id and self.audio_context_available(context_id):
                        await self.append_to_audio_context(context_id, frame)
                    else:
                        await self.push_frame(frame)
                elif msg.get("type") == "error":
                    error_msg = msg.get("data", {}).get("message", "Unknown error")
                    logger.warning(f"Sarvam TTS Error: {error_msg}")

class VoiceDeskPipeline:
    """Manages the lifecycle of a real-time voice receptionist call session."""

    def __init__(self, transport, session_id: str):
        self.transport = transport
        self.session_id = session_id
        self.latency_tracker = TurnLatencyTracker(session_id=session_id)
        self.task: Optional[PipelineTask] = None
        self.runner: Optional[PipelineRunner] = None

    async def build_and_run(self):
        logger.info(f"Building VoiceDesk pipeline for session: {self.session_id}")

        # 1. Speech-to-Text (STT)
        stt_settings_kwargs = {
            "model": settings.DEEPGRAM_STT_MODEL,
            "language": settings.DEEPGRAM_STT_LANGUAGE,
        }
        if not settings.DEEPGRAM_STT_MODEL.startswith("nova-3"):
            stt_settings_kwargs["keywords"] = [
                "namaskara:2", "Indiranagar:2", "SmileCare:2", "Ananya:2", "Vikram:2",
                "cleaning:2", "checkup:2", "root canal:2", "dantada:2", "hallu:2",
                "novvu:2", "yelli:2", "ideya:2", "beku:2", "appointment:2", "cancel:2"
            ]

        stt = DeepgramSTTService(
            api_key=settings.DEEPGRAM_API_KEY,
            sample_rate=16000,
            settings=DeepgramSTTService.Settings(**stt_settings_kwargs)
        )

        # 2. LLM Brain & Tools
        system_prompt = generate_system_prompt(clinic_config)
        if settings.LLM_PROVIDER.lower() == "groq" or (settings.GROQ_API_KEY and not settings.OPENAI_API_KEY):
            logger.info(f"Using Groq LLM (zero cost): {settings.GROQ_MODEL}")
            llm = OpenAILLMService(
                api_key=settings.GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1",
                settings=OpenAILLMService.Settings(model=settings.GROQ_MODEL),
            )
        else:
            logger.info(f"Using OpenAI LLM: {settings.OPENAI_MODEL}")
            llm = OpenAILLMService(
                api_key=settings.OPENAI_API_KEY,
                settings=OpenAILLMService.Settings(model=settings.OPENAI_MODEL),
            )
        register_all_tools(llm)

        # Conversation context with tools
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        context = OpenAILLMContext(messages, tools=ALL_VOICE_TOOLS)
        context_aggregator = llm.create_context_aggregator(context)

        # 3. Text-to-Speech (TTS)
        if settings.TTS_PROVIDER.lower() == "sarvam" or (settings.SARVAM_API_KEY and settings.TTS_PROVIDER.lower() != "deepgram"):
            logger.info(f"Using Sarvam AI TTS (Native Indian Voice: {settings.SARVAM_TTS_VOICE}, Language: {settings.SARVAM_TTS_LANGUAGE})")
            tts = ReliableSarvamTTSService(
                api_key=settings.SARVAM_API_KEY,
                sample_rate=16000,
                settings=SarvamTTSService.Settings(
                    model=settings.SARVAM_TTS_MODEL,
                    voice=settings.SARVAM_TTS_VOICE,
                    language=settings.SARVAM_TTS_LANGUAGE,
                    min_buffer_size=20,
                    max_chunk_length=80,
                ),
            )
        else:
            logger.info(f"Using Deepgram TTS: {settings.DEEPGRAM_TTS_VOICE}")
            tts = DeepgramTTSService(
                api_key=settings.DEEPGRAM_API_KEY,
                settings=DeepgramTTSService.Settings(voice=settings.DEEPGRAM_TTS_VOICE),
            )

        # 4. Build Pipeline: Audio in -> STT -> User Aggregator -> LLM -> TTS -> Metrics Tracker -> Audio out -> Assistant Aggregator
        pipeline = Pipeline([
            self.transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            self.latency_tracker,
            self.transport.output(),
            context_aggregator.assistant(),
        ])

        self.task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
                send_initial_empty_metrics=False,
            )
        )

        # Send initial greeting
        clinic_name = clinic_config.get("clinic", {}).get("name", "our clinic")
        greeting = f"Hello, thank you for calling {clinic_name}. I am the AI receptionist. How can I help you today?"
        
        greeting_triggered = False

        async def send_greeting():
            nonlocal greeting_triggered
            if greeting_triggered:
                return
            greeting_triggered = True
            logger.info(f"Triggering initial greeting for session {self.session_id}")
            await asyncio.sleep(0.4)
            await self.task.queue_frames([
                LLMMessagesFrame(messages + [{"role": "system", "content": f"Say to the caller: '{greeting}'"}])
            ])

        async def on_client_joined(*args, **kwargs):
            logger.info(f"Caller joined event fired for session {self.session_id}.")
            await send_greeting()

        for ev in ("on_client_connected", "on_first_participant_joined"):
            try:
                self.transport.add_event_handler(ev, on_client_joined)
            except Exception:
                pass

        # Guaranteed fallback trigger in case event fired before handler was registered
        async def scheduled_greeting():
            await asyncio.sleep(1.2)
            if not greeting_triggered:
                logger.info(f"Scheduled fallback greeting for session {self.session_id}")
                await send_greeting()

        asyncio.create_task(scheduled_greeting())

        self.runner = PipelineRunner()
        await self.runner.run(self.task)
