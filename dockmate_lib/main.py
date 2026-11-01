#!/usr/bin/env python3
"""Main application — system checks, interactive command loop, and routing."""

import sys
import os
import subprocess

from . import ui
from . import docker_manager
from . import dockerhub
from . import installer
from . import inspector
from . import ai_engine


class DockMate:
    """Interactive DockMate session."""

    def __init__(self):
        self.install_base = installer.DEFAULT_INSTALL_BASE
        self.system_status = None

    # ── Entry point ────────────────────────────────────────────────────────

    def run(self):
        ui.show_banner()
        self._check_python_deps()
        self._check_system()
        self._command_loop()

    # ── System checks ──────────────────────────────────────────────────────

    def _check_python_deps(self):
        """Auto-install required Python dependencies if missing."""
        # No external dependencies currently required.
        pass

    def _check_system(self):
        ui.header("System Check")

        self.system_status = docker_manager.check_system()

        # Docker installed?
        if self.system_status["docker_installed"]:
            ui.success(self.system_status["docker_version"])
        else:
            ui.error("Docker is not installed")
            print()
            if ui.confirm("Would you like to install Docker now?"):
                if docker_manager.install_docker():
                    self.system_status = docker_manager.check_system()
                else:
                    ui.error("Installation failed. Please install Docker manually.")
                    ui.info("https://docs.docker.com/engine/install/")
                    sys.exit(1)
            else:
                ui.warning("Docker is required. Install it and try again.")
                sys.exit(0)

        # Daemon running?
        if self.system_status["docker_running"]:
            ui.success("Docker daemon is running")
        elif self.system_status.get("docker_state") == "permission_denied":
            ui.error("Permission denied when connecting to Docker daemon.")
            ui.info("You may need to log out and back in for group changes to take effect.")
            ui.info("Alternatively, run: newgrp docker")
            sys.exit(1)
        else:
            ui.error("Docker daemon is not running")
            ui.info("Try: sudo systemctl start docker")
            if ui.confirm("Attempt to start Docker now?"):
                subprocess.run(
                    "sudo systemctl start docker",
                    shell=True, capture_output=True,
                )
                self.system_status = docker_manager.check_system()
                if self.system_status["docker_running"]:
                    ui.success("Docker daemon started!")
                elif self.system_status.get("docker_state") == "permission_denied":
                    ui.error("Docker started, but you lack permission to access it.")
                    ui.info("You may need to log out and back in, or run: newgrp docker")
                    sys.exit(1)
                else:
                    ui.error("Could not start the Docker daemon.")
                    sys.exit(1)
            else:
                sys.exit(1)

        # Compose available?
        if self.system_status["compose_available"]:
            ui.success(
                f"Docker Compose available ({self.system_status['compose_command']})"
            )
        else:
            ui.warning("Docker Compose not found — some features may not work.")

        print()

    # ── Command loop ───────────────────────────────────────────────────────

    def _command_loop(self):
        while True:
            user_input = ui.prompt()

            if user_input is None:          # Ctrl-C / Ctrl-D
                print()
                ui.info("Goodbye! 👋")
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            parts = user_input.split(None, 1)
            command = parts[0].lower()
            args = parts[1].strip() if len(parts) > 1 else ""

            self._dispatch(command, args)

    # ── Dispatch ───────────────────────────────────────────────────────────

    _COMMANDS = None  # populated lazily

    def _dispatch(self, command, args):
        if self._COMMANDS is None:
            self._COMMANDS = {
                "install":  self._cmd_install,
                "search":   self._cmd_hub,
                "hub":      self._cmd_hub,
                "status":   self._cmd_status,
                "start":    self._cmd_start,
                "stop":     self._cmd_stop,
                "remove":   self._cmd_remove,
                "logs":     self._cmd_logs,
                "update":   self._cmd_update,
                "help":     self._cmd_help,
                "exit":     self._cmd_exit,
                "quit":     self._cmd_exit,
                "q":        self._cmd_exit,
            }

        handler = self._COMMANDS.get(command)
        if handler:
            handler(args)
            return

        ui.error(f"Unknown command: '{command}'")
        ui.info("Type 'help' for available commands.")

    # ── install (catalog + Docker Hub fallback) ────────────────────────────

    def _cmd_install(self, args):
        """Install a container — from catalog first, then Docker Hub."""
        if not args:
            ui.error("Usage: install <container-name> [-v <version>]")
            ui.info("Type 'list' to browse or 'search <term>' to find containers.")
            return

        import shlex
        try:
            args_parts = shlex.split(args)
        except ValueError:
            args_parts = args.split()

        version = None
        for flag in ("-v", "--version"):
            if flag in args_parts:
                idx = args_parts.index(flag)
                if idx + 1 < len(args_parts):
                    version = args_parts[idx + 1]
                    args_parts.pop(idx + 1)
                args_parts.pop(idx)
                break

        if not args_parts:
            ui.error("Usage: install <container-name> [-v <version>]")
            return

        name = args_parts[0].lower()

        # ① If it looks like a full image reference, install directly
        if "/" in name or ":" in name:
            if version and ":" not in name:
                name += f":{version}"
            ui.info(f"Installing Docker image: {ui.c(ui.Colors.BRIGHT_CYAN, name)}")
            self._install_custom_image(name)
            return

        # ② Search Docker Hub to find the real image
        ui.info(f"Searching Docker Hub for '{name}'…")
        print()

        results = dockerhub.search(name)

        if results is None:
            ui.error("Could not reach Docker Hub. Check your internet connection.")
            ui.info("If you know the exact image, try: install user/image:tag")
            return

        if not results:
            ui.info(f"No images found matching '{name}'.")
            return

        # Show results
        ui.header(f"Docker Hub Results — '{name}'")
        display = results[:8]

        for i, r in enumerate(display, 1):
            official_badge = (
                ui.c(ui.Colors.BRIGHT_GREEN, " [official]") if r["official"] else ""
            )
            stars = ui.c(
                ui.Colors.BRIGHT_YELLOW,
                f"★ {dockerhub.format_stars(r['stars'])}",
            )
            print(
                f"  {ui.c(ui.Colors.BOLD, str(i).rjust(2))}. "
                f"{ui.c(ui.Colors.BRIGHT_CYAN, r['name'].ljust(35))} "
                f"{stars}{official_badge}"
            )
            if r["description"]:
                print(f"      {ui.c(ui.Colors.DIM, r['description'])}")

        print()
        choice = ui.ask(
            "Pick a number, or type a full image name (e.g. user/image:tag)",
            default="1",
        )

        if not choice or choice.lower() in ["exit", "quit", "cancel"]:
            return

        # Resolve the selected image
        selected = None
        is_official = False
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(display):
                selected_item = display[idx]
                selected = selected_item["name"]
                is_official = selected_item.get("official", False)
            else:
                ui.error("Invalid selection.")
                return
        except ValueError:
            selected = choice
            is_official = False

        # Ask for a version tag
        if ":" not in selected:
            if version:
                selected += f":{version}"
            else:
                ui.info("Pinning to a specific version (e.g. 1.5.2) is recommended over using 'latest'.")
                tag = ui.ask("Enter a version tag", default="latest")
                selected += f":{tag}"

        # ③ Use deterministic fetcher to find compose file
        web_compose = ai_engine.generate_compose(name, docker_image=selected)
        if web_compose:
            installer.install_raw_compose(name, web_compose, self.install_base)
            return
        else:
            ui.info("Fetch failed. Falling back to manual configuration...")

        # ⑤ Fallback: manual interactive install
        self._install_custom_image(selected, is_official=is_official)

    def _install_custom_image(self, image, is_official=False):
        """Prompt for ports / volumes / env and install an arbitrary image."""
        print()
        ui.header("Container Configuration")
        ui.info(f"Image: {ui.c(ui.Colors.BRIGHT_CYAN, image)}")
        
        # Security Warning
        print()
        if is_official:
            ui.success("This is an Official Docker image.")
        else:
            ui.warning("SECURITY WARNING: You are installing an unverified third-party image.")
            ui.info("Anyone can publish to Docker Hub. Malicious images can compromise your system.")
            if not ui.confirm("Do you trust the publisher of this image and want to continue?", default=False):
                ui.info("Installation cancelled.")
                return
        
        print()
        ui.step(f"Analyzing '{image}' to determine default configuration...")
        metadata = inspector.inspect_image(image)
        if metadata:
            ui.success("Image analyzed successfully.")
            default_ports = ", ".join(metadata["ports"]) if metadata["ports"] else ""
            default_volumes = ", ".join(metadata["volumes"]) if metadata["volumes"] else ""
        else:
            ui.error("Could not analyze image metadata. Proceeding with empty defaults.")
            default_ports = ""
            default_volumes = ""
            metadata = {"env": []}

        # Ports
        ports_input = ui.ask(
            "Ports to expose (e.g. 8080:80, 3000:3000) — comma-separated, or leave empty",
            default=default_ports,
        )
        ports = []
        if ports_input:
            raw_ports = [p.strip() for p in ports_input.split(",") if p.strip()]
            if raw_ports:
                ui.warning("Exposing ports directly (0.0.0.0) makes this service accessible to your entire local network.")
                ui.info("Binding to 127.0.0.1 keeps it secure and accessible only from this machine (ideal if using a reverse proxy).")
                expose_lan = ui.confirm("Expose to the entire local network?", default=False)
                
                for p in raw_ports:
                    if expose_lan:
                        ports.append(p)
                    else:
                        # Prepend 127.0.0.1: if it's not already there and not just a container port
                        if ":" in p and not p.startswith("127.0.0.1:"):
                            ports.append(f"127.0.0.1:{p}")
                        else:
                            ports.append(p)

        # Volumes
        volumes_input = ui.ask(
            "Volumes to mount (e.g. ./data:/data) — comma-separated, or leave empty",
            default=default_volumes,
        )
        volumes = (
            [v.strip() for v in volumes_input.split(",") if v.strip()]
            if volumes_input else None
        )

        # Environment
        env = []
        if metadata.get("env"):
            ui.info("\nThe image has default environment variables.")
            if ui.confirm("Would you like to review and configure them?", default=False):
                for e in metadata["env"]:
                    if "=" in e:
                        k, v = e.split("=", 1)
                        new_val = ui.ask(f"Value for {k}", default=v)
                        if new_val:
                            env.append(f"{k}={new_val}")
        
        env_input = ui.ask(
            "Additional Environment variables (e.g. TZ=UTC) — comma-separated, or leave empty",
            default="",
        )
        if env_input:
            env.extend([e.strip() for e in env_input.split(",") if e.strip()])
            
        if not env:
            env = None

        print()
        installer.install_custom_container(
            image=image,
            ports=ports,
            volumes=volumes,
            env=env,
            install_base=self.install_base,
        )

    # ── search (Docker Hub) ─────────────────────────────────────────────

    def _cmd_search(self, args):
        if not args:
            ui.error("Usage: search <term>")
            return

        ui.info(f"Searching Docker Hub for '{args}'...")
        results = dockerhub.search(args)
        if not results:
            ui.info(f"No Docker Hub images matching '{args}'.")
            return

        ui.header(f"Docker Hub Results — '{args}'")
        for i, match in enumerate(results[:10], 1):
            stars = ui.c(ui.Colors.BRIGHT_YELLOW, f"★ {dockerhub.format_stars(match['stars'])}")
            official = ui.c(ui.Colors.BRIGHT_GREEN, " [official]") if match['official'] else ""
            print(f"  {ui.c(ui.Colors.BOLD, str(i).rjust(2))}. {ui.c(ui.Colors.BRIGHT_CYAN, match['name'].ljust(35))} {stars}{official}")
            if match['description']:
                print(f"      {ui.c(ui.Colors.DIM, match['description'][:80])}")
        print()
        ui.info("Use 'install <name>' to install any of these.")

    # ── hub (Docker Hub search) ────────────────────────────────────────────

    def _cmd_hub(self, args):
        """Search Docker Hub directly."""
        if not args:
            ui.error("Usage: hub <search-term>")
            return

        ui.info(f"Searching Docker Hub for '{args}'…")
        print()

        results = dockerhub.search(args)

        if results is None:
            ui.error("Could not reach Docker Hub. Check your internet connection.")
            return

        if not results:
            ui.info(f"No images found on Docker Hub matching '{args}'.")
            return

        ui.header(f"Docker Hub — '{args}'")

        for i, r in enumerate(results[:10], 1):
            official_badge = (
                ui.c(ui.Colors.BRIGHT_GREEN, " [official]") if r["official"] else ""
            )
            stars = ui.c(
                ui.Colors.BRIGHT_YELLOW,
                f"★ {dockerhub.format_stars(r['stars'])}",
            )
            print(
                f"  {ui.c(ui.Colors.BOLD, str(i).rjust(2))}. "
                f"{ui.c(ui.Colors.BRIGHT_CYAN, r['name'].ljust(35))} "
                f"{stars}{official_badge}"
            )
            if r["description"]:
                print(f"      {ui.c(ui.Colors.DIM, r['description'])}")

        print()
        ui.info("To install any of these: install <image-name>")

    # ── status ─────────────────────────────────────────────────────────────

    def _cmd_status(self, _args):
        ui.header("Running Containers")

        containers = installer.list_running()
        if not containers:
            ui.info("No DockMate containers are currently running.")
            return

        rows = [
            [c["name"], c["status"], (c["ports"] or "-")[:45]]
            for c in containers
        ]
        ui.show_table(["Container", "Status", "Ports"], rows)

    # ── start / stop / remove ──────────────────────────────────────────────

    def _cmd_start(self, args):
        if not args:
            ui.error("Usage: start <container-name>")
            return
        installer.start_container(args.split()[0], self.install_base)

    def _cmd_stop(self, args):
        if not args:
            ui.error("Usage: stop <container-name>")
            return
        installer.stop_container(args.split()[0], self.install_base)

    def _cmd_remove(self, args):
        if not args:
            ui.error("Usage: remove <container-name>")
            return
        installer.remove_container(args.split()[0], self.install_base)

    # ── logs ───────────────────────────────────────────────────────────────

    def _cmd_logs(self, args):
        if not args:
            ui.error("Usage: logs <container-name> [lines]")
            return

        parts = args.split()
        name = parts[0]
        lines = 50
        if len(parts) > 1:
            try:
                lines = int(parts[1])
            except ValueError:
                pass

        output = installer.get_logs(name, lines)
        if output:
            ui.header(f"Logs — {name}")
            print(output)
        else:
            ui.error(f"Could not retrieve logs for '{name}'.")

    # ── update ─────────────────────────────────────────────────────────────

    def _cmd_update(self, args):
        """Pull the latest image and recreate the container."""
        if not args:
            ui.error("Usage: update <container-name> [-v <version>]")
            return

        import shlex
        try:
            args_parts = shlex.split(args)
        except ValueError:
            args_parts = args.split()

        version = None
        for flag in ("-v", "--version"):
            if flag in args_parts:
                idx = args_parts.index(flag)
                if idx + 1 < len(args_parts):
                    version = args_parts[idx + 1]
                    args_parts.pop(idx + 1)
                args_parts.pop(idx)
                break

        if not args_parts:
            ui.error("Usage: update <container-name> [-v <version>]")
            return

        name = args_parts[0].lower()
        canonical_key = installer._resolve_key(name, self.install_base)
        if not canonical_key:
            ui.error(f"No installed container matching '{name}'.")
            return

        compose_cmd = docker_manager.get_compose_command()
        if not compose_cmd:
            ui.error("Docker Compose is not available.")
            return

        install_dir = installer.get_install_dir(canonical_key, self.install_base)
        compose_file = os.path.join(install_dir, "docker-compose.yml")

        if not os.path.exists(compose_file):
            ui.error(f"No installation found for '{name}'.")
            return

        if version:
            ui.step(f"Updating image version to '{version}'…")
            import re
            with open(compose_file, "r") as f:
                compose_content = f.read()
            
            def replacer(match):
                base = match.group(1).split(':')[0]
                return f"image: {base}:{version}"
            
            new_content = re.sub(r'image:\s+([^\s]+)', replacer, compose_content)
            with open(compose_file, "w") as f:
                f.write(new_content)

        display = name

        ui.header(f"Updating {display}")
        ui.step("Pulling latest image…")
        print()
        subprocess.run(f"{compose_cmd} pull", shell=True, cwd=install_dir)

        print()
        ui.step("Recreating container with new image…")
        print()
        subprocess.run(f"{compose_cmd} up -d", shell=True, cwd=install_dir)

        print()
        ui.success(f"{display} has been updated!")

    def _cmd_help(self, _args):
        ui.header("DockMate Commands")

        cmds = [
            ("install <name> [-v <ver>]", "Install any container autonomously"),
            ("search <term>",     "Search Docker Hub"),
            ("status",            "List running DockMate containers"),
            ("start <name>",      "Start a previously installed container"),
            ("stop <name>",       "Stop a running container"),
            ("remove <name>",     "Remove a container (data is kept)"),
            ("update <name> [-v <ver>]",  "Pull latest image and recreate, optionally set version"),
            ("logs <name> [n]",   "Show last n log lines (default 50)"),
            ("help",              "Show this help message"),
            ("exit / quit",       "Exit DockMate"),
        ]

        for cmd, desc in cmds:
            print(
                f"  {ui.c(ui.Colors.BRIGHT_CYAN, cmd.ljust(26))} {desc}"
            )

        print()
        ui.info("Install anything! DockMate uses a deterministic GitHub pipeline")
        ui.info("to intelligently find docker-compose files on the fly.")

    @staticmethod
    def _cmd_exit(_args):
        ui.info("Goodbye! 👋")
        sys.exit(0)


# ─── Entry point ───────────────────────────────────────────────────────────────

def main():
    try:
        DockMate().run()
    except KeyboardInterrupt:
        print()
        ui.info("Goodbye! 👋")
        sys.exit(0)
