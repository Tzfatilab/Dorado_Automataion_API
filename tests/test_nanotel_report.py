"""Regression for report-only failures after successful NanoTel filtering."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("Rscript"), "Rscript is required")
class NanoTelReportTests(unittest.TestCase):
    def test_density_export_preserves_existing_samples(self):
        script = r'''args <- commandArgs(trailingOnly = TRUE)
env <- new.env(parent = baseenv())
env$write.csv <- utils::write.csv
env$make_barcode_read_stem <- function(serial) paste0("barcode01_read", serial)
for (expr in parse(args[1])) {
  if (is.call(expr) && identical(expr[[1]], as.name("<-")) &&
      identical(expr[[2]], as.name("export_report_density"))) eval(expr, env)
}
windows <- data.frame(start_index=c(1,101), end_index=c(100,200), density=c(0.93,0.12))
analysis <- list(windows, list(motif_matches=data.frame(motif="TCAGGG", matched_sequence="TCAGGG", start=7L, end=12L, role="tvr", max_mismatch=0L)))
folder <- tempfile(); dir.create(folder)
env$export_report_density("read full header", 1, list(exact=analysis, mismatch=analysis, tvr_inclusive=NULL), folder)
result <- read.csv(file.path(folder,"report_details","barcode01_read1_density.csv"))
stopifnot(nrow(result)==4, identical(result$density,c(0.93,0.12,0.93,0.12)),
  all(result$read_id=="read full header"), all(result$convention=="one_based_inclusive"))
motifs <- read.csv(file.path(folder,"report_details","barcode01_read1_motifs.csv"))
stopifnot(nrow(motifs)==4, sum(motifs$record_type=="search_complete")==2,
  all(motifs$motif[motifs$record_type=="match"]=="TCAGGG"))
unlink(folder, recursive=TRUE)
'''
        source = Path(__file__).resolve().parents[1] / "dorado_workflow/data/NanoTel.R"
        result = subprocess.run([shutil.which("Rscript"), "-", str(source)], input=script,
                                capture_output=True, text=True, errors="replace", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_motif_capture_keeps_scientific_ranges(self):
        script = r'''args <- commandArgs(trailingOnly=TRUE)
suppressPackageStartupMessages(library(Biostrings))
suppressPackageStartupMessages(library(stringr))
for(expr in parse(args[1])) if(is.call(expr) && identical(expr[[1]],as.name("<-")) &&
  identical(expr[[2]],as.name("get_density_iranges"))) eval(expr)
global_max_mismatch <- 0
seq <- DNAString("TTAGGGTCAGGGTTAGGG")
result <- get_density_iranges(seq, "TTAGGG", tvr_patterns=list("TCAGGG"))
stopifnot(result[[1]]==1, sum(width(result[[2]]))==18,
  nrow(result$motif_matches)==3,
  identical(result$motif_matches$matched_sequence,c("TTAGGG","TTAGGG","TCAGGG")),
  result$motif_matches$start[3]==7, result$motif_matches$end[3]==12)
# Existing scalar TVR branch does not union exact hits: preserve that behavior.
scalar <- get_density_iranges(seq, "TTAGGG", tvr_patterns="TCAGGG")
stopifnot(scalar[[1]]==12/18, nrow(scalar$motif_matches)==3)
none <- get_density_iranges(DNAString("AAAAAAAAAAAA"), "TTAGGG", tvr_patterns=list("TCAGGG"))
stopifnot(nrow(none$motif_matches)==0, none[[1]]==0)
'''
        source = Path(__file__).resolve().parents[1] / "dorado_workflow/data/NanoTel.R"
        result = subprocess.run([shutil.which("Rscript"), "-", str(source)], input=script,
                                capture_output=True, text=True, errors="replace", timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_threshold_is_resolved_in_report_scope(self):
        script = r'''
args <- commandArgs(trailingOnly = TRUE)
env <- new.env(parent = baseenv())
env$log_message <- function(...) invisible(NULL)
env$rep_str <- function(x, n) paste(rep(x, n), collapse = "")
env$`%||%` <- function(a, b) if (is.null(a)) b else a
for (expr in parse(args[1])) {
  if (is.call(expr) && identical(expr[[1]], as.name("<-")) &&
      identical(expr[[2]], as.name("generate_nanotel_report"))) eval(expr, env)
}
reads <- list(barcode02 = data.frame(Telomere_length_mismatch = 4000,
                                   sequence_length = 5000, telo_density_mismatch = 0.9))
for (threshold in c(2000, 3500)) {
  stats <- data.frame(barcode = "barcode02", amount_of_telomeres = 1,
                      median_telomere_length = 4000, med_read_len = 5000, mean_density = 0.9)
  stats[[paste0("below_", threshold, "bp_pct")]] <- 0
  config <- list(input_dir = "input", output_dir = "output")
  if (threshold != 2000) config$short_telomere_threshold_bp <- threshold
  output <- tempfile(fileext = ".txt")
  env$generate_nanotel_report(reads, stats, output, config)
  stopifnot(any(grepl(paste("Below", threshold, "bp: 0 %"), readLines(output), fixed = TRUE)))
  unlink(output)
}
'''
        source = Path(__file__).resolve().parents[1] / "dorado_workflow/r_analysis/batch_nanotel_analysis.R"
        result = subprocess.run([shutil.which("Rscript"), "-", str(source)], input=script,
                                capture_output=True, text=True, errors="replace", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
