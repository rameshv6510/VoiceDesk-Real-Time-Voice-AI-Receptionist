"""Latency tracking and frame performance metrics processor."""
import time
from typing import Optional, List, Dict, Any
from loguru import logger
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import (
    Frame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    TranscriptionFrame,
    TextFrame,
    TTSTextFrame,
    AggregatedTextFrame,
    TTSStartedFrame,
    TTSAudioRawFrame,
    AudioRawFrame,
    EndFrame,
    OutputTransportMessageUrgentFrame,
)

class TurnLatencyTracker(FrameProcessor):
    """Measures precise turn-to-turn latency: caller stopped speaking -> first agent audio frame."""

    def __init__(self, session_id: str = "default_session"):
        super().__init__()
        self.session_id = session_id
        self.user_stopped_speaking_at: Optional[float] = None
        self.agent_first_audio_at: Optional[float] = None
        self.turn_count: int = 0
        self.latencies: List[Dict[str, Any]] = []
        self._awaiting_first_audio: bool = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if getattr(self, "_task_manager", None):
            await super().process_frame(frame, direction)

        if isinstance(frame, UserStartedSpeakingFrame):
            self._awaiting_first_audio = False
            self.user_stopped_speaking_at = None

        elif isinstance(frame, UserStoppedSpeakingFrame):
            self.user_stopped_speaking_at = time.time()
            self._awaiting_first_audio = True

        elif isinstance(frame, (TTSAudioRawFrame, AudioRawFrame)) and direction == FrameDirection.DOWNSTREAM:
            if self._awaiting_first_audio and self.user_stopped_speaking_at:
                self.agent_first_audio_at = time.time()
                latency_ms = (self.agent_first_audio_at - self.user_stopped_speaking_at) * 1000.0
                self.turn_count += 1
                self._awaiting_first_audio = False

                turn_record = {
                    "turn": self.turn_count,
                    "session_id": self.session_id,
                    "latency_ms": round(latency_ms, 2),
                    "timestamp": time.time()
                }
                self.latencies.append(turn_record)
                logger.info(f"⏱️ [TURN {self.turn_count} LATENCY] Turn-to-Turn: {latency_ms:.1f}ms")

                if getattr(self, "_task_manager", None):
                    try:
                        from pipecat.frames.frames import OutputTransportMessageUrgentFrame
                        await self.push_frame(
                            OutputTransportMessageUrgentFrame(message={
                                "type": "latency",
                                "latency_ms": round(latency_ms, 1),
                                "turn": self.turn_count
                            }),
                            FrameDirection.DOWNSTREAM
                        )
                    except Exception:
                        pass

        elif isinstance(frame, TranscriptionFrame):
            text = getattr(frame, "text", "").strip()
            if text:
                logger.info(f"👤 Caller said: {text}")
                if getattr(self, "_task_manager", None):
                    try:
                        from pipecat.frames.frames import OutputTransportMessageUrgentFrame
                        await self.push_frame(
                            OutputTransportMessageUrgentFrame(message={
                                "type": "transcript",
                                "sender": "caller",
                                "text": text
                            }),
                            FrameDirection.DOWNSTREAM
                        )
                    except Exception:
                        pass

        elif isinstance(frame, (TTSTextFrame, TextFrame)) and not isinstance(frame, AggregatedTextFrame) and direction == FrameDirection.DOWNSTREAM:
            text = getattr(frame, "text", "").strip()
            if text:
                logger.info(f"🤖 Receptionist: {text}")
                if getattr(self, "_task_manager", None):
                    try:
                        from pipecat.frames.frames import OutputTransportMessageUrgentFrame
                        await self.push_frame(
                            OutputTransportMessageUrgentFrame(message={
                                "type": "transcript",
                                "sender": "agent",
                                "text": text
                            }),
                            FrameDirection.DOWNSTREAM
                        )
                    except Exception:
                        pass

        # Push frame along the pipeline if active inside a running pipeline task
        if getattr(self, "_task_manager", None):
            await self.push_frame(frame, direction)

    def get_summary(self) -> Dict[str, Any]:
        if not self.latencies:
            return {"total_turns": 0, "avg_latency_ms": 0.0, "p50_latency_ms": 0.0, "p95_latency_ms": 0.0}
        
        vals = sorted([r["latency_ms"] for r in self.latencies])
        n = len(vals)
        p50 = vals[n // 2]
        p95 = vals[min(int(n * 0.95), n - 1)]
        avg = sum(vals) / n

        return {
            "total_turns": n,
            "avg_latency_ms": round(avg, 2),
            "p50_latency_ms": round(p50, 2),
            "p95_latency_ms": round(p95, 2),
            "records": self.latencies
        }
