from typing import Any, Dict, List, Optional

from langchain_core.embeddings import Embeddings
from langchain_core.pydantic_v1 import BaseModel, root_validator
from langchain_core.utils import get_from_dict_or_env
from packaging.version import parse

__all__ = ["GradientEmbeddings"]


class GradientEmbeddings(BaseModel, Embeddings):
    """Gradient.ai Embedding models.

    GradientLLM is a class to interact with Embedding Models on gradient.ai

    To use, set the environment variable ``GRADIENT_ACCESS_TOKEN`` with your
    API token and ``GRADIENT_WORKSPACE_ID`` for your gradient workspace,
    or alternatively provide them as keywords to the constructor of this class.

    Example:
        .. code-block:: python

            from langchain_community.embeddings import GradientEmbeddings
            GradientEmbeddings(
                model="bge-large",
                gradient_workspace_id="12345614fc0_workspace",
                gradient_access_token="gradientai-access_token",
            )
    """

    model: str
    "Underlying gradient.ai model id."

    gradient_workspace_id: Optional[str] = None
    "Underlying gradient.ai workspace_id."

    gradient_access_token: Optional[str] = None
    """gradient.ai API Token, which can be generated by going to
        https://auth.gradient.ai/select-workspace
        and selecting "Access tokens" under the profile drop-down.
    """

    gradient_api_url: str = "https://api.gradient.ai/api"
    """Endpoint URL to use."""

    query_prompt_for_retrieval: Optional[str] = None
    """Query pre-prompt"""

    client: Any = None  #: :meta private:
    """Gradient client."""

    # LLM call kwargs
    class Config:
        extra = "forbid"

    @root_validator(allow_reuse=True)
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key and python package exists in environment."""

        values["gradient_access_token"] = get_from_dict_or_env(
            values, "gradient_access_token", "GRADIENT_ACCESS_TOKEN"
        )
        values["gradient_workspace_id"] = get_from_dict_or_env(
            values, "gradient_workspace_id", "GRADIENT_WORKSPACE_ID"
        )

        values["gradient_api_url"] = get_from_dict_or_env(
            values, "gradient_api_url", "GRADIENT_API_URL"
        )
        try:
            import gradientai
        except ImportError:
            raise ImportError(
                'GradientEmbeddings requires `pip install -U "gradientai>=1.4.0"`.'
            )

        if parse(gradientai.__version__) < parse("1.4.0"):
            raise ImportError(
                'GradientEmbeddings requires `pip install -U "gradientai>=1.4.0"`.'
            )

        gradient = gradientai.Gradient(
            access_token=values["gradient_access_token"],
            workspace_id=values["gradient_workspace_id"],
            host=values["gradient_api_url"],
        )
        values["client"] = gradient.get_embeddings_model(slug=values["model"])

        return values

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Call out to Gradient's embedding endpoint.

        Args:
            texts: The list of texts to embed.

        Returns:
            List of embeddings, one for each text.
        """
        inputs = [{"input": text} for text in texts]

        result = self.client.embed(inputs=inputs).embeddings

        return [e.embedding for e in result]

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Async call out to Gradient's embedding endpoint.

        Args:
            texts: The list of texts to embed.

        Returns:
            List of embeddings, one for each text.
        """
        inputs = [{"input": text} for text in texts]

        result = (await self.client.aembed(inputs=inputs)).embeddings

        return [e.embedding for e in result]

    def embed_query(self, text: str) -> List[float]:
        """Call out to Gradient's embedding endpoint.

        Args:
            text: The text to embed.

        Returns:
            Embeddings for the text.
        """
        query = (
            f"{self.query_prompt_for_retrieval} {text}"
            if self.query_prompt_for_retrieval
            else text
        )
        return self.embed_documents([query])[0]

    async def aembed_query(self, text: str) -> List[float]:
        """Async call out to Gradient's embedding endpoint.

        Args:
            text: The text to embed.

        Returns:
            Embeddings for the text.
        """
        query = (
            f"{self.query_prompt_for_retrieval} {text}"
            if self.query_prompt_for_retrieval
            else text
        )
        embeddings = await self.aembed_documents([query])
        return embeddings[0]


class TinyAsyncGradientEmbeddingClient:  #: :meta private:
    """Deprecated, TinyAsyncGradientEmbeddingClient was removed.

    This class is just for backwards compatibility with older versions
    of langchain_community.
    It might be entirely removed in the future.
    """

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        raise ValueError("Deprecated,TinyAsyncGradientEmbeddingClient was removed.")
