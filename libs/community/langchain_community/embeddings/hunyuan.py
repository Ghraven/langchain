import json
import time
from typing import Any, Dict, List, Literal, Type

from langchain_core.embeddings import Embeddings
from langchain_core.pydantic_v1 import BaseModel, Field, SecretStr, root_validator
from langchain_core.runnables.config import run_in_executor
from langchain_core.utils import convert_to_secret_str, get_from_dict_or_env
from tqdm import tqdm


class HunyuanEmbeddings(Embeddings, BaseModel):
    tencent_cloud_secret_id: SecretStr = Field(alias="secret_id", default=None)
    tencent_cloud_secret_key: SecretStr = Field(alias="secret_key", default=None)

    region: Literal["ap-guangzhou", "ap-beijing"] = "ap-guangzhou"

    embedding_ctx_length: int = 1024
    max_retries: int = 5

    show_progress_bar: bool = False

    request_cls: Type = Field(default=None, exclude=True)

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key and python package exists in environment."""
        values["tencent_cloud_secret_id"] = convert_to_secret_str(
            get_from_dict_or_env(
                values,
                "tencent_cloud_secret_id",
                "TENCENT_CLOUD_SECRET_ID",
            )
        )
        values["tencent_cloud_secret_key"] = convert_to_secret_str(
            get_from_dict_or_env(
                values,
                "tencent_cloud_secret_key",
                "TENCENT_CLOUD_SECRET_KEY",
            )
        )
        # Check OPENAI_ORGANIZATION for backwards compatibility.

        try:
            from tencentcloud.common.credential import Credential
            from tencentcloud.common.profile.client_profile import ClientProfile
            from tencentcloud.hunyuan.v20230901.hunyuan_client import HunyuanClient
            from tencentcloud.hunyuan.v20230901.models import GetEmbeddingRequest
        except ImportError:
            raise ImportError("Could not import tencentcloud sdk python package. " "Please install it with `pip install tencentcloud-sdk-python`.")

        client_profile = ClientProfile()
        client_profile.httpProfile.pre_conn_pool_size = 3

        credential = Credential(values["tencent_cloud_secret_id"].get_secret_value(), values["tencent_cloud_secret_key"].get_secret_value())

        values["request_cls"] = GetEmbeddingRequest
        values["client"] = HunyuanClient(credential, values["region"], client_profile)
        return values

    def _embed_text(self, text: str) -> List[float]:
        request = self.request_cls()
        request.Input = text

        retry_sec = 1
        response = None
        for _ in range(self.max_retries):
            try:
                response = self.client.GetEmbedding(request)
            except Exception:
                time.sleep(retry_sec)
                retry_sec <<= 1
            else:
                break

        if not response:
            raise RuntimeError("Hunyuan embedding error: Retry time exceed")

        _response: Dict[str, Any] = json.loads(response.to_json_string())

        data: List[Dict[str, Any]] | None = _response.get("Data")
        if not data:
            raise RuntimeError("Occur hunyuan embedding error: Data is empty")

        embedding = data[0].get("Embedding")
        if not embedding:
            raise RuntimeError("Occur hunyuan embedding error: Embedding is empty")

        return embedding

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed search docs."""
        embeddings = []
        if self.show_progress_bar:
            _iter = tqdm(iterable=texts, desc="Hunyuan Embedding")
        else:
            _iter = texts
        for text in _iter:
            embeddings.append(self.embed_query(text))

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embed query text."""
        return self._embed_text(text)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Asynchronous Embed search docs."""
        return await run_in_executor(None, self.embed_documents, texts)

    async def aembed_query(self, text: str) -> List[float]:
        """Asynchronous Embed query text."""
        return await run_in_executor(None, self.embed_query, text)
