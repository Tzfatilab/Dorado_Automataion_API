# Exercise the output boundary without loading/running scientific analysis.
expressions <- parse("dorado_workflow/data/NanoTel.R")
helpers <- c("ensure_output_directory", "write_read_fasta", "create_dirs")
for (expression in expressions) {
  if (is.call(expression) && identical(expression[[1]], as.name("<-")) &&
      as.character(expression[[2]]) %in% helpers) eval(expression)
}
root <- tempfile("NanoTel output with spaces ")
dir.create(root)
base_writer <- function(sequence, path, compress) {
  stopifnot(isTRUE(compress))
  connection <- gzfile(path, "wt")
  on.exit(close(connection))
  writeLines(c(">read1", sequence), connection)
}
path <- file.path(root, "missing", "reads", "barcode16_read13.fasta.gz")
write_read_fasta("TTAGGG", path, writer=base_writer)
connection <- gzfile(path, "rt")
stopifnot(identical(readLines(connection), c(">read1", "TTAGGG")))
close(connection)

# An existing file cannot be treated as a directory; fail with its actual path.
blocked <- file.path(root, "not-a-directory")
invisible(file.create(blocked))
error <- tryCatch(ensure_output_directory(blocked), error=conditionMessage)
stopifnot(is.character(error), grepl(blocked, error, fixed=TRUE))

# Retain filesystem diagnostics, rather than reporting just a Reduce error.
failing_writer <- function(...) {
  warning("No space left on device")
  stop("cannot open file")
}
error <- suppressWarnings(tryCatch(
  write_read_fasta("TTAGGG", path, writer=failing_writer), error=conditionMessage))
stopifnot(grepl(path, error, fixed=TRUE),
          grepl("No space left on device", error, fixed=TRUE),
          grepl("cannot open file", error, fixed=TRUE))

# Workers create the same missing parent safely and save separate gzip files.
cluster <- parallel::makePSOCKcluster(2)
parallel::clusterExport(cluster, c("ensure_output_directory", "write_read_fasta", "base_writer"))
paths <- file.path(root, "parallel", "reads", paste0("read", 1:4, ".fasta.gz"))
invisible(parallel::parLapply(cluster, paths, function(path) write_read_fasta("TTAGGG", path, writer=base_writer)))
parallel::stopCluster(cluster)
stopifnot(all(file.exists(paths)))
create_dirs(file.path(root, "full"))
stopifnot(dir.exists(file.path(root, "full", "reads")))
create_dirs(file.path(root, "summary"), summary_only=TRUE)
stopifnot(!dir.exists(file.path(root, "summary", "reads")))
if (requireNamespace("Biostrings", quietly=TRUE)) {
  actual <- file.path(root, "Biostrings", "read.fasta.gz")
  sequence <- Biostrings::DNAStringSet(c(read1="TTAGGG"))
  write_read_fasta(sequence, actual)
  stopifnot(identical(as.character(Biostrings::readDNAStringSet(actual)), c(read1="TTAGGG")))
  cat("PASS: real Biostrings compressed FASTA round trip\n")
} else {
  cat("SKIP: Biostrings is unavailable locally; output-boundary checks used a base-R gzip writer\n")
}
cat("PASS: gzip output, missing directories, concurrent workers, failures and summary-only mode\n")
