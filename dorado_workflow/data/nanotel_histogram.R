# Shared original NanoTel histogram builder for analysis and report regeneration.
# Inputs: barcode (Barcode label or record used by this operation)
# Outputs: Formatted barcode title.
analysis_barcode_title <- function(barcode) {
  if (grepl("^(barcode|bc)[_-]?[0-9]+$", barcode, ignore.case = TRUE)) {
    return(sprintf("Barcode %02d", as.integer(gsub("[^0-9]", "", barcode))))
  }
  barcode
}

# Inputs: data (Read-level or measurement table for this operation)
# Outputs: Histogram bins and per-read completeness metadata.
make_telomere_histogram_data <- function(data) {
  # Match BiModal's linear pretty(..., n=45) breaks and right-closed intervals.
  # Bars include censored reads; the rug marks them again, not an extra population.
  valid <- is.finite(data$telomere_length_bp) & data$telomere_length_bp > 0
  reads <- data[valid, , drop = FALSE]
  excluded <- sum(!valid)
  trend <- data.frame()
  if (!nrow(reads)) return(list(reads = reads, bins = data.frame(), trend = trend, excluded = excluded))
  breaks <- pretty(range(reads$telomere_length_bp), n = 45L)
  histogram <- hist(reads$telomere_length_bp, breaks = breaks,
                    include.lowest = TRUE, right = TRUE, plot = FALSE)
  bins <- data.frame(
    lower_bp = head(histogram$breaks, -1L), upper_bp = tail(histogram$breaks, -1L),
    center_bp = histogram$mids, count = histogram$counts,
    pct = 100 * histogram$counts / nrow(reads)
  )
  # Visual Gaussian KDE of OBSERVED lengths (including censored observations),
  # not a mixture fit or censoring-corrected estimate. Scale by the bin width
  # so the curve has the same count/percentage units as the bars.
  if (nrow(reads) >= 2L && length(unique(reads$telomere_length_bp)) > 1L) {
    smooth <- stats::density(reads$telomere_length_bp, bw = "nrd0", kernel = "gaussian",
                             n = 512L, from = max(0, min(breaks)), to = max(breaks))
    trend <- data.frame(length_bp = smooth$x,
                        count = smooth$y * nrow(reads) * diff(breaks)[1],
                        pct = smooth$y * 100 * diff(breaks)[1])
  }
  list(reads = reads, bins = bins, trend = trend, excluded = excluded)
}

# Inputs: histogram (Previously calculated histogram bins and metadata); barcode (Barcode label or
# record used by this operation); mismatch_allowance (Recorded canonical mismatch allowance)
# Outputs: Plotly histogram with count/percentage controls.
make_telomere_histogram_plot <- function(histogram, barcode, mismatch_allowance) {
  bins <- histogram$bins
  reads <- histogram$reads
  trend <- histogram$trend
  mode <- if (mismatch_allowance == 0L) "exact" else "mismatch"
  title <- paste0("Telomere Lengths Distribution - ", analysis_barcode_title(barcode))
  subtitle <- sprintf("Final-filtered reads | %s | complete: %d | censored: %d | unknown: %d",
                      mode, sum(reads$event == 1L, na.rm = TRUE),
                      sum(reads$event == 0L, na.rm = TRUE), sum(is.na(reads$event)))
  if (histogram$excluded) subtitle <- paste0(subtitle, " | non-positive/non-finite lengths omitted: ", histogram$excluded)
  p <- plotly::plot_ly()
  if (nrow(bins)) {
    hover <- sprintf("Telomere length: %s%.0f, %.0f] bp<br>Reads: %d<br>Percentage of plotted reads: %.2f%%",
                     c("[", rep("(", nrow(bins) - 1L)), bins$lower_bp, bins$upper_bp,
                     bins$count, bins$pct)
    p <- plotly::add_trace(p, x = bins$center_bp, y = bins$count,
      width = bins$upper_bp - bins$lower_bp, type = "bar", name = "Telomeric reads",
      marker = list(color = "#D9E8F5", line = list(color = "white", width = 1)),
      text = hover, textposition = "none", hovertemplate = "%{text}<extra></extra>")
    if (nrow(trend)) p <- plotly::add_trace(p,
      x = trend$length_bp, y = trend$count, type = "scatter", mode = "lines",
      name = "Smoothed observed lengths", line = list(color = "#263B64", width = 2.5),
      hovertemplate = "Telomere length: %{x:,.0f} bp<br>Smoothed height: %{y:.2f}<extra>Observed lengths only</extra>")
    count_values <- if (nrow(trend)) list(bins$count, trend$count) else list(bins$count)
    pct_values <- if (nrow(trend)) list(bins$pct, trend$pct) else list(bins$pct)
    trace_indices <- if (nrow(trend)) list(0L, 1L) else list(0L)
    # Switch bars and trend together; the separate rug strip has no count units.
    p <- plotly::layout(p, updatemenus = list(list(
      type = "buttons", direction = "right", x = 0, y = 1.13,
      buttons = list(
        list(label = "Read count", method = "update", args = list(
          list(y = count_values),
          list("yaxis.title.text" = "Read count", "yaxis.ticksuffix" = "",
               "yaxis.tickformat" = ",d", "yaxis.autorange" = TRUE), trace_indices)),
        list(label = "Percentage", method = "update", args = list(
          list(y = pct_values),
          list("yaxis.title.text" = "Percentage of plotted reads", "yaxis.ticksuffix" = "%",
               "yaxis.tickformat" = ".1f", "yaxis.autorange" = TRUE), trace_indices))
      ))))
  }
  # Export explicit per-read completeness; absence from the censored rug alone
  # must never be interpreted as proof of completeness by the dashboard.
  p <- plotly::layout(p, meta = list(read_completeness = lapply(seq_len(nrow(reads)), function(i)
    list(read_id = as.character(reads$read_id[i]), event = as.integer(reads$event[i])))))
  censored <- reads[which(reads$event == 0L), , drop = FALSE]
  if (nrow(censored)) p <- plotly::add_trace(p,
    x = censored$telomere_length_bp, y = rep(0.5, nrow(censored)), yaxis = "y2",
    type = "scatter", mode = "markers", name = "Censored reads (observed lengths)",
    marker = list(symbol = "line-ns", size = 16, color = "#CC79A7", opacity = 0.55,
                  line = list(color = "#CC79A7", width = 1)),
    text = htmltools::htmlEscape(censored$read_id),
    hovertemplate = "Read: %{text}<br>Observed telomere length: %{x:,.0f} bp<br>Censored: full length unknown<extra></extra>")
  p <- plotly::layout(p,
    title = list(text = paste0(htmltools::htmlEscape(title), "<br><sup>", subtitle, "</sup>")),
    xaxis = list(title = "Telomere length (bp)", tickformat = ",d", anchor = "y2"),
    yaxis = list(title = "Read count", tickformat = ",d", rangemode = "tozero", domain = c(0.12, 1)),
    yaxis2 = list(domain = c(0, 0.07), range = c(0, 1), visible = FALSE, fixedrange = TRUE),
    shapes = list(list(type = "rect", xref = "paper", yref = "paper",
                       x0 = 0, x1 = 1, y0 = 0, y1 = 0.07, fillcolor = "#FFF8FA",
                       line = list(color = "#F1DCE5", width = 1), layer = "below")),
    legend = list(orientation = "h", y = -0.18), margin = list(t = 145, b = 110),
    dragmode = "zoom", plot_bgcolor = "white", paper_bgcolor = "white")
  if (!nrow(reads)) p <- plotly::layout(p, annotations = list(
    list(text = "No final-filtered reads with finite positive telomere lengths",
         x = 0.5, y = 0.5, xref = "paper", yref = "paper", showarrow = FALSE)))
  p
}

