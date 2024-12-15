from functools import partial
from typing import Optional

import typer
from toolz import first, pipe
from toolz.curried import filter

from ..config.constants import LIST_MODELS_FLAG, MODEL_SELECTION_CONFIG_PANEL
from ..config.models import resolve_anthropic
from .chat import handle_chat
from .config import handle_list_models, handle_show_config, handle_show_version
from .options import CliOption, model_alias_typer_option
from .remember import handle_remember, handle_remember_file

app = typer.Typer(
    help="Elroy CLI",
    context_settings={"obj": {}},
    no_args_is_help=False,  # Don't show help when no args provided
    callback=None,  # Important - don't use a default command
)


@app.callback(invoke_without_command=True)
def common(
    # Basic Configuration
    ctx: typer.Context,
    config_file: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to YAML configuration file. Values override defaults but are overridden by explicit flags or environment variables.",
        rich_help_panel="Basic Configuration",
    ),
    debug: bool = CliOption(
        "debug",
        help="Whether to fail fast when errors occur, and emit more verbose logging.",
        rich_help_panel="Basic Configuration",
    ),
    user_token: str = CliOption(
        "user_token",
        help="User token to use for Elroy",
        rich_help_panel="Basic Configuration",
    ),
    # Database Configuration
    postgres_url: Optional[str] = CliOption(
        "postgres_url",
        envvar="ELROY_POSTGRES_URL",
        help="Postgres URL to use for Elroy.",
        rich_help_panel="Database Configuration",
    ),
    # API Configuration
    openai_api_key: Optional[str] = CliOption(
        "openai_api_key",
        envvar="OPENAI_API_KEY",
        help="OpenAI API key, required for OpenAI (or OpenAI compatible) models.",
        rich_help_panel="API Configuration",
    ),
    openai_api_base: Optional[str] = CliOption(
        "openai_api_base",
        envvar="OPENAI_API_BASE",
        help="OpenAI API (or OpenAI compatible) base URL.",
        rich_help_panel="API Configuration",
    ),
    openai_embedding_api_base: Optional[str] = CliOption(
        "openai_embedding_api_base",
        envvar="OPENAI_API_BASE",
        help="OpenAI API (or OpenAI compatible) base URL for embeddings.",
        rich_help_panel="API Configuration",
    ),
    openai_organization: Optional[str] = CliOption(
        "openai_organization",
        envvar="OPENAI_ORGANIZATION",
        help="OpenAI (or OpenAI compatible) organization ID.",
        rich_help_panel="API Configuration",
    ),
    anthropic_api_key: Optional[str] = CliOption(
        "anthropic_api_key",
        envvar="ANTHROPIC_API_KEY",
        help="Anthropic API key, required for Anthropic models.",
        rich_help_panel="API Configuration",
    ),
    # Model Configuration
    chat_model: str = CliOption(
        "chat_model",
        envvar="ELROY_CHAT_MODEL",
        help="The model to use for chat completions.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    embedding_model: str = CliOption(
        "embedding_model",
        help="The model to use for text embeddings.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    embedding_model_size: int = CliOption(
        "embedding_model_size",
        help="The size of the embedding model.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    enable_caching: bool = CliOption(
        "enable_caching",
        help="Whether to enable caching for the LLM, both for embeddings and completions.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    # Context Management
    context_refresh_trigger_tokens: int = CliOption(
        "context_refresh_trigger_tokens",
        help="Number of tokens that triggers a context refresh and compresion of messages in the context window.",
        rich_help_panel="Context Management",
    ),
    context_refresh_target_tokens: int = CliOption(
        "context_refresh_target_tokens",
        help="Target number of tokens after context refresh / context compression, how many tokens to aim to keep in context.",
        rich_help_panel="Context Management",
    ),
    max_context_age_minutes: float = CliOption(
        "max_context_age_minutes",
        help="Maximum age in minutes to keep. Messages older tha this will be dropped from context, regardless of token limits",
        rich_help_panel="Context Management",
    ),
    context_refresh_interval_minutes: float = CliOption(
        "context_refresh_interval_minutes",
        help="How often in minutes to refresh system message and compress context.",
        rich_help_panel="Context Management",
    ),
    min_convo_age_for_greeting_minutes: float = CliOption(
        "min_convo_age_for_greeting_minutes",
        help="Minimum age in minutes of conversation before the assistant will offer a greeting on login.",
        rich_help_panel="Context Management",
    ),
    # Memory Management
    l2_memory_relevance_distance_threshold: float = CliOption(
        "l2_memory_relevance_distance_threshold",
        help="L2 distance threshold for memory relevance.",
        rich_help_panel="Memory Management",
    ),
    l2_memory_consolidation_distance_threshold: float = CliOption(
        "l2_memory_consolidation_distance_threshold",
        help="L2 distance threshold for memory consolidation.",
        rich_help_panel="Memory Management",
    ),
    initial_context_refresh_wait_seconds: int = CliOption(
        "initial_context_refresh_wait_seconds",
        help="Initial wait time in seconds after login before the initial context refresh and compression.",
        rich_help_panel="Memory Management",
    ),
    # UI Configuration
    show_internal_thought: bool = CliOption(
        "show_internal_thought",
        help="Show the assistant's internal thought monologue like memory consolidation and internal reflection.",
        rich_help_panel="UI Configuration",
    ),
    system_message_color: str = CliOption(
        "system_message_color",
        help="Color for system messages.",
        rich_help_panel="UI Configuration",
    ),
    user_input_color: str = CliOption(
        "user_input_color",
        help="Color for user input.",
        rich_help_panel="UI Configuration",
    ),
    assistant_color: str = CliOption(
        "assistant_color",
        help="Color for assistant output.",
        rich_help_panel="UI Configuration",
    ),
    warning_color: str = CliOption(
        "warning_color",
        help="Color for warning messages.",
        rich_help_panel="UI Configuration",
    ),
    internal_thought_color: str = CliOption(
        "internal_thought_color",
        help="Color for internal thought messages.",
        rich_help_panel="UI Configuration",
    ),
    # Logging
    log_file_path: str = CliOption(
        "log_file_path",
        envvar="ELROY_LOG_FILE_PATH",
        help="Where to write logs.",
        rich_help_panel="Logging",
    ),
    # Commmands
    chat: bool = typer.Option(
        False,
        "--chat",
        help="Opens an interactive chat session, or generates a response to stdin input. THe default command.",
        rich_help_panel="Commands",
    ),
    remember: bool = typer.Option(
        False,
        "--remember",
        "-r",
        help="Create a new memory from stdin or interactively",
        rich_help_panel="Commands",
    ),
    remember_file: Optional[str] = typer.Option(
        None,
        "--remember-file",
        "-f",
        help="File to read memory text from when using --remember",
        rich_help_panel="Commands",
    ),
    list_models: bool = typer.Option(
        False,
        LIST_MODELS_FLAG,
        help="Lists supported chat models and exits",
        rich_help_panel="Commands",
    ),
    show_config: bool = typer.Option(
        False,
        "--show-config",
        help="Shows current configuration and exits.",
        rich_help_panel="Commands",
    ),
    version: bool = typer.Option(
        None,
        "--version",
        help="Show version and exit.",
        rich_help_panel="Commands",
    ),
    sonnet: bool = model_alias_typer_option("sonnet", "Use Anthropic's Sonnet model", lambda: resolve_anthropic("sonnet")),
    opus: bool = model_alias_typer_option("opus", "Use Anthropic's Opus model", lambda: resolve_anthropic("opus")),
    gpt4o: bool = model_alias_typer_option("4o", "Use OpenAI's GPT-4o model", lambda: "gpt-4o"),
    gpt4o_mini: bool = model_alias_typer_option("4o-mini", "Use OpenAI's GPT-4o-mini model", lambda: "gpt-4o-mini"),
    o1: bool = model_alias_typer_option("o1", "OpenAI's o1 model", lambda: "o1-preview"),
    o1_mini: bool = model_alias_typer_option("o1-mini", "Use OpenAI's o1-mini model", lambda: "o1-mini"),
):
    """Common parameters."""
    pipe(
        [
            (show_config, partial(handle_show_config, ctx)),
            (version, handle_show_version),
            (list_models, handle_list_models),
            (remember_file, partial(handle_remember_file, ctx, remember_file)),
            (remember, partial(handle_remember, ctx)),
            (True, partial(handle_chat, ctx)),  # Chat is default
        ],
        filter(lambda x: x[0]),
        first,
        lambda x: x[1](),
    )


if __name__ == "__main__":
    app()
