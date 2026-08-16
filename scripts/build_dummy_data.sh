#!/usr/bin/env bash
# Rebuild dummy_data/ from scratch.
#
#   scripts/make_dummy_data.py  writes the plain-text formats (pure Python)
#   this script                 compiles them into indexed binary formats
#
# The compiled files are committed to the repository, so you only need to run
# this if you change the generator. Run it from the repository root.

set -euo pipefail

command -v samtools >/dev/null || { echo "samtools not found - activate the conda env first" >&2; exit 1; }
command -v bcftools >/dev/null || { echo "bcftools not found - activate the conda env first" >&2; exit 1; }
command -v bgzip    >/dev/null || { echo "bgzip not found - activate the conda env first" >&2; exit 1; }

DD=dummy_data

echo "== generating text sources"
python3 scripts/make_dummy_data.py

echo "== indexing reference"
samtools faidx "$DD/ref.fa"
cut -f1,2 "$DD/ref.fa.fai" > "$DD/genome.txt"   # bedtools genome file

echo "== compiling BAM"
samtools sort -o "$DD/aligned.bam" "$DD/aligned.sam"
samtools index "$DD/aligned.bam"

echo "== compressing and indexing VCF"
bgzip -f -k "$DD/variants.vcf"
tabix -f -p vcf "$DD/variants.vcf.gz"

echo "== compressing FASTQ"
# bgzip output is valid gzip, so pigz/gzip/zcat all read it happily
for f in "$DD"/reads_R*.fq; do
  bgzip -f -k "$f"
done

echo "== sorting BED"
sort -k1,1 -k2,2n "$DD/genes.bed" -o "$DD/genes.bed"

echo
echo "== verification"
printf '  contigs         %s\n' "$(wc -l < "$DD/ref.fa.fai" | tr -d ' ')"
printf '  BAM records     %s\n' "$(samtools view -c "$DD/aligned.bam")"
printf '  primary mapped  %s\n' "$(samtools view -c -F 0x904 "$DD/aligned.bam")"
printf '  variants        %s\n' "$(bcftools index -n "$DD/variants.vcf.gz")"
printf '  samples         %s\n' "$(bcftools query -l "$DD/variants.vcf.gz" | tr '\n' ' ')"
printf '  BED features    %s\n' "$(wc -l < "$DD/genes.bed" | tr -d ' ')"
printf '  GTF lines       %s\n' "$(grep -vc '^#' "$DD/annotation.gtf")"
echo
echo "dummy_data/ rebuilt."
