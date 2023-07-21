import logging

from pydantic import BaseModel, Extra
from typing import List, Optional, Dict, Any, Mapping

from langchain.callbacks.manager import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain.chat_models.base import BaseChatModel
from langchain.schema.messages import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
)
from langchain.schema import (
    ChatGeneration,
    ChatResult,
)

logger = logging.getLogger(__name__)


class ChatParams(BaseModel, extra=Extra.allow):
    """Parameters for the MLflow AI Gateway LLM."""

    temperature: float = 0.0
    candidate_count: int = 1
    """The number of candidates to return."""
    stop: Optional[List[str]] = None
    max_tokens: Optional[int] = None


class ChatMLflowAIGateway(BaseChatModel):
    """Wrapper around OpenAI Chat large language models.

    To use, you should have the ``openai`` python package installed, and the
    environment variable ``OPENAI_API_KEY`` set with your API key.

    Any parameters that are valid to be passed to the openai.create call can be passed
    in, even if not explicitly saved on this class.

    Example:
        .. code-block:: python

            from langchain.chat_models import ChatOpenAI
            openai = ChatOpenAI(model_name="gpt-3.5-turbo")
    """

    def __init__(self, **kwargs: Any):
        try:
            import mlflow.gateway
        except ImportError as e:
            raise ImportError(
                "Could not import `mlflow.gateway` module. "
                "Please install it with `pip install mlflow[gateway]`."
            ) from e

        super().__init__(**kwargs)
        if self.gateway_uri:
            mlflow.gateway.set_gateway_uri(self.gateway_uri)

    route: str
    gateway_uri: Optional[str] = None
    params: Optional[ChatParams] = None

    @property
    def _default_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "gateway_uri": self.gateway_uri,
            "route": self.route,
            **(self.params.dict() if self.params else {}),
        }
        return params

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        try:
            import mlflow.gateway
        except ImportError as e:
            raise ImportError(
                "Could not import `mlflow.gateway` module. "
                "Please install it with `pip install mlflow[gateway]`."
            ) from e

        message_dicts = [
            ChatMLflowAIGateway._convert_dict_to_message(message)
            for message in messages
        ]
        data: Dict[str, Any] = {
            "messages": message_dicts,
            **(self.params.dict() if self.params else {}),
        }

        resp = mlflow.gateway.query(self.route, data=data)
        return ChatMLflowAIGateway._create_chat_result(resp)

    # async def _agenerate(
    #     self,
    #     messages: List[BaseMessage],
    #     stop: Optional[List[str]] = None,
    #     run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
    #     **kwargs: Any,
    # ) -> ChatResult:
    #     message_dicts, params = self._create_message_dicts(messages, stop)
    #     params = {**params, **kwargs}
    #     if self.streaming:
    #         inner_completion = ""
    #         role = "assistant"
    #         params["stream"] = True
    #         function_call: Optional[dict] = None
    #         async for stream_resp in await acompletion_with_retry(
    #             self, messages=message_dicts, **params
    #         ):
    #             role = stream_resp["choices"][0]["delta"].get("role", role)
    #             token = stream_resp["choices"][0]["delta"].get("content", "")
    #             inner_completion += token or ""
    #             _function_call = stream_resp["choices"][0]["delta"].get("function_call")
    #             if _function_call:
    #                 if function_call is None:
    #                     function_call = _function_call
    #                 else:
    #                     function_call["arguments"] += _function_call["arguments"]
    #             if run_manager:
    #                 await run_manager.on_llm_new_token(token)
    #         message = ChatMLflowAIGateway._convert_dict_to_message(
    #             {
    #                 "content": inner_completion,
    #                 "role": role,
    #                 "function_call": function_call,
    #             }
    #         )
    #         return ChatResult(generations=[ChatGeneration(message=message)])
    #     else:
    #         response = await acompletion_with_retry(
    #             self, messages=message_dicts, **params
    #         )
    #         return self._create_chat_result(response)

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {**{"model_name": self.model_name}, **self._default_params}

    @property
    def _client_params(self) -> Mapping[str, Any]:
        """Get the parameters used for the openai client."""
        openai_creds: Dict[str, Any] = {
            "api_key": self.openai_api_key,
            "api_base": self.openai_api_base,
            "organization": self.openai_organization,
            "model": self.model_name,
        }
        if self.openai_proxy:
            import openai

            openai.proxy = {"http": self.openai_proxy, "https": self.openai_proxy}  # type: ignore[assignment]  # noqa: E501
        return {**openai_creds, **self._default_params}

    def _get_invocation_params(
        self, stop: Optional[List[str]] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """Get the parameters used to invoke the model FOR THE CALLBACKS."""
        return {
            **super()._get_invocation_params(stop=stop, **kwargs),
            **self._default_params,
            "model": self.model_name,
            "function": kwargs.get("functions"),
        }

    @property
    def _llm_type(self) -> str:
        """Return type of chat model."""
        return "openai-chat"

    @staticmethod
    def _convert_dict_to_message(_dict: Mapping[str, Any]) -> BaseMessage:
        role = _dict["role"]
        content = _dict["content"]
        if role == "user":
            return HumanMessage(content=content)
        elif role == "assistant":
            return AIMessage(content=content)
        elif role == "system":
            return SystemMessage(content=content)
        else:
            return ChatMessage(content=content, role=role)

    @staticmethod
    def _raise_functions_not_supported():
        raise ValueError(
            "Function messages are not supported by the MLflow AI Gateway. Please"
            " create a feature request at https://github.com/mlflow/mlflow/issues."
        )

    @staticmethod
    def _convert_message_to_dict(message: BaseMessage) -> dict:
        if isinstance(message, ChatMessage):
            message_dict = {"role": message.role, "content": message.content}
        elif isinstance(message, HumanMessage):
            message_dict = {"role": "user", "content": message.content}
        elif isinstance(message, AIMessage):
            message_dict = {"role": "assistant", "content": message.content}
        elif isinstance(message, SystemMessage):
            message_dict = {"role": "system", "content": message.content}
        elif isinstance(message, FunctionMessage):
            raise ValueError(
                "Function messages are not supported by the MLflow AI Gateway. Please"
                " create a feature request at https://github.com/mlflow/mlflow/issues."
            )
        else:
            raise ValueError(f"Got unknown message type: {message}")

        if "function_call" in message.additional_kwargs:
            ChatMLflowAIGateway._raise_functions_not_supported()
        if message.additional_kwargs:
            logger.warning(
                "Additional message arguments are unsupported by MLflow AI Gateway "
                " and will be ignored: %s",
                message.additional_kwargs,
            )
        return message_dict

    @staticmethod
    def _create_chat_result(response: Mapping[str, Any]) -> ChatResult:
        generations = []
        for candidate in response["candidates"]:
            message = ChatMLflowAIGateway._convert_dict_to_message(candidate["message"])
            message_metadata = candidate.get("metadata", {})
            gen = ChatGeneration(
                message=message,
                generation_info=dict(message_metadata),
            )
            generations.append(gen)

        response_metadata = response.get("metadata", {})
        return ChatResult(generations=generations, llm_output=response_metadata)
