# Rank already quality-filtered alignments, without changing the original BAM.
# Coordinates below are zero-based, half-open on NanoTel's analyzed-read axis.
mapping_candidate_metrics <- function(row, telomere_start, telomere_end, read_length,
                                      reversed_read) {
  missing <- c(subtelomeric_aligned_bp=NA_real_, boundary_gap_bp=NA_real_)
  cigar <- as.character(row$alignment_cigar)
  strand <- as.character(row$alignment_direction)
  if (length(cigar) != 1L || is.na(cigar) ||
      !grepl("^([1-9][0-9]*[MIDNSHP=X])+$", cigar) ||
      length(strand) != 1L || is.na(strand) || !strand %in% c("+", "-") ||
      length(reversed_read) != 1L || is.na(reversed_read) || !is.logical(reversed_read) ||
      any(!is.finite(c(telomere_start, telomere_end, read_length))) ||
      any(c(telomere_start, telomere_end, read_length) %% 1 != 0) ||
      telomere_start < 1 || telomere_end < telomere_start || telomere_end > read_length)
    return(missing)
  tokens <- regmatches(cigar, gregexpr("[0-9]+[MIDNSHP=X]", cigar))[[1]]
  sizes <- as.numeric(sub("[MIDNSHP=X]$", "", tokens))
  ops <- sub("^[0-9]+", "", tokens)
  core <- which(!ops %in% c("S", "H"))
  if (!length(core) || any(ops[seq.int(min(core), max(core))] %in% c("S", "H"))) return(missing)
  consumed <- sizes * (ops %in% c("M", "I", "S", "H", "=", "X"))
  if (sum(consumed) != read_length) return(missing)
  ends <- cumsum(consumed)
  starts <- ends-consumed
  aligned <- ops %in% c("M", "=", "X")
  starts <- starts[aligned]; ends <- ends[aligned]
  if (!length(starts)) return(missing)
  # SAM CIGAR faces the reference; NanoTel may also reverse-complement input.
  if (xor(strand == "-", reversed_read)) {
    old_starts <- starts
    starts <- read_length-ends; ends <- read_length-old_starts
  }
  lo <- telomere_start-1; hi <- telomere_end
  left_ends <- pmin(ends, lo); left <- left_ends > starts
  right_starts <- pmax(starts, hi); right <- ends > right_starts
  coverage <- sum(left_ends[left]-starts[left]) + sum(ends[right]-right_starts[right])
  # Either adjacent flank can supply evidence; no head/tail or strand guess.
  gaps <- c(lo-left_ends[left], right_starts[right]-hi)
  c(subtelomeric_aligned_bp=coverage, boundary_gap_bp=if (length(gaps)) min(gaps) else Inf)
}

select_mapping_candidates <- function(alignments, nanotel, reversed_read=NULL) {
  audit <- alignments
  audit$subtelomeric_aligned_bp <- rep(NA_real_, nrow(audit))
  audit$boundary_gap_bp <- rep(NA_real_, nrow(audit))
  audit$mapping_telomere_start_bp <- rep(NA_real_, nrow(audit))
  audit$mapping_telomere_end_bp <- rep(NA_real_, nrow(audit))
  audit$mapping_boundary_columns <- rep(NA_character_, nrow(audit))
  audit$mapping_selected <- rep(TRUE, nrow(audit))
  audit$mapping_selection_reason <- rep("Not ranked: missing or ambiguous boundary/orientation/CIGAR", nrow(audit))
  if (!nrow(audit)) return(list(selected=alignments, candidates=audit))
  columns <- list(
    c("Telomere_start_mismatch_tvr", "Telomere_end_mismatch_tvr"),
    c("Telomere_start_mismatch", "Telomere_end_mismatch"),
    c("Telomere_start", "Telomere_end"))
  columns <- Filter(function(pair) all(pair %in% names(nanotel)), columns)
  if (!length(columns) || !"sequence_length" %in% names(nanotel))
    return(list(selected=alignments, candidates=audit))
  source_groups <- split(seq_len(nrow(nanotel)), nanotel$read_id_clean)
  alignment_groups <- split(seq_len(nrow(audit)), audit$read_id_clean)
  for (id in names(alignment_groups)) {
    indices <- alignment_groups[[id]]
    source <- source_groups[[id]]
    if (length(source) != 1L) next
    read <- nanotel[source, , drop=FALSE]
    # Prefer the recorded variant-inclusive call, then canonical with mismatch,
    # then exact canonical. Never use the filtration outcome to choose a read.
    boundary <- NULL
    for (pair in columns) {
      candidate <- suppressWarnings(as.numeric(unlist(read[pair], use.names=FALSE)))
      if (length(candidate) == 2L && all(is.finite(candidate))) {
        boundary <- candidate
        audit$mapping_boundary_columns[indices] <- paste(pair, collapse=", ")
        break
      }
    }
    if (is.null(boundary)) next
    audit$mapping_telomere_start_bp[indices] <- boundary[1]
    audit$mapping_telomere_end_bp[indices] <- boundary[2]
    scores <- vapply(indices, function(i) mapping_candidate_metrics(audit[i, , drop=FALSE],
      boundary[1], boundary[2], as.numeric(read$sequence_length), reversed_read), numeric(2))
    audit$subtelomeric_aligned_bp[indices] <- scores[1, ]
    audit$boundary_gap_bp[indices] <- scores[2, ]
    # An unscorable competitor could be better: retain the entire group.
    if (anyNA(scores)) next
    coverage <- scores[1, ]; gap <- scores[2, ]
    selected <- rep(TRUE, length(indices))
    best_coverage <- -Inf; best_gap <- Inf
    # Sorted sweep avoids pairwise comparisons when a read has many hits.
    for (j in order(gap, -coverage)) {
      selected[j] <- coverage[j] > best_coverage ||
        (coverage[j] == best_coverage && gap[j] == best_gap)
      if (coverage[j] > best_coverage) {
        best_coverage <- coverage[j]; best_gap <- gap[j]
      }
    }
    audit$mapping_selected[indices] <- selected
    audit$mapping_selection_reason[indices] <- ifelse(!selected,
      "Not selected: another alignment has no less subtelomeric coverage and no greater boundary gap, with a strict improvement",
      if (sum(selected) > 1L) "Ambiguous: equal scores or coverage/proximity trade-off" else
        "Selected: no competing alignment improves coverage/proximity without a trade-off")
    if (all(coverage == 0)) audit$mapping_selection_reason[indices] <- "Not ranked: no aligned bases outside the recorded telomere"
  }
  list(selected=audit[audit$mapping_selected, , drop=FALSE], candidates=audit)
}

# Read only explicit NanoTel orientation metadata. Legacy files lacking it keep
# all candidates, rather than silently comparing opposite coordinate systems.
mapping_read_orientation <- function(nanotel_path) {
  path <- sub("_summary\\.csv$", "_analysis.json", nanotel_path)
  if (identical(path, nanotel_path) || !file.exists(path)) return(NULL)
  metadata <- tryCatch(jsonlite::read_json(path, simplifyVector=TRUE), error=function(e) NULL)
  if (!is.list(metadata)) return(NULL)
  barcode <- sub("_summary\\.csv$", "", basename(nanotel_path))
  if (!identical(metadata$barcode, barcode)) return(NULL)
  value <- metadata$analyzed_read_reverse_complemented
  if (is.logical(value) && length(value) == 1L && !is.na(value)) value else NULL
}
