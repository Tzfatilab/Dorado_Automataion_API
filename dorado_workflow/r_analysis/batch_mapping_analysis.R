#!/usr/bin/env Rscript
# r_analysis/batch_mapping_analysis.R
# Batch processing script for alignment mapping and BAM filtering

# Load required functions
# Get the directory where this script is located
script_dir <- tryCatch({
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg) > 0) {
    script_file <- sub("^--file=", "", file_arg[[1]])
    dirname(gsub("~+~", " ", script_file, fixed = TRUE))
  } else {
    getwd()
  }
}, error = function(e) {
  getwd()
})
source(file.path(script_dir, "functions", "utils.R"))
source(file.path(script_dir, "functions", "mapping_functions.R"))

# Process a single barcode with multiple BAM files
# Inputs: barcode_configs_list (Per-BAM configurations belonging to one barcode)
# Outputs: Combined per-barcode mapping results and filtered output paths.
process_barcode_multiple_bams <- function(barcode_configs_list) {
  cat("DEBUG: ENTERING process_barcode_multiple_bams function\n")
  # All configs in the list should be for the same barcode
  barcode_name <- toupper(normalize_barcode_name(barcode_configs_list[[1]]$barcode_name))
  log_message(paste("Processing", length(barcode_configs_list), "BAM files for barcode:", barcode_name))

  # All BAM fragments for this barcode contribute to one output directory.
  barcode_output_dir <- file.path(barcode_configs_list[[1]]$output_dir, barcode_name)
  cat("DEBUG: About to create directory:", barcode_output_dir, "\n")
  cat("DEBUG: Directory exists before creation:", dir.exists(barcode_output_dir), "\n")
  ensure_directory_exists(barcode_output_dir)
  cat("DEBUG: Directory exists after creation:", dir.exists(barcode_output_dir), "\n")
  all_mapped_data <- list()
  all_filtered_bam_paths <- character()
  all_pileup_bed_paths <- character()
  total_reads <- 0
  processing_errors <- character()

  # Process each BAM file for this barcode
  for (i in seq_along(barcode_configs_list)) {
    config <- barcode_configs_list[[i]]

    log_message(paste("Processing BAM file", i, "of", length(barcode_configs_list), "for", barcode_name))
    log_message(paste("BAM file:", basename(config$bam_file_path)))

    tryCatch({
      # Step 1: Process mapping for this BAM file
      mapping_result <- process_barcode_mapping(
        alignment_summary_path = config$alignment_summary_path,
        filtered_nanotel_path = config$filtered_nanotel_path,
        bam_file_path = config$bam_file_path,
        output_dir = barcode_output_dir,
        barcode_name = paste0(barcode_name, "_bam", i),  # Unique name for this BAM
        min_mapq = config$min_mapq,
        head_max_start = config$head_max_start,
        tail_min_end = config$tail_min_end
      )

      if (length(mapping_result$filtered_ids) == 0) {
        log_message(paste("No reads remain after mapping filters for BAM file", i, "of", barcode_name), "WARNING")
        next
      }

      # Step 2: Create filtered BAM for this file
      filtered_bam_path <- file.path(barcode_output_dir,
                                     paste0("filtered_", barcode_name, "_bam", i, ".bam"))

      create_filtered_bam(
        filtered_read_ids = mapping_result$filtered_ids,
        input_bam_path = config$bam_file_path,
        output_bam_path = filtered_bam_path
      )

      # Step 3: Run methylation pileup only when methylation analysis is enabled.
      pileup_result <- NULL
      if (config$run_modkit_pileup %||% FALSE) {
        pileup_bed_path <- file.path(barcode_output_dir,
                                     paste0("pileup-", tolower(barcode_name), "_bam", i, ".bed"))

        pileup_result <- run_modkit_pileup(
          filtered_bam_path = filtered_bam_path,
          output_bed_path = pileup_bed_path,
          filter_threshold_c = config$filter_threshold_c,
          filter_threshold_g = config$filter_threshold_g,
          mod_threshold_m = config$mod_threshold_m,
          timeout_seconds = get_modkit_timeout_seconds(
            length(mapping_result$filtered_ids),
            config$modkit_timeout_seconds %||% 900
          )
        )
      }

      # Store results
      all_mapped_data[[i]] <- mapping_result$mapped_data
      all_filtered_bam_paths <- c(all_filtered_bam_paths, filtered_bam_path)
      if (!is.null(pileup_result)) {
        all_pileup_bed_paths <- c(all_pileup_bed_paths, pileup_result)
      }
      total_reads <- total_reads + length(mapping_result$filtered_ids)

      log_message(paste("Successfully processed BAM file", i, "for", barcode_name))

    }, error = function(e) {
      processing_errors <<- c(processing_errors, e$message)
      log_message(paste("Error processing BAM file", i, "for", barcode_name, ":", e$message), "ERROR")
    })
  }

  if (length(all_mapped_data) == 0) {
    if (length(processing_errors) > 0) {
      log_message(paste("No BAM files could be processed for", barcode_name), "ERROR")
      return(NULL)
    }
    log_message(paste("Skipping", barcode_name, "- no reads remain after filtering."), "WARNING")
    return(list(barcode=barcode_name, status="empty", read_count=0L))
  }

  # Step 4: Combine all mapped data for this barcode
  combined_mapped_data <- unique(do.call(rbind, all_mapped_data))
  total_reads <- length(unique(combined_mapped_data$read_id_clean))
  combined_output_file <- file.path(barcode_output_dir,
                                    paste0("mapped", barcode_name, "_combined.csv"))
  safe_write_csv(combined_mapped_data, combined_output_file)

  # Step 5: Merge pileup BED files for this barcode
  if (length(all_pileup_bed_paths) > 1) {
    merged_bed_path <- merge_pileup_bed_files(all_pileup_bed_paths, barcode_name,
                                              barcode_output_dir)
  } else if (length(all_pileup_bed_paths) == 1) {
    # Rename single BED file to standard name
    merged_bed_path <- file.path(barcode_output_dir,
                                 paste0("pileup-", tolower(barcode_name), ".bed"))
    file.copy(all_pileup_bed_paths[1], merged_bed_path, overwrite = TRUE)
  } else {
    merged_bed_path <- NA
    log_message(
      paste("No methylation BED file produced for", barcode_name),
      "WARNING"
    )
  }

  log_message(paste("Completed processing for", barcode_name, "- Total reads:", total_reads))

  return(list(
    barcode = barcode_name,
    mapped_file = combined_output_file,
    filtered_bams = all_filtered_bam_paths,
    individual_beds = all_pileup_bed_paths,
    merged_bed = merged_bed_path,
    read_count = total_reads,
    bam_files_processed = length(all_mapped_data)
  ))
}

# Group all BAM fragments by barcode before producing combined mapping results.
# Inputs: config_file (Saved JSON configuration path)
# Outputs: Mapping-stage results and saved per-barcode mapping artifacts.
main_mapping_analysis <- function(config_file) {

  cat("Starting Mapping Batch Analysis\n")
  cat("===============================\n\n")

  # Load required packages
  load_required_packages()

  # Read configuration
  config <- read_config(config_file)

  # Validate configuration
  required_params <- c("alignment_summary_path", "filtered_nanotel_dir",
                       "bam_dir", "output_dir")
  missing_params <- required_params[!(required_params %in% names(config))]
  if (length(missing_params) > 0) {
    stop("Missing required configuration parameters: ", paste(missing_params, collapse = ", "))
  }

  # Set default parameters
  min_mapq <- config$min_mapq %||% 10
  head_max_start <- config$head_max_start %||% 5000
  tail_min_end <- config$tail_min_end %||% 35000
  filter_threshold_c <- config$filter_threshold_c %||% 0.75
  filter_threshold_g <- config$filter_threshold_g %||% 0.75
  mod_threshold_m <- config$mod_threshold_m %||% 0.75
  modkit_timeout_seconds <- config$modkit_timeout_seconds %||% 900
  run_modkit_pileup <- config$run_modkit_pileup %||% FALSE

  log_message("Configuration loaded successfully")
  log_message(paste("Alignment summary:", config$alignment_summary_path))
  log_message(paste("Filtered NanoTel dir:", config$filtered_nanotel_dir))
  log_message(paste("BAM directory:", config$bam_dir))
  log_message(paste("Output directory:", config$output_dir))

  # Find filtered NanoTel files
  nanotel_files <- find_files_by_pattern(config$filtered_nanotel_dir,
                                         "filtered_summary.*\\.csv$", recursive = TRUE)

  if (length(nanotel_files) == 0) {
    log_message(
      paste(
        "No filtered NanoTel files found in:",
        config$filtered_nanotel_dir,
        "- mapping will be reported as empty."
      ),
      "WARNING"
    )
    write_empty_mapping_report(
      config,
      reason_lines = c(
        "No filtered NanoTel summary files were produced.",
        "NanoTel filtering may have removed all reads for this run."
      ),
      failed_barcodes = character()
    )
    return(list(
      successful_results = list(),
      failed_barcodes = character(),
      total_processed = 0
    ))
  }

  # Find BAM files
  bam_info <- find_barcode_bam_files(config$bam_dir)

  if (nrow(bam_info) == 0) {
    stop("No barcode BAM files found in: ", config$bam_dir)
  }

  log_message(paste("Found", length(nanotel_files), "filtered NanoTel files"))
  log_message(paste("Found", nrow(bam_info), "BAM files"))

  # Create grouped barcode configurations (multiple BAM files per barcode)
  grouped_barcode_configs <- create_barcode_configs_grouped(
    nanotel_files = nanotel_files,
    bam_info = bam_info,
    alignment_summary_path = config$alignment_summary_path,
    output_dir = config$output_dir,
    min_mapq = min_mapq,
    head_max_start = head_max_start,
    tail_min_end = tail_min_end,
    filter_threshold_c = filter_threshold_c,
    filter_threshold_g = filter_threshold_g,
    mod_threshold_m = mod_threshold_m,
    modkit_timeout_seconds = modkit_timeout_seconds,
    run_modkit_pileup = run_modkit_pileup
  )

  if (length(grouped_barcode_configs) == 0) {
    stop("No matching barcode configurations found")
  }

  log_message(paste("Created configurations for", length(grouped_barcode_configs), "barcodes"))

  # Process each barcode (with multiple BAM files)
  results <- list()
  failed_barcodes <- character()
  skipped_barcodes <- character()

  for (i in seq_along(grouped_barcode_configs)) {
    barcode_name <- names(grouped_barcode_configs)[i]
    barcode_configs_list <- grouped_barcode_configs[[i]]

    show_progress(i, length(grouped_barcode_configs), "Processing barcodes")

    tryCatch({
      result <- process_barcode_multiple_bams(barcode_configs_list)
      if (!is.null(result) && identical(result$status, "empty")) {
        skipped_barcodes <- c(skipped_barcodes, barcode_name)
      } else if (!is.null(result)) {
        results[[barcode_name]] <- result
      } else {
        failed_barcodes <- c(failed_barcodes, barcode_name)
      }
    }, error = function(e) {
      log_message(paste("Error processing", barcode_name, ":", e$message), "ERROR")
      failed_barcodes <- c(failed_barcodes, barcode_name)
    })
  }

  ensure_directory_exists(config$output_dir)
  jsonlite::write_json(list(successful_barcodes=names(results) %||% character(),
                           skipped_barcodes=skipped_barcodes, failed_barcodes=failed_barcodes),
                      file.path(config$output_dir, "mapping_status.json"), auto_unbox=FALSE)
  log_message(paste("Processing complete. Success:", length(results),
                    "Skipped (no reads):", length(skipped_barcodes), "Failed:", length(failed_barcodes)))
  if (length(skipped_barcodes) > 0) {
    log_message(paste("Skipped barcodes (no reads):", paste(skipped_barcodes, collapse=", ")), "WARNING")
  }

  if (length(failed_barcodes) > 0) {
    log_message(paste("Failed barcodes:", paste(failed_barcodes, collapse = ", ")), "WARNING")
  }

  if (length(results) == 0) {
    log_message(
      paste(
        "Mapping analysis produced no mapped barcodes.",
        "All NanoTel-filtered reads were unmapped or failed mapping filters."
      ),
      "WARNING"
    )
    write_empty_mapping_report(
      config,
      reason_lines = c(
        "No mapped barcodes were produced.",
        "All NanoTel-filtered reads were unmapped, did not match alignment read IDs,",
        "or failed the configured mapping filters."
      ),
      failed_barcodes = failed_barcodes,
      skipped_barcodes = skipped_barcodes
    )

    return(list(
      successful_results = results,
      failed_barcodes = failed_barcodes,
      skipped_barcodes = skipped_barcodes,
      total_processed = length(grouped_barcode_configs)
    ))
  }

  # Generate summary report
  if (length(results) > 0) {
    report_file <- file.path(config$output_dir, "mapping_analysis_report.txt")
    generate_mapping_report_multiple_bams(results, failed_barcodes, report_file, config, skipped_barcodes)
  }

  log_message("Mapping batch analysis completed!")

  return(list(
    successful_results = results,
    failed_barcodes = failed_barcodes,
    skipped_barcodes = skipped_barcodes,
    total_processed = length(grouped_barcode_configs)
  ))
}

# Inputs: config (Configuration values to read or update); reason_lines (Explanations for an empty
# mapping output); failed_barcodes (Barcode labels whose processing failed)
# Outputs: Writes a mapping report explaining why no records were produced.
write_empty_mapping_report <- function(config, reason_lines, failed_barcodes = character(), skipped_barcodes = character()) {
  ensure_directory_exists(config$output_dir)
  report_file <- file.path(config$output_dir, "mapping_analysis_report.txt")
  failed_text <- if (length(failed_barcodes) > 0) {
    paste(failed_barcodes, collapse = ", ")
  } else {
    "none"
  }

  report_lines <- c(
    rep_str("=", 80),
    "MAPPING BATCH ANALYSIS REPORT",
    rep_str("=", 80),
    paste("Analysis date:", Sys.Date()),
    paste("Analysis time:", format(Sys.time(), "%H:%M:%S")),
    "",
    reason_lines,
    "",
    paste("Failed barcodes:", failed_text),
    paste("Skipped barcodes (no reads):", paste(skipped_barcodes, collapse=", ")),
    paste("Alignment summary:", config$alignment_summary_path),
    paste("Filtered NanoTel dir:", config$filtered_nanotel_dir),
    paste("BAM directory:", config$bam_dir),
    rep_str("=", 80)
  )
  writeLines(report_lines, report_file)
  log_message(paste("Empty mapping report saved to:", report_file))
  invisible(report_file)
}

# Updated report generation for multiple BAM files
# Inputs: results (Results directory or collected processing results); failed_barcodes (Barcode
# labels whose processing failed); output_file (Output file); config (Configuration values to read
# or update)
# Outputs: Writes the run mapping summary for all barcode/BAM fragments.
generate_mapping_report_multiple_bams <- function(results, failed_barcodes, output_file, config, skipped_barcodes = character()) {

  log_message("Generating mapping analysis report for multiple BAM files")

  total_reads <- sum(sapply(results, function(x) x$read_count))
  total_bam_files <- sum(sapply(results, function(x) x$bam_files_processed))

  report_lines <- c(
    rep_str("=", 80),
    "MAPPING BATCH ANALYSIS REPORT (Multiple BAM Files per Barcode)",
    rep_str("=", 80),
    paste("Analysis date:", Sys.Date()),
    paste("Analysis time:", format(Sys.time(), "%H:%M:%S")),
    "",
    "ANALYSIS PARAMETERS:",
    paste("  Alignment summary:", config$alignment_summary_path),
    paste("  BAM directory:", config$bam_dir),
    paste("  Output directory:", config$output_dir),
    paste("  Min MAPQ:", config$min_mapq %||% 10),
    paste("  Head max start:", config$head_max_start %||% 5000),
    paste("  Tail min end:", config$tail_min_end %||% 35000),
    paste("  Methylation filter C:", config$filter_threshold_c %||% 0.75),
    paste("  Methylation filter G:", config$filter_threshold_g %||% 0.75),
    paste("  Modification threshold:", config$mod_threshold_m %||% 0.75),
    "",
    "PROCESSING RESULTS:",
    paste("  Total barcodes attempted:", length(results) + length(failed_barcodes) + length(skipped_barcodes)),
    paste("  Successful barcodes:", length(results)),
    paste("  Skipped barcodes (no reads):", length(skipped_barcodes)),
    paste("  Skipped barcode list:", paste(skipped_barcodes, collapse=", ")),
    paste("  Failed barcodes:", length(failed_barcodes)),
    paste("  Total BAM files processed:", total_bam_files),
    paste("  Total telomeric reads processed:", total_reads),
    ""
  )

  if (length(failed_barcodes) > 0) {
    report_lines <- c(report_lines,
                      "FAILED BARCODES:",
                      paste("  ", failed_barcodes, collapse = "\n"),
                      ""
    )
  }

  report_lines <- c(report_lines, "SUCCESSFUL BARCODES:")

  # Add successful barcode details
  for (barcode in names(results)) {
    result <- results[[barcode]]
    merged_bed_label <- if (is.na(result$merged_bed)) {
      "not generated"
    } else {
      basename(result$merged_bed)
    }
    report_lines <- c(report_lines,
                      paste("  ", result$barcode, ":"),
                      paste("    BAM files processed:", result$bam_files_processed),
                      paste("    Telomeric reads:", result$read_count),
                      paste("    Combined mapped file:", basename(result$mapped_file)),
                      paste("    Individual filtered BAMs:", length(result$filtered_bams)),
                      paste("    Individual BED files:", length(result$individual_beds)),
                      paste("    Merged BED file:", merged_bed_label),
                      ""
    )
  }

  output_lines <- c(
    "OUTPUT FILES GENERATED:",
    "  For each barcode:",
    "    - mapped<BARCODE>_combined.csv (combined alignment + NanoTel data)",
    "    - filtered_<BARCODE>_bam1.bam, bam2.bam, etc. (individual filtered BAMs)"
  )
  next_steps <- c(
    "NEXT STEPS:",
    "  1. Review combined mapped CSV files for data quality",
    "  2. Investigate any failed barcodes"
  )

  if (config$run_modkit_pileup %||% FALSE) {
    output_lines <- c(
      output_lines,
      "    - pileup-<barcode>_bam1.bed, bam2.bed, etc. (individual methylation data when available)",
      "    - pileup-<barcode>.bed (merged methylation data when available)"
    )
    next_steps <- c(
      "NEXT STEPS:",
      "  1. Review combined mapped CSV files for data quality",
      "  2. Check merged BED files for methylation analysis",
      "  3. Investigate any failed barcodes"
    )
  }

  report_lines <- c(report_lines, output_lines, "", next_steps, "", rep_str("=", 80))

  # Write report
  writeLines(report_lines, output_file)

  log_message(paste("Mapping report saved to:", basename(output_file)))

  return(output_file)
}

# Create barcode configuration objects
# Inputs: nanotel_files (Filtered NanoTel CSV paths); bam_info (Discovered BAM paths and their
# barcode labels); alignment_summary_path (Tab-separated exported alignment summary); output_dir
# (Directory for generated outputs); ... (Additional arguments forwarded to the underlying function)
# Outputs: Per-BAM mapping configurations for the discovered barcodes.
create_barcode_configs <- function(nanotel_files, bam_info, alignment_summary_path,
                                   output_dir, ...) {

  log_message("Creating barcode configurations")

  configs <- list()

  for (nanotel_file in nanotel_files) {
    # Extract barcode from NanoTel filename
    barcode <- extract_barcode_from_path(nanotel_file)

    if (is.na(barcode)) {
      log_message(paste("Could not extract barcode from:", basename(nanotel_file)), "WARNING")
      next
    }

    # Find matching BAM file
    matching_bam <- bam_info[bam_info$barcode == barcode, ]

    if (nrow(matching_bam) == 0) {
      log_message(paste("No matching BAM file found for:", barcode), "WARNING")
      next
    }

    if (nrow(matching_bam) > 1) {
      log_message(paste("Multiple BAM files found for:", barcode, "- using first"), "WARNING")
      matching_bam <- matching_bam[1, ]
    }

    # Create configuration
    config <- list(
      barcode_name = toupper(barcode),
      alignment_summary_path = alignment_summary_path,
      filtered_nanotel_path = nanotel_file,
      bam_file_path = matching_bam$bam_path,
      output_dir = output_dir,
      ...
    )

    configs[[barcode]] <- config
  }

  log_message(paste("Created", length(configs), "valid configurations"))

  return(configs)
}

# Command line interface
if (!interactive()) {
  # Parse command line arguments
  args <- commandArgs(trailingOnly = TRUE)

  if (length(args) != 1) {
    cat("Usage: Rscript batch_mapping_analysis.R <config_file>\n")
    cat("\n")
    cat("Arguments:\n")
    cat("  config_file: JSON configuration file with analysis parameters\n")
    cat("\n")
    cat("Example:\n")
    cat("  Rscript batch_mapping_analysis.R config/mapping_config.json\n")
    quit(status = 1)  # â† MISSING: = 1)
  }

  config_file <- args[1]

  # Validate config file exists
  if (!file.exists(config_file)) {
    cat("Error: Configuration file not found:", config_file, "\n")
    quit(status = 1)
  }

  # Run analysis
  tryCatch({
    result <- main_mapping_analysis(config_file)
    cat("\nMapping analysis completed successfully!\n")
    cat("Successfully processed", length(result$successful_results), "barcodes\n")
    if (length(result$skipped_barcodes) > 0) {
      cat("Skipped barcodes (no reads):", paste(result$skipped_barcodes, collapse=", "), "\n")
    }
    if (length(result$failed_barcodes) > 0) {
      cat("Failed barcodes:", paste(result$failed_barcodes, collapse = ", "), "\n")
    }
  }, error = function(e) {
    cat("Error during analysis:", e$message, "\n")
    quit(status = 1)
  })
}
