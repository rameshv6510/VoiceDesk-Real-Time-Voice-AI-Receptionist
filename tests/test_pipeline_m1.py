"""Tests for Milestone 1 configuration, system prompts, and metrics tracking."""
import time
import pytest
from app.config import clinic_config, settings
from app.pipeline.prompts import generate_system_prompt
from app.pipeline.metrics import TurnLatencyTracker
from pipecat.frames.frames import (
    StartFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    TTSAudioRawFrame,
)
from pipecat.processors.frame_processor import FrameDirection

def test_clinic_config_loaded():
    assert "clinic" in clinic_config
    assert clinic_config["clinic"]["name"] == "SmileCare Dental Clinic"
    assert len(clinic_config["services"]) >= 3
    assert len(clinic_config["doctors"]) >= 2
    assert len(clinic_config["faqs"]) >= 3

def test_system_prompt_generation():
    prompt = generate_system_prompt(clinic_config)
    assert "SmileCare Dental Clinic" in prompt
    assert "EMERGENCIES" in prompt
    assert "Dental Consultation & Checkup" in prompt
    assert "Dr. Ananya Rao" in prompt
    assert "Indiranagar 100ft Road" in prompt

@pytest.mark.asyncio
async def test_turn_latency_tracker():
    tracker = TurnLatencyTracker(session_id="test_session_1")
    
    # User starts and stops speaking
    await tracker.process_frame(UserStartedSpeakingFrame(), FrameDirection.UPSTREAM)
    await tracker.process_frame(UserStoppedSpeakingFrame(), FrameDirection.UPSTREAM)
    
    # Simulate 300ms processing delay before first agent audio
    time.sleep(0.3)
    
    # Agent audio frame arrives downstream
    dummy_audio = TTSAudioRawFrame(audio=b'\x00' * 320, sample_rate=16000, num_channels=1)
    await tracker.process_frame(dummy_audio, FrameDirection.DOWNSTREAM)
    
    summary = tracker.get_summary()
    assert summary["total_turns"] == 1
    assert summary["avg_latency_ms"] >= 280.0
    assert summary["p50_latency_ms"] >= 280.0
