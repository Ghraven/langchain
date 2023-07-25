"""Agent for working with pandas objects."""
from typing import Any, Dict, List, Optional

from langchain.agents.agent import AgentExecutor
from langchain.agents.agent_toolkits.spark.prompt import PREFIX, SUFFIX
from langchain.agents.mrkl.base import ZeroShotAgent
from langchain.callbacks.base import BaseCallbackManager
from langchain.chains.llm import LLMChain
from langchain.llms.base import BaseLLM
from langchain.tools.python.tool import PythonAstREPLTool


def _validate_spark_df(df: Any) -> bool:
    try:
        from pyspark.sql import DataFrame as SparkLocalDataFrame

        if isinstance(df, list):
            return all(isinstance(d, SparkLocalDataFrame) for d in df)
        else:
            return isinstance(df, SparkLocalDataFrame)
    except ImportError:
        return False


def _validate_spark_connect_df(df: Any) -> bool:
    try:
        from pyspark.sql.connect.dataframe import DataFrame as SparkConnectDataFrame

        if isinstance(df, list):
            return all(isinstance(d, SparkConnectDataFrame) for d in df)
        else:
            return isinstance(df, SparkConnectDataFrame)
    except ImportError:
        return False


def create_spark_dataframe_agent(
    llm: BaseLLM,
    dfs: Any,  # Accept multiple DataFrames as input
    callback_manager: Optional[BaseCallbackManager] = None,
    prefix: str = PREFIX,
    suffix: str = SUFFIX,
    input_variables: Optional[List[str]] = None,
    verbose: bool = False,
    return_intermediate_steps: bool = False,
    max_iterations: Optional[int] = 15,
    max_execution_time: Optional[float] = None,
    early_stopping_method: str = "force",
    agent_executor_kwargs: Optional[Dict[str, Any]] = None,
    **kwargs: Dict[str, Any],
) -> AgentExecutor:
    """Construct a Spark agent from an LLM and DataFrame(s)."""

    if not _validate_spark_df(dfs) and not _validate_spark_connect_df(dfs):
        raise ValueError("Spark is not installed. run `pip install pyspark`.")

    if input_variables is None:
        input_variables = ["dfs", "input", "agent_scratchpad"]
    tools = [PythonAstREPLTool(locals={"dfs": dfs})]  # Update the locals variable

    # Determine whether the input contains single or multiple DataFrames
    if isinstance(dfs, list):
        prompt = ZeroShotAgent.create_prompt(
            tools,
            prefix=prefix,
            suffix=suffix,
            input_variables=input_variables + ["num_dfs"],  # Add 'num_dfs' to input variables
        )
        partial_prompt = prompt.partial(num_dfs=str(len(dfs)))  # Add 'num_dfs' to partial_prompt
    else:
        prompt = ZeroShotAgent.create_prompt(
            tools,
            prefix=prefix,
            suffix=suffix,
            input_variables=input_variables,
        )
        partial_prompt = prompt.partial(dfs=str(dfs.first()))

    llm_chain = LLMChain(
        llm=llm,
        prompt=partial_prompt,
        callback_manager=callback_manager,
    )
    tool_names = [tool.name for tool in tools]
    agent = ZeroShotAgent(
        llm_chain=llm_chain,
        allowed_tools=tool_names,
        callback_manager=callback_manager,
        **kwargs,
    )
    return AgentExecutor.from_agent_and_tools(
        agent=agent,
        tools=tools,
        callback_manager=callback_manager,
        verbose=verbose,
        return_intermediate_steps=return_intermediate_steps,
        max_iterations=max_iterations,
        max_execution_time=max_execution_time,
        early_stopping_method=early_stopping_method,
        **(agent_executor_kwargs or {}),
    )


