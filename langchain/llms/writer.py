"""Wrapper around Writer APIs."""
from typing import Any, Dict, List, Mapping, Optional

import requests
from pydantic import Extra, root_validator

from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.llms.base import LLM
from langchain.llms.utils import enforce_stop_tokens
from langchain.utils import get_from_dict_or_env


class Writer(LLM):
    """Wrapper around Writer large language models.

    To use, you should have the environment variable ``WRITER_API_KEY``
    set with your API key.

    Example:
        .. code-block:: python

            from langchain import Writer
            writer = Writer(model_id="palmyra-base")
    """

    model_id: str = "palmyra-base"
    """Model name to use."""

    tokens_to_generate: int = 24
    """Max number of tokens to generate."""

    logprobs: bool = False
    """Whether to return log probabilities."""

    temperature: float = 1.0
    """What sampling temperature to use."""

    length: int = 256
    """The maximum number of tokens to generate in the completion."""

    top_p: float = 1.0
    """Total probability mass of tokens to consider at each step."""

    top_k: int = 1
    """The number of highest probability vocabulary tokens to
    keep for top-k-filtering."""

    repetition_penalty: float = 1.0
    """Penalizes repeated tokens according to frequency."""

    random_seed: int = 0
    """The model generates random results.
    Changing the random seed alone will produce a different response
    with similar characteristics. It is possible to reproduce results
    by fixing the random seed (assuming all other hyperparameters
    are also fixed)"""

    beam_search_diversity_rate: float = 1.0
    """Only applies to beam search, i.e. when the beam width is >1.
    A higher value encourages beam search to return a more diverse
    set of candidates"""

    beam_width: Optional[int] = None
    """The number of concurrent candidates to keep track of during
    beam search"""

    length_pentaly: float = 1.0
    """Only applies to beam search, i.e. when the beam width is >1.
    Larger values penalize long candidates more heavily, thus preferring
    shorter candidates"""

    writer_api_key: Optional[str] = None

    stop: Optional[List[str]] = None
    """Sequences when completion generation will stop"""

    base_url: Optional[str] = None
    """Base url to use, if None decides based on model name."""

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key exists in environment."""
        writer_api_key = get_from_dict_or_env(
            values, "writer_api_key", "WRITER_API_KEY"
        )
        values["writer_api_key"] = writer_api_key
        return values

    @property
    def _default_params(self) -> Mapping[str, Any]:
        """Get the default parameters for calling Writer API."""
        return {
            "tokens_to_generate": self.tokens_to_generate,
            "stop": self.stop,
            "logprobs": self.logprobs,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repetition_penalty": self.repetition_penalty,
            "random_seed": self.random_seed,
            "beam_search_diversity_rate": self.beam_search_diversity_rate,
            "beam_width": self.beam_width,
            "length_pentaly": self.length_pentaly,
        }

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {**{"model_id": self.model_id}, **self._default_params}

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "writer"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
    ) -> str:
        """Call out to Writer's complete endpoint.

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.

        Returns:
            The string generated by the model.

        Example:
            .. code-block:: python

                response = Writer("Tell me a joke.")
        """
        if self.base_url is not None:
            base_url = self.base_url
        else:
            base_url = (
                "https://api.llm.writer.com/v1/models/{self.model_id}/completions"
            )
        response = requests.post(
            url=base_url,
            headers={
                "Authorization": f"Bearer {self.writer_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={"prompt": prompt, **self._default_params},
        )
        text = response.text
        if stop is not None:
            # I believe this is required since the stop tokens
            # are not enforced by the model parameters
            text = enforce_stop_tokens(text, stop)
        return text
