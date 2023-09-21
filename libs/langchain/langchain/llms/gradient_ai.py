from typing import Any, Dict, List, Mapping, Optional, Union

import aiohttp
import requests

from langchain.callbacks.manager import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain.llms.base import LLM
from langchain.llms.utils import enforce_stop_tokens
from langchain.pydantic_v1 import Extra, root_validator
from langchain.utils import get_from_dict_or_env


class GradientLLM(LLM):
    """Gradient.ai LLM Endpoints.

    GradientLLM is a class to interact with LLMs on gradient.ai

    To use, set the environment variable ``GRADIENT_ACCESS_TOKEN`` with your
    API token and ``GRADIENT_WORKSPACE_ID`` for your gradient workspace,
    or alternatively provide them as keywords to the constructor of this class.

    Example:
        .. code-block:: python

            from langchain.llms.gradientai_endpoint import GradientAIEndpoint
            GradientLLM(
                model_id="cad6644_base_ml_model",
                model_kwargs={
                    "max_generated_token_count": 200,
                    "temperature": 0.75,
                    "top_p": 0.95,
                    "top_k": 20,
                    "stop": [],
                },
                gradient_workspace_id="12345614fc0_workspace",
                gradient_access_token="gradientai-access_token",
            )

    """

    model_id: str
    "Underlying gradient.ai model id (base or fine-tuned)."

    gradient_workspace_id: Optional[str] = None
    "Underlying gradient.ai workspace_id."

    gradient_access_token: Optional[str] = None
    """gradient.ai API Token, which can be generated by going to
        https://auth.gradient.ai/select-workspace
        and selecting "Access tokens" under the profile drop-down.
    """

    model_kwargs: Optional[dict] = None
    """Key word arguments to pass to the model."""

    gradient_api_url: str = "https://api.gradient.ai/api"
    """Endpoint URL to use."""

    aiosession: Optional[aiohttp.ClientSession] = None
    """ClientSession, in case we want to reuse connection for better performance."""

    # LLM call kwargs
    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid

    @root_validator(allow_reuse=True)
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key and python package exists in environment."""

        values["gradient_access_token"] = get_from_dict_or_env(
            values, "gradient_access_token", "GRADIENT_ACCESS_TOKEN"
        )
        values["gradient_workspace_id"] = get_from_dict_or_env(
            values, "gradient_workspace_id", "GRADIENT_WORKSPACE_ID"
        )

        if (
            values["gradient_access_token"] is None
            or len(values["gradient_access_token"]) < 10
        ):
            raise ValueError("env variable `GRADIENT_ACCESS_TOKEN` must be set")

        if (
            values["gradient_workspace_id"] is None
            or len(values["gradient_access_token"]) < 3
        ):
            raise ValueError("env variable `GRADIENT_WORKSPACE_ID` must be set")

        if values["model_kwargs"]:
            kw = values["model_kwargs"]
            if not 0 <= kw.get("temperature", 0.5) <= 1:
                raise ValueError("`temperature` must be in the range [0.0, 1.0]")

            if not 0 <= kw.get("top_p", 0.5) <= 1:
                raise ValueError("`top_p` must be in the range [0.0, 1.0]")

            if 0 >= kw.get("top_k", 0.5):
                raise ValueError("`top_k` must be positive")

            if 0 >= kw.get("max_generated_token_count", 1):
                raise ValueError("`max_generated_token_count` must be positive")

        values["gradient_api_url"] = get_from_dict_or_env(
            values, "gradient_api_url", "GRADIENT_API_URL"
        )

        return values

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        _model_kwargs = self.model_kwargs or {}
        return {
            **{"gradient_api_url": self.gradient_api_url},
            **{"model_kwargs": _model_kwargs},
        }

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "gradient"

    def _kwargs_post_request(
        self, prompt: str, kwargs: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Build the kwargs for the Post request, used by sync

        Args:
            prompt (str): prompt used in query
            kwargs (dict): model kwargs in payload

        Returns:
            Dict[str, Union[str,dict]]: _description_
        """
        _model_kwargs = self.model_kwargs or {}
        _params = {**_model_kwargs, **kwargs}

        return dict(
            url=f"{self.gradient_api_url}/models/{self.model_id}/complete",
            headers={
                "authorization": f"Bearer {self.gradient_access_token}",
                "x-gradient-workspace-id": f"{self.gradient_workspace_id}",
                "accept": "application/json",
                "content-type": "application/json",
            },
            json=dict(
                query=prompt,
                maxGeneratedTokenCount=_params.get("max_generated_token_count", None),
                temperature=_params.get("temperature", None),
                topK=_params.get("top_k", None),
                topP=_params.get("top_p", None),
            ),
        )

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call to Gradients API `model/{id}/complete`.

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.

        Returns:
            The string generated by the model.
        """
        try:
            response = requests.post(**self._kwargs_post_request(prompt, kwargs))
            if response.status_code != 200:
                raise Exception(
                    f"Gradient returned an unexpected response with status "
                    f"{response.status_code}: {response.text}"
                )
        except requests.exceptions.RequestException as e:
            raise Exception(f"RequestException while calling Gradient Endpoint: {e}")

        text = response.json()["generatedOutput"]

        if stop is not None:
            # Apply stop tokens when making calls to Gradient
            text = enforce_stop_tokens(text, stop)

        return text

    async def _acall(
        self,
        prompt: str,
        stop: Union[List[str], None] = None,
        run_manager: Union[AsyncCallbackManagerForLLMRun, None] = None,
        **kwargs: Any,
    ) -> str:
        """Async Call to Gradients API `model/{id}/complete`.

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.

        Returns:
            The string generated by the model.
        """
        if not self.aiosession:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    **self._kwargs_post_request(prompt=prompt, kwargs=kwargs)
                ) as response:
                    if response.status != 200:
                        raise Exception(
                            f"Gradient returned an unexpected response with status "
                            f"{response.status}: {response.text}"
                        )
                    text = (await response.json())["generatedOutput"]
        else:
            async with self.aiosession.post(
                **self._kwargs_post_request(prompt=prompt, kwargs=kwargs)
            ) as response:
                if response.status != 200:
                    raise Exception(
                        f"Gradient returned an unexpected response with status "
                        f"{response.status}: {response.text}"
                    )
                text = (await response.json())["generatedOutput"]

        if stop is not None:
            # Apply stop tokens when making calls to Gradient
            text = enforce_stop_tokens(text, stop)

        return text
