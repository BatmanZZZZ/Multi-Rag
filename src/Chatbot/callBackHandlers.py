from langchain.callbacks.base import BaseCallbackHandler
from typing import Dict, List, Any
from langchain.schema.messages import BaseMessage
from langchain.schema import LLMResult


class QueueCallback(BaseCallbackHandler):
    """Callback handler for streaming LLM responses to a queue."""

    def __init__(self, q):
        super().__init__()
        self.q = q
        self._stop_signal = None

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        self.q.put(token)

    def on_llm_start(
            self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """Run when LLM starts running."""

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Run when LLM ends running."""
        # self.q.put(self._stop_signal)
        self.q.empty()

    # def on_llm_end(self, *args, **kwargs: Any) -> None:
    #     return self.q.empty()
    def on_chat_model_start(
            self,
            serialized: Dict[str, Any],
            messages: List[List[BaseMessage]],
            **kwargs: Any
    ) -> None:
        """Run when LLM starts running."""
        pass
