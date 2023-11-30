"""Wrapper around Google VertexAI chat-based models."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
    cast,
)

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.pydantic_v1 import root_validator

from langchain.callbacks.manager import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain.chat_models.base import (
    BaseChatModel,
    agenerate_from_stream,
    generate_from_stream,
)
from langchain.llms.vertexai import _VertexAICommon, is_codey_model
from langchain.utilities.vertexai import raise_vertex_import_error

if TYPE_CHECKING:
    from vertexai.language_models import (
        ChatMessage,
        ChatSession,
        CodeChatSession,
        InputOutputTextPair,
    )

logger = logging.getLogger(__name__)


@dataclass
class _ChatHistory:
    """Represents a context and a history of messages."""

    history: List["ChatMessage"] = field(default_factory=list)
    context: Optional[str] = None


def _parse_chat_history(history: List[BaseMessage]) -> _ChatHistory:
    """Parse a sequence of messages into history.

    Args:
        history: The list of messages to re-create the history of the chat.
    Returns:
        A parsed chat history.
    Raises:
        ValueError: If a sequence of message has a SystemMessage not at the
        first place.
    """
    from vertexai.language_models import ChatMessage

    vertex_messages, context = [], None
    for i, message in enumerate(history):
        content = cast(str, message.content)
        if i == 0 and isinstance(message, SystemMessage):
            context = content
        elif isinstance(message, AIMessage):
            vertex_message = ChatMessage(content=message.content, author="bot")
            vertex_messages.append(vertex_message)
        elif isinstance(message, HumanMessage):
            vertex_message = ChatMessage(content=message.content, author="user")
            vertex_messages.append(vertex_message)
        else:
            raise ValueError(
                f"Unexpected message with type {type(message)} at the position {i}."
            )
    chat_history = _ChatHistory(context=context, history=vertex_messages)
    return chat_history


def _parse_examples(examples: List[BaseMessage]) -> List["InputOutputTextPair"]:
    from vertexai.language_models import InputOutputTextPair

    if len(examples) % 2 != 0:
        raise ValueError(
            f"Expect examples to have an even amount of messages, got {len(examples)}."
        )
    example_pairs = []
    input_text = None
    for i, example in enumerate(examples):
        if i % 2 == 0:
            if not isinstance(example, HumanMessage):
                raise ValueError(
                    f"Expected the first message in a part to be from human, got "
                    f"{type(example)} for the {i}th message."
                )
            input_text = example.content
        if i % 2 == 1:
            if not isinstance(example, AIMessage):
                raise ValueError(
                    f"Expected the second message in a part to be from AI, got "
                    f"{type(example)} for the {i}th message."
                )
            pair = InputOutputTextPair(
                input_text=input_text, output_text=example.content
            )
            example_pairs.append(pair)
    return example_pairs


def _get_question(messages: List[BaseMessage]) -> HumanMessage:
    """Get the human message at the end of a list of input messages to a chat model."""
    if not messages:
        raise ValueError("You should provide at least one message to start the chat!")
    question = messages[-1]
    if not isinstance(question, HumanMessage):
        raise ValueError(
            f"Last message in the list should be from human, got {question.type}."
        )
    return question


class ChatVertexAI(_VertexAICommon, BaseChatModel):
    """`Vertex AI` Chat large language models API."""

    model_name: str = "chat-bison"
    "Underlying model name."
    examples: Optional[List[BaseMessage]] = None

    @classmethod
    def is_lc_serializable(self) -> bool:
        return True

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that the python package exists in environment."""
        cls._try_init_vertexai(values)
        try:
            from vertexai.language_models import ChatModel, CodeChatModel
        except ImportError:
            raise_vertex_import_error()
        if is_codey_model(values["model_name"]):
            model_cls = CodeChatModel
        else:
            model_cls = ChatModel
        values["client"] = model_cls.from_pretrained(values["model_name"])
        return values

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        stream: Optional[bool] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate next turn in the conversation.

        Args:
            messages: The history of the conversation as a list of messages. Code chat
                does not support context.
            stop: The list of stop words (optional).
            run_manager: The CallbackManager for LLM run, it's not used at the moment.
            stream: Whether to use the streaming endpoint.

        Returns:
            The ChatResult that contains outputs generated by the model.

        Raises:
            ValueError: if the last message in the list is not from human.
        """
        should_stream = stream if stream is not None else self.streaming
        if should_stream:
            stream_iter = self._stream(
                messages, stop=stop, run_manager=run_manager, **kwargs
            )
            return generate_from_stream(stream_iter)

        question = _get_question(messages)
        chat, params = self._start_chat(
            messages=messages, stop=stop, stream=False, **kwargs
        )
        msg_params = {}
        if "candidate_count" in params:
            msg_params["candidate_count"] = params.pop("candidate_count")
        response = chat.send_message(question.content, **msg_params)
        generations = [
            ChatGeneration(message=AIMessage(content=r.text))
            for r in response.candidates
        ]
        return ChatResult(generations=generations)

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        stream: Optional[bool] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Asynchronously generate next turn in the conversation.

        Args:
            messages: The history of the conversation as a list of messages. Code chat
                does not support context.
            stop: The list of stop words (optional).
            run_manager: The CallbackManager for LLM run
            stream: Overrides the streaming used on model setup (optional)

        Returns:
            The ChatResult that contains outputs generated by the model.

        Raises:
            ValueError: if the last message in the list is not from human.
        """
        should_stream = stream if stream is not None else self.streaming
        if should_stream:
            stream_iter = self._astream(
                messages, stop=stop, run_manager=run_manager, **kwargs
            )
            return await agenerate_from_stream(stream_iter)

        question = _get_question(messages)
        chat, params = self._start_chat(messages=messages, stop=stop, **kwargs)
        msg_params = {}
        if "candidate_count" in params:
            msg_params["candidate_count"] = params.pop("candidate_count")
        response = await chat.send_message_async(question.content, **msg_params)
        generations = [
            ChatGeneration(message=AIMessage(content=r.text))
            for r in response.candidates
        ]
        return ChatResult(generations=generations)

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        question = _get_question(messages)
        chat, params = self._start_chat(messages=messages, stop=stop, **kwargs)
        responses = chat.send_message_streaming(question.content, **params)
        for response in responses:
            if run_manager:
                run_manager.on_llm_new_token(response.text)
            yield ChatGenerationChunk(message=AIMessageChunk(content=response.text))

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        question = _get_question(messages)
        chat, params = self._start_chat(messages=messages, stop=stop, **kwargs)
        responses = chat.send_message_streaming_async(question.content, **params)
        async for response in responses:
            if run_manager:
                await run_manager.on_llm_new_token(response.text)
            yield ChatGenerationChunk(message=AIMessageChunk(content=response.text))

    def _start_chat(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Tuple[Union[ChatSession, CodeChatSession], dict]:
        history = _parse_chat_history(messages[:-1])
        params = self._prepare_params(stop=stop, **kwargs)
        examples = kwargs.get("examples", None)
        if examples:
            params["examples"] = _parse_examples(examples)

        if not self.is_codey_model:
            return self.client.start_chat(
                context=history.context, message_history=history.history, **kwargs
            )
        else:
            return self.client.start_chat(message_history=history.history, **kwargs)
