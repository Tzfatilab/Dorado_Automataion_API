"""
Barcode Manager Module
=====================

Handles barcode extraction, normalization, tracking, and reporting.
Centralized barcode management across the workflow pipeline.
"""

import re
from pathlib import Path
from typing import Optional, List, Dict, Set
from collections import defaultdict


class BarcodeManager:
    """
    Manages barcode identification, tracking, and status across workflow stages.

    Features:
    - Extract and normalize barcode names from paths
    - Auto-discover barcodes in directories
    - Track success/failure status per process
    - Handle multiple BAM files per barcode
    - Generate barcode summary reports
    """

    # Regex pattern for barcode extraction (case-insensitive)
    BARCODE_PATTERN = re.compile(r'(bc|barcode)(\d+)', re.IGNORECASE)

    def __init__(self):
        """Initialize the barcode manager."""
        # Track barcode status: {barcode: {process_name: {'status': 'success/failed', 'error': '...'}}}
        self.barcode_status: Dict[str, Dict[str, Dict]] = defaultdict(dict)

        # Track discovered barcodes
        self.discovered_barcodes: Set[str] = set()

        # Track multiple files per barcode (e.g., multiple BAMs)
        self.barcode_files: Dict[str, List[Path]] = defaultdict(list)

    # ==================== Barcode Extraction & Normalization ====================

    def extract_barcode(self, path: str) -> Optional[str]:
        """
        Extract barcode from filename or directory path.
        Python reimplementation of R's extract_barcode_from_path.

        Searches for patterns like:
        - barcode01, barcode02, ... barcode24
        - bc01, bc02, ... bc24
        - BARCODE01, BC01 (case-insensitive)

        Args:
            path: File path or directory path

        Returns:
            Extracted barcode (e.g., "barcode01") or None if not found
        """
        path_obj = Path(path)

        # First try the filename
        match = self.BARCODE_PATTERN.search(path_obj.name)
        if match:
            prefix = match.group(1).lower()  # "bc" or "barcode"
            number = match.group(2)  # "01", "02", etc.

            # Standardize to "barcodeXX" format
            if prefix == "bc":
                return f"barcode{number}"
            else:
                return f"{prefix}{number}"

        # If not in filename, try parent directory
        if path_obj.parent.name:
            match = self.BARCODE_PATTERN.search(path_obj.parent.name)
            if match:
                prefix = match.group(1).lower()
                number = match.group(2)

                if prefix == "bc":
                    return f"barcode{number}"
                else:
                    return f"{prefix}{number}"

        return None

    def normalize_barcode(self, barcode: str) -> str:
        """
        Normalize barcode name to standard format.
        Python reimplementation of R's normalize_barcode_name.

        Converts various formats to standard:
        - "bc01" -> "barcode1"
        - "BARCODE01" -> "barcode1"
        - "barcode02" -> "barcode2"

        Removes leading zeros from numbers.

        Args:
            barcode: Barcode string in any format

        Returns:
            Normalized barcode (e.g., "barcode1", "barcode10")
        """
        if not barcode:
            return ""

        barcode_lower = barcode.lower()

        # Extract prefix and number
        match = self.BARCODE_PATTERN.search(barcode_lower)
        if match:
            prefix = match.group(1)  # "bc" or "barcode"
            number_str = match.group(2)  # "01", "02", etc.

            # Convert to integer to remove leading zeros, then back to string
            number = str(int(number_str))

            # Always use "barcode" prefix
            return f"barcode{number}"

        # If no match, return lowercase version
        return barcode_lower

    # ==================== Barcode Discovery ====================

    def discover_barcodes(self, directory: Path, pattern: str = "*") -> List[str]:
        """
        Auto-discover barcodes in a directory by scanning for barcode subdirectories.

        Args:
            directory: Directory to scan
            pattern: Glob pattern for searching (default: "*")

        Returns:
            Sorted list of discovered barcode names (normalized)
        """
        directory = Path(directory)

        if not directory.exists():
            return []

        discovered = set()

        # Scan for subdirectories
        for item in directory.iterdir():
            if item.is_dir():
                barcode = self.extract_barcode(str(item))
                if barcode:
                    normalized = self.normalize_barcode(barcode)
                    discovered.add(normalized)
                    self.discovered_barcodes.add(normalized)

        # Sort barcodes by number
        return self._sort_barcodes(list(discovered))

    def discover_barcode_files(self, directory: Path, file_pattern: str = "*.bam") -> Dict[str, List[Path]]:
        """
        Discover all files for each barcode (handles multiple files per barcode).

        Args:
            directory: Directory to scan
            file_pattern: File pattern to match (e.g., "*.bam", "*.fastq")

        Returns:
            Dictionary mapping barcode -> list of file paths
        """
        directory = Path(directory)

        if not directory.exists():
            return {}

        barcode_file_map = defaultdict(list)

        # Recursively find files matching pattern
        for file_path in directory.rglob(file_pattern):
            barcode = self.extract_barcode(str(file_path))
            if barcode:
                normalized = self.normalize_barcode(barcode)
                barcode_file_map[normalized].append(file_path)
                self.discovered_barcodes.add(normalized)

        # Store in instance variable
        for barcode, files in barcode_file_map.items():
            self.barcode_files[barcode].extend(files)

        return dict(barcode_file_map)

    # ==================== Status Tracking ====================

    def register_success(self, barcode: str, process_name: str) -> None:
        """
        Register successful processing for a barcode.

        Args:
            barcode: Barcode name
            process_name: Name of the process (e.g., "basecalling", "nanotel")
        """
        normalized = self.normalize_barcode(barcode)
        self.barcode_status[normalized][process_name] = {
            'status': 'success'
        }
        self.discovered_barcodes.add(normalized)

    def register_failure(self, barcode: str, process_name: str, error: str = "") -> None:
        """
        Register failed processing for a barcode.

        Args:
            barcode: Barcode name
            process_name: Name of the process
            error: Error message or reason for failure
        """
        normalized = self.normalize_barcode(barcode)
        self.barcode_status[normalized][process_name] = {
            'status': 'failed',
            'error': error
        }
        self.discovered_barcodes.add(normalized)

    def get_barcode_status(self, barcode: str, process_name: Optional[str] = None) -> Dict:
        """
        Get status for a barcode.

        Args:
            barcode: Barcode name
            process_name: Optional specific process name. If None, returns all statuses.

        Returns:
            Status dictionary
        """
        normalized = self.normalize_barcode(barcode)

        if process_name:
            return self.barcode_status.get(normalized, {}).get(process_name, {})
        else:
            return self.barcode_status.get(normalized, {})

    def should_process_barcode(self, barcode: str, required_process: str) -> bool:
        """
        Check if a barcode should be processed based on prerequisite step status.

        Args:
            barcode: Barcode name
            required_process: Name of prerequisite process that must have succeeded

        Returns:
            True if barcode should be processed, False if prerequisite failed
        """
        normalized = self.normalize_barcode(barcode)
        status = self.get_barcode_status(normalized, required_process)

        # If no status recorded, assume it should be processed
        if not status:
            return True

        # Only skip if explicitly failed
        return status.get('status') != 'failed'

    # ==================== Reporting & Summary ====================

    def get_successful_barcodes(self, process_name: str) -> List[str]:
        """
        Get list of barcodes that succeeded for a specific process.

        Args:
            process_name: Name of the process

        Returns:
            Sorted list of successful barcode names
        """
        successful = []

        for barcode in self.discovered_barcodes:
            status = self.get_barcode_status(barcode, process_name)
            if status.get('status') == 'success':
                successful.append(barcode)

        return self._sort_barcodes(successful)

    def get_failed_barcodes(self, process_name: str) -> List[str]:
        """
        Get list of barcodes that failed for a specific process.

        Args:
            process_name: Name of the process

        Returns:
            Sorted list of failed barcode names
        """
        failed = []

        for barcode in self.discovered_barcodes:
            status = self.get_barcode_status(barcode, process_name)
            if status.get('status') == 'failed':
                failed.append(barcode)

        return self._sort_barcodes(failed)

    def get_barcode_summary(self) -> Dict[str, Dict]:
        """
        Get complete summary of all barcodes and their statuses.

        Returns:
            Dictionary with summary statistics
        """
        summary = {
            'total_barcodes': len(self.discovered_barcodes),
            'barcodes': sorted(list(self.discovered_barcodes)),
            'process_summary': {}
        }

        # Collect all unique process names
        all_processes = set()
        for barcode_statuses in self.barcode_status.values():
            all_processes.update(barcode_statuses.keys())

        # Generate summary per process
        for process in all_processes:
            successful = len(self.get_successful_barcodes(process))
            failed = len(self.get_failed_barcodes(process))

            summary['process_summary'][process] = {
                'successful': successful,
                'failed': failed,
                'success_rate': f"{(successful / (successful + failed) * 100):.1f}%" if (
                                                                                                    successful + failed) > 0 else "N/A"
            }

        return summary

    def generate_barcode_report(self) -> List[str]:
        """
        Generate a detailed barcode report for logging/display.

        Returns:
            List of report lines
        """
        report_lines = [
            "=" * 60,
            "BARCODE PROCESSING SUMMARY",
            "=" * 60,
            f"Total barcodes discovered: {len(self.discovered_barcodes)}",
            f"Barcodes: {', '.join(self._sort_barcodes(list(self.discovered_barcodes)))}",
            ""
        ]

        # Get summary
        summary = self.get_barcode_summary()

        if summary['process_summary']:
            report_lines.append("PROCESS-WISE SUMMARY:")
            report_lines.append("-" * 60)

            for process, stats in summary['process_summary'].items():
                report_lines.extend([
                    f"  {process}:",
                    f"    Successful: {stats['successful']}",
                    f"    Failed: {stats['failed']}",
                    f"    Success rate: {stats['success_rate']}",
                    ""
                ])

        # List failed barcodes with errors
        report_lines.append("FAILED BARCODES (if any):")
        report_lines.append("-" * 60)

        has_failures = False
        for barcode in self._sort_barcodes(list(self.discovered_barcodes)):
            barcode_statuses = self.barcode_status.get(barcode, {})
            failed_processes = []

            for process, status in barcode_statuses.items():
                if status.get('status') == 'failed':
                    error = status.get('error', 'Unknown error')
                    failed_processes.append(f"{process}: {error}")

            if failed_processes:
                has_failures = True
                report_lines.append(f"  {barcode}:")
                for failure in failed_processes:
                    report_lines.append(f"    - {failure}")
                report_lines.append("")

        if not has_failures:
            report_lines.append("  None")
            report_lines.append("")

        report_lines.append("=" * 60)

        return report_lines

    # ==================== Utility Methods ====================

    def _sort_barcodes(self, barcodes: List[str]) -> List[str]:
        """
        Sort barcodes by their numeric component.

        Args:
            barcodes: List of barcode names

        Returns:
            Sorted list
        """

        def extract_number(barcode):
            match = re.search(r'(\d+)', barcode)
            return int(match.group(1)) if match else 0

        return sorted(barcodes, key=extract_number)

    def get_barcode_files(self, barcode: str) -> List[Path]:
        """
        Get all files associated with a barcode.

        Args:
            barcode: Barcode name

        Returns:
            List of file paths for this barcode
        """
        normalized = self.normalize_barcode(barcode)
        return self.barcode_files.get(normalized, [])

    def __repr__(self) -> str:
        """String representation of BarcodeManager."""
        return (
            f"BarcodeManager("
            f"barcodes={len(self.discovered_barcodes)}, "
            f"tracked_processes={len(set(p for statuses in self.barcode_status.values() for p in statuses.keys()))})"
        )