from tests.utils import process_test_message

from elroy.system_commands import reset_messages
from elroy.tools.user_preferences import (
    get_user_preferred_name,
    reset_system_persona,
    set_assistant_name,
    set_system_persona,
)


def test_update_user_preferred_name(ctx):

    process_test_message(
        ctx,
        "Please call me TestUser500 from now on.",
    )

    assert get_user_preferred_name(ctx) == "TestUser500"


def test_update_persona(ctx):
    reply = process_test_message(ctx, "What is your name?")

    assert "elroy" in reply.lower()

    set_system_persona(ctx, "You are a helpful assistant." "Your name is Jarvis" "If asked what your name is, be sure to reply with Jarvis")

    reply = process_test_message(ctx, "What is your name?")

    assert "jarvis" in reply.lower()
    assert "elroy" not in reply.lower()

    reply = process_test_message(ctx, "What is your name?")

    reset_system_persona(ctx)


def test_assistant_name(ctx):
    assert "elroy" in process_test_message(ctx, "What is your name?").lower()

    set_assistant_name(ctx, "Jimbo")
    reset_messages(ctx)

    assert "jimbo" in process_test_message(ctx, "What is your name?").lower()
