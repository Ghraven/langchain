from typing import Dict, List, Optional

from langchain.chains.base import CallbackManagerForChainRun, Chain

from langchain_core.callbacks import StdOutCallbackHandler


class FakeChain(Chain):
    """Fake chain class for testing purposes."""

    be_correct: bool = True
    the_input_keys: List[str] = ["foo"]
    the_output_keys: List[str] = ["bar"]

    @property
    def input_keys(self) -> List[str]:
        """Input keys."""
        return self.the_input_keys

    @property
    def output_keys(self) -> List[str]:
        """Output key of bar."""
        return self.the_output_keys

    def _call(
        self,
        inputs: Dict[str, str],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, str]:
        return {"bar": "bar"}


def test_stdoutcallback(capsys):
    chain_test = FakeChain(callbacks=[StdOutCallbackHandler(color="red")])
    chain_test.invoke({"foo": "bar"})
    # Capture the output
    captured = capsys.readouterr()
    # Assert the output is as expected
    assert "> Entering new FakeChain chain..." in captured.out
