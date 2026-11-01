#!/usr/bin/env python3
"""Terminal UI utilities for DockMate — colors, formatting, prompts."""

import sys
import os
import time
import threading


# ─── ANSI Color Codes ──────────────────────────────────────────────────────────

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Regular
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


# ─── Color helpers ─────────────────────────────────────────────────────────────

def _supports_color():
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


USE_COLOR = _supports_color()


def c(color_code, text):
    """Apply ANSI color to text if the terminal supports it."""
    if USE_COLOR:
        return f"{color_code}{text}{Colors.RESET}"
    return str(text)


def bold(text):
    return c(Colors.BOLD, text)


def dim(text):
    return c(Colors.DIM, text)


# ─── Status messages ───────────────────────────────────────────────────────────

def success(msg):
    print(f"  {c(Colors.BRIGHT_GREEN, '✔')} {msg}")


def error(msg):
    print(f"  {c(Colors.BRIGHT_RED, '✘')} {msg}")


def warning(msg):
    print(f"  {c(Colors.BRIGHT_YELLOW, '⚠')} {msg}")


def info(msg):
    print(f"  {c(Colors.BRIGHT_CYAN, 'ℹ')} {msg}")


def step(msg):
    print(f"  {c(Colors.BRIGHT_MAGENTA, '▸')} {msg}")


# ─── Headings ──────────────────────────────────────────────────────────────────

def header(msg):
    print(f"\n  {c(Colors.BOLD + Colors.BRIGHT_CYAN, msg)}")
    print(f"  {c(Colors.DIM, '─' * len(msg))}")


# ─── User input ───────────────────────────────────────────────────────────────

def prompt(text=""):
    """Show the interactive prompt and read user input."""
    try:
        return input(
            f"\n  {c(Colors.BRIGHT_CYAN, 'dockmate')} "
            f"{c(Colors.DIM, '›')} {text}"
        )
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def confirm(msg, default=True):
    """Ask a yes/no question and return the boolean result."""
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        answer = input(
            f"  {c(Colors.BRIGHT_YELLOW, '?')} {msg} "
            f"{c(Colors.DIM, suffix)} "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def ask(msg, default=""):
    """Prompt the user for a string value with an optional default."""
    suffix = f" {c(Colors.DIM, f'({default})')}" if default else ""
    try:
        answer = input(
            f"  {c(Colors.BRIGHT_YELLOW, '?')} {msg}{suffix}: "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return answer if answer else default


# ─── Banner ────────────────────────────────────────────────────────────────────

BANNER = r"""
    ____             __   __  ___      __
   / __ \____  _____/ /__/  |/  /___ _/ /____
  / / / / __ \/ ___/ //_/ /|_/ / __ `/ __/ _ \
 / /_/ / /_/ / /__/ ,< / /  / / /_/ / /_/  __/
/_____/\____/\___/_/|_/_/  /_/\__,_/\__/\___/
"""


def show_banner():
    print(c(Colors.BRIGHT_CYAN, BANNER))
    print(c(Colors.DIM, "  Your Docker container assistant  │  Type 'help' for commands"))
    print(c(Colors.DIM, "  ─────────────────────────────────┘"))
    print()


# ─── Tables ────────────────────────────────────────────────────────────────────

def show_table(headers, rows, col_widths=None):
    """Display a formatted table with header, separator, and rows."""
    if not col_widths:
        col_widths = []
        for i, h in enumerate(headers):
            max_w = len(h)
            for row in rows:
                if i < len(row):
                    max_w = max(max_w, len(str(row[i])))
            col_widths.append(min(max_w + 2, 50))

    # Header
    header_str = "  "
    for i, h in enumerate(headers):
        header_str += c(Colors.BOLD + Colors.BRIGHT_WHITE, h.ljust(col_widths[i]))
    print(header_str)

    # Separator
    sep = "  "
    for w in col_widths:
        sep += c(Colors.DIM, "─" * w)
    print(sep)

    # Rows
    for row in rows:
        row_str = "  "
        for i, cell in enumerate(row):
            if i < len(col_widths):
                text = str(cell).ljust(col_widths[i])
                if i == 0:
                    text = c(Colors.BRIGHT_CYAN, text)
                else:
                    text = c(Colors.WHITE, text)
                row_str += text
        print(row_str)


# ─── Spinner ───────────────────────────────────────────────────────────────────

class Spinner:
    """Animated braille spinner for long-running operations."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message=""):
        self.message = message
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def _spin(self):
        i = 0
        while self._running:
            frame = self.FRAMES[i % len(self.FRAMES)]
            sys.stdout.write(f"\r  {c(Colors.BRIGHT_CYAN, frame)} {self.message}")
            sys.stdout.flush()
            time.sleep(0.08)
            i += 1

    def stop(self, final_message=None):
        self._running = False
        if self._thread:
            self._thread.join()
        sys.stdout.write("\r" + " " * 80 + "\r")
        if final_message:
            print(f"  {final_message}")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
