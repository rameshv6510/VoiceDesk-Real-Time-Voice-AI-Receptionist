"""Health check script to verify Python environment and Pipecat imports."""
import sys

def verify():
    print("Checking dependencies...")
    try:
        import fastapi
        import uvicorn
        import yaml
        import pydantic
        import pipecat
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.processors.frame_processor import FrameProcessor
        from pipecat.audio.vad.silero import SileroVADAnalyzer
        from pipecat.services.deepgram.stt import DeepgramSTTService
        from pipecat.services.deepgram.tts import DeepgramTTSService
        from pipecat.services.openai.llm import OpenAILLMService
        print("? All Pipecat & AI service dependencies verified successfully!")
        return True
    except Exception as e:
        print(f"? Dependency import error: {e}")
        return False

if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)
