"""Azure Mistral AI chat wrapper."""

from __future__ import annotations

import logging
import os
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Type,
    TypedDict,
    Union,
)

from pydantic import BaseModel, Field, SecretStr, model_validator
from typing_extensions import Self

from langchain_core.utils import from_env, secret_from_env
from langchain_core.utils.pydantic import is_basemodel_subclass
from langchain_openai.chat_models.base import ChatMistralAI

logger = logging.getLogger(__name__)


def _is_pydantic_class(obj: Any) -> bool:
    return isinstance(obj, type) and is_basemodel_subclass(obj)


class AzureChatMistralAI(ChatMistralAI):
    """Azure Mistral AI chat model integration.

    This class wraps the Mistral AI model to be used on Azure endpoints, following
    a structure similar to the `AzureChatOpenAI` class.

    Setup:
        Similar to how Azure ChatOpenAI is set up, this class expects environment
        variables `AZURE_MISTRAL_API_KEY` and `AZURE_MISTRAL_ENDPOINT` to be set.

    Key init args - completion params:
        azure_deployment: str
            Name of Azure Mistral deployment to use.
        temperature: float
            Sampling temperature.
        max_tokens: Optional[int]
            Max number of tokens to generate.
        top_p: float
            Decodes using nucleus sampling.
        random_seed: Optional[int]
            Random seed for deterministic output.
        safe_prompt: bool
            Enable safe mode prompt.

    Key init args - client params:
        azure_endpoint: str
            Azure endpoint for the Mistral model.
        mistral_api_type: Optional[str]
            Reserved for future compatibility. Currently defaults to "azure".
        max_retries: int
            Max number of retries.
        model: Optional[str]
            The name of the underlying Mistral model used.
        mistral_api_version: Optional[str]
            The version of the underlying Mistral model used.

    Example:
        .. code-block:: python

            from langchain_openai import AzureChatMistralAI

            llm = AzureChatMistralAI(
                azure_deployment="your-deployment",
                azure_endpoint="https://your-mistral-endpoint.azure.com/",
                temperature=0.7,
                max_tokens=256,
                top_p=0.9,
                random_seed=42,
                safe_prompt=True,
                max_retries=3,
            )

        By default, the necessary values are inferred from environment variables.

    Invocations:
        .. code-block:: python

            messages = [
                ("system", "You are an insightful assistant for azure hosted Mistral AI."),
                ("human", "Could you explain what a black hole is in simple terms?")
            ]
            llm.invoke(messages)

        For streaming:
        .. code-block:: python

            for chunk in llm.stream(messages):
                print(chunk)

    """

    azure_endpoint: Optional[str] = Field(
        default_factory=from_env("AZURE_MISTRAL_ENDPOINT", default=None)
    )
    """Your Azure endpoint for Mistral, including the resource.

    Automatically inferred from env var AZURE_MISTRAL_ENDPOINT if not provided.

    Example: https://your-mistral-endpoint.azure.com/
    """

    deployment_name: Union[str, None] = Field(
        default=None, alias="deployment_name")
    """Name of your Azure Mistral deployment to use for requests."""

    mistral_api_version: Optional[str] = Field(
        alias="api_version",
        default_factory=from_env("MISTRAL_API_VERSION", default=None),
    )
    """The version of the Mistral API to use, if applicable. By default, none."""
    mistral_api_key: Optional[SecretStr] = Field(
        alias="api_key",
        default_factory=secret_from_env(
            ["AZURE_MISTRAL_API_KEY", "MISTRAL_API_KEY"], default=None
        ),
    )
    """Your Azure Mistral API key. Automatically inferred from env var AZURE_MISTRAL_API_KEY if not provided."""
    mistral_api_type: Optional[str] = Field(
        default_factory=from_env("MISTRAL_API_TYPE", default="azure")
    )

    azure_ad_token: Optional[SecretStr] = Field(
        default_factory=secret_from_env("AZURE_OPENAI_AD_TOKEN", default=None)
    )
    """Your Azure Active Directory token.

        Automatically inferred from env var `AZURE_OPENAI_AD_TOKEN` if not provided.

        For more:
        https://www.microsoft.com/en-us/security/business/identity-access/microsoft-entra-id.
    """
    azure_ad_token_provider: Union[Callable[[], str], None] = None
    """A function that returns an Azure Active Directory token.
        
        Will be invoked on every sync request. For async requests,
        will be invoked if `azure_ad_async_token_provider` is not provided.
    """
    azure_ad_async_token_provider: Union[Callable[[
    ], Awaitable[str]], None] = None
    """A function that returns an Azure Active Directory token.
        
        Will be invoked on every async request.
    """

    """Specifies the type of API for forward compatibility. Defaults to 'azure'."""
    validate_base_url: bool = True
    """Determines if the base URL (azure_endpoint) should be validated."""
    model: str = Field(default="mistral-small", alias="model_name")
    """The name of the Mistral model used. Defaults to 'mistral-base'."""

    @property
    def _azure_endpoint_url(self) -> str:
        """Constructs the full URL for the Azure Mistral endpoint."""
        if not self.azure_endpoint:
            raise ValueError(
                "Azure endpoint must be specified or set in the environment.")
        if not self.azure_deployment:
            raise ValueError("Azure deployment name must be specified.")
        # Construct URL analogous to how Azure endpoints for OpenAI are structured
        return f"{self.azure_endpoint}azureai/deployments/{self.azure_deployment}"

    @classmethod
    def get_lc_namespace(cls) -> List[str]:
        """Get the namespace of the langchain object for Azure Mistral AI."""
        return ["langchain", "chat_models", "azure_mistral"]

    @property
    def lc_secrets(self) -> Dict[str, str]:
        return {
            "mistral_api_key": "AZURE_MISTRAL_API_KEY",
        }

    @classmethod
    def is_lc_serializable(cls) -> bool:
        return True

    @model_validator(mode="after")
    def validate_environment(self) -> Self:
        """Validate that the Azure environment is properly configured for Mistral."""
        # Check mandatory fields
        if self.n < 1:
            raise ValueError("n must be at least 1.")
        if self.n > 1 and self.streaming:
            raise ValueError("n must be 1 when streaming.")

        # Check azure_endpoint and azure_deployment
        if not self.azure_endpoint:
            self.azure_endpoint = os.getenv("AZURE_MISTRAL_ENDPOINT")
        if not self.azure_deployment:
            self.azure_deployment = os.getenv("AZURE_MISTRAL_DEPLOYMENT")

        if not self.azure_endpoint:
            raise ValueError(
                "Azure Mistral endpoint not found. Set it explicitly or via AZURE_MISTRAL_ENDPOINT env variable."
            )
        if not self.azure_deployment:
            raise ValueError(
                "Azure Mistral deployment name not found. Set it explicitly or via AZURE_MISTRAL_DEPLOYMENT env variable."
            )

        # Set up the client for Azure endpoint:
        self.endpoint = self._azure_endpoint_url

        client_params: dict = {
            "mistral_api_version": self.mistral_api_version,
            "azure_endpoint": self.azure_endpoint,
            "azure_deployment": self.deployment_name,
            "api_key": (
                self.mistral_api_key.get_secret_value() if self.mistral_api_key else None
            ),
            "azure_ad_token": (
                self.azure_ad_token.get_secret_value() if self.azure_ad_token else None
            ),
            "azure_ad_token_provider": self.azure_ad_token_provider,
            # "base_url": self.mistral_api_key,
            "timeout": self.request_timeout,
            "max_retries": self.max_retries,
            "default_headers": self.default_headers,
            "default_query": self.default_query,
        }

        # if not self.client:
        #     sync_specific = {"http_client": self.http_client}
        #     self.root_client = openai.AzureOpenAI(**client_params, **sync_specific)  # type: ignore[arg-type]
        #     self.client = self.root_client.chat.completions
        # if not self.async_client:
        #     async_specific = {"http_client": self.http_async_client}
        #
        #     if self.azure_ad_async_token_provider:
        #         client_params["azure_ad_token_provider"] = (
        #             self.azure_ad_async_token_provider
        #         )
        #
        #     self.root_async_client = openai.AsyncAzureOpenAI(
        #         **client_params,
        #         **async_specific,  # type: ignore[arg-type]
        #     )
        #     self.async_client = self.root_async_client.chat.completions
        super().validate_environment()
        return self

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Combine Azure-specific parameters with parent class parameters."""
        return {
            **{"azure_deployment": self.deployment_name},
            **super()._identifying_params,
        }

    @property
    def _llm_type(self) -> str:
        return "azure-mistral-chat"

    @property
    def lc_attributes(self) -> Dict[str, Any]:
        attributes: Dict[str, Any] = super().lc_attributes
        attributes.update({
            "azure_endpoint": self.azure_endpoint,
            "azure_deployment": self.azure_deployment,
            "mistral_api_type": self.mistral_api_type,
            "mistral_api_version": self.mistral_api_version,
        })
        return attributes

    def _create_message_dicts(
        self, messages: List[BaseMessage], stop: Optional[List[str]]
    ) -> Tuple[List[Dict], Dict[str, Any]]:
        """Override method to add azure-specific parameters to the message creation."""
        message_dicts, params = super()._create_message_dicts(messages, stop)
        # Add azure deployment to parameters
        params["azure_deployment"] = self.azure_deployment
        if self.openai_api_version:
            params["api_version"] = self.openai_api_version
        return message_dicts, params
