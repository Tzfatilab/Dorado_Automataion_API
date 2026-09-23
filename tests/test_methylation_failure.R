# Load just the pipeline function, without loading production R dependencies.
expressions <- parse('dorado_workflow/r_analysis/main_analysis_pipeline.R')
for (expr in expressions) {
  if (is.call(expr) && identical(expr[[1]], as.name('<-')) &&
      identical(expr[[2]], as.name('main_r_analysis_pipeline'))) eval(expr)
}
load_required_packages <- function() NULL
read_config <- function(...) list(
  nanotel_analysis = list(summary_only = TRUE), mapping_analysis = list(),
  methylation_analysis = list(output_dir = tempdir()),
  run_nanotel_analysis = FALSE, run_mapping_analysis = FALSE,
  run_methylation_analysis = TRUE, stop_on_error = TRUE
)
log_message <- function(...) NULL
mapping_has_successful_results <- function(...) TRUE
mapping_has_methylation_results <- function(...) TRUE
create_temp_config <- function(...) tempfile()
rep_str <- function(...) ''
file.remove <- function(...) TRUE
system <- function(...) 7L
error <- tryCatch(main_r_analysis_pipeline('unused'), error = identity)
stopifnot(inherits(error, 'error'), grepl('methylation analysis failure', conditionMessage(error)))
system <- function(...) 0L
result <- main_r_analysis_pipeline('unused')
stopifnot(!is.null(result$methylation))
cat('Methylation success/failure regression checks passed\n')
