"""Consistent command formatting for the workflow's platform shell.

These helpers quote argument lists only. Callers assemble operators such as
pipes and redirection separately so they remain shell syntax.
"""
import os
import shlex
import subprocess
from typing import Iterable


def format_command(arguments: Iterable[object]) -> str:
    """Return a shell command from arguments, converting paths/numbers to text."""
    text_arguments = [str(argument) for argument in arguments]
    if os.name == 'nt':
        return subprocess.list2cmdline(text_arguments)
    return shlex.join(text_arguments)


def quote_path(path: object) -> str:
    """Quote a single path for use beside shell pipes or redirection."""
    return format_command([path])
