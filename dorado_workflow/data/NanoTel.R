#!/usr/bin/env Rscript

################################################################
# Author: Dan Lichtental
# Copyright (c) Dan Lichtental, 2022
# Email:  dan.lichtental@mail.huji.ac.il
# Last updated:  2024-Jun-19
# Script Name: Telomere pattern finder
# Script Description: In this script we search over fastq file sequences for
# telomeric patterns.
#
# Notes: Running the script on linux:
# "Rscript --vanilla NanoTel -i input_path --save_path output_path --patterns "some patterns"
# See Rscript --vanilla NanoTel.R  --help for more additional flags
# format can be either fasta or fastq, input_path can be either a full path for a
# single fastq/a file or a directory containing fastq/a files.
# Please try to give the output_path outside the input dir path and vice versa

suppressPackageStartupMessages(require(optparse))

########## start of the flags ###############
# global vars
# My last change: 22/10/2022 - change the global_min_density from 0.3 to 0.6
global_min_density <- 0.6

global_subseq_length <- 100



option_list = list(

  # input_path
  make_option(c("-i","--input_path"), action = "store", type = "character" ,
              default = NULL, help = "Path to input files.( dir or single file)", metavar = "input path"),

  # save_path
  make_option("--save_path", action = "store",
              type = "character" , default = NULL,
              help = "A path to a directory for storing the output files.",
              metavar = "output dir path"),
  make_option("--log_path", action = "store", type = "character",
              default = NULL,
              help = "Optional log file path. Defaults to save_path/log/run.log.",
              metavar = "log file path"),

  # format( fastq/fasta)
  make_option("--format", action = "store",
              type = "character", default = "fastq" ,
              help = "input files format (Either \"fastq\" (the default) or \"fasta\", gzip is supported)",
              metavar = "file format"),

  # nrec
  make_option(c("-n","--nrec"), action = "store", type = "integer",
              default = 10000 ,
              help = "Single integer. The maximum of number of records to read in to memory for each iteration. Negative values are ignored."),

  # do rc ?
  make_option(c("-r","--rc"), action = "store_true", default = FALSE,
              help = "Should we do reverse complement on the given reads.",
              metavar = "Reverse complement on reads."),

  # pattern/s
  make_option("--patterns", action = "store", default = NULL, type = "character",
              help = "Space separated list of pattern(s). Must be in double quotes.",
              metavar = "pattern"),

  make_option("--min_density", action = "store", default = 0.6,
              type = "double",
              help = "Minimal density to consider a subsequence as a pattern region.",
              metavar = "Minimal density."),

  make_option("--subseq_length", action = "store", default = 100,
              type = "integer", help = "The length of the sub-sequence.",
              metavar = "Sub-sequence length." ),

  make_option("--use_filter", action = "store_true", default = FALSE,
              help = "Filter reads accoding to the edge.",
              metavar = "USE FILTER" ),

  make_option("--check_right_edge", action = "store_true", default = FALSE,
              help = "This flag tells us the expected telomere position: helps with the filter and telo_position accuracy",
              metavar = "Check right or left edge for filter and position"),
  make_option("--include_km", action = "store_true", default = FALSE,
              help = "Opt in to Kaplan-Meier fitting and exports for any organism."),
  make_option("--summary_only", action = "store_true", default = FALSE,
              help = "Summary-only mode: keep numeric CSV/JSON/KM analysis; skip FASTA, tracks, per-read and aggregate plots.",
              metavar = "Skip detailed per-read output files"),
  make_option("--tsq_pattern", action = "store", default = "AACCGC", type = "character",
              help = "TSQ1 search motif, reported separately from other TVRs."),
  make_option("--tvr_patterns", action = "store", default = NULL, type = "character",
              help = "Space separated list of additional pattern(s) for Telomere variant repeats. Must be in double quotes.",
              metavar = " Telomere variant repeats patterns"),

  make_option("--max_mismatch", action = "store", default = 0, type = "integer",
              help = "Maximum mismatches allowed for canonical telomere patterns (0 or 1). TVR and TSQ patterns always match exactly.",
              metavar = "maximum mismatches"),
  make_option("--short_telomere_threshold_bp", action = "store", default = 2000,
              type = "integer",
              help = "Length threshold used to calculate the percentage of short telomeres.",
              metavar = "short telomere threshold"),

  make_option("--version",
              action = "store_true",
              default = FALSE,
              help = "Print version information and exit"),

  make_option("--analysis", action = "store_true", default = FALSE,
              help = "Run post-processing filtration and produce summaries, stats TXT/JSON, KM CSV, interactive plots and PNGs.",
              metavar = "Run analysis"),

  make_option("--organism", action = "store", type = "character", default = NULL,
              help = "Organism name. Human and Homo sapiens skip KM fitting and KM exports."),

  make_option("--max_telomere_start", action = "store", default = 150,
              type = "integer",
              help = "Maximum telomere start position retained during post-processing.",
              metavar = "maximum telomere start"),

  make_option("--max_edge_distance", action = "store", default = 134,
              type = "integer",
              help = "Maximum edge distance; retained reads must have sequence length minus running median greater than this value.",
              metavar = "maximum edge distance")
)
opt = parse_args(OptionParser(option_list=option_list))
if (is.na(opt$short_telomere_threshold_bp) || opt$short_telomere_threshold_bp <= 0) {
  stop("Short telomere threshold must be greater than zero")
}

# Handle --version flag
if (opt$version) {
  cat("Telomere Analyzer  version v1.1.9-beta 2026-02-19 \n")
  quit(save = "no", status = 0)
}



# The 'confilcted' package tries to make your function choice explicit.
#   it produce an error if a function name is found on 2 or more packages!!!
suppressPackageStartupMessages(require(BiocGenerics))
suppressPackageStartupMessages(require(S4Vectors))
suppressPackageStartupMessages(require(IRanges))
suppressPackageStartupMessages(require(Biostrings))
suppressPackageStartupMessages(require(conflicted))
suppressPackageStartupMessages(require(tidyverse))

# Prefer base::intersect to avoid conflicts between lubridate / Biostrings
conflicts_prefer(base::intersect)
conflicts_prefer(base::setdiff)

# Fallback: if tidyverse failed to load (e.g. missing ragg system lib on Linux),
# load its core packages individually so the script can still run.
if (!isNamespaceLoaded("purrr")) {
  for (pkg in c("dplyr","ggplot2","tidyr","readr","purrr","tibble","stringr","forcats","lubridate")) {
    suppressPackageStartupMessages(require(pkg, character.only = TRUE))
  }
}
# purrr removed compose() in v1.0.0 ׳’ג‚¬ג€ define it here as a compatibility shim
# so the script works with any purrr version.
if (!exists("compose", mode = "function")) {
  # Inputs: ... (Additional arguments forwarded to the underlying function)
  # Outputs: Composed callable applying the supplied functions in sequence.
  compose <- function(...) {
    fns <- rev(list(...))
    function(x) Reduce(function(v, f) f(v), fns, x)
  }
}
suppressPackageStartupMessages(require(parallel))
suppressPackageStartupMessages(require(logr))
suppressPackageStartupMessages(require(future))

suppressPackageStartupMessages(require(testit))
if (isTRUE(opt$include_km)) {
  suppressPackageStartupMessages(require(survival))
}
#utils::globalVariables(c("start_index"))

# Minimum margin (bp) between sequence end and telomere end for a read to be
# considered a complete (non-censored) event in the KM survival fit.
BUFFER <- 50L

# Provisional reporting policy pending scientific approval, not an accuracy guarantee.
KM_MAX_RELATIVE_CI_WIDTH_PCT <- 20
KM_REPORT_MESSAGES <- list(
  non_estimable = "A complete KM median confidence interval could not be estimated. Consider additional sequencing.",
  invalid = "The KM estimate is not reported because the median or confidence limits are invalid.",
  failed = "KM estimation failed: %s",
  too_wide = "The KM estimate is not reported because its confidence interval is too wide (%s%%; reporting limit %s%%). Consider additional sequencing.",
  rounding = "The unrounded width exceeds the reporting limit."
)

# Inputs: median (Estimated median telomere length in base pairs); lower (Lower confidence limit in
# base pairs); upper (Upper confidence limit in base pairs); limit (Maximum accepted relative
# confidence-interval width); warnings (Warnings); error (Error)
# Outputs: Assessment list containing reportability, estimates and the reporting reason.
assess_km_result <- function(median, lower, upper,
                             limit = KM_MAX_RELATIVE_CI_WIDTH_PCT,
                             warnings = character(), error = NULL) {
  if (!is.numeric(limit) || length(limit) != 1L || !is.finite(limit) || limit <= 0) {
    stop("KM_MAX_RELATIVE_CI_WIDTH_PCT must be finite and positive.")
  }
  result <- list(median = median, lower = lower, upper = upper,
                 relative_ci_width_pct = NA_real_, limit = limit,
                 warnings = warnings, error = error, status = "non_estimable",
                 reason = KM_REPORT_MESSAGES$non_estimable)
  if (!is.null(error)) {
    result$status <- "failed"
    detail <- substr(gsub("[[:space:]]+", " ", error), 1L, 240L)
    result$reason <- sprintf(KM_REPORT_MESSAGES$failed, detail)
    return(result)
  }
  # Inputs: x (Value being checked or formatted)
  # Outputs: TRUE for one finite numeric value; FALSE otherwise.
  valid_number <- function(x) is.numeric(x) && length(x) == 1L && is.finite(x)
  if (!all(vapply(list(median, lower, upper), valid_number, logical(1)))) return(result)
  if (median <= 0 || lower > median || median > upper) {
    result$status <- "invalid"
    result$reason <- KM_REPORT_MESSAGES$invalid
    return(result)
  }
  result$relative_ci_width_pct <- 100 * ((upper - lower) / median)
  if (result$relative_ci_width_pct <= limit) {
    result$status <- "reportable"
    result$reason <- NULL
  } else {
    result$status <- "too_wide"
    width_text <- sprintf("%.1f", result$relative_ci_width_pct)
    limit_text <- sprintf("%.1f", limit)
    result$reason <- sprintf(KM_REPORT_MESSAGES$too_wide, width_text, limit_text)
    if (width_text == limit_text) {
      result$reason <- paste(result$reason, KM_REPORT_MESSAGES$rounding)
    }
  }
  result
}

# Inputs: data (Read-level or measurement table for this operation); limit (Maximum accepted
# relative confidence-interval width); fit_function (Fit function); summary_function (Summary
# function)
# Outputs: Assessed KM result; failure paths retain an unavailable/failed status.
fit_km_result <- function(data, limit = KM_MAX_RELATIVE_CI_WIDTH_PCT,
                          fit_function = survival::survfit,
                          summary_function = summary) {
  # Validate policy independently of fit errors.
  invisible(assess_km_result(NA_real_, NA_real_, NA_real_, limit))
  fit_warnings <- character()
  fit_error <- NULL
  estimates <- c(median = NA_real_, lower = NA_real_, upper = NA_real_)
  tryCatch(withCallingHandlers({
    # The caller supplies canonical measurements from the selected matching mode.
    data$margin <- data$sequence_length - data$telomere_end
    data$event <- as.integer(data$margin >= BUFFER)
    fit <- fit_function(
      survival::Surv(telomere_length, event) ~ 1,
      data = data, conf.type = "log-log", conf.int = 0.95
    )
    fit_table <- summary_function(fit)$table
    estimates <- c(median = unname(fit_table["median"]),
                   lower = unname(fit_table["0.95LCL"]),
                   upper = unname(fit_table["0.95UCL"]))
  }, warning = function(w) {
    fit_warnings <<- c(fit_warnings, conditionMessage(w))
    invokeRestart("muffleWarning")
  }), error = function(e) {
    fit_error <<- conditionMessage(e)
  })
  assess_km_result(estimates[["median"]], estimates[["lower"]],
                   estimates[["upper"]], limit, fit_warnings, fit_error)
}

# Inputs: result (Result produced by the preceding operation)
# Outputs: Human-readable text describing the assessed KM result.
format_km_report <- function(result) {
  # Inputs: x (Value being checked or formatted)
  # Outputs: Formatted base-pair value.
  fmt_bp <- function(x) paste0(format(round(x), big.mark = ",", scientific = FALSE,
                                     trim = TRUE), " bp")
  reportable <- identical(result$status, "reportable")
  lines <- c(
    paste0("KM Median Telomeric Length                 : ",
           if (reportable) fmt_bp(result$median) else "Not reported"),
    paste0("KM Median 95% Confidence Interval          : ",
           if (reportable) paste0(format(round(result$lower), big.mark = ",", scientific = FALSE, trim = TRUE),
                                   "\u2013", fmt_bp(result$upper)) else "Not reported"),
    paste0("KM Whole Relative CI Width                 : ",
           if (is.na(result$relative_ci_width_pct)) "Not available" else
             sprintf("%.1f%%", result$relative_ci_width_pct))
  )
  if (!reportable) lines <- c(lines, paste0("KM Reporting Reason                       : ", result$reason))
  lines
}

# Machine-readable equivalent of results.txt; never export withheld KM estimates.
# Non-finite descriptive values become JSON null, not NaN/Infinity.
# Inputs: barcode (Barcode label or record used by this operation); n_reads (Number of reads in the
# recorded population); n_complete (Number of fully observed reads); n_censored (Number of censored
# reads); censoring_rate (Censoring rate); med_telo (Med telo); pct_short (Pct short);
# short_threshold (Short threshold); km_result (Already assessed KM result and reporting status)
# Outputs: Machine-readable analysis fields with unavailable values represented explicitly.
make_analysis_report <- function(barcode, n_reads, n_complete, n_censored,
                                 censoring_rate, med_telo, pct_short,
                                 short_threshold, km_result) {
  reportable <- identical(km_result$status, "reportable")
  # Inputs: x (Value being checked or formatted)
  # Outputs: The finite scalar input, otherwise NULL.
  finite_or_null <- function(x) if (length(x) == 1L && is.finite(x)) x else NULL
  report <- list(
    barcode = barcode,
    number_of_telomeric_reads_post_filtration = n_reads,
    complete_telomeric_reads = n_complete,
    incomplete_telomeric_reads = n_censored,
    censoring_rate_pct = finite_or_null(100 * censoring_rate),
    median_telomeric_length_post_filtration_bp = finite_or_null(med_telo),
    short_telomere_threshold_bp = short_threshold,
    telomeres_shorter_than_threshold_pct = finite_or_null(pct_short),
    km_median_telomeric_length_bp = if (reportable) km_result$median else NULL,
    km_median_95_ci_lower_bp = if (reportable) km_result$lower else NULL,
    km_median_95_ci_upper_bp = if (reportable) km_result$upper else NULL,
    km_whole_relative_ci_width_pct = finite_or_null(km_result$relative_ci_width_pct),
    km_reporting_reason = km_result$reason
  )
  if (is.null(km_result)) report <- report[!(startsWith(names(report), "km_") |
    names(report) %in% c("complete_telomeric_reads", "incomplete_telomeric_reads", "censoring_rate_pct"))]
  report
}

# KM censoring describes the pre-edge KM input, even when its median is withheld.
# Store it silently in CSV; the visible TXT retains final-filter censoring only.
# Inputs: barcode (Barcode label or record used by this operation); km_input (Population used by the
# KM fit); km_result (Already assessed KM result and reporting status)
# Outputs: One-row table of saved KM measurements and reporting status.
make_km_statistics <- function(barcode, km_input, km_result) {
  margins <- km_input$sequence_length - km_input$telomere_end
  events <- as.integer(margins >= BUFFER)
  valid_events <- all(is.finite(margins))
  n <- nrow(km_input)
  reportable <- identical(km_result$status, "reportable")
  data.frame(
    barcode = barcode,
    km_status = km_result$status,
    km_median_bp = if (reportable) km_result$median else NA_real_,
    km_ci_lower_bp = if (reportable) km_result$lower else NA_real_,
    km_ci_upper_bp = if (reportable) km_result$upper else NA_real_,
    km_whole_relative_ci_width_pct = if (is.finite(km_result$relative_ci_width_pct))
      km_result$relative_ci_width_pct else NA_real_,
    km_input_read_count = n,
    km_complete_read_count = if (valid_events) sum(events == 1L) else NA_integer_,
    km_censored_read_count = if (valid_events) sum(events == 0L) else NA_integer_,
    km_censoring_rate_pct = if (valid_events && n > 0L) 100 * mean(events == 0L) else NA_real_,
    km_reporting_reason = if (is.null(km_result$reason)) "" else km_result$reason
  )
}

# Plot inputs follow the selected canonical mode; never infer mode from a CSV name.
# No sampling: retain every read in the supplied (pre-edge or final) population.
# Inputs: data (Read-level or measurement table for this operation); columns (Exported measurement
# columns selected for plotting); max_edge_distance (Max edge distance)
# Outputs: Read-level plotting data selected from the supplied population.
make_analysis_plot_data <- function(data, columns, max_edge_distance, include_km = FALSE) {
  n <- nrow(data)
  result <- data.frame(
    read_index = seq_len(n),
    read_id = sub("[[:space:]].*$", "", as.character(data$sequence_ID)),
    read_length_bp = data$sequence_length,
    telomere_length_bp = data[[columns[["length"]]]],
    running_median_bp = data$TelLenMM_RunningMed,
    retained_by_edge_filter = data$SeqLen_minus_RunMed > max_edge_distance
  )
  if (isTRUE(include_km)) {
    margin <- data$sequence_length - data[[columns[["end"]]]]
    result$event <- ifelse(is.finite(margin), as.integer(margin >= BUFFER), NA_integer_)
  }
  result
}

# Share the original histogram implementation with regenerated dashboards.
nanotel_script_file <- sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE)[[1]])
nanotel_script_file <- gsub("~+~", " ", nanotel_script_file, fixed = TRUE)
source(file.path(dirname(normalizePath(nanotel_script_file)), "nanotel_histogram.R"))

# Inputs: data (Read-level or measurement table for this operation); barcode (Barcode label or
# record used by this operation); mismatch_allowance (Recorded canonical mismatch allowance)
# Outputs: Plotly per-read telomere/read-length figure.
make_telomere_line_plot <- function(data, barcode, mismatch_allowance) {
  mode <- if (mismatch_allowance == 0L) "exact" else "mismatch"
  hover <- paste0(
    "Read: ", htmltools::htmlEscape(data$read_id),
    "<br>Rank: ", data$read_index,
    "<br>Read length: ", format(data$read_length_bp, big.mark = ",", trim = TRUE), " bp",
    "<br>Telomere length (", mode, "): ", format(data$telomere_length_bp, big.mark = ",", trim = TRUE), " bp",
    "<br>Running median: ", format(data$running_median_bp, big.mark = ",", trim = TRUE), " bp",
    "<br>Edge filter: ", ifelse(is.na(data$retained_by_edge_filter), "Unknown",
                                ifelse(data$retained_by_edge_filter, "Retained", "Removed"))
  )
  p <- plotly::plot_ly()
  for (series in list(
    list("Read Length", data$read_length_bp, "#E8735A"),
    list(paste0("Telomere Length (", mode, ")"), data$telomere_length_bp, "#228B22"),
    list("Running Median Telomere Length", data$running_median_bp, "#4169E1")
  )) {
    p <- plotly::add_trace(p, x = data$read_index, y = series[[2]],
                          type = "scattergl", mode = "lines", name = series[[1]],
                          line = list(color = series[[3]]), text = hover,
                          hovertemplate = "%{text}<extra>%{fullData.name}</extra>")
  }
  p <- plotly::layout(p,
    title = list(text = paste0("Telomere and Read Lengths - ",
                              htmltools::htmlEscape(analysis_barcode_title(barcode)),
                              "<br><sup>Density/start-filtered reads, before edge filtering</sup>")),
    xaxis = list(title = "Read rank (longest to shortest)", tickformat = ",d"),
    yaxis = list(title = "Length (bp)", tickformat = ",d", rangemode = "tozero"),
    legend = list(orientation = "h", y = -0.18), margin = list(t = 95, b = 110),
    dragmode = "zoom", plot_bgcolor = "white", paper_bgcolor = "white")
  if (!nrow(data)) p <- plotly::layout(p, annotations = list(
    list(text = "No reads passed the density/start filters", x = 0.5, y = 0.5,
         xref = "paper", yref = "paper", showarrow = FALSE)))
  p
}

# Inputs: plot (Figure to save); prefix (Field-name prefix for nested source facts)
# Outputs: Writes figure artifacts under prefix; callers use the saved files.
save_analysis_plot <- function(plot, prefix) {
  plot <- plotly::config(plot, displaylogo = FALSE, responsive = TRUE,
    toImageButtonOptions = list(format = "png", filename = basename(prefix),
                               width = 1800, height = 900, scale = 1))
  specification <- as.character(plotly::plotly_json(plot, jsonedit = FALSE))
  # Keep only the source specification needed to regenerate the dashboard.
  details <- file.path(dirname(prefix), "report_details")
  dir.create(details, recursive=TRUE, showWarnings=FALSE)
  writeLines(specification, file.path(details, paste0(basename(prefix), ".plotly.json")), useBytes = TRUE)

}



#' my changes: 5.11.2023
#' 1. Change thr for re-indexing  telomere_density < 0.85
#'  (telomere_density2 < 0.85) this should exclude small islands from the telo.
#' 2. Added: print the input arguments to the log file.




# test matchPattern with latters !in c("A", "C", "G", "T")








#' 3. Only canonical patterns use global_max_mismatch (default 0).
#'    TVR and TSQ patterns always use exact matching.





#' TODO: replace all for loops to map with a private functio
#' instead of for(...{if...else...} : map(x, p_function)
#' map(numlist, ~.x %>% sqrt() %>% sin())

# Last change: 16:09 4/10/2023 max-matches <- 2 (insteadof 1)

#










global_min_density <- 0.5
global_subseq_length <- 100


#' bug fix of faild calculating the telomere indcies after re-telo_position:
#' Check: My last change : 22/10/2023



# try using this code:
#' # Install and load the GenomicRanges package

#library(GenomicRanges)
# Set the total length and width
#total_length <- 1000
#width <- 100
# Create a GRanges object
#ranges <- GRanges(seqnames = 'chr1', ranges = IRanges(start = seq(1, total_length, width), end = seq(width, total_length, width)))
# Print the GRanges object
#print(ranges)

# Inputs: dna_seq (DNAString sequence to analyze); sub_length (Window length in base pairs)
# Outputs: IRanges windows covering the analyzed sequence.
split_telo <- function(dna_seq, sub_length) {
  #' @title Splits a DNA sequence into subsequences.
  #' @description This function calculate the sequence len and creates IRanges
  #' objects of subseuences of a given length.
  #' if The dna_seq%%subseq != 0   and last' width < sub_length/2 Then we will
  #' remove this last index making the last subtelomere longer then by.
  #' (because we want to prevent a case where we have for
  #' example subtelomere of length < sub_length/2 which is too short to consider
  #'  -> then the last subtelomere is a bit longer)
  #' If the length of dna_seq is less then the sub_length it will return an
  #' empty Iranges Object.
  #' @usage
  #' @param dna_seq: DNAString object
  #' @param sub_length: The length of each subsequence
  #' @value An IRanges object of the subsequences.
  #' @return iranges_idx: IRanges obsject of the indices of each subsequence
  #' @examples
  idx_start <- seq(1, length(dna_seq), by = sub_length)
  idx_end <- idx_start + sub_length - 1
  idx_end[length(idx_end)] <- length(dna_seq)
  # if last subsequence is less then 50%
  if (length(dna_seq) - dplyr::last(idx_start) < (sub_length / 2)) {
    idx_start <- idx_start[1:length(idx_start) - 1]
    idx_end <- idx_end[1:length(idx_end) - 1]
    idx_end[length(idx_end)] <- length(dna_seq)
  }
  idx_ranges <- IRanges(start = idx_start, end = idx_end)
  return(idx_ranges)
} # IRanges object


# create a patterns which are create from 1 pattern using 1
# mismatch + the original pattern








# My last change: 15/10/2023 - use trim for out-of-bound matches"
#' This is a feature. The matchPattern/vmatchPattern family of functions treat
#' out-of-bound nucleotide positions as mismatches (think of these positions as
#' having letters that don't match any letter in DNA_ALPHABET).
#'
#' Note that the out-of-bound matches are easy to remove:
#'
#' library(Biostrings)
#' matches <- matchPattern("ATGG", subject, max.mismatch=1)
#' matches

# Views on a 16-letter DNAString subject
# subject: AATGCGCGTGGATATG
# views:
#       start end width
#   [1]     2   5     4 [ATGC]
#   [2]     8  11     4 [GTGG]
#   [3]    14  17     4 [ATG ]
#'
## Remove the out-of-bound matches:
#' keep_me <- (0 <= start(matches)) & (end(matches) <= length(subject(matches)))
#' matches[keep_me]
# Views on a 16-letter DNAString subject
# subject: AATGCGCGTGGATATG
# views:
#       start end width
#   [1]     2   5     4 [ATGC]
#   [2]     8  11     4 [GTGG]
#' Alternatively, you can trim the out-of-bound matches:
#' trim(matches)
# Views on a 16-letter DNAString subject
# subject: AATGCGCGTGGATATG
# views:
#       start end width
#   [1]     2   5     4 [ATGC]
#   [2]     8  11     4 [GTGG]
#   [3]    14  16     3 [ATG]

# my improvment: fiding the IRanges and making union for overlaps and then
#calculate according to sum(width of the IRanges)
# The calculation is on the full sequence and it is not fit for subsequences
#' use purrr::map to replace the for loops code
# Inputs: sequence (DNA sequence in the analyzed orientation); patterns (Canonical/search motifs
# used by this analysis); with_mismatch (Whether canonical searching allows one mismatch);
# tvr_patterns (Additional selected TVR motifs)
# Outputs: List containing total density, unioned matched ranges and motif-specific matches.
get_density_iranges <- function(sequence, patterns, with_mismatch = FALSE, tvr_patterns = NULL) {
  #' @title Pattern searching function.
  #' @description: get the density of a given pattern or a total density of a
  #' list of patterns, and IRanges of the patterns.
  #' @param pattern: a list of patterns or a string of 1 pattern.
  #' @param sequence: DNAString object
  #' @param tvr_patterns: Additional TVR's.(Telomeric varient repeats)
  #' @value A numeric for the total density of the pattern(patterns) in the
  #' sequences, a IRanges object of the indcies of the patterns found.
  #' @return a tuple of (density, IRanges) Total density of all the patterns in
  #' the list( % of the patterns in this sequence) and the IRanges of them
  #' @examples
  total_density <- 0
  max_mismatch <- 0
  if(with_mismatch) {
    max_mismatch <- 1
  }

  mp_all <- IRanges()# union of all the IRanges of all the patterns in the list
  # Preserve the existing search hits before union removes motif identity.
  # This extra return member never changes the density/ranges used for calling.
  motif_matches <- data.frame(motif=character(), matched_sequence=character(),
                              start=integer(), end=integer(), role=character(), max_mismatch=integer())
  # Inputs: hits (Exported motif matches; this function does not search sequences); motif (Motif
  # associated with the exported matches); role (Canonical or TVR role of the motif); allowance
  # (Maximum allowed mismatches for this search)
  # Outputs: Updates the enclosing motif-match table; no public return value.
  retain_hits <- function(hits, motif, role, allowance) {
    if (!length(hits)) return(invisible(NULL))
    motif_matches <<- rbind(motif_matches, data.frame(
      motif=motif, matched_sequence=as.character(Views(unlist(sequence), start=start(hits), end=end(hits))),
      start=start(hits), end=end(hits), role=role, max_mismatch=allowance))
  }
  if (is.list(patterns)) {
    patterns <- unique(patterns)  # make sure there are no dups

    #  use map instead and do
    for (pat in patterns){
      #' letters that represent ambiguity which are used when more than one kind
      #'  of nucleotide could occur at that position - than it is not fixed pattern
      fixed <- !str_detect(string = pat, pattern = "[WSMKRYBDHVN]")
      curr_mp <- matchPattern(pattern = pat, subject =
              unlist(sequence),  fixed = fixed,  max.mismatch = max_mismatch)
      if( (fixed == FALSE) || (max_mismatch > 0) ) {
        curr_mp <- trim(curr_mp)
      }

      retain_hits(curr_mp, pat, "canonical", max_mismatch)
      mp_all <- IRanges::union(mp_all, curr_mp)


    }
    mp_all <- IRanges::union(mp_all, mp_all) # incase there are overlaps

  } else {
    fixed <- !str_detect(string = patterns, pattern = "[WSMKRYBDHVN]")
    mp_all <- matchPattern(pattern = patterns, subject = unlist(sequence),
                           max.mismatch = max_mismatch, fixed = fixed)
    # Trimming is part of the original search semantics; retain those same hits.
    report_hits <- if (!fixed || max_mismatch > 0) trim(mp_all) else mp_all
    retain_hits(report_hits, patterns, "canonical", max_mismatch)
    if( (fixed == FALSE) || (max_mismatch > 0) ) {
      mp_all <- trim(mp_all)
      mp_all <- IRanges::union(mp_all, mp_all) # incase there are overlaps
    }

  }


  # additional TVR's
  if(!is.null(tvr_patterns)) {
    if (is.list(tvr_patterns)) {
      tvr_patterns <- unique(tvr_patterns)  # make sure there are no dups

      #  use map instead and do
      for (pat in tvr_patterns){
        #' letters that represent ambiguity which are used when more than one kind
        #'  of nucleotide could occur at that position - than it is not fixed pattern
        fixed <- !str_detect(string = pat, pattern = "[WSMKRYBDHVN]")
        curr_mp <- matchPattern(pattern = pat, subject =
                                  unlist(sequence), fixed = fixed,
                                  max.mismatch = 0L)
        if( (fixed == FALSE) ) {
          curr_mp <- trim(curr_mp)
        }

        retain_hits(curr_mp, pat, "tvr", 0L)
        mp_all <- IRanges::union(mp_all, curr_mp)
      }



    mp_all <- IRanges::union(mp_all, mp_all) # incase there are overlaps


    }else {
      fixed <- !str_detect(string = tvr_patterns, pattern = "[WSMKRYBDHVN]")
      mp_curr <- matchPattern(pattern = tvr_patterns, subject = unlist(sequence),
                              fixed = fixed,
                              max.mismatch = 0L)
      report_hits <- if (!fixed) trim(mp_curr) else mp_curr
      retain_hits(report_hits, tvr_patterns, "tvr", 0L)
      if( (fixed == FALSE) ) {
        mp_curr <- trim(mp_curr)
      }
      mp_all <- IRanges::union(mp_all, mp_curr) # include exact TVR/TSQ matches too
      mp_all <- IRanges::union(mp_all, mp_all) # incase there are overlaps
    }
  }

  total_density <- sum(width(mp_all)) / nchar(sequence)
  return(list(total_density, mp_all, motif_matches=motif_matches))
}

# Versioned report measurements over existing calls/hits; no additional search,
# boundary detection or filtering. Coordinates remain 1-based inclusive.
# Inputs: read_id (Read identifier used for joins or navigation); boundary (Called telomere interval
# in 1-based inclusive coordinates); hits (Exported motif matches; this function does not search
# sequences)
# Outputs: Versioned base-coverage record, or NULL when the boundary is unavailable.
report_repeat_coverage <- function(read_id, boundary, hits) {
  if (length(boundary) != 1L || width(boundary) <= 0L) return(NULL)
  # Inputs: role (Canonical or TVR role of the motif)
  # Outputs: Unioned matched ranges clipped to the selected role and boundary.
  clipped_union <- function(role) {
    chosen <- if (role == "tsq") hits[hits$role == "tvr" & hits$motif == global_tsq_pattern, , drop=FALSE]
      else hits[hits$role == role, , drop=FALSE]
    if (!nrow(chosen)) return(IRanges::IRanges())
    ranges <- IRanges::IRanges(start=chosen$start, end=chosen$end)
    IRanges::reduce(IRanges::intersect(ranges, boundary))
  }
  canonical <- clipped_union("canonical")
  tvr <- clipped_union("tvr")
  # Each category is a union: overlapping hits never inflate its coverage.
  # Categories may overlap each other; export that ambiguity, do not assign it.
  canonical_bp <- sum(width(canonical)); tvr_bp <- sum(width(tvr))
  overlap_bp <- sum(width(IRanges::intersect(canonical, tvr)))
  tsq <- clipped_union("tsq")
  tsq_bp <- sum(width(tsq))
  # TSQ is removed from ordinary TVR coverage, so variant bases count once.
  ordinary_tvr_bp <- sum(width(IRanges::setdiff(tvr, tsq)))
  denominator <- as.integer(width(boundary))
  list(tsq_pattern=global_tsq_pattern, tsq_bp=tsq_bp,
    ordinary_tvr_bp=ordinary_tvr_bp,
    schema_version=2L, definition="union_coverage_tvr_interval_v2",
    read_id=read_id, method="tvr_inclusive", convention="one_based_inclusive",
    space="nanotel_analyzed_read", start=as.integer(start(boundary)),
    end=as.integer(end(boundary)), denominator_bp=denominator,
    canonical_bp=canonical_bp, tvr_bp=tvr_bp, overlap_bp=overlap_bp,
    unassigned_bp=denominator-canonical_bp-tvr_bp+overlap_bp,
    canonical_pct=100*canonical_bp/denominator, tvr_pct=100*tvr_bp/denominator,
    tvr_motifs=as.list(unique(as.character(hits$motif[hits$role == "tvr" &
      hits$end >= start(boundary) & hits$start <= end(boundary)]))))
}

# Compact TSQ tandem-array counts, shared by Full and Summary. Only complete,
# exact copies inside the TSQ-inclusive call enter maximal adjacent-copy runs.
report_tsq_tandems <- function(boundary, hits) {
  if (length(boundary) != 1L || start(boundary) < 1L || width(boundary) <= 0L) return(NULL)
  size <- nchar(global_tsq_pattern)
  starts <- sort(unique(hits$start[hits$role == "tvr" & hits$motif == global_tsq_pattern &
    hits$matched_sequence == global_tsq_pattern & hits$end-hits$start+1L == size &
    hits$start >= start(boundary) & hits$end <= end(boundary)]))
  runs <- data.frame(start=integer(), copies=integer())
  for (phase in split(starts, starts %% size)) {
    groups <- split(phase, cumsum(c(TRUE, diff(phase) != size)))
    for (group in groups) if (length(group) >= 2L)
      runs <- rbind(runs, data.frame(start=min(group), copies=length(group)))
  }
  # Self-overlapping motifs can produce alternative phases for the same array.
  # Count a physical span once: longest array first, then earliest start.
  accepted_start <- integer(); accepted_end <- integer(); counts <- list()
  if (nrow(runs)) for (i in order(-runs$copies, runs$start)) {
    lo <- runs$start[i]; hi <- lo+runs$copies[i]*size-1L
    if (any(lo <= accepted_end & hi >= accepted_start)) next
    accepted_start <- c(accepted_start, lo); accepted_end <- c(accepted_end, hi)
    key <- as.character(runs$copies[i])
    counts[[key]] <- if (is.null(counts[[key]])) 1L else counts[[key]]+1L
  }
  bins <- lapply(sort(as.integer(names(counts))), function(n)
    list(repeats=n, count=counts[[as.character(n)]]))
  list(schema_version=1L, motif=global_tsq_pattern, start=as.integer(start(boundary)),
    end=as.integer(end(boundary)), counts=bins)
}

# Summary-mode motif aggregates: no per-hit coordinates or sequences are saved.
report_repeat_summary <- function(boundary, hits) {
  if (length(boundary) != 1L || width(boundary) <= 0L) return(NULL)
  lo <- as.integer(start(boundary)); hi <- as.integer(end(boundary))
  hits <- hits[hits$end >= lo & hits$start <= hi, , drop=FALSE]
  observed <- as.character(hits$matched_sequence)
  motif <- as.character(hits$motif)
  labels <- ifelse(is.na(observed) | !nzchar(observed), paste0(motif, " (searched motif; sequence unavailable)"),
    ifelse(nchar(observed) != nchar(motif), paste0(observed, " (partial match to ", motif, ")"),
      ifelse(observed != motif, "Mismatch", paste0(motif, ifelse(hits$role == "canonical", " (canonical)", "")))))
  labels[hits$role == "tvr" & motif == global_tsq_pattern] <- "TSQ"
  bases <- list()
  if (nrow(hits)) {
    ranges <- IRanges::IRanges(start=pmax(lo, hits$start), end=pmin(hi, hits$end))
    pieces <- IRanges::disjoin(ranges, with.revmap=TRUE)
    reverse_map <- S4Vectors::mcols(pieces)$revmap
    for (i in seq_along(pieces)) {
      active <- unique(labels[as.integer(reverse_map[[i]])])
      label <- if (length(active) == 1L) active else "Overlapping motifs"
      bases[[label]] <- (if (is.null(bases[[label]])) 0L else bases[[label]]) + as.integer(width(pieces)[i])
    }
  }
  count_labels <- function(values) {
    counts <- table(values)
    stats::setNames(as.list(counts), as.character(names(counts)))
  }
  covered <- sum(unlist(bases))
  bases[["Unassigned bases"]] <- as.integer(width(boundary)) - covered
  list(schema_version=1L, method="tvr_inclusive", start=lo, end=hi,
       base_counts=bases, match_counts=count_labels(labels),
       tvr_motifs=count_labels(motif[hits$role == "tvr"]))
}

# Each parallel search group owns two buffered connections in the local temp
# directory. Workers never append concurrently to a shared barcode file.
# Inputs: folder (Directory used to locate or store artifacts)
# Outputs: Named export connections used by the chunk writer.
open_report_batch <- function(folder) {
  sink <- new.env(parent=emptyenv())
  sink$connections <- list(); sink$written <- list()
  for (kind in c("density", "motifs", "index")) {
    sink$connections[[kind]] <- file(tempfile(paste0(kind, "_"), tmpdir=folder, fileext=".csv"), "wt")
    sink$written[[kind]] <- FALSE
  }
  sink
}

# Losslessly collapse identical method rows; method names are expanded by the
# report adapter. Coverage/search results themselves are never changed.
# Inputs: rows (Records included in this operation); serial (Original NanoTel read number)
# Outputs: Detail rows using compact per-read identity fields.
compact_report_rows <- function(rows, serial) {
  rows$read_id <- as.character(serial)
  rows$schema_version <- 2L
  fields <- setdiff(names(rows), "method")
  key <- do.call(paste, c(rows[fields], sep="\034"))
  # Preserve repeated identical observations within a method. Only corresponding
  # occurrences across different methods are shared, never dropped.
  occurrence <- ave(seq_along(key), paste(rows$method,key,sep="|"), FUN=seq_along)
  key <- paste(key, occurrence, sep="|")
  groups <- split(seq_len(nrow(rows)), factor(key, levels=unique(key)))
  first <- vapply(groups, function(ids) ids[1], integer(1))
  result <- rows[first, , drop=FALSE]
  result$method <- vapply(groups, function(ids) paste(unique(rows$method[ids]), collapse="|"), character(1))
  result
}

# Inputs: sink (Open batch-export connection collection); kind (Detail-export kind selecting the
# output connection); rows (Records included in this operation)
# Outputs: Appends detail rows to the selected batch connection.
write_report_batch <- function(sink, kind, rows) {
  write.table(rows, sink$connections[[kind]], sep=",", row.names=FALSE,
              col.names=!sink$written[[kind]], na="", qmethod="double")
  sink$written[[kind]] <- TRUE
}

# Merge without loading barcode-sized tables into memory. Header-only/empty
# workers contribute no extra headers; all read IDs and completion rows survive.
# Inputs: folder (Directory used to locate or store artifacts); output_dir (Directory for generated
# outputs); barcode (Barcode label or record used by this operation)
# Outputs: Writes combined barcode detail exports from completed chunk batches.
merge_report_batches <- function(folder, output_dir, barcode) {
  details <- file.path(output_dir, "report_details")
  dir.create(details, recursive=TRUE, showWarnings=FALSE)
  for (kind in c("density", "motifs", "index")) {
    destination <- file.path(details, paste0(barcode, "_reads_", kind, ".csv.gz"))
    temporary <- paste0(destination, ".partial")
    out <- gzfile(temporary, "wt", compression=6); header <- NULL
    tryCatch({
      for (path in sort(list.files(folder, pattern=paste0("^", kind, "_.*\\.csv$"), full.names=TRUE))) {
        input <- file(path, "rt")
        tryCatch({
          first <- readLines(input, n=1, warn=FALSE)
          if (length(first)) {
            if (is.null(header)) { header <- first; writeLines(header, out) }
            else if (!identical(header, first)) stop("Inconsistent report batch columns")
            repeat {
              lines <- readLines(input, n=10000, warn=FALSE)
              if (!length(lines)) break
              writeLines(lines, out)
            }
          }
        }, finally=close(input))
      }
    }, finally=close(out))
    if (is.null(header)) { unlink(temporary); next }
    if (file.exists(destination) && !file.remove(destination)) stop("Cannot replace report export")
    if (!file.rename(temporary, destination)) stop("Cannot publish report export")
  }
}

# Export only already-computed windows and hits, in the analyzed read's native
# 1-based inclusive coordinates. A completion row distinguishes zero hits from
# a missing search. Summary-only runs intentionally omit these detailed files.
# Inputs: read_id (Read identifier used for joins or navigation); serial (Original NanoTel read
# number); analyses (Exact, mismatch and TVR-inclusive call results); output_dir (Directory for
# generated outputs); tvr_boundary (TVR-inclusive called interval, when available)
# Outputs: Writes selected per-read density, motif and coverage artifacts.
export_report_density <- function(read_id, serial, analyses, output_dir, tvr_boundary=NULL) {
  folder <- file.path(output_dir, "report_details")
  dir.create(folder, recursive=TRUE, showWarnings=FALSE)
  densities <- list(); motifs <- list()
  for (method in names(analyses)) {
    analysis <- analyses[[method]]
    if (is.null(analysis)) next
    windows <- analysis[[1]]
    densities[[method]] <- data.frame(read_id=read_id, method=method,
      start=windows$start_index, end=windows$end_index, density=windows$density,
      convention="one_based_inclusive", space="nanotel_analyzed_read")
    # Combined motif hits already retain the searched category. Independent
    # calls need their own densities/boundaries, not duplicate motif files.
    if (method %in% c("tvr_only", "tsq_inclusive")) next
    hits <- analysis[[2]]$motif_matches
    marker <- data.frame(motif="", matched_sequence="", start=NA_integer_, end=NA_integer_,
                         role="", max_mismatch=NA_integer_)
    rows <- rbind(marker, hits)
    motifs[[method]] <- cbind(data.frame(read_id=read_id, method=method,
      record_type=c("search_complete", rep("match", nrow(hits))),
      convention="one_based_inclusive", space="nanotel_analyzed_read"), rows)
  }
  stem <- make_barcode_read_stem(serial)
  if (!is.null(tvr_boundary) && !is.null(analyses$tvr_inclusive)) {
    coverage <- report_repeat_coverage(read_id, tvr_boundary,
      analyses$tvr_inclusive[[2]]$motif_matches)
    if (!is.null(coverage)) jsonlite::write_json(coverage,
      file.path(folder, paste0(stem, "_coverage.json")), auto_unbox=TRUE,
      pretty=TRUE, digits=NA)
  }
  sink <- getOption("nanotel.report_batch")
  if (!is.null(sink)) {
    write_report_batch(sink, "index", data.frame(read_key=as.character(serial), read_id=read_id, schema_version=2L))
    write_report_batch(sink, "density", compact_report_rows(do.call(rbind, densities), serial))
    write_report_batch(sink, "motifs", compact_report_rows(do.call(rbind, motifs), serial))
  } else {
    # Compatibility for standalone callers outside the batched pipeline.
    write.csv(do.call(rbind, densities), file.path(folder, paste0(stem, "_density.csv")), row.names=FALSE)
    write.csv(do.call(rbind, motifs), file.path(folder, paste0(stem, "_motifs.csv")), row.names=FALSE, na="")
  }
}


# with a data frame we can further explore the different patterns
# my improvment: fiding the IRanges and making union for overlaps and then
# calculate according to sum(width of the IRanges)
# The calculation is on the full sequence and it is not fit for subsequences
#' use purrr::map to replace the for loops code


# Inputs: sub_irange (Sequence interval whose covered fraction is requested); ranges (Matched
# intervals used for density calculation)
# Outputs: Fraction of the supplied interval covered by matched ranges.
get_sub_density <- function(sub_irange, ranges) {
  #' @title Calculate density of a subsequnce.
  #' @details with a given IRanges of a subsequence and IRanges of patterns,
  #' compute the density of the IRanges within the
  #'        subseuence range.
  #' @param sub_irange: the IRange of the subsequence
  #' @param ranges: The IRanges of the patterns found in the full sequence
  #' @value a numeric which is the density in range [0,1].
  #' @return The density of the patterns in the subseuence according to the
  #' IRanges.
  #' @description  sub_irange = (10, 30), ranges = {(2,8), (16,21), (29,56)} ->
  #' the intersect is {(16,21), (29, 30)} ->
  #                width = 6+2 = 8 , sub_irange width = 21 -> density = 8/21
  #' @examples sub_irange <- IRanges(start = 10, end = 30)
  #'           ranges <- IRanges(start = c(2,16,29), end = c(8,21,56))
  #'           get_sub_density(sub_irange =  sub_irange, ranges = ranges) # 0.38
  #' this compute the desity of iranges of patterns within a given irange of a
  #' subsequence
  return(sum(width(IRanges::intersect(sub_irange, ranges))) / width(sub_irange))
}















# I Can merge the 2 functions to 1 with additional paramater which tells me to return start or end index?
# ' Helper for search_left_patterns
#' I need to think about a pattern which is a list of patterns
#' -> return an start index ( maximal end index)
#' We assume patterns is a list of strings.
#' @param read - A dna seq DNAString
#' @param patterns - A list of Strings , each represen a pattern
#' @param subseq_start - Index for the start of the subsequence we want to check.
#' @param subseq_end - "               end ".
#' @param with_mismatches - If True, allow 1 mismatch.
#' @tvr_patterns - Additional TVR and TSQ patterns, always matched exactly.
#' @returns  - New index, or Inf if there is no updated start index.
# Inputs: read (Imported read record and its available measurements); patterns (Canonical/search
# motifs used by this analysis); subseq_start (Subsequence start on the analyzed-read axis);
# subseq_end (Subsequence end on the analyzed-read axis); with_mismatches (Whether canonical
# searching allows one mismatch); tvr_patterns (Additional selected TVR motifs)
# Outputs: Candidate left boundary, preserving the search sentinel when no hit is found.
multi_pattern_step_left <- function(read,patterns, subseq_start, subseq_end, with_mismatches = FALSE, tvr_patterns = NULL) {
  new_start <- Inf

  if (!is.null(tvr_patterns) && !with_mismatches) { # exact canonical, TVR and TSQ matching
    all_patterns <- unique(unlist(list(patterns, tvr_patterns)))
    for(pat in all_patterns) {
      curr_mp <- matchPattern(pattern = pat, subject = subseq(read, start = subseq_start, end = subseq_end ) )
      if(length(curr_mp) > 0) {
        new_start <- min(new_start, min(start(curr_mp)))
      }
    }

    return(ifelse(new_start == Inf, new_start , as.integer(new_start + subseq_start - 1)) )
  }

  for(pat in patterns) {
    curr_mp <- matchPattern(pattern = pat, subject = subseq(read, start = subseq_start, end = subseq_end), max.mismatch = as.numeric(with_mismatches) )
    if(length(curr_mp) > 0) {
      new_start <- min(new_start, min(start(curr_mp)))
    }
  }
  if(!is.null(tvr_patterns)) {
    for(pat in tvr_patterns) {
      curr_mp <- matchPattern(pattern = pat,
                              subject = subseq(read, start = subseq_start, end = subseq_end),
                              max.mismatch = 0L)
      if(length(curr_mp) > 0) {
        new_start <- min(new_start, min(start(curr_mp)))
      }
    }

  }

  return(ifelse(new_start == Inf, new_start , as.integer(new_start + subseq_start - 1)) )
}



######## Helper functions for more accurate telomere length ##############


#' I need to think about a pattern which is a list of patterns
#' -> return an end index ( maximal end index)
#' We assume patterns is a list of strings.
#' @param read - A dna seq DNAString
#' @param patterns - A list of Strings , each represen a pattern
#' @param subseq_start - Index for the start of the subsequence we want to check.
#' @param subseq_end - "               end ".
#' @param with_mismatches - If True, allow 1 mismatch.
#' @tvr_patterns - Additional TVR and TSQ patterns, always matched exactly.
# Inputs: read (Imported read record and its available measurements); patterns (Canonical/search
# motifs used by this analysis); subseq_start (Subsequence start on the analyzed-read axis);
# subseq_end (Subsequence end on the analyzed-read axis); with_mismatches (Whether canonical
# searching allows one mismatch); tvr_patterns (Additional selected TVR motifs)
# Outputs: Candidate right boundary, preserving the search sentinel when no hit is found.
multi_pattern_step_right <- function(read,patterns, subseq_start, subseq_end, with_mismatches = FALSE, tvr_patterns = NULL) {
  new_end <- -1
  if (!is.null(tvr_patterns) && !with_mismatches) { # exact canonical, TVR and TSQ matching
    all_patterns <- unique(unlist(list(patterns, tvr_patterns)))
    for(pat in all_patterns) {
      curr_mp <- matchPattern(pattern = pat, subject = subseq(read, start = subseq_start, end = subseq_end ) )
      if(length(curr_mp) > 0) {
        new_end <- max(new_end,max(end(curr_mp)))
      }
    }

    return(ifelse(new_end == -1, new_end, new_end + subseq_start - 1) )
  }

  for(pat in patterns) {
    curr_mp <- matchPattern(pattern = pat, subject = subseq(read, start = subseq_start, end = subseq_end), max.mismatch = as.numeric(with_mismatches) )
    if(length(curr_mp) > 0) {
      new_end <- max(new_end,max(end(curr_mp)))
    }
  }
  if(!is.null(tvr_patterns)) {
    for(pat in tvr_patterns) {
      curr_mp <- matchPattern(pattern = pat,
                              subject = subseq(read, start = subseq_start, end = subseq_end),
                              max.mismatch = 0L)
      if(length(curr_mp) > 0) {
        new_end <- max(new_end,max(end(curr_mp)))
      }
    }

  }

  return(ifelse(new_end == -1, new_end, new_end + subseq_start - 1) )
}
# Inputs: read (Imported read record and its available measurements); start_index (Start index);
# subseq_width (Search-window width in base pairs); step_size (Boundary-search step in base pairs);
# max_steps (Maximum number of boundary-search steps); pattern (Filename pattern or recorded search
# motif for this operation); with_mismatch (Whether canonical searching allows one mismatch);
# tvr_patterns (Additional selected TVR motifs)
# Outputs: Refined left search boundary.
search_left_patterns <- function(read, start_index, subseq_width = 18, step_size = 10, max_steps = 4, pattern , with_mismatch = FALSE, tvr_patterns = NULL) {
  #' This function advance to the left to find more patterns for more accurate
  #' start index.
  #' @param read - A dna seq
  #' @param start_index - the index to start from
  #' @param subseq_width - The length of the subseq each time we search.
  #' @param step_size - The step for the subseq each time we move more to the left.
  #' @param max_steps - How many iterations.
  #' @param  pattern - The dna pattern to serach (a single string)
  #' @param tvr_patterns - As with right...
  #' @param with_mismatch - If TRUE allow 1 mismatch.


  assert("Subsequence lengt is not smaller than the Pattern length!", str_length(pattern) <= subseq_width)
  #  I need to set boundary checks: length(pattern) < subseq_width ....
  subseq_start <- max(start_index - subseq_width, 1)
  new_start <- start_index
  for( i in 1:max_steps) {
    curr_end <- min(subseq_start + subseq_width - 1, length(read)) # make sure no out of boundry

    if(is.list(pattern) ) {
      # max for incase returns Inf
      curr_start <- multi_pattern_step_left(read = read, patterns = pattern,
                                            subseq_start = subseq_start, subseq_end = curr_end,
                                            with_mismatches = as.numeric(with_mismatch),
                                            tvr_patterns = tvr_patterns )
      if(curr_start == Inf) { break }
      new_start <- curr_start

    } else {
      if(!is.null(tvr_patterns)) {
        curr_start <- multi_pattern_step_left(read = read, patterns = as.list(pattern),
                                              subseq_start = subseq_start, subseq_end = curr_end,
                                              with_mismatches = with_mismatch, tvr_patterns = tvr_patterns)
        if(curr_start == Inf) { break }
        new_start <- curr_start

      } else { #No list, no TVR's
        curr_mp <- matchPattern(pattern = pattern,
                                subject = subseq(read, start = subseq_start, end = curr_end),
                                max.mismatch = as.numeric(with_mismatch) )
        if(length(curr_mp) == 0) {
          break
        }
        new_start <- min(start(curr_mp)) + subseq_start - 1

      } # End of No list, no TVR's
    }


    # iteration part
    subseq_start_new <- max(subseq_start - step_size +1, 1) # check boundry
    if(subseq_start_new == subseq_start) {break} # we already checked it!
    subseq_start <- subseq_start_new
  }
  return(new_start)

}

# Inputs: read (Imported read record and its available measurements); end_index (End index);
# subseq_width (Search-window width in base pairs); step_size (Boundary-search step in base pairs);
# max_steps (Maximum number of boundary-search steps); pattern (Filename pattern or recorded search
# motif for this operation); with_mismatch (Whether canonical searching allows one mismatch);
# tvr_patterns (Additional selected TVR motifs)
# Outputs: Refined right search boundary.
search_right_patterns <- function(read, end_index, subseq_width = 18, step_size = 10, max_steps = 4, pattern , with_mismatch = FALSE, tvr_patterns = NULL) {
  #' This function advance to the left to find more patterns for more accurate
  #' end index.
  #' @param read - A dna seq DNAString
  #' @param end_index - the index to the end to start from.
  #' @param subseq_width - The length of the subseq each time we search.
  #' @param step_size - The step for the subseq each time we move more to the left.
  #' @param max_steps - How many iterations.
  #' @param  pattern - The dna pattern to serach (a single string)
  #' @param with_mismatch - If TRUE allow 1 mismatch.


  assert("Subsequence length is not smaller than the Pattern length!", str_length(pattern) <= subseq_width)
  # avvoid of limit (end_index > length(read))
  subseq_end <- min(end_index + subseq_width, length(read))
  new_end <- end_index
  for( i in 1:max_steps) {
    # avoid of limit start index (<= 1)
    curr_start <- max(subseq_end - subseq_width + 1, 1)

    if(is.list(pattern) ) {
      # max for incase returns -1
      curr_end <- multi_pattern_step_right(read = read, patterns = pattern,
                                           subseq_start = curr_start, subseq_end = subseq_end,
                                           with_mismatches = with_mismatch, tvr_patterns = tvr_patterns)
      if(curr_end == -1) { break}
      new_end <- curr_end




    } else{
      if(!is.null(tvr_patterns)) {
        curr_end <- multi_pattern_step_right(read = read, patterns = as.list(pattern),
                                             subseq_start = curr_start, subseq_end = subseq_end,
                                             with_mismatches = with_mismatch, tvr_patterns = tvr_patterns)
        if(curr_end == -1) { break}
        new_end <- curr_end


      } else {
        curr_mp <- matchPattern(pattern = pattern,
                                subject = subseq(read, start = curr_start, end = subseq_end ),
                                max.mismatch = as.numeric(with_mismatch) )

        if(length(curr_mp) == 0) {
          break
        }
        new_end <- max(end(curr_mp)) + curr_start - 1 #  adjust index to the full length read



      }
    }
    # iteration part
    # avvoid of limit (end_index > length(read))
    subseq_end_new <- min(subseq_end + step_size +1, length(read))
    if(subseq_end_new == subseq_end) { break}
    subseq_end <- subseq_end_new
  }
  return(new_end)

}



######## End of Helper functions for more accurate telomere length ##############






#' future changes:
#'   1. remove the ID column
#'   2. class: give the class a name according to type "CCCTAA/TTAGGG"
#'   3. Add the middle_point as in the plotTelomere.R
#'   4. use purrr::map / future_map to replace the for loops code
#'   5. Give names to the elements in the list : for example:
#'      m_list[["subtelos]] <- subtelos
#'      ( see the course Foundations of Functional Programming with purrr)
###########3 My cahnge from prev - return a list 0f (df, total_density) ######
# Inputs: dna_seq (DNAString sequence to analyze); patterns (Canonical/search motifs used by this
# analysis); sub_length (Window length in base pairs); min_density (Minimum repeat density as a
# fraction); with_mismatch (Whether canonical searching allows one mismatch); tvr_patterns
# (Additional selected TVR motifs)
# Outputs: List containing candidate windows and their pattern-density measurements.
analyze_subtelos <- function(dna_seq, patterns, sub_length,
                       min_density, with_mismatch = FALSE, tvr_patterns = NULL, density_result = NULL) {
  # return list(subtelos, list_density_mp[1])
  #' @title Analyze the patterns for each subsequence.
  #' @description s split a dna sequence to subsequences and calculate the
  #' density of each subsequence
  #' @param dna_seq: a dna sequence (DNAString object)
  #' @param patterns: a list of patterns or a string of 1 pattern
  #' @param sub_length: The length of the subsequences for split_telo fuction.s
  #' @value a list(data frame of all subtelomeres and their properties ,numeric
  #' for total density)
  #' @return  a list of (a data frame, list(numeric: total density, IRanges for
  #' patterns)
  #' @examples
  # aother option is to create 5 vector s and then make a data.table from them

  # density and iranges of matchPattern
  list_density_mp <- if (is.null(density_result)) get_density_iranges(dna_seq, patterns = patterns, with_mismatch = with_mismatch, tvr_patterns) else density_result
  mp_iranges <- list_density_mp[[2]]
  # get start indexes of "subtelo"
  idx_iranges <- split_telo(dna_seq, sub_length = sub_length)
  # create empty dataframe which will contain all subtelomeres and their
  # properties.
  subtelos <- data.frame(ID = as.integer(), start_index = as.integer(),
                         end_index = as.integer(), density = as.numeric(),
                         class = as.numeric())
  cur_id <- 1             # intitialize ID counter
  # loop through start indexs
  for (i in seq_along(idx_iranges)) {
    subtelo_density <- get_sub_density(sub_irange = idx_iranges[i],
                                      ranges = mp_iranges)
    #TODO : rename -5,1,0 to a facators
    classes <- list("CCCTAA" = -5, "NONE" = 1, "SKIP" = 0)
    ###############3 NEED TO CHANGE FOR AN ARGUMENT OF classes #################
    subtelo_class <- classes$CCCTAA
    if (subtelo_density < min_density) {
      if (subtelo_density < 0.1) {
        subtelo_class <- classes$SKIP
      }else {
        subtelo_class <- classes$NONE
      }
    }
    subtelos <- subtelos %>%
      add_row(ID = cur_id, start_index = start(idx_iranges[i]), end_index =
                end(idx_iranges[i]), density = subtelo_density, class =
                subtelo_class)
    cur_id <- cur_id + 1
  }
  return(list(subtelos, list_density_mp))
}
#  a a list of (a data frame, numeric: total density)

# find a hole inside a telomeric sequence



# max_diff what is the max distance between the end of the read to the end of the telomere
# Inputs: seq_length (Analyzed sequence length in base pairs); subtelos (Window-based telomere
# candidates and densities); max_diff (Maximum allowed gap between candidate windows)
# Outputs: Called IRanges interval, or the existing (-1, -1) missing-call sentinel.
find_right_telo <- function(seq_length, subtelos, max_diff = 200) {

  classes <- list("CCCTAA" = -5, "NONE" = 1, "SKIP" = 0)
  # set score, start, in.a.row to 0,-1,0


  # check also if there is the last were it is bigger.smaller
  start_end_diff <- subtelos[1, "end_index"] - subtelos[1, "start_index"]
  start <- 1
  end <- 1
  # loop through subsequences
  # I need to change it to fit the case when last subseq is in range of [101:150]
  # and  the density is 36/122 < 0.3

  last_i <- 1

  for (i in nrow(subtelos):1){
    subt <- subtelos[i, ]
    if(subt$end_index < seq_length -max_diff) {
      return(IRanges(-1, -1)) # no telomere was found, change to NULL
    }
    # if the subsequence's class is SKIP, NONE or NA, reset values
    if (subt$class == classes$SKIP || subt$class == classes$NONE ||
        is.na(subt$class)) {
      next

    } else {
      # otherwise add one to in.a.row, update score and set start index
      end <- subt$end_index
      last_i <- i
      break
    }
  }

  for(i in last_i:1) {
    subt <- subtelos[i, ]
    if (subt$class == classes$SKIP || subt$class == classes$NONE ||
        is.na(subt$class)) {
      break

    } else {
      # otherwise add one to in.a.row, update score and set start index
      start <- subt$start_index
      last_i <- i
    }
  }


  # check also if there is the last were it is bigger.smaller
  start_end_diff <- subtelos[last_i, "end_index"] - subtelos[last_i, "start_index"]
  if (start > end) {
    end <- start + start_end_diff
  }

  return(IRanges(start = start, end = end))

}  # end of function 'find_right_telo'





# max_diff what is the max distance between the startof the read to the start of the telomere
# Inputs: seq_length (Analyzed sequence length in base pairs); subtelos (Window-based telomere
# candidates and densities); max_diff (Maximum allowed gap between candidate windows)
# Outputs: Called IRanges interval, or the existing (-1, -1) missing-call sentinel.
find_left_telo <- function(seq_length, subtelos, max_diff = 200) {

  classes <- list("CCCTAA" = -5, "NONE" = 1, "SKIP" = 0)
  # set score, start, in.a.row to 0,-1,0



  start <- 1
  end <- 1

  last_i <- 1

  # start searching the telo patterns from the start (left)
  for (i in seq_len(nrow(subtelos))){
    subt <- subtelos[i, ]
    if(subt$start > max_diff) {
      return(IRanges(-1, -1)) # no telomere was found, change to NULL
    }
    # if the subsequence's class is SKIP, NONE or NA, reset values
    if (subt$class == classes$SKIP || subt$class == classes$NONE ||
        is.na(subt$class)) {
      next
    }else {
      # otherwise add one to in.a.row, update score and set start index
      start <- subt$start
      last_i <- i
      break
    }

  }

  last_i_start <- last_i

  for (i in last_i:nrow(subtelos)){
    subt <- subtelos[i, ]
    # if the subsequence's class is SKIP, NONE or NA, reset values
    if(subt$class == classes$SKIP || subt$class == classes$NONE ||
       is.na(subt$class)) {
      break
    }else {
      # otherwise add one to in.a.row, update score and set start index
      end<- subt$end
    }
  }
  # check also if there is the last were it is bigger.smaller
  start_end_diff <- subtelos[last_i_start, "end_index"] - subtelos[last_i_start, "start_index"]
  if (start > end) {
    end <- start + start_end_diff
  }

  return(IRanges(start = start, end = end))


} # end of function 'find_left_telo'


# I need to put The classes as an arument ?
#' Have to create help-functions to this function - it is too long"
#' help_function1 : find_the_start_of_telomere
#' help_function2: find_the_end_of_telomere
#' end/start should both use the find first/last pattern at the edges
#' check_edges: see if we can go forethere with the indice: using the
#' matchpattern with mismathes = 2 + indels.
#' If density < density_thr:
#' First check if the low density is to the right or left.
#' Then rerun with 15,10 only to one of start/end accordingly.
#' Should solve problems like
# Inputs: seq_length (Analyzed sequence length in base pairs); subtelos (Window-based telomere
# candidates and densities); min_in_a_row (Minimum consecutive windows supporting a candidate);
# min_density_score (Min density score)
# Outputs: Called IRanges interval, or the existing (-1, -1) missing-call sentinel.
find_telo_position <- function(seq_length, subtelos, min_in_a_row = 3,
                        min_density_score = 2) { # 15,10 for sub_length == 20
  #' @title: Find the position of the Telomere(subsequence) within the seuence.
  #' @description:  Find the start and end indices of the subsequence within the
  #'  sequence according to a data frame.
  #' @usage
  #' @param seq_length: The length of the read.
  #' @param subtelos: data frame of a subseuences indices, density and class
  #' (from the analyze_subtelos)
  #' @value An IRanges object of length 1.
  #' @return (start, end) irange  of the Telomere.
  #' @examples

  ###############3 NEED TO CHANGE FOR AN ARGUMENT OF classes ###################
  #' we have a problem in this function: Error in if (subt$class == classes$SKIP
  #'  | subt$class == classes$NONE |  : argument is of length zero
  classes <- list("CCCTAA" = -5, "NONE" = 1, "SKIP" = 0)
  # set score, start, in.a.row to 0,-1,0

  score <- 0.0
  start <- -1
  end <- -1
  in_a_row <- 0
  # check also if there is the last were it is bigger.smaller
  start_end_diff <- subtelos[1, "end_index"] - subtelos[1, "start_index"]

  # loop through subsequences
  # I need to change it to fit the case when last subseq is in range of [101:150]
  # and  the density is 36/122 < 0.3
  end_position <- 0 # for end loop
  for (i in seq_len(nrow(subtelos))){
    subt <- subtelos[i, ]
    # if the subsequence's class is SKIP, NONE or NA, reset values
    if (subt$class == classes$SKIP || subt$class == classes$NONE ||
        is.na(subt$class)) {
      score <- 0
      start <- -1
      in_a_row <- 0
    }else {
      # otherwise add one to in.a.row, update score and set start index
      in_a_row <- in_a_row + 1
      score <- score + subt$density
      if (start == -1) {
        start <- subt$start_index
      }
    }
    #' if more than MIN.IN.A.ROW subtelomeres were found and the overall score
    #' is high enough, return start index
    if (in_a_row >= min_in_a_row && score >= min_density_score) {
      end_position <- i + 1
      break
    }
  }
  if (end_position == 0) {
    return(IRanges(-1, -1)) # no telomere was found, change to NULL
  }


  #' search for end from the last subsequence (backward to finding stat incase
  #' there is island of non-telomeric subsequence)
  end <- -1
  score <- 0.0
  in_a_row <- 0
  # what if end_position >= nrow(subtelos) - min_in_a_row +1
  if(end_position >= nrow(subtelos) - min_in_a_row +1 ) {
    i <- nrow(subtelos)
    subt <- subtelos[i, ]
    while(subt$class != classes$CCCTAA && i > end_position) {
      i <- i-1
      subt <- subtelos[i, ]
    }
    end <- subt$end_index
  } else {
    for (i in nrow(subtelos):end_position){
      subt <- subtelos[i, ]
      # if the subsequence's class is SKIP, NONE or NA, reset values
      if (subt$class == classes$SKIP || subt$class == classes$NONE ||
          is.na(subt$class)) {
        score <- 0.0
        end <- -1
        in_a_row <- 0
      } else {
        # otherwise add one to in.a.row, update score and set start index
        in_a_row <- in_a_row + 1
        score <- score + subt$density
        if (end == -1) {
          end <- subt$end_index
        }
      }

      #' if more than MIN.IN.A.ROW subtelomeres were found and the overall score
      #' is high enough, return start index
      if (in_a_row >= min_in_a_row && score >= min_density_score) {
        break
      }
    }

  }

  if (start > end) {
    end <- start + start_end_diff
  }

  return(IRanges(start = start, end = end))
}

# if right_edge is false then we check left edge instead
# Inputs: read (Imported read record and its available measurements); patterns (Canonical/search
# motifs used by this analysis); with_mismatch (Whether canonical searching allows one mismatch);
# tvr_patterns (Additional selected TVR motifs); seq_length (Analyzed sequence length in base
# pairs); subtelos (Window-based telomere candidates and densities); analyze_list (Intermediate
# boundary-search results); right_edge (Whether to select the right-end candidate)
# Outputs: Boundary-search result for the selected read end and matching mode.
find_telo_position_wraper <- function(read, patterns, with_mismatch, tvr_patterns, seq_length, subtelos, analyze_list,right_edge = FALSE) {


  # I need to change the name to subseq_irange ( 1:100, 101:200 ,....)
  telo_position <- find_telo_position(seq_length = seq_length,
                                      subtelos = analyze_list[[1]],
                                      min_in_a_row = 3, min_density_score = 2)
  # TODO: duplicated code: use a helper functio....

  # change the name to iranges_patterns
  irange_telo <- analyze_list[[2]][[2]]



  # Go over the telo_index and add gray area to the plot ....


  #' Onc ew have the Telomere indices calculate the density of the patterns
  #' within it's range.
  telo_density <- get_sub_density(telo_position, analyze_list[[2]][[2]])

  #' My last change: 22/10/2023
  #' Check first the length of the telomere, before setting min_in_a_row
  num_rows <- width(telo_position) %/% global_subseq_length
  if (telo_density < 0.85 && num_rows > 5) {
    min_rows <- ifelse(num_rows <= 7, yes = num_rows - 2, no = 7)
    min_density <- 0.6*min_rows
    telo_position <- find_telo_position(seq_length = seq_length,
                                        subtelos = analyze_list[[1]], min_in_a_row = min_rows,
                                        min_density_score = min_density)

    #' Onc ew have the Telomere indices calculate the density of the patterns
    #' within it's range.
    #telo_density <- get_sub_density(telo_position, analyze_list[[2]][[2]])
  }



  # I should validate start <= end
  start_acc <- get_accurate_start(telo_start = start(telo_position) , irange_telo = irange_telo)
  end_acc <- get_accurate_end(telo_end = end(telo_position), irange_telo = irange_telo)

  if (start_acc > end_acc) {
    end_acc <- start_acc
  }

  telo_position <- IRanges(start = start_acc, end = end_acc)


  if(width(telo_position) < 100) {
    # find at the telomere at the edge
    if(right_edge) { # right edge TTAGGG
      telo_position <- find_right_telo(seq_length = seq_length, subtelos = subtelos)
    } else { # left edge CCCTAA
      telo_position <- find_left_telo(seq_length = seq_length, subtelos = subtelos)
    }
  }

  # new args: read, patterns, with_mismatch, tvr_patterns
  # use match pattern steps for more accurate results
  if(end(telo_position) < length(read)) {
    end_acc <- search_right_patterns(read = read , end_index = end(telo_position) + 1, pattern = patterns , with_mismatch = with_mismatch, tvr_patterns = tvr_patterns)
  } else {
    end_acc <- end(telo_position)
  }
  if(start(telo_position) > 1) {
    start_acc  <- search_left_patterns(read = read, start_index = start(telo_position) -1 , pattern =  patterns, with_mismatch = with_mismatch, tvr_patterns = tvr_patterns)
  } else {
    start_acc <- start(telo_position)
  }


  telo_position <- IRanges(start = start_acc, end = end_acc)

  return (telo_position)
}


# get the telomere end index, with more accuracy
# find_telo_position gives only the indices according to the subseqs
# When using the package : give option for a function as argument for the end/start
# Inputs: telo_end (Current telomere end in base pairs); irange_telo (Matched repeat intervals used
# to refine the boundary)
# Outputs: Refined repeat-supported end coordinate, or the existing missing sentinel.
get_accurate_end <- function(telo_end, irange_telo) {
  #' try more accurate: take the max of which and also check new_end >=
  #' new_start before updating the IRange object
  if(telo_end == -1) {
    return(-1)
  }
  e_index <- telo_end
  iranges_end <- which(end(irange_telo) %in% (e_index - 99):e_index)
  if (length(iranges_end) > 0) {
    #end(telo_position) <- end(irange_telo[iranges_end[1]])}
    # take the last pattern in range ( max(end))
    e_index <- max(end(irange_telo[iranges_end]))
    # make sure end >= start

  }
  # take to consideration if the end is above 100length for exmple 1:216 is (1:100, 102:216)
  # check next 100 block if partial ...
    # change 20 to subseq_length/3
  iranges_end <- which(end(irange_telo) %in% (telo_end + 1 ):(telo_end+50)  )
  if (length(iranges_end) > 0) {
      #end(telo_position) <- end(irange_telo[iranges_end[1]])}
      # take the last pattern in range ( max(end))
    e_index <- max(end(irange_telo[iranges_end]))

  }


  return(e_index)

}

#' This function adjust to a pattern of length ~6.
#' @param telo_start - the start position according to subseqs
#' @param irange_telo - The paterns iranges.
# Inputs: telo_start (Current telomere start in base pairs); irange_telo (Matched repeat intervals
# used to refine the boundary)
# Outputs: Refined repeat-supported start coordinate.
get_accurate_start <- function(telo_start, irange_telo) {
  if(telo_start == -1) {
    return(telo_start)
  }

  s_index <- telo_start
  first_50 <- get_sub_density(IRanges(start = telo_start, width = 50), ranges = irange_telo)
  # This means probably the subseq is half telomeric
  if(first_50 < 0.3) {
    iranges_start <- which(start(irange_telo) %in% (s_index+48):(s_index + 99))
    #message("start index if the first subseq is partial: ", iranges_start2) # to remove 2
    if (length(iranges_start) > 0) {
      telo_start <- min(start(irange_telo[iranges_start]))
      #message("The start index after iranges which check for -20: ", start(telo_position2)) # to remove 5
    }
    # search for pattern before, check range of 16 bases ( for the case when 2 patterns are at the end...)
    iranges_start <- which(start(irange_telo) %in% (s_index+33):(s_index + 48))
    if (length(iranges_start) > 0) {
      telo_start <- min(start(irange_telo[iranges_start]))
      #message("The start index after iranges which check for -20: ", start(telo_position2)) # to remove 5
    }
  } else {
    # check + option to look in the prev subseq
    iranges_start <- which(start(irange_telo) %in% s_index:(s_index + 99))
    if (length(iranges_start) > 0) {
      telo_start <- min(start(irange_telo[iranges_start]))
    }
    if(first_50 >= 0.72){
      # check before (if prev 100 have at the end TTAGGG pattern) search last 20
      iranges_start <- which(start(irange_telo) %in% (s_index-36):(s_index-1) )
      if (length(iranges_start) > 0) {
        telo_start <- min(start(irange_telo[iranges_start]))
      }
    }

  }

  return(telo_start)
}


#' get a single read find and analyze the telomeric patterns in it.
#' Plot graphs and return a summary row.
#' This function is too long - make it more readable and shorter
#' get rid of the id, instead use a shortcut od the read_id as name: once done
#' with all the reads -> reaname all the files accoding to the final df.
#' Also make dir for each different type of plot
#' right_edge - if the telomere is expected to be to the right: NNNN...NNN(TTAGGG)n
# Shared typed schema for read, worker and run-level summary tables.
# Empty workers must carry the same optional columns as populated workers.
empty_telomere_summary <- function(tvr_patterns = NULL, summary_only = FALSE) {
  df <- data.frame(Serial = integer(), sequence_ID = character(),
                   sequence_length = integer(), telo_density = double()
                   , Telomere_start = integer(), Telomere_end = integer(),
                   Telomere_length = integer(), telo_density_mismatch = double()
                   , Telomere_start_mismatch = integer(), Telomere_end_mismatch = integer(),
                   Telomere_length_mismatch = integer() )

  if(!is.null(tvr_patterns)) {
    df <- data.frame(Serial = integer(), sequence_ID = character(),
                     sequence_length = integer(), telo_density = double()
                     , Telomere_start = integer(), Telomere_end = integer(),
                     Telomere_length = integer(), telo_density_mismatch = double()
                     , Telomere_start_mismatch = integer(), Telomere_end_mismatch = integer(),
                     Telomere_length_mismatch = integer(),
                     telo_density_mismatch_tvr = double()
                     , Telomere_start_mismatch_tvr = integer(), Telomere_end_mismatch_tvr = integer(),
                     Telomere_length_mismatch_tvr = integer())
  }

  if (!is.null(tvr_patterns) && global_tsq_pattern %in% unlist(tvr_patterns)) {
    df$tsq_tandem_counts <- character()
    for (suffix in c("_tsq", "_tvr_only")) {
      df[[paste0("telo_density", suffix)]] <- double()
      for (field in c("Telomere_start", "Telomere_end", "Telomere_length"))
        df[[paste0(field, suffix)]] <- integer()
    }
  }
  # Retain compact coverage facts even when detailed tracks are skipped.
  if (summary_only) {
    df$repeat_coverage <- character()
    df$repeat_summary <- character()
  }

  df
}

# Inputs: current_seq (Read sequence currently being analyzed); current_serial (Original read
# number); pattern_list (Canonical and selected TVR search motifs); min_density (Minimum repeat
# density as a fraction); output_dir (Directory for generated outputs); tvr_patterns
# (Additional selected TVR motifs); right_edge (Whether to select the right-end candidate);
# summary_only (Whether to omit individual-read pages from the report)
# Outputs: Per-read summary row with measurements and boundary calls.
analyze_read <- function(current_seq, current_serial, pattern_list, min_density,
                         output_dir, tvr_patterns, right_edge = FALSE,
                         summary_only = FALSE ) {
  current_fastq_name <- names(current_seq)
  current_seq_unlist <- unlist(current_seq)

  # returns a a list of (a data frame, list(numeric: total density,iranges))
  analyze_list <- analyze_subtelos(dna_seq = current_seq_unlist, patterns =
                                     pattern_list, min_density = min_density, sub_length = global_subseq_length, with_mismatch = FALSE)


  # new args: read, patterns, with_mismatch, tvr_patterns
    # I need to change the name to subseq_irange ( 1:100, 101:200 ,....)
  telo_position <- find_telo_position_wraper(read = current_seq_unlist, patterns = pattern_list,with_mismatch = FALSE, tvr_patterns = NULL, seq_length = length(current_seq_unlist), subtelos = analyze_list[[1]], analyze_list = analyze_list , right_edge = right_edge)




  if(global_max_mismatch > 0) {
    analyze_list2 <- analyze_subtelos(dna_seq = current_seq_unlist, patterns =
                                       pattern_list, min_density = min_density, sub_length = global_subseq_length, with_mismatch = TRUE)

    telo_position2 <- find_telo_position_wraper(read = current_seq_unlist, patterns = pattern_list,with_mismatch = TRUE, tvr_patterns = NULL
      , seq_length = length(current_seq_unlist), subtelos = analyze_list2[[1]], analyze_list = analyze_list2, right_edge = right_edge)
  } else {
    # Keep the established output schema, but make its mismatch-named values
    # identical to the exact-match analysis when mismatches are disabled.
    analyze_list2 <- analyze_list
    telo_position2 <- telo_position
  }





  telo_position3 <- NULL
  irange_telo3 <- NULL
  analyze_list3 <- NULL
  telo_density3 <- NULL

  # Now check with TVR's
  if(!is.null(tvr_patterns)) {
    # The mismatch option applies to canonical repeats; TVR and TSQ matches are exact.
    analyze_list3 <- analyze_subtelos(dna_seq = current_seq_unlist, patterns =
                pattern_list, min_density = min_density, sub_length = global_subseq_length, with_mismatch = global_max_mismatch > 0, tvr_patterns = tvr_patterns)
    telo_position3 <- find_telo_position_wraper(read = current_seq_unlist, patterns = pattern_list, with_mismatch = global_max_mismatch > 0, tvr_patterns = tvr_patterns,
                                                seq_length = length(current_seq_unlist), subtelos = analyze_list3[[1]], analyze_list = analyze_list3, right_edge = right_edge )


  }




  # Independent boundaries: TSQ never contributes to the ordinary TVR call.
  separate_calls <- list()
  if (!is.null(tvr_patterns) && global_tsq_pattern %in% unlist(tvr_patterns)) {
    groups <- list(tsq_inclusive=global_tsq_pattern,
                   tvr_only=base::setdiff(unlist(tvr_patterns), global_tsq_pattern))
    for (method in names(groups)) {
      group <- groups[[method]]
      if (!length(group)) next
      if (base::setequal(group, unlist(tvr_patterns))) {
        analysis <- analyze_list3; boundary <- telo_position3
      } else {
        selected <- if (length(group) > 1L) as.list(group) else group
        # Reuse the combined search hits: only windows and boundary refinement
        # differ between categories. Do not rescan the entire read per category.
        hits <- analyze_list3[[2]]$motif_matches
        hits <- hits[hits$role == "canonical" | hits$motif %in% group, , drop=FALSE]
        ranges <- IRanges::reduce(IRanges::IRanges(start=hits$start, end=hits$end))
        density_result <- list(sum(width(ranges))/length(current_seq_unlist), ranges, motif_matches=hits)
        analysis <- analyze_subtelos(dna_seq=current_seq_unlist, patterns=pattern_list,
          min_density=min_density, sub_length=global_subseq_length,
          with_mismatch=global_max_mismatch > 0, tvr_patterns=selected, density_result=density_result)
        boundary <- find_telo_position_wraper(read=current_seq_unlist, patterns=pattern_list,
          with_mismatch=global_max_mismatch > 0, tvr_patterns=selected,
          seq_length=length(current_seq_unlist), subtelos=analysis[[1]],
          analyze_list=analysis, right_edge=right_edge)
      }
      separate_calls[[method]] <- list(analysis=analysis, boundary=boundary)
    }
  }
  df <- empty_telomere_summary(tvr_patterns, summary_only)

  # last update
  telo_density <- get_sub_density(telo_position, analyze_list[[2]][[2]])
  telo_density2 <- get_sub_density(telo_position2, analyze_list2[[2]][[2]])
  if(!is.null(tvr_patterns)) {
    telo_density3 <- get_sub_density(telo_position3, analyze_list3[[2]][[2]])
  }


  if (max(width(telo_position), width(telo_position2) )  < 30 && is.null(tvr_patterns)) {
    df <- add_row(df, Serial = NA, sequence_ID = NA, sequence_length = NA
                  , telo_density = NA, Telomere_start = NA, Telomere_end = NA,
                  Telomere_length = NA, telo_density_mismatch = NA,
                  Telomere_start_mismatch = NA, Telomere_end_mismatch = NA,
                  Telomere_length_mismatch = NA)

    return(df)
  } # not considered a Telomere
  if(!is.null(tvr_patterns)) {
    if (max(width(telo_position), width(telo_position2), width(telo_position3) )  < 30 ) {
      df <- add_row(df, Serial = NA, sequence_ID = NA, sequence_length = NA
                    , telo_density = NA, Telomere_start = NA, Telomere_end = NA,
                    Telomere_length = NA, telo_density_mismatch = NA,
                    Telomere_start_mismatch = NA, Telomere_end_mismatch = NA,
                    Telomere_length_mismatch = NA, telo_density_mismatch_tvr = NA,
                    Telomere_start_mismatch_tvr = NA, Telomere_end_mismatch_tvr = NA,
                    Telomere_length_mismatch_tvr = NA )

      return(df)
    } # not consid
  }

  if(!summary_only) {
    export_report_density(current_fastq_name, current_serial,
      c(list(exact=analyze_list, mismatch=analyze_list2, tvr_inclusive=analyze_list3),
        lapply(separate_calls, function(call) call$analysis)), dirname(output_dir), if (is.null(tvr_patterns)) NULL else telo_position3)
    # changed to compressed file: 2026-01-29
    output_telo_fasta <- file.path(output_dir, paste0(make_barcode_read_stem(current_serial),
                                                      ".fasta.gz"))
    write_read_fasta(current_seq, output_telo_fasta)


  }

  # check for valid telomere iranges
  telo_length <- width(telo_position)
  telo_start <- start(telo_position)
  telo_end <- end(telo_position)
  if(start(telo_position) == -1) {
    telo_length <- NA
    telo_start <- NA
    telo_end <- NA
    telo_density <- NA
  }
  telo_length2 <- width(telo_position2)
  telo_start2 <- start(telo_position2)
  telo_end2 <- end(telo_position2)
  if(start(telo_position2) == -1) {
    telo_length2 <- NA
    telo_start2 <- NA
    telo_end2 <- NA
    telo_density2 <- NA
  }


  if(is.null(tvr_patterns)) {
  df <- df %>%
    add_row(Serial = current_serial, sequence_ID = current_fastq_name,
    sequence_length = length(current_seq_unlist), telo_density = telo_density
    , Telomere_start = telo_start, Telomere_end = telo_end, Telomere_length =
      telo_length, telo_density_mismatch = telo_density2,
    Telomere_start_mismatch = telo_start2, Telomere_end_mismatch = telo_end2,
    Telomere_length_mismatch = telo_length2)
  } else {

    telo_length3 <- width(telo_position3)
    telo_start3 <- start(telo_position3)
    telo_end3 <- end(telo_position3)
    if(start(telo_position3) == -1) {
      telo_length3 <- NA
      telo_start3 <- NA
      telo_end3 <- NA
      telo_density3 <- NA
    }

    df <- df %>%
      add_row(Serial = current_serial, sequence_ID = current_fastq_name,
              sequence_length = length(current_seq_unlist), telo_density = telo_density
              , Telomere_start = telo_start, Telomere_end = telo_end, Telomere_length =
                telo_length, telo_density_mismatch = telo_density2,
              Telomere_start_mismatch = telo_start2, Telomere_end_mismatch = telo_end2,
              Telomere_length_mismatch = telo_length2,
              telo_density_mismatch_tvr = telo_density3
              , Telomere_start_mismatch_tvr = telo_start3, Telomere_end_mismatch_tvr = telo_end3,
              Telomere_length_mismatch_tvr = telo_length3)
  }
  for (method in names(separate_calls)) {
    call <- separate_calls[[method]]; boundary <- call$boundary
    suffix <- if (method == "tsq_inclusive") "_tsq" else "_tvr_only"
    valid <- length(boundary) == 1L && start(boundary) > 0L && width(boundary) > 0L
    df[[paste0("Telomere_start", suffix)]] <- if (valid) start(boundary) else NA_integer_
    df[[paste0("Telomere_end", suffix)]] <- if (valid) end(boundary) else NA_integer_
    df[[paste0("Telomere_length", suffix)]] <- if (valid) width(boundary) else NA_integer_
    df[[paste0("telo_density", suffix)]] <- if (valid) get_sub_density(boundary, call$analysis[[2]][[2]]) else NA_real_
  }
  tsq_call <- separate_calls[["tsq_inclusive"]]
  if (!is.null(tsq_call)) {
    tandems <- report_tsq_tandems(tsq_call$boundary, tsq_call$analysis[[2]]$motif_matches)
    if (!is.null(tandems)) df$tsq_tandem_counts <- as.character(jsonlite::toJSON(
      tandems, auto_unbox=TRUE, digits=NA))
  }
  if (summary_only && !is.null(tvr_patterns) && !is.na(telo_start3) && telo_start3 > 0) {
    coverage <- report_repeat_coverage(current_fastq_name, telo_position3,
      analyze_list3[[2]]$motif_matches)
    if (!is.null(coverage)) df$repeat_coverage <- as.character(jsonlite::toJSON(
      coverage, auto_unbox=TRUE, digits=NA))
    summary <- report_repeat_summary(telo_position3, analyze_list3[[2]]$motif_matches)
    if (!is.null(summary)) df$repeat_summary <- as.character(jsonlite::toJSON(
      summary, auto_unbox=TRUE, digits=NA))
  }
  return(df)

} # End of analyze_read


# Inputs: path (File or directory path)
# Outputs: Opens the selected NanoTel log destination for the run.
open_nanotel_log <- function(path) {
  logfile <- logr::log_open(path, logdir=FALSE)
  # logr installs recursive error/warning logging hooks. If logging itself
  # fails, these can obscure the original worker error and prevent clean exit.
  # Explicit log_print calls remain enabled; Rscript reports conditions to
  # stderr and exits nonzero on an unhandled error for the workflow to detect.
  options(error=NULL, warning.expression=NULL, warn=1)
  logfile
}

# Inputs: path (File or directory path)
# Outputs: Creates the destination when needed and returns its path invisibly.
ensure_output_directory <- function(path) {
  # Another worker may create the same directory between the two checks.
  if (!dir.exists(path)) dir.create(path, recursive=TRUE, showWarnings=FALSE)
  if (!dir.exists(path)) stop("Cannot create NanoTel output directory: ", path, call.=FALSE)
  if (file.access(path, 2L) != 0L) {
    stop("NanoTel output directory is not writable: ", path, call.=FALSE)
  }
  invisible(path)
}

# Inputs: sequence (DNA sequence in the analyzed orientation); path (File or directory path); writer
# (FASTA writer called with the prepared sequence)
# Outputs: Writes the sequence and returns its path invisibly.
write_read_fasta <- function(sequence, path, writer=Biostrings::writeXStringSet) {
  # Check in the worker that actually saves the read, not only in the parent.
  # Preserve the low-level warning (disk full, quota, permissions, etc.) that
  # would otherwise be hidden behind future's Reduce/value error wrapper.
  warnings <- character()
  tryCatch({
    ensure_output_directory(dirname(path))
    withCallingHandlers(
      writer(sequence, path, compress=TRUE),
      # Inputs: w (W)
      # Outputs: Handles the FASTA-writer warning without changing sequence data.
      warning=function(w) {
        warnings <<- c(warnings, conditionMessage(w))
      })
  }, error=function(e) {
    detail <- paste(unique(c(conditionMessage(e), warnings)), collapse="; ")
    stop("Cannot save NanoTel read FASTA: ", path, "\n", detail,
         "\nCheck output-directory permissions, free disk space and disk quota on the analysis machine.",
         call.=FALSE)
  })
  invisible(path)
}

# Inputs: output_dir (Directory for generated outputs); summary_only (Whether to omit
# individual-read pages from the report); log_path (Log path)
# Outputs: Creates the selected NanoTel output directories and log destination.
create_dirs <- function(output_dir, summary_only = FALSE, log_path = NULL) {
  ensure_output_directory(output_dir)

  if (!summary_only) {
    reads_dir <- paste(output_dir, "reads", sep = "/")
    ensure_output_directory(reads_dir)
  }

  log_dir <- if (is.null(log_path)) file.path(output_dir, "log") else dirname(log_path)
  ensure_output_directory(log_dir)
}

# Inputs: input_path (Input path)
# Outputs: Normalized barcode filename prefix.
get_barcode_file_prefix <- function(input_path) {
  # Normalize the input folder name into a stable file prefix so every output
  # file can be traced back to its barcode, even when folder names vary
  # between barcode01, barcode_01, bc01, etc.
  barcode_name <- basename(normalizePath(input_path, mustWork = FALSE))
  match <- regmatches(barcode_name, regexpr("(barcode|bc)[_-]*[0-9]+", barcode_name, ignore.case = TRUE))

  if (length(match) > 0 && nzchar(match[1])) {
    barcode_num <- regmatches(match[1], regexpr("[0-9]+", match[1]))
    return(paste0("barcode", sprintf("%02d", as.integer(barcode_num))))
  }

  safe_name <- gsub("[^A-Za-z0-9_-]+", "_", barcode_name)
  gsub("^_+|_+$", "", safe_name)
}

# Inputs: serial_num (Serial num)
# Outputs: Read-artifact filename stem based on the original serial number.
make_barcode_read_stem <- function(serial_num) {
  # Per-read outputs are created before the final summary files, so they use a
  # global prefix initialized from the input barcode before processing starts.
  barcode_prefix <- get0("global_barcode_file_prefix", envir = globalenv(), ifnotfound = "")
  prefix <- if (nzchar(barcode_prefix)) paste0(barcode_prefix, "_") else ""
  paste0(prefix, "read", serial_num)
}

############## Running functions ###############################################

# Inputs: sample_telomeres (Candidate reads selected for detailed motif analysis); pattern_list
# (Canonical and selected TVR search motifs); output_dir (Directory for generated outputs);
# serial_start (Serial start); min_density (Minimum repeat density as a fraction);
# tvr_patterns (Additional selected TVR motifs); right_edge
# (Whether to select the right-end candidate); summary_only (Whether to omit individual-read pages
# from the report); report_batch_dir (Report batch dir)
# Outputs: Detailed candidate-read analysis table.
search_patterns <- function(sample_telomeres, pattern_list,
     output_dir, serial_start = 1, min_density, tvr_patterns, right_edge = FALSE,
     summary_only = FALSE, report_batch_dir = NULL) {
  if (!is.null(report_batch_dir)) {
    sink <- open_report_batch(report_batch_dir)
    previous <- options(nanotel.report_batch=sink)
    on.exit({ lapply(sink$connections, close); options(previous) }, add=TRUE)
  }
  #'@title Search given Patterns over a DNA sequences.
  #'@param sample_telomeres: the DNAString Set of the reads.
  #'@param pattern_list: a list of patterns or a string of 1 pattern.
  #'@param output_dir:
  #'@param serial_start: The first id serial number.
  #'@param min_density: The minimal density of the patterns in a sequence to
  #'be consider relevant.
  #'@param tvr_patterns : Additional patterns for TVR's.
  #'@param right_edge : if the expected telomere is to be to the rigth : NNNN....NNN(TTAGGG)n
  #'@param return: Returns a data frame of the reads.


  # output_telo_csv <- paste(output_dir, paste(csv_name, "csv", sep = "."), sep = "/")
  # output_telo_fasta <- paste(output_dir, paste("reads", "fasta", sep = "."),  sep = "/")
  output_reads <- paste(output_dir, "reads", sep = "/")

  #  I HAVE ADDED TLOMERE LENGTH, START @ END



  df <- empty_telomere_summary(tvr_patterns, summary_only)

  # add telo density : get_sub_density <- function(sub_irange, ranges){
  # For the fasta output of the reads which pass the filter
  #telomeres_dna_string_set <- DNAStringSet()
  current_serial <- serial_start
  # try map instead
  for (i in seq_along(sample_telomeres)) {
    #' now make corrections with mismax+indels patterns both for start and end
    #' of the telomere
    #telo_position <- gray_area_adges(telo_position, current_seq)
    curr_df <- analyze_read(current_seq = sample_telomeres[i], current_serial =
               current_serial, pattern_list = pattern_list, min_density =
               min_density, output_dir = output_reads, tvr_patterns = tvr_patterns,
               right_edge = right_edge, summary_only = summary_only)
    # not a telomeric read
    if (is.na(curr_df[1,1])) {
      next

    } else {
      df <- dplyr::rows_append(df, curr_df)
    }

    #telomeres_dna_string_set <- append(telomeres_dna_string_set, values = sample_telomeres[i])
    current_serial <- current_serial + 1
  } # end of for loop
  # need to save the df in a file
  #write.csv(x = df, file = output_telo_csv, row.names = FALSE)
  #writeXStringSet(telomeres_dna_string_set, output_telo_fasta)
  #message("Done!")
  #'  now what's left is to extract the sequences from fasta to fasta using
  #'  the read_names list file ( 3 files )
  return(df)
} # end of the function search_patterns



# need to create parApply for filter
# Inputs: sequence (DNA sequence in the analyzed orientation); patterns (Canonical/search motifs
# used by this analysis); min_density (Minimum repeat density as a fraction)
# Outputs: TRUE when repeat density meets the supplied cutoff.
filter_density <- function(sequence, patterns, min_density = 0.18) {
  #'
  total_density <- 0
  # union of all the IRanges of all the patterns in the list
  mp_all <- IRanges::IRanges()
  if (is.list(patterns)) {
    patterns <- unique(patterns)  # make sure there are no dups
    for (pat in patterns){
      mp_all <- IRanges::union(mp_all, Biostrings::matchPattern(pattern = pat,
                subject = unlist(sequence), max.mismatch = 0, fixed = FALSE))
    }
  } else {
    mp_all <- Biostrings::matchPattern(pattern = patterns,
              subject = unlist(sequence), max.mismatch = 0, fixed = FALSE)
    mp_all <- IRanges::union(mp_all, mp_all) # incase there are overlaps
  }

  total_density <- sum(IRanges::width(mp_all)) / nchar(sequence)
  return(total_density >= min_density)

}


# Inputs: input_path (Input path); format (Input sequence format: FASTA or FASTQ)
# Outputs: Sequence paths matching the selected FASTA/FASTQ format.
list_sequence_files <- function(input_path, format = "fastq") {
  # Barcode directories may contain README and other non-sequence files.
  suffix <- switch(format,
                   fastq = "\\.(fastq|fq)(\\.gz)?$",
                   fasta = "\\.(fasta|fa|fna)(\\.gz)?$",
                   stop("Unsupported sequence format: ", format))
  files <- if (dir.exists(input_path)) {
    list.files(input_path, pattern = suffix, full.names = TRUE,
               recursive = TRUE, ignore.case = TRUE)
  } else if (file.exists(input_path) && grepl(suffix, input_path, ignore.case = TRUE)) {
    input_path
  } else {
    character()
  }
  if (length(files) == 0L) {
    stop("No ", format, " files found in: ", input_path)
  }
  files
}


# update : 2023-02-10 change the function to use parallel::parLapply instead of mclapply for Windows compatibility
# Inputs: samples (Read sequences and their source metadata); patterns (Canonical/search motifs used
# by this analysis); do_rc (Whether to analyze reverse-complemented sequences); num_of_cores (Num of
# cores); subread_width (Subread width); right_edge (Whether to select the right-end candidate);
# trimm_length (Trimm length)
# Outputs: Candidate sequence records, or the existing NA sentinel when none qualify.
filter_reads <- function(samples, patterns, do_rc = TRUE,
                         num_of_cores = 10,
                         subread_width = 200,
                         right_edge = TRUE,
                         trimm_length = 70) {

  samps_1000 <- samples[width(samples) >= 1e3]

  if (isTRUE(do_rc)) {
    samps_1000 <- Biostrings::reverseComplement(samps_1000)
  }

  # Detect OS
  is_windows <- .Platform$OS.type == "windows"

  # Create cluster
  cl_type <- if (is_windows) "PSOCK" else "FORK"
  cl <- parallel::makeCluster(num_of_cores, type = cl_type)

  if (is_windows) {
    parallel::clusterEvalQ(cl, {
      suppressPackageStartupMessages(require(BiocGenerics))
      suppressPackageStartupMessages(require(S4Vectors))
      suppressPackageStartupMessages(require(IRanges))
      suppressPackageStartupMessages(require(Biostrings))
    })
  }

  if (right_edge) {
    trimm_length <- -(trimm_length + 1)

    samp_100 <- parallel::parLapply(
      cl,
      samps_1000,
      subseq,
      end = trimm_length,
      width = subread_width
    )
  } else {
    samp_100 <- parallel::parLapply(
      cl,
      samps_1000,
      subseq,
      start = trimm_length + 1,
      width = subread_width
    )
  }

  if (is_windows) {
    parallel::clusterExport(
      cl,
      c("filter_density", "patterns", "global_min_density"),
      envir = environment()
    )

    logical_100 <- parallel::parLapply(
      cl,
      samp_100,
      filter_density,
      patterns = patterns,
      min_density = global_min_density * 0.8
    )
  } else {

    logical_100 <- parallel::mclapply(
      X = samp_100,
      FUN = filter_density,
      patterns = patterns,
      min_density = global_min_density * 0.8,
      mc.cores = num_of_cores
    )
  }

  stopCluster(cl)

  rm(samp_100)

  names(logical_100) <- NULL
  samps_1000 <- samps_1000[unlist(logical_100)]

  if (length(samps_1000) < 1) {
    message("No read have passed the filtration at run_with_rc_and_filter!")
    return(NA)
  }

  samps_1000
}



################## final function ######################################################

# Inputs: workers (Number of parallel workers)
# Outputs: Configures the future execution plan.
set_nanotel_parallel_plan <- function(workers = 8) {
  if (future::supportsMulticore()) {
    plan(multicore, workers = workers)
  } else {
    plan(multisession, workers = workers)
  }
}

# run The future par search_pattern on small chunks inorder to save memory.
# Inputs: input_path (Input path); output_path (Output path); format (Input sequence format: FASTA
# or FASTQ); nrec (Maximum number of sequence records per chunk); patterns (Canonical/search motifs
# used by this analysis); do_rc (Whether to analyze reverse-complemented sequences); use_filter (Use
# filter); right_edge (Whether to select the right-end candidate); tvr_patterns (Additional selected
# TVR motifs); summary_only (Whether to omit individual-read pages from the report)
# Outputs: Collected chunk-worker results and saved barcode artifacts.
run_future_worker_chuncks <- function(input_path, output_path, format = c("fasta","fastq"), nrec = 10000,
                                      patterns, do_rc, use_filter = FALSE, right_edge = TRUE, tvr_patterns,
                                      summary_only = FALSE) {

  report_batch_dir <- NULL
  if (!summary_only) {
    report_batch_dir <- tempfile("nanotel-report-batches-")
    dir.create(report_batch_dir)
    on.exit(unlink(report_batch_dir, recursive=TRUE), add=TRUE)
  }
  filepath <- list_sequence_files(input_path, format)

  files <- open_input_files(filepath)

  i <- 0
  dna_length <- integer(0)

  df_summary <- empty_telomere_summary(tvr_patterns, summary_only)

  options(future.globals.maxSize = 1048576000*1.5) # 1.5 gigabyte max
  set_nanotel_parallel_plan(workers = 8)
  serial_start <- 1
  while (TRUE) {
    i <- i + 1
    ## Load 40 records at a time. Each new call to readDNAStringSet()
    ## picks up where the previous call left.
    dna_reads <- readDNAStringSet(files, nrec=nrec, format = format)


    if (length(dna_reads) == 0L)
      break

    if(do_rc) {
      dna_reads <- reverseComplement(dna_reads)
    }
    cat("processing chunk", i, "...\n")
    ## do something with 'dna' ...
    dna_length <- c(dna_length, width(dna_reads))

    if(use_filter) {
      plan(sequential)
      dna_reads <- filter_reads(samples = dna_reads , patterns = patterns , do_rc = FALSE, right_edge = right_edge, num_of_cores = 8)
      set_nanotel_parallel_plan(workers = 8)
      if(is.na(dna_reads[1])) {next}
    }

    groups_length <- 8
    seq_over_length <- seq.int(from = 1, by = 1, length.out = length(dna_reads))
    if( length(seq_over_length) < groups_length) {
      plan(sequential)
      curr_df <- search_patterns(sample_telomeres = dna_reads, pattern_list = patterns, output_dir = output_path, min_density = global_min_density, serial_start = serial_start , tvr_patterns = tvr_patterns, right_edge = right_edge, summary_only = summary_only, report_batch_dir = report_batch_dir)
      df_summary <- union_all(df_summary, curr_df)
    } else {

      groups <- 1:groups_length
      split_seq <- suppressWarnings(split(x = seq_over_length, f = groups))

      df1 %<-% search_patterns(sample_telomeres = dna_reads[split_seq$`1`], pattern_list = patterns, output_dir = output_path, min_density = global_min_density, serial_start = serial_start, tvr_patterns = tvr_patterns, right_edge = right_edge, summary_only = summary_only, report_batch_dir = report_batch_dir )
      df2 %<-% search_patterns(sample_telomeres = dna_reads[split_seq$`2`], pattern_list = patterns, output_dir = output_path, min_density = global_min_density, serial_start = length(split_seq$`1`) + serial_start , tvr_patterns = tvr_patterns, right_edge = right_edge, summary_only = summary_only, report_batch_dir = report_batch_dir)
      df3 %<-% search_patterns(sample_telomeres = dna_reads[split_seq$`3`], pattern_list = patterns, output_dir = output_path, min_density = global_min_density, serial_start = length(unlist(split_seq[1:2])) + serial_start, tvr_patterns = tvr_patterns, right_edge = right_edge, summary_only = summary_only, report_batch_dir = report_batch_dir)
      df4 %<-% search_patterns(sample_telomeres = dna_reads[split_seq$`4`], pattern_list = patterns, output_dir = output_path, min_density = global_min_density, serial_start = length(unlist(split_seq[1:3])) + serial_start, tvr_patterns = tvr_patterns, right_edge = right_edge, summary_only = summary_only, report_batch_dir = report_batch_dir)
      df5 %<-% search_patterns(sample_telomeres = dna_reads[split_seq$`5`], pattern_list = patterns, output_dir = output_path, min_density = global_min_density, serial_start = length(unlist(split_seq[1:4])) + serial_start, tvr_patterns = tvr_patterns, right_edge = right_edge, summary_only = summary_only, report_batch_dir = report_batch_dir)
      df6 %<-% search_patterns(sample_telomeres = dna_reads[split_seq$`6`], pattern_list = patterns, output_dir = output_path, min_density = global_min_density, serial_start = length(unlist(split_seq[1:5])) + serial_start, tvr_patterns = tvr_patterns, right_edge = right_edge, summary_only = summary_only, report_batch_dir = report_batch_dir)
      df7 %<-% search_patterns(sample_telomeres = dna_reads[split_seq$`7`], pattern_list = patterns, output_dir = output_path, min_density = global_min_density, serial_start = length(unlist(split_seq[1:6])) + serial_start, tvr_patterns = tvr_patterns, right_edge = right_edge, summary_only = summary_only, report_batch_dir = report_batch_dir)
      df8 %<-% search_patterns(sample_telomeres = dna_reads[split_seq$`8`], pattern_list = patterns, output_dir = output_path, min_density = global_min_density, serial_start = length(unlist(split_seq[1:7])) + serial_start, tvr_patterns = tvr_patterns, right_edge = right_edge, summary_only = summary_only, report_batch_dir = report_batch_dir)

      df_summary <- Reduce(union_all , list(df_summary, df1,df2,df3, df4, df5, df6, df7, df8))
      # end of parallel try
    }

    if (nrow(df_summary) > 0L) {
      serial_start <- max(df_summary$Serial) + 1
    }

  }

  plan(sequential)
  if (!is.null(report_batch_dir)) merge_report_batches(report_batch_dir, output_path, get_barcode_file_prefix(input_path))
  ans_list <- list(df_summary, dna_length)
  names(ans_list) <- c("df_summary", "all_reads_length_vec")

  return(ans_list)

}


# TODO
# todo:
#' 2. Make a package
#' 3. upload to git
#' 4. Add a subtelo- only reads (Telomers are trimmed off)
#' 5. Give trimm barcode option (length of nt to trimm..1300/30)
#' 7. Create  a log file : https://cran.r-project.org/web/packages/logr/vignettes/logr.html
#' 8. Use the suppressMessages or suppressPackageStartupMessages(library_wich give as saving 7*7....) : https://campus.datacamp.com/courses/defensive-r-programming/early-warning-systems?ex=5
#' 9. Use message() to show to process of work % and how much time it takes ....
#' 10. Check the warrnings : see https://campus.datacamp.com/courses/defensive-r-programming/early-warning-systems?ex=10
#' 11. Add error messages using stop for bad arguments... see https://campus.datacamp.com/courses/defensive-r-programming/early-warning-systems?ex=13
#' 12. Use try for fixing bad arguments such as: 'fasa -> use fasta instead ....
#' 13. Make parallel option for searh_patterns - done using future ( dn't work on windows os)
#' 14. some reads (about 1 %) do,'t pass the filteration but are found to be telomeric with search_patterns: as the telomere start after more than 160 first bases
#' 15. Add interactive plotly plot with telomeric density and sequence letters on buttom + ability to zoom in/out ....
#' 16. Add the matchPatterns with indels and max.mis == 2 at the edges -> plot at the graph as yellow for pattern with error....
#' 17. Swith instersect.Vector/union.Vector to IRange intersect  - done.
#' 18. use assertive  https://www.rdocumentation.org/packages/assertive/versions/0.3-6 for checking assert_is_numeric(..) ....
#' 19. Use cuncks inorder to save memory
#' 20. Try use parApply instead of future: see Parallel Programming in R start of chapter 2
#' ( with FORK it should work beacause of shared memo: mclapply is faster (uses fork))
#' 21. Use the microbenchmarck and profvis toos to find were we can make it more efficient.
#' (see Parallel Programming in R ,chapter 1 )
#' 22. Use another filter: count "TTAGGG" pattern and if it is 5-10% (depends
#' on the read length and sample) count it as a suspect for telomeric read and
#' if is is filtered out check why. (could be read with a bug on indices)
#' 23. Perhaps splitting telomere into 2 or more telomeric region will solve
#' problems of incorrect indices or [-1,-1] indices.





if(is.null(opt$patterns)) {
  stop("Missing required parameter:  --patterns", call.=FALSE)
}

if (is.null(opt$save_path)) {
  stop("Missing required parameter:  --save_path", call.=FALSE)
}

if (is.null(opt$input_path)) {
  stop("Missing required parameter:  --input_path", call.=FALSE)
}

if( is.null(opt$format)) {
  stop("Format should be a string fastq or fasta")
}


# check pattern
extract_patterns <- compose(unlist, partial(str_split, pattern = "\\s+") )
cur_patterns <- extract_patterns(opt$patterns)
if(length(cur_patterns) > 1) {
  cur_patterns <- as.list(cur_patterns)
}

cur_tvr_patterns <- NULL
if(!is.null(opt$tvr_patterns)) {
  cur_tvr_patterns <- extract_patterns(opt$tvr_patterns)
  if(length(cur_tvr_patterns) > 1) {
    cur_tvr_patterns <- as.list(cur_tvr_patterns)
  }
}


global_tsq_pattern <- toupper(opt$tsq_pattern)
global_min_density <- opt$min_density
global_subseq_length <- opt$subseq_length
global_max_mismatch <- max(0L, min(1L, as.integer(opt$max_mismatch)))
# TODO: consider omitting redundant canonical *_mismatch columns from NanoTel
# outputs when the effective mismatch allowance is 0. This is a future schema
# change: coordinate CSV producers, downstream readers, existing-file compatibility,
# GUI/reporting and packaging tests before implementing it. Keep the columns for now.

lockBinding("global_subseq_length", globalenv())
lockBinding("global_min_density", globalenv())
lockBinding("global_max_mismatch", globalenv())
lockBinding("global_tsq_pattern", globalenv())


# log function blueprint : summary(sample), %telomeric_reads , summary(telo_read) ...
# I need to create a log funcion : with ifelse ( if telomeric patterns were found or not -> no one passed the filteration or df isempty ....)
# test log file
create_dirs(output_dir = opt$save_path, summary_only = opt$summary_only,
            log_path = opt$log_path)
tmp <- if (is.null(opt$log_path)) {
  file.path(opt$save_path, "log", "run.log")
} else {
  opt$log_path
}

# Open log
# The log path already includes its directory; logr must not add another /log.
lf <- open_nanotel_log(tmp)
log_print('Telomere Analyzer  version v1.1.9-beta 2026-02-19', hide_notes = TRUE, console = FALSE) # Send message to log
t1 <- Sys.time()
log_print(base::paste("Work started at:", toString(t1)), hide_notes = TRUE, console = FALSE) # Send message to log

log_print("############### The input argumetns for this run: ################", hide_notes = TRUE, console = FALSE)
if(opt$rc) {
  log_print("Reverse complement was applied on the input reads.", hide_notes = TRUE, console = FALSE)
}
log_print(base::paste("The patterns to search:", opt$patterns), hide_notes = TRUE, console = FALSE)
log_print(base::paste("The sub-sequence length  is:",
                      toString(opt$subseq_length)), hide_notes = TRUE, console = FALSE)
log_print(base::paste("The minimal density for a telomeric subseq:",
                      toString(opt$min_density)), hide_notes = TRUE, console = FALSE)

if(!is.null(cur_tvr_patterns) ) {
  log_print(base::paste("Additional Telomere variant repeats patterns were added:",
                        opt$tvr_patterns), hide_notes = TRUE, console = FALSE)
}


log_print("##################################################################",hide_notes = TRUE, , console = FALSE)

log_print("The input files:", hide_notes = TRUE, console = FALSE)
# add the names of the files which we analyze.


for (filepath in list_sequence_files(opt$input_path, opt$format)) {
  log_print(filepath, hide_notes = TRUE, console = FALSE)
}

# Use one barcode prefix for all files produced by this NanoTel run. It must be
# initialized before run_future_worker_chuncks because per-read plots and FASTA
# files are created inside nested analysis functions.
barcode_name <- get_barcode_file_prefix(opt$input_path)
global_barcode_file_prefix <- barcode_name
log_print(base::paste("Resolved barcode file prefix:", barcode_name),
          hide_notes = TRUE, console = FALSE)


ans_list <- run_future_worker_chuncks(input_path = opt$input_path, output_path = opt$save_path,
    format = opt$format, nrec = opt$nrec, patterns = cur_patterns, do_rc = opt$rc,
    use_filter = opt$use_filter, right_edge = opt$check_right_edge,
    tvr_patterns = cur_tvr_patterns, summary_only = opt$summary_only)

global_total_length <- length(ans_list$all_reads_length_vec)

log_print(base::paste("Total reads in sample:", global_total_length), hide_notes = TRUE, console = FALSE)
log_print("Summary statistics of the sample reads length:", hide_notes = TRUE, console = FALSE)
log_print(summary(ans_list$all_reads_length_vec), hide_notes = TRUE, console = FALSE)

# try FastqStreamerList for streaming, n records each yield ....

#now try parallel using future package
# prev cod
# df_summary <- search_patterns(sample_telomeres = dna_reads, pattern_list = curr_patterns, output_dir = args[2], min_density = 0.3, serial_start = )



log_print(base::paste0("Number of reads which identified as Telomeric: ", nrow(ans_list$df_summary)), hide_notes = TRUE, console = FALSE)
log_print(base::paste0("% of total reads: ", toString(round( (100*nrow(ans_list$df_summary)) / global_total_length, 2 ) ), "%" ), hide_notes = TRUE, console = FALSE)

# summary statistics of the Telomeric reads
log_print("Summary statistics for the Telomeric reads:", hide_notes = TRUE, console = FALSE)
log_print("reads length:", hide_notes = TRUE, console = FALSE)
log_print(summary(ans_list$df_summary$sequence_length), hide_notes = TRUE, console = FALSE)
log_print("Telomere length:", hide_notes = TRUE, console = FALSE)
log_print(summary(ans_list$df_summary$Telomere_length), hide_notes = TRUE, console = FALSE)

log_print("Telomere length with 1 mismatch allowed:", hide_notes = TRUE, console = FALSE)
log_print(summary(ans_list$df_summary$Telomere_length_mismatch), hide_notes = TRUE, console = FALSE)


if(!is.null(cur_tvr_patterns)) {
  log_print('Combined telomere length including selected TVRs and TSQ (run matching settings):', hide_notes = TRUE, console = FALSE)
  log_print(summary(ans_list$df_summary$Telomere_length_mismatch_tvr), hide_notes = TRUE, console = FALSE)
}

if ("Telomere_length_tsq" %in% names(ans_list$df_summary)) {
  log_print("Telomere length including TSQ (independent call):", hide_notes=TRUE, console=FALSE)
  log_print(summary(ans_list$df_summary$Telomere_length_tsq), hide_notes=TRUE, console=FALSE)
}
if ("Telomere_length_tvr_only" %in% names(ans_list$df_summary) &&
    length(setdiff(unlist(cur_tvr_patterns), global_tsq_pattern))) {
  log_print("Telomere length including TVRs, excluding TSQ (independent call):", hide_notes=TRUE, console=FALSE)
  log_print(summary(ans_list$df_summary$Telomere_length_tvr_only), hide_notes=TRUE, console=FALSE)
}

# Write top-level NanoTel outputs with the barcode in the filename. This avoids
# generic names like reads_ids.txt and makes files self-describing outside their
# barcode directory.
summary_file <- file.path(opt$save_path, paste0(barcode_name, "_summary.csv"))
write_csv(x = ans_list$df_summary,
          file = summary_file)
log_print(base::paste("NanoTel summary CSV saved to:", summary_file),
          hide_notes = TRUE, console = FALSE)
if (!opt$summary_only) {
  reads_ids_file <- file.path(opt$save_path, paste0(barcode_name, "_reads_ids.txt"))
  write_lines(x = ans_list$df_summary$sequence_ID,
              file = reads_ids_file)
  log_print(base::paste("NanoTel read IDs saved to:", reads_ids_file),
            hide_notes = TRUE, console = FALSE)
}

# =====================================================================
# POST-PROCESSING ANALYSIS (only runs when --analysis flag is set)
# =====================================================================
if (isTRUE(opt$analysis)) {

  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    stop("The --analysis JSON export requires the jsonlite package.")
  }
  if ((!requireNamespace("plotly", quietly = TRUE) ||
      !requireNamespace("htmltools", quietly = TRUE))) {
    stop("The --analysis interactive plots require plotly and htmltools.")
  }

  # Select canonical measurements explicitly for this analysis.
  # TVR measurements are not used.
  analysis_columns <- if (global_max_mismatch == 0L) {
    c(
      density = "telo_density",
      start   = "Telomere_start",
      end     = "Telomere_end",
      length  = "Telomere_length"
    )
  } else {
    c(
      density = "telo_density_mismatch",
      start   = "Telomere_start_mismatch",
      end     = "Telomere_end_mismatch",
      length  = "Telomere_length_mismatch"
    )
  }

  # --- Step 1: Filter ---
  df_step1_filtered <- ans_list$df_summary %>%
    dplyr::filter(
      .data[[analysis_columns[["density"]]]] >= opt$min_density,
      .data[[analysis_columns[["start"]]]] <= opt$max_telomere_start
    )

  # KM uses density/start-filtered reads BEFORE running-median edge filtering.
  # Keep raw estimates and diagnostics internally, including withheld results.
  # Neutral internal names separate the measurement from its matching mode.
  km_result <- NULL
  if (isTRUE(opt$include_km)) {
    km_input <- data.frame(
      sequence_length = df_step1_filtered$sequence_length,
      telomere_length = df_step1_filtered[[analysis_columns[["length"]]]],
      telomere_end    = df_step1_filtered[[analysis_columns[["end"]]]]
    )
    km_result <- fit_km_result(km_input)
  } else {
    log_print("KM disabled: skipping KM fitting and KM exports.",
              hide_notes = TRUE, console = FALSE)
  }

  df_filtered <- df_step1_filtered %>%

    # --- Step 2: Sort by sequence length descending ---
    dplyr::arrange(desc(sequence_length)) %>%

    # --- Step 3: Add running median and difference columns ---
    dplyr::mutate(
      # vapply preserves numeric(0) when no reads pass the filters.
      TelLenMM_RunningMed = vapply(
        seq_len(dplyr::n()),
        function(i) median(
          .data[[analysis_columns[["length"]]]][seq_len(i)]
        ),
        numeric(1)
      ),
      SeqLen_minus_RunMed = sequence_length - TelLenMM_RunningMed
    )

  # Save pre-final-filter data for the plot (shows the full x-range up to the crossing point)
  df_for_plot <- df_filtered %>%
    dplyr::mutate(read_index = seq_len(dplyr::n()))

  # --- Step 4: max edge distance < sequence length - running median ---
  df_filtered <- df_filtered %>%
    dplyr::filter(SeqLen_minus_RunMed > opt$max_edge_distance)

  # Preserve source filter decisions for reporting; do not change membership.
  filter_audit <- ans_list$df_summary
  density_values <- filter_audit[[analysis_columns[["density"]]]]
  start_values <- filter_audit[[analysis_columns[["start"]]]]
  edge_values <- df_for_plot$SeqLen_minus_RunMed[match(filter_audit$Serial, df_for_plot$Serial)]
  filter_reasons <- vapply(seq_len(nrow(filter_audit)), function(i) {
    reasons <- character()
    if (!is.finite(density_values[i])) reasons <- c(reasons, "Telomere density unavailable")
    else if (density_values[i] < opt$min_density)
      reasons <- c(reasons, sprintf("Telomere density %.4f below minimum %.4f", density_values[i], opt$min_density))
    if (!is.finite(start_values[i])) reasons <- c(reasons, "Telomere start unavailable")
    else if (start_values[i] > opt$max_telomere_start)
      reasons <- c(reasons, sprintf("Telomere start %s bp exceeds maximum %s bp", start_values[i], opt$max_telomere_start))
    if (!length(reasons) && (!is.finite(edge_values[i]) || edge_values[i] <= opt$max_edge_distance))
      reasons <- c(reasons, if (!is.finite(edge_values[i])) "Edge-filter measurement unavailable" else
        sprintf("Edge filter: read length minus running median telomere length (%s bp) is not greater than %s bp", edge_values[i], opt$max_edge_distance))
    if (!length(reasons)) "Passed NanoTel filters" else paste(reasons, collapse="; ")
  }, character(1))
  if (!isTRUE(opt$summary_only)) {
  audit_dir <- file.path(opt$save_path, "report_details")
  dir.create(audit_dir, recursive=TRUE, showWarnings=FALSE)
  write_csv(data.frame(sequence_ID=filter_audit$sequence_ID, Serial=filter_audit$Serial,
    reason=filter_reasons), file.path(audit_dir, paste0(barcode_name, "_filter_reasons.csv")))
  }

  # Write filtered sorted summary
  write_csv(x = df_filtered,
            file = file.path(opt$save_path,
                             paste0(barcode_name, "_filtered_sorted_summary.csv")))

  # --- Stats .txt ---

  # KM survival fit: event = 1 when the telomere is fully captured in the read
  # (enough margin between sequence end and telomere end), 0 = censored.
  if (isTRUE(opt$include_km)) df_filtered <- df_filtered %>%
    dplyr::mutate(
      margin = sequence_length - .data[[analysis_columns[["end"]]]],
      event  = as.integer(margin >= BUFFER)
    )

  n_reads        <- nrow(df_filtered)
  n_complete     <- if (isTRUE(opt$include_km)) sum(df_filtered$event == 1) else NULL
  n_censored     <- if (isTRUE(opt$include_km)) sum(df_filtered$event == 0) else NULL
  censoring_rate <- if (isTRUE(opt$include_km) && n_reads > 0L) n_censored / n_reads else NA_real_

  med_telo <- median(df_filtered[[analysis_columns[["length"]]]])
  # This is NanoTel.R's FINAL-filter population. r_analysis computes its own
  # percentage with the same threshold but may add a minimum-read-length filter;
  # the two percentages can differ and must not be treated as interchangeable.
  pct_short <- if (n_reads > 0L) round(100 * mean(
    df_filtered[[analysis_columns[["length"]]]] < opt$short_telomere_threshold_bp,
    na.rm = TRUE
  ), 1) else NA_real_


  # Inputs: x (Value being checked or formatted)
  # Outputs: Formatted integer text.
  fmt <- function(x) format(round(x), big.mark = ",", scientific = FALSE)

  results_lines <- c(
    paste0("Results for ", barcode_name),
    "==========================================",
    paste0("Number of telomeric reads (post-filtration) : ", fmt(n_reads)),
    "",
    paste0("Median Telomeric Length (post-filtration)  : ", fmt(med_telo), " bp"),
    paste0("% of telomeres shorter than ", opt$short_telomere_threshold_bp,
           " bp : ", pct_short, "%")
  )

  if (!is.null(km_result)) results_lines <- c(results_lines,
    paste0("Complete Telomeric Reads : ", fmt(n_complete)),
    paste0("Incomplete Telomeric Reads : ", fmt(n_censored)),
    paste0("Censoring Rate : ", round(100 * censoring_rate, 1), "%"), "", format_km_report(km_result))
  if (n_reads == 0L) {
    empty_message <- "No reads passed the NanoTel analysis filters; length and percentage statistics are unavailable."
    results_lines <- c(results_lines, "", empty_message)
    log_print(empty_message, hide_notes = TRUE, console = FALSE)
  }

  write_lines(results_lines,
              file.path(opt$save_path, paste0(barcode_name, "_results.txt")))

  analysis_report <- make_analysis_report(
    barcode_name, n_reads, n_complete, n_censored, censoring_rate,
    med_telo, pct_short, opt$short_telomere_threshold_bp, km_result
  )
  # Query alignment coordinates refer to the original input sequence. Record
  # the transformation applied by iter_fastq_files so reports can project them
  # onto the analyzed read without guessing from the reference strand.
  analysis_report$total_read_length_median_bp <- if (length(ans_list$all_reads_length_vec)) median(ans_list$all_reads_length_vec) else NULL
  analysis_report$analyzed_read_reverse_complemented <- isTRUE(opt$rc)
  jsonlite::write_json(
    analysis_report,
    file.path(opt$save_path, paste0(barcode_name, "_analysis.json")),
    auto_unbox = TRUE, pretty = TRUE, null = "null", na = "null", digits = NA
  )
  # One barcode row is also usable after a standalone NanoTel.R --analysis run.
  if (!is.null(km_result)) write_csv(
    make_km_statistics(barcode_name, km_input, km_result),
    file.path(opt$save_path, paste0(barcode_name, "_km_statistics.csv")), na = ""
  )

  {
  # --- Telomere plot (uses pre-final-filter data so x-axis extends to the crossing point) ---
  # Preserve the line plot's pre-edge population; the histogram uses final reads.
  # Selected exact/mismatch columns are shared with filtering/KM, not TVR columns.
  line_data <- make_analysis_plot_data(df_for_plot, analysis_columns, opt$max_edge_distance, opt$include_km)
  histogram_data <- make_telomere_histogram_data(
    make_analysis_plot_data(df_filtered, analysis_columns, opt$max_edge_distance, opt$include_km)
  )
  save_analysis_plot(
    make_telomere_line_plot(line_data, barcode_name, global_max_mismatch),
    file.path(opt$save_path, paste0(barcode_name, "_telomere_plot"))
  )
  save_analysis_plot(
    make_telomere_histogram_plot(histogram_data, barcode_name, global_max_mismatch, include_km = opt$include_km),
    file.path(opt$save_path, paste0(barcode_name, "_telomere_histogram"))
  )

  } # detailed analysis plots: full mode only
} # end --analysis block

t2 <- Sys.time()


log_print(base::paste("Work ended at:", toString(t2)), hide_notes = TRUE, console = FALSE)
# Close log
log_close(footer = FALSE)
writeLines(readLines(lf))
