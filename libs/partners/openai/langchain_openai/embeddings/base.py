from __future__ import annotations

import asyncio
import logging
import os
import warnings
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

import openai
import tiktoken
from langchain_core.embeddings import Embeddings
from langchain_core.pydantic_v1 import BaseModel, Field, SecretStr, root_validator
from langchain_core.runnables.utils import gather_with_concurrency
from langchain_core.utils import (
    convert_to_secret_str,
    get_from_dict_or_env,
    get_pydantic_field_names,
)

logger = logging.getLogger(__name__)


def _process_split_embeddings(
    num_texts: int,
    split_tokens: List[Union[List[int], str]],
    split_embeddings: List[List[float]],
    split_embeddings_text_indices: List[int],
    skip_empty: bool,
) -> List[Optional[List[float]]]:
    split_embeddings_by_text: List[List[List[float]]] = [[] for _ in range(num_texts)]
    split_num_tokens_by_text: List[List[int]] = [[] for _ in range(num_texts)]

    for text_idx, embeddings, tokens in zip(
        split_embeddings_text_indices, split_embeddings, split_tokens
    ):
        if skip_empty and len(embeddings) == 1:
            continue
        split_embeddings_by_text[text_idx].append(embeddings)
        split_num_tokens_by_text[text_idx].append(len(tokens))

    # for each text, this is the final embedding
    averaged_embeddings: List[Optional[List[float]]] = []
    for text_idx, (curr_split_embeddings, curr_split_num_tokens) in enumerate(
        zip(split_embeddings_by_text, split_num_tokens_by_text)
    ):
        if len(curr_split_embeddings) == 0:
            # this will be populated with the embedding of an empty string
            # in the sync or async code calling this
            averaged_embeddings.append(None)
        elif len(curr_split_embeddings) == 1:
            # if only one embedding was produced, use it
            averaged_embeddings.append(curr_split_embeddings[0])
        else:
            # else we need to take weighted average
            averaged_embeddings.append(
                _normed_vector_avg(curr_split_embeddings, curr_split_num_tokens)
            )

    return averaged_embeddings


class OpenAIEmbeddings(BaseModel, Embeddings):
    """OpenAI embedding model integration.

    Setup:
        Install ``langchain_openai`` and set environment variable ``OPENAI_API_KEY``.

        .. code-block:: bash

            pip install -U langchain_openai
            export OPENAI_API_KEY="your-api-key"

    Key init args — embedding params:
        model: str
            Name of OpenAI model to use.
        dimensions: Optional[int] = None
            The number of dimensions the resulting output embeddings should have.
            Only supported in `text-embedding-3` and later models.

    Key init args — client params:
        api_key: Optional[SecretStr] = None
            OpenAI API key.
        organization: Optional[str] = None
            OpenAI organization ID. If not passed in will be read
            from env var OPENAI_ORG_ID.
        max_retries: int = 2
            Maximum number of retries to make when generating.
        request_timeout: Optional[Union[float, Tuple[float, float], Any]] = None
            Timeout for requests to OpenAI completion API.
        max_concurrency: Optional[int] = None
            Maximum number of coroutines to run concurrently. Only used for
            ``aembed_documents()``.

    See full list of supported init args and their descriptions in the params section.

    Instantiate:
        .. code-block:: python

            from langchain_openai import OpenAIEmbeddings

            embed = OpenAIEmbeddings(
                model="text-embedding-3-large"
                # With the `text-embedding-3` class
                # of models, you can specify the size
                # of the embeddings you want returned.
                # dimensions=1024
            )

    Embed single text:
        .. code-block:: python

            input_text = "The meaning of life is 42"
            vector = embeddings.embed_query("hello")
            print(vector[:3])

        .. code-block:: python

            [-0.024603435769677162, -0.007543657906353474, 0.0039630369283258915]

    Embed multiple texts:
        .. code-block:: python

            vectors = embeddings.embed_documents(["hello", "goodbye"])
            # Showing only the first 3 coordinates
            print(len(vectors))
            print(vectors[0][:3])

        .. code-block:: python

            2
            [-0.024603435769677162, -0.007543657906353474, 0.0039630369283258915]

    Async:
        .. code-block:: python

            await embed.aembed_query(input_text)
            print(vector[:3])

            # multiple:
            # await embed.aembed_documents(input_texts)

        .. code-block:: python

            [-0.009100092574954033, 0.005071679595857859, -0.0029193938244134188]
    """

    client: Any = Field(default=None, exclude=True)  #: :meta private:
    async_client: Any = Field(default=None, exclude=True)  #: :meta private:
    model: str = "text-embedding-ada-002"
    dimensions: Optional[int] = None
    """The number of dimensions the resulting output embeddings should have.

    Only supported in `text-embedding-3` and later models.
    """
    # to support Azure OpenAI Service custom deployment names
    deployment: Optional[str] = model
    # TODO: Move to AzureOpenAIEmbeddings.
    openai_api_version: Optional[str] = Field(default=None, alias="api_version")
    """Automatically inferred from env var `OPENAI_API_VERSION` if not provided."""
    # to support Azure OpenAI Service custom endpoints
    openai_api_base: Optional[str] = Field(default=None, alias="base_url")
    """Base URL path for API requests, leave blank if not using a proxy or service
        emulator."""
    # to support Azure OpenAI Service custom endpoints
    openai_api_type: Optional[str] = None
    # to support explicit proxy for OpenAI
    openai_proxy: Optional[str] = None
    embedding_ctx_length: int = 8191
    """The maximum number of tokens to embed at once."""
    openai_api_key: Optional[SecretStr] = Field(default=None, alias="api_key")
    """Automatically inferred from env var `OPENAI_API_KEY` if not provided."""
    openai_organization: Optional[str] = Field(default=None, alias="organization")
    """Automatically inferred from env var `OPENAI_ORG_ID` if not provided."""
    allowed_special: Union[Literal["all"], Set[str], None] = None
    disallowed_special: Union[Literal["all"], Set[str], Sequence[str], None] = None
    chunk_size: int = 1000
    """Maximum number of texts to embed in each batch"""
    max_retries: int = 2
    """Maximum number of retries to make when generating."""
    request_timeout: Optional[Union[float, Tuple[float, float], Any]] = Field(
        default=None, alias="timeout"
    )
    """Timeout for requests to OpenAI completion API. Can be float, httpx.Timeout or
        None."""
    headers: Any = None
    tiktoken_enabled: bool = True
    """Set this to False for non-OpenAI implementations of the embeddings API, e.g.
    the `--extensions openai` extension for `text-generation-webui`"""
    tiktoken_model_name: Optional[str] = None
    """The model name to pass to tiktoken when using this class.
    Tiktoken is used to count the number of tokens in documents to constrain
    them to be under a certain limit. By default, when set to None, this will
    be the same as the embedding model name. However, there are some cases
    where you may want to use this Embedding class with a model name not
    supported by tiktoken. This can include when using Azure embeddings or
    when using one of the many model providers that expose an OpenAI-like
    API but with different models. In those cases, in order to avoid erroring
    when tiktoken is called, you can specify a model name to use here."""
    show_progress_bar: bool = False
    """Whether to show a progress bar when embedding."""
    model_kwargs: Dict[str, Any] = Field(default_factory=dict)
    """Holds any model parameters valid for `create` call not explicitly specified."""
    skip_empty: bool = False
    """Whether to skip empty strings when embedding or raise an error.
    Defaults to not skipping."""
    default_headers: Union[Mapping[str, str], None] = None
    default_query: Union[Mapping[str, object], None] = None
    # Configure a custom httpx client. See the
    # [httpx documentation](https://www.python-httpx.org/api/#client) for more details.
    retry_min_seconds: int = 4
    """Min number of seconds to wait between retries"""
    retry_max_seconds: int = 20
    """Max number of seconds to wait between retries"""
    http_client: Union[Any, None] = None
    """Optional httpx.Client. Only used for sync invocations. Must specify 
        http_async_client as well if you'd like a custom client for async invocations.
    """
    http_async_client: Union[Any, None] = None
    """Optional httpx.AsyncClient. Only used for async invocations. Must specify 
        http_client as well if you'd like a custom client for sync invocations."""
    check_embedding_ctx_length: bool = True
    """Whether to check the token length of inputs and automatically split inputs 
        longer than embedding_ctx_length."""
    max_concurrency: Optional[int] = None
    """Maximum number of coroutines to run concurrently.
    
    Only used for ``aembed_documents()``.
    """

    class Config:
        """Configuration for this pydantic object."""

        extra = "forbid"
        allow_population_by_field_name = True

    @root_validator(pre=True)
    def build_extra(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Build extra kwargs from additional params that were passed in."""
        all_required_field_names = get_pydantic_field_names(cls)
        extra = values.get("model_kwargs", {})
        for field_name in list(values):
            if field_name in extra:
                raise ValueError(f"Found {field_name} supplied twice.")
            if field_name not in all_required_field_names:
                warnings.warn(
                    f"""WARNING! {field_name} is not default parameter.
                    {field_name} was transferred to model_kwargs.
                    Please confirm that {field_name} is what you intended."""
                )
                extra[field_name] = values.pop(field_name)

        invalid_model_kwargs = all_required_field_names.intersection(extra.keys())
        if invalid_model_kwargs:
            raise ValueError(
                f"Parameters {invalid_model_kwargs} should be specified explicitly. "
                f"Instead they were passed in as part of `model_kwargs` parameter."
            )

        values["model_kwargs"] = extra
        return values

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key and python package exists in environment."""
        openai_api_key = get_from_dict_or_env(
            values, "openai_api_key", "OPENAI_API_KEY"
        )
        values["openai_api_key"] = (
            convert_to_secret_str(openai_api_key) if openai_api_key else None
        )
        values["openai_api_base"] = values["openai_api_base"] or os.getenv(
            "OPENAI_API_BASE"
        )
        values["openai_api_type"] = get_from_dict_or_env(
            values, "openai_api_type", "OPENAI_API_TYPE", default=""
        )
        values["openai_proxy"] = get_from_dict_or_env(
            values, "openai_proxy", "OPENAI_PROXY", default=""
        )
        values["openai_api_version"] = get_from_dict_or_env(
            values, "openai_api_version", "OPENAI_API_VERSION", default=""
        )
        # Check OPENAI_ORGANIZATION for backwards compatibility.
        values["openai_organization"] = (
            values["openai_organization"]
            or os.getenv("OPENAI_ORG_ID")
            or os.getenv("OPENAI_ORGANIZATION")
        )
        if values["openai_api_type"] in ("azure", "azure_ad", "azuread"):
            raise ValueError(
                "If you are using Azure, "
                "please use the `AzureOpenAIEmbeddings` class."
            )
        client_params = {
            "api_key": (
                values["openai_api_key"].get_secret_value()
                if values["openai_api_key"]
                else None
            ),
            "organization": values["openai_organization"],
            "base_url": values["openai_api_base"],
            "timeout": values["request_timeout"],
            "max_retries": values["max_retries"],
            "default_headers": values["default_headers"],
            "default_query": values["default_query"],
        }

        if values["openai_proxy"] and (
            values["http_client"] or values["http_async_client"]
        ):
            openai_proxy = values["openai_proxy"]
            http_client = values["http_client"]
            http_async_client = values["http_async_client"]
            raise ValueError(
                "Cannot specify 'openai_proxy' if one of "
                "'http_client'/'http_async_client' is already specified. Received:\n"
                f"{openai_proxy=}\n{http_client=}\n{http_async_client=}"
            )
        if not values.get("client"):
            if values["openai_proxy"] and not values["http_client"]:
                try:
                    import httpx
                except ImportError as e:
                    raise ImportError(
                        "Could not import httpx python package. "
                        "Please install it with `pip install httpx`."
                    ) from e
                values["http_client"] = httpx.Client(proxy=values["openai_proxy"])
            sync_specific = {"http_client": values["http_client"]}
            values["client"] = openai.OpenAI(
                **client_params, **sync_specific
            ).embeddings
        if not values.get("async_client"):
            if values["openai_proxy"] and not values["http_async_client"]:
                try:
                    import httpx
                except ImportError as e:
                    raise ImportError(
                        "Could not import httpx python package. "
                        "Please install it with `pip install httpx`."
                    ) from e
                values["http_async_client"] = httpx.AsyncClient(
                    proxy=values["openai_proxy"]
                )
            async_specific = {"http_client": values["http_async_client"]}
            values["async_client"] = openai.AsyncOpenAI(
                **client_params, **async_specific
            ).embeddings
        return values

    @property
    def _invocation_params(self) -> Dict[str, Any]:
        params: Dict = {"model": self.model, **self.model_kwargs}
        if self.dimensions is not None:
            params["dimensions"] = self.dimensions
        return params

    def _tokenize_and_split(
        self, texts: List[str]
    ) -> Tuple[List[Union[List[int], str]], List[int]]:
        """
        Tokenize and split the input texts to be shorter than max ctx length.

        Each individual text is also split into multiple texts based on the
        `embedding_ctx_length` parameter (based on number of tokens).

        Returns:
            This function returns a 2-tuple of the following:
                split_tokens: A list of tokenized texts, where each text has already
                    been split into sub-texts based on the `embedding_ctx_length`
                    parameter. In the case of tiktoken, this is a list of token arrays.
                    In the case of HuggingFace transformers, this is a list of strings.
                indices: An iterable of the same length as `split_tokens` that maps
                    each token array to the index of the original text in `texts`.
        """
        # If tiktoken flag set to False
        if not self.tiktoken_enabled:
            return self._transformers_tokenize_and_split(texts)
        else:
            return self._tiktoken_tokenize_and_split(texts)

    def _transformers_tokenize_and_split(
        self, texts: List[str]
    ) -> Tuple[List[Union[List[int], str]], List[int]]:
        tokens: List[Union[List[int], str]] = []
        indices: List[int] = []
        model_name = self.tiktoken_model_name or self.model

        try:
            from transformers import AutoTokenizer
        except ImportError:
            raise ValueError(
                "Could not import transformers python package. "
                "This is needed for OpenAIEmbeddings to work without "
                "`tiktoken`. Please install it with `pip install transformers`. "
            )

        tokenizer = AutoTokenizer.from_pretrained(
            pretrained_model_name_or_path=model_name
        )
        for i, text in enumerate(texts):
            # Tokenize the text using HuggingFace transformers
            tokenized: List[int] = tokenizer.encode(text, add_special_tokens=False)

            # Split tokens into chunks respecting the embedding_ctx_length
            for j in range(0, len(tokenized), self.embedding_ctx_length):
                token_chunk: List[int] = tokenized[j : j + self.embedding_ctx_length]

                # Convert token IDs back to a string
                chunk_text: str = tokenizer.decode(token_chunk)
                tokens.append(chunk_text)
                indices.append(i)
        return tokens, indices

    def _tiktoken_tokenize_and_split(
        self, texts: List[str]
    ) -> Tuple[List[Union[List[int], str]], List[int]]:
        tokens: List[Union[List[int], str]] = []
        indices: List[int] = []
        model_name = self.tiktoken_model_name or self.model
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        encoder_kwargs: Dict = {
            "allowed_special": self.allowed_special,
            "disallowed_special": self.disallowed_special,
        }
        encoder_kwargs = {k: v for k, v in encoder_kwargs.items() if v is not None}
        for i, text in enumerate(texts):
            if self.model.endswith("001"):
                # See: https://github.com/openai/openai-python/
                #      issues/418#issuecomment-1525939500
                # replace newlines, which can negatively affect performance.
                text = text.replace("\n", " ")

            if encoder_kwargs:
                token = encoding.encode(text, **encoder_kwargs)
            else:
                token = encoding.encode_ordinary(text)

            # Split tokens into chunks respecting the embedding_ctx_length
            for j in range(0, len(token), self.embedding_ctx_length):
                tokens.append(token[j : j + self.embedding_ctx_length])
                indices.append(i)

        return tokens, indices

    # Inspired by
    # https://github.com/openai/openai-cookbook/blob/main/examples/Embedding_long_inputs.ipynb
    def _get_len_safe_embeddings(
        self,
        num_texts: int,
        split_tokens: List[Union[List[int], str]],
        split_to_text_indices: List[int],
        *,
        chunk_size: Optional[int] = None,
    ) -> List[List[float]]:
        """
        Generate length-safe embeddings for a list of texts.

        This method handles tokenization and embedding generation, respecting the
        set embedding context length and chunk size. It supports both tiktoken
        and HuggingFace tokenizer based on the tiktoken_enabled flag.

        Args:
            num_texts : Number of original texts.
            split_tokens: Tokenized splits of the texts.
            split_to_text_indices: Index of the original text that each token split
                corresponds to.
            chunk_size: Maximum number of texts to embed in each batch.

        Returns:
            List[List[float]]: A list of embeddings for each input text.
        """
        split_embeddings = self._get_embeddings(split_tokens, chunk_size=chunk_size)
        averaged_embeddings = _process_split_embeddings(
            num_texts,
            split_tokens,
            split_embeddings,
            split_to_text_indices,
            self.skip_empty,
        )
        _cached_empty_embedding: Optional[List[float]] = None

        def empty_embedding() -> List[float]:
            nonlocal _cached_empty_embedding
            if _cached_empty_embedding is None:
                _cached_empty_embedding = self._get_embeddings([""])[0]
            return _cached_empty_embedding

        return [e if e is not None else empty_embedding() for e in averaged_embeddings]

    # Inspired by
    # https://github.com/openai/openai-cookbook/blob/main/examples/Embedding_long_inputs.ipynb
    async def _aget_len_safe_embeddings(
        self,
        num_texts: int,
        split_tokens: List[Union[List[int], str]],
        split_to_text_indices: List[int],
        *,
        chunk_size: Optional[int] = None,
        max_concurrency: Optional[int] = None,
    ) -> List[List[float]]:
        """
        Generate length-safe embeddings for a list of texts.

        This method handles tokenization and embedding generation, respecting the
        set embedding context length and chunk size. It supports both tiktoken
        and HuggingFace tokenizer based on the tiktoken_enabled flag.

        Args:
            num_texts : Number of original texts.
            split_tokens: Tokenized splits of the texts.
            split_to_text_indices: Index of the original text that each token split
                corresponds to.
            chunk_size: Maximum number of texts to embed in each batch.

        Returns:
            List[List[float]]: A list of embeddings for each input text.
        """
        split_embeddings = await self._aget_embeddings(
            split_tokens, chunk_size=chunk_size, max_concurrency=max_concurrency
        )
        averaged_embeddings = _process_split_embeddings(
            num_texts,
            split_tokens,
            split_embeddings,
            split_to_text_indices,
            self.skip_empty,
        )
        _cached_empty_embedding: Optional[List[float]] = None

        async def empty_embedding() -> List[float]:
            nonlocal _cached_empty_embedding
            if _cached_empty_embedding is None:
                _cached_empty_embedding = (await self._aget_embeddings([""]))[0]
            return _cached_empty_embedding

        return [
            e if e is not None else (await empty_embedding())
            for e in averaged_embeddings
        ]

    def embed_documents(
        self, texts: List[str], chunk_size: Optional[int] = None
    ) -> List[List[float]]:
        """Call out to OpenAI's embedding endpoint for embedding search docs.

        Args:
            texts: The list of texts to embed.
            chunk_size: The chunk size of embeddings. If None, will use the chunk size
                specified by the class.

        Returns:
            List of embeddings, one for each text.
        """
        if not self.check_embedding_ctx_length:
            return self._get_embeddings(texts, chunk_size=chunk_size)

        num_texts = len(texts)
        split_tokens, embedding_to_text_indices = self._tokenize_and_split(texts)
        if len(split_tokens) == num_texts:
            return self._get_embeddings(texts, chunk_size=chunk_size)

        return self._get_len_safe_embeddings(
            num_texts, split_tokens, embedding_to_text_indices, chunk_size=chunk_size
        )

    async def aembed_documents(
        self,
        texts: List[str],
        chunk_size: Optional[int] = None,
        *,
        max_concurrency: Optional[int] = None,
    ) -> List[List[float]]:
        """Call out to OpenAI's embedding endpoint async for embedding search docs.

        Args:
            texts: The list of texts to embed.
            chunk_size: The chunk size of embeddings. If None, will use the chunk size
                specified by the class.

        Returns:
            List of embeddings, one for each text.
        """
        max_concurrency = (
            max_concurrency if max_concurrency is not None else self.max_concurrency
        )
        if not self.check_embedding_ctx_length:
            return await self._aget_embeddings(
                texts, chunk_size=chunk_size, max_concurrency=max_concurrency
            )

        num_texts = len(texts)
        split_tokens, embedding_to_text_indices = self._tokenize_and_split(texts)
        if len(split_tokens) == num_texts:
            return await self._aget_embeddings(
                texts, chunk_size=chunk_size, max_concurrency=max_concurrency
            )

        return await self._aget_len_safe_embeddings(
            num_texts,
            split_tokens,
            embedding_to_text_indices,
            chunk_size=chunk_size,
            max_concurrency=max_concurrency,
        )

    def embed_query(self, text: str) -> List[float]:
        """Call out to OpenAI's embedding endpoint for embedding query text.

        Args:
            text: The text to embed.

        Returns:
            Embedding for the text.
        """
        return self.embed_documents([text])[0]

    async def aembed_query(self, text: str) -> List[float]:
        """Call out to OpenAI's embedding endpoint async for embedding query text.

        Args:
            text: The text to embed.

        Returns:
            Embedding for the text.
        """
        embeddings = await self.aembed_documents([text])
        return embeddings[0]

    def _get_embeddings(
        self,
        input: Sequence[Union[List[int], str]],
        *,
        chunk_size: Optional[int] = None,
    ) -> List[List[float]]:
        embeddings: List[List[float]] = []
        chunk_size = chunk_size or self.chunk_size
        _iter: Iterable = range(0, len(input), chunk_size)
        if self.show_progress_bar:
            try:
                from tqdm.auto import tqdm
            except ImportError:
                pass
            else:
                _iter = tqdm(_iter)
        for chunk_start in _iter:
            chunk_end = chunk_start + chunk_size
            response = self.client.create(
                input=input[chunk_start:chunk_end], **self._invocation_params
            )
            if not isinstance(response, dict):
                if hasattr(response, "model_dump"):
                    response = response.model_dump()
                else:
                    response = response.dict()
            embeddings.extend(r["embedding"] for r in response["data"])
        return embeddings

    async def _aget_embeddings(
        self,
        input: Sequence[Union[List[int], str]],
        *,
        chunk_size: Optional[int] = None,
        max_concurrency: Optional[int] = None,
    ) -> List[List[float]]:
        chunk_size = chunk_size or self.chunk_size
        responses = await gather_with_concurrency(
            max_concurrency,
            *(
                self.async_client.create(
                    input=input[start : start + chunk_size], **self._invocation_params
                )
                for start in range(0, len(input), chunk_size)
            ),
        )
        embeddings: List = []
        for res in responses:
            if not isinstance(res, dict):
                res = res.model_dump() if hasattr(res, "model_dump") else res.dict()
            embeddings.extend(r["embedding"] for r in res["data"])
        return embeddings


def _normed_vector_avg(vectors: List[List[float]], weights: List[int]) -> List[float]:
    # should be same as
    # np.average(vectors, axis=0, weights=weights)
    total_weight = sum(weights)
    averaged = []
    for transposed_vec in zip(*vectors):
        avg_ = sum(v * w for v, w in zip(transposed_vec, weights)) / total_weight
        averaged.append(avg_)

    return _vector_norm(averaged)


def _vector_norm(vector: List[float]) -> List[float]:
    # should be same as
    # (np.array(vector) / np.linalg.norm(vector)).tolist()
    magnitude = sum(x**2 for x in vector) ** 0.5
    return [x / magnitude for x in vector]
