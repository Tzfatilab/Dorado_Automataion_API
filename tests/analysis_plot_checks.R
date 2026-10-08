# Load functions only: no FASTQ processing, mixture fitting or research simulations.
args <- commandArgs(trailingOnly = TRUE)
expressions <- parse(file = args[[1]])
needed <- c("BUFFER", "KM_MAX_RELATIVE_CI_WIDTH_PCT", "KM_REPORT_MESSAGES",
            "assess_km_result", "fit_km_result", "format_km_report",
            "make_analysis_report", "make_km_statistics", "make_analysis_plot_data",
            "analysis_barcode_title", "make_telomere_line_plot",
            "make_telomere_histogram_data", "make_telomere_histogram_plot",
            "save_analysis_plot", "save_telomere_histogram_png")
for (expr in expressions) {
  if (is.call(expr) && identical(expr[[1]], as.name("<-")) &&
      as.character(expr[[2]]) %in% needed) eval(expr)
}
check <- function(x) stopifnot(isTRUE(x))
dir.create(args[[2]], recursive = TRUE, showWarnings = FALSE)
fixture <- data.frame(sequence_ID = c("read1 metadata", "read2", "read3"),
  sequence_length = c(12000, 7000, 5000),
  telo_density = c(.9, .9, .9), Telomere_start = c(1, 1, 1),
  Telomere_length = c(4000, 6000, 4800), Telomere_end = c(4000, 6980, 4950),
  telo_density_mismatch = c(.95, .95, .95), Telomere_start_mismatch = c(1, 1, 1),
  Telomere_length_mismatch = c(5000, 6800, 4951),
  Telomere_end_mismatch = c(5000, 6950, 4951),
  TelLenMM_RunningMed = c(4000, 5000, 4800), SeqLen_minus_RunMed = c(8000, 2000, 200))
for (allowance in c(0L, 1L)) {
  suffix <- if (allowance == 0L) "" else "_mismatch"
  columns <- c(length = paste0("Telomere_length", suffix), end = paste0("Telomere_end", suffix))
  data <- make_analysis_plot_data(fixture, columns, 300)
  check(identical(data$read_id, c("read1", "read2", "read3")))
  check(identical(data$telomere_length_bp, fixture[[columns[["length"]]]]))
  check(identical(data$event, if (allowance == 0L) c(1L, 0L, 1L) else c(1L, 1L, 0L)))
  check(identical(data$retained_by_edge_filter, c(TRUE, TRUE, FALSE)))
  h <- make_telomere_histogram_data(data[data$retained_by_edge_filter, ])
  check(sum(h$bins$count) == 2 && abs(sum(h$bins$pct) - 100) < 1e-10)
  reference <- hist(h$reads$telomere_length_bp,
                    breaks = pretty(range(h$reads$telomere_length_bp), n = 45L),
                    plot = FALSE, include.lowest = TRUE)
  check(identical(h$bins$count, reference$counts))
  check(identical(h$bins$lower_bp, head(reference$breaks, -1L)))
  line <- plotly::plotly_build(make_telomere_line_plot(data, "barcode01", allowance))
  check(length(line$x$data) == 3 && length(line$x$data[[1]]$x) == 3)
  check(grepl(if (allowance == 0L) "exact" else "mismatch", line$x$data[[2]]$name))
  plot <- plotly::plotly_build(make_telomere_histogram_plot(h, "barcode01", allowance))
  check(sum(plot$x$data[[1]]$y) == 2)
  if (allowance == 0L) {
    check(length(plot$x$data[[3]]$x) == 1) # Censored read counted AND in rug.
    check(plot$x$data[[3]]$x == 6000)
  }
  check(nrow(h$trend) == 512)
  check(max(abs(h$trend$pct - h$trend$count * 100 / nrow(h$reads))) < 1e-10)
  check(plot$x$layout$yaxis$domain[1] > plot$x$layout$yaxis2$domain[2])
  check(length(plot$x$layout$updatemenus[[1]]$buttons) == 2)
}
# Equal lengths, empty final population, and invalid lengths need usable plots.
single <- data[1, , drop = FALSE]
single$telomere_length_bp <- 5000
check(sum(make_telomere_histogram_data(single)$bins$count) == 1)
invalid <- data
invalid$telomere_length_bp <- c(NA_real_, Inf, 0)
h <- make_telomere_histogram_data(invalid)
check(h$excluded == 3 && nrow(h$reads) == 0)
save_analysis_plot(make_telomere_line_plot(data[FALSE, ], "barcode01", 1L),
                   file.path(args[[2]], "empty_line"))
save_analysis_plot(make_telomere_histogram_plot(h, "barcode01", 1L),
                   file.path(args[[2]], "empty_histogram"))
save_telomere_histogram_png(h, file.path(args[[2]], "empty_histogram.png"), "barcode01", 1L)

# Execute the actual --analysis block with a small deterministic summary fixture.
library(dplyr)
library(readr)
library(ggplot2)
library(ggprism)
ans_list <- list(df_summary = fixture)
global_max_mismatch <- 0L
barcode_name <- "barcode01"
opt <- list(save_path = args[[2]], min_density = .5, max_telomere_start = 150,
            max_edge_distance = 300, short_telomere_threshold_bp = 2000, analysis = TRUE)
block <- Filter(function(x) is.call(x) && identical(x[[1]], as.name("if")) &&
                  identical(x[[2]], quote(isTRUE(opt$analysis))), as.list(expressions))[[1]]
eval(block)
check(nrow(df_for_plot) == 3 && nrow(df_filtered) == 2)
check(nrow(line_data) == 3 && sum(histogram_data$bins$count) == 2)
check(identical(km_input$telomere_length, fixture$Telomere_length))
cat("Analysis plot checks passed\n")
