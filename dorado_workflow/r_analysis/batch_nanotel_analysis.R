#!/usr/bin/env Rscript
# r_analysis/batch_nanotel_analysis.R
# Batch processing script for NanoTel analysis

# Load required functions
# Get the directory where this script is located
script_dir <- tryCatch({
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg) > 0) {
    dirname(sub("^--file=", "", file_arg))
  } else {
    getwd()
  }
}, error = function(e) {
  getwd()
})
source(file.path(script_dir, "functions", "utils.R"))
source(file.path(script_dir, "functions", "nanotel_functions.R"))

# Main function for batch NanoTel processing
main_nanotel_analysis <- function(config_file) {

  cat("Starting NanoTel Batch Analysis\n")
  cat("================================\n\n")

  cat("DEBUG: Received config file:", config_file, "\n")
  cat("DEBUG: Config file exists:", file.exists(config_file), "\n")
  # Load required packages
  load_required_packages()

  # Read configuration
  config <- read_config(config_file)

  # Validate configuration
  required_params <- c("input_dir", "output_dir")
  missing_params <- required_params[!(required_params %in% names(config))]
  if (length(missing_params) > 0) {
    stop("Missing required configuration parameters: ", paste(missing_params, collapse = ", "))
  }

  # Set default parameters
  density_threshold <- config$density_threshold %||% 0.75
  max_telomere_start <- config$max_telomere_start %||% 150

  log_message("Configuration loaded successfully")
  log_message(paste("Input directory:", config$input_dir))
  log_message(paste("Output directory:", config$output_dir))
  log_message(paste("Density threshold:", density_threshold))
  log_message(paste("Max telomere start:", max_telomere_start))

  # Find NanoTel summary files
  nanotel_files <- find_nanotel_summary_files(config$input_dir)

  if (length(nanotel_files) == 0) {
    stop("No NanoTel summary files found in input directory")
  }

  log_message(paste("Found", length(nanotel_files), "NanoTel files to process"))

  # Process all files
  processed_data <- batch_process_nanotel_files(
    input_files = nanotel_files,
    output_dir = config$output_dir,
    density_threshold = density_threshold,
    max_telomere_start = max_telomere_start
  )

  if (length(processed_data) == 0) {
    warning("No data was successfully processed")
    return(invisible(NULL))
  }

  # Generate summary statistics
  summary_output_file <- file.path(config$output_dir, "nanotel_summary_statistics.csv")
  summary_stats <- generate_nanotel_summary_stats(processed_data, summary_output_file)

  # Create analysis report
  report_file <- file.path(config$output_dir, "nanotel_analysis_report.txt")
  generate_nanotel_report(processed_data, summary_stats, report_file, config)

  log_message("NanoTel batch analysis completed successfully!")

  return(list(
    processed_data = processed_data,
    summary_stats = summary_stats,
    files_processed = length(nanotel_files),
    barcodes_processed = length(processed_data)
  ))
}

# Generate detailed analysis report
generate_nanotel_report <- function(processed_data, summary_stats, output_file, config) {

  log_message("Generating NanoTel analysis report")

  total_reads <- sum(sapply(processed_data, nrow))

  report_lines <- c(
    rep_str("=", 80),
    "NANOTEL BATCH ANALYSIS REPORT",
    rep_str("=", 80),
    paste("Analysis date:", Sys.Date()),
    paste("Analysis time:", format(Sys.time(), "%H:%M:%S")),
    "",
    "ANALYSIS PARAMETERS:",
    paste("  Input directory:", config$input_dir),
    paste("  Output directory:", config$output_dir),
    paste("  Density threshold:", config$density_threshold %||% 0.75),
    paste("  Max telomere start:", config$max_telomere_start %||% 150),
    "",
    "PROCESSING RESULTS:",
    paste("  Total barcodes processed:", length(processed_data)),
    paste("  Total reads after filtering:", total_reads),
    paste("  Average reads per barcode:", round(total_reads / length(processed_data), 1)),
    "",
    "BARCODE DETAILS:"
  )

  # Add individual barcode information
  for (barcode in names(processed_data)) {
    data <- processed_data[[barcode]]
    report_lines <- c(report_lines,
                      paste("  ", toupper(barcode), ":"),
                      paste("    Reads:", nrow(data)),
                      paste("    Mean telomere length:", round(mean(data$Telomere_length_mismatch, na.rm = TRUE), 1), "bp"),
                      paste("    Mean read length:", round(mean(data$sequence_length, na.rm = TRUE), 1), "bp"),
                      paste("    Mean density:", round(mean(data$telo_density_mismatch, na.rm = TRUE), 3)),
                      ""
    )
  }

  report_lines <- c(report_lines,
                    "SUMMARY STATISTICS:",
                    ""
  )

  # Add summary table
  if (nrow(summary_stats) > 0) {
    for (i in 1:nrow(summary_stats)) {
      row <- summary_stats[i, ]
      report_lines <- c(report_lines,
                        paste("  ", toupper(row$barcode), ":"),
                        paste("    Telomeres:", row$amount_of_telomeres),
                        paste("    Median length:", row$median_telomere_length, "bp"),
                        paste("    Below 2kb:", row$below_2kb_pct, "%"),
                        paste("    Median read length:", row$med_read_len, "bp"),
                        paste("    Mean density:", row$mean_density),
                        ""
      )
    }
  }

  report_lines <- c(report_lines,
                    "OUTPUT FILES:",
                    paste("  - Filtered summary files: filtered_summary*.csv"),
                    paste("  - Summary statistics: nanotel_summary_statistics.csv"),
                    paste("  - Analysis report: nanotel_analysis_report.txt"),
                    "",
                    "NEXT STEPS:",
                    "  1. Review filtered summary files for quality",
                    "  2. Proceed with mapping analysis using filtered data",
                    "  3. Check summary statistics for outliers",
                    "",
                    rep_str("=", 80)
  )

  # Write report
  writeLines(report_lines, output_file)

  log_message(paste("Analysis report saved to:", basename(output_file)))

  return(output_file)
}

# Command line interface
if (!interactive()) {
  # Parse command line arguments
  args <- commandArgs(trailingOnly = TRUE)

  if (length(args) != 1) {
    cat("Usage: Rscript batch_nanotel_analysis.R <config_file>\n")
    cat("\n")
    cat("Arguments:\n")
    cat("  config_file: JSON configuration file with analysis parameters\n")
    cat("\n")
    cat("Example:\n")
    cat("  Rscript batch_nanotel_analysis.R config/nanotel_config.json\n")
    quit(status = 1)
  }

  config_file <- args[1]

  # Validate config file exists
  if (!file.exists(config_file)) {
    cat("Error: Configuration file not found:", config_file, "\n")
    quit(status = 1)
  }

  # Run analysis
  tryCatch({
    result <- main_nanotel_analysis(config_file)
    cat("\nAnalysis completed successfully!\n")
    cat("Processed", result$barcodes_processed, "barcodes\n")
  }, error = function(e) {
    cat("Error during analysis:", e$message, "\n")
    quit(status = 1)
  })
}
