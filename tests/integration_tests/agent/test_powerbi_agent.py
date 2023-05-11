from langchain.agents.agent_toolkits import create_pbi_agent
from langchain.agents.agent_toolkits import PowerBIToolkit
from langchain.utilities.powerbi import PowerBIDataset
from langchain.chat_models import ChatOpenAI
from langchain.utils import get_from_env
from azure.identity import DefaultAzureCredential

def test_daxquery():

    DATASET_ID = get_from_env("","POWERBI_DATASET_ID")
    TABLE_NAME = get_from_env("", "POWERBI_TABLE_NAME")
    NUM_ROWS = get_from_env("", "POWERBI_NUMROWS")

    fast_llm = ChatOpenAI(temperature=0.5, max_tokens=1000, model_name="gpt-3.5-turbo", verbose=True)
    smart_llm = ChatOpenAI(temperature=0, max_tokens=100, model_name="gpt-4", verbose=True)

    toolkit = PowerBIToolkit(
        powerbi=PowerBIDataset(dataset_id=DATASET_ID, table_names=[TABLE_NAME], credential=DefaultAzureCredential()), 
        llm=smart_llm
    )

    agent_executor = create_pbi_agent(
        llm=fast_llm,
        toolkit=toolkit,
        verbose=True
    )

    output = agent_executor.run(f"How many rows are in the table, {TABLE_NAME}")
    assert NUM_ROWS in output
    