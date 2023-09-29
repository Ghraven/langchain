import json
from typing import Any

import pytest

from langchain.schema.messages import (
    HumanMessage,
    SystemMessage,
    HumanMessageChunk,
)
from langserve.custom_json import LangChainEncoder, LangChainDecoder


@pytest.mark.parametrize(
    "data, expected_json",
    [
        # Test with python primitives
        (1, 1),
        ([], []),
        ({}, {}),
        ({"a": 1}, {"a": 1}),
        # Test with a single message (HumanMessage)
        (
            HumanMessage(content="Hello"),
            {
                "additional_kwargs": {},
                "content": "Hello",
                "example": False,
                "type": "human",
            },
        ),
        # Test with a list containing mixed elements
        (
            [HumanMessage(content="Hello"), SystemMessage(content="Hi"), 42, "world"],
            [
                {
                    "additional_kwargs": {},
                    "content": "Hello",
                    "example": False,
                    "type": "human",
                },
                {"additional_kwargs": {}, "content": "Hi", "type": "system"},
                42,
                "world",
            ],
        ),
        # # Attention: This test is not correct right now
        # # Test with full and chunk messages
        # (
        #     [HumanMessage(content="Hello"), HumanMessageChunk(content="Hi")],
        #     [
        #         {
        #             "additional_kwargs": {},
        #             "content": "Hello",
        #             "example": False,
        #             "type": "human",
        #         },
        #         {
        #             "additional_kwargs": {},
        #             "content": "Hi",
        #             "example": False,
        #             "type": "human",
        #         },
        #     ],
        # ),
        # # Attention: This test is not correct right now
        # # Test with full and chunk messages
        # (
        #     [HumanMessageChunk(content="Hello"), HumanMessage(content="Hi")],
        #     [
        #         {
        #             "additional_kwargs": {},
        #             "content": "Hello",
        #             "example": False,
        #             "type": "human",
        #         },
        #         {
        #             "additional_kwargs": {},
        #             "content": "Hi",
        #             "example": False,
        #             "type": "human",
        #         },
        #     ],
        # ),
        # Test with a dictionary containing mixed elements
        (
            {
                "message": HumanMessage(content="Greetings"),
                "numbers": [1, 2, 3],
                "text": "Hello, world!",
            },
            {
                "message": {
                    "additional_kwargs": {},
                    "content": "Greetings",
                    "example": False,
                    "type": "human",
                },
                "numbers": [1, 2, 3],
                "text": "Hello, world!",
            },
        ),
    ],
)
def test_serialization(data: Any, expected_json: Any) -> None:
    """Test that the LangChainEncoder encodes the data as expected."""
    # Test encoding
    assert json.loads(LangChainEncoder().encode(data)) == expected_json
    # Test decoding
    assert LangChainDecoder().decode(json.dumps(expected_json)) == data
