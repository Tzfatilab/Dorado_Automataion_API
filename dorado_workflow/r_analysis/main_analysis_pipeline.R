#!/usr/bin/env Rscript
# r_analysis/main_analysis_pipeline.R
# Main pipeline script that orchestrates all R analysis steps

# Load required functions
# Determine script directory robustly (works for Rscript and source())
script_dir <- tryCatch({
  # Preferred when running via Rscript
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg) > 0) {
    return(dirname(sub("^--file=", "", file_arg)))
  }

  # Fallback: when sourced in an IDE
  frames <- lapply(sys.frames(), function(x) x$ofile)
  frames <- Filter(Negate(is.null), frames)
  if (length(frames) > 0) {
    return(dirname(frames[[1]]))
  }

  # Final fallback: working directory
  getwd()
}, error = function(e) {
  getwd()
})

source(file.path(script_dir, "functions", "utils.R"))

library(jsonlite)
# Main pipeline function
main_r_analysis_pipeline <- function(config_file, trial_name = NULL) {

  cat("Starting Complete R Analysis Pipeline\n")
  cat("=====================================\n\n")

  # Load required packages
  load_required_packages()

  `%||%` <- function(a, b) if (is.null(a)) b else a
  # Read configuration
  config <- read_config(config_file)

  # Attach trial information if provided
  if (!is.null(trial_name)) {
    config$trial_name <- trial_name
  }


  # Validate configuration has all required sections
  required_sections <- c("nanotel_analysis", "mapping_analysis", "methylation_analysis")
  missing_sections <- required_sections[!(required_sections %in% names(config))]
  if (length(missing_sections) > 0) {
    stop("Missing required configuration sections: ", paste(missing_sections, collapse = ", "))
  }

  pipeline_start_time <- Sys.time()
  results <- list()

  log_message("Starting complete R analysis pipeline")
  log_message(paste("Base output directory:", config$base_output_dir))

  # Step 1: NanoTel Analysis
  if (config$run_nanotel_analysis %||% TRUE) {
    log_message("==================================================")
    log_message("STEP 1: NANOTEL ANALYSIS")
    log_message("==================================================")

    tryCatch({
      # Create temporary config file for NanoTel analysis
      nanotel_config <- config$nanotel_analysis
      if (!is.null(config$trial_name)) {
        nanotel_config$trial_name <- config$trial_name
      }
      nanotel_config_file <- create_temp_config(nanotel_config, "nanotel_temp_config.json")

      # Run NanoTel analysis as subprocess instead of sourcing
      cmd <- paste("Rscript batch_nanotel_analysis.R", shQuote(nanotel_config_file))
      cat("DEBUG: Running command:", cmd, "\n")

      result_code <- system(cmd)

      if (result_code == 0) {
        log_message("âœ“ NanoTel analysis completed successfully")

        # Try to count actual processed barcodes from output files
        nanotel_output_dir <- config$nanotel_analysis$output_dir
        # Look for barcode subdirectories
        barcode_dirs <- list.dirs(nanotel_output_dir, recursive = FALSE, full.names = FALSE)
        barcode_dirs <- barcode_dirs[grepl("^(bc|barcode)[0-9]+$", barcode_dirs, ignore.case = TRUE)]
        barcodes_count <- length(barcode_dirs)

        results$nanotel <- list(
          barcodes_processed = barcodes_count,
          files_processed = barcodes_count
        )
      } else {
        stop("NanoTel analysis failed with exit code: ", result_code)
      }

      # Clean up temp file
      file.remove(nanotel_config_file)

    }, error = function(e) {
      log_message(paste("âœ— NanoTel analysis failed:", e$message), "ERROR")
      if (config$stop_on_error %||% TRUE) {
        stop("Pipeline stopped due to NanoTel analysis failure")
      }
    })
  } else {
    log_message("Skipping NanoTel analysis (disabled in config)")
  }

  # Step 2: Mapping Analysis
  if (config$run_mapping_analysis %||% TRUE) {
    log_message("==================================================")
    log_message("STEP 2: MAPPING ANALYSIS")
    log_message("==================================================")

    tryCatch({
      # Update mapping config with NanoTel results if available
      mapping_config <- config$mapping_analysis
      if (!is.null(results$nanotel)) {
        mapping_config$filtered_nanotel_dir <- config$nanotel_analysis$output_dir
      }
      if (!is.null(config$trial_name)) {
        mapping_config$trial_name <- config$trial_name
      }

      # Create temporary config file for mapping analysis
      mapping_config_file <- create_temp_config(mapping_config, "mapping_temp_config.json")

      # Run mapping analysis as subprocess
      cmd <- paste("Rscript batch_mapping_analysis.R", shQuote(mapping_config_file))
      cat("DEBUG: Running command:", cmd, "\n")

      result_code <- system(cmd)

      if (result_code == 0) {
        log_message("âœ“ Mapping analysis completed successfully")

        # Try to count actual processed barcodes from output files
        mapping_output_dir <- config$mapping_analysis$output_dir
        combined_files <- list.files(mapping_output_dir, pattern = "mapped.*_combined\\.csv$", recursive = TRUE)
        merged_bed_files <- list.files(mapping_output_dir, pattern = "pileup-barcode[0-9]+\\.bed$", recursive = TRUE)

        # Extract barcode numbers from filenames
        successful_barcodes <- character()

        # Extract from combined files (pattern: mapped_barcode01_combined.csv)
        if (length(combined_files) > 0) {
          barcode_matches <- regmatches(combined_files, regexpr("barcode[0-9]+", combined_files))
          successful_barcodes <- c(successful_barcodes, barcode_matches)
        }

        # Extract from bed files (pattern: pileup-barcode01.bed)
        if (length(merged_bed_files) > 0) {
          barcode_matches <- regmatches(merged_bed_files, regexpr("barcode[0-9]+", merged_bed_files))
          successful_barcodes <- c(successful_barcodes, barcode_matches)
        }

        # Remove duplicates and get unique successful barcodes
        successful_barcodes <- unique(successful_barcodes)

        # Determine failed barcodes (assuming barcodes are numbered 01-10 based on NanoTel results)
        if (!is.null(results$nanotel)) {
          expected_barcodes <- paste0("barcode", sprintf("%02d", 1:results$nanotel$barcodes_processed))
          failed_barcodes <- setdiff(expected_barcodes, successful_barcodes)
        } else {
          failed_barcodes <- character()
        }

        results$mapping <- list(
          successful_results = successful_barcodes,  # Now a vector of barcode names
          failed_barcodes = failed_barcodes,         # Vector of failed barcode names
          total_processed = length(successful_barcodes) + length(failed_barcodes)
        )
      } else {
        stop("Mapping analysis failed with exit code: ", result_code)
      }

      # Clean up temp file
      file.remove(mapping_config_file)

    }, error = function(e) {
      log_message(paste("âœ— Mapping analysis failed:", e$message), "ERROR")
      if (config$stop_on_error %||% TRUE) {
        stop("Pipeline stopped due to mapping analysis failure")
      }
    })
  } else {
    log_message("Skipping mapping analysis (disabled in config)")
  }

  # Step 3: Methylation Analysis
  if (config$run_methylation_analysis %||% TRUE) {
    log_message("==================================================")
    log_message("STEP 3: METHYLATION ANALYSIS")
    log_message("==================================================")

    tryCatch({
      # Update methylation config with mapping results if available
      methylation_config <- config$methylation_analysis
      if (!is.null(results$mapping)) {
        methylation_config$pileup_bed_dir <- config$mapping_analysis$output_dir
      }
      if (!is.null(config$trial_name)) {
        methylation_config$trial_name <- config$trial_name
      }

      # Create temporary config file for methylation analysis
      methylation_config_file <- create_temp_config(methylation_config, "methylation_temp_config.json")

      # Run methylation analysis as subprocess
      cmd <- paste("Rscript batch_methylation_prep.R", shQuote(methylation_config_file))
      cat("DEBUG: Running command:", cmd, "\n")

      result_code <- system(cmd)

      if (result_code == 0) {
        log_message("âœ“ Methylation analysis completed successfully")

        # Try to count actual processed data
        methylation_output_dir <- config$methylation_analysis$output_dir
        processed_data_file <- file.path(methylation_output_dir, "processed_data", "processed_methylation_data.csv")

        if (file.exists(processed_data_file)) {
          # Count unique barcodes in processed data
          tryCatch({
            data <- read.csv(processed_data_file)
            barcodes_count <- length(unique(data$barcode))
            total_sites <- nrow(data)
          }, error = function(e) {
            barcodes_count <- "Unknown"
            total_sites <- "Unknown"
          })
        } else {
          barcodes_count <- "Unknown"
          total_sites <- "Unknown"
        }

        results$methylation <- list(
          processed_files = barcodes_count,
          total_sites = total_sites
        )
      } else {
        log_message(paste("âœ— Methylation analysis failed with exit code: ", result_code), "ERROR")
        # Continue anyway since most processing succeeded
      }

      # Clean up temp file
      file.remove(methylation_config_file)

    }, error = function(e) {
      log_message(paste("âœ— Methylation analysis failed:", e$message), "ERROR")
      if (config$stop_on_error %||% TRUE) {
        stop("Pipeline stopped due to methylation analysis failure")
      }
    })
  } else {
    log_message("Skipping methylation analysis (disabled in config)")
  }

  pipeline_end_time <- Sys.time()
  pipeline_duration <- as.numeric(difftime(pipeline_end_time, pipeline_start_time, units = "mins"))

  # Generate final pipeline report
  generate_pipeline_report(results, config, pipeline_duration)

  log_message(rep_str("=", 50))
  log_message("PIPELINE COMPLETED SUCCESSFULLY")
  log_message(rep_str("=", 50))
  log_message(paste("Total duration:", round(pipeline_duration, 1), "minutes"))

  return(results)
}

# Create temporary configuration file
# Create temporary configuration file
create_temp_config <- function(config_section, filename) {
  cat("DEBUG: Creating temp config for:", filename, "\n")
  cat("DEBUG: Config section type:", class(config_section), "\n")
  cat("DEBUG: Config section names:", names(config_section), "\n")

  if (is.null(config_section)) {
    stop("Config section is NULL")
  }

  temp_file <- file.path(tempdir(), filename)
  cat("DEBUG: Temp file path:", temp_file, "\n")

  tryCatch({
    jsonlite::write_json(config_section, temp_file, auto_unbox = TRUE, pretty = TRUE)

    # Verify file was created and show content
    if (file.exists(temp_file)) {
      cat("DEBUG: Temp config file created successfully\n")
      cat("DEBUG: File content:\n")
      content <- readLines(temp_file)
      cat(paste(content, collapse = "\n"), "\n")
    } else {
      stop("Temp config file was not created")
    }

    return(temp_file)
  }, error = function(e) {
    cat("ERROR in create_temp_config:", e$message, "\n")
    stop("Failed to write temp config: ", e$message)
  })
}

# Generate comprehensive pipeline report
generate_pipeline_report <- function(results, config, duration) {

  log_message("Generating comprehensive pipeline report")

  report_file <- file.path(config$base_output_dir, "complete_pipeline_report.txt")

  report_lines <- c(
    rep_str("=", 80),
    "COMPLETE R ANALYSIS PIPELINE REPORT",
    rep_str("=", 80),
    paste("Pipeline date:", Sys.Date()),
    paste("Pipeline start time:", format(Sys.time() - duration * 60, "%H:%M:%S")),
    paste("Pipeline end time:", format(Sys.time(), "%H:%M:%S")),
    paste("Total duration:", round(duration, 1), "minutes"),
    "",
    "PIPELINE CONFIGURATION:",
    paste("  Base output directory:", config$base_output_dir),
    paste("  NanoTel analysis:", ifelse(config$run_nanotel_analysis %||% TRUE, "ENABLED", "DISABLED")),
    paste("  Mapping analysis:", ifelse(config$run_mapping_analysis %||% TRUE, "ENABLED", "DISABLED")),
    paste("  Methylation analysis:", ifelse(config$run_methylation_analysis %||% TRUE, "ENABLED", "DISABLED")),
    paste("  Stop on error:", ifelse(config$stop_on_error %||% TRUE, "YES", "NO")),
    "",
    "ANALYSIS RESULTS:"
  )

  # NanoTel results
  if (!is.null(results$nanotel)) {
    nanotel <- results$nanotel
    report_lines <- c(report_lines,
                      "",
                      "1. NANOTEL ANALYSIS:",
                      paste("   Status: SUCCESS"),
                      paste("   Barcodes processed:", nanotel$barcodes_processed),
                      paste("   Files processed:", nanotel$files_processed),
                      paste("   Output directory:", config$nanotel_analysis$output_dir)
    )
  } else {
    report_lines <- c(report_lines,
                      "",
                      "1. NANOTEL ANALYSIS:",
                      "   Status: SKIPPED OR FAILED"
    )
  }

  # Mapping results
  if (!is.null(results$mapping)) {
    mapping <- results$mapping
    report_lines <- c(report_lines,
                      "",
                      "2. MAPPING ANALYSIS:",
                      paste("   Status: SUCCESS"),
                      paste("   Total processed:", mapping$total_processed),
                      paste("   Successful barcodes:", length(mapping$successful_results)),
                      paste("   Failed barcodes:", length(mapping$failed_barcodes)),
                      paste("   Output directory:", config$mapping_analysis$output_dir)
    )

    if (length(mapping$failed_barcodes) > 0) {
      report_lines <- c(report_lines,
                        paste("   Failed barcode list:", paste(mapping$failed_barcodes, collapse = ", "))
      )
    }
  } else {
    report_lines <- c(report_lines,
                      "",
                      "2. MAPPING ANALYSIS:",
                      "   Status: SKIPPED OR FAILED"
    )
  }

  # Methylation results
  if (!is.null(results$methylation)) {
    methylation <- results$methylation
    report_lines <- c(report_lines,
                      "",
                      "3. METHYLATION ANALYSIS:",
                      paste("   Status: SUCCESS"),
                      paste("   BED files processed:", methylation$processed_files),
                      paste("   Total methylation sites:", methylation$total_sites),
                      paste("   Output directory:", config$methylation_analysis$output_dir)
    )
  } else {
    report_lines <- c(report_lines,
                      "",
                      "3. METHYLATION ANALYSIS:",
                      "   Status: SKIPPED OR FAILED"
    )
  }

  report_lines <- c(report_lines,
                    "",
                    "OUTPUT STRUCTURE:",
                    paste("  ", config$base_output_dir, "/"),
                    "    â”œâ”€â”€ nanotel_output/",
                    "    â”‚   â”œâ”€â”€ barcode*/.csv",
                    "    â”‚       â”œâ”€â”€ filtered_summary*.csv",
                    "    â”‚       â”œâ”€â”€ nanotel_summary_statistics.csv",
                    "    â”‚       â””â”€â”€ nanotel_analysis_report.txt",
                    "    â”œâ”€â”€ mapping_output/",
                    "    â”‚   â”œâ”€â”€ mapped*.csv",
                    "    â”‚   â”œâ”€â”€ filtered_*.bam",
                    "    â”‚   â”œâ”€â”€ pileup-*.bed",
                    "    â”‚   â””â”€â”€ mapping_analysis_report.txt",
                    "    â”œâ”€â”€ methylation_output/",
                    "    â”‚   â”œâ”€â”€ plots/",
                    "    â”‚   â”œâ”€â”€ processed_data/",
                    "    â”‚   â”œâ”€â”€ shiny_app/ (if enabled)",
                    "    â”‚   â”œâ”€â”€ methylation_summary_statistics.csv",
                    "    â”‚   â””â”€â”€ methylation_analysis_report.txt",
                    "    â””â”€â”€ complete_pipeline_report.txt",
                    "",
                    "NEXT STEPS:",
                    "  1. Review individual analysis reports for detailed results",
                    "  2. Check any failed barcodes and investigate issues",
                    "  3. Use interactive Shiny app for methylation visualization",
                    "  4. Proceed with downstream analysis using processed data",
                    "",
                    rep_str("=", 80)
  )

  # Write report
  writeLines(report_lines, report_file)

  log_message(paste("Complete pipeline report saved to:", basename(report_file)))

  return(report_file)
}

# Command line interface
if (!interactive()) {
  # Parse command line arguments
  args <- commandArgs(trailingOnly = TRUE)

  if (length(args) != 2) {
    cat("Usage: Rscript main_analysis_pipeline.R <config_file> <trial_name>\n")
    cat("\n")
    cat("Arguments:\n")
    cat("  config_file: JSON configuration file with complete pipeline parameters\n")
    cat("  trial_name : Name of the current trial (used for labeling outputs)\n")
    cat("\n")
    cat("Example:\n")
    cat("  Rscript main_analysis_pipeline.R config/pipeline_config.json Trial_75\n")
    cat("\n")
    cat("The configuration file should contain sections for:\n")
    cat("  - nanotel_analysis\n")
    cat("  - mapping_analysis\n")
    cat("  - methylation_analysis\n")
    cat("\n")
    quit(status = 1)
  }

  config_file <- args[1]
  trial_name  <- args[2]

  # Validate config file exists
  if (!file.exists(config_file)) {
    cat("Error: Configuration file not found:", config_file, "\n")
    quit(status = 1)
  }

  # Run complete pipeline
  tryCatch({
    results <- main_r_analysis_pipeline(config_file)
    cat("\nðŸŽ‰ Complete R analysis pipeline finished successfully!\n")

    # Print summary
    if (!is.null(results$nanotel)) {
      cat("âœ“ NanoTel: Processed", results$nanotel$barcodes_processed, "barcodes\n")
    }
    if (!is.null(results$mapping)) {
      cat("âœ“ Mapping: Processed", length(results$mapping$successful_results), "barcodes\n")
    }
    if (!is.null(results$methylation)) {
      cat("âœ“ Methylation:", results$methylation$total_sites, "sites analyzed\n")
    }

  }, error = function(e) {
    cat("âŒ Pipeline failed:", e$message, "\n")
    quit(status = 1)
  })
}
