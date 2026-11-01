# 🐳 DockMate

**Your Docker container assistant for the Linux.**

DockMate makes it simple to install, and manage Docker containers.

---

## Features

- **Auto-detects Docker** — installs it for you if it's missing
- **Docker Hub search** — search and browse images directly from the terminal
- **Deterministic compose fetching** — automatically finds `docker-compose.yml` files from GitHub repos
- **One-command installs** — just type `install container name` and you're done
- **Full lifecycle management** — install, start, stop, update, remove, and view logs
- **Security warnings** — warns about untrusted images and Docker socket mounts
- **Zero dependencies** — pure Python 3 standard library, no pip installs needed

## Quick Start

```bash
# Clone the project
git clone https://github.com/campi997/dock-mate.git
cd dock-mate

# Make the launcher executable
chmod +x dockmate

# Run it
./dockmate
```

## Usage

```
  dockmate ›  help

  install <name> [-v <ver>]   Install any container autonomously
  search <term>               Search Docker Hub
  status                      List running DockMate containers
  start <name>                Start a previously installed container
  stop <name>                 Stop a running container
  remove <name>               Remove a container (data is kept)
  update <name> [-v <ver>]    Pull latest image and recreate, optionally set version
  logs <name> [n]             Show last n log lines (default 50)
  help                        Show this help message
  exit / quit                 Exit DockMate
```

### Examples

```bash
# Install a container — DockMate searches Docker Hub, lets you pick, then
# automatically finds the official docker-compose.yml from GitHub
dockmate ›  install jellyfin

# Install a specific version
dockmate ›  install nginx -v 1.25

# Install a direct image reference
dockmate ›  install linuxserver/sonarr:latest

# Search Docker Hub
dockmate ›  search monitoring

# See what's running
dockmate ›  status

# Update a container to the latest version
dockmate ›  update jellyfin

# Check the logs
dockmate ›  logs jellyfin 100
```

## How It Works

### Install Flow

```
User types: install <name>
      │
      ▼
Search Docker Hub → User picks image + version tag
      │
      ▼
Deterministic Compose Fetcher (ai_engine.py):
  1. Check Docker Hub repo metadata for a GitHub link
  2. If ghcr.io image, resolve GitHub repo directly
  3. Fallback: GitHub search API using container name
  4. Fetch known compose paths (docker-compose.yml, compose.yaml, etc.)
  5. If no file found, extract YAML from README.md code blocks
  6. If nothing found → null → falls through to manual config wizard
      │
      ▼
Show compose preview → User accepts or edits in nano
      │
      ▼
Create ~/dockmate-containers/<name>/ → docker compose pull → up -d
```

### Container Tracking

DockMate tracks containers using Docker Compose labels (`com.docker.compose.project.working_dir`) rather than container name prefixes. This means containers keep their official upstream names.

### Data Storage

All container data is stored under `~/dockmate-containers/<name>/`. Each container gets its own directory containing:
- `docker-compose.yml` — the compose configuration
- Bind-mounted data directories (adjacent to the yml file)

Removing a container keeps your data safe by default.

## Project Structure

```
dockmate/
├── dockmate                    # Entry point script (chmod +x, run directly)
└── dockmate_lib/               # Python package
    ├── __init__.py             # Package init, version
    ├── main.py                 # CLI app — system checks, command loop, dispatch
    ├── ai_engine.py            # Deterministic compose fetcher (Docker Hub + GitHub)
    ├── installer.py            # Container lifecycle — install, start, stop, remove, status, logs
    ├── docker_manager.py       # Docker/Compose detection, distro-aware installation
    ├── dockerhub.py            # Docker Hub search API client
    ├── inspector.py            # Docker image metadata inspector (ports, volumes, env)
    ├── ui.py                   # Terminal UI — colors, prompts, tables, spinner, banner
    └── config.py               # Config file management (legacy, not actively used)
```

## Requirements

- **Linux**
- **Python 3.6+** (pre-installed on most distros)

## License

MIT
