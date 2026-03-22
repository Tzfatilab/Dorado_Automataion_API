#!/usr/bin/env Rscript
# Debug script to check barcode matching

source("functions/utils.R")
library(stringr)

# Test barcode extraction and normalization
test_filename <- "e8cbe1c0-b0e8-4956-bf76-868d3dd7833a_SQK-NBD114-24_barcode02.bam"
cat("Testing filename:", test_filename, "\n")

# Test extraction
extracted <- extract_barcode_from_path(test_filename)
cat("Extracted barcode:", extracted, "\n")

# Test normalization
normalized <- normalize_barcode_name(extracted)
cat("Normalized barcode:", normalized, "\n")

# Test with NanoTel filenames
nanotel_files <- c(
  "filtered_summaryBARCODE10.csv",
  "filtered_summaryBARCODE11.csv",
  "filtered_summaryBARCODE2.csv"
)

cat("\nTesting NanoTel files:\n")
for (file in nanotel_files) {
  extracted <- extract_barcode_from_path(file)
  normalized <- normalize_barcode_name(extracted)
  cat("File:", file, "-> Extracted:", extracted, "-> Normalized:", normalized, "\n")
}

# Check actual BAM directory
bam_dir <- "/home/tzfati/Desktop/minknow_runs/Trial_74_Aki/demuxed"
if (dir.exists(bam_dir)) {
  cat("\nActual BAM files found:\n")
  bam_files <- list.files(bam_dir, pattern = "\\.bam$", recursive = TRUE, full.names = TRUE)

  for (i in 1:min(5, length(bam_files))) {  # Show first 5
    file <- bam_files[i]
    extracted <- extract_barcode_from_path(file)
    normalized <- normalize_barcode_name(extracted)
    cat("BAM:", basename(file), "-> Extracted:", extracted, "-> Normalized:", normalized, "\n")
  }

  cat("Total BAM files found:", length(bam_files), "\n")

  # Show unique barcodes
  all_normalized <- sapply(bam_files, function(x) normalize_barcode_name(extract_barcode_from_path(x)))
  unique_barcodes <- unique(all_normalized[!is.na(all_normalized)])
  cat("Unique normalized barcodes in BAM files:", paste(unique_barcodes, collapse = ", "), "\n")
}

# Check NanoTel directory
nanotel_dir <- "/home/tzfati/Desktop/minknow_runs/Dorado_automation_test/Trial_74_Aki_TEST/nanotel_output"
if (dir.exists(nanotel_dir)) {
  cat("\nActual NanoTel files found:\n")
  nanotel_files <- list.files(nanotel_dir, pattern = "filtered_summary.*\\.csv$", full.names = TRUE)

  for (file in nanotel_files) {
    extracted <- extract_barcode_from_path(file)
    normalized <- normalize_barcode_name(extracted)
    cat("NanoTel:", basename(file), "-> Extracted:", extracted, "-> Normalized:", normalized, "\n")
  }

  # Show unique barcodes
  all_normalized <- sapply(nanotel_files, function(x) normalize_barcode_name(extract_barcode_from_path(x)))
  unique_barcodes <- unique(all_normalized[!is.na(all_normalized)])
  cat("Unique normalized barcodes in NanoTel files:", paste(unique_barcodes, collapse = ", "), "\n")
}
