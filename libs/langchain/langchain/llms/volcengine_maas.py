from typing import TYPE_CHECKING, Any

from langchain._api import create_importer

if TYPE_CHECKING:
    from langchain_community.llms import VolcEngineMaasLLM, VolcEngineMaasLLMV3
    from langchain_community.llms.volcengine_maas import (
        VolcEngineMaasBase,
        VolcEngineMaasBaseV3,
    )

# Create a way to dynamically look up deprecated imports.
# Used to consolidate logic for raising deprecation warnings and
# handling optional imports.
DEPRECATED_LOOKUP = {
    "VolcEngineMaasBase": "langchain_community.llms.volcengine_maas",
    "VolcEngineMaasBaseV3": "langchain_community.llms.volcengine_maas",
    "VolcEngineMaasLLM": "langchain_community.llms",
    "VolcEngineMaasLLMV3": "langchain_community.llms",
}

_import_attribute = create_importer(__package__, deprecated_lookups=DEPRECATED_LOOKUP)


def __getattr__(name: str) -> Any:
    """Look up attributes dynamically."""
    return _import_attribute(name)


__all__ = [
    "VolcEngineMaasBase",
    "VolcEngineMaasBaseV3",
    "VolcEngineMaasLLM",
    "VolcEngineMaasLLMV3",
]
