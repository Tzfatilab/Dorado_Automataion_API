# Focused deterministic checks; load only KM helpers, never run NanoTel's CLI.
args <- commandArgs(trailingOnly = TRUE)
expressions <- parse(file = args[[1]])
needed <- c("BUFFER", "KM_MAX_RELATIVE_CI_WIDTH_PCT", "KM_REPORT_MESSAGES",
            "assess_km_result", "fit_km_result", "format_km_report")
for (expr in expressions) {
  if (is.call(expr) && identical(expr[[1]], as.name("<-")) &&
      as.character(expr[[2]]) %in% needed) eval(expr)
}
check <- function(condition) stopifnot(isTRUE(condition))
for (width in c(10, 20, 20.001, 24)) {
  r <- assess_km_result(5000, 5000 - width * 25, 5000 + width * 25)
  check(r$status == if (width <= 20) "reportable" else "too_wide")
  check(abs(r$relative_ci_width_pct - width) < 1e-10)
}
check(grepl("unrounded", assess_km_result(5000, 4499.975, 5500.025)$reason))
check(assess_km_result(5000, 4400, 5600, limit = 25)$status == "reportable")
for (bad in list(NA_real_, NaN, Inf, -Inf, NULL, numeric())) {
  for (position in 1:3) {
    values <- list(5000, 4500, 5500)
    values[position] <- list(bad)
    check(do.call(assess_km_result, values)$status == "non_estimable")
  }
}
for (values in list(c(0, 0, 1), c(-1, -2, 0), c(5, 6, 7), c(5, 3, 4), c(5, 7, 3))) {
  check(do.call(assess_km_result, as.list(values))$status == "invalid")
}
for (limit in list(0, -1, Inf, NA_real_, "20", c(10, 20))) {
  check(inherits(try(assess_km_result(5, 4, 6, limit), silent = TRUE), "try-error"))
}

fixture <- data.frame(sequence_length = c(10000, 7000, 5000),
                      Telomere_length_mismatch = c(5000, 6980, 4900),
                      Telomere_end_mismatch = c(5000, 6980, 4900))
spy <- function(formula, data, conf.type, conf.int) {
  check(nrow(data) == 3L) # Includes the third read, which fails the edge filter.
  check(identical(data$event, c(1L, 0L, 1L)))
  check(conf.type == "log-log" && conf.int == 0.95)
  survival::survfit(formula, data = data, conf.type = conf.type, conf.int = conf.int)
}
r <- fit_km_result(fixture, fit_function = spy)
check(is.null(r$error))
reference_data <- transform(fixture, event = c(1, 0, 1))
reference <- summary(survival::survfit(
  survival::Surv(Telomere_length_mismatch, event) ~ 1, data = reference_data,
  conf.type = "log-log", conf.int = 0.95))$table
check(identical(r$median, unname(reference["median"])))
check(identical(r$lower, unname(reference["0.95LCL"])))
check(identical(r$upper, unname(reference["0.95UCL"])))
boundary <- fixture
boundary$Telomere_end_mismatch <- boundary$sequence_length - c(49, 50, 51)
fit_km_result(boundary, fit_function = function(formula, data, ...) {
  check(identical(data$event, c(0L, 1L, 1L)))
  survival::survfit(formula, data = data, ...)
})
failed <- fit_km_result(fixture, fit_function = function(...) stop("fixture fit failure"))
check(failed$status == "failed" && grepl("fixture fit failure", failed$error))
check(!grepl("too wide", failed$reason))
failed_summary <- fit_km_result(fixture, summary_function = function(...) stop("summary failure"))
check(failed_summary$status == "failed")
warned <- fit_km_result(fixture, fit_function = function(...) {
  warning("fixture warning")
  survival::survfit(...)
})
check(identical(warned$warnings, "fixture warning"))
check(fit_km_result(fixture[FALSE, ])$status == "failed")

# Inspect the actual analysis block's data flow and evaluate its report construction.
blocks <- Filter(function(x) is.call(x) && identical(x[[1]], as.name("if")) &&
                   identical(x[[2]], quote(isTRUE(opt$analysis))), as.list(expressions))
check(length(blocks) == 1L)
statements <- as.list(blocks[[1]][[3]])[-1]
assignments <- Filter(function(x) is.call(x) && identical(x[[1]], as.name("<-")), statements)
km_call <- Filter(function(x) identical(x[[2]], as.name("km_result")), assignments)[[1]]
check(identical(km_call[[3]], quote(fit_km_result(df_step1_filtered))))
km_index <- which(vapply(statements, identical, logical(1), km_call))
edge_index <- which(vapply(statements, function(x) grepl("filter\\(SeqLen_minus_RunMed >", paste(deparse(x), collapse = " ")), logical(1)))
check(km_index < edge_index)
report_assignments <- Filter(function(x) as.character(x[[2]]) %in% c("fmt", "results_lines"), assignments)
n_reads <- 2; n_complete <- 1; n_censored <- 1; censoring_rate <- 0.5
med_telo <- 5990; pct_short <- 0; barcode_name <- "barcode01"
opt <- list(short_telomere_threshold_bp = 2000)
cases <- list(reportable = assess_km_result(5000, 4500, 5500),
              too_wide = assess_km_result(5000, 4400, 5600),
              non_estimable = assess_km_result(5000, NA_real_, 5500),
              failed = failed)
descriptive <- NULL
for (name in names(cases)) {
  km_result <- cases[[name]]
  for (expr in report_assignments) eval(expr)
  current <- results_lines[!grepl("^KM ", results_lines)]
  if (is.null(descriptive)) descriptive <- current else check(identical(descriptive, current))
  if (name != "reportable") {
    km_lines <- format_km_report(km_result)
    check(!any(grepl("5,000|4,400|5,600|5,500", km_lines)))
  }
  writeLines(results_lines, file.path(args[[2]], paste0(name, "_results.txt")), useBytes = TRUE)
}
check(cases$too_wide$median == 5000 && cases$too_wide$lower == 4400 && cases$too_wide$upper == 5600)
# A tight deterministic sample exercises a genuinely reportable survival fit.
tight <- data.frame(Telomere_length_mismatch = seq(4900, 5100, length.out = 101))
tight$Telomere_end_mismatch <- tight$Telomere_length_mismatch
tight$sequence_length <- tight$Telomere_length_mismatch + 1000
check(fit_km_result(tight)$status == "reportable")
cat("KM R checks passed\n")
