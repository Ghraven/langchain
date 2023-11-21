from typing import Any, Dict, List

from langchain.pydantic_v1 import BaseModel, Extra, Field
from langchain.schema.cross_encoder import CrossEncoder

DEFAULT_MODEL_NAME = "BAAI/bge-reranker-base"


class HuggingFaceCrossEncoder(BaseModel, CrossEncoder):
    """HuggingFace cross encoder models.

    Example:
        .. code-block:: python

            from langchain.cross_encoders import HuggingFaceCrossEncoder

            model_name = "BAAI/bge-reranker-base"
            model_kwargs = {'device': 'cpu'}
            hf = HuggingFaceCrossEncoder(
                model_name=model_name,
                model_kwargs=model_kwargs
            )
    """

    client: Any  #: :meta private:
    model_name: str = DEFAULT_MODEL_NAME
    """Model name to use."""
    model_kwargs: Dict[str, Any] = Field(default_factory=dict)
    """Keyword arguments to pass to the model."""

    def __init__(self, **kwargs: Any):
        """Initialize the sentence_transformer."""
        super().__init__(**kwargs)
        try:
            import sentence_transformers

        except ImportError as exc:
            raise ImportError(
                "Could not import sentence_transformers python package. "
                "Please install it with `pip install sentence-transformers`."
            ) from exc

        self.client = sentence_transformers.CrossEncoder(
            self.model_name, **self.model_kwargs
        )

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid

    def score(self, pairs: List[List[str]]) -> List[float]:
        """Compute similarity scores using a HuggingFace transformer model.

        Args:
            pairs: The list of text pairs to score the similarity.

        Returns:
            List of scores, one for each pair.
        """
        scores = self.client.predict(pairs)
        return scores
