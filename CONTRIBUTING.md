# Contributing to ease-Desk

First off, thank you for considering contributing to `ease-Desk`! It's people like you that make ease-Desk such a great lightweight cloud desktop environment. 

## Project Architecture

`ease-Desk` is built with a mix of Python (GTK3 for the UI), Bash (installation & lifecycle), and Rust (for high-performance system integrations). The repository is structured into several key modules:

- **`desktop/`**: Contains the core desktop UI components.
  - `session.py`: The main orchestrator that manages Openbox and the GTK desktop shell.
  - `shell.py`: The desktop environment shell (panels, docks, wallpaper).
  - `game_changer.py`: The GNOME-inspired spotlight search overlay.
  - `task_manager/`, `media_player/`, `settings/`, `terminal/`: Core system applications.

- **`file_manager/`**: A fully functional, lightweight file manager (`This PC`) built with GTK3.
  - `gui.py`: The main user interface.
  - `core/fs.py`: Core filesystem operations (copy, move, delete, permissions).
  - `viewer.py`: Built-in text and image viewers.

- **`shared/`**: Contains shared utilities and configurations used across applications.
  - `utilities/sysinfo.py`: Hardware metrics and system info fetching.
  - `utilities/animate.py`: GTK animation helpers.
  - `openbox_theme/`: Window manager configurations and styles.

- **`scripts/`**: Automation scripts for setup and deployment.
  - `install.sh`: The robust, multi-distro deployment script.
  - `entrypoint.sh`: The Docker entrypoint script.

- **`src/` (Rust)**: The native high-performance Rust core that provides fast system bindings when compiled with `maturin`.

## Commit Message Guidelines

We use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) to make our history clear and easy to read. Please ensure all your commits follow this standard.

### Format

```
<type>(<scope>): <subject>

<body>
```

### Types
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools and libraries

### Example
```
feat(shell): add spotlight search functionality

Implemented a GNOME-style spotlight search overlay that can be triggered via a keyboard shortcut. It searches through installed apps and pinned configurations.
```

## Code Style

- **Python**: We follow standard PEP 8. Please ensure you add a descriptive docstring to the top of any new file you create.
- **Shell**: Use `set -euo pipefail` at the top of scripts and ensure proper quoting.

## Getting Started

1. Fork the repository
2. Install via `./scripts/install.sh` or use Docker (`docker-compose up -d --build`)
3. Make your changes and test them locally
4. Submit a Pull Request

Happy coding!
