"""Local, abstaining viewport grounding; no browser action lives here."""
from elvion.vision.grounder import LocalVisionGrounder
from elvion.vision.ollama import OllamaVisionProvider

__all__ = ["LocalVisionGrounder", "OllamaVisionProvider"]
