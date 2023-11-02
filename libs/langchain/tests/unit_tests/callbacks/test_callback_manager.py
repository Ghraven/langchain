"""Test CallbackManager."""
from typing import List, Tuple
from unittest.mock import patch

import pytest

from langchain.callbacks.base import BaseCallbackHandler
from langchain.callbacks.manager import (
    AsyncCallbackManager,
    CallbackManager,
    get_openai_callback,
    trace_as_chain_group,
)
from langchain.callbacks.stdout import StdOutCallbackHandler
from langchain.callbacks.tracers.langchain import LangChainTracer
from langchain.llms.openai import BaseOpenAI
from langchain.schema import AgentAction, AgentFinish, LLMResult
from tests.unit_tests.callbacks.fake_callback_handler import (
    BaseFakeCallbackHandler,
    FakeAsyncCallbackHandler,
    FakeCallbackHandler,
)


def _test_callback_manager(
    manager: CallbackManager, *handlers: BaseFakeCallbackHandler
) -> None:
    """Test the CallbackManager."""
    run_managers = manager.on_llm_start({}, ["prompt"])
    for run_manager in run_managers:
        run_manager.on_llm_end(LLMResult(generations=[]))
        run_manager.on_llm_error(Exception())
        run_manager.on_llm_new_token("foo")
        run_manager.on_text("foo")

    run_manager_chain = manager.on_chain_start({"name": "foo"}, {})
    run_manager_chain.on_chain_end({})
    run_manager_chain.on_chain_error(Exception())
    run_manager_chain.on_agent_action(AgentAction(tool_input="foo", log="", tool=""))
    run_manager_chain.on_agent_finish(AgentFinish(log="", return_values={}))
    run_manager_chain.on_text("foo")

    run_manager_tool = manager.on_tool_start({}, "")
    run_manager_tool.on_tool_end("")
    run_manager_tool.on_tool_error(Exception())
    run_manager_tool.on_text("foo")
    _check_num_calls(handlers)


async def _test_callback_manager_async(
    manager: AsyncCallbackManager, *handlers: BaseFakeCallbackHandler
) -> None:
    """Test the CallbackManager."""
    run_managers = await manager.on_llm_start({}, ["prompt"])
    for run_manager in run_managers:
        await run_manager.on_llm_end(LLMResult(generations=[]))
        await run_manager.on_llm_error(Exception())
        await run_manager.on_llm_new_token("foo")
        await run_manager.on_text("foo")

    run_manager_chain = await manager.on_chain_start({"name": "foo"}, {})
    await run_manager_chain.on_chain_end({})
    await run_manager_chain.on_chain_error(Exception())
    await run_manager_chain.on_agent_action(
        AgentAction(tool_input="foo", log="", tool="")
    )
    await run_manager_chain.on_agent_finish(AgentFinish(log="", return_values={}))
    await run_manager_chain.on_text("foo")

    run_manager_tool = await manager.on_tool_start({}, "")
    await run_manager_tool.on_tool_end("")
    await run_manager_tool.on_tool_error(Exception())
    await run_manager_tool.on_text("foo")
    _check_num_calls(handlers)


def _check_num_calls(handlers: Tuple[BaseFakeCallbackHandler, ...]) -> None:
    for handler in handlers:
        assert handler.starts == 4
        assert handler.ends == 4
        assert handler.errors == 3
        assert handler.text == 3

        assert handler.llm_starts == 1
        assert handler.llm_ends == 1
        assert handler.llm_streams == 1

        assert handler.chain_starts == 1
        assert handler.chain_ends == 1

        assert handler.tool_starts == 1
        assert handler.tool_ends == 1


def test_callback_manager() -> None:
    """Test the CallbackManager."""
    handler1 = FakeCallbackHandler()
    handler2 = FakeCallbackHandler()
    manager = CallbackManager(handlers=[handler1, handler2])
    _test_callback_manager(manager, handler1, handler2)


def test_callback_manager_with_async() -> None:
    """Test the CallbackManager."""
    handler1 = FakeCallbackHandler()
    handler2 = FakeCallbackHandler()
    handler3 = FakeAsyncCallbackHandler()
    handler4 = FakeAsyncCallbackHandler()
    manager = CallbackManager(handlers=[handler1, handler2, handler3, handler4])
    _test_callback_manager(manager, handler1, handler2, handler3, handler4)


@pytest.mark.asyncio
async def test_callback_manager_with_async_with_running_loop() -> None:
    """Test the CallbackManager."""
    handler1 = FakeCallbackHandler()
    handler2 = FakeCallbackHandler()
    handler3 = FakeAsyncCallbackHandler()
    handler4 = FakeAsyncCallbackHandler()
    manager = CallbackManager(handlers=[handler1, handler2, handler3, handler4])
    _test_callback_manager(manager, handler1, handler2, handler3, handler4)


def test_ignore_llm() -> None:
    """Test ignore llm param for callback handlers."""
    handler1 = FakeCallbackHandler(ignore_llm_=True)
    handler2 = FakeCallbackHandler()
    manager = CallbackManager(handlers=[handler1, handler2])
    run_managers = manager.on_llm_start({}, ["prompt"])
    for run_manager in run_managers:
        run_manager.on_llm_end(LLMResult(generations=[]))
        run_manager.on_llm_error(Exception())
    assert handler1.starts == 0
    assert handler1.ends == 0
    assert handler1.errors == 0
    assert handler2.starts == 1
    assert handler2.ends == 1
    assert handler2.errors == 1


def test_ignore_chain() -> None:
    """Test ignore chain param for callback handlers."""
    handler1 = FakeCallbackHandler(ignore_chain_=True)
    handler2 = FakeCallbackHandler()
    manager = CallbackManager(handlers=[handler1, handler2])
    run_manager = manager.on_chain_start({"name": "foo"}, {})
    run_manager.on_chain_end({})
    run_manager.on_chain_error(Exception())
    assert handler1.starts == 0
    assert handler1.ends == 0
    assert handler1.errors == 0
    assert handler2.starts == 1
    assert handler2.ends == 1
    assert handler2.errors == 1


def test_ignore_agent() -> None:
    """Test ignore agent param for callback handlers."""
    handler1 = FakeCallbackHandler(ignore_agent_=True)
    handler2 = FakeCallbackHandler()
    manager = CallbackManager(handlers=[handler1, handler2])
    run_manager = manager.on_tool_start({}, "")
    run_manager.on_tool_end("")
    run_manager.on_tool_error(Exception())
    assert handler1.starts == 0
    assert handler1.ends == 0
    assert handler1.errors == 0
    assert handler2.starts == 1
    assert handler2.ends == 1
    assert handler2.errors == 1


def test_ignore_retriever() -> None:
    """Test the ignore retriever param for callback handlers."""
    handler1 = FakeCallbackHandler(ignore_retriever_=True)
    handler2 = FakeCallbackHandler()
    manager = CallbackManager(handlers=[handler1, handler2])
    run_manager = manager.on_retriever_start({}, "")
    run_manager.on_retriever_end([])
    run_manager.on_retriever_error(Exception())
    assert handler1.starts == 0
    assert handler1.ends == 0
    assert handler1.errors == 0
    assert handler2.starts == 1
    assert handler2.ends == 1
    assert handler2.errors == 1


@pytest.mark.asyncio
async def test_async_callback_manager() -> None:
    """Test the AsyncCallbackManager."""
    handler1 = FakeAsyncCallbackHandler()
    handler2 = FakeAsyncCallbackHandler()
    manager = AsyncCallbackManager(handlers=[handler1, handler2])
    await _test_callback_manager_async(manager, handler1, handler2)


@pytest.mark.asyncio
async def test_async_callback_manager_sync_handler() -> None:
    """Test the AsyncCallbackManager."""
    handler1 = FakeCallbackHandler()
    handler2 = FakeAsyncCallbackHandler()
    handler3 = FakeAsyncCallbackHandler()
    manager = AsyncCallbackManager(handlers=[handler1, handler2, handler3])
    await _test_callback_manager_async(manager, handler1, handler2, handler3)


def test_callback_manager_inheritance() -> None:
    handler1, handler2, handler3, handler4 = (
        FakeCallbackHandler(fake_id="handler1"),
        FakeCallbackHandler(fake_id="handler2"),
        FakeCallbackHandler(fake_id="handler3"),
        FakeCallbackHandler(fake_id="handler4"),
    )

    callback_manager1 = CallbackManager(handlers=[handler1, handler2])
    assert callback_manager1.handlers == [handler1, handler2]
    assert callback_manager1.inheritable_handlers == []

    callback_manager2 = CallbackManager(handlers=[])
    assert callback_manager2.handlers == []
    assert callback_manager2.inheritable_handlers == []

    callback_manager2.set_handlers([handler1, handler2])
    assert callback_manager2.handlers == [handler1, handler2]
    assert callback_manager2.inheritable_handlers == [handler1, handler2]

    callback_manager2.set_handlers([handler3, handler4], inherit=False)
    assert callback_manager2.handlers == [handler3, handler4]
    assert callback_manager2.inheritable_handlers == []

    callback_manager2.add_handler(handler1)
    assert callback_manager2.handlers == [handler3, handler4, handler1]
    assert callback_manager2.inheritable_handlers == [handler1]

    callback_manager2.add_handler(handler2, inherit=False)
    assert callback_manager2.handlers == [handler3, handler4, handler1, handler2]
    assert callback_manager2.inheritable_handlers == [handler1]

    run_manager = callback_manager2.on_chain_start({"name": "foo"}, {})
    child_manager = run_manager.get_child()
    assert child_manager.handlers == [handler1]
    assert child_manager.inheritable_handlers == [handler1]

    run_manager_tool = child_manager.on_tool_start({}, "")
    assert run_manager_tool.handlers == [handler1]
    assert run_manager_tool.inheritable_handlers == [handler1]

    child_manager2 = run_manager_tool.get_child()
    assert child_manager2.handlers == [handler1]
    assert child_manager2.inheritable_handlers == [handler1]


def test_duplicate_callbacks() -> None:
    handler = FakeCallbackHandler()
    manager = CallbackManager(handlers=[handler])
    manager.add_handler(handler)
    assert manager.handlers == [handler]


def test_callback_manager_configure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test callback manager configuration."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING", "false")
    handler1, handler2, handler3, handler4 = (
        FakeCallbackHandler(fake_id="handler1"),
        FakeCallbackHandler(fake_id="handler2"),
        FakeCallbackHandler(fake_id="handler3"),
        FakeCallbackHandler(fake_id="handler4"),
    )

    inheritable_callbacks: List[BaseCallbackHandler] = [handler1, handler2]
    local_callbacks: List[BaseCallbackHandler] = [handler3, handler4]
    configured_manager = CallbackManager.configure(
        inheritable_callbacks=inheritable_callbacks,
        local_callbacks=local_callbacks,
        verbose=True,
    )

    assert len(configured_manager.handlers) == 5
    assert len(configured_manager.inheritable_handlers) == 2
    assert configured_manager.inheritable_handlers == inheritable_callbacks
    assert configured_manager.handlers[:4] == inheritable_callbacks + local_callbacks
    assert isinstance(configured_manager.handlers[4], StdOutCallbackHandler)
    assert isinstance(configured_manager, CallbackManager)

    async_local_callbacks = AsyncCallbackManager(handlers=[handler3, handler4])
    async_configured_manager = AsyncCallbackManager.configure(
        inheritable_callbacks=inheritable_callbacks,
        local_callbacks=async_local_callbacks,
        verbose=False,
    )

    assert len(async_configured_manager.handlers) == 4
    assert len(async_configured_manager.inheritable_handlers) == 2
    assert async_configured_manager.inheritable_handlers == inheritable_callbacks
    assert async_configured_manager.handlers == inheritable_callbacks + [
        handler3,
        handler4,
    ]
    assert isinstance(async_configured_manager, AsyncCallbackManager)


@patch.object(LangChainTracer, "_persist_run_single")
def test_callback_manager_configure_context_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test callback manager configuration."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING", "false")
    with trace_as_chain_group("test") as group_manager:
        assert len(group_manager.handlers) == 1
        tracer = group_manager.handlers[0]
        assert isinstance(tracer, LangChainTracer)

        with get_openai_callback() as cb:
            # This is a new empty callback handler
            assert cb.successful_requests == 0
            assert cb.total_tokens == 0

            # configure adds this openai cb but doesn't modify the group manager
            mngr = CallbackManager.configure(group_manager)
            assert mngr.handlers == [tracer, cb]
            assert group_manager.handlers == [tracer]

            response = LLMResult(
                generations=[],
                llm_output={
                    "token_usage": {
                        "prompt_tokens": 2,
                        "completion_tokens": 1,
                        "total_tokens": 3,
                    },
                    "model_name": BaseOpenAI.__fields__["model_name"].default,
                },
            )
            mngr.on_llm_start({}, ["prompt"])[0].on_llm_end(response)

            # The callback handler has been updated
            assert cb.successful_requests == 1
            assert cb.total_tokens == 3
            assert cb.prompt_tokens == 2
            assert cb.completion_tokens == 1
            assert cb.total_cost > 0

        with get_openai_callback() as cb:
            # This is a new empty callback handler
            assert cb.successful_requests == 0
            assert cb.total_tokens == 0

            # configure adds this openai cb but doesn't modify the group manager
            mngr = CallbackManager.configure(group_manager)
            assert mngr.handlers == [tracer, cb]
            assert group_manager.handlers == [tracer]

            response = LLMResult(
                generations=[],
                llm_output={
                    "token_usage": {
                        "prompt_tokens": 2,
                        "completion_tokens": 1,
                        "total_tokens": 3,
                    },
                    "model_name": BaseOpenAI.__fields__["model_name"].default,
                },
            )
            mngr.on_llm_start({}, ["prompt"])[0].on_llm_end(response)

            # The callback handler has been updated
            assert cb.successful_requests == 1
            assert cb.total_tokens == 3
            assert cb.prompt_tokens == 2
            assert cb.completion_tokens == 1
            assert cb.total_cost > 0
    assert LangChainTracer._persist_run_single.call_count == 1
