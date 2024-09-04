"""Wrapper around Konko AI's Completion API."""

import logging
import warnings
from typing import Any, Dict, List, Optional

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.llms import LLM
from pydantic import ConfigDict, SecretStr, model_validator, root_validator

from langchain_community.utils.openai import is_openai_v1

logger = logging.getLogger(__name__)


class Konko(LLM):
    """Konko AI models.

    To use, you'll need an API key. This can be passed in as init param
    ``konko_api_key`` or set as environment variable ``KONKO_API_KEY``.

    Konko AI API reference: https://docs.konko.ai/reference/
    """

    base_url: str = "https://api.konko.ai/v1/completions"
    """Base inference API URL."""
    konko_api_key: SecretStr
    """Konko AI API key."""
    model: str
    """Model name. Available models listed here: 
       https://docs.konko.ai/reference/get_models
    """
    temperature: Optional[float] = None
    """Model temperature."""
    top_p: Optional[float] = None
    """Used to dynamically adjust the number of choices for each predicted token based 
        on the cumulative probabilities. A value of 1 will always yield the same 
        output. A temperature less than 1 favors more correctness and is appropriate 
        for question answering or summarization. A value greater than 1 introduces more 
        randomness in the output.
    """
    top_k: Optional[int] = None
    """Used to limit the number of choices for the next predicted word or token. It 
        specifies the maximum number of tokens to consider at each step, based on their 
        probability of occurrence. This technique helps to speed up the generation 
        process and can improve the quality of the generated text by focusing on the 
        most likely options.
    """
    max_tokens: Optional[int] = None
    """The maximum number of tokens to generate."""
    repetition_penalty: Optional[float] = None
    """A number that controls the diversity of generated text by reducing the 
        likelihood of repeated sequences. Higher values decrease repetition.
    """
    logprobs: Optional[int] = None
    """An integer that specifies how many top token log probabilities are included in 
        the response for each token generation step.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    @model_validator(mode="before")
    @classmethod
    def validate_environment(cls, values: Dict[str, Any]) -> Any:
        """Validate that python package exists in environment."""
        try:
            import konko

        except ImportError:
            raise ImportError(
                "Could not import konko python package. "
                "Please install it with `pip install konko`."
            )
        if not hasattr(konko, "_is_legacy_openai"):
            warnings.warn(
                "You are using an older version of the 'konko' package. "
                "Please consider upgrading to access new features"
                "including the completion endpoint."
            )
        return values

    def construct_payload(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        stop_to_use = stop[0] if stop and len(stop) == 1 else stop
        payload: Dict[str, Any] = {
            **self.default_params,
            "prompt": prompt,
            "stop": stop_to_use,
            **kwargs,
        }
        return {k: v for k, v in payload.items() if v is not None}

    @property
    def _llm_type(self) -> str:
        """Return type of model."""
        return "konko"

    @staticmethod
    def get_user_agent() -> str:
        from langchain_community import __version__

        return f"langchain/{__version__}"

    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "max_tokens": self.max_tokens,
            "repetition_penalty": self.repetition_penalty,
        }

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call out to Konko's text generation endpoint.

        Args:
            prompt: The prompt to pass into the model.

        Returns:
            The string generated by the model..
        """
        import konko

        payload = self.construct_payload(prompt, stop, **kwargs)

        try:
            if is_openai_v1():
                response = konko.completions.create(**payload)
            else:
                response = konko.Completion.create(**payload)

        except AttributeError:
            raise ValueError(
                "`konko` has no `Completion` attribute, this is likely "
                "due to an old version of the konko package. Try upgrading it "
                "with `pip install --upgrade konko`."
            )

        if is_openai_v1():
            output = response.choices[0].text
        else:
            output = response["choices"][0]["text"]

        return output

    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Asynchronously call out to Konko's text generation endpoint.

        Args:
            prompt: The prompt to pass into the model.

        Returns:
            The string generated by the model.
        """
        import konko

        payload = self.construct_payload(prompt, stop, **kwargs)

        try:
            if is_openai_v1():
                client = konko.AsyncKonko()
                response = await client.completions.create(**payload)
            else:
                response = await konko.Completion.acreate(**payload)

        except AttributeError:
            raise ValueError(
                "`konko` has no `Completion` attribute, this is likely "
                "due to an old version of the konko package. Try upgrading it "
                "with `pip install --upgrade konko`."
            )

        if is_openai_v1():
            output = response.choices[0].text
        else:
            output = response["choices"][0]["text"]

        return output
