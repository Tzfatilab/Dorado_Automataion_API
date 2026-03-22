#!/usr/bin/env Rscript
# r_analysis/batch_methylation_prep.R
# Batch processing script for methylation data preparation and visualization

# Load required functions
# Get the directory where this script is located
script_dir <- tryCatch({
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg) > 0) {
    dirname(sub("^--file=", "", file_arg))
  } else {
    getwd()
  }
}, error = function(e) {
  getwd()
})
source(file.path(script_dir, "functions", "utils.R"))
source(file.path(script_dir, "functions", "methylation_functions.R"))

# Main function for batch methylation analysis
main_methylation_analysis <- function(config_file) {

  cat("Starting Methylation Batch Analysis\n")
  cat("===================================\n\n")

  # Load required packages
  load_required_packages()

  # Read configuration
  config <- read_config(config_file)

  # Validate configuration
  required_params <- c("pileup_bed_dir", "output_dir")
  missing_params <- required_params[!(required_params %in% names(config))]
  if (length(missing_params) > 0) {
    stop("Missing required configuration parameters: ", paste(missing_params, collapse = ", "))
  }

  # Set default parameters
  head_max_pos <- config$head_max_pos %||% 5000
  tail_min_pos <- config$tail_min_pos %||% 145000
  reference_length <- config$reference_length %||% 150000
  create_plots <- config$create_plots %||% TRUE
  plot_width <- config$plot_width %||% 12
  plot_height <- config$plot_height %||% 8

  log_message("Configuration loaded successfully")
  log_message(paste("Pileup BED directory:", config$pileup_bed_dir))
  log_message(paste("Output directory:", config$output_dir))

  # Create output subdirectories
  plots_dir <- file.path(config$output_dir, "plots")
  data_dir <- file.path(config$output_dir, "processed_data")
  ensure_directory_exists(plots_dir)
  ensure_directory_exists(data_dir)

  # Find pileup BED files
  bed_info <- find_pileup_bed_files(config$pileup_bed_dir, config$barcode_mapping)

  if (nrow(bed_info) == 0) {
    stop("No pileup BED files found in: ", config$pileup_bed_dir)
  }

  log_message(paste("Found", nrow(bed_info), "pileup BED files"))

  # Process all BED files
  bed_data_list <- process_all_bed_files(bed_info)

  if (length(bed_data_list) == 0) {
    stop("No BED files could be processed successfully")
  }

  # Standardize and combine data
  log_message("Standardizing methylation data")
  methylation_data <- standardize_methylation_data(bed_data_list)

  # Filter for telomeric regions
  log_message("Filtering for telomeric regions")
  telomeric_data <- filter_telomeric_regions(
    methylation_data = methylation_data,
    head_max_pos = head_max_pos,
    tail_min_pos = tail_min_pos,
    reference_length = reference_length
  )

  if (nrow(telomeric_data) == 0) {
    warning("No telomeric methylation data found after filtering")
    return(invisible(NULL))
  }

  # Save processed data
  processed_data_file <- file.path(data_dir, "processed_methylation_data.csv")
  safe_write_csv(telomeric_data, processed_data_file)

  # Create summary statistics
  summary_file <- file.path(config$output_dir, "methylation_summary_statistics.csv")
  summary_stats <- create_methylation_summary(telomeric_data, summary_file)

  # Prepare interactive data
  interactive_data_file <- file.path(data_dir, "interactive_methylation_data.rds")
  interactive_data <- prepare_interactive_data(telomeric_data, interactive_data_file)

  # Create static plots if requested
  plot_files <- NULL
  if (create_plots) {
    log_message("Creating static methylation plots")
    plot_files <- create_static_methylation_plots(
      telomeric_data, plots_dir, plot_width, plot_height
    )
  }

  # Generate analysis report
  analysis_params <- list(
    head_max_pos = head_max_pos,
    tail_min_pos = tail_min_pos,
    reference_length = reference_length
  )

  report_file <- file.path(config$output_dir, "methylation_analysis_report.txt")
  tryCatch({
    generate_methylation_report(telomeric_data, summary_stats, report_file, analysis_params)
  }, error = function(e) {
    log_message(paste("Warning: Could not generate final report:", e$message), "WARNING")
    # Don't fail the entire process for a report generation error
  })

  # Create original-style interactive plot if requested
  if (config$create_original_interactive %||% FALSE) {
    log_message("Creating original-style interactive plot")
    interactive_plot_file <- file.path(config$output_dir, "interactive_methylation_original.html")
    original_plot <- create_original_interactive_plot(telomeric_data, interactive_plot_file)
  }

  # Create Shiny app files if requested
  if (config$create_shiny_app %||% FALSE) {
    create_shiny_methylation_app(config$output_dir, interactive_data_file)
  }

  log_message("Methylation batch analysis completed successfully!")

  return(list(
    methylation_data = telomeric_data,
    summary_stats = summary_stats,
    plot_files = plot_files,
    processed_files = length(bed_data_list),
    total_sites = nrow(telomeric_data)
  ))
}

# Process all BED files
process_all_bed_files <- function(bed_info) {

  log_message("Processing all pileup BED files")

  bed_data_list <- list()

  for (i in 1:nrow(bed_info)) {
    bed_file <- bed_info$bed_path[i]
    barcode <- bed_info$barcode[i]
    cell_line <- bed_info$cell_line[i]

    show_progress(i, nrow(bed_info), "Processing BED files")

    tryCatch({
      bed_data <- process_pileup_bed_file(bed_file, barcode, cell_line)
      bed_data_list[[barcode]] <- bed_data
    }, error = function(e) {
      log_message(paste("Error processing", basename(bed_file), ":", e$message), "ERROR")
    })
  }

  log_message(paste("Successfully processed", length(bed_data_list), "BED files"))

  return(bed_data_list)
}

# Create Shiny app for interactive visualization
create_shiny_methylation_app <- function(output_dir, interactive_data_file) {

  log_message("Creating Shiny app for interactive visualization")

  app_dir <- file.path(output_dir, "shiny_app")
  ensure_directory_exists(app_dir)

  # Create app.R file
  app_content <- paste(
    "# Interactive Methylation Viewer",
    "# Auto-generated Shiny application",
    "",
    "library(shiny)",
    "library(plotly)",
    "library(dplyr)",
    "library(RColorBrewer)",
    "library(htmlwidgets)",
    "",
    "# Load data",
    paste0("methylation_data <- readRDS('", basename(interactive_data_file), "')"),
    "",
    "# UI",
    "ui <- fluidPage(",
    "  titlePanel('Interactive Methylation Viewer'),",
    "  ",
    "  sidebarLayout(",
    "    sidebarPanel(",
    "      checkboxGroupInput('cell_line', 'Select Cell Line:',",
    "                         choices = unique(methylation_data$cell_line),",
    "                         selected = unique(methylation_data$cell_line)),",
    "      downloadButton('downloadPlot', 'Download Plot as HTML'),",
    "      br(), br(),",
    "      h4('Data Summary:'),",
    "      verbatimTextOutput('data_summary')",
    "    ),",
    "    ",
    "    mainPanel(",
    "      plotlyOutput('methPlot', height = '600px')",
    "    )",
    "  )",
    ")",
    "",
    "# Server",
    "server <- function(input, output) {",
    "  ",
    "  plot_data_reactive <- reactive({",
    "    req(input$cell_line)",
    "    methylation_data %>% filter(cell_line %in% input$cell_line)",
    "  })",
    "  ",
    "  output$data_summary <- renderText({",
    "    df <- plot_data_reactive()",
    "    paste(",
    "      'Total sites:', nrow(df), '\\n',",
    "      'Chromosomes:', length(unique(df$chromosome)), '\\n',",
    "      'Cell lines:', length(unique(df$cell_line)), '\\n',",
    "      'Mean methylation:', round(mean(df$fraction_modified, na.rm = TRUE), 3)",
    "    )",
    "  })",
    "  ",
    "  plot_reactive <- reactive({",
    "    df <- plot_data_reactive()",
    "    chromosomes <- unique(df$chromosome)",
    "    cell_lines <- unique(df$cell_line)",
    "    ",
    "    if (nrow(df) == 0) return(plotly_empty())",
    "    ",
    "    # Color palette",
    "    n_colors <- length(cell_lines)",
    "    colors <- if(n_colors <= 8) {",
    "      brewer.pal(max(3, n_colors), 'Dark2')[1:n_colors]",
    "    } else {",
    "      rainbow(n_colors)",
    "    }",
    "    names(colors) <- cell_lines",
    "    ",
    "    # Create plot for first chromosome",
    "    chr_data <- df %>% filter(chromosome == chromosomes[1])",
    "    ",
    "    p <- plot_ly(chr_data, x = ~start_pos, y = ~fraction_modified_pct,",
    "                 color = ~cell_line, colors = colors,",
    "                 size = ~score, sizes = c(10, 100),",
    "                 text = ~paste('Position:', start_pos,",
    "                              '<br>Coverage:', score,",
    "                              '<br>Modified:', Nmod,",
    "                              '<br>Canonical:', Ncanonical,",
    "                              '<br>Methylation:', fraction_modified_pct, '%'),",
    "                 hoverinfo = 'text') %>%",
    "      add_markers() %>%",
    "      layout(title = paste('Methylation Pattern -', chromosomes[1]),",
    "             xaxis = list(title = 'Position (bp)'),",
    "             yaxis = list(title = 'Fraction Modified (%)'),",
    "             showlegend = TRUE)",
    "    ",
    "    return(p)",
    "  })",
    "  ",
    "  output$methPlot <- renderPlotly({",
    "    plot_reactive()",
    "  })",
    "  ",
    "  output$downloadPlot <- downloadHandler(",
    "    filename = function() {",
    "      paste0('interactive_methylation_', Sys.Date(), '.html')",
    "    },",
    "    content = function(file) {",
    "      saveWidget(plot_reactive(), file, selfcontained = TRUE)",
    "    }",
    "  )",
    "}",
    "",
    "# Run app",
    "shinyApp(ui = ui, server = server)",
    sep = "\n"
  )

  # Write app.R file
  app_file <- file.path(app_dir, "app.R")
  writeLines(app_content, app_file)

  # Copy data file to app directory
  file.copy(interactive_data_file, app_dir)

  log_message(paste("Shiny app created in:", app_dir))
  log_message("To run the app, use: shiny::runApp('path/to/shiny_app')")

  return(app_dir)
}

# Command line interface
if (!interactive()) {
  # Parse command line arguments
  args <- commandArgs(trailingOnly = TRUE)

  if (length(args) != 1) {
    cat("Usage: Rscript batch_methylation_prep.R <config_file>\n")
    cat("\n")
    cat("Arguments:\n")
    cat("  config_file: JSON configuration file with analysis parameters\n")
    cat("\n")
    cat("Example:\n")
    cat("  Rscript batch_methylation_prep.R config/methylation_config.json\n")
    quit(status = 1)
  }

  config_file <- args[1]

  # Validate config file exists
  if (!file.exists(config_file)) {
    cat("Error: Configuration file not found:", config_file, "\n")
    quit(status = 1)
  }

  # Run analysis
  tryCatch({
    result <- main_methylation_analysis(config_file)
    cat("\nMethylation analysis completed successfully!\n")
    cat("Processed", result$processed_files, "BED files\n")
    cat("Total methylation sites:", result$total_sites, "\n")
  }, error = function(e) {
    cat("Error during analysis:", e$message, "\n")
    quit(status = 1)
  })
}
