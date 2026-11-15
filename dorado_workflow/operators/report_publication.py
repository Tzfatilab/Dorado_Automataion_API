"""Publish run reports and finalize retained files in workflow order.

Renderers build presentation content; this service owns the sequence of source
organization, HTML/Excel publication, verified cleanup and native-data archiving.
"""
from pathlib import Path
from dorado_workflow.reports.interactive.importers import import_results
from dorado_workflow.reports.overview.comparisons import comparison_data
from dorado_workflow.reports.overview.dashboard import render_screen


def publish_run_report(results, nanotel_directory, progress=None):
    """Save a self-contained dashboard.html directly under NanoTel.

    Source provenance and links to barcode reports are embedded in the HTML.
    Native barcode exports are grouped under supporting_data; recalculations
    keep references to their original read details without copying them.

    Args:
        results: Results directory or collected processing results.
        nanotel_directory: Nanotel directory.

    Returns:
        Path to the completed run dashboard.
    """
    from dorado_workflow.reports.storage.layout import prepare_run_report, atomic_text, organize_barcode_reports
    from dorado_workflow.reports.storage.archive import available_details, pack_details
    from time import perf_counter
    progress = progress or (lambda message: None)
    started = perf_counter()
    progress("Dashboard: discovering saved report sources")
    organize_barcode_reports(nanotel_directory)
    is_recalculated_run = (Path(results) / 'reports' / 'post_analysis_source.json').is_file()
    if not is_recalculated_run:
        from dorado_workflow.reports.storage.layout import organize_supporting_data
        organize_supporting_data(nanotel_directory)
    # Import and embed saved plots while the archive contents are available.
    with available_details(results):
        run = import_results(results, progress=progress)
        progress(f"Dashboard: saved data loaded in {perf_counter()-started:.1f}s; building charts and HTML")
        started = perf_counter()
        comparisons = comparison_data(run)
        page = render_screen(run, results_root=results, comparisons=comparisons)
        destination, page = prepare_run_report(nanotel_directory, run, page)
        atomic_text(destination, page)
        from .report_cleanup import cleanup_legacy_reports
        cleanup_legacy_reports(nanotel_directory, page)
        progress(f"Dashboard: HTML saved in {perf_counter()-started:.1f}s; writing unified Excel")
        del page
        started = perf_counter()
        from dorado_workflow.reports.exports.dashboard_workbook import write_dashboard_workbook
        write_dashboard_workbook(run, Path(nanotel_directory) / "nanotel_results.xlsx", results, comparisons=comparisons, progress=progress)
        progress(f"Dashboard: Excel saved in {perf_counter()-started:.1f}s; verifying retained sources")
        from .report_cleanup import cleanup_analysis_json
        from dorado_workflow.reports.shared.organism import show_km
        cleanup_analysis_json(results, include_km=show_km(run))
    from .report_cleanup import cleanup_source_tables
    cleanup_source_tables(results, Path(nanotel_directory) / 'nanotel_results.xlsx')
    progress("Dashboard: source verification complete")
    # Recalculation references original details. Only native detection exports
    # belong in a new archive; never repack source details for a recalculation.
    if not is_recalculated_run:
        # Archive only after a complete dashboard has been saved successfully.
        from dorado_workflow.utils.source_discovery import barcode_directories
        for barcode_directory in barcode_directories(nanotel_directory):
            if barcode_directory.is_dir():
                pack_details(barcode_directory)
    return destination
