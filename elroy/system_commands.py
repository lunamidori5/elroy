import inspect
import json
import logging
from typing import Callable, List, Optional, Set

from rich.console import Group
from rich.pretty import Pretty
from rich.table import Table
from sqlmodel import select
from toolz import pipe
from toolz.curried import map

from .config.constants import ASSISTANT, SYSTEM, TOOL, USER, tool
from .config.ctx import ElroyContext
from .db.db_models import Goal, Memory
from .llm.client import get_embedding, query_llm
from .llm.prompts import contemplate_prompt
from .messaging.context import (
    add_goal_to_current_context,
    add_memory_to_current_context,
    drop_goal_from_current_context,
    drop_memory_from_current_context,
    format_context_messages,
    get_refreshed_system_message,
)
from .repository.data_models import ContextMessage
from .repository.goals.operations import (
    add_goal_status_update,
    create_goal,
    delete_goal_permanently,
    get_db_goal_by_name,
    mark_goal_completed,
    rename_goal,
)
from .repository.goals.queries import get_active_goals
from .repository.memories.operations import create_memory
from .repository.message import (
    add_context_messages,
    get_context_messages,
    get_current_system_message,
    replace_context_messages,
)
from .tools.coding import make_coding_edit
from .tools.developer import create_bug_report, print_config, tail_elroy_logs
from .tools.user_preferences import (
    get_user_full_name,
    get_user_preferred_name,
    set_assistant_name,
    set_user_full_name,
    set_user_preferred_name,
)


def refresh_system_instructions(ctx: ElroyContext) -> str:
    """Refreshes the system instructions

    Args:
        user_id (_type_): user id

    Returns:
        str: The result of the system instruction refresh
    """

    context_messages = get_context_messages(ctx)
    if len(context_messages) == 0:
        context_messages.append(
            get_refreshed_system_message(ctx, []),
        )
    else:
        context_messages[0] = get_refreshed_system_message(
            ctx,
            context_messages[1:],
        )
    replace_context_messages(ctx, context_messages)
    return "System instruction refresh complete"


def print_system_instruction(ctx: ElroyContext) -> Optional[str]:
    """Prints the current system instruction for the assistant

    Args:
        user_id (int): user id

    Returns:
        str: The current system instruction
    """

    return pipe(
        get_current_system_message(ctx),
        lambda _: _.content if _ else None,
    )  # type: ignore


def help(ctx: ElroyContext) -> None:
    """Prints the available system commands

    Returns:
        str: The available system commands
    """
    from .io.cli import CliIO

    if isinstance(ctx.io, CliIO):
        from rich.table import Table

        commands = pipe(
            SYSTEM_COMMANDS,
            map(
                lambda f: (
                    f.__name__,
                    inspect.getdoc(f).split("\n")[0],  # type: ignore
                )
            ),
            list,
            sorted,
        )

        table = Table(title="Available Slash Commands")
        table.add_column("Command", justify="left", style="cyan", no_wrap=True)
        table.add_column("Description", justify="left", style="green")

        for command, description in commands:  # type: ignore
            table.add_row(command, description)

        ctx.io.print(table)
    else:
        # not really expecting to use this function outside of CLI, but just in case
        for f in SYSTEM_COMMANDS:
            ctx.io.print(f.__name__)


def add_internal_thought(ctx: ElroyContext, thought: str) -> str:
    """Inserts internal thought for the assistant. Useful for guiding the assistant's thoughts in a specific direction.

    Args:
        context (ElroyContext): context obj
        thought (str): The thought to add

    Returns:
        str: The result of the internal thought addition
    """

    add_context_messages(
        ctx,
        [
            ContextMessage(
                role=SYSTEM,
                content=thought,
                chat_model=ctx.chat_model.name,
            )
        ],
    )

    return f"Internal thought added: {thought}"


def reset_messages(ctx: ElroyContext) -> str:
    """Resets the context for the user, removing all messages from the context except the system message.
    This should be used sparingly, only at the direct request of the user.

    Args:
        user_id (int): user id

    Returns:
        str: The result of the context reset
    """
    logging.info("Resetting messages: Dropping all conversation messages and recalculating system message")

    replace_context_messages(
        ctx,
        [get_refreshed_system_message(ctx, [])],
    )

    return "Context reset complete"


def print_context_messages(ctx: ElroyContext) -> Table:
    """Logs all of the current context messages to stdout

    Args:
        session (Session): _description_
        user_id (int): _description_
    """
    messages = get_context_messages(ctx)

    table = Table(show_header=True, padding=(0, 2), show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Message Details")

    for idx, message in enumerate(messages, 1):
        # Determine style based on role

        # Create message details
        details = [
            f"[bold]ID[/]: {message.id}",
            f"[bold]Role[/]: {message.role}",
            f"[bold]Model[/]: {message.chat_model or ''}",
        ]

        if message.created_at:
            details.append(f"[bold]Created[/]: {message.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

        if message.content:
            details.append(f"\n[bold]Content[/]:\n{message.content}")

        if message.tool_calls:
            details.append("[bold]Tool Calls:[/]")
            for tc in message.tool_calls:
                try:
                    tc.function["arguments"] = json.loads(tc.function["arguments"])
                except json.JSONDecodeError:
                    logging.info("Couldn't decode arguments for tool call")
                details.append(Pretty(tc, expand_all=True))  # type: ignore

        table.add_row(
            str(idx),
            Group(*details),
            style={
                ASSISTANT: ctx.params.assistant_color,
                USER: ctx.params.user_input_color,
                SYSTEM: ctx.params.system_message_color,
                TOOL: ctx.params.system_message_color,
            }.get(message.role, "white"),
        )

    return table


@tool
def print_goal(ctx: ElroyContext, goal_name: str) -> str:
    """Prints the goal with the given name. This does NOT create a goal, it only prints the existing goal with the given name if it has been created already.

    Args:
        goal_name (str): Name of the goal to retrieve

    Returns:
        str: The goal's details if found, or an error message if not found
    """
    goal = ctx.db.exec(
        select(Goal).where(
            Goal.user_id == ctx.user_id,
            Goal.name == goal_name,
            Goal.is_active == True,
        )
    ).first()
    if goal:
        return goal.to_fact()
    else:
        return f"Goal '{goal_name}' not found for the current user."


def get_active_goal_names(ctx: ElroyContext) -> List[str]:
    """Gets the list of names for all active goals

    Returns:
        List[str]: List of names for all active goals
    """

    return [goal.name for goal in get_active_goals(ctx)]


def get_goal_by_name(ctx: ElroyContext, goal_name: str) -> Optional[str]:
    """Get the fact for a goal by name

    Args:
        ctx (ElroyContext): context obj
        goal_name (str): Name of the goal

    Returns:
        Optional[str]: The fact for the goal with the given name
    """
    goal = get_db_goal_by_name(ctx, goal_name)
    if goal:
        return goal.to_fact()


@tool
def print_memory(ctx: ElroyContext, memory_name: str) -> str:
    """Prints the memory with the given name

    Args:
        memory_name (str): Name of the memory retrieve

    Returns:
        str: The memory's details if found, or an error message if not found
    """
    memory = ctx.db.exec(
        select(Memory).where(
            Memory.user_id == ctx.user_id,
            Memory.name == memory_name,
            Memory.is_active == True,
        )
    ).first()
    if memory:
        return memory.to_fact()
    else:
        return f"Memory '{memory_name}' not found for the current user."


@tool
def contemplate(ctx: ElroyContext, contemplation_prompt: Optional[str] = None) -> str:
    """Contemplate the current context and return a response.

    Args:
        contemplation_prompt (str, optional): Custom prompt to guide the contemplation.
            If not provided, will contemplate the current conversation context

    Returns:
        str: A thoughtful response analyzing the current context and any provided prompt
    """

    logging.info("Contemplating...")

    user_preferred_name = get_user_preferred_name(ctx)
    context_messages = get_context_messages(ctx)

    msgs_input = format_context_messages(context_messages, user_preferred_name)

    response = query_llm(
        model=ctx.chat_model,
        prompt=msgs_input,
        system=contemplate_prompt(user_preferred_name, contemplation_prompt),
    )

    add_context_messages(
        ctx,
        [
            ContextMessage(
                role=SYSTEM,
                content=response,
                chat_model=ctx.chat_model.name,
            )
        ],
    )

    ctx.io.internal_thought(response)

    return response


@tool
def query_memory(ctx: ElroyContext, query: str) -> str:
    """Search through memories and goals using semantic search.

    Args:
        query (str): The search query text to find relevant memories and goals

    Returns:
        str: A response synthesizing relevant memories and goals that match the query
    """
    # Get query embedding
    query_embedding = get_embedding(ctx.embedding_model, query)

    # Search memories and goals
    relevant_memories = [
        memory
        for memory in ctx.db.query_vector(ctx.l2_memory_relevance_distance_threshold, Memory, ctx.user_id, query_embedding)
        if isinstance(memory, Memory)
    ]

    relevant_goals = [
        goal
        for goal in ctx.db.query_vector(ctx.l2_memory_relevance_distance_threshold, Goal, ctx.user_id, query_embedding)
        if isinstance(goal, Goal)
    ]

    # Format context for LLM
    context_parts = []
    if relevant_memories:
        context_parts.append("Relevant memories:")
        for memory in relevant_memories:
            context_parts.append(f"- {memory.name}: {memory.text}")

    if relevant_goals:
        if context_parts:
            context_parts.append("\n")
        context_parts.append("Relevant goals:")
        for goal in relevant_goals:
            context_parts.append(f"- {goal.name}: {goal.to_fact()}")

    if not context_parts:
        return "No relevant memories or goals found."

    context = "\n".join(context_parts)

    # Generate response using LLM
    system_prompt = """You are an AI assistant helping to answer questions based on retrieved memories and goals.
Your task is to analyze the provided context and answer the user's query thoughtfully.
Base your response entirely on the provided context. If the context doesn't contain relevant information, say so.
Answer the question directly, short and concise. Do not say things like "based on the current context", just answer straightforwardly.
"""

    return query_llm(
        model=ctx.chat_model,
        system=system_prompt,
        prompt=f"Query: {query}\n\nContext:\n{context}\n\nPlease provide a thoughtful response to the query based on the above context.",
    )


def do_not_use() -> str:
    """This is a dummy function that should not be used. It is only for testing purposes.

    Returns:
        str: A message indicating that this function should not be used
    """
    return "This function should not be used."


IN_CONTEXT_GOAL_COMMANDS: Set[Callable] = {
    drop_goal_from_current_context,
}

NON_CONTEXT_GOAL_COMMANDS: Set[Callable] = {
    add_goal_to_current_context,
}

ALL_ACTIVE_GOAL_COMMANDS: Set[Callable] = {
    rename_goal,
    print_goal,
    add_goal_status_update,
    mark_goal_completed,
    delete_goal_permanently,
}

IN_CONTEXT_MEMORY_COMMANDS: Set[Callable] = {
    drop_memory_from_current_context,
}

NON_CONTEXT_MEMORY_COMMANDS: Set[Callable] = {
    add_memory_to_current_context,
}

ALL_ACTIVE_MEMORY_COMMANDS: Set[Callable] = {
    print_memory,
}


NON_ARG_PREFILL_COMMANDS: Set[Callable] = {
    create_goal,
    create_memory,
    contemplate,
    query_memory,
    get_user_full_name,
    set_user_full_name,
    get_user_preferred_name,
    set_user_preferred_name,
    tail_elroy_logs,
    make_coding_edit,
}

# These are commands that are visible to the assistant to be executed as tools.
ASSISTANT_VISIBLE_COMMANDS: Set[Callable] = (
    NON_ARG_PREFILL_COMMANDS
    | IN_CONTEXT_GOAL_COMMANDS
    | NON_CONTEXT_GOAL_COMMANDS
    | ALL_ACTIVE_GOAL_COMMANDS
    | IN_CONTEXT_MEMORY_COMMANDS
    | NON_CONTEXT_MEMORY_COMMANDS
    | ALL_ACTIVE_MEMORY_COMMANDS
)


# User only commands are commands that are only available to the user, via CLI.
USER_ONLY_COMMANDS = {
    print_config,
    add_internal_thought,
    reset_messages,
    print_context_messages,
    print_system_instruction,
    refresh_system_instructions,
    help,
    create_bug_report,
    set_assistant_name,
}


SYSTEM_COMMANDS = ASSISTANT_VISIBLE_COMMANDS | USER_ONLY_COMMANDS
