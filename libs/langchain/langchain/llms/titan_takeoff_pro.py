from typing import Any, Iterator, List, Mapping, Optional

import requests
from requests.exceptions import ConnectionError

from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.llms.base import LLM
from langchain.llms.utils import enforce_stop_tokens
from langchain.schema.output import GenerationChunk


class TitanTakeoffPro(LLM):
    base_url: Optional[str] = "http://localhost:3000"
    """Specifies the baseURL to use for the Titan Takeoff Pro API.
    Default = http://localhost:3000.
    """

    max_new_tokens: Optional[int] = None
    """Maximum tokens generated."""

    min_new_tokens: Optional[int] = None
    """Minimum tokens generated."""

    sampling_topk: Optional[int] = None
    """Sample predictions from the top K most probable candidates."""

    sampling_topp: Optional[float] = None
    """Sample from predictions whose cumulative probability exceeds this value.
    """

    sampling_temperature: Optional[float] = None
    """Sample with randomness. Bigger temperatures are associated with 
    more randomness and 'creativity'.
    """

    repetition_penalty: Optional[float] = None
    """Penalise the generation of tokens that have been generated before. 
    Set to > 1 to penalize.
    """

    regex_string: Optional[str] = None
    """A regex string for constrained generation."""

    no_repeat_ngram_size: Optional[int] = None
    """Prevent repetitions of ngrams of this size. Default = 0 (turned off)."""

    streaming: bool = False
    """Whether to stream the output. Default = False."""

    @property
    def _default_params(self) -> Mapping[str, Any]:
        """Get the default parameters for calling Titan Takeoff Server (Pro)."""
        return {
            **(
                {"regex_string": self.regex_string}
                if self.regex_string is not None
                else {}
            ),
            **(
                {"sampling_temperature": self.sampling_temperature}
                if self.sampling_temperature is not None
                else {}
            ),
            **(
                {"sampling_topp": self.sampling_topp}
                if self.sampling_topp is not None
                else {}
            ),
            **(
                {"repetition_penalty": self.repetition_penalty}
                if self.repetition_penalty is not None
                else {}
            ),
            **(
                {"max_new_tokens": self.max_new_tokens}
                if self.max_new_tokens is not None
                else {}
            ),
            **(
                {"min_new_tokens": self.min_new_tokens}
                if self.min_new_tokens is not None
                else {}
            ),
            **(
                {"sampling_topk": self.sampling_topk}
                if self.sampling_topk is not None
                else {}
            ),
            **(
                {"no_repeat_ngram_size": self.no_repeat_ngram_size}
                if self.no_repeat_ngram_size is not None
                else {}
            ),
        }
        # params: Mapping[str, Any] = {}
        # if self.regex_string is not None:
        #     params["regex_string"] = self.regex_string
        # if self.sampling_temperature is not None:
        #     params["sampling_temperature"] = self.sampling_temperature
        # if self.sampling_topp is not None:
        #     params["sampling_topp"] = self.sampling_topp
        # if self.repetition_penalty is not None:
        #     params["repetition_penalty"] = self.repetition_penalty
        # if self.max_new_tokens is not None:
        #     params["max_new_tokens"] = self.max_new_tokens
        # if self.min_new_tokens is not None:
        #     params["min_new_tokens"] = self.min_new_tokens
        # if self.sampling_topk is not None:
        #     params["sampling_topk"] = self.sampling_topk
        # if self.no_repeat_ngram_size is not None:
        #     params["no_repeat_ngram_size"] = self.no_repeat_ngram_size
        # return params

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "titan_takeoff_pro"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call out to Titan Takeoff (Pro) generate endpoint.

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.

        Returns:
            The string generated by the model.

        Example:
            .. code-block:: python

                prompt = "What is the capital of the United Kingdom?"
                response = model(prompt)

        """
        try:
            if self.streaming:
                text_output = ""
                for chunk in self._stream(
                    prompt=prompt,
                    stop=stop,
                    run_manager=run_manager,
                ):
                    text_output += chunk.text
                return text_output
            url = f"{self.base_url}/generate"
            params = {"text": prompt, **self._default_params}

            response = requests.post(url, json=params)
            response.raise_for_status()
            response.encoding = "utf-8"

            text = ""
            if "text" in response.json():
                text = response.json()["text"]
                text = text.replace("</s>", "")
            else:
                raise ValueError("Something went wrong.")
            if stop is not None:
                text = enforce_stop_tokens(text, stop)
            return text
        except ConnectionError:
            raise ConnectionError(
                "Could not connect to Titan Takeoff (Pro) server. \
                Please make sure that the server is running."
            )

    def _stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        """Call out to Titan Takeoff (Pro) stream endpoint.

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.

        Returns:
            The string generated by the model.

        Yields:
            A dictionary like object containing a string token.

        Example:
            .. code-block:: python

                prompt = "What is the capital of the United Kingdom?"
                response = model(prompt)

        """
        url = f"{self.base_url}/generate_stream"
        params = {"text": prompt, **self._default_params}

        response = requests.post(url, json=params, stream=True)
        response.encoding = "utf-8"
        buffer = ""
        for text in response.iter_content(chunk_size=1, decode_unicode=True):
            buffer += text
            if "data:" in buffer:
                # Remove the first instance of "data:" from the buffer.
                if buffer.startswith("data:"):
                    buffer = ""
                if len(buffer.split("data:", 1)) == 2:
                    content, _ = buffer.split("data:", 1)
                    buffer = content.rstrip("\n")
                # Trim the buffer to only have content after the "data:" part.
                if buffer:  # Ensure that there's content to process.
                    chunk = GenerationChunk(text=buffer)
                    buffer = ""  # Reset buffer for the next set of data.
                    yield chunk
                    if run_manager:
                        run_manager.on_llm_new_token(token=chunk.text)

        # Yield any remaining content in the buffer.
        if buffer:
            chunk = GenerationChunk(text=buffer.replace("</s>", ""))
            yield chunk
            if run_manager:
                run_manager.on_llm_new_token(token=chunk.text)

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {"base_url": self.base_url, **{}, **self._default_params}
