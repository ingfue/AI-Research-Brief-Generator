from app.agents.tone_agent import ToneAgent

# Shared instance so the Foundry agent is created once and reused
_tone_agent = ToneAgent()


class ToneService:
    def adjust_tone(self, text: str, tone: str, custom_instruction: str | None = None) -> str:
        return _tone_agent.adjust(text, tone, custom_instruction)
