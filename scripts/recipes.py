#!/usr/bin/env python3
"""Every recipe in the cookbook, in one place.

This file is the single source of truth. `test_cookbook.py` runs each `cmd`
against dummy_data/ and checks `expect`; `render_readme.py` rebuilds the
README tables from the same list. Adding a recipe here adds it to both.

Fields
------
id      stable short identifier, used in the test report
cat     category key, see CATEGORIES below
task    what the recipe does, in plain language
cmd     the one-liner, exactly as it appears in the README
trap    optional: the mistake this recipe exists to avoid
expect  optional check on stdout:
            None        -> exit 0 and non-empty output
            "=VALUE"    -> stripped stdout equals VALUE
            "~REGEX"    -> stdout matches REGEX (search, multiline)
            "ok"        -> exit 0, output may be empty
tools   tools the recipe needs, so the runner can skip cleanly
"""

CATEGORIES = [
    ("fastx",  "FASTQ & FASTA"),
    ("vcf",    "VCF & BCF"),
    ("bam",    "BAM & SAM"),
    ("bed",    "BED & region math"),
    ("gtf",    "GTF & GFF"),
    ("perf",   "Compression, search & pipeline hygiene"),
]

R = dict

RECIPES = [

    # ---------------------------------------------------------------- fastx
    R(id="F01", cat="fastx", tools=["seqtk"],
      task="Count reads and bases in a gzipped FASTQ in one pass",
      cmd="seqtk size dummy_data/reads_R1.fq.gz",
      trap="`wc -l | awk '{print $1/4}'` decompresses the whole file just to "
           "count lines, and tells you nothing about bases.",
      expect="~^171"),

    R(id="F02", cat="fastx", tools=[],
      task="Count reads without seqtk",
      cmd="gzip -dc dummy_data/reads_R1.fq.gz | awk 'END {print NR/4}'",
      trap="Piping into `wc -l` and dividing spawns an extra process and "
           "miscounts a file with no trailing newline.",
      expect="=171"),

    R(id="F03", cat="fastx", tools=["seqtk"],
      task="Subsample read pairs while keeping mates in sync",
      cmd="seqtk sample -s100 dummy_data/reads_R1.fq.gz 50 > sub_R1.fq && "
          "seqtk sample -s100 dummy_data/reads_R2.fq.gz 50 > sub_R2.fq && "
          "echo 'pairs kept in sync'",
      trap="Using a different -s seed for R1 and R2 silently destroys "
           "pairing. The seed must be identical for both mates.",
      expect="~sync"),

    R(id="F04", cat="fastx", tools=["seqtk"],
      task="Convert FASTQ to FASTA",
      cmd="seqtk seq -a dummy_data/reads_R1.fq.gz | head -2",
      expect="~^>READ"),

    R(id="F05", cat="fastx", tools=["seqtk"],
      task="GC content of every sequence in a FASTA",
      cmd="seqtk comp dummy_data/ref.fa | "
          "awk '{printf \"%s\\t%.4f\\n\", $1, ($4+$5)/$2}'",
      trap="A hand-rolled awk GC counter mishandles wrapped (multi-line) "
           "records, keeps the '>' in the name, and divides by zero on "
           "blank lines. seqtk already counts every base.",
      expect="~^chr1"),

    R(id="F06", cat="fastx", tools=["seqtk"],
      task="Total assembly size and sequence count",
      cmd="seqtk size dummy_data/ref.fa",
      expect="~15000"),

    R(id="F07", cat="fastx", tools=["seqtk"],
      task="Pull out sequences named in a list",
      cmd="printf 'chr2\\n' > ids.txt && "
          "seqtk subseq dummy_data/ref.fa ids.txt | head -1",
      expect="~^>chr2"),

    R(id="F08", cat="fastx", tools=["samtools"],
      task="Extract a genomic region from a FASTA",
      cmd="samtools faidx dummy_data/ref.fa chr1:1001-1100",
      trap="samtools faidx coordinates are 1-based inclusive; BED is 0-based "
           "half-open. Feeding a BED start straight in shifts you one base.",
      expect="~^>chr1:1001-1100"),

    R(id="F09", cat="fastx", tools=["seqtk"],
      task="Reverse complement every sequence",
      cmd="seqtk seq -r dummy_data/ref.fa | head -1",
      expect="~^>chr1"),

    R(id="F10", cat="fastx", tools=["seqtk"],
      task="Unwrap a FASTA to one line per record",
      cmd="seqtk seq -l 0 dummy_data/ref.fa | awk 'NR==2 {print length}'",
      expect="=10000"),

    R(id="F11", cat="fastx", tools=["seqtk"],
      task="Keep only sequences above a length threshold",
      cmd="seqtk seq -L 6000 dummy_data/ref.fa | grep -c '^>'",
      expect="=1"),

    R(id="F12", cat="fastx", tools=[],
      task="Per-contig lengths without reading the FASTA at all",
      cmd="cut -f1,2 dummy_data/ref.fa.fai",
      trap="Parsing a multi-gigabyte FASTA to measure contigs re-reads every "
           "base. The .fai index already stores the lengths.",
      expect="~chr1"),

    R(id="F13", cat="fastx", tools=["seqtk"],
      task="Interleave two paired FASTQ files",
      cmd="seqtk mergepe dummy_data/reads_R1.fq.gz dummy_data/reads_R2.fq.gz "
          "| awk 'END {print NR/4}'",
      expect="=342"),

    R(id="F14", cat="fastx", tools=[],
      task="Strip a FASTQ down to read IDs",
      cmd="gzip -dc dummy_data/reads_R1.fq.gz | "
          "awk 'NR%4==1 {sub(/^@/, \"\"); print $1}' | head -3",
      trap="`grep '^@'` also matches quality lines that happen to start with "
           "'@', because '@' is a legal Phred score.",
      expect="~READ"),

    # ------------------------------------------------------------------ vcf
    R(id="V01", cat="vcf", tools=["bcftools"],
      task="Count variants instantly",
      cmd="bcftools index -n dummy_data/variants.vcf.gz",
      trap="`bcftools view -H | wc -l` decompresses and parses every record. "
           "The index already stores the count.",
      expect="=42"),

    R(id="V02", cat="vcf", tools=["bcftools"],
      task="List sample names",
      cmd="bcftools query -l dummy_data/variants.vcf.gz",
      expect="~HG001"),

    R(id="V03", cat="vcf", tools=["bcftools"],
      task="Keep only PASS variants",
      cmd="bcftools view -H -f PASS dummy_data/variants.vcf.gz | wc -l",
      trap="-f matches the FILTER column, so `-f PASS` also keeps '.' "
           "(filters not applied). Use -i 'FILTER==\"PASS\"' to be strict.",
      expect="=40"),

    R(id="V04", cat="vcf", tools=["bcftools"],
      task="Extract a genomic region",
      cmd="bcftools view -H -r chr1:1200-2400 dummy_data/variants.vcf.gz | wc -l",
      trap="-r jumps via the index and fails without one; -t streams the "
           "whole file instead. Also check your coordinates match the "
           "assembly the VCF was called against.",
      expect="~[0-9]"),

    R(id="V05", cat="vcf", tools=["bcftools"],
      task="Flatten a VCF into a table",
      cmd="bcftools query -f '%CHROM\\t%POS\\t%REF\\t%ALT\\t%QUAL\\n' "
          "dummy_data/variants.vcf.gz | head -3",
      expect="~chr1"),

    R(id="V06", cat="vcf", tools=["bcftools"],
      task="Count SNPs and indels separately",
      cmd="for t in snps indels; do "
          "printf '%s\\t%s\\n' \"$t\" "
          "\"$(bcftools view -H -v $t dummy_data/variants.vcf.gz | wc -l | tr -d ' ')\"; "
          "done",
      expect="~snps"),

    R(id="V07", cat="vcf", tools=["bcftools"],
      task="Split multi-allelic sites into one row per allele",
      cmd="bcftools norm -m -any -f dummy_data/ref.fa "
          "dummy_data/variants.vcf.gz 2>/dev/null | grep -vc '^#'",
      trap="Allele frequencies and genotype counts computed over packed "
           "multi-allelic rows are wrong. Normalise before you count.",
      expect="~[0-9]"),

    R(id="V08", cat="vcf", tools=["bcftools"],
      task="Filter on QUAL and depth together",
      cmd="bcftools view -H -i 'QUAL>=30 && INFO/DP>=20' "
          "dummy_data/variants.vcf.gz | wc -l",
      trap="INFO/DP and FORMAT/DP are different fields. Unqualified 'DP' in "
           "an expression is ambiguous - always say which one you mean.",
      expect="~[0-9]"),

    R(id="V09", cat="vcf", tools=["bcftools"],
      task="Dump a genotype matrix",
      cmd="bcftools query -f '%CHROM\\t%POS[\\t%GT]\\n' "
          "dummy_data/variants.vcf.gz | head -3",
      expect="~chr1"),

    R(id="V10", cat="vcf", tools=["bcftools"],
      task="Per-sample het, hom and missing counts",
      cmd="bcftools stats -s - dummy_data/variants.vcf.gz | "
          "grep '^PSC' | cut -f3,5,6,14",
      expect="~HG001"),

    R(id="V11", cat="vcf", tools=["bcftools"],
      task="Subset samples and drop sites that are no longer variable",
      cmd="bcftools view -s HG001,HG002 -a -H dummy_data/variants.vcf.gz | wc -l",
      trap="Subsetting samples leaves AC/AN stale. -a trims unseen alleles; "
           "add `+fill-tags` if you need the INFO counts recomputed.",
      expect="~[0-9]"),

    R(id="V12", cat="vcf", tools=["bgzip", "tabix"],
      task="Compress and index a plain VCF so it can be queried by region",
      cmd="bgzip -c dummy_data/variants.vcf > out.vcf.gz && "
          "tabix -p vcf out.vcf.gz && echo indexed",
      trap="A plain `gzip` file cannot be indexed. bgzip writes block-gzip, "
           "which every tool reads as normal gzip but tabix can seek into.",
      expect="=indexed"),

    R(id="V13", cat="vcf", tools=["bcftools"],
      task="Variant count per chromosome",
      cmd="bcftools query -f '%CHROM\\n' dummy_data/variants.vcf.gz | uniq -c",
      trap="`sort | uniq -c` on a coordinate-sorted VCF is wasted work - the "
           "chromosomes already arrive grouped.",
      expect="~chr1"),

    # ------------------------------------------------------------------ bam
    R(id="B01", cat="bam", tools=["samtools"],
      task="Count every alignment record",
      cmd="samtools view -c dummy_data/aligned.bam",
      expect="=349"),

    R(id="B02", cat="bam", tools=["samtools"],
      task="Count primary mapped reads",
      cmd="samtools view -c -F 0x904 dummy_data/aligned.bam",
      trap="-F 4 also counts secondary (0x100) and supplementary (0x800) "
           "alignments, so it over-reports. On this toy BAM: 337 vs 330.",
      expect="=330"),

    R(id="B03", cat="bam", tools=["samtools"],
      task="Full mapping summary",
      cmd="samtools flagstat dummy_data/aligned.bam | head -6",
      expect="~total"),

    R(id="B04", cat="bam", tools=["samtools"],
      task="Mean depth across the whole reference",
      cmd="samtools depth -a dummy_data/aligned.bam | awk '{s+=$3} END {print s/NR}'",
      trap="Without -a, samtools depth omits zero-coverage positions "
           "entirely, so dividing by NR gives mean depth over covered bases "
           "only. On this toy BAM that is 3.84x instead of the true 2.14x.",
      expect="~^2\\."),

    R(id="B05", cat="bam", tools=["samtools"],
      task="Coverage, depth and breadth per contig",
      cmd="samtools coverage dummy_data/aligned.bam",
      trap="This is the purpose-built tool. Reach for it before hand-rolling "
           "awk over `samtools depth`.",
      expect="~chr1"),

    R(id="B06", cat="bam", tools=["samtools"],
      task="Extract a region as BAM",
      cmd="samtools view -b dummy_data/aligned.bam chr1:1200-2400 > region.bam && "
          "samtools view -c region.bam",
      trap="Region queries need the .bai next to the .bam. Without it "
           "samtools reads the entire file or refuses outright.",
      expect="~[0-9]"),

    R(id="B07", cat="bam", tools=["samtools"],
      task="Recover unmapped reads as paired FASTQ",
      cmd="samtools fastq -f 4 -1 un_R1.fq -2 un_R2.fq -0 /dev/null "
          "-s /dev/null -n dummy_data/aligned.bam 2>/dev/null && "
          "awk 'END {print NR/4}' un_R1.fq",
      trap="`samtools fastq -f 4 in.bam > out.fq` interleaves R1 and R2 into "
           "one file and drops singletons silently. Always give -1/-2/-0/-s.",
      expect="=6"),

    R(id="B08", cat="bam", tools=["samtools"],
      task="Sort and index in a single pass",
      cmd="samtools sort --write-index -o sorted.bam dummy_data/aligned.sam "
          "2>/dev/null && ls sorted.bam.csi",
      trap="`samtools sort && samtools index` re-reads the entire sorted BAM. "
           "--write-index builds the index during the sort.",
      expect="~sorted.bam.csi"),

    R(id="B09", cat="bam", tools=["samtools"],
      task="Count PCR duplicates",
      cmd="samtools view -c -f 1024 dummy_data/aligned.bam",
      trap="This counts reads already flagged by markdup. samtools does not "
           "detect duplicates as a side effect of counting them.",
      expect="=10"),

    R(id="B10", cat="bam", tools=["samtools"],
      task="Filter by mapping quality",
      cmd="samtools view -c -q 30 dummy_data/aligned.bam",
      trap="MAPQ scales differ between aligners. BWA's 0 means multi-mapping; "
           "a MAPQ 30 cut means different things across tools.",
      expect="~[0-9]"),

    R(id="B11", cat="bam", tools=["samtools"],
      task="Reads per chromosome, read from the index",
      cmd="samtools idxstats dummy_data/aligned.bam",
      trap="Counting per chromosome with `view -c` scans the alignments. "
           "idxstats reads only the index and returns instantly.",
      expect="~chr1"),

    R(id="B12", cat="bam", tools=["samtools"],
      task="Insert size summary",
      cmd="samtools stats dummy_data/aligned.bam | grep '^SN' | "
          "grep 'insert size'",
      expect="~insert size"),

    R(id="B13", cat="bam", tools=["samtools"],
      task="Convert BAM to CRAM",
      cmd="samtools view -T dummy_data/ref.fa -C -o out.cram "
          "dummy_data/aligned.bam && samtools view -c out.cram",
      trap="CRAM is reference-compressed. Lose the exact reference FASTA and "
           "you may not be able to decode the file again.",
      expect="=349"),

    R(id="B14", cat="bam", tools=["samtools"],
      task="Read the header / contig list",
      cmd="samtools view -H dummy_data/aligned.bam | grep '^@SQ'",
      expect="~SN:chr1"),

    R(id="B15", cat="bam", tools=["samtools"],
      task="Deterministic downsample",
      cmd="samtools view -c -s 42.5 dummy_data/aligned.bam",
      trap="-s takes SEED.FRACTION as a single number. `-s 0.1` is seed 0 at "
           "10%, which is rarely what people think they wrote.",
      expect="~[0-9]"),

    # ------------------------------------------------------------------ bed
    R(id="D01", cat="bed", tools=["bedtools"],
      task="Merge overlapping intervals",
      cmd="sort -k1,1 -k2,2n dummy_data/genes.bed | bedtools merge -i - | wc -l",
      trap="bedtools merge assumes sorted input. Give it unsorted intervals "
           "and it returns wrong output without an error.",
      expect="~4"),

    R(id="D02", cat="bed", tools=["bedtools"],
      task="Variants that fall inside annotated genes",
      cmd="bedtools intersect -a dummy_data/variants.vcf.gz "
          "-b dummy_data/genes.bed -u -header | grep -vc '^#'",
      trap="Without -u, a variant overlapping two genes is emitted once per "
           "overlap, quietly inflating your counts.",
      expect="~[0-9]"),

    R(id="D03", cat="bed", tools=["bedtools"],
      task="Count variants per gene",
      cmd="bedtools intersect -c -a dummy_data/genes.bed "
          "-b dummy_data/variants.vcf.gz",
      expect="~GENE1"),

    R(id="D04", cat="bed", tools=["bedtools"],
      task="Pull the sequence of every interval",
      cmd="bedtools getfasta -fi dummy_data/ref.fa -bed dummy_data/genes.bed "
          "-name | head -1",
      expect="~GENE"),

    R(id="D05", cat="bed", tools=["bedtools"],
      task="Find the regions with no annotation",
      cmd="bedtools complement -i dummy_data/genes.bed "
          "-g dummy_data/genome.txt | wc -l",
      trap="complement needs a genome file of contig lengths. Build it "
           "straight from the .fai: cut -f1,2 ref.fa.fai > genome.txt",
      expect="~[0-9]"),

    R(id="D06", cat="bed", tools=["bedtools"],
      task="Read coverage over each gene",
      cmd="bedtools coverage -a dummy_data/genes.bed -b dummy_data/aligned.bam "
          "| cut -f4,7,8,10",
      expect="~GENE1"),

    R(id="D07", cat="bed", tools=["bedtools"],
      task="Nearest gene to every variant",
      cmd="bedtools closest -a dummy_data/variants.vcf.gz "
          "-b dummy_data/genes.bed 2>/dev/null | head -2",
      trap="closest needs both inputs sorted the same way, and reports "
           "distance 0 for anything overlapping.",
      expect="~chr1"),

    R(id="D08", cat="bed", tools=[],
      task="Total bases covered by a BED file",
      cmd="awk '{s += $3 - $2} END {print s}' dummy_data/genes.bed",
      trap="Correct for BED because it is 0-based half-open. The same "
           "arithmetic on a GTF is off by one per feature - GTF is 1-based "
           "inclusive and needs end-start+1.",
      expect="=6900"),

    R(id="D09", cat="bed", tools=["bedtools"],
      task="Extend intervals without running off the contig",
      cmd="bedtools slop -b 500 -i dummy_data/genes.bed "
          "-g dummy_data/genome.txt | head -2",
      trap="Adding flanks with awk produces negative starts and coordinates "
           "past the contig end. slop clamps them because it knows the sizes.",
      expect="~chr1"),

    R(id="D10", cat="bed", tools=["bedtools"],
      task="Subtract one interval set from another",
      cmd="bedtools subtract -a dummy_data/genes.bed "
          "-b dummy_data/variants.vcf.gz | wc -l",
      expect="~[0-9]"),

    # ------------------------------------------------------------------ gtf
    R(id="G01", cat="gtf", tools=[],
      task="Count features by type",
      cmd="awk -F'\\t' '!/^#/ {print $3}' dummy_data/annotation.gtf | "
          "sort | uniq -c | sort -rn",
      expect="~exon"),

    R(id="G02", cat="gtf", tools=[],
      task="Extract gene_id and gene_name reliably",
      cmd="awk -F'\\t' '$3==\"gene\" { id=nm=\"NA\"; "
          "if (match($9, /gene_id \"[^\"]+\"/)) "
          "id=substr($9, RSTART+9, RLENGTH-10); "
          "if (match($9, /gene_name \"[^\"]+\"/)) "
          "nm=substr($9, RSTART+11, RLENGTH-12); "
          "print id \"\\t\" nm }' dummy_data/annotation.gtf",
      trap="Positional parsing (`cut -d';' -f3`) breaks on genes with no "
           "gene_name - common for novel and lncRNA genes - and silently "
           "returns gene_source instead. Match on the key, never the position.",
      expect="~GENE1"),

    R(id="G03", cat="gtf", tools=[],
      task="Convert GTF genes to BED",
      cmd="awk -F'\\t' '$3==\"gene\" {print $1 \"\\t\" ($4-1) \"\\t\" $5}' "
          "dummy_data/annotation.gtf | head -3",
      trap="GTF is 1-based inclusive, BED is 0-based half-open. The start "
           "must lose exactly one base; the end must not.",
      expect="~chr1"),

    R(id="G04", cat="gtf", tools=[],
      task="Exon count per gene",
      cmd="awk -F'\\t' '$3==\"exon\" { if (match($9, /gene_id \"[^\"]+\"/)) "
          "print substr($9, RSTART+9, RLENGTH-10) }' "
          "dummy_data/annotation.gtf | sort | uniq -c",
      expect="~TOYG"),

    R(id="G05", cat="gtf", tools=["bedtools"],
      task="Exonic length per gene, without double counting",
      cmd="awk -F'\\t' '$3==\"exon\" { if (match($9, /gene_id \"[^\"]+\"/)) "
          "print $1 \"\\t\" ($4-1) \"\\t\" $5 \"\\t\" "
          "substr($9, RSTART+9, RLENGTH-10) }' dummy_data/annotation.gtf | "
          "sort -k1,1 -k2,2n | bedtools merge -i - -c 4 -o distinct | "
          "awk '{len[$4] += $3-$2} END {for (g in len) print g \"\\t\" len[g]}' | sort",
      trap="Summing exon lengths straight from the GTF double-counts exons "
           "shared between transcripts of the same gene. Merge first.",
      expect="~TOYG"),

    R(id="G06", cat="gtf", tools=[],
      task="List every attribute key present in the file",
      cmd="grep -v '^#' dummy_data/annotation.gtf | cut -f9 | tr ';' '\\n' | "
          "awk 'NF {print $1}' | sort | uniq -c | sort -rn",
      trap="Do this before writing any parser. Attribute sets differ between "
           "Ensembl, GENCODE and NCBI, and between feature types in one file.",
      expect="~gene_id"),

    R(id="G07", cat="gtf", tools=[],
      task="Genes on one strand within a region",
      cmd="awk -F'\\t' '$1==\"chr1\" && $3==\"gene\" && $7==\"+\" && "
          "$4 < 4000 {print $1, $4, $5, $7}' dummy_data/annotation.gtf",
      expect="~chr1"),

    # ----------------------------------------------------------------- perf
    R(id="P01", cat="perf", tools=["pigz"],
      task="Compress with all your cores",
      cmd="pigz -p 4 -c dummy_data/ref.fa | wc -c",
      trap="pigz parallelises compression only. Gzip *decompression* is "
           "inherently serial, so `pigz -dc` is barely faster than `gzip -dc` "
           "- it is not the speed-up people expect.",
      expect="~[0-9]"),

    R(id="P02", cat="perf", tools=["bgzip", "tabix"],
      task="Compress so you can seek into the file later",
      cmd="bgzip -c -@ 2 dummy_data/variants.vcf > p.vcf.gz && "
          "tabix -p vcf p.vcf.gz && tabix p.vcf.gz chr1:1200-2400 | wc -l",
      trap="Random access needs block-gzip. bgzip output stays readable by "
           "gzip and zcat, so there is no reason to use plain gzip for "
           "anything you will query later.",
      expect="~[0-9]"),

    R(id="P03", cat="perf", tools=[],
      task="Sort large files much faster",
      cmd="LC_ALL=C sort -k1,1 -k2,2n -S 512M dummy_data/genes.bed | head -2",
      trap="LC_ALL=C is a large speed-up but it changes collation order. Use "
           "it consistently across every sort in a pipeline, or `join`, "
           "`comm` and `bedtools` will silently mismatch.",
      expect="~chr1"),

    R(id="P04", cat="perf", tools=["rg"],
      task="Search inside compressed files without decompressing first",
      cmd="rg -z -c 'READ00001' dummy_data/reads_R1.fq.gz",
      trap="ripgrep's real advantage is recursive multi-file search. On a "
           "single plain file grep is just as fast.",
      expect="~[0-9]"),

    R(id="P05", cat="perf", tools=[],
      task="Let awk open the file itself",
      cmd="awk 'END {print NR}' dummy_data/genes.bed",
      trap="`cat file | awk ...` forks an extra process and throws away "
           "FILENAME and FNR, which awk needs for multi-file work.",
      expect="=6"),

    R(id="P06", cat="perf", tools=[],
      task="Make a pipeline fail when any stage fails",
      cmd="(set -o pipefail; samtools view /no/such/file.bam 2>/dev/null | "
          "wc -l > /dev/null; echo \"exit=$?\")",
      trap="By default a pipeline reports only the LAST command's status, so "
           "a crashed samtools upstream of `wc -l` looks like success. This "
           "is the single most common silent-failure bug in bioinformatics "
           "shell scripts.",
      expect="~exit=[1-9]"),

    R(id="P07", cat="perf", tools=["samtools"],
      task="Stream through a pipeline without temporary files",
      cmd="samtools view -u -F 0x904 dummy_data/aligned.bam | "
          "samtools sort -o /dev/null - 2>/dev/null && echo streamed",
      trap="-u writes uncompressed BAM between processes. Compressing "
           "intermediate output just to decompress it again wastes CPU.",
      expect="=streamed"),
]


# The traps worth putting at the top of the README: the ones that fail
# silently and produce a plausible wrong number rather than an error.
# Written against generic filenames rather than dummy_data/ so the table reads
# as a reference. (recipe id, what people write, what it should be)
HERO = [
    ("B04",
     "samtools depth in.bam | awk '{s+=$3} END {print s/NR}'",
     "samtools depth -a in.bam | awk '{s+=$3} END {print s/NR}'"),
    ("B02",
     "samtools view -c -F 4 in.bam",
     "samtools view -c -F 0x904 in.bam"),
    ("B07",
     "samtools fastq -f 4 in.bam > unmapped.fq",
     "samtools fastq -f 4 -1 un_R1.fq -2 un_R2.fq -0 /dev/null "
     "-s /dev/null -n in.bam"),
    ("G02",
     "awk -F'\\t' '$3==\"gene\" {print $9}' in.gtf | awk -F';' '{print $1, $3}'",
     "awk -F'\\t' '$3==\"gene\" && match($9, /gene_name \"[^\"]+\"/) "
     "{print substr($9, RSTART+11, RLENGTH-12)}' in.gtf"),
    ("P06",
     "samtools view in.bam | wc -l",
     "set -o pipefail; samtools view in.bam | wc -l"),
    ("V12",
     "gzip -c in.vcf > in.vcf.gz && tabix -p vcf in.vcf.gz",
     "bgzip -c in.vcf > in.vcf.gz && tabix -p vcf in.vcf.gz"),
    ("D01",
     "bedtools merge -i regions.bed",
     "sort -k1,1 -k2,2n regions.bed | bedtools merge -i -"),
    ("F03",
     "seqtk sample -s100 R1.fq.gz 10000 > s1.fq; "
     "seqtk sample -s42 R2.fq.gz 10000 > s2.fq",
     "seqtk sample -s100 R1.fq.gz 10000 > s1.fq; "
     "seqtk sample -s100 R2.fq.gz 10000 > s2.fq"),
    ("P01",
     "pigz -dc big.fq.gz | wc -l",
     "gzip -dc big.fq.gz | wc -l   # same speed; use pigz -p N to COMPRESS"),
    ("P03",
     "sort -k1,1 -k2,2n big.bed | join - ids.txt",
     "LC_ALL=C sort -k1,1 -k2,2n big.bed | LC_ALL=C join - ids.txt"),
]


# Short, feed-legible headlines for the carousel slides, keyed by recipe id.
SLIDE_TITLES = {
    "B04": "Your coverage number is too high",
    "B02": "You are counting the same read twice",
    "B07": "Your unmapped reads lost their pairing",
    "G02": "Your gene names are silently wrong",
    "P06": "The pipeline failed and said nothing",
    "V12": "gzip is not bgzip",
    "D01": "merge trusted you to sort first",
    "F03": "Your subsampled mates no longer match",
    "P01": "pigz did not speed that up",
    "P03": "LC_ALL=C is fast, and dangerous",
}


def get(recipe_id):
    for r in RECIPES:
        if r["id"] == recipe_id:
            return r
    raise KeyError(recipe_id)


def by_category():
    out = []
    for key, title in CATEGORIES:
        items = [r for r in RECIPES if r["cat"] == key]
        if items:
            out.append((key, title, items))
    return out


if __name__ == "__main__":
    print("%d recipes across %d categories" % (len(RECIPES), len(CATEGORIES)))
    for key, title, items in by_category():
        traps = sum(1 for r in items if r.get("trap"))
        print("  %-34s %2d recipes, %2d traps" % (title, len(items), traps))
