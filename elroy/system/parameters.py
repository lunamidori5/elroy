import os

CLI_USER_ID = 1

### Model parameters ###

CHAT_MODEL = os.getenv("ELROY_CHAT_MODEL", "gpt-4o")
MEMORY_PROCESSING_MODEL = os.getenv("MEMORY_PROCESSING_MODEL", "gpt-4o-mini")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_SIZE = 1536

L2_MEMORY_RELEVANCE_DISTANCE_THRESHOLD = 1.24

L2_MEMORY_CONSOLIDATION_DISTANCE_THRESHOLD = 0.65


RESULT_SET_LIMIT_COUNT = 5

# String constants

UNKNOWN = "Unknown"

INNER_THOUGHT_TAG = "inner_thought_monologue"

MEMORY_WORD_COUNT_LIMIT = 300
DEFAULT_OUTPUT_COLOR = "#77DFD8"
DEFAULT_INPUT_COLOR = "#FFE377"
SYSTEM_MESSAGE_COLOR = "#9ACD32"
