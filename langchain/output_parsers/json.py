from __future__ import annotations

import json
import re
from typing import List

from langchain.schema import OutputParserException


def parse_json_markdown(json_string: str) -> dict:
    # Try to find JSON string within triple backticks

    # The amount of backticks at the end of the LLM response can vary,
    # so we use a regex to match what we want even if we have fewer than 3 backticks
    # As a tradeoff, we might fetch some backticks in the command below: match.group(2)
    # We will get rid of them using rstrip() later
    match = re.search(r"```(json)?(.*)(`{1,3})?", json_string, re.DOTALL)

    # If no match found, assume the entire string is a JSON string
    if match is None:
        json_str = json_string
    else:
        # If match found, use the content within the backticks
        json_str = match.group(2)
        # In case we have picked some trailing backticks, get rid of them
        json_str = json_str.rstrip("`")

    # Strip whitespace and newlines from the start and end
    json_str = json_str.strip()

    # Parse the JSON string into a Python dictionary
    parsed = json.loads(json_str)

    return parsed


def parse_and_check_json_markdown(text: str, expected_keys: List[str]) -> dict:
    try:
        json_obj = parse_json_markdown(text)
    except json.JSONDecodeError as e:
        raise OutputParserException(f"Got invalid JSON object. Error: {e}")
    for key in expected_keys:
        if key not in json_obj:
            raise OutputParserException(
                f"Got invalid return object. Expected key `{key}` "
                f"to be present, but got {json_obj}"
            )
    return json_obj
