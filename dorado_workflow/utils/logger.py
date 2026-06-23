"""
Logger Module
=============


Handles all logging operations for the Dorado workflow.
Provides centralized logging with command tracking and history generation.


No dependencies - this is the foundation class.
"""


import sys
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Callable
import threading




class CallbackHandler(logging.Handler):
    """Logging handler that forwards formatted messages to a callback."""

    _R_STARTUP_NOISE = re.compile(
        r"^(?:\d+: )?package '.+' was built under R version \d+(?:\.\d+)+$"
    )


    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self.callback = callback


    def emit(self, record: logging.LogRecord) -> None:
        try:
            gui_message = getattr(record, "gui_message", None)
            message = gui_message if gui_message is not None else record.getMessage()
            if not getattr(record, "gui_visible", True) or self._is_gui_noise(message):
                return
            msg = gui_message if gui_message is not None else self.format(record)
            self.callback(msg)
        except Exception:
            self.handleError(record)

    @classmethod
    def _is_gui_noise(cls, message: str) -> bool:
        """Hide routine R package startup notices from the GUI only."""
        message = message.strip()
        return (
            message in {"Warning message:", "Warning messages:"}
            or bool(cls._R_STARTUP_NOISE.match(message))
            or message.startswith("[conflicted] Will prefer ")
        )




class WorkflowLogger:
    """
    Centralized logger for the Dorado workflow pipeline.


    Features:
    - Timestamped log messages with levels (INFO, WARNING, ERROR)
    - Command execution tracking with success/failure status
    - Shell script generation of executed commands
    - Thread-safe command tracking
    - Both file and console output
    """


    def __init__(
        self,
        log_file_path: Optional[Path] = None,
        log_level: str = "INFO",
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the workflow logger.


        Args:
            log_file_path: Path to the log file. If None, only console logging is enabled.
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_callback: Optional callback for forwarding log text.
        """
        self.log_file_path = log_file_path
        self.log_callback = log_callback
        self.executed_commands: List[Dict] = []
        self.command_lock = threading.Lock()


        # Setup Python's logging module
        self._setup_logging(log_level)


        if log_file_path:
            self.info(f"Logger initialized. Log file: {log_file_path}", gui_visible=False)


    def _setup_logging(self, log_level: str) -> None:
        """Configure Python's logging module."""
        level = getattr(logging, log_level.upper(), logging.INFO)


        # Create logger
        self.logger = logging.getLogger("dorado_workflow")
        self.logger.setLevel(level)


        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()


        # Console or callback handler
        console_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s',
                                           datefmt='%Y-%m-%d %H:%M:%S')


        if self.log_callback:
            callback_handler = CallbackHandler(self.log_callback)
            callback_handler.setLevel(level)
            # The GUI adds its own compact [HH:MM:SS] timestamp.  Forwarding
            # only the message avoids a noisy, duplicated terminal-style prefix.
            callback_handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(callback_handler)
        else:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(console_format)
            self.logger.addHandler(console_handler)


        # File handler (if log file specified)
        if self.log_file_path:
            # Ensure parent directory exists
            self.log_file_path.parent.mkdir(parents=True, exist_ok=True)


            file_handler = logging.FileHandler(self.log_file_path)
            file_handler.setLevel(level)
            file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s',
                                            datefmt='%Y-%m-%d %H:%M:%S')
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)


    # ==================== Logging Methods ====================


    def debug(self, message: str) -> None:
        """Log debug message."""
        self.logger.debug(message)


    def info(self, message: str, gui_visible: bool = True,
             gui_message: Optional[str] = None) -> None:
        """Log info message."""
        self.logger.info(
            message,
            extra={"gui_visible": gui_visible, "gui_message": gui_message},
        )


    def warning(self, message: str) -> None:
        """Log warning message."""
        self.logger.warning(message)


    def error(self, message: str) -> None:
        """Log error message."""
        self.logger.error(message)


    def critical(self, message: str) -> None:
        """Log critical message."""
        self.logger.critical(message)


    # ==================== Command Tracking ====================


    def register_command(self, command: str, cwd: Optional[Path] = None) -> int:
        """
        Register a command as it starts executing.
        Thread-safe operation.


        Args:
            command: The command string to register


        Returns:
            Command index for later status updates
        """
        with self.command_lock:
            cmd_index = len(self.executed_commands)
            started_at = datetime.now()
            self.executed_commands.append({
                'number': cmd_index + 1,
                'timestamp': started_at.strftime('%H:%M:%S'),
                'started_at': started_at.isoformat(timespec='seconds'),
                'command': command,
                'cwd': str(cwd) if cwd else None,
                'status': 'running',
                '_started_timestamp': started_at.timestamp(),
            })
            self.info("Starting command", gui_visible=False)
            self.info(f"  Command: {command}", gui_visible=False)
            self.info(
                f"  Location: {cwd if cwd else 'workflow default'}",
                gui_visible=False,
            )
            return cmd_index


    def mark_command_success(self, cmd_index: int, returncode: int = 0,
                             stdout: Optional[str] = None,
                             stderr: Optional[str] = None,
                             output_level: str = "debug") -> None:
        """
        Mark a command as successfully completed.


        Args:
            cmd_index: Index returned from register_command()
        """
        with self.command_lock:
            if 0 <= cmd_index < len(self.executed_commands):
                command = self.executed_commands[cmd_index]
                duration = datetime.now().timestamp() - command.pop('_started_timestamp')
                command.update({
                    'status': 'success',
                    'returncode': returncode,
                    'duration_seconds': duration,
                })
                self.info(f"Command completed in {duration:.1f}s")
                self.info(f"  Exit code: {returncode}", gui_visible=False)
                self._log_command_output(stdout, stderr, level=output_level)
                return
                self.executed_commands[cmd_index]['status'] = 'success'
                self.info(f"✓ Command completed successfully")


    def mark_command_failed(self, cmd_index: int, error: str = "",
                            returncode: Optional[int] = None,
                            stdout: Optional[str] = None,
                            stderr: Optional[str] = None) -> None:
        """
        Mark a command as failed.


        Args:
            cmd_index: Index returned from register_command()
            error: Error message or exception details
        """
        with self.command_lock:
            if 0 <= cmd_index < len(self.executed_commands):
                command = self.executed_commands[cmd_index]
                duration = datetime.now().timestamp() - command.pop('_started_timestamp')
                command.update({
                    'status': 'failed',
                    'error': error,
                    'returncode': returncode,
                    'duration_seconds': duration,
                })
                exit_code = f" (exit code {returncode})" if returncode is not None else ""
                self.error(f"Command failed after {duration:.1f}s")
                if returncode is not None:
                    self.error(f"  Exit code: {returncode}")
                self.error(f"  Error: {error}")
                self._log_command_output(stdout, stderr, level="error")
                return
                self.executed_commands[cmd_index]['status'] = 'failed'
                self.executed_commands[cmd_index]['error'] = error
                self.error(f"✗ Command failed: {error}")


    def _log_command_output(self, stdout: Optional[str], stderr: Optional[str],
                            level: str = "debug") -> None:
        """Log captured command output when it contains useful diagnostic detail."""
        for name, output in (("stdout", stdout), ("stderr", stderr)):
            if output and output.strip():
                log = getattr(self, level)
                log(f"  {name.title()}:")
                for line in output.strip().splitlines():
                    log(f"    {line}")

    def get_command_history(self) -> List[Dict]:
        """
        Get the complete command execution history.


        Returns:
            List of command dictionaries with timestamp, command, status, and optional error
        """
        with self.command_lock:
            return self.executed_commands.copy()


    # ==================== Report Generation ====================


    def save_command_history(self, output_path: Path) -> str:
        """
        Save command history as an executable shell script.


        Args:
            output_path: Path where the shell script should be saved


        Returns:
            Path to the generated script
        """
        script_lines = [
            "#!/bin/bash",
            f"# Commands executed by Dorado Workflow",
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "# NOTE: This is a record of commands that were executed.",
            "# You can review, modify, and re-run these commands manually if needed.",
            "",
        ]


        with self.command_lock:
            for i, cmd_info in enumerate(self.executed_commands, 1):
                status_comment = f"# {cmd_info['status'].upper()}"
                script_lines.extend([
                    f"# Command {i} - {cmd_info['timestamp']} - {status_comment}",
                    f"# Duration: {cmd_info.get('duration_seconds', 0):.1f}s; exit code: {cmd_info.get('returncode', 'n/a')}",
                    f"# Working directory: {cmd_info['cwd']}" if cmd_info.get('cwd') else "# Working directory: inherited",
                    cmd_info['command'],
                    ""
                ])


                if cmd_info['status'] == 'failed' and 'error' in cmd_info:
                    script_lines.insert(-1, f"# Error: {cmd_info['error']}")


        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)


        # Write script
        output_path.write_text('\n'.join(script_lines))


        # Make executable
        output_path.chmod(0o755)


        self.info(f"Command history saved to: {output_path}")
        return str(output_path)


    def generate_summary_report(self, output_path: Path, custom_sections: Optional[Dict] = None) -> str:
        """
        Generate a comprehensive summary report.


        Args:
            output_path: Path where the report should be saved
            custom_sections: Optional dictionary of custom report sections
                           Format: {"SECTION_NAME": ["line1", "line2", ...]}


        Returns:
            Path to the generated report
        """
        report_lines = [
            "=" * 80,
            "WORKFLOW EXECUTION SUMMARY",
            "=" * 80,
            f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]


        # Add custom sections if provided
        if custom_sections:
            for section_name, section_lines in custom_sections.items():
                report_lines.extend([
                    section_name,
                    "-" * len(section_name),
                    *section_lines,
                    "",
                ])


        # Add command execution summary
        with self.command_lock:
            total_commands = len(self.executed_commands)
            successful = sum(1 for cmd in self.executed_commands if cmd['status'] == 'success')
            failed = sum(1 for cmd in self.executed_commands if cmd['status'] == 'failed')


            report_lines.extend([
                "COMMAND EXECUTION SUMMARY",
                "-" * 30,
                f"Total commands executed: {total_commands}",
                f"Successful: {successful}",
                f"Failed: {failed}",
                "",
            ])


            # Detailed command list
            if self.executed_commands:
                report_lines.extend([
                    "EXECUTED COMMANDS",
                    "=" * 50,
                ])


                for i, cmd_info in enumerate(self.executed_commands, 1):
                    status_icon = "✓" if cmd_info['status'] == 'success' else "✗"
                    report_lines.extend([
                        f"{i}. [{cmd_info['timestamp']}] {status_icon} {cmd_info['status'].upper()}",
                        f"   Command: {cmd_info['command']}",
                        f"   Duration: {cmd_info.get('duration_seconds', 0):.1f}s",
                        f"   Exit code: {cmd_info.get('returncode', 'n/a')}",
                    ])

                    if cmd_info.get('cwd'):
                        report_lines.append(f"   Working directory: {cmd_info['cwd']}")


                    if cmd_info['status'] == 'failed' and 'error' in cmd_info:
                        report_lines.append(f"   Error: {cmd_info['error']}")


                    report_lines.append("")


        report_lines.append("=" * 80)


        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)


        # Write report
        output_path.write_text('\n'.join(report_lines))


        self.info(f"Summary report saved to: {output_path}")
        return str(output_path)


    # ==================== Utility Methods ====================


    def section_header(self, title: str, char: str = "=") -> None:
        """
        Log a formatted section header.


        Args:
            title: Section title
            char: Character to use for the border
        """
        self.info(title)


    def close(self) -> None:
        """Close the logger and flush all handlers."""
        for handler in self.logger.handlers:
            handler.close()
        self.logger.handlers.clear()
