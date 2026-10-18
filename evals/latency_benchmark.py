"""Latency benchmark evaluator for TurnLatencyTracker."""
import asyncio
import time
import random
from typing import Dict, Any, List

from app.pipeline.metrics import TurnLatencyTracker
from pipecat.frames.frames import (
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    TTSAudioRawFrame,
)
from pipecat.processors.frame_processor import FrameDirection

async def run_latency_benchmark(num_turns: int = 20, simulated_base_delay_ms: float = 350.0) -> Dict[str, Any]:
    """Runs synthetic turn sequences through TurnLatencyTracker and analyzes latency distribution."""
    tracker = TurnLatencyTracker(session_id="benchmark_session")
    dummy_audio = TTSAudioRawFrame(audio=b'\x00' * 320, sample_rate=16000, num_channels=1)

    for i in range(num_turns):
        # Caller starts & stops speaking
        await tracker.process_frame(UserStartedSpeakingFrame(), FrameDirection.UPSTREAM)
        await tracker.process_frame(UserStoppedSpeakingFrame(), FrameDirection.UPSTREAM)

        # Simulated pipeline processing jitter (e.g. 300ms - 500ms)
        jitter = random.uniform(-50.0, 80.0)
        delay_sec = max(0.05, (simulated_base_delay_ms + jitter) / 1000.0)
        await asyncio.sleep(delay_sec)

        # First TTS audio frame received downstream
        await tracker.process_frame(dummy_audio, FrameDirection.DOWNSTREAM)

    summary = tracker.get_summary()
    latencies = [r["latency_ms"] for r in summary.get("records", [])]

    # Calculate p90, p95, max
    sorted_lats = sorted(latencies)
    n = len(sorted_lats)
    p50 = sorted_lats[n // 2] if n > 0 else 0.0
    p90 = sorted_lats[int(n * 0.9)] if n > 0 else 0.0
    p95 = sorted_lats[min(int(n * 0.95), n - 1)] if n > 0 else 0.0
    max_lat = max(sorted_lats) if n > 0 else 0.0
    avg_lat = sum(sorted_lats) / n if n > 0 else 0.0

    sla_target_ms = 1200.0
    sla_compliant = (p95 <= sla_target_ms)

    return {
        "suite": "turn_latency_benchmark",
        "turns_evaluated": n,
        "avg_latency_ms": round(avg_lat, 2),
        "p50_latency_ms": round(p50, 2),
        "p90_latency_ms": round(p90, 2),
        "p95_latency_ms": round(p95, 2),
        "max_latency_ms": round(max_lat, 2),
        "sla_target_ms": sla_target_ms,
        "sla_passed": sla_compliant
    }
