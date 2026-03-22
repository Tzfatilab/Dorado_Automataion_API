"""
Command Executor Module
======================

Handles execution of shell commands with logging and error handling.
Integrates with WorkflowLogger for command tracking.
"""

import subprocess
from typing import Optional, List
from pathlib import Path


class CommandExecutor:
    """
    Executes shell commands with integrated logging and error handling.

    Features:
    - Execute commands with automatic logging
    - Track command success/failure
    - Capture output when needed
    - Thread-safe execution with logger integration
    """

    def __init__(self, logger):
        """
        Initialize the command executor.

        Args:
            logger: WorkflowLogger instance for logging commands
        """
        self.logger = logger

    def execute(self, command: str, capture_output: bool = False,
                check: bool = True, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        """
        Execute a shell command with logging.

        Args:
            command: Shell command to execute
            capture_output: If True, capture stdout/stderr
            check: If True, raise exception on non-zero exit code
            cwd: Working directory for command execution

        Returns:
            subprocess.CompletedProcess object

        Raises:
            subprocess.CalledProcessError: If command fails and check=True
        """
        # Register command with logger
        cmd_index = self.logger.register_command(command)

        try:
            # Execute command
            if capture_output:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    check=check,
                    cwd=cwd
                )
            else:
                result = subprocess.run(
                    command,
                    shell=True,
                    check=check,
                    cwd=cwd
                )

            # Mark as successful
            self.logger.mark_command_success(cmd_index)
            return result

        except subprocess.CalledProcessError as e:
            # Mark as failed
            error_msg = str(e)
            if capture_output and e.stderr:
                error_msg += f"\nstderr: {e.stderr}"

            self.logger.mark_command_failed(cmd_index, error_msg)
            raise

    def execute_safe(self, command: str, capture_output: bool = False,
                     cwd: Optional[Path] = None) -> tuple[bool, Optional[subprocess.CompletedProcess]]:
        """
        Execute a command without raising exceptions on failure.
        Useful for optional or non-critical commands.

        Args:
            command: Shell command to execute
            capture_output: If True, capture stdout/stderr
            cwd: Working directory for command execution

        Returns:
            Tuple of (success: bool, result: CompletedProcess or None)
        """
        try:
            result = self.execute(command, capture_output=capture_output,
                                  check=True, cwd=cwd)
            return (True, result)
        except subprocess.CalledProcessError:
            return (False, None)

    def execute_with_retry(self, command: str, max_retries: int = 3,
                           capture_output: bool = False,
                           cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        """
        Execute a command with retry logic.

        Args:
            command: Shell command to execute
            max_retries: Maximum number of retry attempts
            capture_output: If True, capture stdout/stderr
            cwd: Working directory for command execution

        Returns:
            subprocess.CompletedProcess object

        Raises:
            subprocess.CalledProcessError: If all retries fail
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self.logger.warning(f"Retry attempt {attempt + 1}/{max_retries}")

                return self.execute(command, capture_output=capture_output,
                                    check=True, cwd=cwd)
            except subprocess.CalledProcessError as e:
                last_exception = e
                if attempt < max_retries - 1:
                    continue

        # All retries failed
        raise last_exception

    def check_tool_available(self, tool_name: str) -> bool:
        """
        Check if a command-line tool is available in PATH.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if tool is available, False otherwise
        """
        try:
            result = subprocess.run(
                f"which {tool_name}",
                shell=True,
                capture_output=True,
                check=False
            )
            return result.returncode == 0
        except Exception:
            return False

    def validate_tools(self, required_tools: List[str]) -> tuple[bool, List[str]]:
        """
        Validate that all required tools are available.

        Args:
            required_tools: List of required tool names

        Returns:
            Tuple of (all_available: bool, missing_tools: List[str])
        """
        missing_tools = []

        for tool in required_tools:
            if not self.check_tool_available(tool):
                missing_tools.append(tool)
                self.logger.error(f"Required tool not found: {tool}")

        if missing_tools:
            self.logger.error(f"Missing tools: {', '.join(missing_tools)}")
            return (False, missing_tools)

        self.logger.info(f"All required tools available: {', '.join(required_tools)}")
        return (True, [])

    def __repr__(self) -> str:
        """String representation of CommandExecutor."""
        return f"CommandExecutor(logger={self.logger})"