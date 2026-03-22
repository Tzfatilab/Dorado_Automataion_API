# r_analysis/functions/methylation_functions.R
# Functions for methylation data processing and visualization

# Get the directory where this script is located
script_dir <- tryCatch({
  # Try commandArgs method first (for Rscript)
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg) > 0) {
    dirname(sub("^--file=", "", file_arg))
  } else {
    # Try sys.frame for when sourced
    frame_files <- lapply(sys.frames(), function(x) x$ofile)
    frame_files <- Filter(Negate(is.null), frame_files)
    if (length(frame_files) > 0) {
      dirname(frame_files[[1]])
    } else {
      getwd()
    }
  }
}, error = function(e) {
  getwd()
})

# Only source utils.R if not already loaded
if (!exists("log_message", mode = "function")) {
  source(file.path(script_dir, "utils.R"))
}

# Read and process a single pileup BED file
process_pileup_bed_file <- function(bed_file_path, barcode_name, cell_line_name) {

  log_message(paste("Processing pileup BED file for:", barcode_name))

  validate_file_exists(bed_file_path, "Pileup BED file")

  # Check if file is empty
  if (file.size(bed_file_path) == 0) {
    log_message(paste("BED file is empty:", basename(bed_file_path)), "WARNING")
    return(data.frame())  # Return empty data frame
  }

  # Read BED file (tab-separated, no header)
  bed_data <- tryCatch({
    read.table(bed_file_path, header = FALSE, sep = "\t",
               stringsAsFactors = FALSE, comment.char = "")
  }, error = function(e) {
    log_message(paste("Error reading BED file", bed_file_path, ":", e$message), "WARNING")
    return(data.frame())  # Return empty data frame on error
  })

  if (nrow(bed_data) == 0) {
    log_message(paste("No data in BED file:", basename(bed_file_path)), "WARNING")
    return(data.frame())
  }

  # Add barcode and cell line information
  bed_data$barcode <- barcode_name
  bed_data$cell_line <- cell_line_name

  log_message(paste("Loaded", nrow(bed_data), "methylation sites for", barcode_name))

  return(bed_data)
}

# Process and standardize methylation data
standardize_methylation_data <- function(bed_data_list) {

  log_message("Standardizing methylation data across all samples")

  # Combine all samples
  all_samples <- bind_rows(bed_data_list)

  # Set standard column names
  colnames(all_samples) <- c(
    "chromosome", "start_pos", "end_pos", "modification", "score",
    "strand", "start_pos2", "end_pos2", "color", "Nvalid",
    "fraction_modified", "Nmod", "Ncanonical",
    "Nother_mod", "Ndelete", "Nfail", "Ndiff", "Nnocall",
    "barcode", "cell_line"
  )

  # Remove duplicate position columns
  all_samples <- all_samples[, -c(7, 8, 9)]

  # Filter out 'h' modifications (if any)
  all_samples <- all_samples %>%
    filter(modification != "h")

  # Adjust positions based on reference genome (1-based coordinates)
  all_samples$start_pos <- all_samples$start_pos + 1
  all_samples$end_pos <- all_samples$end_pos + 1

  log_message(paste("Standardized data:", nrow(all_samples), "methylation sites"))

  return(all_samples)
}

# Filter methylation data for telomeric regions
filter_telomeric_regions <- function(methylation_data,
                                     head_max_pos = 5000,
                                     tail_min_pos = 145000,
                                     reference_length = 150000) {

  log_message("Filtering for telomeric regions")

  # Filter for telomeric regions (head and tail)
  telomeric_data <- methylation_data %>%
    filter(
      (strand == "+" & start_pos <= head_max_pos) |
        (strand == "-" & start_pos >= tail_min_pos)
    )

  # Adjust positions for negative strand (relative to telomere start)
  telomeric_data <- telomeric_data %>%
    mutate(
      start_pos = ifelse(strand == "-",
                         abs(start_pos - reference_length),
                         start_pos)
    )

  log_message(paste("Telomeric filtering complete:", nrow(telomeric_data), "sites"))

  return(telomeric_data)
}

# Create summary statistics for methylation data
create_methylation_summary <- function(methylation_data, output_file) {

  log_message("Creating methylation summary statistics")

  summary_stats <- methylation_data %>%
    group_by(cell_line, barcode, chromosome, strand) %>%
    summarise(
      total_sites = n(),
      mean_fraction_modified = round(mean(fraction_modified, na.rm = TRUE), 3),
      median_fraction_modified = round(median(fraction_modified, na.rm = TRUE), 3),
      mean_coverage = round(mean(score, na.rm = TRUE), 1),
      median_coverage = round(median(score, na.rm = TRUE), 1),
      sites_above_50pct = sum(fraction_modified > 0.5, na.rm = TRUE),
      sites_above_75pct = sum(fraction_modified > 0.75, na.rm = TRUE),
      .groups = "drop"
    )

  # Save summary
  safe_write_csv(summary_stats, output_file)

  log_message(paste("Methylation summary saved to:", basename(output_file)))

  return(summary_stats)
}

# Create static methylation plots
create_static_methylation_plots <- function(methylation_data, output_dir,
                                            plot_width = 12, plot_height = 8) {

  log_message("Creating static methylation plots")

  ensure_directory_exists(output_dir)

  # Get unique combinations for plotting
  chromosomes <- unique(methylation_data$chromosome)
  cell_lines <- unique(methylation_data$cell_line)

  # Color palette for cell lines
  n_colors <- length(cell_lines)
  if (n_colors <= 8) {
    colors <- RColorBrewer::brewer.pal(max(3, n_colors), "Dark2")[1:n_colors]
  } else {
    colors <- rainbow(n_colors)
  }
  names(colors) <- cell_lines

  # Create plots for each chromosome
  for (chr in chromosomes) {
    chr_data <- methylation_data %>% filter(chromosome == chr)

    if (nrow(chr_data) == 0) next

    p <- ggplot(chr_data, aes(x = start_pos, y = fraction_modified,
                              color = cell_line, size = score)) +
      geom_point(alpha = 0.6) +
      scale_color_manual(values = colors) +
      scale_size_continuous(range = c(1, 6), name = "Coverage") +
      labs(
        title = paste("Methylation Pattern -", chr),
        x = "Position (bp)",
        y = "Fraction Modified",
        color = "Cell Line"
      ) +
      theme_minimal() +
      theme(
        plot.title = element_text(hjust = 0.5, size = 14),
        legend.position = "bottom",
        panel.background = element_rect(fill = "white", color = NA),
        plot.background = element_rect(fill = "white", color = NA),
        panel.grid.major = element_line(color = "gray90"),
        panel.grid.minor = element_line(color = "gray95")
      )

    # Save plot with white background
    plot_file <- file.path(output_dir, paste0("methylation_", chr, ".png"))
    ggsave(plot_file, p, width = plot_width, height = plot_height, dpi = 300,
           bg = "white")  # Force white background

    log_message(paste("Static plot saved:", basename(plot_file)))
  }

  # Create combined overview plot
  p_overview <- ggplot(methylation_data, aes(x = start_pos, y = fraction_modified,
                                             color = cell_line)) +
    geom_point(alpha = 0.4, size = 1) +
    facet_wrap(~chromosome, scales = "free") +
    scale_color_manual(values = colors) +
    labs(
      title = "Methylation Overview - All Chromosomes",
      x = "Position (bp)",
      y = "Fraction Modified",
      color = "Cell Line"
    ) +
    theme_minimal() +
    theme(
      plot.title = element_text(hjust = 0.5, size = 16),
      strip.text = element_text(size = 12),
      legend.position = "bottom",
      panel.background = element_rect(fill = "white", color = NA),
      plot.background = element_rect(fill = "white", color = NA),
      panel.grid.major = element_line(color = "gray90"),
      panel.grid.minor = element_line(color = "gray95")
    )

  overview_file <- file.path(output_dir, "methylation_overview.png")
  ggsave(overview_file, p_overview, width = 16, height = 12, dpi = 300,
         bg = "white")  # Force white background

  log_message(paste("Overview plot saved:", basename(overview_file)))

  return(list(
    chromosome_plots = file.path(output_dir, paste0("methylation_", chromosomes, ".png")),
    overview_plot = overview_file
  ))
}

# Prepare data for interactive visualization
prepare_interactive_data <- function(methylation_data, output_file) {

  log_message("Preparing data for interactive visualization")

  # Create a more compact dataset for interactive use
  interactive_data <- methylation_data %>%
    select(chromosome, start_pos, fraction_modified, score, strand,
           Ncanonical, Nmod, barcode, cell_line) %>%
    # Add percentage format for display
    mutate(
      fraction_modified_pct = round(fraction_modified * 100, 1)
    )

  # Save as RDS for efficient loading in Shiny
  saveRDS(interactive_data, output_file)

  log_message(paste("Interactive data saved to:", basename(output_file)))

  return(interactive_data)
}

# Create the original-style interactive methylation visualization
create_original_interactive_plot <- function(methylation_data, output_file) {

  log_message("Creating original-style interactive methylation plot")

  chromosomes <- unique(methylation_data$chromosome)
  cell_lines <- unique(methylation_data$cell_line)

  if (length(chromosomes) == 0 || length(cell_lines) == 0) {
    warning("No data available for interactive plot")
    return(NULL)
  }

  # Color palette for cell lines (matching original)
  n_colors <- length(cell_lines)
  cell_line_colors <- if(n_colors <= 8) {
    RColorBrewer::brewer.pal(max(3, n_colors), "Dark2")[1:n_colors]
  } else {
    rainbow(n_colors)
  }
  names(cell_line_colors) <- cell_lines

  # Build traces for all chromosome Ã— cell_line combinations (matching original logic)
  trace_list <- list()
  visibility_matrix <- list()
  trace_index <- 0

  for (chr in chromosomes) {
    vis_vec <- rep(FALSE, length(chromosomes) * length(cell_lines))

    for (cl in cell_lines) {
      trace_data <- methylation_data %>%
        filter(chromosome == chr, cell_line == cl)

      trace_index <- trace_index + 1
      vis_vec[trace_index] <- TRUE

      if (nrow(trace_data) > 0) {
        trace_list[[trace_index]] <- list(
          data = trace_data,
          x = ~start_pos,
          y = ~fraction_modified,
          type = "scatter",
          mode = "markers",
          name = cl,
          marker = list(
            size = ~score,
            sizemode = "diameter",
            sizeref = max(trace_data$score, na.rm = TRUE) / (4^2),
            sizemin = 2,
            color = cell_line_colors[[cl]],
            line = list(width = 0)
          ),
          visible = ifelse(chr == chromosomes[1], TRUE, FALSE),
          showlegend = FALSE,
          legendgroup = cl,
          text = ~paste(
            "<br>Position:", start_pos,
            "<br>Number of hits:", score,
            "<br>Canonical C:", Ncanonical,
            "<br>Modified C:", Nmod,
            "<br>Fraction Modified:", paste0(round(fraction_modified * 100, 1), "%")
          ),
          hoverinfo = "text"
        )
      }
    }
    visibility_matrix[[chr]] <- c(vis_vec, rep(TRUE, length(cell_lines)))
  }

  # Create the plot and add all traces
  p <- plot_ly()
  for (trace in trace_list) {
    if (!is.null(trace$data) && nrow(trace$data) > 0) {
      p <- add_trace(p,
                     data = trace$data,
                     x = trace$x,
                     y = trace$y,
                     type = trace$type,
                     mode = trace$mode,
                     name = trace$name,
                     marker = trace$marker,
                     visible = trace$visible,
                     text = trace$text,
                     hoverinfo = trace$hoverinfo,
                     showlegend = trace$showlegend,
                     legendgroup = trace$legendgroup)
    }
  }

  # Add legend traces for each cell line (matching original)
  for (cl in cell_lines) {
    p <- add_trace(p,
                   x = 0, y = 0,  # no visible data
                   type = "scatter",
                   mode = "markers",
                   name = cl,
                   marker = list(
                     size = 10,
                     color = cell_line_colors[[cl]],
                     line = list(width = 0)
                   ),
                   showlegend = TRUE,
                   legendgroup = cl,
                   visible = TRUE,
                   inherit = FALSE)
  }

  # Create dropdown menu to toggle chromosomes (matching original)
  buttons <- lapply(seq_along(chromosomes), function(i) {
    chr <- chromosomes[i]
    list(
      method = "update",
      args = list(
        list(visible = visibility_matrix[[chr]]),
        list(title = paste("Chromosome:", chr))
      ),
      label = chr
    )
  })

  # Apply layout with dropdown (exactly like original)
  p <- layout(p,
              title = paste("Chromosome:", chromosomes[1]),
              xaxis = list(title = "Position"),
              yaxis = list(title = "Fraction Modified"),
              updatemenus = list(list(
                buttons = buttons,
                direction = "down",
                showactive = TRUE,
                x = 0,
                xanchor = "left",
                y = 1.2,
                yanchor = "top"
              )),
              legend = list(
                title = list(text = "Cell Line"),
                tracegroupgap = 5
              ))

  # Save as HTML file
  htmlwidgets::saveWidget(p, output_file, selfcontained = FALSE)

  log_message(paste("Original-style interactive plot saved to:", basename(output_file)))

  return(p)
}

# Generate methylation analysis report
generate_methylation_report <- function(methylation_data, summary_stats,
                                        output_file, analysis_params = list()) {

  log_message("Generating methylation analysis report")

  # Add safety checks
  if (nrow(summary_stats) == 0) {
    warning("No summary statistics available for report")
    return(NULL)
  }

  report_lines <- c(
    rep_str("=", 80),
    "METHYLATION ANALYSIS REPORT",
    rep_str("=", 80),
    paste("Analysis date:", Sys.Date()),
    paste("Analysis time:", format(Sys.time(), "%H:%M:%S")),
    "",
    "ANALYSIS PARAMETERS:",
    paste("  Head region max position:", analysis_params$head_max_pos %||% "5000 bp"),
    paste("  Tail region min position:", analysis_params$tail_min_pos %||% "145000 bp"),
    paste("  Reference length:", analysis_params$reference_length %||% "150000 bp"),
    "",
    "DATA OVERVIEW:",
    paste("  Total methylation sites:", nrow(methylation_data)),
    paste("  Unique chromosomes:", length(unique(methylation_data$chromosome))),
    paste("  Cell lines analyzed:", length(unique(methylation_data$cell_line))),
    paste("  Barcodes processed:", length(unique(methylation_data$barcode))),
    "",
    "CELL LINES:",
    paste("  ", paste(unique(methylation_data$cell_line), collapse = ", ")),
    "",
    "CHROMOSOMES:",
    paste("  ", paste(unique(methylation_data$chromosome), collapse = ", ")),
    "",
    "METHYLATION STATISTICS:"
  )

  # Add summary statistics with safety checks
  for (i in 1:nrow(summary_stats)) {
    row <- summary_stats[i, ]
    # Ensure all values are not empty
    barcode_str <- if(!is.na(row$barcode) && row$barcode != "") row$barcode else "Unknown"
    cell_line_str <- if(!is.na(row$cell_line) && row$cell_line != "") row$cell_line else "Unknown"

    report_lines <- c(report_lines,
                      paste("  ", cell_line_str, "-", barcode_str, ":"),
                      paste("    Sites:", row$total_sites %||% 0),
                      paste("    Mean fraction modified:", row$mean_fraction_modified %||% 0),
                      paste("    Mean coverage:", row$mean_coverage %||% 0),
                      ""
    )
  }

  report_lines <- c(report_lines,
                    "",
                    rep_str("=", 80)
  )

  # Write report with error handling
  tryCatch({
    writeLines(report_lines, output_file)
    log_message(paste("Methylation report saved to:", basename(output_file)))
  }, error = function(e) {
    log_message(paste("Error writing report:", e$message), "ERROR")
  })

  return(output_file)
}

# Find pileup BED files for processing
find_pileup_bed_files <- function(input_dir, barcode_mapping = NULL) {

  log_message(paste("Looking for pileup BED files in:", input_dir))

  bed_files <- find_files_by_pattern(input_dir, "pileup.*\\.bed$", recursive = TRUE)

  if (length(bed_files) == 0) {
    warning("No pileup BED files found in: ", input_dir)
    return(data.frame())
  }

  # Extract barcode information
  bed_info <- data.frame(
    bed_path = bed_files,
    barcode = sapply(bed_files, extract_barcode_from_path),
    stringsAsFactors = FALSE
  )

  # Add cell line information if mapping provided
  if (!is.null(barcode_mapping)) {
    bed_info <- merge(bed_info, barcode_mapping, by = "barcode", all.x = TRUE)

    # Fill missing cell lines with barcode name
    bed_info$cell_line[is.na(bed_info$cell_line)] <- bed_info$barcode[is.na(bed_info$cell_line)]
  } else {
    # Default: use barcode as cell line name
    bed_info$cell_line <- bed_info$barcode
  }

  log_message(paste("Found", nrow(bed_info), "pileup BED files"))

  return(bed_info)
}
