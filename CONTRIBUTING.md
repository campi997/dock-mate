# Contributing to DockMate — AI Agent Handoff Guide

This document is written specifically for AI coding agents picking up this project.
It explains the architecture, design decisions, current state, and what's left to do.

---

## Architecture Overview

DockMate is a **pure Python 3 CLI tool** (no pip dependencies) that helps users discover, install, and manage Docker containers on Linux. It runs as an interactive REPL.

### Entry Point

`./dockmate` → imports `dockmate_lib.main` → calls `main()` → creates `DockMate()` instance → runs system checks → enters command loop.

### Module Responsibilities

| Module | Purpose |
|---|---|
| `main.py` | CLI app shell. System checks, command dispatch, install flow, update flow. The `_cmd_install` method is the main entry point for installations. |
| `ai_engine.py` | **Deterministic compose fetcher.** Despite the legacy name, this contains NO AI/LLM code. It fetches `docker-compose.yml` files from GitHub using public APIs (Docker Hub + GitHub REST API). The `generate_compose(container_name, docker_image)` function is the main entry point. |
| `installer.py` | Container lifecycle. Install (both raw compose and custom/manual), start, stop, remove, status listing, log retrieval. Uses `docker compose` CLI under the hood. |
| `docker_manager.py` | Docker/Compose detection and distro-aware Docker installation. Reads `/etc/os-release` and routes to the right package manager. |
| `dockerhub.py` | Docker Hub search API client. Returns structured results. |
| `inspector.py` | Pulls a Docker image and inspects its metadata (`docker inspect`) to extract default ports, volumes, and environment variables. Used for the manual config fallback. |
| `ui.py` | All terminal output — ANSI colors, prompts, confirmations, tables, spinner, banner. |
| `config.py` | Legacy config file manager (`~/.dockmate_config.json`). Currently stores a Cohere API key that is **no longer used**. Safe to repurpose or remove. |

### Install Flow (the main feature)

```
_cmd_install(args)
  → dockerhub.search(name)           # Search Docker Hub
  → User picks image + version tag
  → ai_engine.generate_compose(name, docker_image=selected)
      → Try Docker Hub API for GitHub repo link
      → Try GitHub search API
      → Fetch known compose file paths from repo
      → Fallback: regex YAML from README.md
      → Returns compose YAML string or None
  → If compose found:
      installer.install_raw_compose(name, compose_content)
        → Shows preview, user accepts or edits in nano
        → Creates ~/dockmate-containers/<name>/
        → Writes docker-compose.yml
        → docker compose pull && up -d
  → If compose NOT found:
      _install_custom_image(selected)
        → inspector.inspect_image() for defaults
        → Interactive prompts for ports, volumes, env
        → installer.install_custom_container()
```

### Container Tracking

Status tracking (`list_running`) uses Docker Compose labels:
- `com.docker.compose.project.working_dir` — matches against `~/dockmate-containers/`
- This means containers can have ANY `container_name` — no prefix required

Log retrieval (`get_logs`) also uses this label to find the actual container name dynamically.

---

## Design Decisions & History

1. **No LLM/AI**: The project originally used Gemini, then Groq Compound for compose generation. This was replaced with a deterministic GitHub-based pipeline because LLMs hallucinated volume paths, container names, and ports. The file is still called `ai_engine.py` for backwards compatibility.

2. **No external Python dependencies**: Everything uses `urllib.request`, `json`, `subprocess`, `re`, `os` from the standard library. No pip installs. This is intentional — the tool should work on a fresh Linux install with just Python 3.

3. **No API keys needed**: Both Docker Hub's public API and GitHub's public REST API work without authentication for the read-only lookups DockMate performs.

4. **Container names use upstream defaults**: The compose files fetched from GitHub keep the original `container_name` from the upstream project. DockMate does NOT prefix names with `dockmate-`.

5. **Data lives next to the compose file**: All bind mounts use relative paths (`./data:/app/data`) so data directories sit inside `~/dockmate-containers/<name>/`.

---

## Known Issues & Technical Debt

### Bugs
- `installer.py` line 176: unreachable `return True` after an earlier `return True` on line 174 in `install_custom_container()`.
- `installer.py` line 48: `generate_custom_compose()` still hardcodes `container_name: dockmate-{container_name}` — inconsistent with the rest of the system which no longer uses the prefix. Fix it to just use `{container_name}`.
- `installer.py` line 128: `install_custom_container()` still prints `Container name: dockmate-{container_name}` — same prefix issue.
- `config.py`: Still references "cohere_api_key" — this is dead code since the LLM was removed. Can be cleaned up or repurposed.

### Missing Features (from user's backlog)
- **Version selection via `-v` flags during update**: The `_cmd_update` method in `main.py` already supports `-v` for changing image tags, but it hasn't been extensively tested.
- **Docker distribution compatibility**: Handle edge cases for niche Linux distributions during Docker installation.
- **Official Docker Hub images**: When a user picks an "official" image (like `nginx`, `postgres`), these use the `library/` namespace on Docker Hub. The compose fetcher may not find GitHub repos for these since official images often don't have a simple 1:1 GitHub mapping. Consider a curated fallback catalog for the top ~50 official images.
- **GitHub API rate limiting**: Unauthenticated GitHub API requests are limited to 60/hour. Consider optional token support for heavy users.

### Improvement Ideas
- Rename `ai_engine.py` to something like `compose_fetcher.py` to reflect what it actually does now.
- Add `compose.yml` (without the `docker-` prefix) to the list of paths checked in the fetcher.
- Add support for checking GitHub releases for compose files (some projects put them there).
- Add a `list` command that shows all installed containers (by scanning `~/dockmate-containers/`).

---

## Testing

There are no automated tests. To manually test:

```bash
cd /path/to/dock-mate
chmod +x dockmate
./dockmate

# Then inside the REPL:
install dockhand      # Tests the full deterministic fetch pipeline
status                # Tests container tracking via Docker labels
logs dockhand         # Tests dynamic container name resolution
stop dockhand         # Tests compose-based lifecycle
remove dockhand       # Tests removal + data cleanup prompt
```

---

## File Locations at Runtime

| Path | Purpose |
|---|---|
| `~/dockmate-containers/` | Base directory for all installed containers |
| `~/dockmate-containers/<name>/docker-compose.yml` | Compose file for each container |
| `~/dockmate-containers/<name>/data/`, `./config/`, etc. | Bind-mounted data directories |
| `~/.dockmate_config.json` | Legacy config file (currently unused) |
