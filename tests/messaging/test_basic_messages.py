import pytest
from tests.utils import process_test_message

from elroy.config.constants import InvalidForceToolError
from elroy.tools.user_preferences import (
    get_user_preferred_name,
    set_user_preferred_name,
)


def test_hello_world(elroy_context):
    # Test message
    test_message = "Hello, World!"

    # Get the argument passed to the delivery function
    response = process_test_message(elroy_context, test_message)

    # Assert that the response is a non-empty string
    assert isinstance(response, str)
    assert len(response) > 0

    # Assert that the response contains a greeting
    assert any(greeting in response.lower() for greeting in ["hello", "hi", "greetings"])


def test_force_tool(elroy_context):
    process_test_message(elroy_context, "Jimmy", set_user_preferred_name.__name__)
    assert get_user_preferred_name(elroy_context) == "Jimmy"


def test_force_invalid_tool(elroy_context):
    with pytest.raises(InvalidForceToolError):
        process_test_message(elroy_context, "Jimmy", "invalid_tool")
