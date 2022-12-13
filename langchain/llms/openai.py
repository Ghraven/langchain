"""Wrapper around OpenAI APIs."""
from typing import Any, Dict, List, Mapping, Optional

from pydantic import BaseModel, Extra, Field, root_validator

from langchain.llms.base import LLM, Generation, LLMResult
from langchain.utils import get_from_dict_or_env


class OpenAI(LLM, BaseModel):
    """Wrapper around OpenAI large language models.

    To use, you should have the ``openai`` python package installed, and the
    environment variable ``OPENAI_API_KEY`` set with your API key.

    Any parameters that are valid to be passed to the openai.create call can be passed
    in, even if not explicitly saved on this class.

    Example:
        .. code-block:: python

            from langchain import OpenAI
            openai = OpenAI(model="text-davinci-003")
    """

    client: Any  #: :meta private:
    model_name: str = "text-davinci-003"
    """Model name to use."""
    temperature: float = 0.7
    """What sampling temperature to use."""
    max_tokens: int = 256
    """The maximum number of tokens to generate in the completion."""
    top_p: float = 1
    """Total probability mass of tokens to consider at each step."""
    frequency_penalty: float = 0
    """Penalizes repeated tokens according to frequency."""
    presence_penalty: float = 0
    """Penalizes repeated tokens."""
    n: int = 1
    """How many completions to generate for each prompt."""
    best_of: int = 1
    """Generates best_of completions server-side and returns the "best"."""
    model_kwargs: Dict[str, Any] = Field(default_factory=dict)
    """Holds any model parameters valid for `create` call not explicitly specified."""
    openai_api_key: Optional[str] = None

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid

    @root_validator(pre=True)
    def build_extra(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Build extra kwargs from additional params that were passed in."""
        all_required_field_names = {field.alias for field in cls.__fields__.values()}

        extra = values.get("model_kwargs", {})
        for field_name in list(values):
            if field_name not in all_required_field_names:
                if field_name in extra:
                    raise ValueError(f"Found {field_name} supplied twice.")
                extra[field_name] = values.pop(field_name)
        values["model_kwargs"] = extra
        return values

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key and python package exists in environment."""
        openai_api_key = get_from_dict_or_env(
            values, "openai_api_key", "OPENAI_API_KEY"
        )
        try:
            import openai

            openai.api_key = openai_api_key
            values["client"] = openai.Completion
        except ImportError:
            raise ValueError(
                "Could not import openai python package. "
                "Please it install it with `pip install openai`."
            )
        return values

    @property
    def _default_params(self) -> Dict[str, Any]:
        """Get the default parameters for calling OpenAI API."""
        normal_params = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "n": self.n,
            "best_of": self.best_of,
        }
        return {**normal_params, **self.model_kwargs}

    def generate(
        self, prompts: List[str], stop: Optional[List[str]] = None
    ) -> LLMResult:
        """ "Call out to OpenAI's endpoint with k unique prompts.

        Args:
            prompts: The prompts to pass into the model.
            stop: Optional list of stop words to use when generating.

        Returns:
            The full LLM output.

        Example:
            .. code-block:: python

                response = openai.generate(["Tell me a joke."])
        """
        params = self._default_params
        if stop is not None:
            if "stop" in params:
                raise ValueError("`stop` found in both the input and default params.")
            params["stop"] = stop

        if params["max_tokens"] == -1:
            if len(prompts) != 1:
                raise ValueError(
                    "max_tokens set to -1 not supported for multiple inputs."
                )
            params["max_tokens"] = self.max_tokens_for_prompt(prompts[0])

        response = self.client.create(model=self.model_name, prompt=prompts, **params)
        generations = []
        for i, prompt in enumerate(prompts):
            choices = response["choices"][i * self.n : (i + 1) * self.n]
            generations.append([Generation(text=choice["text"]) for choice in choices])
        # Get the token usage from the response.
        # Includes prompt, completion, and total tokens used.
        token_usage = response["usage"]
        return LLMResult(
            generations=generations, llm_output={"token_usage": token_usage}
        )

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {**{"model": self.model_name}, **self._default_params}

    def __call__(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        """Call out to OpenAI's create endpoint.

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.

        Returns:
            The string generated by the model.

        Example:
            .. code-block:: python

                response = openai("Tell me a joke.")
        """
        return self.generate([prompt], stop=stop).generations[0][0].text

    def modelname_to_contextsize(self, modelname: str) -> int:
        """Calculate the maximum number of tokens possible to generate for a model.

        text-davinci-003: 4,000 tokens
        text-curie-001: 2,048 tokens
        text-babbage-001: 2,048 tokens
        text-ada-001: 2,048 tokens
        code-davinci-002: 8,000 tokens
        code-cushman-001: 2,048 tokens

        Args:
            modelname: The modelname we want to know the context size for.

        Returns:
            The maximum context size

        Example:
            .. code-block:: python

                max_tokens = openai.modelname_to_contextsize("text-davinci-003")
        """
        if modelname == "text-davinci-003":
            return 4000
        elif modelname == "text-curie-001":
            return 2048
        elif modelname == "text-babbage-001":
            return 2048
        elif modelname == "text-ada-001":
            return 2048
        elif modelname == "code-davinci-002":
            return 8000
        elif modelname == "code-cushman-001":
            return 2048
        else:
            return 4000

    def max_tokens_for_prompt(self, prompt: str) -> int:
        """Calculate the maximum number of tokens possible to generate for a prompt.

        Args:
            prompt: The prompt to pass into the model.

        Returns:
            The maximum number of tokens to generate for a prompt.

        Example:
            .. code-block:: python

                max_tokens = openai.max_token_for_prompt("Tell me a joke.")
        """
        # TODO: this method may not be exact.
        # TODO: this method may differ based on model (eg codex).
        try:
            from transformers import GPT2TokenizerFast
        except ImportError:
            raise ValueError(
                "Could not import transformers python package. "
                "This is needed in order to calculate max_tokens_for_prompt. "
                "Please it install it with `pip install transformers`."
            )
        # create a GPT-3 tokenizer instance
        tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")

        # tokenize the text using the GPT-3 tokenizer
        tokenized_text = tokenizer.tokenize(prompt)

        # calculate the number of tokens in the tokenized text
        num_tokens = len(tokenized_text)

        # get max context size for model by name
        max_size = self.modelname_to_contextsize(self.model_name)
        return max_size - num_tokens
