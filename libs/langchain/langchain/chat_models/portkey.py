from __future__ import annotations

import logging
from typing import (TYPE_CHECKING, Any, Dict, List, Optional, Union, Iterator, TypedDict)

from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.chat_models.base import SimpleChatModel
from langchain.pydantic_v1 import Field, PrivateAttr
from langchain.schema.messages import BaseMessage
from langchain.schema.output import GenerationChunk

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import portkey
    from portkey import (
        LLMOptions,
        CacheLiteral,
        CacheType,
        Modes,
        ModesLiteral,
        PortkeyResponse,
    )




IMPORT_ERROR_MESSAGE = (
    "Portkey is not installed.Please install it with `pip install portkey-ai`."
)

class Message(TypedDict):
    role: str
    content: str



class ChatPortkey(SimpleChatModel):
    """`Portkey` Chat large language models.

    To use, you should have the ``portkey-ai`` python package installed, and the
    environment variable ``PORTKEY_API_KEY``, set with your API key, or pass
    it as a named parameter to the `Portkey` constructor.

    NOTE: You can install portkey using ``pip install portkey-ai``

    Example:
        .. code-block:: python

            import portkey
            from langchain.chat_models import ChatPortkey

            # Simplest invocation for an openai provider. Can be extended to
            # others as well
            llm_option = portkey.LLMOptions(
                provider="openai",  
                virtual_key="openai-virtual-key", # Checkout the docs for the virtual-api-key
                model="text-davinci-003"
            )

            # Initialise the client
            client = ChatPortkey(
                api_key="PORTKEY_API_KEY", 
                mode="single"
            ).add_llms(llms=llm_option)

            response = client("What are the biggest risks facing humanity?")

    """
    mode: Optional[Union["Modes", "ModesLiteral"]] = Field(
        description="The mode for using the Portkey integration", default=None
    )

    model: Optional[str] = Field(default="gpt-3.5-turbo")
    llm: "LLMOptions" = Field(description="LLM parameter", default_factory=dict)
    streaming: bool = False

    llms: List["LLMOptions"] = Field(description="LLM parameters", default_factory=list)

    _portkey: portkey = PrivateAttr()

    def __init__(
        self,
        *,
        mode: Union["Modes", "ModesLiteral"],
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        try:
            import portkey
        except ImportError as exc:
            raise ImportError(IMPORT_ERROR_MESSAGE) from exc

        super().__init__()
        if api_key is not None:
            portkey.api_key = api_key

        if base_url is not None:
            portkey.base_url = base_url

        portkey.mode = mode

        self._portkey = portkey
        self.model = None
        self.mode = mode
        

    def add_llms(self, llm_params: Union[LLMOptions, List[LLMOptions]]) -> "Portkey":
        """
        Adds the specified LLM parameters to the list of LLMs. This may be used for
        fallbacks or load-balancing as specified in the mode.

        Args:
            llm_params (Union[LLMOptions, List[LLMOptions]]): A single LLM parameter \
            set or a list of LLM parameter sets. Each set should be an instance of \
            LLMOptions with
            the specified attributes.
                > provider: Optional[ProviderTypes]
                > model: str
                > temperature: float
                > max_tokens: Optional[int]
                > max_retries: int
                > trace_id: Optional[str]
                > cache_status: Optional[CacheType]
                > cache: Optional[bool]
                > metadata: Dict[str, Any]
                > weight: Optional[float]
                > **kwargs : Other additional parameters that are supported by \
                    LLMOptions in portkey-ai

            NOTE: User may choose to pass additional params as well.
        Returns:
            self
        """
        try:
            from portkey import LLMOptions
        except ImportError as exc:
            raise ImportError(IMPORT_ERROR_MESSAGE) from exc
        if isinstance(llm_params, LLMOptions):
            llm_params = [llm_params]
        self.llms.extend(llm_params)
        if self.model is None:
            self.model = self.llms[0].model
        return self
    
    def _call(
        self,
        messages: List[Message],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call Portkey's chatCompletions endpoint. 

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.
        Returns:
            The string generated by the provider set in the initialisation of the LLM.
        
        Example:
            .. code-block:: python
                message = [{
                    "role": "user",
                    "content": "Tell me a joke."
                }]
                response = portkey(message)
        """
        try:
            from portkey import Config
        except ImportError as exc:
            raise ImportError(IMPORT_ERROR_MESSAGE) from exc
        self._client.config = Config(llms=self.llms)
        response = self._client.ChatCompletions.create(messages=messages, stream=False, stop=stop, **kwargs)
        message = response.choices[0].message
        return message.get("content", "") if message else "" 

    @property
    def _client(self):
        try:
            from portkey import Config
        except ImportError as exc:
            raise ImportError(IMPORT_ERROR_MESSAGE) from exc
        self._portkey.config = Config(llms=self.llms)
        return self._portkey
    
    def _stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        """Call Portkey completion_stream and return the resulting generator.

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.
        Returns:
            A generator representing the stream of tokens from Portkey.
        Example:
            .. code-block:: python

                prompt = "Write a poem about a stream."
                generator = portkey.stream(prompt)
                for token in generator:
                    yield token
        """
        response = self._client.Completions.create(stream=True, prompt=prompt, stop=stop, **kwargs)
        for token in response:
            chunk = GenerationChunk(text = token.choices[0].text or "")
            yield chunk
            if run_manager:
                run_manager.on_llm_new_token(chunk.text, chunk=chunk)


    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "portkey-ai-gateway"
    