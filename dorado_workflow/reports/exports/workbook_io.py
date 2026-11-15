"""Workbook serialization with cooperative cancellation and explicit ZIP cleanup."""
from zipfile import ZipFile, ZIP_DEFLATED
from openpyxl.writer.excel import ExcelWriter
from dorado_workflow.utils.cancellation import CancellableWriter


def save_cancellable(workbook, stream, check_cancelled):
    """Close the ZIP archive before its temporary stream, including on cancellation."""
    with ZipFile(CancellableWriter(stream, check_cancelled), 'w', ZIP_DEFLATED,
                 allowZip64=True) as archive:
        ExcelWriter(workbook, archive).save()
