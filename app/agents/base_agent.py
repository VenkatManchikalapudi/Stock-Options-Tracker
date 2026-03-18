from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    name: str = ""
    description: str = ""
    model: str = ""  # Ollama model name used by this agent

    @abstractmethod
    async def run(self, action: str, params: dict) -> dict:
        """
        Execute the given action with the provided parameters.

        Returns a dict with:
          - response (str):  natural language answer, always present
          - stock    (dict | None): OHLCV data if available
          - options  (dict | None): puts/calls data if available
        """
        pass
