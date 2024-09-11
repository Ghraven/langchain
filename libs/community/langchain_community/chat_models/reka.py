from typing import Any, AsyncIterator, Callable, Dict, Iterator, List, Mapping, Optional

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseLanguageModel
from langchain_core.language_models.chat_models import (
    BaseChatModel,
    agenerate_from_stream,
    generate_from_stream,
)
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    ChatMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.pydantic_v1 import Field, SecretStr, root_validator
from langchain_core.utils import (
    get_from_dict_or_env,
    get_pydantic_field_names,
)
from langchain_core.utils.utils import build_extra_kwargs, convert_to_secret_str

try:
    from reka.client import AsyncReka, Reka
except ImportError:
    raise ValueError(
        "Reka is not installed. Please install it with `pip install reka-api`."
    )

REKA_MODELS = [
    "reka-edge",
    "reka-flash",
    "reka-core",
]

DEFAULT_REKA_MODEL = "reka-flash"


def get_role(message: BaseMessage) -> str:
    """Get the role of the message."""
    if isinstance(message, (ChatMessage, HumanMessage)):
        return "user"
    elif isinstance(message, AIMessage):
        return "assistant"
    elif isinstance(message, SystemMessage):
        return "system"
    else:
        raise ValueError(f"Got unknown type {message}")


def process_messages_for_reka(messages: List[BaseMessage]) -> List[Dict[str, str]]:
    """Process messages for Reka format."""
    reka_messages = []
    system_message = None

    for message in messages:
        if isinstance(message, SystemMessage):
            if system_message is None:
                system_message = message.content
            else:
                raise ValueError("Multiple system messages are not supported.")
        else:
            content = message.content
            if system_message and isinstance(message, HumanMessage):
                content = f"{system_message}\n{content}"
                system_message = None
            reka_messages.append({"role": get_role(message), "content": content})

    return reka_messages


class RekaCommon(BaseLanguageModel):
    client: Any = None  #: :meta private:
    async_client: Any = None  #: :meta private:
    model: str = Field(default=DEFAULT_REKA_MODEL, alias="model_name")
    """Model name to use."""

    max_tokens: int = Field(default=256)
    """Denotes the number of tokens to predict per generation."""

    temperature: Optional[float] = None
    """A non-negative float that tunes the degree of randomness in generation."""

    streaming: bool = False
    """Whether to stream the results."""

    default_request_timeout: Optional[float] = None
    """Timeout for requests to Reka Completion API. Default is 600 seconds."""

    max_retries: int = 2
    """Number of retries allowed for requests sent to the Reka Completion API."""

    reka_api_key: Optional[SecretStr] = None

    count_tokens: Optional[Callable[[str], int]] = None
    model_kwargs: Dict[str, Any] = Field(default_factory=dict)

    @root_validator(pre=True)
    def build_extra(cls, values: Dict) -> Dict:
        extra = values.get("model_kwargs", {})
        all_required_field_names = get_pydantic_field_names(cls)
        values["model_kwargs"] = build_extra_kwargs(
            extra, values, all_required_field_names
        )
        return values

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key and python package exists in environment."""
        values["reka_api_key"] = convert_to_secret_str(
            get_from_dict_or_env(values, "reka_api_key", "REKA_API_KEY")
        )

        try:
            from reka.client import AsyncReka, Reka

            values["client"] = Reka(
                api_key=values["reka_api_key"].get_secret_value(),
            )
            values["async_client"] = AsyncReka(
                api_key=values["reka_api_key"].get_secret_value(),
            )

        except ImportError:
            raise ImportError(
                "Could not import reka python package. "
                "Please install it with `pip install reka-api`."
            )
        return values

    @property
    def _default_params(self) -> Mapping[str, Any]:
        """Get the default parameters for calling Reka API."""
        d = {
            "max_tokens": self.max_tokens,
            "model": self.model,
        }
        if self.temperature is not None:
            d["temperature"] = self.temperature
        return {**d, **self.model_kwargs}

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {**{}, **self._default_params}


class ChatReka(BaseChatModel, RekaCommon):
    """Reka chat large language models."""

    @property
    def _llm_type(self) -> str:
        """Return type of chat model."""
        return "reka-chat"

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        reka_messages = process_messages_for_reka(messages)
        params = {**self._default_params, **kwargs}
        if stop:
            params["stop"] = stop

        stream = self.client.chat.create_stream(messages=reka_messages, **params)

        for chunk in stream:
            content = chunk.responses[0].chunk.content
            chunk = ChatGenerationChunk(message=AIMessageChunk(content=content))
            yield chunk
            if run_manager:
                run_manager.on_llm_new_token(content, chunk=chunk)

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        reka_messages = process_messages_for_reka(messages)
        params = {**self._default_params, **kwargs}
        if stop:
            params["stop"] = stop

        stream = self.async_client.chat.create_stream(messages=reka_messages, **params)

        async for chunk in stream:
            content = chunk.responses[0].chunk.content
            chunk = ChatGenerationChunk(message=AIMessageChunk(content=content))
            yield chunk
            if run_manager:
                await run_manager.on_llm_new_token(content, chunk=chunk)

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self.streaming:
            return generate_from_stream(
                self._stream(messages, stop=stop, run_manager=run_manager, **kwargs)
            )

        reka_messages = process_messages_for_reka(messages)
        params = {**self._default_params, **kwargs}
        if stop:
            params["stop"] = stop
        response = self.client.chat.create(messages=reka_messages, **params)

        message = AIMessage(content=response.responses[0].message.content)
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self.streaming:
            return await agenerate_from_stream(
                self._astream(messages, stop=stop, run_manager=run_manager, **kwargs)
            )

        reka_messages = process_messages_for_reka(messages)
        params = {**self._default_params, **kwargs}
        if stop:
            params["stop"] = stop
        response = await self.async_client.chat.create(messages=reka_messages, **params)

        message = AIMessage(content=response.responses[0].message.content)
        return ChatResult(generations=[ChatGeneration(message=message)])

    def get_num_tokens(self, text: str) -> int:
        """Calculate number of tokens."""
        if self.count_tokens is None:
            raise NotImplementedError(
                "get_num_tokens() is not implemented for Reka models."
            )
        return self.count_tokens(text)
