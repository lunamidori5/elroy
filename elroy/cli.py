import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import List, Optional

import typer
from colorama import init
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from pygments.lexers.special import TextLexer
from rich.console import Console
from rich.panel import Panel
from sqlmodel import select
from toolz import concat, pipe, unique
from toolz.curried import filter, map

from alembic import command
from alembic.config import Config
from docker_postgres import is_docker_running, start_db, stop_db
from elroy.config import (ROOT_DIR, ElroyConfig, ElroyContext, get_config,
                          session_manager)
from elroy.logging_config import setup_logging
from elroy.memory.system_context import context_refresh_if_needed
from elroy.onboard_user import onboard_user
from elroy.store.data_models import Goal
from elroy.store.message import get_context_messages
from elroy.store.user import is_user_exists
from elroy.system.clock import get_utc_now
from elroy.system.parameters import CLI_USER_ID
from elroy.tools.functions.user_preferences import set_user_preferred_name
from elroy.tools.messenger import process_message
from elroy.tools.system_commands import (GOAL_COMMANDS, SYSTEM_COMMANDS,
                                         invoke_system_command)

app = typer.Typer()


def get_user_goals(context: ElroyContext) -> List[str]:
    """Fetch all active goals for the user"""
    goals = context.session.exec(
        select(Goal).where(
            Goal.user_id == context.user_id,
            Goal.is_active == True,
        )
    ).all()
    return [goal.name for goal in goals]


class SlashCompleter(Completer):
    def __init__(self, goals):
        self.goals = goals

    def get_completions(self, document, complete_event):
        from elroy.tools.system_commands import SYSTEM_COMMANDS

        text = document.text_before_cursor
        if text.startswith("/"):
            input = text.split("/")[-1].strip()
            input_cmd = input.split()[0] if len(input) > 1 else ""

            for cmd in sorted(SYSTEM_COMMANDS.keys() - GOAL_COMMANDS):
                if cmd.lower().startswith(input_cmd.lower()):
                    yield Completion(cmd, start_position=-len(input_cmd))

            for cmd in GOAL_COMMANDS:
                for goal in self.goals:
                    if f"{cmd} {goal}".lower().startswith(input.lower()):
                        yield Completion(f"{cmd} {goal}", start_position=-len(input))


def get_relevant_memories(context: ElroyContext) -> List[str]:
    return pipe(
        get_context_messages(context),
        filter(lambda m: m.created_at_utc_epoch_secs > get_utc_now().timestamp() - context.config.max_in_context_message_age_seconds),
        map(lambda m: m.memory_metadata),
        filter(lambda m: m is not None),
        concat,
        # filter(lambda m: m.memory_type == Goal.__name__),  # TODO: Consolidate memories if they are redundant
        map(lambda m: f"{m.memory_type}: {m.name}"),
        unique,
        list,
        sorted,
    )  # type: ignore


DEFAULT_OUTPUT_COLOR = "#77DFD8"
DEFAULT_INPUT_COLOR = "#FFE377"
SYSTEM_MESSAGE_COLOR = "#9ACD32"


def rule():
    console = Console()
    console.rule(style=DEFAULT_INPUT_COLOR)


def display_memory_titles(titles):
    console = Console()
    if titles:
        panel = Panel("\n".join(titles), title="Relevant Context", expand=False, border_style=DEFAULT_INPUT_COLOR)
        console.print(panel)


async def async_context_refresh_if_needed(context):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, context_refresh_if_needed, context)


@app.command()
def chat(
    database_url: Optional[str] = typer.Option(None, envvar="ELROY_DATABASE_URL"),
    openai_api_key: Optional[str] = typer.Option(None, envvar="OPENAI_API_KEY"),
    local_storage_path: Optional[str] = typer.Option(None, envvar="ELROY_LOCAL_STORAGE_PATH"),
    context_window_token_limit: Optional[int] = typer.Option(None, envvar="ELROY_CONTEXT_WINDOW_TOKEN_LIMIT"),
    log_file_path: str = typer.Option(os.path.join(ROOT_DIR, "logs", "elroy.log"), envvar="ELROY_LOG_FILE_PATH"),
    use_docker_postgres: Optional[bool] = typer.Option(True, envvar="USE_DOCKER_POSTGRES"),
):
    """Start the Elroy chat interface"""

    console = Console()

    with console.status(f"[{DEFAULT_OUTPUT_COLOR}] Initializing Elroy...", spinner="dots") as status:
        setup_logging(log_file_path)

        if use_docker_postgres:
            if database_url is not None:
                logging.info("use_docker_postgres is set to True, ignoring database_url")

            if not is_docker_running():
                console.print(f"[{SYSTEM_MESSAGE_COLOR}]Docker is not running. Please start Docker and try again.[/]")
                exit(1)

            database_url = start_db()

        assert database_url, "Database URL is required"
        assert openai_api_key, "OpenAI API key is required"

    pipe(
        get_config(
            database_url=database_url,
            openai_api_key=openai_api_key,
            local_storage_path=local_storage_path,
            context_window_token_limit=context_window_token_limit,
        ),
        partial(main_chat, console),
        asyncio.run,
    )

    console.print(f"[{SYSTEM_MESSAGE_COLOR}]Exiting...[/]")

    if use_docker_postgres:
        logging.info("Stopping Docker Postgres containr...")
        stop_db()


async def main_chat(console: Console, config: ElroyConfig):
    init(autoreset=True)

    history = InMemoryHistory()

    style = Style.from_dict(
        {
            "prompt": "bold",
            "user-input": DEFAULT_INPUT_COLOR + " bold",
            "": DEFAULT_INPUT_COLOR,
            "pygments.literal.string": f"bold italic {DEFAULT_INPUT_COLOR}",
        }
    )

    with session_manager(config.database_url) as db_session:
        # Fetch user goals for autocomplete
        context = ElroyContext(
            user_id=CLI_USER_ID,
            session=db_session,
            console=console,
            config=config,
        )

        # Asynchronously refresh context, this will drop old message from context.
        asyncio.create_task(async_context_refresh_if_needed(context))

        user_goals = get_user_goals(context)
        slash_completer = SlashCompleter(user_goals)

        session = PromptSession(
            history=history,
            style=style,
            lexer=PygmentsLexer(TextLexer),
            completer=slash_completer,
        )

        def process_and_deliver_msg(user_input):
            nonlocal slash_completer, session
            if user_input.startswith("/"):
                cmd = user_input[1:].split()[0]

                if cmd.lower() not in SYSTEM_COMMANDS:
                    console.print(f"Unknown command: {cmd}")
                else:
                    try:
                        response = invoke_system_command(context, user_input)
                        console.print(f"[{DEFAULT_OUTPUT_COLOR}]{response}[/]", end="")
                    except Exception as e:
                        print(f"Error invoking system command: {e}")
            else:
                for partial_response in process_message(context, user_input):
                    console.print(f"[{DEFAULT_OUTPUT_COLOR}]{partial_response}[/]", end="")
                console.print()  # New line after complete response

            # Refresh slash completer
            user_goals = get_user_goals(context)
            slash_completer.goals = user_goals
            session.completer = slash_completer

        if not is_user_exists(context):
            name = await session.prompt_async(HTML("<b>Welcome to Elroy! What should I call you? </b>"), style=style)
            user_id = onboard_user(db_session, context.console, context.config, name)
            assert isinstance(user_id, int)

            set_user_preferred_name(context, name)
            msg = f"[This is a hidden system message. Elroy user {name} has been onboarded. Say hello and introduce yourself.]"
            process_and_deliver_msg(msg)

        while True:
            try:
                rule()

                # Fetch and display relevant memories
                relevant_memories = get_relevant_memories(context)
                if relevant_memories:
                    display_memory_titles(relevant_memories)

                user_input = await session.prompt_async(HTML("<b>> </b>"), style=style)
                if user_input.lower().startswith("/exit") or user_input == "exit":
                    break
                elif user_input:
                    process_and_deliver_msg(user_input)
                    # Start context refresh asynchronously
                    asyncio.create_task(async_context_refresh_if_needed(context))
            except KeyboardInterrupt:
                console.clear()
                continue
            except EOFError:
                break


@app.command()
def upgrade(
    database_url: Optional[str] = typer.Option(None, envvar="ELROY_DATABASE_URL"),
):
    """Run Alembic database migrations"""
    assert database_url
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_cfg, "head")
    typer.echo("Database upgrade completed.")


def main():
    app()


if __name__ == "__main__":
    main()
