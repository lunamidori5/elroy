# Elroy

Elroy is a CLI AI personal assistant with long term memory and goal tracking capabilities. It can:

- Remember important information across conversations
- Track and help you achieve your goals
- Maintain context of your ongoing discussions
- Customize its behavior to your preferences

## Installation

There are two ways to install and run Elroy:

### 1. Using pipx (Recommended)

#### Prerequisites
- Python 3.11 or higher
- pipx: Install with `python3.11 -m pip install --user pipx`
- OpenAI key: Set the `OPENAI_API_KEY` environment variable

#### Installation
```
pip install elroy
```

To run:
```bash
# Start the chat interface
elroy chat

# Or just 'elroy' which defaults to chat mode
elroy

```

## Available Commands

While chatting with Elroy, you can use these commands:

### System Commands
- `/print_available_commands` - Show all available commands
- `/print_system_instruction` - View current system instructions
- `/refresh_system_instructions` - Refresh system instructions
- `/reset_system_context` - Reset conversation context
- `/print_context_messages` - View current conversation context

### Goal Management
- `/create_goal` - Create a new goal
- `/rename_goal` - Rename an existing goal
- `/print_goal` - View details of a specific goal
- `/add_goal_to_current_context` - Add a goal to current conversation
- `/drop_goal_from_current_context_only` - Remove goal from current context
- `/add_goal_status_update` - Update goal progress
- `/mark_goal_completed` - Mark a goal as complete
- `/delete_goal_permamently` - Delete a goal

### Memory Management
- `/print_memory` - View a specific memory
- `/create_memory` - Create a new memory

### User Preferences
- `/get_user_full_name` - Get your full name
- `/set_user_full_name` - Set your full name
- `/get_user_preferred_name` - Get your preferred name
- `/set_user_preferred_name` - Set your preferred name

### Conversation
- `/contemplate` - Ask Elroy to reflect on the conversation
- `/start_aider_session` - Start an AI-powered coding session (experimental)
- `/exit` - Exit the chat

You can also pipe text directly to Elroy:
```bash
echo "Summarize this" | elroy
```

## Features

- **Long-term Memory**: Elroy maintains memories across conversations
- **Goal Tracking**: Track and manage personal/professional goals
- **Context Awareness**: Maintains conversation context with configurable token limits
- **Auto-updates**: Checks for new versions and database updates
- **Memory Panel**: Shows relevant memories during conversations
- **Name Customization**: Remembers and uses your preferred name

## Customization

You can customize Elroy's appearance with these options:

- `--system-message-color TEXT` - Color for system messages
- `--user-input-color TEXT` - Color for user input
- `--assistant-color TEXT` - Color for assistant output
- `--warning-color TEXT` - Color for warning messages

### System Requirements

Elroy requires Python > 3.11

### Database Requirement

Elroy needs a PostgreSQL database. By default, it will use Docker to automatically manage a PostgreSQL instance for you. You have two options:

1. Let Elroy manage PostgreSQL (Default):
   - Requires Docker to be installed and running
   - Elroy will automatically create and manage a PostgreSQL container

2. Use your own PostgreSQL (Advanced):
   - Set ELROY_POSTGRES_URL to your database connection string
   - Docker is not required in this case

In either case, you'll need:
- OpenAI key: Set the `OPENAI_API_KEY` environment variable



## Options

* `--version`: Show version and exit.
* `--postgres-url TEXT`: Postgres URL to use for Elroy. If set, ovverrides use_docker_postgres.  [env var: ELROY_POSTGRES_URL]
* `--openai-api-key TEXT`: OpenAI API key, required.  [env var: OPENAI_API_KEY]
* `--context-window-token-limit INTEGER`: How many tokens to keep in context before compressing. Controls how much conversation history Elroy maintains before summarizing older content. [env var: ELROY_CONTEXT_WINDOW_TOKEN_LIMIT]
* `--log-file-path TEXT`: Where to write logs.  [env var: ELROY_LOG_FILE_PATH; default: /Users/tombedor/development/elroy/logs/elroy.log]
* `--use-docker-postgres / --no-use-docker-postgres`: If true and postgres_url is not set, will attempt to start a Docker container for Postgres.  [env var: USE_DOCKER_POSTGRES; default: use-docker-postgres]
* `--stop-docker-postgres-on-exit / --no-stop-docker-postgres-on-exit`: Whether or not to stop the Postgres container on exit.  [env var: STOP_DOCKER_POSTGRES_ON_EXIT; default: no-stop-docker-postgres-on-exit]
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.


## License

Distributed under the GPL 3.0.1 License. See `LICENSE` for more information.
