import os
import platform
import sys
import urllib.parse
import webbrowser
from datetime import datetime
from pprint import pformat
from typing import Optional

import scrubadub
from toolz import pipe
from toolz.curried import keyfilter

from .. import __version__
from ..config.constants import BUG_REPORT_LOG_LINES, REPO_ISSUES_URL
from ..config.ctx import ElroyContext


def tail_elroy_logs(ctx: ElroyContext, lines: int = 10) -> str:
    """
    Returns the last `lines` of the Elroy logs.
    Useful for troubleshooting in cases where errors occur (especially with tool calling).

    Args:
        context (ElroyContext): context obj
        lines (int, optional): Number of lines to return. Defaults to 10.

    Returns:
        str: The last `lines` of the Elroy logs
    """
    with open(ctx.log_file_path, "r") as f:
        return "".join(f.readlines()[-lines:])


def print_config(ctx: ElroyContext) -> None:
    """
    Prints the current Elroy configuration in a formatted table.
    Useful for troubleshooting and verifying the current configuration.

    Args:
        ctx (ElroyContext): context obj
    """
    from rich.table import Table
    from rich.console import Console

    sections = {
        "Basic Configuration": {
            "Debug Mode": ctx.debug,
            "Log File": str(ctx.log_file_path),
            "Default Assistant Name": ctx.default_assistant_name,
            "User Token": ctx.user_token,
            "User ID": ctx.user_id,
        },
        "Model Configuration": {
            "Chat Model": ctx.chat_model_name,
            "Embedding Model": ctx.embedding_model_name,
            "Embedding Model Size": ctx.embedding_model_size,
            "Caching Enabled": ctx.enable_caching,
        },
        "API Configuration": {
            "OpenAI API Base": ctx.openai_api_base or "default",
            "OpenAI Embedding API Base": ctx.openai_embedding_api_base or "default",
            "OpenAI Organization": ctx.openai_organization or "none",
        },
        "Context Management": {
            "Max Assistant Loops": ctx.max_assistant_loops,
            "Context Refresh Trigger Tokens": ctx.context_refresh_trigger_tokens,
            "Context Refresh Target Tokens": ctx.context_refresh_target_tokens,
            "Max Context Age (minutes)": ctx.max_context_age_minutes,
            "Context Refresh Interval (minutes)": ctx.context_refresh_interval_minutes,
        },
        "Memory Management": {
            "Memory Cluster Similarity": ctx.memory_cluster_similarity_threshold,
            "Max Memory Cluster Size": ctx.max_memory_cluster_size,
            "Min Memory Cluster Size": ctx.min_memory_cluster_size,
            "Memories Between Consolidation": ctx.memories_between_consolidation,
            "L2 Memory Relevance Distance": ctx.l2_memory_relevance_distance_threshold,
        },
        "UI Configuration": {
            "Show Internal Thought": ctx.show_internal_thought,
            "System Message Color": ctx.system_message_color,
            "Assistant Color": ctx.assistant_color,
            "User Input Color": ctx.user_input_color,
            "Warning Color": ctx.warning_color,
            "Internal Thought Color": ctx.internal_thought_color,
        }
    }

    console = Console()
    table = Table(title="Elroy Configuration", show_header=True, header_style="bold magenta")
    table.add_column("Section")
    table.add_column("Setting")
    table.add_column("Value")

    for section, settings in sections.items():
        for setting, value in settings.items():
            table.add_row(
                section if setting == list(settings.keys())[0] else "",  # Only show section name once
                setting,
                str(value)
            )
        table.add_row("", "", "")  # Add empty row between sections

    console.print(table)


def create_bug_report(
    ctx: ElroyContext,
    title: str,
    description: Optional[str],
) -> None:
    """
    Generate a bug report and open it as a GitHub issue.

    Args:
        context: The Elroy context
        title: The title for the bug report
        description: Detailed description of the issue
    """
    # Start building the report
    report = [
        f"# Bug Report: {title}",
        f"\nCreated: {datetime.now().isoformat()}",
        "\n## Description",
        description if description else "",
    ]

    # Add system information
    report.extend(
        [
            "\n## System Information",
            f"OS: {platform.system()} {platform.release()}",
            f"Python: {sys.version}",
            f"Elroy Version: {__version__}",
        ]
    )

    report.append(f"\n## Recent Logs (last {BUG_REPORT_LOG_LINES} lines)")
    try:
        logs = tail_elroy_logs(ctx, BUG_REPORT_LOG_LINES)
        report.append("```")
        report.append(logs)
        report.append("```")
    except Exception as e:
        report.append(f"Error fetching logs: {str(e)}")

    # Combine the report
    full_report = scrubadub.clean("\n".join(report))

    github_url = None
    base_url = os.path.join(REPO_ISSUES_URL, "new")
    params = {"title": title, "body": full_report}
    github_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    webbrowser.open(github_url)
