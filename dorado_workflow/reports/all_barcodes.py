"""Stable public entry point for the NanoTel dashboard generator."""
from .overview.dashboard import generate_report, generate_run_report, render_screen, main

__all__ = ['generate_report', 'generate_run_report', 'render_screen', 'main']

if __name__ == '__main__':
    main()
