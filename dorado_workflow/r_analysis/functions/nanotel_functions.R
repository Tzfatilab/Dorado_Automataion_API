# r_analysis/functions/nanotel_functions.R
# Functions for processing NanoTel analysis outputs

# Get the directory where this script is located
script_dir <- tryCatch({
  # Try commandArgs method first (for Rscript)
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg) > 0) {
    dirname(sub("^--file=", "", file_arg))
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
                                    min_mapq = 10) {

  log_message(paste("Processing NanoTel file:", basename(nanotel_csv_path)))

  # Read the NanoTel summary file
  nanotel_data <- safe_read_csv(nanotel_csv_path)

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

  # Final filter: keep only reads where seqLen_runningMED >= 0
  final_data <- filtered_data %>%
    filter(seqLen_runningMED >= 0)

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
                                        max_telomere_start = 150) {

  log_message(paste("Starting batch processing of", length(input_files), "NanoTel files"))

  ensure_directory_exists(output_dir)

  all_processed_data <- list()

  for (i in seq_along(input_files)) {
    file_path <- input_files[i]
    show_progress(i, length(input_files), "Processing NanoTel files")

    tryCatch({
      # Process individual file
      processed_data <- process_nanotel_barcode(
        file_path,
        density_threshold = density_threshold,
        max_telomere_start = max_telomere_start
      )

      if (nrow(processed_data) > 0) {
        # Save individual filtered file
        barcode <- unique(processed_data$barcode)[1]

        # CREATE BARCODE DIRECTORY:
        barcode_output_dir <- file.path(output_dir, barcode)
        ensure_directory_exists(barcode_output_dir)

        # UPDATED FILE PATH:
        output_file <- file.path(barcode_output_dir, paste0("filtered_summary",
                                                            toupper(gsub("bc", "BC", barcode)), ".csv"))
        safe_write_csv(processed_data, output_file)
      }

    }, error = function(e) {
      log_message(paste("Error processing", basename(file_path), ":", e$message), "ERROR")
    })
  }

  log_message(paste("Batch processing complete. Processed",
                    length(all_processed_data), "barcodes successfully"))

  return(all_processed_data)
}

# Generate summary statistics for all barcodes
generate_nanotel_summary_stats <- function(all_barcodes_data, output_file) {

  log_message("Generating summary statistics across all barcodes")

  if (length(all_barcodes_data) == 0) {
    warning("No data available for summary statistics")
    return(data.frame())
  }

  # Combine all barcode data
  combined_data <- bind_rows(all_barcodes_data)

  # Generate summary statistics
  summary_stats <- combined_data %>%
    group_by(barcode) %>%
    summarise(
      amount_of_telomeres = n(),
      median_telomere_length = round(median(Telomere_length_mismatch, na.rm = TRUE), 1),
      below_2kb_pct = round(100 * mean(Telomere_length_mismatch < 2000, na.rm = TRUE), 1),
      # additional statistics, check if needed to drop!
      med_read_len = round(median(sequence_length, na.rm = TRUE), 1),
      mean_density = round(mean(telo_density_mismatch, na.rm = TRUE), 3),
      mean_telo_start = round(mean(Telomere_start_mismatch, na.rm = TRUE), 1),
      .groups = "drop"
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

  # Check for reasonable data ranges
  if (any(data$sequence_length <= 0, na.rm = TRUE)) {
    warning("Found non-positive sequence lengths in ", basename(file_path))
  }

  if (any(data$telo_density_mismatch < 0 | data$telo_density_mismatch > 1, na.rm = TRUE)) {
    warning("Found telomere density values outside [0,1] range in ", basename(file_path))
  }

  return(TRUE)
}
