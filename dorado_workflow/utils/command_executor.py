"""
Command Executor Module
======================

Handles execution of shell commands with logging and error handling.
Integrates with WorkflowLogger for command tracking.
"""

import shutil
import subprocess
import os
import signal
import threading
from typing import Optional, List, Callable
from pathlib import Path
from .cancellation import WorkflowCancelled
from .shell_commands import format_command
from .analysis_constants import PROCESS_POLL_INTERVAL_SECONDS


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
        self.stop_callback = None

    def check_cancelled(self):
        if self.stop_callback and self.stop_callback():
            raise WorkflowCancelled()

    @staticmethod
    def _terminate_tree(process):
        """Stop the command and its children, including shell pipelines."""
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def popen(self, command, **kwargs):
        """Start a process with a cancellation watcher independent of its output."""
        self.check_cancelled()
        if os.name != "nt":
            kwargs["start_new_session"] = True
        process = subprocess.Popen(command, **kwargs)
        if self.stop_callback:
            def watch():
                while process.poll() is None:
                    if self.stop_callback():
                        self._terminate_tree(process)
                        return
                    try:
                        process.wait(timeout=0.1)
                    except subprocess.TimeoutExpired:
                        pass
            threading.Thread(target=watch, daemon=True).start()
        return process

    def run_process(self, command, *, check=False, capture_output=False,
                    timeout=None, **kwargs):
        """Cancellation-aware subprocess.run for commands with redirected files."""
        if capture_output:
            kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with self.popen(command, **kwargs) as process:
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except BaseException:
                self._terminate_tree(process)
                process.communicate()
                raise
            self.check_cancelled()
            if check and process.returncode:
                raise subprocess.CalledProcessError(
                    process.returncode, command, output=stdout, stderr=stderr
                )
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)

    def execute(self, command: str, capture_output: bool = False,
                check: bool = True, cwd: Optional[Path] = None,
                log_captured_output: bool = False,
                stream_output: bool = False,
                gui_output_filter: Optional[Callable[[str], bool]] = None,
                gui_output_transform: Optional[Callable[[str], Optional[str]]] = None) -> subprocess.CompletedProcess:
        """
        Execute a shell command with logging.

        Args:
            command: Shell command to execute
            capture_output: If True, capture stdout/stderr
            check: If True, raise exception on non-zero exit code
            cwd: Working directory for command execution
            log_captured_output: If True, write captured stdout/stderr to the INFO log
            stream_output: If True, relay combined stdout/stderr to the logger as it arrives
            gui_output_filter: Optional function deciding which streamed lines appear in the GUI
            gui_output_transform: Optional function that replaces or hides streamed GUI lines

        Returns:
            subprocess.CompletedProcess object

        Raises:
            subprocess.CalledProcessError: If command fails and check=True
        """
        if capture_output and stream_output:
            raise ValueError("capture_output and stream_output cannot both be enabled")

        # Register command with logger
        self.check_cancelled()
        cmd_index = self.logger.register_command(command, cwd=cwd)

        try:
            # Execute command
            if stream_output:
                process = self.popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=cwd,
                )
                output_lines = []
                for line in process.stdout:
                    line = line.rstrip()
                    if line:
                        output_lines.append(line)
                        gui_line = gui_output_transform(line) if gui_output_transform else line
                        visible = gui_line is not None
                        if gui_output_filter:
                            visible = visible and gui_output_filter(line)
                        self.logger.info(
                            f"    {line}",
                            gui_visible=visible,
                            gui_message=f"    {gui_line}" if visible else None,
                        )

                returncode = process.wait()
                process.stdout.close()
                self.check_cancelled()
                if check and returncode:
                    output = "\n".join(output_lines)
                    raise subprocess.CalledProcessError(
                        returncode, command, output=output
                    )
                result = subprocess.CompletedProcess(command, returncode)
            elif capture_output:
                result = self.run_process(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    check=check,
                    cwd=cwd
                )
            else:
                result = self.run_process(
                    command,
                    shell=True,
                    check=check,
                    cwd=cwd
                )

            # Mark as successful
            self.logger.mark_command_success(
                cmd_index,
                returncode=result.returncode,
                stdout=result.stdout if capture_output else None,
                stderr=result.stderr if capture_output else None,
                output_level="info" if log_captured_output else "debug",
            )
            return result

        except WorkflowCancelled:
            self.logger.mark_command_cancelled(cmd_index)
            raise

        except subprocess.CalledProcessError as e:
            stdout = getattr(e, "stdout", None) or getattr(e, "output", None)
            # Mark as failed
            self.logger.mark_command_failed(
                cmd_index,
                str(e),
                returncode=e.returncode,
                # Streamed output has already reached the GUI line-by-line.
                stdout=stdout if (capture_output or stream_output) else None,
                stderr=e.stderr if capture_output else None,
            )
            raise

        except RuntimeError as e:
            self.logger.mark_command_failed(cmd_index, str(e))
            raise

    def execute_pipeline(self, commands, gui_output_filter=None):
        """Pipe binary stdout between argument lists and require every tool to succeed.

        The final tool writes its own output file. Drain stderr concurrently so
        a verbose tool cannot block the pipeline while another tool is waiting.
        """
        if not commands:
            raise ValueError("Pipeline must contain at least one command")
        self.check_cancelled()
        command_text = " | ".join(format_command(command) for command in commands)
        command_index = self.logger.register_command(command_text)
        processes = []
        readers = []
        diagnostics = [[] for _ in commands]

        def read_diagnostics(process, index):
            for raw_line in iter(process.stderr.readline, b''):
                line = raw_line.decode('utf-8', errors='replace').rstrip()
                if line:
                    diagnostics[index].append(line)
                    self.logger.info(
                        f"    {line}",
                        gui_visible=gui_output_filter(line) if gui_output_filter else True,
                    )

        try:
            try:
                for index, command in enumerate(commands):
                    previous = processes[-1] if processes else None
                    process = self.popen(
                        [str(argument) for argument in command],
                        stdin=previous.stdout if previous else None,
                        stdout=subprocess.PIPE if index < len(commands) - 1 else subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                    )
                    processes.append(process)
                    # Only the downstream tool owns this read end. Retaining it
                    # here would prevent a producer from detecting a closed pipe.
                    if previous:
                        previous.stdout.close()
                    reader = threading.Thread(target=read_diagnostics, args=(process, index))
                    reader.start()
                    readers.append(reader)

                pause = threading.Event()
                while True:
                    self.check_cancelled()
                    returncodes = [process.poll() for process in processes]
                    failed = next((i for i, code in enumerate(returncodes)
                                   if code is not None and code != 0), None)
                    if failed is not None:
                        raise subprocess.CalledProcessError(
                            returncodes[failed], format_command(commands[failed])
                        )
                    if all(code is not None for code in returncodes):
                        break
                    pause.wait(PROCESS_POLL_INTERVAL_SECONDS)
            finally:
                for process in processes:
                    if process.poll() is None:
                        self._terminate_tree(process)
                for process in processes:
                    process.wait()
                    if process.stdout:
                        process.stdout.close()
                for reader in readers:
                    reader.join()
                for process in processes:
                    process.stderr.close()

            self.check_cancelled()
            self.logger.mark_command_success(command_index, returncode=0)
            return subprocess.CompletedProcess(command_text, 0)
        except WorkflowCancelled:
            self.logger.mark_command_cancelled(command_index)
            raise
        except Exception as error:
            self.logger.mark_command_failed(
                command_index, str(error),
                returncode=getattr(error, 'returncode', None),
                stderr='\n'.join(line for output in diagnostics for line in output),
            )
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
        tool_path = shutil.which(tool_name)

        if tool_path:
            self.logger.debug(f"Found {tool_name}: {tool_path}")
            return True

        self.logger.debug(f"Tool not found: {tool_name}")
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
