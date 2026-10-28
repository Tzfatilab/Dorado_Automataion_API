library(Biostrings)
library(stringr)
library(readr)
library(dplyr)

library(testit)

#' @description This function creates a data frame of patterns counts for each 
#'              DNA read,
#' @param subject - An XStringSet
#' @param pattern_list - A list of patterns
#' @returns - A data frame with total counts for each pattern.
#' 
count_patterns <- function(subject, pattern_list)
{
  
  col_list <- list(names(subject))
  
  for(i in seq_along(pattern_list))
  {
    col_list[[i+1]] <- vcountPattern(pattern = pattern_list[[i]], subject = subject)
  }
  
  names(col_list) <- c("chr", as.character(pattern_list))
  
  final_df <- as.data.frame(col_list)
  return(final_df)
    
}





#' @description
#'  Create a single line (for each DNA seq) fasta file.
#' @param genome - The reference genome. (We assume it contains only chromosome without additional data such as mitochondrial genome.)
#' @param save_path - The path for the new reference.
single_line_fasta <- function(genome, save_path)
{
  new_str <- character()
  for(i in seq_along(genome))
  {
    new_str <- c(new_str, str_c(">", names(genome)[i]))
    new_str <- c(new_str , toString(genome[i]))
  }
  writeLines(new_str, con = save_path, sep="\n")
}


#' @description
#'  Gets a reference genome and creates a reference of the edges.
#' @param genome - The reference genome. (We assume it contains only chromosome without additional data such as mitochondrial genome.)
#' @param edge_length - The length of the edges.
#' @param save_path - The path for the new reference.
#' @param compress - Use save as compressed file (gzip).
#' @returns - A ref of the edges.
create_chr_edges <- function(genome, edge_length, save_path, compress=FALSE)
{
  new_rf <- DNAStringSet()
  for( i in seq_along(genome)) {
    curr_head <- subseq(genome[i], start = 1, end = edge_length)
    curr_tail <- subseq(genome[i], end = width(genome[i]), width = edge_length)
    
    # add names
    names(curr_head) <- str_c(names(curr_head), "_Head")
    names(curr_tail) <- str_c(names(curr_tail), "_Tail")
    
    new_rf <- append(new_rf, c(curr_head, curr_tail))
    
  }
  
  # save to a file
  writeXStringSet(x = new_rf, filepath = save_path, compress = compress)
  
  return(new_rf)
}


#' @description
#'  Runs nanotel from linux.
#' @param nanotel_path - The path for nanotel including the directory.
#' @param input_path - The path for input file/dir.
#' @param save_path - the path to save output.
#' @param pattern - The pattern/s to search.
#' @param min_density - The number for min_density flag. should be in range [0.5,1]
#' @param right_edge - If true use the --check_right_edge flag.
#' @param tvr_patterns - If not NA, search additional tvrs given as a string
#'                        (for example: for patterns such as CCTAA, CCCCAA use 
#'                        "\"CCTAA CCCCAA\"" string.
run_nanotel <- function(nanotel_path, input_path, save_path, pattern, min_density=0.6, right_edge=FALSE, tvr_patterns=NA)
{
  system_str <- "Rscript --vanilla"
  system_str <- str_c(system_str, nanotel_path, sep = " ")
  
  # add input path 
  system_str <- str_c(system_str, "-i", input_path, sep = " ")
  
  # add save path
  system_str <- str_c(system_str, "--save_path", save_path, sep = " ")
  
  # add format fasta (We assume genome ref is fasta format)
  system_str <- str_c(system_str, "--format", "fasta", sep = " ")
  
  
  
  system_str <- str_c(system_str, "--patterns", pattern, sep = " ")
  
  system_str <- str_c(system_str, "--min_density", toString(min_density), sep = " ")
  
  
  if(right_edge == TRUE)
  {
    system_str <- str_c(system_str, "--check_right_edge", sep = " ")
  }
  
  if(is.na(tvr_patterns) == FALSE) {
    system_str <- str_c(system_str, "--tvr_patterns", tvr_patterns, sep = " ")
  }
  
  
  # run nanotel command
  system(system_str)
  
}




#' @description
#' this function get indices for sub-telomeric regions and length for the 
#' subtelomers and replace all but the subtelos to Ns.
#' example: (CCCTAA)nAACCCTGA([ACGT]n2)AACCCTGA(TTAGGG)n3 turns to 
#'          (NNNNNN)nAACCCTGA([N]n2)   AACCCTGA(NNNNNN)n3 
#' 
#' @param genome_path: A path to a genome referrence.
#' @param indices_path: A path to a data frame which contains the folllowing columns: 
#'  1.chrom: The chromosome name
#'  2.chrom_length: The length of the chromosome
#'  3.subtelo_Head_start_index: The start of the sub-Telomere to the left.
#'  4.subtelo_Tail_end_index: The end of the sub-Telomere to the right.
#' @param output_path: A path to save the new reference: Make sure t give a fasta/fa/fna extension or fasta.gz if it compressed .
#' @param subtelo_length: The length of the subtelomre which we want to save, all but the subtelomres 
#'  with this given length will become Ns.
#' @param compress: If true the new reference will be compressed. (gz extension)   
#' @return The new reference as a DNAStringset object.   
fill_n <- function(genome_path, indices_path, output_path, subtelo_length, compress=TRUE)
{
  
  indices_df <- read_csv(file = indices_path, col_types = c("c", "i", "i", "i"))
  
  N_ref <- DNAStringSet()
  i <- 1
  while(i <= nrow(indices_df)) {
    curr_chr <- readDNAStringSet(filepath = open_input_files(genome_path), nrec = 1, skip = i - 1)
    
    curr_row <- indices_df %>% dplyr::filter(chrom == names(curr_chr))
    assert::assert(fact = width(curr_chr) == curr_row$chrom_length)
    
    # need to create 2 Iranges for Telomere CCCTAA  middle and  Telomere TTAGGG
    iranges_starts <- c(1, curr_row$subtelo_Head_start_index + subtelo_length, curr_row$subtelo_Tail_end_index +1 )
    iranges_ends <- c(curr_row$subtelo_Head_start_index - 1, curr_row$subtelo_Tail_end_index - subtelo_length, curr_row$chrom_length)
    iranges_names = c("left_telomere", "middle", "right_telomere")
    iranges <- IRanges(start = iranges_starts, end = iranges_ends, names = iranges_names)
    
    # assert subtelo length is not too long
    assert::assert(end(iranges)[1] < start(iranges)[2] && end(iranges)[2] < start(iranges)[3] )
    
    values <- c(str_flatten(rep("N", width(iranges[1]))), str_flatten(rep("N", width(iranges[2]))), str_flatten(rep("N", width(iranges[3])) ))
    
    curr_N_chr <- replaceAt(x = curr_chr, at = iranges, value = values)
    
    N_ref <- append(N_ref, curr_N_chr)
    # move to the next chromosome
    i <- i + 1
  } # end of while loop
  
  remove(values)
  remove(curr_chr)
  remove(curr_N_chr)
  
  
  writeXStringSet(x = N_ref, filepath = output_path, compress = compress)
  
  return(N_ref)
}






################### Mus musculus strain C57BL/6  T2T genoe ref $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

'''
This is the path for T2t mouse:
https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_050437135.1/
'''


genome_path <- "~/ncbi_dataset/ncbi_dataset/data/GCA_050437135.1/GCA_050437135.1_T2T_mhaESC_v1.0_genomic.fna"


genome <- readDNAStringSet(filepath = genome_path)
mm_20k <- create_chr_edges(genome = genome, edge_length = 20000, 
                           save_path = "~/ncbi_dataset/ncbi_dataset/data/GCA_050437135.1/GCA_050437135.1_T2T_mhaESC_v1.0_genomic-20k-edges.fa")



ref_20k <- "~/ncbi_dataset/ncbi_dataset/data/GCA_050437135.1/GCA_050437135.1_T2T_mhaESC_v1.0_genomic-20k-edges.fa"
run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R", input_path = ref_20k , save_path = "~/ncbi_dataset/GCA_050437135.1_T2T_mhaESC_v1.0_genomic-CCCTAA", pattern = "CCCTAA", min_density = 0.5, right_edge = FALSE)
run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R", input_path = ref_20k, save_path = "~/ncbi_dataset/GCA_050437135.1_T2T_mhaESC_v1.0_genomic-TTAGGG", pattern = "TTAGGG", min_density = 0.5, right_edge = TRUE)



# check manually if the indices are accurate
tails <- read_csv(file = ref_20k)
tails$chrom <- str_remove(tails$sequence_ID, "_Tail")


mm_20k <- readDNAStringSet(filepath = ref_20k)
ref_20k_tail <- mm_20k[str_detect(names(mm_20k), pattern = "Tail")]

# the index where the last nuc is the subtelo befor the telomere starts
subtelo_tail_index <- integer()

chr1 <- ref_20k_tail[1]
subtelo_tail_index <-c(subtelo_tail_index, 18948)

chr2 <- ref_20k_tail[2] # 13582
subtelo_tail_index <-c(subtelo_tail_index, 13588)


chr3 <- ref_20k_tail[3] # 12753

subtelo_tail_index <-c(subtelo_tail_index, 12753)

chr4 <- ref_20k_tail[4] # 18782

subtelo_tail_index <-c(subtelo_tail_index, 18783)

chr5 <- ref_20k_tail[5] # 18365

subtelo_tail_index <-c(subtelo_tail_index, 18365)




chr6 <- ref_20k_tail[6] # 15593
subtelo_tail_index <-c(subtelo_tail_index, 15593)




chr7 <- ref_20k_tail[7] # 15689

subtelo_tail_index <-c(subtelo_tail_index, 15689)



chr8 <- ref_20k_tail[8] # 11949


subtelo_tail_index <-c(subtelo_tail_index, 11949)



chr9 <- ref_20k_tail[9] # 15923

subtelo_tail_index <-c(subtelo_tail_index, 15922)



chr10 <- ref_20k_tail[10] # 15961
subtelo_tail_index <-c(subtelo_tail_index, 15961)


chr11 <- ref_20k_tail[11] # 11508
subtelo_tail_index <-c(subtelo_tail_index, 11508)


chr12 <- ref_20k_tail[12] # 10037
subtelo_tail_index <-c(subtelo_tail_index, 10037)


chr13 <- ref_20k_tail[13] # 6935
subtelo_tail_index <-c(subtelo_tail_index, 6927)


chr14 <- ref_20k_tail[14] # 5508
subtelo_tail_index <-c(subtelo_tail_index, 5508)


chr15 <- ref_20k_tail[15] # 7734
subtelo_tail_index <-c(subtelo_tail_index, 7734)



chr16 <- ref_20k_tail[16] # 12295
subtelo_tail_index <-c(subtelo_tail_index, 12294)


chr17 <- ref_20k_tail[17] # 17764
subtelo_tail_index <-c(subtelo_tail_index, 17764)


chr18 <- ref_20k_tail[18] # 14215 - problematic : tvrs like TCAAGGG

# 13560 ?
subtelo_tail_index <-c(subtelo_tail_index, 13560)

chr19 <- ref_20k_tail[17] # 12148
subtelo_tail_index <-c(subtelo_tail_index, 12170)

chrX <- ref_20k_tail[20] # 14590
subtelo_tail_index <-c(subtelo_tail_index, 14586)


# create chrom and lengtt chrom table 
chrom_length <- tibble(chrom = names(genome), chrom_length = width(genome))

# add last index of subtelomere before tail telomeres
chrom_length$subtelo_index_end <- subtelo_tail_index

# adjust indices for tail telo_start/teloe_end <- telo_start/teloe_end + edge_length - edge_length
chrom_length <- chrom_length %>% 
  mutate(subtelo_tail_index_adjust = chrom_length + subtelo_index_end - 2e4)


# check  genome
subseq(genome[1], start = 206960434+1 , end = 206961486 ) # works!


# now find CCCTAA subtelos indices (5' (CCCTAA)n....... )
# check manually if the indices are accurate
heads <- read_csv(file = "~/ncbi_dataset/GCA_050437135.1_T2T_mhaESC_v1.0_genomic-CCCTAA/summary.csv")
heads$chrom <- str_remove(heads$sequence_ID, "_Head")



# we have duplicates
heads_arrang <- heads %>% arrange(Telomere_end_mismatch) %>%  select(sequence_ID, Telomere_end_mismatch)
# 3 clusters: (6, X) , (3, 9, 10 ,13) , (2, 5, 14 , 15, 17 , 18 , 19)

# the index where the last nuc is the subtelo befor the telomere starts
subtelo_head_index <- integer()

ref_20k_head <- mm_20k[str_detect(names(mm_20k), pattern = "Head")]




heads$Telomere_end_mismatch <- as.integer(heads$Telomere_end_mismatch)
count(x = heads, Telomere_end_mismatch)


Telomere_end_mismatch
# 
# 7359
# 8055
# 5714
# 7359
# 7047
# 6518
# 7886
# 8055
# 8055
# 3461
# 8338
# 4681
# 7359
# 7359
8055
7359
7359
7359
7047
# lets check identity
# 2, 5 , 14, 15 , 17 , 18, 19 are identical
(toString(ref_20k_head[2]) == toString(ref_20k_head[5])) & 
  (toString(ref_20k_head[5]) == toString(ref_20k_head[14])) & 
  (toString(ref_20k_head[14]) == toString(ref_20k_head[15])) & 
  (toString(ref_20k_head[15]) == toString(ref_20k_head[17])) & 
  (toString(ref_20k_head[17]) == toString(ref_20k_head[18])) & 
  (toString(ref_20k_head[18]) == toString(ref_20k_head[19])) 

# 6 and X are identical
toString(ref_20k_head[6]) == toString(ref_20k_head[20])



chr1 <- ref_20k_head[1] # 6135
subtelo_head_index <-c(subtelo_head_index, 6135)

# 3, 9 , 10, 16 have similar telomeres

chr2 <- ref_20k_head[2] # 7359 ( 5 , 14, 15 , 17 , 18, 19 are identical)
subtelo_head_index <-c(subtelo_head_index, 7359)

chr3 <- ref_20k_head[3] # 8055
subtelo_head_index <-c(subtelo_head_index, 8055)

chr4 <- ref_20k_head[4] # 5714
subtelo_head_index <-c(subtelo_head_index, 5714)

chr5 <- ref_20k_head[5]
subtelo_head_index <-c(subtelo_head_index, 7359)

chr6 <- ref_20k_head[6] # 7047 X identical
subtelo_head_index <-c(subtelo_head_index, 7047)

chr7 <- ref_20k_head[7] # 6518
subtelo_head_index <-c(subtelo_head_index, 6518)

chr8 <- ref_20k_head[8] # 7886
subtelo_head_index <-c(subtelo_head_index, 7886)

chr9 <- ref_20k_head[9] # 8055
subtelo_head_index <-c(subtelo_head_index, 8054)

chr10 <- ref_20k_head[10] # 8055
subtelo_head_index <-c(subtelo_head_index, 8054)

chr11 <- ref_20k_head[11] # 3461
subtelo_head_index <-c(subtelo_head_index, 3461)

chr12 <- ref_20k_head[12] # 8338
subtelo_head_index <-c(subtelo_head_index, 8338)

chr13 <- ref_20k_head[13] # 4681
subtelo_head_index <-c(subtelo_head_index, 4681)



chr14 <- ref_20k_head[14] # 8055
subtelo_head_index <-c(subtelo_head_index, 7359)

chr15 <- ref_20k_head[15] 
subtelo_head_index <-c(subtelo_head_index, 7359)

chr16 <- ref_20k_head[16] # 8055
subtelo_head_index <-c(subtelo_head_index, 8055)

chr17 <- ref_20k_head[17]
subtelo_head_index <-c(subtelo_head_index, 7359)

chr18 <- ref_20k_head[18]
subtelo_head_index <-c(subtelo_head_index, 7359)

chr19 <- ref_20k_head[19]
subtelo_head_index <-c(subtelo_head_index, 7359)

chrX <- ref_20k_head[20] #
subtelo_head_index <-c(subtelo_head_index, 7047)


# validate - tail\head index ~ telomere_index
heads <- heads %>%  arrange(sequence_ID)
heads <- heads %>% dplyr::filter(sequence_ID != "CM115064.1 Mus musculus strain C57BL/6 chromosome 15, whole genome shotgun sequence_Tail")



abs(heads$Telomere_end_mismatch - subtelo_head_index) # works



tails <- tails %>%  arrange(sequence_ID)
abs(tails$Telomere_start_mismatch - subtelo_tail_index) # works


chrom_length$subtelo_Head_start_index <- subtelo_head_index


chrom_length$subtelo_Tail_end_index <- chrom_length$subtelo_tail_index_adjust

final_csv <- chrom_length %>% 
  dplyr::select(chrom, chrom_length, subtelo_Head_start_index, subtelo_Tail_end_index)
save_path <- "~/ncbi_dataset/ncbi_dataset/data/subtelo_indices-Mus-musculus-strain-C57BL-6.csv"  
write_csv(x = final_csv, file = save_path ) # use csv for data 


indices_df <- chrom_length %>% 
  select("chrom", "chrom_length", "subtelo_Head_start_index", 
         "subtelo_Tail_end_index")




# test fill N function:

# args for the function:
subtelo_length <- 2e5
genome_path <- "~/ncbi_dataset/ncbi_dataset/data/GCA_050437135.1/GCA_050437135.1_T2T_mhaESC_v1.0_genomic.fna"
indices_path <- "~/ncbi_dataset/ncbi_dataset/data/subtelo_indices-Mus-musculus-strain-C57BL-6.csv"  
 
output_path <- "ncbi_dataset/ncbi_dataset/data/GCA_050437135.1/GCA_050437135.1_T2T_mhaESC_v1.0_genomic-200k-subtelos-N.fasta.gz"
compress <- TRUE

indices_df <- read_csv(file = indices_path, col_types = c("c", "i", "i", "i"))


N_ref <- DNAStringSet()
i <- 1
while(i <= nrow(indices_df)) {
  curr_chr <- readDNAStringSet(filepath = open_input_files(genome_path), nrec = 1, skip = i - 1)
  
  curr_row <- indices_df %>% dplyr::filter(chrom == names(curr_chr))
  assert(fact = width(curr_chr) == curr_row$chrom_length)
  
  # need to create 2 Iranges for Telomere CCCTAA  middle and  Telomere TTAGGG
  iranges_starts <- c(1, curr_row$subtelo_Head_start_index + subtelo_length, curr_row$subtelo_Tail_end_index +1 )
  iranges_ends <- c(curr_row$subtelo_Head_start_index - 1, curr_row$subtelo_Tail_end_index - subtelo_length, curr_row$chrom_length)
  iranges_names = c("left_telomere", "middle", "right_telomere")
  iranges <- IRanges(start = iranges_starts, end = iranges_ends, names = iranges_names)
  
  # assert subtelo length is not too long
  assert(end(iranges)[1] < start(iranges)[2] && end(iranges)[2] < start(iranges)[3] )
  
  values <- c(str_flatten(rep("N", width(iranges[1]))), str_flatten(rep("N", width(iranges[2]))), str_flatten(rep("N", width(iranges[3])) ))
  
  curr_N_chr <- replaceAt(x = curr_chr, at = iranges, value = values)
  
  N_ref <- append(N_ref, curr_N_chr)
  
  
  
  i <- i + 1
}
remove(values)
remove(curr_chr)
remove(curr_N_chr)


writeXStringSet(x = N_ref, filepath = output_path, compress = compress)



system_str <- ifelse(compress,str_c("awk 1 ", output_dir, "/*.fasta.gz > " , output_dir, "/", output_name, ".fasta.gz"),
                    str_c("awk 1 ", output_dir, "/*.fasta > " , output_dir, "/", output_name, "fa")) 

# run nanotel command
system(system_str)


# check output 
test_N

# check the new function
test_N2 <- fill_n(genome_path = "~/ncbi_dataset/ncbi_dataset/data/GCA_050437135.1/GCA_050437135.1_T2T_mhaESC_v1.0_genomic.fna",
                  indices_path = "~/ncbi_dataset/ncbi_dataset/data/subtelo_indices-Mus-musculus-strain-C57BL-6.csv", 
                  output_path = "ncbi_dataset/ncbi_dataset/data/GCA_050437135.1/GCA_050437135.1_T2T_mhaESC_v1.0_genomic-200k-subtelos-N.fasta.gz", 
                  subtelo_length = 2e5, compress = TRUE)

################### End of Mus musculus strain C57BL/6  T2T genoe ref $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$





############### check Zebra Fish ###############################################

# Zebra Fish genome: GCA_052040795.1
zebra_path <- "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/ncbi_dataset/ncbi_dataset/data/GCA_052040795.1/GCA_052040795.1_GRCz12ab_genomic.fna.gz"

zebra_genome <- readDNAStringSet(filepath = zebra_path)
zebra_chr_edges_50k <- create_chr_edges(genome = zebra_genome, edge_length = 5e4,save_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/ncbi_dataset/ncbi_dataset/data/GCA_052040795.1/GCA_052040795.1_GRCz12ab_genomic-50kEdges.fna.gz")

df_head_counts <- tibble(chr = names(reads_head), CCCCTAGTTGACTA= v1, CCCCTAGTTCGCTCTA=v2, CCCCTAGAACTCTTA=v5, CCCCTAGTTGACTCT=v6)

# tail - should be 19 
v1t <- vcountPattern(pattern = reverseComplement(DNAString( tvr_pattern_1)) , subject = reads_tail)
v2t <- vcountPattern(pattern = reverseComplement(DNAString( tvr_pattern_2)) , subject = reads_tail)
v3t <- vcountPattern(pattern = reverseComplement(DNAString( tvr_pattern_3)) , subject = reads_tail)

v4t <- vcountPattern(pattern = reverseComplement(DNAString( tvr_pattern_4)) , subject = reads_tail) # 0 
v5t <- vcountPattern(pattern = reverseComplement(DNAString( tvr_pattern_5)) , subject = reads_tail) # 0
v6t <- vcountPattern(pattern = reverseComplement(DNAString( tvr_pattern_6)) , subject = reads_tail) # 0

df_tail <- tibble(chr = names(reads_tail), TAGTCAACTAGGGG=v1t, TAGAGCGAACTAGGG=v2t, TAAGAGTCCTAGGGG=v3t)


zebra_fish_tvr_list_Head <- c("CCCCTAGTTGACTA", "CCCCTAGTTCGCTCTA", "CCCCTAGAACTCTTA", "CCCCTAGTTGACTCT")
zebra_fish_tvr_list_Tail <-c("TAGTCAACTAGGGG", "TAGAGCGAACTAGGG", "TAAGAGTCCTAGGGG")
                              TAGTCAACTAGGGG
tvr_string_Head <- str_c("\"", stringr::str_flatten(zebra_fish_tvr_list_Head, " ") , "\"")
tvr_string_Tail <- str_c("\"", stringr::str_flatten(zebra_fish_tvr_list_Tail, " ") , "\"")

#Heads
run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R", input_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/ncbi_dataset/ncbi_dataset/data/GCA_052040795.1/GCA_052040795.1_GRCz12ab_genomic-50kEdges.fna.gz", save_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-50k-Heads", pattern = "CCCTAA", min_density = 0.6, right_edge = FALSE , tvr_patterns = tvr_string_Head)

#Tails
run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R", input_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/ncbi_dataset/ncbi_dataset/data/GCA_052040795.1/GCA_052040795.1_GRCz12ab_genomic-50kEdges.fna.gz", save_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-50k-Tails", pattern = "TTAGGG", min_density = 0.6, right_edge = TRUE , tvr_patterns = tvr_string_Tail)


# load the edges

# Tail 
tail_50k <- readDNAStringSet(filepath = dir(path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-50k-Tails/reads", full.names = TRUE))
tail_50k <- tail_50k[str_detect(names(tail_50k), pattern = "Tail")]

# end of subtelo index
subtelo_tail_index <- integer()

chr_1 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 1,")] # 39735
subtelo_tail_index <- c(subtelo_tail_index, 39728)




chr_2 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 2,")] # 38189
subtelo_tail_index <- c(subtelo_tail_index, 38183)

chr_3 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 3,")] # 37199
subtelo_tail_index <- c(subtelo_tail_index, 37200)

chr_4 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 4,")] # 49335

telo_app <- subseq(x = chr_4, start = 49256, end = 5e4)

v1 <- matchPattern(pattern = "TTAGGG", subject = toString(telo_app), max.mismatch = 1)
v2 <- matchPattern(pattern = "TTAGGG", subject = toString(telo_app), max.mismatch = 1, with.indels = TRUE)
v1_df <- as.data.frame(v1)
v2_df <- as.data.frame(v2)



subtelo_tail_index <- c(subtelo_tail_index, 49256)



chr_5 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 5,")] # 33320
subtelo_tail_index <- c(subtelo_tail_index, 33320)

# serial number == 22
chr_6 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 6,")] # 29305 or 37556 (There is a TVR island)

subtelo_tail_index <- c(subtelo_tail_index, 37550)

# serial number 34 , tvr :TAGTCAACTAGGGG
chr_7 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 7,")] # 15393 or 42372 or 33320

chr_7_remove_island <- replaceAt(x = chr_7, 
                                 at = IRanges(start = 15000, end = 21000), 
                                 value = str_flatten(rep("N", 6001)) )
Biostrings::writeXStringSet(x =  chr_7_remove_island, filepath = "chr7_tail_island-removed.fasta")

run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R", input_path = "chr7_tail_island-removed.fasta", save_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-chr7_no-island-Tail", pattern = "TTAGGG", min_density = 0.6, right_edge = TRUE , tvr_patterns = tvr_string_Tail)



subtelo_tail_index <- c(subtelo_tail_index, 33320)
names(subtelo_tail_index) <- c("chr_1", "chr_2", "chr_3", "chr_4", "chr_5", "chr_6", "chr_7")


# TAGTCAACTAGGGG 
chr_8 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 8,")] # 11596
subtelo_tail_index <- c(subtelo_tail_index, chr_8 = 11596)


# TAGTCAACTAGGGG 
chr_9 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 9,")] # 38592
subtelo_tail_index <- c(subtelo_tail_index, chr_9 = 38592)


# TAGTCAACTAGGGG 
chr_10 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 10,")] # 28515
subtelo_tail_index <- c(subtelo_tail_index, chr_10 = 28515)


# TAGTCAACTAGGGG 
chr_11 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 11,")] # 32658
subtelo_tail_index <- c(subtelo_tail_index, chr_11 = 32657)


# TAGTCAACTAGGGG 
# serial number 47
chr_12 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 12,")] # 17172



chr_12_remove_island <- replaceAt(x = chr_12, 
                                 at = IRanges(start = 17000, end = 30000), 
                                 value = str_flatten(rep("N", 13001)) )
Biostrings::writeXStringSet(x =  chr_12_remove_island, filepath = "chr_12_tail_island-removed.fasta")
run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R", input_path = "chr_12_tail_island-removed.fasta", save_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-chr_12_no-island-Tail", pattern = "TTAGGG", min_density = 0.6, right_edge = TRUE , tvr_patterns = "TAGTCAACTAGGGG")
# 34387
subtelo_tail_index <- c(subtelo_tail_index, chr_12 = 34388)


# TAAGAGTCCTAGGGG TVR
chr_13 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 13,")] # 40161
subtelo_tail_index <- c(subtelo_tail_index,chr_13 = 40161)

# serial number == 24, TAGTCAACTAGGGG TVR
chr_14 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 14,")] # 20456

chr_14_remove_island <- replaceAt(x = chr_14, 
                                  at = IRanges(start = 20456, width = 7500), 
                                  value = str_flatten(rep("N", 7500)) )

Biostrings::writeXStringSet(x =  chr_14_remove_island, filepath = "chr_14_tail_island-removed.fasta")
run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R", input_path = "chr_14_tail_island-removed.fasta", save_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-chr_14_no-island-Tail", pattern = "TTAGGG", min_density = 0.6, right_edge = TRUE , tvr_patterns = "TAGTCAACTAGGGG")

# new indexx: 34387
subtelo_tail_index <- c(subtelo_tail_index, chr_14 = 34388)

# TAGTCAACTAGGGG TVR
chr_15 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 15,")] # 33320
subtelo_tail_index <- c(subtelo_tail_index, chr_15 = 33320)


#  16 19 24 - no TVR
chr_16 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 16,")] # 34154
subtelo_tail_index <- c(subtelo_tail_index, chr_16 = 34153)

# TAGTCAACTAGGGG TVR
chr_17 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 17,")] # 39656
subtelo_tail_index <- c(subtelo_tail_index, chr_17 = 39655)


# TAGAGCGAACTAGGG TVR
chr_18 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 18,")] # 39055
subtelo_tail_index <- c(subtelo_tail_index, chr_18 = 39040)



#  16 19 24 - no TVR
chr_19 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 19,")] # 31557
subtelo_tail_index <- c(subtelo_tail_index,chr_19 = 31544)


# TAGTCAACTAGGGG TVR
chr_20 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 20,")] # 33320
subtelo_tail_index <- c(subtelo_tail_index, chr_20 = 33320)


# TAGTCAACTAGGGG TVR
chr_21 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 21,")] # 24257
subtelo_tail_index <- c(subtelo_tail_index, chr_21 = 24256)

# TAGTCAACTAGGGG TVR
chr_22 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 22,")] # 42158
subtelo_tail_index <- c(subtelo_tail_index, chr_22 = 42158)

# TAGTCAACTAGGGG TVR
chr_23 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 23,")] # 27316  

subtelo_tail_index <- c(subtelo_tail_index, chr_23 = 27317)


#  16 19 24 - no TVR
chr_24 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 24,")] # 44648
subtelo_tail_index <- c(subtelo_tail_index, chr_24 = 44647)



# TAGAGCGAACTAGGG TVR
chr_25 <- tail_50k[str_detect(names(tail_50k), pattern = "chromosome 25,")] # 36806
subtelo_tail_index <- c(subtelo_tail_index, chr_25 = 36806)

chrom_length <- tibble(chrom = names(zebra_genome), chrom_length = width(zebra_genome))


# add last index of subtelomere before tail telomeres
chrom_length$subtelo_index_end <- subtelo_tail_index

# adjust indices for tail 
chrom_length <- chrom_length %>% 
  mutate(subtelo_tail_index_adjust = chrom_length + subtelo_index_end - 5e4)

# save 
write_csv(x = chrom_length, file = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/subtelo_tail_index.csv")



arrange(count(tibble(chr = 1:25, index=subtelo_tail_index), index), desc(n))
'''
   index     n
   <dbl> <int>    
 1 33320     4 : chr_5, chr_7, chr_15, chr_20, -> identical for the last 20,000 nucs
 2 34388     2 : 12, 14 -> identical for the last 20,000 nucs
'''
names_short <- str_c("chromosome ", 1:25, ",")
tail_50k_arranged <- DNAStringSet()
for(i in seq_along(names_short)) 
{
  tail_50k_arranged <- append(tail_50k_arranged, tail_50k[str_detect(names(tail_50k), pattern = names_short[i])])
}


pwalign::pairwiseAlignment(subseq(tail_50k_arranged[12], end = 50000, width = 20000), subseq(tail_50k_arranged[14], end = 50000, width = 20000) )
toString(subseq(tail_50k_arranged[12], end = 50000, width = 3e4)) == toString(subseq(tail_50k_arranged[14], end = 5e4, width = 3e4) )


# 5 7 15 21
toString(subseq(tail_50k_arranged[5], end = 50000, width = 2e4)) == toString(subseq(tail_50k_arranged[7], end = 5e4, width = 2e4) )
toString(subseq(tail_50k_arranged[5], end = 50000, width = 2e4)) == toString(subseq(tail_50k_arranged[15], end = 5e4, width = 2e4) )
toString(subseq(tail_50k_arranged[5], end = 50000, width = 2e4)) == toString(subseq(tail_50k_arranged[20], end = 5e4, width = 2e4) )


pwalign::pairwiseAlignment(subseq(tail_50k[5], end = 50000, width = 20000), subseq(tail_50k[25], end = 50000, width = 20000) )
pwalign::pairwiseAlignment(subseq(tail_50k[25], end = 50000, width = 20000), subseq(tail_50k[13], end = 50000, width = 20000) )
pwalign::pairwiseAlignment(subseq(tail_50k[25], end = 50000, width = 20000), subseq(tail_50k[15], end = 50000, width = 20000) )
pwalign::pairwiseAlignment(subseq(tail_50k[25], end = 50000, width = 20000), subseq(tail_50k[22], end = 50000, width = 20000) )


pwalign::pairwiseAlignment(subseq(tail_50k[25], end = 50000, width = 40000), subseq(tail_50k[25], end = 50000, width = 40000) )
pwalign::pairwiseAlignment(subseq(tail_50k[25], end = 50000, width = 40000), subseq(tail_50k[13], end = 50000, width = 40000) )
pwalign::pairwiseAlignment(subseq(tail_50k[25], end = 50000, width = 40000), subseq(tail_50k[15], end = 50000, width = 40000) )
pwalign::pairwiseAlignment(subseq(tail_50k[25], end = 50000, width = 40000), subseq(tail_50k[22], end = 50000, width = 40000) )


pwalign::pairwiseAlignment(subseq(tail_50k[25], end = 50000, width = 40000), subseq(tail_50k[25], end = 50000, width = 40000) , type = "local")
pwalign::pairwiseAlignment(subseq(tail_50k[25], end = 50000, width = 40000), subseq(tail_50k[13], end = 50000, width = 40000) , type = "local")
pwalign::pairwiseAlignment(subseq(tail_50k[25], end = 50000, width = 40000), subseq(tail_50k[15], end = 50000, width = 40000) , type = "local")
pwalign::pairwiseAlignment(subseq(tail_50k[25], end = 50000, width = 40000), subseq(tail_50k[22], end = 50000, width = 40000) , type = "local")

pwalign::pairwiseAlignment(subseq(tail_50k[13], end = 50000, width = 40000), subseq(tail_50k[15], end = 50000, width = 40000) , type = "local")


# Heads/Tails df -> There are a lot of similarity ...
df_head <- read_csv(file = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-50k-Heads/summary.csv", col_types = "icidiiidiiidiii")
df_tail <- read_csv(file = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-50k-Tails/summary.csv", col_types = "icidiiidiiidiii")
df_tail <- df_tail %>% 
  dplyr::filter(str_detect(sequence_ID,pattern = "Tail"))



head_50k <- readDNAStringSet(filepath = dir(path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-50k-Heads/reads", full.names = TRUE))

head_50k <- head_50k[str_detect(names(head_50k), pattern = "Head")]

subtelo_head_index <- integer()

# 1 is problematic: It has a huge hole in the middle: we will not include what comes next as part of a telomere but a telomeric island
chr_1 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 1,")]

chr_1_remove_island <- replaceAt(x = chr_1, 
                                  at = IRanges(start = 21000, width = 8500), 
                                  value = str_flatten(rep("N", 8500)) )

Biostrings::writeXStringSet(x =  chr_1_remove_island, filepath = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-50k-Heads/chr1_removed_island.fasta")

run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R", input_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-50k-Heads/chr1_removed_island.fasta" , save_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-chr_1_no-island-Head", pattern = "CCCTAA", min_density = 0.6, right_edge = FALSE , tvr_patterns = "CCCCTAGTTGACTA")


# view TVR counts head
tvr_head <- count_patterns(subject = head_50k, 
             pattern_list = list("CCCCTAGTTGACTA", "CCCCTAGTTCGCTCTA", 
                                 "CCCCTAGAACTCTTA", "CCCCTAGTTGACTCT"))
tvr_head$chr <- str_extract(tvr_head$chr, pattern = "chromosome \\d+")
tvr_head$chr <- str_extract(tvr_head$chr, pattern = "\\d+")
tvr_head$chr <- as.integer(tvr_head$chr)
tvr_head <- tvr_head %>% arrange(chr)



# CCCCTAGTTGACTA pattern
# 15588
subtelo_head_index <- c(subtelo_head_index, chr_1 = 15589)

## 11051
chr_2 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 2,")]
subtelo_head_index <- c(subtelo_head_index, chr_2 = 11052)

# CCCCTAGTTCGCTCTA
# 10380
chr_3 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 3,")]
subtelo_head_index <- c(subtelo_head_index, chr_3= 10380)

test_CCCCTAGTTGACTA <- vmatchPattern(pattern = "CCCCTAGTTGACTA", subject = head_50k)
df_CCCCTAGTTGACTA <- as.data.frame(sapply(test_CCCCTAGTTCGCTCTA, length))
df_CCCCTAGTTGACTA$chr <- str_extract(row.names(df_CCCCTAGTTGACTA), pattern = "chromosome \\d+")
row.names(df_CCCCTAGTTGACTA) <- NULL

df_CCCCTAGTTGACTA <- df_CCCCTAGTTGACTA %>% 
  mutate(CCCCTAGTTCGCTCTA_counts = sapply(test_CCCCTAGTTCGCTCTA, length)) %>% 
  select(chr, CCCCTAGTTCGCTCTA_counts)

test_CCCCTAGTTCGCTCTA <- vmatchPattern(pattern = "CCCCTAGTTCGCTCTA", subject = head_50k)
test_CCCCTAGAACTCTTA <- vmatchPattern(pattern = "CCCCTAGAACTCTTA", subject = head_50k)
test_CCCCTAGTTGACTCT <- vmatchPattern(pattern = "CCCCTAGTTGACTCT", subject = head_50k)

# CCCCTAGTTGACTA CCCCTAGTTCGCTCTA CCCCTAGAACTCTTA CCCCTAGTTGACTCT 
# 21275 CCCCTAGAACTCTTA
chr_4 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 4,")]
subtelo_head_index <- c(subtelo_head_index, chr_4= 21276)

# no TVR 3001
chr_5 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 5,")]

subtelo_head_index <- c(subtelo_head_index, chr_5= 3001)



# CCCCTAGTTGACTA 22265
chr_6 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 6,")]

subtelo_head_index <- c(subtelo_head_index, chr_6= 22265)


# CCCCTAGTTGACTA 15614
chr_7 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 7,")]
subtelo_head_index <- c(subtelo_head_index, chr_7= 15615)

# CCCCTAGTTGACTCT 21797
chr_8 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 8,")]
subtelo_head_index <- c(subtelo_head_index, chr_8=21797)



# CCCCTAGTTGACTA
  
chr_9 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 9,")]
subtelo_head_index <- c(subtelo_head_index, chr_9= 38634)

# no tvr
chr_10 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 10,")]
subtelo_head_index <- c(subtelo_head_index, chr_10=3001)


# no tvr
chr_11 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 11,")]
subtelo_head_index <- c(subtelo_head_index, chr_11= 14570)

# no tvr 3001
chr_12 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 12,")]
subtelo_head_index <- c(subtelo_head_index, chr_12= 3001)


# CCCCTAGTTGACTA 21464
chr_13 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 13,")]
subtelo_head_index <- c(subtelo_head_index, chr_13= 21464)


# no tvr ~ 3000 
chr_14 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 14,")]

Biostrings::writeXStringSet(x=subseq(chr_14, start = 1, width = 40000), filepath = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-50k-Heads/chr_14-40k.fasta")

run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R", 
            input_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-50k-Heads/chr_14-40k.fasta" , 
            save_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-chr_14_no-island-Head", 
            pattern = "CCCTAA", min_density = 0.6, right_edge = FALSE )

subtelo_head_index <- c(subtelo_head_index, chr_14= 3001)


# CCCCTAGTTCGCTCTA 13231
chr_15 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 15,")]
subtelo_head_index <- c(subtelo_head_index, chr_15= 13230)


# CCCCTAGTTCGCTCTA 
chr_16 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 16,")]
subtelo_head_index <- c(subtelo_head_index, chr_16=13351 )


# CCCCTAGTTGACTA
chr_17 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 17,")]
subtelo_head_index <- c(subtelo_head_index, chr_17= 13913)


# CCCCTAGTTCGCTCTA
chr_18 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 18,")]
subtelo_head_index <- c(subtelo_head_index, chr_18= 7903)


# CCCCTAGTTGACTA
chr_19 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 19,")]
subtelo_head_index <- c(subtelo_head_index, chr_19=15397)


# no tvr
chr_20 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 20,")]
subtelo_head_index <- c(subtelo_head_index, chr_20=4870)


# CCCCTAGTTGACTA
chr_21 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 21,")]
subtelo_head_index <- c(subtelo_head_index, chr_21= 5951)


# CCCCTAGTTGACTA
chr_22 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 22,")]
subtelo_head_index <- c(subtelo_head_index, chr_22=16305 )


# CCCCTAGTTCGCTCTA
chr_23 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 23,")]


Biostrings::writeXStringSet(x=subseq(chr_23, start = 1, width = 18000), filepath = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-50k-Heads/chr_23-18k.fasta")

run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R", 
            input_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-50k-Heads/chr_23-18k.fasta" , 
            save_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/nanotel_output-chr_23_no-island-Head", 
            pattern = "CCCTAA", min_density = 0.6, right_edge = FALSE )


subtelo_head_index <- c(subtelo_head_index, chr_23= 12600) # 12600





# no tvr
chr_24 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 24,")]
subtelo_head_index <- c(subtelo_head_index, chr_24= 13991)


# CCCCTAGTTGACTCT
chr_25 <- head_50k[str_detect(names(head_50k), pattern = "chromosome 25,")]
subtelo_head_index <- c(subtelo_head_index, chr_25= 24463)


df_tail <- read_csv(file = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/subtelo_tail_index.csv", col_types = "ciii")

final_df_zebra <- df_tail %>% 
  select(chrom, chrom_length)
final_df_zebra$subtelo_Head_start_index <- subtelo_head_index
final_df_zebra$subtelo_Tail_end_index <- df_tail$subtelo_tail_index_adjust
  
write_csv(x = final_df_zebra, file = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/subtelo_indices-GCA_052040795.1-Danio-rerio-strain-M-AB-ecotype-USA.csv")

fill_n(genome_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/ncbi_dataset/ncbi_dataset/data/GCA_052040795.1/GCA_052040795.1_GRCz12ab_genomic.fna.gz",
       indices_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/subtelo_indices-GCA_052040795.1-Danio-rerio-strain-M-AB-ecotype-USA.csv", 
       output_path = "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/GCA_052040795.1_GRCz12ab_genomic-200k-subtelos-N.fasta.gz", 
       subtelo_length = 200000, compress = TRUE )


############### End of Zebra Fish ##############################################




################### Homo sapiens (human) T2T genome ref  NCBI RefSeq assembly GCF_009914755.1 #############################################
# This is the path for the genome ref : https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_009914755.1/

genome_path <- "~/Human-ref/GCF_009914755.1_T2T-CHM13v2.0_genomic.fna"

genome <- readDNAStringSet(filepath = genome_path)

edges <- create_chr_edges(genome = genome, edge_length = 5e4, save_path ="~/Human-ref/GCF_009914755.1_T2T-CHM13v2.0_genomic-50k-edges.fna" , compress = TRUE)

heads <- edges[str_detect(names(edges), pattern = "Head")]
tails <- edges[str_detect(names(edges), pattern = "Tail")]

writeXStringSet(x = heads, filepath = "~/Human-ref/GCF_009914755.1_T2T-CHM13v2.0_genomic-50k-edges-Heads.fna")
writeXStringSet(x = tails, filepath = "~/Human-ref/GCF_009914755.1_T2T-CHM13v2.0_genomic-50k-edges-Tails.fna")



run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R",
            input_path = "~/Human-ref/GCF_009914755.1_T2T-CHM13v2.0_genomic-50k-edges-Heads.fna" , save_path = "~/Human-ref/CHM13v2.0_genomic-50k-edges-Heads" , pattern = "CCCTAA", min_density = 0.6, right_edge = FALSE)

run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R", input_path = "~/Human-ref/GCF_009914755.1_T2T-CHM13v2.0_genomic-50k-edges-Tails.fna", save_path = "~/Human-ref/CHM13v2.0_genomic-50k-edges-Tails" , pattern = "TTAGGG", min_density = 0.6, right_edge = TRUE)


# check inner islands  : For CCCTAA/TTAGGG island in the Tails/Heads - No inner 
run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R",
            input_path = "~/Human-ref/GCF_009914755.1_T2T-CHM13v2.0_genomic-50k-edges.fna.gzip" 
            , save_path = "~/Human-ref/CHM13v2.0_genomic-50k-edges-Heads-all-edges" 
            , pattern = "CCCTAA", min_density = 0.6, right_edge = FALSE)

run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R", 
            input_path = "~/Human-ref/GCF_009914755.1_T2T-CHM13v2.0_genomic-50k-edges.fna.gzip", 
            save_path = "~/Human-ref/CHM13v2.0_genomic-50k-edges-Tails-all-edges" 
            , pattern = "TTAGGG", min_density = 0.6, right_edge = TRUE)



# the index where the last nuc is the subtelo before the telomere starts
subtelo_tail_index <- integer()

# Telomere_start_mismatch
# 46796
chr_01 <- tails[str_detect(names(tails), pattern = "chromosome 1,")]
subtelo_tail_index <- c(subtelo_tail_index, chr_01 = 46796)



# 47378
chr_02 <- tails[str_detect(names(tails), pattern = "chromosome 2,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_02 = 47378)



# 45370
chr_03 <- tails[str_detect(names(tails), pattern = "chromosome 3,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_03 = 45370)



# 47685
chr_04 <- tails[str_detect(names(tails), pattern = "chromosome 4,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_04 = 47685)


# 48453
chr_05 <- tails[str_detect(names(tails), pattern = "chromosome 5,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_05 = 48439)


# 47221
chr_06 <- tails[str_detect(names(tails), pattern = "chromosome 6,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_06 = 47221)



# 47780
chr_07 <- tails[str_detect(names(tails), pattern = "chromosome 7,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_07 = 47780)



# 47378
chr_08 <- tails[str_detect(names(tails), pattern = "chromosome 8,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_08 = 47378)



# 47029
chr_09 <- tails[str_detect(names(tails), pattern = "chromosome 9,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_09 = 47022)


# 46803
chr_10 <- tails[str_detect(names(tails), pattern = "chromosome 10,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_10 = 46796)



# 47393
chr_11 <- tails[str_detect(names(tails), pattern = "chromosome 11,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_11 = 47393)



# 47717
chr_12 <- tails[str_detect(names(tails), pattern = "chromosome 12,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_12 = 47662)



# 46500
chr_13 <- tails[str_detect(names(tails), pattern = "chromosome 13,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_13 = 46493)



# 48354
chr_14 <- tails[str_detect(names(tails), pattern = "chromosome 14,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_14 = 48347)



# 47070
chr_15 <- tails[str_detect(names(tails), pattern = "chromosome 15,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_15 = 47070)



# 47321
chr_16 <- tails[str_detect(names(tails), pattern = "chromosome 16,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_16 = 47314)



# 46985
chr_17 <- tails[str_detect(names(tails), pattern = "chromosome 17,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_17 = 46978)



# 46510
chr_18 <- tails[str_detect(names(tails), pattern = "chromosome 18,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_18 = 46510)


# 47065
chr_19 <- tails[str_detect(names(tails), pattern = "chromosome 19,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_19 = 47065)



# 47000
chr_20 <- tails[str_detect(names(tails), pattern = "chromosome 20,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_20 = 46846)



# 45434
chr_21 <- tails[str_detect(names(tails), pattern = "chromosome 21,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_21 = 45426)


# 47039
chr_22 <- tails[str_detect(names(tails), pattern = "chromosome 22,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_22 = 47025)



# 47282
chr_X <- tails[str_detect(names(tails), pattern = "chromosome X,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_X = 47056)



# 43611
chr_Y <- tails[str_detect(names(tails), pattern = "chromosome Y,")]

subtelo_tail_index <- c(subtelo_tail_index, chr_Y = 43611)


chrom_length <- tibble(chrom = names(genome), chrom_length = width(genome))
chrom_length$subtelo_index_end <- subtelo_tail_index

chrom_length <- chrom_length %>% 
  mutate(subtelo_tail_index_adjust = chrom_length + subtelo_index_end - 5e4)


# heads
subtelo_head_index <- integer()



# 2702
chr_01 <- heads[str_detect(names(heads), pattern = "chromosome 1,")]
subtelo_head_index <- c(subtelo_head_index, chr_01 = 2702)


# 3630
chr_02 <- heads[str_detect(names(heads), pattern = "chromosome 2,")]
subtelo_head_index <- c(subtelo_head_index, chr_02 = 3630)


# 2638
chr_03 <- heads[str_detect(names(heads), pattern = "chromosome 3,")]
subtelo_head_index <- c(subtelo_head_index, chr_03 = 2637)


# 3351
chr_04 <- heads[str_detect(names(heads), pattern = "chromosome 4,")]
subtelo_head_index <- c(subtelo_head_index, chr_04 = 3272) # 3272


# 2297
chr_05 <- heads[str_detect(names(heads), pattern = "chromosome 5,")]
subtelo_head_index <- c(subtelo_head_index, chr_05 = 2297)


# 2900
chr_06 <- heads[str_detect(names(heads), pattern = "chromosome 6,")]
subtelo_head_index <- c(subtelo_head_index, chr_06 = 2900)


# 3414
chr_07 <- heads[str_detect(names(heads), pattern = "chromosome 7,")]
subtelo_head_index <- c(subtelo_head_index, chr_07 = 3414)


# 2514
chr_08 <- heads[str_detect(names(heads), pattern = "chromosome 8,")]
subtelo_head_index <- c(subtelo_head_index, chr_08 = 2514)


# 3692
chr_09 <- heads[str_detect(names(heads), pattern = "chromosome 9,")]
subtelo_head_index <- c(subtelo_head_index, chr_09 = 3692)



# 2638
chr_10 <- heads[str_detect(names(heads), pattern = "chromosome 10,")]
subtelo_head_index <- c(subtelo_head_index, chr_10 = 2638)



# 2002
chr_11<- heads[str_detect(names(heads), pattern = "chromosome 11,")]
subtelo_head_index <- c(subtelo_head_index, chr_11 = 2002)



# 3103
chr_12 <- heads[str_detect(names(heads), pattern = "chromosome 12,")]
subtelo_head_index <- c(subtelo_head_index, chr_12 = 3103)



# 2543
chr_13 <- heads[str_detect(names(heads), pattern = "chromosome 13,")]
subtelo_head_index <- c(subtelo_head_index, chr_13 = 2543)



# 2119
chr_14 <- heads[str_detect(names(heads), pattern = "chromosome 14,")]
subtelo_head_index <- c(subtelo_head_index, chr_14 = 2075)




# 3346
chr_15 <- heads[str_detect(names(heads), pattern = "chromosome 15,")]
subtelo_head_index <- c(subtelo_head_index, chr_15 = 3267)



# 2330
chr_16<- heads[str_detect(names(heads), pattern = "chromosome 16,")]
subtelo_head_index <- c(subtelo_head_index, chr_16 = 2330)



# 2207
chr_17 <- heads[str_detect(names(heads), pattern = "chromosome 17,")]
subtelo_head_index <- c(subtelo_head_index, chr_17 = 2207)



# 2039
chr_18 <- heads[str_detect(names(heads), pattern = "chromosome 18,")]
subtelo_head_index <- c(subtelo_head_index, chr_18 = 2017)



# 2247
chr_19 <- heads[str_detect(names(heads), pattern = "chromosome 19,")]
subtelo_head_index <- c(subtelo_head_index, chr_19 = 2283)




# 2725
chr_20 <- heads[str_detect(names(heads), pattern = "chromosome 20,")]
subtelo_head_index <- c(subtelo_head_index, chr_20 = 2725)




# 2710
chr_21 <- heads[str_detect(names(heads), pattern = "chromosome 21,")]
subtelo_head_index <- c(subtelo_head_index, chr_21 = 2710)



# 4330
chr_22 <- heads[str_detect(names(heads), pattern = "chromosome 22,")]
subtelo_head_index <- c(subtelo_head_index, chr_22 = 4330)



# 1824
chr_X <- heads[str_detect(names(heads), pattern = "chromosome X,")]
subtelo_head_index <- c(subtelo_head_index, chr_X = 1824)



# 5649
chr_Y <- heads[str_detect(names(heads), pattern = "chromosome Y,")]
subtelo_head_index <- c(subtelo_head_index, chr_Y = 5660)









final_df_human <- chrom_length %>% select(chrom, chrom_length)
final_df_human$subtelo_Head_start_index <- subtelo_head_index
final_df_human$subtelo_Tail_end_index <- chrom_length$subtelo_tail_index_adjust



save_path <- "~/Human-ref/subtelo_indices-Human-T2T-GCF_009914755.1.csv"
write_csv(x = final_df_human, file = save_path ) # use csv for data 


fill_n(genome_path = genome_path, indices_path = save_path, 
       output_path = "~/Human-ref/GCF_009914755.1_T2T-CHM13v2.0_genomic-200k-subtelos-N.fasta.gz", 
       subtelo_length = 2e5, compress = TRUE)

############### End of Homo sapiens (human) ##############################################









################### Mus musculus strain C57BL_6J_T2T_v1  genoe ref $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

# This ref has no sex chromosomes (XY)

# link to the ref:
https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_964188535.1/
  
  
# ref path
path <-  "~/test-my-R-code/mouse-T2T-check/Genome-assembly-C57BL_6J_T2T_v1/ncbi_dataset/data/GCA_964188535.1/GCA_964188535.1_C57BL_6J_T2T_v1_genomic.fna" 
genome_t2t_mm <- readDNAStringSet(filepath = path ) 

# remove contig 
genome_t2t_mm <- genome_t2t_mm[1:19]  

# shorten the names
test <- stringr::str_replace(string = names(genome_t2t_mm), 
  pattern = "OZ\\d+.\\d Mus musculus strain C57BL_6J genome assembly, "
  , replacement = "")

test <- stringr::str_replace(string = test, pattern = " ", replacement = "")

names(genome_t2t_mm) <- test

ref <- create_chr_edges(genome = genome_t2t_mm, compress = FALSE, save_path = "~/ncbi_dataset/C57BL_6J_T2T_v1/GCA_964188535.1_C57BL_6J_T2T_v1_genomic-edges-50k.fna", edge_length = 5e4)
  



run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R", 
            input_path = "~/ncbi_dataset/C57BL_6J_T2T_v1/GCA_964188535.1_C57BL_6J_T2T_v1_genomic-edges-50k.fna" , 
            save_path = "~/test-my-R-code/mouse-T2T-check/Genome-assembly-C57BL_6J_T2T_v1/GCA_964188535.1_C57BL_6J_T2T_v1_genomic.fna-50k-nanotel-rigthEdge", pattern = "TTAGGG", min_density = 0.5, right_edge = TRUE)


ref <- readDNAStringSet(filepath = "~/ncbi_dataset/C57BL_6J_T2T_v1/GCA_964188535.1_C57BL_6J_T2T_v1_genomic-edges-50k.fna")
ref_50k_tail <- ref[str_detect(string = names(ref), pattern = "Tail")]

# the index where the last nuc is the subtelo befor the telomere starts

df_telo_tail <- read_csv(file = "~/test-my-R-code/mouse-T2T-check/Genome-assembly-C57BL_6J_T2T_v1/GCA_964188535.1_C57BL_6J_T2T_v1_genomic.fna-50k-nanotel-rigthEdge/summary.csv")
df_index <- df_telo_tail %>% 
  select(Serial, sequence_ID, Telomere_start_mismatch)

subtelo_tail_index <- integer()

chr1 <- ref_50k_tail[1] #  33563
subtelo_tail_index <-c(subtelo_tail_index, chr_1 = 33563)

chr2 <- ref_50k_tail[2] # 38780 chromosome:2_Tail                    
subtelo_tail_index <-c(subtelo_tail_index, chr_2 = 38780)

chr3 <- ref_20k_tail[3] # 40184
subtelo_tail_index <-c(subtelo_tail_index, chr_3 = 40159)

chr4 <- ref_50k_tail[4] # 26808
subtelo_tail_index <-c(subtelo_tail_index, chr_4 =  26807)

chr5 <- ref_50k_tail[5] #  40250
subtelo_tail_index <-c(subtelo_tail_index, chr_5 = 40250)


chr6 <- ref_50k_tail[6] # 37522
subtelo_tail_index <-c(subtelo_tail_index, chr_6 = 37522)

chr7 <- ref_50k_tail[7] # 39730
subtelo_tail_index <-c(subtelo_tail_index, chr_7 = 39730)


chr8 <- ref_50k_tail[8] # 41714
subtelo_tail_index <-c(subtelo_tail_index, chr_8 = 41714)



# tail 9 is problematic (large hole in the middle)
chr9 <- ref_50k_tail[9] # 28046
subtelo_tail_index <-c(subtelo_tail_index, chr_9 = 28045)



chr10 <- ref_50k_tail[10] #  29861
subtelo_tail_index <-c(subtelo_tail_index, chr_10 = 29861)

chr11 <- ref_50k_tail[11] # 37867
subtelo_tail_index <-c(subtelo_tail_index, chr_11 = 37867)

# in has TCGGGG  and TTCGGG paterns in the edge near subtelomere 
chr12 <- ref_50k_tail[12] # 31131
subtelo_tail_index <-c(subtelo_tail_index, chr_12 = 31043)

chr13 <- ref_50k_tail[13] # 30725
subtelo_tail_index <-c(subtelo_tail_index, chr_13 = 30717)


chr14 <- ref_50k_tail[14] # 33732
subtelo_tail_index <-c(subtelo_tail_index, chr_14 = 33732)

chr15 <- ref_50k_tail[15] # 35276
subtelo_tail_index <-c(subtelo_tail_index, chr_15 = 35276)

chr16 <- ref_50k_tail[16] # 37861
subtelo_tail_index <-c(subtelo_tail_index, chr_16 = 37860)


chr17 <- ref_50k_tail[17] # 34164
subtelo_tail_index <-c(subtelo_tail_index, chr_17 = 34164)

chr18 <- ref_50k_tail[18] # 34182
subtelo_tail_index <-c(subtelo_tail_index, chr_18 = 34182)


chr19 <- ref_50k_tail[19] # 39530
subtelo_tail_index <-c(subtelo_tail_index, chr_19 = 39530)

# adjust the indices to the real chr length



# create chrom and lengtt chrom table 
chrom_length <- tibble(chrom = names(genome_t2t_mm), chrom_length = width(genome_t2t_mm))

# add last index of subtelomere before tail telomeres
chrom_length$subtelo_index_end <- subtelo_tail_index

# adjust indices for tail telo_start/teloe_end <- telo_start/teloe_end + edge_length - edge_length
chrom_length <- chrom_length %>% 
  mutate(subtelo_tail_index_adjust = chrom_length + subtelo_index_end - 5e4)


chrom_length <- chrom_length %>% 
  mutate(chrom_short = names(subtelo_tail_index),.before = chrom_length)

# check  genome
subseq(genome_t2t_mm[1], width = 200, end = 206823553 ) # ok!
subseq(chr1, end = 33563, width = 200)


########### Now check Head

ref_50k_Head <- ref[str_detect(names(ref), "Head")]


df_head_tail <- read_csv(file = "~/test-my-R-code/mouse-T2T-check/Genome-assembly-C57BL_6J_T2T_v1/GCA_964188535.1_C57BL_6J_T2T_v1_genomic.fna-50k-nanotel/summary.csv")
df_index <- df_head_tail %>% 
  select(Serial, sequence_ID, Telomere_end_mismatch)

# Need to add sex chroms if avalibale 
# check X!=Y!=6

subtelo_head_index <- integer()


chr1 <- ref_50k_Head[1] # 16695

# check exact end 
subseq(chr1, end = 16695 , width = 200)

# This is the index for the start of the subtelomre
subtelo_head_index <-c(subtelo_head_index, chr_1 = 16695)


chr2 <- ref_50k_Head[2] #  9284
subtelo_head_index <-c(subtelo_head_index, chr_2 = 9284)

chr3 <- ref_50k_Head[3] #  5866
subtelo_head_index <-c(subtelo_head_index, chr_3 = 5866)

chr4 <- ref_50k_Head[4] #  16554
subtelo_head_index <-c(subtelo_head_index, chr_4 = 16554)

chr5 <- ref_50k_Head[5] #  26099
subtelo_head_index <-c(subtelo_head_index, chr_5 = 26099)

chr6 <- ref_50k_Head[6] # 21147 
subtelo_head_index <-c(subtelo_head_index, chr_6 = 21147)

chr7 <- ref_50k_Head[7] # 8397 
subtelo_head_index <-c(subtelo_head_index, chr_7 = 8397)

chr8 <- ref_50k_Head[8] # 5820 
subtelo_head_index <-c(subtelo_head_index, chr_8 = 5820)

chr9 <- ref_50k_Head[9] # 13983 
subtelo_head_index <-c(subtelo_head_index, chr_9 = 13983)

chr10 <- ref_50k_Head[10] #  8491
subtelo_head_index <-c(subtelo_head_index, chr_10 = 8491)

chr11 <- ref_50k_Head[11] #  10594
subtelo_head_index <-c(subtelo_head_index, chr_11 = 10594)

chr12 <- ref_50k_Head[12] # 8654 
subtelo_head_index <-c(subtelo_head_index, chr_12 = 8654)

chr13 <- ref_50k_Head[13] #  10857
subtelo_head_index <-c(subtelo_head_index, chr_13 = 10857)


chr14 <- ref_50k_Head[14] # 13376 
subtelo_head_index <-c(subtelo_head_index, chr_14 = 13376)

chr15 <- ref_50k_Head[15] # 17592 
subtelo_head_index <-c(subtelo_head_index, chr_15 = 17592)

chr16 <- ref_50k_Head[16] # 1693 
subtelo_head_index <-c(subtelo_head_index, chr_16 = 1693)

chr17 <- ref_50k_Head[17] #  8461
subtelo_head_index <-c(subtelo_head_index, chr_17 = 8461)

chr18 <- ref_50k_Head[18] #  19173
subtelo_head_index <-c(subtelo_head_index, chr_18 = 19173)

chr19 <- ref_50k_Head[19] #  9557
subtelo_head_index <-c(subtelo_head_index, chr_19 = 9557)

                
# GCA_964188535.1_C57BL_6J_T2T_v1_genomic.fna               
final_df_mm <- chrom_length %>% select(chrom, chrom_short, chrom_length)
final_df_mm$subtelo_Head_start_index <- subtelo_head_index
final_df_mm$subtelo_Tail_end_index <- chrom_length$subtelo_tail_index_adjust



save_path <- "~/test-my-R-code/mouse-T2T-check/Genome-assembly-C57BL_6J_T2T_v1/subtelo_indices-Mus-musculus-GCA_964188535.1_C57BL_6J_T2T_v1.csv"

write_csv(x = final_df_mm, file = save_path ) # use csv for data 

genome_path <- "~/test-my-R-code/mouse-T2T-check/Genome-assembly-C57BL_6J_T2T_v1/ncbi_dataset/data/GCA_964188535.1/GCA_964188535.1_C57BL_6J_T2T_v1_genomic.fna"

fill_n(genome_path = genome_path, indices_path = save_path, 
       output_path = "~/test-my-R-code/mouse-T2T-check/Genome-assembly-C57BL_6J_T2T_v1/GCA_964188535.1_C57BL_6J_T2T_v1_genomic-200k-subtelos-N-noXY.fasta.gz", 
       subtelo_length = 2e5, compress = TRUE)                
                

################## ref 3: Genome assembly T2T_mhaESC_v1.5 ################################################################
#' link: https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_056825265.1/
# According to my check chromosoe 6 Head in this reference is not similar to X from the other T2T ref (T2T_mhaESC_v1.5)                 
# So I assume XY is real so I can add it to this ref inorder to check if all can make a full subtelomeric ref.


ref3_path <- "~/test-my-R-code/mouse-T2T-check/Genome-assembly-T2T_mhaESC_v1.5/ncbi_dataset/data/GCA_056825265.1/GCA_056825265.1_T2T_mhaESC_v1.5_genomic.fna"
ref3_XY <- readDNAStringSet(filepath = ref3_path, skip = 19, nrec = 2 ) # take XY

new_rf <- create_chr_edges(genome = ref3_XY, edge_length = 1e5, save_path = "~/test-my-R-code/mouse-T2T-check/Genome-assembly-T2T_mhaESC_v1.5/ncbi_dataset/data/GCA_056825265.1/GCA_056825265.1_T2T_mhaESC_v1.5-100k-edges-XYOnly.fna")

ref_100k <- "~/test-my-R-code/mouse-T2T-check/Genome-assembly-T2T_mhaESC_v1.5/ncbi_dataset/data/GCA_056825265.1/GCA_056825265.1_T2T_mhaESC_v1.5-100k-edges-XYOnly.fna"

run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R", input_path = ref_100k , save_path = "~/ncbi_dataset/GCA_056825265.1_T2T_mhaESC_v1.5-100k-edges-XYOnly-CCCTAA", pattern = "CCCTAA", min_density = 0.5, right_edge = FALSE)
run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R", input_path = ref_100k, save_path = "~/ncbi_dataset/GCA_056825265.1_T2T_mhaESC_v1.5-100k-edges-XYOnly-TTAGGG", pattern = "TTAGGG", min_density = 0.5, right_edge = TRUE)



subtelo_tail_index <- integer()

chr_X <- subseq(x = ref3_XY[[1]], start = 170978164, width = 200)  #  94590 + 170983574 - 100000 = 170978164
chr_y <- subseq(x = ref3_XY[[2]], start = 95193283, width = 200)  #  83174 +  95210109 - 100000 =  95193283
  
# full length index
subtelo_tail_index <-c(subtelo_tail_index, chr_X = 170978164) 
subtelo_tail_index <-c(subtelo_tail_index, chr_Y = 95193283)

# add length 
chrom_length <- tibble(chrom = names(ref3_XY), chrom_length = width(ref3_XY))




subtelo_head_index <- integer()
# X 7047
# Y 42908
subseq(x = ref3_XY[[1]], start = 7047, width = 200)
subseq(x = ref3_XY[[2]], start = 42908, width = 200)

subtelo_head_index <-c(subtelo_head_index, chr_X = 7047)
subtelo_head_index <-c(subtelo_head_index, chr_Y = 42908)


chrom_length$subtelo_Head_start_index <- subtelo_head_index
chrom_length$subtelo_Tail_end_index <- subtelo_tail_index

chrom_length <- chrom_length %>% 
  mutate(chrom_short = names(subtelo_tail_index),.before = chrom_length)

file_path <- "~/test-my-R-code/mouse-T2T-check/Genome-assembly-T2T_mhaESC_v1.5/subtelo_indices-GCA_056825265.1_T2T_mhaESC_v1.5-XYOnly.csv"

chrom_length <- chrom_length[, c(1,2,3, 5,4)] # rearrange so the head before tail
write_csv(x = chrom_length, file = file_path)

path <- "~/test-my-R-code/mouse-T2T-check/Genome-assembly-T2T_mhaESC_v1.5/GCA_056825265.1_T2T_mhaESC_v1.5-XYOnly.fna"

Biostrings::writeXStringSet(x = ref3_XY, filepath = path)

output_path <- "~/test-my-R-code/mouse-T2T-check/Genome-assembly-T2T_mhaESC_v1.5/GCA_056825265.1_T2T_mhaESC_v1.5-XYOnly-200k-subtelos-N.fna"


ref_check <-  fill_n(genome_path = path, indices_path = file_path , output_path = output_path , subtelo_length = 2e5, compress = TRUE)


# now merge it with the second ref (Mus musculus strain C57BL_6J_T2T_v1)

ref_C57BL_6J_T2T_v1 <- readDNAStringSet(filepath = "~/test-my-R-code/mouse-T2T-check/Genome-assembly-C57BL_6J_T2T_v1/T2T-Mus-musculus-GCA_964188535.1_C57BL_6J_T2T_v1/GCA_964188535.1_C57BL_6J_T2T_v1_genomic-200k-subtelos-N-noXY.fasta.gz")

ref_C57BL_6J_T2T_v1 <- append(ref_C57BL_6J_T2T_v1, ref_check)

# merge the df
df_merged <- read_csv(file = "~/test-my-R-code/mouse-T2T-check/Genome-assembly-C57BL_6J_T2T_v1/T2T-Mus-musculus-GCA_964188535.1_C57BL_6J_T2T_v1/subtelo_indices-Mus-musculus-GCA_964188535.1_C57BL_6J_T2T_v1.csv")

df_merged <- bind_rows(df_merged, chrom_length)

# replace white space with '-' for minimpa names
names(ref_C57BL_6J_T2T_v1) <- stringr::str_replace_all(string = names(ref_C57BL_6J_T2T_v1), pattern = " ", replacement = '-')
df_merged$chrom <- stringr::str_replace_all(string = df_merged$chrom, pattern = " ", replacement = '-')
all.equal(names(ref_C57BL_6J_T2T_v1),df_merged$chrom)


merged_csv <- "~/test-my-R-code/mouse-T2T-check/merged-C57BL_6J_T2T_v1-With-T2T_mhaESC_v1.5-XY/subtelo-indices-merged-C57BL_6J_T2T_v1-With-T2T_mhaESC_v1.5-XY-200k-subtelos-N.csv"
merged_ref <- "~/test-my-R-code/mouse-T2T-check/merged-C57BL_6J_T2T_v1-With-T2T_mhaESC_v1.5-XY/merged-C57BL_6J_T2T_v1-With-T2T_mhaESC_v1.5-XY-200k-subtelos-N.fasta.gz"

write_csv(x = df_merged, file = merged_csv)
writeXStringSet(x = ref_C57BL_6J_T2T_v1, filepath = merged_ref, compress = TRUE)


# update alignment_genome column 
df_merged <- readr::read_csv(file = merged_csv)
df_merged$alignment_genome <- df_merged$chrom_short


readr::write_csv(x = df_merged, file = merged_csv)

# undo replac_all
df_merged$chrom <- stringr::str_replace_all(string = df_merged$chrom, pattern = '-', replacement = " ")


# update the names of the genome ref to chrom_short
ref_merged <- readDNAStringSet(filepath = merged_ref)


# replace the short names
names(ref_merged) <- df_merged$alignment_genome
# 
writeXStringSet(x = ref_merged, filepath = merged_ref, compress = TRUE)


#################################################################################################



###################### Zebra fish 13 AB ######################################################

# The link to the ref:
# https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_052040795.2/

#' An error in the original submission of this assembly resulted in the 
#' inclusion of chr4 and chr19 from the GRCz12tu (GCA_049306965.1) Tuebingen 
#' strain instead of the intended sequences from the AB strain. 
#' This has been corrected in the GRCz13ab assembly.

# Zebra Fish genome: GCA_052040795.2
zebra_path <- "~/ZebraFish-T2T/ncbi_dataset/data/GCA_052040795.2/GCA_052040795.2_GRCz13ab_genomic.fna"

# I need to check only chr 4 and 19, all the others are already in the prev ref. 
zebra_genome <- readDNAStringSet(filepath = zebra_path)

genome_names <- names(zebra_genome)

zebra_genome <- zebra_genome[c(4, 19)]
gc()
  
zebra_chr_edges_50k <- create_chr_edges(genome = zebra_genome, edge_length = 5e4,save_path = "ZebraFish-T2T/ncbi_dataset/data/GCA_052040795.2/GCA_052040795.2_chr4-chr19_genomic-50kEdges.fna.gz", compress = TRUE)

zebra_fish_tvr_list_Head <- c("CCCCTAGTTGACTA", "CCCCTAGTTCGCTCTA", "CCCCTAGAACTCTTA", "CCCCTAGTTGACTCT")
zebra_fish_tvr_list_Tail <-c("TAGTCAACTAGGGG", "TAGAGCGAACTAGGG", "TAAGAGTCCTAGGGG")
tvr_string_Head <- str_c("\"", stringr::str_flatten(zebra_fish_tvr_list_Head, " ") , "\"")
tvr_string_Tail <- str_c("\"", stringr::str_flatten(zebra_fish_tvr_list_Tail, " ") , "\"")

#Heads
run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R", 
            input_path = "ZebraFish-T2T/ncbi_dataset/data/GCA_052040795.2/GCA_052040795.2_chr4-chr19_genomic-50kEdges.fna.gz", save_path = "ZebraFish-T2T/ncbi_dataset/data/GCA_052040795.2/GCA_052040795.2_chr4-chr19_genomic-50kEdges-nanotel-CCCTAA", pattern = "CCCTAA"  , min_density = 0.6, right_edge = FALSE, tvr_patterns = tvr_string_Head )
# 1 is 4 , 2 is 19
#  Tvr pattern" CCCCTAGAACTCTTA , 17756
head_4_index <- 17765 

# no TVR, 3001
head_19_index <- 3001


#Tails
run_nanotel(nanotel_path = "Telomere-Analyzer/NanoTel.R",
            input_path = "ZebraFish-T2T/ncbi_dataset/data/GCA_052040795.2/GCA_052040795.2_chr4-chr19_genomic-50kEdges.fna.gz", save_path = "ZebraFish-T2T/ncbi_dataset/data/GCA_052040795.2/GCA_052040795.2_chr4-chr19_genomic-50kEdges-nanotel-TTAGGG", pattern = "TTAGGG", min_density = 0.6, right_edge = TRUE , tvr_patterns = tvr_string_Tail)


# 1 is 4, 3 is 19 
# chr4 tail 33320 + adjust  tvr: TAGTCAACTAGGGG
# adjust = 81415375 + 33320 - 50000 = 81398695
tail_4_index <- 81398695



# 19 tail , 34387 tvr TAGTCAACTAGGGG
# 34387 + 51337948 - 50000 = 51322335
tail_19_index <- 51322334

new_path <- "~/ZebraFish-T2T/ncbi_dataset/data/GCA_052040795.2/GCA_052040795.2_GRCz13ab_genomic-4-19-Only.fa.gz"
writeXStringSet(x = zebra_genome, filepath = new_path, compress = TRUE)

df_4_19 <- tibble(chrom = names(zebra_genome), chrom_length = width(zebra_genome),
                  subtelo_Head_start_index = c(head_4_index, head_19_index), 
                  subtelo_Tail_end_index = c(tail_4_index, tail_19_index))

write_csv(x = df_4_19, file = "~/ZebraFish-T2T/ncbi_dataset/data/GCA_052040795.2/subtelo-indicesGCA_052040795.2_GRCz13ab_genomic-4-19-Only.csv")
fill_n_4_19 <- fill_n(genome_path = new_path , indices_path = "~/ZebraFish-T2T/ncbi_dataset/data/GCA_052040795.2/subtelo-indicesGCA_052040795.2_GRCz13ab_genomic-4-19-Only.csv", output_path = "~/ZebraFish-T2T/ncbi_dataset/data/GCA_052040795.2/GCA_052040795.2_GRCz13ab_genomic-4-19-Only-fillN-200k.fa.gz", subtelo_length = 200000, compress = TRUE)





  
# check refs are erally equal besides 19 and 4
# Zebra Fish genome: GCA_052040795.1
old_zebra_path <- "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/ncbi_dataset/ncbi_dataset/data/GCA_052040795.1/GCA_052040795.1_GRCz12ab_genomic.fna.gz"

# che i to i (besides 4 and 19) 1:3, 4 , 5:
for(i in 0:2) { # all equal 1, 2,3 
  print(i)
  
  curr_old <- readDNAStringSet(filepath = old_zebra_path, skip = i, nrec = 1)
  curr_new <- readDNAStringSet(filepath = zebra_path, skip = i, nrec = 1)
  print(names(curr_old))
  print(names(curr_new))
  assert(toString(curr_new) == toString(curr_old))
} 

for(i in 4:17) { # all equal 5:18
  print(i)
  
  curr_old <- readDNAStringSet(filepath = old_zebra_path, skip = i, nrec = 1)
  curr_new <- readDNAStringSet(filepath = zebra_path, skip = i, nrec = 1)
  print(names(curr_old))
  print(names(curr_new))
  assert(toString(curr_new) == toString(curr_old))
} 

for(i in 19:24) { # all equal 20, 21, 22, 23 ,24 , 25
  print(i)
  
  curr_old <- readDNAStringSet(filepath = old_zebra_path, skip = i, nrec = 1)
  curr_new <- readDNAStringSet(filepath = zebra_path, skip = i, nrec = 1)
  print(names(curr_old))
  print(names(curr_new))
  assert(toString(curr_new) == toString(curr_old))
} 


# use old df with the new for new N-ref + alignment_genome names 
old_df_path <- "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/ZebraFish-/subtelo_indices-GCA_052040795.1-Danio-rerio-strain-M-AB-ecotype-USA.csv"
df_old <- read_csv(file = old_df_path)


df_new <- add_row(df_old[1:3,], df_4_19[1, ])

df_new_2 <- add_row(df_new, df_old[5:18,])

df_new_3 <- add_row(df_new_2, df_4_19[2, ])
df_final <- add_row(df_new_3, df_old[20:25, ])

# todo:
#' 1. merge N 19 _ 4 with old (4 and 19 ) excluded
#' 2. add  alignment_genome column and rename te ref names accordinglly.
#' 

old_N_path <- "~/ZebraFish-20260705T071318Z-3-001/ZebraFish/ZebraFish-/GCA_052040795.1_GRCz12ab_genomic-200k-subtelos-N.fasta.gz"

genome_old_1_3 <- readDNAStringSet(filepath = old_N_path, nrec = 3)

genome_old_1_3 <- append(genome_old_1_3, fill_n_4_19[1])

genome_5__18 <- readDNAStringSet(filepath = old_N_path, nrec = 14, skip = 4) 

genome_5__18 <- append(genome_old_1_3, genome_5__18) 

genome_5__18 <- append(genome_5__18,  fill_n_4_19[2])

genome_last <- readDNAStringSet(filepath = old_N_path, skip = 19) 

genome_last <- append(genome_5__18, genome_last)


names(genome_last) <- str_replace_all(string = names(genome_last), pattern = ',', replacement = "")
names(genome_last) <- str_replace_all(string = names(genome_last), pattern = ' ', replacement = "-")

df_final$alignment_genome <- names(genome_last)

writeXStringSet(x = genome_last, filepath = "~/ZebraFish-T2T/ncbi_dataset/data/Zebra-Fish/GCA_052040795.2_GRCz12ab_genomic-200k-subtelos-N.fasta.gz", compress = TRUE)
write_csv(x = df_final, file = "~/ZebraFish-T2T/ncbi_dataset/data/Zebra-Fish/subtelo-indices-200k.csv")

# update README accordingly , TVR and errors ...



# update the plots  and TVR's












###########################3 End of Zebra Fish 13ab ########################################








