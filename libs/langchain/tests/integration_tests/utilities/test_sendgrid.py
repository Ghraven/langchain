"""Integration test for Email."""
from langchain.utilities.sendgrid import SendgridAPIWrapper


def test_call() -> None:
    """Test that call runs."""
    sendgrid = SendgridAPIWrapper()
    # From address must be from a verified sender to work.
    # For more information: https://docs.sendgrid.com/ui/sending-email/sender-verification
    # Ensure SENDGRID_API_KEY is set in environment.
    output = sendgrid.run(
        "test@test.com",
        "test@test.com",
        "langchain - test",
        "langchain FTW",
        "text/plain",
    )
    assert output == 202
