"""Test Upstage Chat API wrapper."""
import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import (
    AIMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
)

from langchain_community.chat_models.openai import ChatOpenAI
from langchain_community.chat_model.upstage import ChatUpstage


@pytest.mark.requires("openai")
def test_openai_model_param() -> None:
    llm = ChatOpenAI(model="foo")
    assert llm.model_name == "foo"
    llm = ChatOpenAI(model_name="foo")
    assert llm.model_name == "foo"


@pytest.fixture
def mock_completion() -> dict:
    return {
        "id": "chatcmpl-7fcZavknQda3SQ",
        "object": "chat.completion",
        "created": 1689989000,
        "model": "gpt-3.5-turbo-0613",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Bar Baz",
                },
                "finish_reason": "stop",
            }
        ],
    }


@pytest.mark.requires("openai")
def test_openai_predict(mock_completion: dict) -> None:
    llm = ChatOpenAI()
    mock_client = MagicMock()
    completed = False

    def mock_create(*args: Any, **kwargs: Any) -> Any:
        nonlocal completed
        completed = True
        return mock_completion

    mock_client.create = mock_create
    with patch.object(
        llm,
        "client",
        mock_client,
    ):
        res = llm.predict("bar")
        assert res == "Bar Baz"
    assert completed


@pytest.mark.requires("openai")
async def test_openai_apredict(mock_completion: dict) -> None:
    llm = ChatOpenAI()
    mock_client = MagicMock()
    completed = False

    def mock_create(*args: Any, **kwargs: Any) -> Any:
        nonlocal completed
        completed = True
        return mock_completion

    mock_client.create = mock_create
    with patch.object(
        llm,
        "client",
        mock_client,
    ):
        res = llm.predict("bar")
        assert res == "Bar Baz"
    assert completed
