from typing import List

from sqlmodel import select
from toolz import pipe
from toolz.curried import filter

from elroy.store.data_models import Goal
from elroy.store.message import ContextMessage, get_context_messages
from tests.fixtures import BASKETBALL_FOLLOW_THROUGH_REMINDER_NAME
from tests.utils import process_test_message, vector_search_by_text


def test_goal_relevance(george_context):

    assert vector_search_by_text(george_context, "I'm off to go play basketball!", Goal)
    assert not vector_search_by_text(george_context, "I'm off to ride horses!", Goal)
    assert not vector_search_by_text(george_context, "I wonder what time it is", Goal)
    assert vector_search_by_text(
        george_context,
        "Big day today! I'm going to watch a bunch of television, probably 20 shows, might play some bball alter",
        Goal,
    )
    assert not vector_search_by_text(
        george_context, "Elephants swiftly draw vibrant pancakes across whispering oceans under midnight skies.", Goal
    )


def test_goal_in_context(george_context):
    goal = george_context.session.exec(
        select(Goal).where(
            Goal.user_id == george_context.user_id,
            Goal.name == BASKETBALL_FOLLOW_THROUGH_REMINDER_NAME,
        )
    ).one_or_none()
    assert goal
    goal_id = goal.id

    process_test_message(george_context, "I'm off to go play basketball!")

    context_messages = get_context_messages(george_context)

    assert len(messages_with_goal_id(context_messages, goal_id)) == 1

    # Ensure we do not redundantly add the same goal to the context
    process_test_message(george_context, "I'm in the car, heading over to play basketball")

    context_messages = get_context_messages(george_context)

    assert len(messages_with_goal_id(context_messages, goal_id)) == 1


def messages_with_goal_id(context_messages: List[ContextMessage], goal_id) -> List[ContextMessage]:
    return pipe(
        context_messages,
        filter(
            lambda m: m.memory_metadata
            and any(metadata.id == goal_id and metadata.memory_type == Goal.__name__ for metadata in m.memory_metadata)
        ),
        list,
    )
