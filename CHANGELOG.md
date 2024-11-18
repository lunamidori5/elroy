# Changelog

All notable changes to this project will be documented in this file.

## [0.0.42] - 2024-11-17

### Added
- Updated README to document all startup options and system commands for better user guidance.
- Added more verbose error output for tool calls to improve debugging and error tracking.

### Fixed
- Improved autocomplete functionality by filtering goals and memories for more relevant options.
- Simplified demo recording script for easier demonstration creation.

### Improved
- Enhanced error handling for goal-related functions to better surface available goals.
- Added override parameters to name setting functions to discourage redundant calls.
- Provided additional context in login messages for a more informative user experience.

### Infrastructure
- Added a `wait-for-pypi` job to verify package availability before Docker publishing, ensuring smoother deployment processes.

## [0.0.41] - 2024-11-14

Updates to package publishing

## [0.0.40] - 2024-11-14
### Added
- Initial release of Elroy, a CLI AI personal assistant with long-term memory and goal tracking capabilities.
- Features include long-term memory, goal tracking, and a memory panel for relevant memories during conversations.
- Supports installation via Docker, pip, or from source.
- Includes commands for system management, goal management, memory management, user preferences, and conversation handling.