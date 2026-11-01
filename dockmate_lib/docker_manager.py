#!/usr/bin/env python3
"""Docker detection, health checks, and distro-aware installation for DockMate."""

import subprocess
import os

from . import ui


# ─── Shell helpers ─────────────────────────────────────────────────────────────

def _run(cmd, capture=True, timeout=60):
    """Run a shell command and return the CompletedProcess, or None on failure."""
    try:
        return subprocess.run(
            cmd, shell=True, capture_output=capture,
            text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


# ─── Detection ─────────────────────────────────────────────────────────────────

def is_docker_installed():
    """Return True if the ``docker`` CLI is on PATH."""
    result = _run("docker --version")
    return result is not None and result.returncode == 0


def check_docker_state():
    """Return 'running', 'stopped', or 'permission_denied'."""
    result = _run("docker info")
    if result is None:
        return "stopped"
    if result.returncode == 0:
        return "running"
    output = (result.stdout + result.stderr).lower()
    if "permission denied" in output:
        return "permission_denied"
    return "stopped"


def get_docker_version():
    """Return the human-readable Docker version string, or None."""
    result = _run("docker --version")
    if result and result.returncode == 0:
        return result.stdout.strip()
    return None


def has_docker_compose():
    """
    Check for Docker Compose availability.

    Returns ``"plugin"`` | ``"standalone"`` | ``None``.
    """
    result = _run("docker compose version 2>/dev/null")
    if result and result.returncode == 0:
        return "plugin"
    result = _run("docker-compose --version 2>/dev/null")
    if result and result.returncode == 0:
        return "standalone"
    return None


def get_compose_command():
    """Return the compose invocation string."""
    kind = has_docker_compose()
    if kind == "plugin":
        return "docker compose"
    if kind == "standalone":
        return "docker-compose"
    return None


# ─── Distro detection ─────────────────────────────────────────────────────────
#
# Instead of only matching the distro ID, we read ID_LIKE from
# /etc/os-release to detect the *base* distribution.
# CachyOS → ID_LIKE="arch", Linux Mint → ID_LIKE="ubuntu debian", etc.

def _detect_distro():
    """
    Parse ``/etc/os-release`` and determine the package-management base.

    Returns a dict with keys:
        id, id_like, name, base, pkg_manager
    """
    info = {
        "id": "", "id_like": "", "name": "",
        "base": "unknown", "pkg_manager": "unknown",
    }

    try:
        with open("/etc/os-release") as f:
            for line in f:
                line = line.strip()
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                value = value.strip('"').strip("'")
                if key == "ID":
                    info["id"] = value.lower()
                elif key == "ID_LIKE":
                    info["id_like"] = value.lower()
                elif key == "NAME":
                    info["name"] = value
    except FileNotFoundError:
        return info

    distro_id = info["id"]
    id_like = info["id_like"]

    # ── Arch-based (CachyOS, Manjaro, EndeavourOS, Garuda, …) ──
    arch_ids = {
        "arch", "manjaro", "endeavouros", "cachyos", "garuda", "artix",
        "arcolinux", "archcraft", "blackarch", "archbang", "parabola",
        "hyperbola", "crystal", "bluestar", "archman",
    }
    if distro_id in arch_ids or "arch" in id_like:
        info["base"] = "arch"
        info["pkg_manager"] = "pacman"
        return info

    # ── Debian / Ubuntu-based (Mint, Pop!_OS, Zorin, …) ──
    debian_ids = {
        "debian", "ubuntu", "linuxmint", "pop", "elementary", "zorin",
        "kali", "raspbian", "mx", "deepin", "parrot", "pureos", "devuan",
        "neon", "lmde", "trisquel", "antix", "sparky", "bunsenlabs",
    }
    if distro_id in debian_ids or "debian" in id_like or "ubuntu" in id_like:
        info["base"] = "debian"
        info["pkg_manager"] = "apt"
        return info

    # ── Fedora / RHEL-based (CentOS, Rocky, Alma, Nobara, …) ──
    fedora_ids = {
        "fedora", "rhel", "centos", "rocky", "alma", "oracle",
        "amzn", "scientific", "nobara", "ultramarine",
    }
    if distro_id in fedora_ids or "fedora" in id_like or "rhel" in id_like:
        info["base"] = "fedora"
        info["pkg_manager"] = "dnf"
        return info

    # ── SUSE-based ──
    if distro_id in {"opensuse-leap", "opensuse-tumbleweed", "sles"} \
       or "suse" in id_like:
        info["base"] = "suse"
        info["pkg_manager"] = "zypper"
        return info

    # ── Alpine ──
    if distro_id == "alpine":
        info["base"] = "alpine"
        info["pkg_manager"] = "apk"
        return info

    # ── Void ──
    if distro_id == "void":
        info["base"] = "void"
        info["pkg_manager"] = "xbps"
        return info

    return info


# ─── Distro-specific install helpers ──────────────────────────────────────────

def _install_arch():
    """Install Docker on Arch-based systems via pacman."""
    ui.step("Installing docker and docker-compose via pacman…")
    print()
    result = subprocess.run(
        "sudo pacman -Sy --noconfirm docker docker-compose",
        shell=True,
    )
    return result.returncode == 0


def _install_alpine():
    """Install Docker on Alpine via apk."""
    ui.step("Installing docker via apk…")
    print()
    for cmd in ("sudo apk update", "sudo apk add docker docker-compose"):
        if subprocess.run(cmd, shell=True).returncode != 0:
            return False
    return True


def _install_void():
    """Install Docker on Void via xbps."""
    ui.step("Installing docker via xbps-install…")
    print()
    result = subprocess.run(
        "sudo xbps-install -Sy docker docker-compose",
        shell=True,
    )
    return result.returncode == 0


def _install_convenience_script():
    """Fall back to the official get.docker.com convenience script."""
    ui.step("Downloading Docker installation script from get.docker.com…")

    dl = subprocess.run(
        "curl -fsSL https://get.docker.com -o /tmp/get-docker.sh",
        shell=True, capture_output=True, text=True,
    )
    if dl.returncode != 0:
        ui.error("Failed to download the Docker installation script.")
        return False

    ui.step("Running installation script (this may take a few minutes)…")
    print()

    install_result = subprocess.run("sudo sh /tmp/get-docker.sh", shell=True)

    try:
        os.remove("/tmp/get-docker.sh")
    except OSError:
        pass

    return install_result.returncode == 0


# ─── Main install orchestrator ─────────────────────────────────────────────────

def install_docker():
    """
    Install Docker Engine with distro-aware package manager detection.

    Flow:
        1. Read /etc/os-release and resolve the base distribution
        2. Route to the native package manager (pacman, apk, xbps …)
        3. For Debian / Fedora / SUSE / unknown → fall back to get.docker.com
        4. Post-install: add user to docker group, enable & start the service
    """
    ui.header("Docker Installation")

    distro = _detect_distro()
    distro_display = distro["name"] or distro["id"] or "Unknown"

    ui.info(
        f"Detected distribution: "
        f"{ui.c(ui.Colors.BRIGHT_WHITE, distro_display)}"
    )
    ui.info(
        f"Base: {ui.c(ui.Colors.BRIGHT_WHITE, distro['base'])} "
        f"(package manager: {distro['pkg_manager']})"
    )
    print()
    ui.info("This requires sudo privileges.")
    print()

    if not ui.confirm("Proceed with Docker installation?"):
        return False

    print()

    # Pick the right installer
    native_methods = {
        "arch":   _install_arch,
        "alpine": _install_alpine,
        "void":   _install_void,
    }

    method = native_methods.get(distro["base"])

    if method:
        ok = method()
    else:
        # Debian, Fedora, SUSE, unknown → try the convenience script
        ui.info(
            f"Using the official Docker installation script for "
            f"{distro_display}…"
        )
        print()
        ok = _install_convenience_script()

    if not ok:
        ui.error("Docker installation failed.")
        ui.info("You can install Docker manually:")
        ui.info("  https://docs.docker.com/engine/install/")
        if distro["base"] == "arch":
            ui.info("  Or try: sudo pacman -S docker docker-compose")
        return False

    # ── Post-install ───────────────────────────────────────────────────────
    username = os.environ.get("USER") or os.environ.get("LOGNAME", "")
    if username:
        ui.step(f"Adding user '{username}' to the docker group…")
        ui.warning("Security Note: Members of the 'docker' group have root-equivalent access to the host.")
        subprocess.run(
            f"sudo usermod -aG docker {username}",
            shell=True, capture_output=True,
        )

    ui.step("Enabling and starting the Docker service…")
    subprocess.run("sudo systemctl enable docker", shell=True, capture_output=True)
    subprocess.run("sudo systemctl start docker", shell=True, capture_output=True)

    print()
    ui.success("Docker has been installed successfully!")

    if username:
        ui.warning(
            "You may need to log out and back in for docker group changes "
            "to take effect."
        )
        ui.info("Alternatively, run: newgrp docker")

    return True


# ─── Aggregate check ──────────────────────────────────────────────────────────

def check_system():
    """Run all system checks and return a status dict."""
    status = {
        "docker_installed": False,
        "docker_running": False,
        "docker_state": "stopped",
        "docker_version": None,
        "compose_available": False,
        "compose_command": None,
    }

    status["docker_installed"] = is_docker_installed()

    if status["docker_installed"]:
        status["docker_version"] = get_docker_version()
        status["docker_state"] = check_docker_state()
        status["docker_running"] = status["docker_state"] == "running"
        compose_cmd = get_compose_command()
        status["compose_available"] = compose_cmd is not None
        status["compose_command"] = compose_cmd

    return status
