"""Interface for tools."""
from inspect import signature
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union

from langchain.tools.base import BaseTool
from langchain.utils import register


class Tool(BaseTool):
    """Tool that takes in function or coroutine directly."""

    description: str = ""
    func: Callable[[str], str]
    coroutine: Optional[Callable[[str], Awaitable[str]]] = None

    def _run(self, tool_input: str) -> str:
        """Use the tool."""
        return self.func(tool_input)

    async def _arun(self, tool_input: str) -> str:
        """Use the tool asynchronously."""
        if self.coroutine:
            return await self.coroutine(tool_input)
        raise NotImplementedError("Tool does not support async")

    # TODO: this is for backwards compatibility, remove in future
    def __init__(
        self, name: str, func: Callable[[str], str], description: str, **kwargs: Any
    ) -> None:
        """Initialize tool."""
        super(Tool, self).__init__(
            name=name, func=func, description=description, **kwargs
        )


class InvalidTool(BaseTool):
    """Tool that is run when invalid tool name is encountered by agent."""

    name = "invalid_tool"
    description = "Called when tool name is invalid."

    def _run(self, tool_name: str) -> str:
        """Use the tool."""
        return f"{tool_name} is not a valid tool, try another one."

    async def _arun(self, tool_name: str) -> str:
        """Use the tool asynchronously."""
        return f"{tool_name} is not a valid tool, try another one."


def tool(*args: Union[str, Callable], return_direct: bool = False) -> Callable:
    """Make tools out of functions, can be used with or without arguments.

    Requires:
        - Function must be of type (str) -> str
        - Function must have a docstring

    Examples:
        .. code-block:: python

            @tool
            def search_api(query: str) -> str:
                # Searches the API for the query.
                return

            @tool("search", return_direct=True)
            def search_api(query: str) -> str:
                # Searches the API for the query.
                return
    """

    def _make_with_name(tool_name: str) -> Callable:
        def _make_tool(func: Callable[[str], str]) -> Tool:
            assert func.__doc__, "Function must have a docstring"
            # Description example:
            #   search_api(query: str) - Searches the API for the query.
            description = f"{tool_name}{signature(func)} - {func.__doc__.strip()}"
            tool_ = Tool(
                name=tool_name,
                func=func,
                description=description,
                return_direct=return_direct,
            )
            return tool_

        return _make_tool

    if len(args) == 1 and isinstance(args[0], str):
        # if the argument is a string, then we use the string as the tool name
        # Example usage: @tool("search", return_direct=True)
        return _make_with_name(args[0])
    elif len(args) == 1 and callable(args[0]):
        # if the argument is a function, then we use the function name as the tool name
        # Example usage: @tool
        return _make_with_name(args[0].__name__)(args[0])
    elif len(args) == 0:
        # if there are no arguments, then we use the function name as the tool name
        # Example usage: @tool(return_direct=True)
        def _partial(func: Callable[[str], str]) -> BaseTool:
            return _make_with_name(func.__name__)(func)

        return _partial
    else:
        raise ValueError("Too many arguments for tool decorator")


_TOOLS: Dict[str, Tuple[Callable, List[str]]] = {}
_LLM_TOOLS: Dict[str, Tuple[Callable, List[str]]] = {}


def register_tool(key: str, required_kwargs: List[str] = []) -> Callable:
    """Register a tool."""

    def _register_tool_cls(cls: Any) -> Callable:
        register(key, _TOOLS)(cls=cls, required_kwargs=required_kwargs)
        return cls

    return _register_tool_cls


def register_llm_tool(key: str, required_kwargs: List[str] = []) -> Callable:
    """Register an LLM tool."""

    def _register_llm_tool_cls(cls: Any) -> Callable:
        register(key, _LLM_TOOLS)(cls=cls, required_kwargs=required_kwargs)
        return cls

    return _register_llm_tool_cls


def get_all_tool_names() -> List[str]:
    """Get a list of all possible tool names."""
    return list(_TOOLS) + list(_LLM_TOOLS)
