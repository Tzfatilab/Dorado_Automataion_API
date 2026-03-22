#!/usr/bin/env python3
"""
Dorado Workflow - Main Entry Point
==================================

Command-line interface for the Dorado workflow system.

Usage:
    # POD5 workflow (complete pipeline)
    python main.py pod5 Trial_75 /path/to/pod5 --organism mouse

    # FASTQ workflow (from MinKNOW output)
    python main.py fastq Trial_75 /path/to/fastq --organism mouse

    # Single process execution
    python main.py nanotel Trial_75 /path/to/fastq
    python main.py align Trial_75 /path/to/fastq --organism mouse
    python main.py r-analysis Trial_75 --filtration --mapping --methylation

    # Show version
    python main.py --version
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

# Import workflow components
from operators.workflow_operator import WorkflowOperator
from processors.base import WorkflowContext
from managers.config_manager import ConfigManager
from managers.path_manager import PathManager
from managers.barcode_manager import BarcodeManager
from utils.logger import WorkflowLogger
from utils.command_executor import CommandExecutor


def setup_context(trial_name: str,
                  base_output_dir: Optional[str] = None,
                  config_path: Optional[str] = None) -> WorkflowContext:
    """
    Initialize and setup workflow context with all dependencies.

    Args:
        trial_name: Name of the trial (e.g., "Trial_75")
        base_output_dir: Base output directory (optional)
        config_path: Path to config file (optional, uses default if not provided)

    Returns:
        WorkflowContext with all initialized dependencies
    """
    # Initialize configuration
    if config_path:
        config = ConfigManager(config_path)
    else:
        config = ConfigManager()

    # Initialize path manager
    path_mgr = PathManager(trial_name, base_output_dir, config_manager=config)

    # Initialize logger
    log_file = path_mgr.get_log_file_path()
    logger = WorkflowLogger(log_file)

    logger.info("=" * 60)
    logger.info(f"Dorado Workflow v2.0 - Trial: {trial_name}")
    logger.info("=" * 60)

    # Initialize command executor
    executor = CommandExecutor(logger)

    # Initialize barcode manager
    barcode_mgr = BarcodeManager()

    # Create and return context
    context = WorkflowContext(logger, config, path_mgr, barcode_mgr, executor)

    return context


def cmd_pod5_workflow(args) -> int:
    """Execute POD5 complete workflow."""
    context = setup_context(args.trial_name, args.output_dir, args.config)
    operator = WorkflowOperator(context)

    success = operator.run_pod5_workflow(
        pod5_input=args.input,
        organism=args.organism
    )

    return 0 if success else 1


def cmd_fastq_workflow(args) -> int:
    """Execute FASTQ workflow."""
    context = setup_context(args.trial_name, args.output_dir, args.config)
    operator = WorkflowOperator(context)

    success = operator.run_fastq_workflow(
        fastq_input=args.input,
        organism=args.organism
    )

    return 0 if success else 1


def cmd_nanotel_only(args) -> int:
    """Execute NanoTel analysis only."""
    context = setup_context(args.trial_name, args.output_dir, args.config)
    operator = WorkflowOperator(context)

    success = operator.run_nanotel_only(fastq_input=args.input)

    return 0 if success else 1


def cmd_alignment_only(args) -> int:
    """Execute alignment only."""
    context = setup_context(args.trial_name, args.output_dir, args.config)
    operator = WorkflowOperator(context)

    success = operator.run_alignment_only(
        fastq_input=args.input,
        organism=args.organism
    )

    return 0 if success else 1


def cmd_r_analysis_only(args) -> int:
    """Execute R analysis only."""
    context = setup_context(args.trial_name, args.output_dir, args.config)
    operator = WorkflowOperator(context)

    success = operator.run_r_analysis_only(
        run_filtration=args.filtration,
        run_mapping=args.mapping,
        run_methylation=args.methylation
    )

    return 0 if success else 1


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Dorado Workflow - Nanopore sequencing data processing pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Complete POD5 workflow
  python main.py pod5 Trial_75 /data/pod5_files --organism mouse

  # FASTQ workflow (from MinKNOW)
  python main.py fastq Trial_75 /data/fastq_pass --organism human

  # Single processes
  python main.py nanotel Trial_75 /data/fastqs
  python main.py align Trial_75 /data/fastqs --organism mouse

  # R analysis - all three by default
  python main.py r-analysis Trial_75

  # R analysis - selective (use --no-* flags to skip)
  python main.py r-analysis Trial_75 --no-mapping --no-methylation  # filtration only
  python main.py r-analysis Trial_75 --no-filtration                 # mapping & methylation only
        """
    )

    parser.add_argument('--version', action='version', version='Dorado Workflow v2.0')
    parser.add_argument('--config', type=str, help='Path to custom config file')
    parser.add_argument('--output-dir', type=str, help='Base output directory')

    subparsers = parser.add_subparsers(dest='command', help='Workflow command')
    subparsers.required = True

    # POD5 workflow
    parser_pod5 = subparsers.add_parser(
        'pod5',
        help='Run complete POD5 workflow (basecall → demux → nanotel → align → R analysis)'
    )
    parser_pod5.add_argument('trial_name', help='Trial name (e.g., Trial_75)')
    parser_pod5.add_argument('input', help='Path to POD5 input (file or directory)')
    parser_pod5.add_argument('--organism', choices=['mouse', 'human', 'zebrafish'], default='mouse',
                             help='Organism type for reference selection')
    parser_pod5.set_defaults(func=cmd_pod5_workflow)

    # FASTQ workflow
    parser_fastq = subparsers.add_parser(
        'fastq',
        help='Run FASTQ workflow (nanotel → align → R filtration)'
    )
    parser_fastq.add_argument('trial_name', help='Trial name (e.g., Trial_75)')
    parser_fastq.add_argument('input', help='Path to FASTQ directory')
    parser_fastq.add_argument('--organism', choices=['mouse', 'human', 'zebrafish'], default='mouse',
                              help='Organism type for reference selection')
    parser_fastq.set_defaults(func=cmd_fastq_workflow)

    # NanoTel only
    parser_nanotel = subparsers.add_parser(
        'nanotel',
        help='Run NanoTel analysis only'
    )
    parser_nanotel.add_argument('trial_name', help='Trial name')
    parser_nanotel.add_argument('input', help='Path to FASTQ directory')
    parser_nanotel.set_defaults(func=cmd_nanotel_only)

    # Alignment only
    parser_align = subparsers.add_parser(
        'align',
        help='Run alignment only'
    )
    parser_align.add_argument('trial_name', help='Trial name')
    parser_align.add_argument('input', help='Path to FASTQ directory')
    parser_align.add_argument('--organism', choices=['mouse', 'human', 'zebrafish'], default='mouse',
                              help='Organism type for reference selection')
    parser_align.set_defaults(func=cmd_alignment_only)

    # R analysis only
    parser_r = subparsers.add_parser(
        'r-analysis',
        help='Run R analysis only (requires prior NanoTel and/or alignment outputs)'
    )
    parser_r.add_argument('trial_name', help='Trial name')
    parser_r.add_argument('--no-filtration', dest='filtration', action='store_false', default=True,
                          help='Skip NanoTel filtration (default: run filtration)')
    parser_r.add_argument('--no-mapping', dest='mapping', action='store_false', default=True,
                          help='Skip mapping analysis (default: run mapping)')
    parser_r.add_argument('--no-methylation', dest='methylation', action='store_false', default=True,
                          help='Skip methylation analysis (default: run methylation)')
    parser_r.set_defaults(func=cmd_r_analysis_only)

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    try:
        exit_code = args.func(args)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nERROR: Workflow failed with exception: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()