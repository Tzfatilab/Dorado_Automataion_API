# r_analysis/functions/utils.R
# Shared utility functions for the R analysis pipeline

# Load required libraries with error handling
load_required_packages <- function() {
  required_packages <- c("dplyr", "readr", "tidyr", "purrr", "stringr",
                         "ggplot2", "plotly", "shiny", "htmlwidgets",
                         "RColorBrewer", "gridExtra", "fuzzyjoin", "readxl")

  missing_packages <- required_packages[!(required_packages %in% installed.packages()[,"Package"])]

  if(length(missing_packages) > 0) {
    cat("Installing missing packages:", paste(missing_packages, collapse = ", "), "\n")
    install.packages(missing_packages, repos = "https://cran.r-project.org")
  }

  # Load all packages
  invisible(lapply(required_packages, function(pkg) {
    suppressPackageStartupMessages(library(pkg, character.only = TRUE))
  }))

  cat("All required packages loaded successfully\n")
}

# Validate that input file exists
validate_file_exists <- function(file_path, description = "File") {
  if (!file.exists(file_path)) {
    stop(paste(description, "does not exist:", file_path))
  }
  return(TRUE)
}

# Validate that directory exists, create if needed
ensure_directory_exists <- function(dir_path) {
  if (!dir.exists(dir_path)) {
    dir.create(dir_path, recursive = TRUE)
    cat("Created directory:", dir_path, "\n")
  }
  return(dir_path)
}

# Read configuration from JSON file (passed from Python)
read_config <- function(config_file) {
  if (!file.exists(config_file)) {
    stop("Configuration file not found: ", config_file)
  }

  config <- jsonlite::fromJSON(config_file)
  cat("Configuration loaded from:", config_file, "\n")
  return(config)
}

# Safe file reading with error handling
safe_read_csv <- function(file_path, ...) {
  tryCatch({
    validate_file_exists(file_path, "CSV file")
    data <- readr::read_csv(file_path, show_col_types = FALSE, ...)
    cat("Successfully read:", nrow(data), "rows from", basename(file_path), "\n")
    return(data)
  }, error = function(e) {
    stop("Failed to read CSV file ", file_path, ": ", e$message)
  })
}

# Safe file writing with error handling
safe_write_csv <- function(data, file_path, ...) {
  tryCatch({
    ensure_directory_exists(dirname(file_path))
    readr::write_csv(data, file_path, ...)
    cat("Successfully wrote:", nrow(data), "rows to", basename(file_path), "\n")
    return(TRUE)
  }, error = function(e) {
    stop("Failed to write CSV file ", file_path, ": ", e$message)
  })
}

# Find files matching a pattern in a directory
find_files_by_pattern <- function(directory, pattern, recursive = TRUE) {
  if (!dir.exists(directory)) {
    warning("Directory does not exist: ", directory)
    return(character(0))
  }

  files <- list.files(directory, pattern = pattern, full.names = TRUE, recursive = recursive)
  cat("Found", length(files), "files matching pattern '", pattern, "' in", directory, "\n")
  return(files)
}

# Enhanced barcode extraction
extract_barcode_from_path <- function(file_path) {
  # First try filename - look for barcode pattern with zero-padding
  barcode_match <- stringr::str_extract(basename(file_path),
                                        "(?i)(bc|barcode)(\\d+)")

  if (!is.na(barcode_match)) {
    return(tolower(barcode_match))
  }

  # If filename doesn't have barcode, try parent directory
  parent_dir <- basename(dirname(file_path))
  barcode_match <- stringr::str_extract(parent_dir,
                                        "(?i)(bc|barcode)(\\d+)")

  if (!is.na(barcode_match)) {
    return(tolower(barcode_match))
  }

  warning("Could not extract barcode from: ", file_path)
  return(NA)
}

# Normalize barcode names to handle zero-padding differences
normalize_barcode_name <- function(barcode) {
  if (is.na(barcode)) return(NA)

  # Extract the number part and prefix
  if (grepl("^bc", barcode, ignore.case = TRUE)) {
    prefix <- "bc"
    number_part <- stringr::str_extract(barcode, "\\d+")
  } else if (grepl("^barcode", barcode, ignore.case = TRUE)) {
    prefix <- "barcode"
    number_part <- stringr::str_extract(barcode, "\\d+")
  } else {
    return(tolower(barcode))
  }

  # Convert to integer to remove leading zeros, then back to string
  if (!is.na(number_part)) {
    normalized_number <- as.character(as.integer(number_part))
    return(paste0(prefix, normalized_number))
  }

  return(tolower(barcode))
}

# System command wrapper with error handling
run_system_command <- function(command, description = "Command") {
  cat("Running:", description, "\n")
  cat("Command:", command, "\n")

  result <- system(command, intern = FALSE)

  if (result != 0) {
    stop(paste(description, "failed with exit code:", result))
  }

  cat(description, "completed successfully\n")
  return(result)
}

# Progress indicator for long operations
show_progress <- function(current, total, prefix = "Progress") {
  percent <- round((current / total) * 100, 1)
  cat("\r", prefix, ":", current, "/", total, "(", percent, "%)", sep = "")
  if (current == total) cat("\n")
}

# Log message with timestamp
log_message <- function(message, level = "INFO") {
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  cat("[", timestamp, "] [", level, "] ", message, "\n", sep = "")
}

# Create summary statistics data frame
create_summary_stats <- function(data, group_col, value_col, stats_name = "value") {
  data %>%
    group_by(!!sym(group_col)) %>%
    summarise(
      count = n(),
      mean = round(mean(!!sym(value_col), na.rm = TRUE), 2),
      median = round(median(!!sym(value_col), na.rm = TRUE), 2),
      sd = round(sd(!!sym(value_col), na.rm = TRUE), 2),
      min = min(!!sym(value_col), na.rm = TRUE),
      max = max(!!sym(value_col), na.rm = TRUE),
      .groups = "drop"
    ) %>%
    setNames(c(group_col, paste0(stats_name, "_", c("count", "mean", "median", "sd", "min", "max"))))
}

# String repetition helper (R doesn't support "string" * number like Python)
rep_str <- function(string, times) {
  paste(rep(string, times), collapse = "")
}
