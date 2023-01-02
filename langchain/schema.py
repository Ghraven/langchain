"""Common schema objects."""

from typing import List, NamedTuple, Optional
from dataclasses_json import dataclass_json
from dataclasses import dataclass


class AgentAction(NamedTuple):
    """Agent's action to take."""

    tool: str
    tool_input: str
    log: str


class AgentFinish(NamedTuple):
    """Agent's return value."""

    log: str
    return_values: dict


@dataclass_json
@dataclass
class Generation:
    """Output of a single generation."""

    text: str
    """Generated text output."""
    # TODO: add log probs


@dataclass_json
@dataclass
class LLMResult:
    """Class that contains all relevant information for an LLM Result."""

    generations: List[List[Generation]]
    """List of the things generated. This is List[List[]] because
    each input could have multiple generations."""
    llm_output: Optional[dict] = None
    """For arbitrary LLM provider specific output."""
