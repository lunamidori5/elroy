# Elroy

[![Discord](https://img.shields.io/discord/1200684659277832293?color=7289DA&label=Discord&logo=discord&logoColor=white)](https://discord.gg/5PJUY4eMce)

Elroy is a CLI AI personal assistant with long term memory and goal tracking capabilities. It features:

- **Long-term Memory**: Elroy maintains memories across conversations
- **Goal Tracking**: Track and manage personal/professional goals
- **Memory Panel**: Shows relevant memories during conversations

![Goals Demo](images/goals_demo.gif)


## Installation & Usage

### Prerequisites

- Relevant API keys (for simplest setup, set OPENAI_API_KEY)
- Database, either:
    - SQLite (sqlite-vec will be installed)
    - PostgreSQL with pgvector extension

By default, Elroy will use SQLite. To add a custom DB, you can provide your database url either via the `ELROY_DATABASE_URL`, the `database_url` config value, or via the `--database-url` startup flag.


### Option 1: Using Docker (Recommended)

#### Prerequisites
- Docker and Docker Compose

This option automatically sets up everything you need, including the required PostgreSQL database with pgvector extension.

1. Download the docker-compose.yml:
```bash
curl -O https://raw.githubusercontent.com/elroy-bot/elroy/main/docker-compose.yml
```

2. Run Elroy:
```bash
# to ensure you have the most up to date image
docker compose build --no-cache
docker compose run --rm elroy

# Add parameters as needed, e.g. here to use Anthropic's Sonnet model
docker compose run --rm elroy --sonnet
```

The Docker image is publicly available at `ghcr.io/elroy-bot/elroy`.

### Option 2: Using UV

#### Prerequisites
- UV [Local Install](https://docs.astral.sh/uv/getting-started/installation/)
- Relevant API keys (for simplest setup, set OPENAI_API_KEY)
- Database (SQLite or PostgreSQL with pgvector extension)

Install - ``uv tool install elroy``
Run - ``uv tool run elroy``

### Option 3: Using pip

#### Prerequisites
- Python 3.9 or higher
- Relevant API keys (for simplest setup, set OPENAI_API_KEY)
- Database (SQLite or PostgreSQL with pgvector extension)

```bash
pip install elroy
```

### Option 4: Installing from Source

#### Prerequisites
- Python 3.11 or higher
- Poetry package manager
- Relevant API keys (for simplest setup, set OPENAI_API_KEY)
- PostgreSQL database with pgvector extension

```bash
# Clone the repository
git clone https://github.com/elroy-bot/elroy.git
cd elroy

# Install dependencies and the package
poetry install

# Run Elroy
poetry run elroy
```

### Basic Usage

Once installed locally you can:
```bash
# Start the chat interface
elroy chat

# Or just 'elroy' which defaults to chat mode
elroy

# Process a single message and exit
elroy --message "Say hello world"

# Force use of a specific tool
elroy --message "Create a goal" --tool create_goal

# Elroy also accepts stdin
echo "Say hello world" | elroy
```

## Available Commands
![Remember command](images/remember_command.gif)

Elroy provides both CLI commands and in-chat commands (which can be used by both users and the assistant). For full schema information, see [tools schema reference](docs/tools_schema.md).


### Supported Models

#### Chat Models
- OpenAI Models: GPT-4o (default), GPT-4o-mini, O1, O1-mini
- Anthropic Models: Sonnet, Opus, Haiku
- OpenAI-Compatible APIs: Any provider offering OpenAI-compatible chat endpoints (via --openai-api-base)

#### Embedding Models
- OpenAI Models: text-embedding-3-small (default, 1536 dimensions)
- OpenAI-Compatible APIs: Any provider offering OpenAI-compatible embedding endpoints (via --openai-embedding-api-base)


### CLI Commands
These commands can be run directly from your terminal:

- `elroy chat` - Opens an interactive chat session (default command)
- `elroy message TEXT` - Process a single message and exit
  - Usage: `elroy message "Your message" [--tool TOOL_NAME]`
  - Example: `elroy message "Create a goal" --tool create_goal`

- `elroy remember [TEXT]` - Create a new memory from text or interactively
  - Usage: `elroy remember "Memory text"` or just `elroy remember` for interactive mode
  - Examples:
    - Interactive: `elroy remember` then type your memory
    - Direct: `elroy remember "Important meeting notes"`
    - From file: `cat notes.txt | elroy remember`

- `elroy list-models` - Lists supported chat models and exits
- `elroy print-config` - Shows current configuration and exits
  - `elroy print-config --show-secrets` to include API keys
  - Shows:
    - Current model settings
    - Database configuration
    - Memory management settings
    - Context management settings

- `elroy version` - Show version and exit

- `elroy set-persona TEXT` - Set a custom persona for the assistant
  - Example: `elroy set-persona "You are a helpful coding assistant"`
- `elroy reset-persona` - Removes any custom persona, reverting to the default
- `elroy show-persona` - Print the system persona and exit
- `elroy print-tools` - Display available tools and their schemas

Note: Running just `elroy` without any command will default to `elroy chat`.

The chat interface accepts input from stdin, so you can pipe text to Elroy:
```bash
# Process a single question
echo "What is 2+2?" | elroy chat

# Create a memory from file content
cat meeting_notes.txt | elroy remember

# Use a specific tool with piped input
echo "Buy groceries" | elroy message --tool create_goal
```

### In-Chat Commands
While chatting with Elroy, commands can be used by typing a forward slash (/) followed by the command name. Commands are divided into two categories:

#### User-Only Commands
These commands can only be used by human users:

- `/help` - Show all available commands
- `/print_system_instruction` - View current system instructions
- `/refresh_system_instructions` - Refresh system instructions
- `/reset_messages` - Reset conversation context
- `/print_context_messages` - View current conversation context
- `/add_internal_thought` - Insert an internal thought for the assistant
- `/print_config` - Display current configuration settings
- `/create_bug_report` - Create a detailed bug report with current context
- `/set_assistant_name` - Set a custom name for the assistant
- `/exit` - Exit the chat

#### Assistant and User Commands
These commands can be used by both users and Elroy:

##### Goal Management
- `/create_goal` - Create a new goal with name, description and optional deadline
- `/rename_goal` - Rename an existing goal while preserving its history
- `/print_goal` - View details of a specific goal including status updates
- `/add_goal_to_current_context` - Add a goal to current conversation for focused discussion
- `/drop_goal_from_current_context` - Remove goal from current conversation
- `/add_goal_status_update` - Update goal progress with new status information
- `/mark_goal_completed` - Mark a goal as complete with final status
- `/delete_goal_permanently` - Permanently delete a goal and its history
- `/get_active_goal_names` - List all currently active goals

##### Memory Management
- `/create_memory` - Create a new long-term memory from text
- `/print_memory` - View a specific memory's full content
- `/add_memory_to_current_context` - Add a memory to current conversation for reference
- `/drop_memory_from_current_context` - Remove memory from current conversation

##### Reflection & Contemplation
- `/contemplate [prompt]` - Ask Elroy to reflect on the conversation or a specific topic

##### User Preferences
- `/get_user_full_name` - Get your stored full name
- `/set_user_full_name` - Set your full name for personalization
- `/get_user_preferred_name` - Get your stored preferred name/nickname
- `/set_user_preferred_name` - Set your preferred name for casual interaction

##### Development Tools
- `/tail_elroy_logs` - View Elroy's log output for debugging
- `/make_coding_edit` - Make changes to code files in the current repository

Note: All these commands can be used with a leading slash (/) in the chat interface. The assistant uses these commands without the slash when helping you.


## Customization

You can customize Elroy's appearance with these options:

- `--system-message-color TEXT` - Color for system messages
- `--user-input-color TEXT` - Color for user input
- `--assistant-color TEXT` - Color for assistant output
- `--warning-color TEXT` - Color for warning messages



## Configuration Options

### Basic Configuration
* `--tool TEXT`: Specifies the tool to use in responding to a message. If specified, the assistant MUST use the tool in responding. Only valid when processing a single message.
* `--config TEXT`: Path to YAML configuration file. Values override defaults but are overridden by explicit flags or environment variables.
* `--default-persona TEXT`: Default persona to use for assistants. [env var: ELROY_DEFAULT_PERSONA]
* `--debug / --no-debug`: Whether to fail fast when errors occur, and emit more verbose logging. [env var: ELROY_DEBUG]
* `--user-token TEXT`: User token to use for Elroy [env var: ELROY_USER_TOKEN]

### Database Configuration
* `--database-url TEXT`: Valid SQLite or Postgres URL for the database. If Postgres, the pgvector extension must be installed. [env var: ELROY_DATABASE_URL]

### API Configuration
* `--openai-api-key TEXT`: OpenAI API key, required for OpenAI (or OpenAI compatible) models. [env var: OPENAI_API_KEY]
* `--openai-api-base TEXT`: OpenAI API (or OpenAI compatible) base URL. [env var: OPENAI_API_BASE]
* `--openai-embedding-api-base TEXT`: OpenAI API (or OpenAI compatible) base URL for embeddings. [env var: OPENAI_API_BASE]
* `--openai-organization TEXT`: OpenAI (or OpenAI compatible) organization ID. [env var: OPENAI_ORGANIZATION]
* `--anthropic-api-key TEXT`: Anthropic API key, required for Anthropic models. [env var: ANTHROPIC_API_KEY]

### Model Configuration
* `--chat-model TEXT`: The model to use for chat completions. [env var: ELROY_CHAT_MODEL] [default: (gpt-4o)]
* `--embedding-model TEXT`: The model to use for text embeddings. [env var: ELROY_EMBEDDING_MODEL] [default: text-embedding-3-small]
* `--embedding-model-size INTEGER`: The size of the embedding model. [default: 1536]
* `--enable-caching / --no-enable-caching`: Whether to enable caching for the LLM, both for embeddings and completions. [default: True]
* `--sonnet`: Use Anthropic's Sonnet model
* `--opus`: Use Anthropic's Opus model
* `--4o`: Use OpenAI's GPT-4o model
* `--4o-mini`: Use OpenAI's GPT-4o-mini model
* `--o1`: Use OpenAI's o1 model
* `--o1-mini`: Use OpenAI's o1-mini model

### Context Management
* `--context-refresh-trigger-tokens INTEGER`: Number of tokens that triggers a context refresh and compression of messages in the context window. [default: 3300]
* `--max-assistant-loops INTEGER`: Maximum number of loops the assistant can run before tools are temporarily made unavailable. [default: 4]
* `--context-refresh-target-tokens INTEGER`: Target number of tokens after context refresh / compression, how many tokens to aim to keep in context. [default: 1650]
* `--max-context-age-minutes FLOAT`: Maximum age in minutes to keep. Messages older than this will be dropped from context, regardless of token limits. [default: 120.0]
* `--context-refresh-interval-minutes FLOAT`: How often in minutes to refresh system message and compress context. [default: 10.0]
* `--min-convo-age-for-greeting-minutes FLOAT`: Minimum age in minutes of conversation before the assistant will offer a greeting on login. [default: 10.0]
* `--enable-assistant-greeting / --no-enable-assistant-greeting`: Whether to allow the assistant to send the first message [default: True]

### Memory Management
* `--memories-between-consolidation INTEGER`: How many memories to create before triggering a memory consolidation operation. [default: 4]
* `--l2-memory-relevance-distance-threshold FLOAT`: L2 distance threshold for memory relevance. [default: 1.24]
* `--memory-cluster-similarity-threshold FLOAT`: Threshold for memory cluster similarity. [default: 0.21125]
* `--max-memory-cluster-size INTEGER`: The maximum number of memories that can be consolidated into a single memory at once. [default: 5]
* `--min-memory-cluster-size INTEGER`: The minimum number of memories that can be consolidated into a single memory at once. [default: 3]
* `--initial-context-refresh-wait-seconds INTEGER`: Initial wait time in seconds after login before the initial context refresh and compression. [default: 600]

### UI Configuration
* `--show-internal-thought`: Show the assistant's internal thought monologue. [default: False]
* `--system-message-color TEXT`: Color for system messages. [default: #9ACD32]
* `--user-input-color TEXT`: Color for user input. [default: #FFE377]
* `--assistant-color TEXT`: Color for assistant output. [default: #77DFD8]
* `--warning-color TEXT`: Color for warning messages. [default: yellow]
* `--internal-thought-color TEXT`: Color for internal thought messages. [default: #708090]

### Logging
* `--log-file-path TEXT`: Where to write logs. [env var: ELROY_LOG_FILE_PATH]

### Shell Integration
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.


## License

Distributed under the GPL 3.0.1 License. See `LICENSE` for more information.
