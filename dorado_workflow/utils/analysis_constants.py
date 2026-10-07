"""Existing operational values, named with units; not new analysis thresholds."""

# NanoTel.R's --nrec default: reads processed per chunk (progress estimate only).
NANOTEL_RECORDS_PER_CHUNK = 10_000
# Standard unwrapped FASTQ has header, sequence, separator and quality lines.
FASTQ_LINES_PER_RECORD = 4
# Poll interval in seconds for checking subprocess completion and cancellation.
PROCESS_POLL_INTERVAL_SECONDS = 0.05
