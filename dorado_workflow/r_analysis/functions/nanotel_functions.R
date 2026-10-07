# r_analysis/functions/nanotel_functions.R
# Functions for processing NanoTel analysis outputs

# Get the directory where this script is located
script_dir <- tryCatch({
  # Try commandArgs method first (for Rscript)
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg) > 0) {
    script_file <- sub("^--file=", "", file_arg[[1]])
    dirname(gsub("~+~", " ", script_file, fixed = TRUE))
  } else {
    # Try sys.frame for when sourced
    frame_files <- lapply(sys.frames(), function(x) x$ofile)
    frame_files <- Filter(Negate(is.null), frame_files)
    if (length(frame_files) > 0) {
      dirname(frame_files[[1]])
    } else {
      getwd()
    }
  }
}, error = function(e) {
  getwd()
})

# Only source utils.R if not already loaded
if (!exists("log_message", mode = "function")) {
  source(file.path(script_dir, "utils.R"))
}

# Process a single NanoTel summary file
process_nanotel_barcode <- function(nanotel_csv_path,
                                    density_threshold = 0.75,
                                    max_telomere_start = 150,
                                    max_edge_distance = 134,
                                    min_read_length = NULL,
                                    min_mapq = 10) {

  log_message(paste("Processing NanoTel file:", basename(nanotel_csv_path)))

  # Read the NanoTel summary file
  nanotel_data <- safe_read_csv(nanotel_csv_path)
  validate_nanotel_data(nanotel_data, nanotel_csv_path)

  # Standardize column names
  if ("sequence_ID" %in% colnames(nanotel_data)) {
    nanotel_data <- nanotel_data %>%
      rename(read_id = sequence_ID)
  }

  # Extract barcode from filename
  barcode <- extract_barcode_from_path(nanotel_csv_path)
  if (is.na(barcode)) {
    # Fallback: use filename without extension
    barcode <- tools::file_path_sans_ext(basename(nanotel_csv_path))
  }

  # Store original count
  original_count <- nrow(nanotel_data)

  # Apply filters
  filtered_data <- nanotel_data %>%
    filter(
      # Telomere density filter
      telo_density_mismatch >= density_threshold,
      !is.na(telo_density_mismatch),
      # Telomere start position filter
      Telomere_start_mismatch <= max_telomere_start
    )

  log_message(paste("Applied density and start position filters:",
                    original_count, "->", nrow(filtered_data), "reads"))

  if (!is.null(min_read_length) && !is.na(min_read_length)) {
    before_length_filter <- nrow(filtered_data)
    filtered_data <- filtered_data %>%
      filter(sequence_length >= min_read_length)
    log_message(paste("Applied minimum read length filter:",
                      before_length_filter, "->", nrow(filtered_data), "reads"))
  }

  if (nrow(filtered_data) == 0) {
    warning("No reads passed filters for barcode: ", barcode)
    return(data.frame())
  }

  # Sort by sequence length (descending)
  filtered_data <- filtered_data %>%
    arrange(desc(sequence_length))

  # Calculate running median telomere length
  filtered_data$running_median <- sapply(seq_along(filtered_data$Telomere_length_mismatch),
                                         function(i) {
                                           median(filtered_data$Telomere_length_mismatch[1:i],
                                                  na.rm = TRUE)
                                         })

  # Calculate sequence length minus running median
  filtered_data$seqLen_runningMED <- filtered_data$sequence_length - filtered_data$running_median

  # Clean up sequence ID format (remove everything after first space)
  filtered_data$read_id <- sub(" .*", "", filtered_data$read_id)

  # Keep reads satisfying:
  # max_edge_distance < sequence_length - running_median.
  final_data <- filtered_data %>%
    filter(seqLen_runningMED > max_edge_distance)

  # Add barcode identifier
  final_data$barcode <- barcode

  log_message(paste("Final filtering complete:",
                    nrow(filtered_data), "->", nrow(final_data), "reads for", barcode))

  return(final_data)
}

# Process multiple NanoTel files and combine results
batch_process_nanotel_files <- function(input_files,
                                        output_dir,
                                        density_threshold = 0.75,
                                        max_telomere_start = 150,
                                        max_edge_distance = 134,
                                        min_read_length = NULL,
                                        summary_only = FALSE) {

  log_message(paste("Starting batch processing of", length(input_files), "NanoTel files"))

  ensure_directory_exists(output_dir)

  all_processed_data <- list()
  # Collect barcode errors so every input is attempted, then fail the batch.
  # An error must not be reported as a barcode with zero filtered reads.
  failed_files <- character()

  for (i in seq_along(input_files)) {
    file_path <- input_files[i]
    show_progress(i, length(input_files), "Processing NanoTel files")

    tryCatch({
      # Process individual file
      processed_data <- process_nanotel_barcode(
        file_path,
        density_threshold = density_threshold,
        max_telomere_start = max_telomere_start,
        max_edge_distance = max_edge_distance,
        min_read_length = min_read_length
      )

      if (nrow(processed_data) > 0) {
        # Save individual filtered file
        barcode <- unique(processed_data$barcode)[1]

        # Summary mode keeps detailed CSVs at the run level. Full mode retains
        # the existing per-barcode output layout.
        if (summary_only) {
          barcode_output_dir <- output_dir
        } else {
          barcode_output_dir <- file.path(output_dir, barcode)
          ensure_directory_exists(barcode_output_dir)
        }

        # UPDATED FILE PATH:
        output_file <- file.path(barcode_output_dir, paste0("filtered_summary",
                                                            toupper(gsub("bc", "BC", barcode)), ".csv"))
        safe_write_csv(processed_data, output_file)
        all_processed_data[[barcode]] <- processed_data
      }

    }, error = function(e) {
      log_message(paste("Error processing", basename(file_path), ":", e$message), "ERROR")
      failed_files <<- c(failed_files, paste0(basename(file_path), ": ", e$message))
    })
  }

  if (length(failed_files) > 0) {
    # The caller must not write a partial combined summary as a successful run.
    stop(
      "NanoTel filtering failed for ", length(failed_files), " file(s): ",
      paste(failed_files, collapse = "; ")
    )
  }

  log_message(paste("Batch processing complete. Processed",
                    length(all_processed_data), "barcodes successfully"))

  return(all_processed_data)
}

# Pure calculation: return statistics without writing files or printing output.
# Lengths and the short-telomere threshold are in base pairs; densities are fractions.
calculate_nanotel_summary_stats <- function(all_barcodes_data,
                                            short_telomere_threshold_bp = 2000) {
  # Combine all barcode data
  combined_data <- bind_rows(all_barcodes_data)

  # Generate summary statistics
  summary_stats <- combined_data %>%
    group_by(barcode) %>%
    summarise(
      amount_of_telomeres = n(),
      median_telomere_length = round(median(Telomere_length_mismatch, na.rm = TRUE), 1),
      below_threshold_pct = round(100 * mean(
        Telomere_length_mismatch < short_telomere_threshold_bp,
        na.rm = TRUE
      ), 1),
      # additional statistics, check if needed to drop!
      med_read_len = round(median(sequence_length, na.rm = TRUE), 1),
      mean_density = round(mean(telo_density_mismatch, na.rm = TRUE), 3),
      mean_telo_start = round(mean(Telomere_start_mismatch, na.rm = TRUE), 1),
      .groups = "drop"
    )

  names(summary_stats)[names(summary_stats) == "below_threshold_pct"] <-
    paste0("below_", short_telomere_threshold_bp, "bp_pct")

  return(summary_stats)
}

# Generate summary statistics for all barcodes
generate_nanotel_summary_stats <- function(all_barcodes_data, output_file,
                                           short_telomere_threshold_bp = 2000) {

  log_message("Generating summary statistics across all barcodes")

  if (length(all_barcodes_data) == 0) {
    warning("No data available for summary statistics")
    return(data.frame())
  }

  summary_stats <- calculate_nanotel_summary_stats(
    all_barcodes_data, short_telomere_threshold_bp
  )

  # Save summary statistics
  safe_write_csv(summary_stats, output_file)

  log_message(paste("Summary statistics saved to:", basename(output_file)))

  # Print summary to console
  cat("\nNanoTel Summary Statistics:\n")
  print(summary_stats)

  return(summary_stats)
}

# Find all NanoTel summary files in a directory
find_nanotel_summary_files <- function(input_dir) {
  log_message(paste("Looking for NanoTel summary files in:", input_dir))

  patterns <- c(
    "summary.*\\.csv$",
    ".*summary.*\\.csv$",
    "nanotel.*\\.csv$"
  )

  all_files <- c()
  for (pattern in patterns) {
    files <- find_files_by_pattern(input_dir, pattern, recursive = TRUE)
    all_files <- c(all_files, files)
  }

  # Remove duplicates and filter out already processed files AND statistics files
  all_files <- unique(all_files)
  all_files <- all_files[!grepl("filtered_", basename(all_files))]
  all_files <- all_files[!grepl("statistics", basename(all_files))]  # ADD THIS LINE

  if (length(all_files) == 0) {
    warning("No NanoTel summary files found in: ", input_dir)
  } else {
    log_message(paste("Found", length(all_files), "NanoTel summary files"))
  }

  return(all_files)
}

# Validate NanoTel data structure
validate_nanotel_data <- function(data, file_path) {

  required_columns <- c("telo_density_mismatch", "Telomere_start_mismatch",
                        "Telomere_length_mismatch", "sequence_length")

  missing_columns <- required_columns[!(required_columns %in% colnames(data))]

  if (length(missing_columns) > 0) {
    stop("Missing required columns in ", basename(file_path), ": ",
         paste(missing_columns, collapse = ", "))
  }

  if (!any(c("sequence_ID", "read_id") %in% colnames(data))) {
    stop("Missing read identifier column (sequence_ID or read_id) in ", basename(file_path))
  }
  if (nrow(data) == 0) {
    log_message(paste("Empty NanoTel dataset:", basename(file_path)), "WARNING")
    return(TRUE)
  }
  for (column in required_columns) {
    if (!is.numeric(data[[column]]) && !all(is.na(data[[column]]))) {
      stop("Non-numeric values in ", column, " in ", basename(file_path))
    }
    if (any(!is.finite(data[[column]]) & !is.na(data[[column]]))) {
      stop("Non-finite values in ", column, " in ", basename(file_path))
    }
  }
  missing_rows <- sum(!complete.cases(data[, required_columns, drop = FALSE]))
  if (missing_rows > 0) {
    # Keep established NA filtering/summary behavior, but make exclusions visible.
    log_message(paste("Missing analysis values in", missing_rows, "row(s) of",
                      basename(file_path), "- existing NA filtering applies; source CSV is retained"),
                "WARNING")
  }

  # Check for reasonable data ranges
  if (any(data$sequence_length <= 0, na.rm = TRUE)) {
    warning("Found non-positive sequence lengths in ", basename(file_path))
  }

  if (any(data$telo_density_mismatch < 0 | data$telo_density_mismatch > 1, na.rm = TRUE)) {
    warning("Found telomere density values outside [0,1] range in ", basename(file_path))
  }

  return(TRUE)
}
