#!/usr/bin/env Rscript
# Build the figures in assets/ from the real toy dataset.
#
#   Rscript scripts/make_figures.R
#
# Every number plotted here is read from dummy_data/ at render time by calling
# samtools and bcftools, so the figures cannot drift from the repository. Run
# from the repository root with the conda environment active.

suppressPackageStartupMessages({
  library(ggplot2); library(dplyr); library(patchwork); library(ragg)
})

dir.create("assets", showWarnings = FALSE)

# ---------------------------------------------------------------- palette ---
# Okabe-Ito, the colourblind-safe qualitative palette. Same set used by the
# ggplot2-20-journal-cases gallery, so the two repositories match.
SURFACE   <- "white"
INK       <- "black"
INK_2     <- "grey25"
INK_3     <- "grey50"
BLUE      <- "#0072B2"   # Okabe-Ito blue
ORANGE    <- "#D55E00"   # vermillion
AQUA      <- "#009E73"   # bluish green
YELLOW    <- "#E69F00"   # orange
# Figures name commands and report counts; they do not colour-code a verdict.
# Interpretation belongs in the caption, not in the ink.
MONO      <- "Menlo"

# theme_bw baseline mirroring R/theme_case.R in the ggplot2 gallery: grey92
# grid, black panel border, black axis text and ticks.
theme_fig <- function(base_size = 11) {
  theme_bw(base_size = base_size) +
    theme(
      plot.background   = element_rect(fill = SURFACE, colour = NA),
      panel.background  = element_rect(fill = SURFACE, colour = NA),
      panel.grid.minor  = element_blank(),
      panel.grid.major  = element_line(colour = "grey92", linewidth = 0.3),
      panel.border      = element_rect(colour = "black", linewidth = 0.5),
      axis.text         = element_text(colour = "black", size = base_size - 2),
      axis.ticks        = element_line(colour = "black", linewidth = 0.4),
      axis.title        = element_text(colour = "black", size = base_size - 1),
      plot.title        = element_text(colour = INK, face = "bold", hjust = 0,
                                       size = base_size + 3),
      plot.subtitle     = element_text(colour = INK_2, size = base_size - 1,
                                       lineheight = 1.2),
      plot.caption      = element_text(colour = INK_3, size = base_size - 3,
                                       hjust = 0),
      legend.key        = element_blank(),
      legend.text       = element_text(colour = "black", size = base_size - 2),
      legend.title      = element_blank(),
      strip.background  = element_rect(fill = "grey95", colour = "black",
                                       linewidth = 0.4),
      strip.text        = element_text(colour = "black", face = "bold",
                                       size = base_size - 1),
      plot.margin       = margin(16, 20, 12, 16)
    )
}

sh <- function(cmd) system(cmd, intern = TRUE)

# ------------------------------------------------------------------- data ---
message("reading dummy_data/ ...")

depth <- read.table(pipe("samtools depth -a dummy_data/aligned.bam"),
                    col.names = c("chrom", "pos", "depth"))
genes <- read.table("dummy_data/genes.bed",
                    col.names = c("chrom", "start", "end", "name",
                                  "score", "strand"))
vars  <- read.table(
  pipe("bcftools query -f '%CHROM\\t%POS\\n' dummy_data/variants.vcf.gz"),
  col.names = c("chrom", "pos"))

n_total  <- as.integer(sh("samtools view -c dummy_data/aligned.bam"))
n_F4     <- as.integer(sh("samtools view -c -F 4 dummy_data/aligned.bam"))
n_F904   <- as.integer(sh("samtools view -c -F 0x904 dummy_data/aligned.bam"))
n_unmap  <- as.integer(sh("samtools view -c -f 4 dummy_data/aligned.bam"))
n_sec    <- as.integer(sh("samtools view -c -f 256 dummy_data/aligned.bam"))
n_supp   <- as.integer(sh("samtools view -c -f 2048 dummy_data/aligned.bam"))

mean_all     <- mean(depth$depth)                       # samtools depth -a
mean_covered <- mean(depth$depth[depth$depth > 0])      # samtools depth
inflation    <- round(100 * (mean_covered / mean_all - 1))

message(sprintf("  %d records | -F 4 = %d | -F 0x904 = %d",
                n_total, n_F4, n_F904))
message(sprintf("  mean depth: all %.2f | covered-only %.2f (+%d%%)",
                mean_all, mean_covered, inflation))

# ============================================================== figure 1 ====
# The depth trap: the same BAM, two means, one of them wrong.

bin <- 20
cov <- depth %>%
  mutate(bin = (pos %/% bin) * bin) %>%
  group_by(chrom, bin) %>%
  summarise(depth = mean(depth), .groups = "drop")

cov1 <- filter(cov, chrom == "chr1")

# the deliberately uncovered windows, found rather than hard-coded
zero_runs <- depth %>%
  filter(chrom == "chr1") %>%
  mutate(zero = depth == 0, grp = cumsum(zero != lag(zero, default = FALSE))) %>%
  filter(zero) %>%
  group_by(grp) %>%
  summarise(start = min(pos), end = max(pos), .groups = "drop") %>%
  filter(end - start > 300)

# Annotate the widest *interior* gap - one with coverage on both sides. The
# run at the start of the contig is also zero-coverage but makes a confusing
# callout, since nothing there looks like a gap.
gap <- zero_runs %>%
  filter(start > min(depth$pos[depth$chrom == "chr1" & depth$depth > 0])) %>%
  slice_max(end - start, n = 1)
gap_x <- min(max(mean(c(gap$start, gap$end)), 1200), 8800)

rule_lab <- tibble(
  x = 9950,
  y = c(mean_covered, mean_all),
  vjust = c(-0.4, 1.4),
  colour = c(INK, INK),
  label = c(sprintf("samtools depth      %.2fx", mean_covered),
            sprintf("samtools depth -a   %.2fx", mean_all)))

fig1 <- ggplot(cov1, aes(bin, depth)) +
  annotate("rect", xmin = zero_runs$start, xmax = zero_runs$end,
           ymin = -Inf, ymax = Inf, fill = "grey93", colour = NA) +
  geom_area(fill = BLUE, alpha = 0.30) +
  geom_line(colour = BLUE, linewidth = 0.5) +
  geom_hline(yintercept = mean_covered, colour = INK,
             linewidth = 0.5, linetype = "22") +
  geom_hline(yintercept = mean_all, colour = INK, linewidth = 0.5) +
  geom_label(data = rule_lab,
             aes(x, y, label = label, vjust = vjust, colour = I(colour)),
             hjust = 1, fill = SURFACE, label.size = 0,
             label.padding = unit(0.16, "lines"),
             family = MONO, size = 2.9, inherit.aes = FALSE) +
  annotate("text", x = gap_x, y = max(cov1$depth) * 0.94,
           label = "no reads here\nomitted from the mean",
           colour = INK_2, size = 2.7, lineheight = 0.95) +
  scale_x_continuous(labels = function(x) paste0(x / 1000, " kb"),
                     expand = expansion(mult = c(0.01, 0.01))) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.12))) +
  labs(x = "position on chr1", y = "read depth") +
  theme_fig()

# ============================================================== figure 2 ====
# Flag anatomy: what -F 4 keeps that it should not.

classes <- tibble(
  class = factor(c("primary mapped", "secondary (0x100)",
                   "supplementary (0x800)", "unmapped (0x4)"),
                 levels = c("primary mapped", "secondary (0x100)",
                            "supplementary (0x800)", "unmapped (0x4)")),
  n = c(n_F904, n_sec, n_supp, n_unmap)) %>%
  mutate(end = cumsum(n), start = end - n, mid = (start + end) / 2)

small <- classes %>%
  filter(n <= 20) %>%
  mutate(lab_y = 0.56 - (row_number() - 1) * 0.17)

brk <- tibble(
  y     = c(1.30, 1.62),
  xend  = c(n_F904, n_F4),
  label = c(sprintf("-F 0x904   n = %d   primary mapped only", n_F904),
            sprintf("-F 4       n = %d   includes %d non-primary records",
                    n_F4, n_F4 - n_F904)),
  colour = c(INK, INK))

fig2 <- ggplot() +
  geom_rect(data = classes,
            aes(xmin = start, xmax = end - 2, ymin = 0.72, ymax = 1.12,
                fill = class)) +
  geom_text(data = filter(classes, n > 20),
            aes(x = mid, y = 0.92, label = n),
            colour = "white", family = MONO, size = 3.2) +
  # leader lines for the segments too thin to label inside, staggered so the
  # labels of adjacent thin segments do not collide
  geom_segment(data = small,
               aes(x = mid, xend = mid, y = 0.70, yend = lab_y + 0.05),
               colour = INK_3, linewidth = 0.3) +
  geom_text(data = small, aes(x = mid, y = lab_y, label = paste0(n, "  ")),
            colour = INK_2, family = MONO, size = 3.1, hjust = 1) +
  geom_segment(data = brk, aes(x = 0, xend = xend, y = y, yend = y,
                               colour = I(colour)), linewidth = 0.5) +
  geom_segment(data = brk, aes(x = xend, xend = xend, y = y - 0.055,
                               yend = y + 0.055, colour = I(colour)),
               linewidth = 0.5) +
  geom_text(data = brk, aes(x = 6, y = y + 0.115, label = label,
                            colour = I(colour)),
            hjust = 0, family = MONO, size = 3.0) +
  scale_fill_manual(values = c(BLUE, AQUA, YELLOW, ORANGE)) +
  scale_x_continuous(expand = expansion(mult = c(0.005, 0.02))) +
  coord_cartesian(ylim = c(0.14, 1.80)) +
  guides(fill = guide_legend(nrow = 1)) +
  labs(x = "alignment records", y = NULL) +
  theme_fig() +
  theme(axis.text.y = element_blank(),
        axis.ticks.y = element_blank(),
        panel.grid.major.y = element_blank(),
        legend.position = "bottom")

# ============================================================== figure 3 ====
# The toy dataset, drawn: how the files line up on the toy genome.

fai <- read.table("dummy_data/ref.fa.fai")[, 1:2]
names(fai) <- c("chrom", "len")

# Put overlapping genes on separate rows so the overlap is visible - it is
# what gives `bedtools merge` something to do.
stack_rows <- function(df) {
  df <- arrange(df, start)
  row <- integer(nrow(df))
  for (i in seq_len(nrow(df))) {
    row[i] <- if (i > 1 && df$start[i] < df$end[i - 1]) 3 - row[i - 1] else 1
  }
  mutate(df, row = row)
}

track_panel <- function(contig) {
  cv <- filter(cov, chrom == contig)
  gn <- stack_rows(filter(genes, chrom == contig))
  vr <- filter(vars, chrom == contig)
  ymax <- max(cv$depth)
  clen <- fai$len[fai$chrom == contig]
  # row 1 sits just under the variant ticks, row 2 below it
  gn <- mutate(gn,
               ytop = -ymax * (0.26 + (row - 1) * 0.155),
               ybot = -ymax * (0.38 + (row - 1) * 0.155))

  ggplot() +
    geom_area(data = cv, aes(bin, depth), fill = BLUE, alpha = 0.30) +
    geom_line(data = cv, aes(bin, depth), colour = BLUE, linewidth = 0.4) +
    geom_point(data = vr, aes(pos, -ymax * 0.15), colour = ORANGE,
               shape = 124, size = 2.4) +
    geom_rect(data = gn,
              aes(xmin = start, xmax = end, ymin = ybot, ymax = ytop),
              fill = AQUA, colour = SURFACE, linewidth = 0.4) +
    geom_text(data = gn, aes(x = (start + end) / 2, y = (ytop + ybot) / 2,
                             label = name),
              colour = "white", size = 2.4, family = MONO) +
    annotate("text", x = 0, y = -ymax * 0.15, label = "variants  ", hjust = 1,
             colour = ORANGE, size = 2.7, family = MONO) +
    annotate("text", x = 0, y = -ymax * 0.40, label = "genes  ", hjust = 1,
             colour = AQUA, size = 2.7, family = MONO) +
    annotate("text", x = 0, y = ymax * 0.55, label = "coverage  ", hjust = 1,
             colour = BLUE, size = 2.7, family = MONO) +
    scale_x_continuous(labels = function(x) paste0(x / 1000, " kb"),
                       limits = c(0, clen),
                       expand = expansion(mult = c(0.13, 0.02))) +
    coord_cartesian(ylim = c(-ymax * 0.62, ymax * 1.05), clip = "off") +
    labs(x = sprintf("%s (%s bp)", contig, format(clen, big.mark = ",")),
         y = NULL) +
    theme_fig() +
    theme(axis.text.y = element_blank(),
          axis.ticks.y = element_blank(),
          panel.grid.major = element_blank())
}

fig3 <- (track_panel("chr1") / track_panel("chr2")) +
  plot_layout(heights = c(1, 1)) +
  plot_annotation(tag_levels = "A") &
  theme(plot.tag = element_text(face = "bold", size = 11))

# ============================================================== figure 4 ====
# What the recipes actually return. Every panel is the parsed stdout of one
# cookbook command, run against dummy_data/ at render time.

cap <- function(txt) {
  # the command that produced the panel, set small and monospaced
  labs(caption = txt)
}
cap_theme <- theme(plot.caption = element_text(family = MONO, size = 6.5,
                                               colour = INK_3, hjust = 0))

## A - read depth distribution:  samtools depth -a
pA <- ggplot(filter(depth, chrom == "chr1"), aes(depth)) +
  geom_histogram(binwidth = 1, fill = BLUE, colour = "white",
                 linewidth = 0.2) +
  geom_vline(xintercept = mean_all, colour = INK, linewidth = 0.45,
             linetype = "22") +
  annotate("text", x = mean_all, y = Inf, label = sprintf(" mean %.2fx", mean_all),
           hjust = 0, vjust = 1.6, size = 2.5, colour = INK,
           family = MONO) +
  labs(x = "read depth", y = "positions on chr1") +
  cap("samtools depth -a aligned.bam") +
  theme_fig(10) + cap_theme

## B - insert size distribution:  samtools stats
ins <- read.table(pipe(
  "samtools stats dummy_data/aligned.bam | grep '^IS' | cut -f2,3"),
  col.names = c("insert", "n")) %>% filter(n > 0)
pB <- ggplot(ins, aes(insert, n)) +
  geom_col(fill = AQUA, width = 1) +
  labs(x = "insert size (bp)", y = "read pairs") +
  cap("samtools stats aligned.bam | grep ^IS") +
  theme_fig(10) + cap_theme

## C - variants per gene:  bedtools intersect -c
vpg <- read.table(pipe(paste(
  "bedtools intersect -c -a dummy_data/genes.bed",
  "-b dummy_data/variants.vcf.gz")),
  col.names = c("chrom", "start", "end", "gene", "score", "strand", "n"))
pC <- ggplot(vpg, aes(reorder(gene, -n), n)) +
  geom_col(fill = BLUE, width = 0.7) +
  geom_text(aes(label = n), vjust = -0.4, size = 2.6, colour = INK_2) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.18))) +
  labs(x = NULL, y = "variants") +
  cap("bedtools intersect -c -a genes.bed -b variants.vcf.gz") +
  theme_fig(10) + cap_theme

## D - QUAL by FILTER:  bcftools query
qual <- read.table(pipe(paste(
  "bcftools query -f '%QUAL\\t%FILTER\\n' dummy_data/variants.vcf.gz")),
  col.names = c("qual", "filter"))
pD <- ggplot(qual, aes(filter, qual, fill = filter)) +
  geom_boxplot(width = 0.5, outlier.size = 0.8, linewidth = 0.35) +
  geom_hline(yintercept = 30, colour = INK_3, linetype = "22",
             linewidth = 0.4) +
  annotate("text", x = 0.6, y = 30, label = "QUAL 30", vjust = -0.6,
           hjust = 0, size = 2.4, colour = INK_3, family = MONO) +
  scale_fill_manual(values = c(LowQual = "grey75", PASS = BLUE)) +
  labs(x = NULL, y = "QUAL") +
  cap("bcftools query -f '%QUAL\\t%FILTER\\n' variants.vcf.gz") +
  theme_fig(10) + cap_theme + theme(legend.position = "none")

## E - GC content in 200 bp windows:  bedtools makewindows | bedtools nuc
gc <- read.table(pipe(paste(
  "bedtools makewindows -g dummy_data/genome.txt -w 200 |",
  "bedtools nuc -fi dummy_data/ref.fa -bed - | grep -v '^#' | cut -f1,2,5")),
  col.names = c("chrom", "start", "gc"))
pE <- ggplot(gc, aes(start / 1000, gc * 100, colour = chrom)) +
  geom_line(linewidth = 0.4) +
  scale_colour_manual(values = c(chr1 = BLUE, chr2 = ORANGE)) +
  labs(x = "position (kb)", y = "GC (%)") +
  cap("bedtools makewindows -w 200 | bedtools nuc -fi ref.fa -bed -") +
  theme_fig(10) + cap_theme +
  theme(legend.position = c(0.99, 0.99), legend.justification = c(1, 1),
        legend.background = element_rect(fill = "white", colour = NA),
        legend.key.size = unit(0.7, "lines"))

## F - GTF feature counts:  awk
feat <- read.table(pipe(paste(
  "awk -F'\\t' '!/^#/ {print $3}' dummy_data/annotation.gtf |",
  "sort | uniq -c | awk '{print $2\"\\t\"$1}'")),
  col.names = c("feature", "n"))
pF <- ggplot(feat, aes(reorder(feature, n), n)) +
  geom_col(fill = YELLOW, width = 0.65) +
  geom_text(aes(label = n), hjust = -0.25, size = 2.6, colour = INK_2) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.22))) +
  coord_flip() +
  labs(x = NULL, y = "lines in annotation.gtf") +
  cap("awk -F'\\t' '!/^#/ {print $3}' annotation.gtf | sort | uniq -c") +
  theme_fig(10) + cap_theme

fig4 <- (pA | pB) / (pC | pD) / (pE | pF) +
  plot_annotation(tag_levels = "A") &
  theme(plot.tag = element_text(face = "bold", size = 11))

# ------------------------------------------------------------------ write ---
save_fig <- function(plot, file, w, h) {
  agg_png(file.path("assets", file), width = w, height = h, units = "in",
          res = 300, background = "white")
  print(plot)
  invisible(dev.off())
  message("  assets/", file)
}

message("writing figures ...")
save_fig(fig1, "fig-depth-trap.png",   9.0, 4.8)
save_fig(fig2, "fig-flag-anatomy.png", 9.0, 4.6)
save_fig(fig3, "fig-toy-dataset.png",  9.0, 6.0)
save_fig(fig4, "fig-recipe-outputs.png", 9.0, 8.6)
message("done.")
