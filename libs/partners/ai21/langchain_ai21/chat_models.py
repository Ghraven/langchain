from typing import Any, AsyncIterator, Iterator, List, Optional, cast

from ai21.models import ChatMessage, RoleType

from langchain_ai21.ai21_base import AI21Base
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    BaseMessageChunk,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult


def _convert_to_ai21_message(
    message: BaseMessage,
) -> ChatMessage:
    content = cast(str, message.content)

    role = None

    if isinstance(message, HumanMessage):
        role = RoleType.USER
    elif isinstance(message, AIMessage):
        role = RoleType.ASSISTANT

    if not role:
        raise ValueError(f"Could not resolve role type from message {message}")

    return ChatMessage(role=role, text=content)


def _pop_system_messages(messages: List[BaseMessage]) -> List[SystemMessage]:
    system_message_indexes = [
        i for i, message in enumerate(messages) if isinstance(message, SystemMessage)
    ]

    return [cast(SystemMessage, messages.pop(i)) for i in system_message_indexes]


class ChatAI21(BaseChatModel, AI21Base):
    """ChatAI21 chat model.

    Example:
        .. code-block:: python

            from langchain_ai21 import ChatAI21


            model = ChatAI21()
    """

    model: str = "j2-ultra"

    @property
    def _llm_type(self) -> str:
        """Return type of chat model."""
        return "chat-ai21"

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        raise NotImplementedError

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        yield ChatGenerationChunk(
            message=BaseMessageChunk(content="Yield chunks", type="ai"),
        )
        yield ChatGenerationChunk(
            message=BaseMessageChunk(content=" like this!", type="ai"),
        )

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        messages = messages.copy()
        system_messages = _pop_system_messages(messages)
        last_system_message_str = system_messages[-1].content if system_messages else ""
        ai21_messages = [_convert_to_ai21_message(message) for message in messages]

        response = self._client.chat.create(
            model=self.model,
            messages=ai21_messages,
            system=last_system_message_str,
            **kwargs,
        )

        outputs = response.outputs
        message = AIMessage(content=outputs[0].text)
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise NotImplementedError
