"""Chat Model Components Derived from ChatModel/NVAIPlay"""

import asyncio
from collections import abc
from typing import Any, Dict, List, Literal

from langchain.llms.nv_aiplay import ClientModel, NVCRModel
from langchain.pydantic_v1 import Field, root_validator
from langchain.schema.embeddings import Embeddings

## NOTE: This file should not be ran in isolation as a single-file standalone.
## Please use llms.nv_aiplay instead.


class NVAIPlayEmbeddings(ClientModel, Embeddings):
    """NVIDIA's AI Playground NVOLVE Question-Answer Asymmetric Model."""

    client: NVCRModel = Field(NVCRModel)
    model: str = Field("nvolveqa")
    max_length: int = Field(2048, ge=1, le=2048)

    @root_validator()
    def validate_model(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values["client"] = values["client"](**values)
        return values

    def _embed(self, text: str, model_type: Literal["passage", "query"]) -> List[float]:
        """Embed a single text entry to either passage or query type"""
        if len(text) > self.max_length:
            text = text[: self.max_length]
        output = self.client.get_req_generation(
            model_name=self.model,
            payload={
                "input": text,
                "model": model_type,
                "encoding_format": "float",
            },
        )
        return output.get("embedding", [])

    def embed_query(self, text: str) -> List[float]:
        """Input pathway for query embeddings."""
        return self._embed(text, model_type="query")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Input pathway for document embeddings."""
        return [self._embed(text, model_type="passage") for text in texts]

    async def aembed_batch_queries(
        self,
        texts: List[str],
        max_concurrency: int = 10,
    ) -> List[List[float]]:
        """Embed search queries with Asynchronous Batching and Concurrency Control."""
        semaphore = asyncio.Semaphore(max_concurrency)

        async def embed_with_semaphore(text: str) -> abc.Coroutine:
            async with semaphore:
                return await self.aembed_query(text)

        tasks = [embed_with_semaphore(text) for text in texts]
        return await asyncio.gather(*tasks)

    async def aembed_batch_documents(
        self,
        texts: List[str],
        max_concurrency: int = 10,
    ) -> List[List[float]]:
        """Embed search docs with Asynchronous Batching and Concurrency Control."""
        semaphore = asyncio.Semaphore(max_concurrency)

        async def embed_with_semaphore(text: str) -> abc.Coroutine:
            async with semaphore:
                return await self.aembed_documents([text])

        tasks = [embed_with_semaphore(text) for text in texts]
        outs = await asyncio.gather(*tasks)
        return [out[0] for out in outs]
