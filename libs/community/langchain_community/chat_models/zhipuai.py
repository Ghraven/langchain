"""ZHIPU AI chat models wrapper."""
from __future__ import annotations

import asyncio
import json
import logging
from functools import partial
from typing import Any, Dict, Iterator, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import (
    BaseChatModel,
    generate_from_stream,
)
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.pydantic_v1 import BaseModel, Field

logger = logging.getLogger(__name__)


class ref(BaseModel):
    enable: bool = Field(True)
    search_query: str = Field("")


class meta(BaseModel):
    user_info: str = Field("")
    bot_info: str = Field("")
    bot_name: str = Field("")
    user_name: str = Field("User")


class ChatZhipuAI(BaseChatModel):
    """
    `ZHIPU AI` large language chat models API.

    To use, you should have the ``zhipuai`` python package installed.

    Example:
    .. code-block:: python

    from langchain_community.chat_models import ChatZhipuAI

    zhipuai_chat = ChatZhipuAI(
        temperature=0.5,
        api_key="your-api-key",
        model="chatglm_turbo",
    )

    """

    zhipuai: Any
    zhipuai_api_key: Optional[str] = Field(default=None, alias="api_key")
    """Automatically inferred from env var `ZHIPUAI_API_KEY` if not provided."""

    model: str = Field("chatglm_turbo")
    """
    Model name to use.
    -chatglm_turbo:
        According to the input of natural language instructions to complete a 
        variety of language tasks, it is recommended to use SSE or asynchronous 
        call request interface.
    -characterglm:
        It supports human-based role-playing, ultra-long multi-round memory, 
        and thousands of character dialogues. It is widely used in anthropomorphic 
        dialogues or game scenes such as emotional accompaniments, game intelligent 
        NPCS, Internet celebrities/stars/movie and TV series IP clones, digital 
        people/virtual anchors, and text adventure games.
    """

    temperature: float = Field(0.95)
    """
    What sampling temperature to use. The value ranges from 0.0 to 1.0 and cannot 
    be equal to 0.
    The larger the value, the more random and creative the output; The smaller 
    the value, the more stable or certain the output will be.
    You are advised to adjust top_p or temperature parameters based on application 
    scenarios, but do not adjust the two parameters at the same time.
    """

    top_p: float = Field(0.7)
    """
    Another method of sampling temperature is called nuclear sampling. The value 
    ranges from 0.0 to 1.0 and cannot be equal to 0 or 1.
    The model considers the results with top_p probability quality tokens.
    For example, 0.1 means that the model decoder only considers tokens from the 
    top 10% probability of the candidate set.
    You are advised to adjust top_p or temperature parameters based on application 
    scenarios, but do not adjust the two parameters at the same time.
    """

    request_id: Optional[str] = Field(None)
    """
    Parameter transmission by the client must ensure uniqueness; A unique 
    identifier used to distinguish each request, which is generated by default 
    by the platform when the client does not transmit it.
    """

    streaming: bool = Field(False)
    """Whether to stream the results or not."""

    incremental: bool = Field(True)
    """
    When invoked by the SSE interface, it is used to control whether the content 
    is returned incremented or full each time.
    If this parameter is not provided, the value is returned incremented by default.
    """

    return_type: str = Field("json_string")
    """
    This parameter is used to control the type of content returned each time.
    - json_string Returns a standard JSON string.
    - text Returns the original text content.
    """

    ref: Optional[ref] = Field(None)
    """
    This parameter is used to control the reference of external information 
    during the request.
    Currently, this parameter is used to control whether to reference external 
    information.
    If this field is empty or absent, the search and parameter passing format 
    is enabled by default.
    {"enable": "true", "search_query": "history "}
    """

    meta: Optional[meta] = Field(None)
    """Used in CharacterGLM"""

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"model_name": self.model}

    @property
    def _llm_type(self) -> str:
        """Return the type of chat model."""
        return "zhipuai"

    @property
    def lc_secrets(self) -> Dict[str, str]:
        return {"zhipuai_api_key": "ZHIPUAI_API_KEY"}

    @classmethod
    def get_lc_namespace(cls) -> List[str]:
        """Get the namespace of the langchain object."""
        return ["langchain", "chat_models", "zhipuai"]

    @property
    def lc_attributes(self) -> Dict[str, Any]:
        attributes: Dict[str, Any] = {}

        if self.model:
            attributes["model"] = self.model

        if self.streaming:
            attributes["streaming"] = self.streaming

        if self.return_type:
            attributes["return_type"] = self.return_type

        return attributes

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        try:
            import zhipuai

            self.zhipuai = zhipuai
            self.zhipuai.api_key = self.zhipuai_api_key
        except ImportError:
            raise RuntimeError(
                "Could not import zhipuai package. "
                "Please install it via 'pip install zhipuai'"
            )

    def invoke(self, prompt):  # type: ignore[no-untyped-def]
        if self.model == "chatglm_turbo":
            return self.zhipuai.model_api.invoke(
                model=self.model,
                prompt=prompt,
                top_p=self.top_p,
                temperature=self.temperature,
                request_id=self.request_id,
                return_type=self.return_type,
            )
        elif self.model == "characterglm":
            meta = self.meta.dict()
            return self.zhipuai.model_api.invoke(
                model=self.model,
                meta=meta,
                prompt=prompt,
                request_id=self.request_id,
                return_type=self.return_type,
            )
        return None

    def sse_invoke(self, prompt):  # type: ignore[no-untyped-def]
        if self.model == "chatglm_turbo":
            return self.zhipuai.model_api.sse_invoke(
                model=self.model,
                prompt=prompt,
                top_p=self.top_p,
                temperature=self.temperature,
                request_id=self.request_id,
                return_type=self.return_type,
                incremental=self.incremental,
            )
        elif self.model == "characterglm":
            meta = self.meta.dict()
            return self.zhipuai.model_api.sse_invoke(
                model=self.model,
                prompt=prompt,
                meta=meta,
                request_id=self.request_id,
                return_type=self.return_type,
                incremental=self.incremental,
            )
        return None

    async def async_invoke(self, prompt):  # type: ignore[no-untyped-def]
        loop = asyncio.get_running_loop()
        partial_func = partial(
            self.zhipuai.model_api.async_invoke, model=self.model, prompt=prompt
        )
        response = await loop.run_in_executor(
            None,
            partial_func,
        )
        return response

    async def async_invoke_result(self, task_id):  # type: ignore[no-untyped-def]
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            self.zhipuai.model_api.query_async_invoke_result,
            task_id,
        )
        return response

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        stream: Optional[bool] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a chat response."""
        prompt = []
        for message in messages:
            if isinstance(message, AIMessage):
                role = "assistant"
            else:  # For both HumanMessage and SystemMessage, role is 'user'
                role = "user"

            prompt.append({"role": role, "content": message.content})

        should_stream = stream if stream is not None else self.streaming
        if not should_stream:
            response = self.invoke(prompt)

            if response["code"] != 200:
                raise RuntimeError(response)

            content = response["data"]["choices"][0]["content"]
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content=content))]
            )

        else:
            stream_iter = self._stream(
                prompt=prompt, stop=stop, run_manager=run_manager, **kwargs  # type: ignore[arg-type]
            )
            return generate_from_stream(stream_iter)

    async def _agenerate(  # type: ignore[override]
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        stream: Optional[bool] = False,
        **kwargs: Any,
    ) -> ChatResult:
        """Asynchronously generate a chat response."""

        prompt = []
        for message in messages:
            if isinstance(message, AIMessage):
                role = "assistant"
            else:  # For both HumanMessage and SystemMessage, role is 'user'
                role = "user"

            prompt.append({"role": role, "content": message.content})

        invoke_response = await self.async_invoke(prompt)
        task_id = invoke_response["data"]["task_id"]

        response = await self.async_invoke_result(task_id)
        while response["data"]["task_status"] != "SUCCESS":
            await asyncio.sleep(1)
            response = await self.async_invoke_result(task_id)

        content = response["data"]["choices"][0]["content"]
        content = json.loads(content)
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=content))]
        )

    def _stream(  # type: ignore[override]
        self,
        prompt: List[Dict[str, str]],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """Stream the chat response in chunks."""
        response = self.sse_invoke(prompt)

        for r in response.events():
            if r.event == "add":
                delta = r.data
                yield ChatGenerationChunk(message=AIMessageChunk(content=delta))
                if run_manager:
                    run_manager.on_llm_new_token(delta)

            elif r.event == "error":
                raise ValueError(f"Error from ZhipuAI API response: {r.data}")
