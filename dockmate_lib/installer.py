#!/usr/bin/env python3
"""Container installation, lifecycle, and compose generation for DockMate."""

import os
import subprocess

from . import ui
from . import docker_manager


DEFAULT_INSTALL_BASE = os.path.expanduser("~/dockmate-containers")


# ─── Path helpers ──────────────────────────────────────────────────────────────

def get_install_dir(container_key, base_dir=None):
    """Return the directory where a container's compose file lives."""
    if base_dir is None:
        base_dir = DEFAULT_INSTALL_BASE
    return os.path.join(base_dir, container_key)


# ─── Key resolution (catalog + custom) ────────────────────────────────────────

def _resolve_key(container_name, install_base=None):
    """
    Resolve a user-provided name to a directory key.
    """
    sanitised = container_name.lower().strip().replace("/", "-").replace(":", "-")
    install_dir = get_install_dir(sanitised, install_base)
    if os.path.exists(os.path.join(install_dir, "docker-compose.yml")):
        return sanitised

    return None





# ─── Compose generation — arbitrary images ─────────────────────────────────────

def generate_custom_compose(container_name, image, ports=None, volumes=None, env=None):
    """Generate a ``docker-compose.yml`` for any Docker image."""
    lines = [
        "services:",
        f"  {container_name}:",
        f"    image: {image}",
        f"    container_name: dockmate-{container_name}",
        "    restart: unless-stopped",
    ]

    if ports:
        lines.append("    ports:")
        for port in ports:
            lines.append(f'      - "{port}"')

    if env:
        lines.append("    environment:")
        for pair in env:
            lines.append(f"      - {pair}")

    if volumes:
        lines.append("    volumes:")
        for vol in volumes:
            lines.append(f"      - {vol}")

    return "\n".join(lines) + "\n"


# ─── Helpers shared by both install paths ──────────────────────────────────────

def _create_volume_dirs(install_dir, host_paths):
    """Create local directories for volume mounts that start with ``./``."""
    for host_path in host_paths:
        if host_path.startswith("./"):
            dir_path = os.path.join(install_dir, host_path[2:])
            if "." not in os.path.basename(dir_path):
                os.makedirs(dir_path, exist_ok=True)


def _pull_and_start(compose_cmd, install_dir):
    """Pull images and bring the stack up. Returns True on success."""
    print()
    ui.step("Pulling container image (this may take a moment)…")
    print()
    if subprocess.run(f"{compose_cmd} pull", shell=True, cwd=install_dir).returncode != 0:
        ui.error("Failed to pull container image.")
        return False

    print()
    ui.step("Starting container…")
    print()
    if subprocess.run(f"{compose_cmd} up -d", shell=True, cwd=install_dir).returncode != 0:
        ui.error("Failed to start container.")
        return False

    return True



# ─── Install — arbitrary Docker image ──────────────────────────────────────────

def install_custom_container(image, container_name=None, ports=None,
                             volumes=None, env=None, install_base=None):
    """
    Install *any* Docker image with user-provided configuration.

    Used for Docker Hub results and direct ``user/image:tag`` installs.
    """
    compose_cmd = docker_manager.get_compose_command()
    if not compose_cmd:
        ui.error("Docker Compose is not available.")
        return False

    # Derive a safe container name from the image if not provided
    if not container_name:
        container_name = image.split("/")[-1].split(":")[0]
        container_name = (
            container_name
            .replace(".", "-")
            .replace("_", "-")
            .lower()
        )

    install_dir = get_install_dir(container_name, install_base)

    ui.header(f"Installing {image}")
    ui.info(f"Container name: dockmate-{container_name}")
    ui.info(f"Install directory: {ui.c(ui.Colors.BRIGHT_WHITE, install_dir)}")

    if ports:
        host_port = ports[0].split(":")[0]
        ui.info(f"Web access: http://localhost:{host_port}")
        
    has_socket = volumes and any("/var/run/docker.sock" in v for v in volumes)
    if has_socket:
        print()
        ui.warning("SECURITY WARNING: This container mounts the Docker socket (/var/run/docker.sock).")
        ui.info("This gives the container full root-equivalent control over your host machine.")

    print()
    if not ui.confirm("Proceed?"):
        ui.info("Installation cancelled.")
        return False

    # Directories
    os.makedirs(install_dir, exist_ok=True)
    if volumes:
        vol_hosts = [v.split(":")[0] for v in volumes]
        _create_volume_dirs(install_dir, vol_hosts)

    # Compose
    compose_content = generate_custom_compose(
        container_name, image, ports, volumes, env,
    )
    compose_file = os.path.join(install_dir, "docker-compose.yml")
    with open(compose_file, "w") as fh:
        fh.write(compose_content)
    ui.success(f"Created {ui.c(ui.Colors.DIM, compose_file)}")

    # Pull & start
    if not _pull_and_start(compose_cmd, install_dir):
        return False

    print()
    ui.success("Container is now running! 🚀")
    if ports:
        host_port = ports[0].split(":")[0]
        ui.info(
            f"Access it at: "
            f"{ui.c(ui.Colors.BOLD + ui.Colors.BRIGHT_CYAN, 'http://localhost:' + host_port)}"
        )
    ui.info(f"Data stored in: {ui.c(ui.Colors.DIM, install_dir)}")
    return True

    return True


# ─── Install — raw compose ─────────────────────────────────────────────

def install_raw_compose(app_name, compose_content, install_base=None):
    """Install a container using a pre-defined docker-compose string."""
    compose_cmd = docker_manager.get_compose_command()
    if not compose_cmd:
        ui.error("Docker Compose is not available.")
        return False

    container_name = app_name.lower()
    install_dir = get_install_dir(container_name, install_base)

    print("\n--- Configuration Summary ---")
    lines = compose_content.strip().split('\n')
    # Print the first few lines as a summary
    for line in lines[:10]:
        print(line)
    if len(lines) > 10:
        print(f"... ({len(lines)-10} more lines)")
    print("-----------------------------\n")

    choice = ui.ask("Press [ENTER] to use the default settings, or type 'custom' to edit the YAML manually", default="")
    
    os.makedirs(install_dir, exist_ok=True)
    compose_file = os.path.join(install_dir, "docker-compose.yml")
    with open(compose_file, "w") as fh:
        fh.write(compose_content)
        
    if choice.lower() == "custom":
        ui.info(f"Opening {compose_file} in nano...")
        import subprocess
        subprocess.run(["nano", compose_file])
        ui.success("Configuration updated.")
    else:
        ui.success(f"Created {ui.c(ui.Colors.DIM, compose_file)}")

    # Re-read compose_content in case it was modified by nano
    with open(compose_file, "r") as fh:
        updated_compose_content = fh.read()

    # Try to ensure any mapped local directories exist
    # A bit basic, but scans for ./ paths in the file
    dirs_to_create = []
    for line in updated_compose_content.split("\n"):
        if "- ./" in line or "- \"./" in line or "- './" in line:
            parts = line.split(":")
            if len(parts) >= 2:
                src = parts[0].strip().lstrip("- ").strip("'\"")
                if src.startswith("./"):
                    dirs_to_create.append(src)
    if dirs_to_create:
        _create_volume_dirs(install_dir, dirs_to_create)

    # Pull & start
    if not _pull_and_start(compose_cmd, install_dir):
        return False

    print()
    ui.success(f"{app_name} is now running! 🚀")
    ui.info(f"Data stored in: {ui.c(ui.Colors.DIM, install_dir)}")
    return True



# ─── Stop / Start / Remove ────────────────────────────────────────────────────
# These all use _resolve_key() so they work for both catalog AND custom
# containers.

def stop_container(container_name, install_base=None):
    """Stop a running DockMate container."""
    canonical_key = _resolve_key(container_name, install_base)
    if not canonical_key:
        ui.error(f"No installed container matching '{container_name}'.")
        return False

    compose_cmd = docker_manager.get_compose_command()
    if not compose_cmd:
        ui.error("Docker Compose is not available.")
        return False

    install_dir = get_install_dir(canonical_key, install_base)
    if not os.path.exists(os.path.join(install_dir, "docker-compose.yml")):
        ui.error(f"No installation found at {install_dir}")
        return False

    ui.step(f"Stopping {container_name}…")
    result = subprocess.run(
        f"{compose_cmd} down", shell=True, cwd=install_dir,
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        ui.success(f"{container_name} has been stopped.")
        return True

    ui.error(f"Failed to stop {container_name}.")
    if result.stderr:
        print(f"  {ui.c(ui.Colors.DIM, result.stderr.strip())}")
    return False


def start_container(container_name, install_base=None):
    """Start a previously-installed container."""
    canonical_key = _resolve_key(container_name, install_base)
    if not canonical_key:
        ui.error(f"No installed container matching '{container_name}'.")
        ui.info(f"Use 'install {container_name}' to install it first.")
        return False

    compose_cmd = docker_manager.get_compose_command()
    if not compose_cmd:
        ui.error("Docker Compose is not available.")
        return False

    install_dir = get_install_dir(canonical_key, install_base)
    if not os.path.exists(os.path.join(install_dir, "docker-compose.yml")):
        ui.error(f"No installation found for '{container_name}'.")
        ui.info(f"Use 'install {container_name}' to install it first.")
        return False

    ui.step(f"Starting {container_name}…")
    result = subprocess.run(
        f"{compose_cmd} up -d", shell=True, cwd=install_dir,
    )
    if result.returncode == 0:
        ui.success(f"{container_name} started!")
        return True

    ui.error(f"Failed to start {container_name}.")
    return False


def remove_container(container_name, install_base=None):
    """Stop a container, remove its images, but keep persistent data."""
    canonical_key = _resolve_key(container_name, install_base)
    if not canonical_key:
        ui.error(f"No installed container matching '{container_name}'.")
        return False

    compose_cmd = docker_manager.get_compose_command()
    if not compose_cmd:
        ui.error("Docker Compose is not available.")
        return False

    install_dir = get_install_dir(canonical_key, install_base)
    if not os.path.exists(os.path.join(install_dir, "docker-compose.yml")):
        ui.error(f"No installation found at {install_dir}")
        return False

    display_name = container_name

    ui.warning(f"This will stop and remove the {display_name} container and its images.")

    if not ui.confirm("Continue?", default=False):
        return False

    ui.step(f"Removing {display_name}…")
    result = subprocess.run(
        f"{compose_cmd} down --rmi all", shell=True, cwd=install_dir,
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        ui.success(f"{display_name} has been removed.")
        
        # Ask to delete persistent data
        print()
        ui.warning(f"Persistent data is currently stored at: {install_dir}")
        ui.info("If you plan to reinstall this app later, you should keep this data.")
        if ui.confirm("Would you like to PERMANENTLY DELETE all persistent data for this container?", default=False):
            ui.step("Deleting persistent data...")
            import shutil
            try:
                # We need sudo if files were written as root by the container
                subprocess.run(["sudo", "rm", "-rf", install_dir], check=True)
                ui.success("Persistent data deleted.")
            except Exception as e:
                ui.error(f"Failed to delete persistent data: {e}")
                ui.info(f"You may need to manually run: sudo rm -rf {install_dir}")
        else:
            ui.info(f"Data was kept at: {install_dir}")
            
        return True

    ui.error(f"Failed to remove {display_name}.")
    return False


# ─── Status / Logs ─────────────────────────────────────────────────────────────

def list_running():
    """Return a list of dicts for running dockmate containers by checking their docker-compose labels."""
    # We find containers whose compose working directory matches our dockmate install base.
    install_base = os.path.expanduser("~/dockmate-containers")
    
    result = subprocess.run(
        'docker ps --format "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t{{.Label \\"com.docker.compose.project.working_dir\\"}}"',
        shell=True, capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []

    containers = []
    for line in result.stdout.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) >= 5:
            working_dir = parts[4]
            if working_dir.startswith(install_base):
                containers.append({
                    "name": parts[0],
                    "image": parts[1],
                    "status": parts[2],
                    "ports": parts[3],
                })
    return containers


def get_logs(container_name, lines=50):
    """Return recent log output for a container, or None on failure."""
    canonical_key = _resolve_key(container_name)
    if not canonical_key:
        # Last-ditch: try the raw name
        canonical_key = container_name.lower().strip()

    # Find the actual container name running for this app
    install_base = os.path.expanduser("~/dockmate-containers")
    app_dir = os.path.join(install_base, canonical_key)
    
    result = subprocess.run(
        f'docker ps --format "{{{{.Names}}}}" --filter "label=com.docker.compose.project.working_dir={app_dir}"',
        shell=True, capture_output=True, text=True,
    )
    
    actual_name = result.stdout.strip().split('\n')[0]
    if not actual_name:
        actual_name = canonical_key # Fallback

    result = subprocess.run(
        ["docker", "logs", actual_name, "--tail", str(lines)],
        shell=False, capture_output=True, text=True,
    )
    if result.returncode == 0:
        return (result.stdout + result.stderr).strip()
    return None
