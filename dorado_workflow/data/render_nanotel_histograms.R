#!/usr/bin/env Rscript
# Render original NanoTel figures from the dashboard's exported populations.
# Inputs: JSON request path and JSON output path supplied as CLI arguments.
# Outputs: Named Plotly specifications; no filtering or repeat detection is run.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L) stop("Expected histogram request and output paths")
script_file <- sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE)[[1]])
script_file <- gsub("~+~", " ", script_file, fixed = TRUE)
source(file.path(dirname(normalizePath(script_file)), "nanotel_histogram.R"))
requests <- jsonlite::fromJSON(args[[1]], simplifyVector = FALSE)
figures <- list()
for (request in requests) {
  lengths <- unlist(request$lengths_bp, use.names = FALSE)
  ids <- unlist(request$read_ids, use.names = FALSE)
  reads <- data.frame(
    read_id = as.character(ids), telomere_length_bp = as.numeric(lengths),
    # Missing completeness evidence remains unknown. Never infer censoring
    # from length or from absence of a saved rug trace.
    event = rep(NA_integer_, length(lengths))
  )
  histogram <- make_telomere_histogram_data(reads)
  figure <- make_telomere_histogram_plot(histogram, request$barcode, request$mismatch_allowance)
  figures[[request$id]] <- jsonlite::fromJSON(
    as.character(plotly::plotly_json(figure, jsonedit = FALSE)), simplifyVector = FALSE)
}
jsonlite::write_json(figures, args[[2]], auto_unbox = TRUE, null = "null", na = "null", digits = NA)
