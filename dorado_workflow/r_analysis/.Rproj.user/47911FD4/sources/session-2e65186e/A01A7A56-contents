#!/usr/bin/env Rscript
# r_analysis/batch_mapping_analysis.R
# Batch processing script for alignment mapping and BAM filtering

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
source(file.path(script_dir, "functions", "mapping_functions.R"))

# Process a single barcode with multiple BAM files
process_barcode_multiple_bams <- function(barcode_configs_list) {
  cat("DEBUG: ENTERING process_barcode_multiple_bams function\n")
  # All configs in the list should be for the same barcode
  barcode_name <- barcode_configs_list[[1]]$barcode_name
  log_message(paste("Processing", length(barcode_configs_list), "BAM files for barcode:", barcode_name))

  # CREATE BARCODE DIRECTORY ONCE AT THE TOP (ADD THIS):
  barcode_output_dir <- file.path(barcode_configs_list[[1]]$output_dir, barcode_name)
  cat("DEBUG: About to create directory:", barcode_output_dir, "\n")
  cat("DEBUG: Directory exists before creation:", dir.exists(barcode_output_dir), "\n")
  ensure_directory_exists(barcode_output_dir)
  cat("DEBUG: Directory exists after creation:", dir.exists(barcode_output_dir), "\n")
  #ensure_directory_exists("/home/tzfati/Desktop/minknow_runs/Dorado_automation_test/Trial_74_Aki_TEST/mapping_output/BARCODE01")
  all_mapped_data <- list()
  all_filtered_bam_paths <- character()
  all_pileup_bed_paths <- character()
  total_reads <- 0

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
        log_message(paste("No reads found in BAM file", i, "for", barcode_name), "WARNING")
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

      # Step 3: Run modkit pileup on this filtered BAM
      pileup_bed_path <- file.path(barcode_output_dir,
                                   paste0("pileup-", tolower(barcode_name), "_bam", i, ".bed"))

      run_modkit_pileup(
        filtered_bam_path = filtered_bam_path,
        output_bed_path = pileup_bed_path,
        filter_threshold_c = config$filter_threshold_c,
        filter_threshold_g = config$filter_threshold_g,
        mod_threshold_m = config$mod_threshold_m
      )

      # Store results
      all_mapped_data[[i]] <- mapping_result$mapped_data
      all_filtered_bam_paths <- c(all_filtered_bam_paths, filtered_bam_path)
      all_pileup_bed_paths <- c(all_pileup_bed_paths, pileup_bed_path)
      total_reads <- total_reads + length(mapping_result$filtered_ids)

      log_message(paste("Successfully processed BAM file", i, "for", barcode_name))

    }, error = function(e) {
      log_message(paste("Error processing BAM file", i, "for", barcode_name, ":", e$message), "ERROR")
    })
  }

  if (length(all_mapped_data) == 0) {
    log_message(paste("No BAM files could be processed for", barcode_name), "ERROR")
    return(NULL)
  }

  # Step 4: Combine all mapped data for this barcode
  combined_mapped_data <- do.call(rbind, all_mapped_data)
  combined_output_file <- file.path(barcode_output_dir,
                                    paste0("mapped", barcode_name, "_combined.csv"))
  safe_write_csv(combined_mapped_data, combined_output_file)

  # Step 5: Merge pileup BED files for this barcode
  if (length(all_pileup_bed_paths) > 1) {
    merged_bed_path <- merge_pileup_bed_files(all_pileup_bed_paths, barcode_name,
                                              barcode_output_dir)
  } else {
    # Rename single BED file to standard name
    merged_bed_path <- file.path(barcode_output_dir,
                                 paste0("pileup-", tolower(barcode_name), ".bed"))
    file.copy(all_pileup_bed_paths[1], merged_bed_path, overwrite = TRUE)
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

# Main function for batch mapping analysis - UPDATED for multiple BAM files
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

  log_message("Configuration loaded successfully")
  log_message(paste("Alignment summary:", config$alignment_summary_path))
  log_message(paste("Filtered NanoTel dir:", config$filtered_nanotel_dir))
  log_message(paste("BAM directory:", config$bam_dir))
  log_message(paste("Output directory:", config$output_dir))

  # Find filtered NanoTel files
  nanotel_files <- find_files_by_pattern(config$filtered_nanotel_dir,
                                         "filtered_summary.*\\.csv$", recursive = TRUE)

  if (length(nanotel_files) == 0) {
    stop("No filtered NanoTel files found in: ", config$filtered_nanotel_dir)
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
    mod_threshold_m = mod_threshold_m
  )

  if (length(grouped_barcode_configs) == 0) {
    stop("No matching barcode configurations found")
  }

  log_message(paste("Created configurations for", length(grouped_barcode_configs), "barcodes"))

  # Process each barcode (with multiple BAM files)
  results <- list()
  failed_barcodes <- character()

  for (i in seq_along(grouped_barcode_configs)) {
    barcode_name <- names(grouped_barcode_configs)[i]
    barcode_configs_list <- grouped_barcode_configs[[i]]

    show_progress(i, length(grouped_barcode_configs), "Processing barcodes")

    tryCatch({
      result <- process_barcode_multiple_bams(barcode_configs_list)
      if (!is.null(result)) {
        results[[barcode_name]] <- result
      }
    }, error = function(e) {
      log_message(paste("Error processing", barcode_name, ":", e$message), "ERROR")
      failed_barcodes <- c(failed_barcodes, barcode_name)
    })
  }

  log_message(paste("Processing complete. Success:", length(results),
                    "Failed:", length(failed_barcodes)))

  if (length(failed_barcodes) > 0) {
    log_message(paste("Failed barcodes:", paste(failed_barcodes, collapse = ", ")), "WARNING")
  }

  # Generate summary report
  if (length(results) > 0) {
    report_file <- file.path(config$output_dir, "mapping_analysis_report.txt")
    generate_mapping_report_multiple_bams(results, failed_barcodes, report_file, config)
  }

  log_message("Mapping batch analysis completed!")

  return(list(
    successful_results = results,
    failed_barcodes = failed_barcodes,
    total_processed = length(grouped_barcode_configs)
  ))
}

# Updated report generation for multiple BAM files
generate_mapping_report_multiple_bams <- function(results, failed_barcodes, output_file, config) {

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
    paste("  Total barcodes attempted:", length(results) + length(failed_barcodes)),
    paste("  Successful barcodes:", length(results)),
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
    report_lines <- c(report_lines,
                      paste("  ", result$barcode, ":"),
                      paste("    BAM files processed:", result$bam_files_processed),
                      paste("    Telomeric reads:", result$read_count),
                      paste("    Combined mapped file:", basename(result$mapped_file)),
                      paste("    Individual filtered BAMs:", length(result$filtered_bams)),
                      paste("    Individual BED files:", length(result$individual_beds)),
                      paste("    Merged BED file:", basename(result$merged_bed)),
                      ""
    )
  }

  report_lines <- c(report_lines,
                    "OUTPUT FILES GENERATED:",
                    "  For each barcode:",
                    "    - mapped<BARCODE>_combined.csv (combined alignment + NanoTel data)",
                    "    - filtered_<BARCODE>_bam1.bam, bam2.bam, etc. (individual filtered BAMs)",
                    "    - pileup-<barcode>_bam1.bed, bam2.bed, etc. (individual methylation data)",
                    "    - pileup-<barcode>.bed (merged methylation data for barcode)",
                    "",
                    "NEXT STEPS:",
                    "  1. Review combined mapped CSV files for data quality",
                    "  2. Check merged BED files for methylation analysis",
                    "  3. Proceed with methylation analysis using merged BED files",
                    "  4. Investigate any failed barcodes",
                    "",
                    rep_str("=", 80)
  )

  # Write report
  writeLines(report_lines, output_file)

  log_message(paste("Mapping report saved to:", basename(output_file)))

  return(output_file)
}

# Create barcode configuration objects
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

# Generate mapping analysis report
generate_mapping_report <- function(results, failed_barcodes, output_file, config) {

  log_message("Generating mapping analysis report")

  total_reads <- sum(sapply(results, function(x) x$read_count))

  report_lines <- c(
    rep_str("=", 80),
    "MAPPING BATCH ANALYSIS REPORT",
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
    paste("  Total barcodes attempted:", length(results) + length(failed_barcodes)),
    paste("  Successful barcodes:", length(results)),
    paste("  Failed barcodes:", length(failed_barcodes)),
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
    report_lines <- c(report_lines,
                      paste("  ", result$barcode, ":"),
                      paste("    Telomeric reads:", result$read_count),
                      paste("    Mapped file:", basename(result$mapped_file)),
                      paste("    Filtered BAM:", basename(result$filtered_bam)),
                      paste("    Pileup BED:", basename(result$pileup_bed)),
                      ""
    )
  }

  report_lines <- c(report_lines,
                    "OUTPUT FILES GENERATED:",
                    "  For each barcode:",
                    "    - mapped<BARCODE>.csv (alignment + NanoTel data)",
                    "    - filtered_<BARCODE>.bam (telomeric reads only)",
                    "    - filtered_<BARCODE>.bam.bai (BAM index)",
                    "    - pileup-<barcode>.bed (methylation data)",
                    "",
                    "NEXT STEPS:",
                    "  1. Review mapped CSV files for data quality",
                    "  2. Check filtered BAM files in genome viewer",
                    "  3. Proceed with methylation analysis using BED files",
                    "  4. Investigate any failed barcodes",
                    "",
                    rep_str("=", 80)
  )

  # Write report
  writeLines(report_lines, output_file)

  log_message(paste("Mapping report saved to:", basename(output_file)))

  return(output_file)
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
    if (length(result$failed_barcodes) > 0) {
      cat("Failed barcodes:", paste(result$failed_barcodes, collapse = ", "), "\n")
    }
  }, error = function(e) {
    cat("Error during analysis:", e$message, "\n")
    quit(status = 1)
  })
}

# Updated functions to handle multiple BAM files per barcode

# Merge multiple pileup BED files for the same barcode
merge_pileup_bed_files <- function(bed_file_paths, barcode_name, output_dir) {

  log_message(paste("Merging", length(bed_file_paths), "BED files for", barcode_name))

  all_bed_data <- list()

  for (i in seq_along(bed_file_paths)) {
    bed_path <- bed_file_paths[i]

    if (!file.exists(bed_path)) {
      log_message(paste("BED file not found:", bed_path), "WARNING")
      next
    }

    tryCatch({
      # Read BED file
      bed_data <- read.table(bed_path, header = FALSE, sep = "\t",
                             stringsAsFactors = FALSE, comment.char = "")
      all_bed_data[[i]] <- bed_data
      log_message(paste("Read", nrow(bed_data), "records from", basename(bed_path)))
    }, error = function(e) {
      log_message(paste("Error reading BED file", bed_path, ":", e$message), "ERROR")
    })
  }

  if (length(all_bed_data) == 0) {
    stop("No BED files could be read for merging")
  }

  # Combine all BED data
  combined_bed_data <- do.call(rbind, all_bed_data)

  # Sort by chromosome and position
  if (ncol(combined_bed_data) >= 3) {
    combined_bed_data <- combined_bed_data[order(combined_bed_data[,1], combined_bed_data[,2]), ]
  }

  # Write merged BED file
  merged_bed_path <- file.path(output_dir, paste0("pileup-", tolower(barcode_name), ".bed"))
  write.table(combined_bed_data, merged_bed_path,
              sep = "\t", quote = FALSE, row.names = FALSE, col.names = FALSE)

  log_message(paste("Merged BED file created:", basename(merged_bed_path),
                    "with", nrow(combined_bed_data), "total records"))

  return(merged_bed_path)
}

# Updated create_barcode_configs to properly group by barcode
create_barcode_configs_grouped <- function(nanotel_files, bam_info, alignment_summary_path,
                                           output_dir, ...) {

  log_message("Creating grouped barcode configurations for multiple BAM processing")

  # First, create individual configs for each BAM file
  all_configs <- list()

  for (nanotel_file in nanotel_files) {
    barcode_raw <- extract_barcode_from_path(nanotel_file)

    if (is.na(barcode_raw)) {
      log_message(paste("Could not extract barcode from:", basename(nanotel_file)), "WARNING")
      next
    }

    barcode <- normalize_barcode_name(barcode_raw)
    matching_bams <- bam_info[bam_info$barcode == barcode, ]

    if (nrow(matching_bams) == 0) {
      log_message(paste("No matching BAM file found for:", barcode), "WARNING")
      next
    }

    # Create config for each BAM file
    for (i in 1:nrow(matching_bams)) {
      bam_row <- matching_bams[i, ]

      config <- list(
        barcode_name = toupper(barcode),
        alignment_summary_path = alignment_summary_path,
        filtered_nanotel_path = nanotel_file,
        bam_file_path = bam_row$bam_path,
        output_dir = output_dir,
        bam_index = i,
        ...
      )

      if (!barcode %in% names(all_configs)) {
        all_configs[[barcode]] <- list()
      }

      all_configs[[barcode]][[i]] <- config

      log_message(paste("Created config for", toupper(barcode), "BAM", i, ":", basename(bam_row$bam_path)))
    }
  }

  log_message(paste("Created configurations for", length(all_configs), "barcodes"))

  # Show summary of what was created
  for (barcode in names(all_configs)) {
    log_message(paste("Barcode", toupper(barcode), ":", length(all_configs[[barcode]]), "BAM files"))
  }

  return(all_configs)
}
