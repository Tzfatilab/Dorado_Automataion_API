#!/usr/bin/env Rscript
# Debug script to check alignment summary structure

source("functions/utils.R")

# Check the alignment summary file structure
alignment_file <- "/home/tzfati/Desktop/minknow_runs/Dorado_automation_test/Trial_74_Aki_TEST/aligned/alignment_summary.txt"

if (file.exists(alignment_file)) {
  cat("Reading alignment summary file...\n")

  # Read first few lines to see structure
  first_lines <- readLines(alignment_file, n = 5)
  cat("First 5 lines of file:\n")
  for (i in 1:length(first_lines)) {
    cat(paste0("Line ", i, ": ", first_lines[i], "\n"))
  }

  # Try to read as CSV/TSV
  cat("\nTrying to read as tab-separated...\n")
  tryCatch({
    data <- read.table(alignment_file, header = TRUE, sep = "\t", nrows = 5)
    cat("Column names found:\n")
    print(colnames(data))
    cat("\nFirst few rows:\n")
    print(data)
  }, error = function(e) {
    cat("Error reading as TSV:", e$message, "\n")
  })

  cat("\nTrying to read as comma-separated...\n")
  tryCatch({
    data <- read.table(alignment_file, header = TRUE, sep = ",", nrows = 5)
    cat("Column names found:\n")
    print(colnames(data))
    cat("\nFirst few rows:\n")
    print(data)
  }, error = function(e) {
    cat("Error reading as CSV:", e$message, "\n")
  })

} else {
  cat("Alignment summary file not found:", alignment_file, "\n")
}

# Also check a NanoTel file structure
nanotel_file <- "/home/tzfati/Desktop/minknow_runs/Dorado_automation_test/Trial_74_Aki_TEST/nanotel_output/filtered_summaryBARCODE10.csv"

if (file.exists(nanotel_file)) {
  cat("\n\nChecking NanoTel file structure...\n")

  tryCatch({
    data <- read.csv(nanotel_file, nrows = 3)
    cat("NanoTel columns:\n")
    print(colnames(data))
    cat("\nFirst few rows:\n")
    print(data[1:3, 1:5])  # Show first 3 rows, first 5 columns
  }, error = function(e) {
    cat("Error reading NanoTel file:", e$message, "\n")
  })
}
