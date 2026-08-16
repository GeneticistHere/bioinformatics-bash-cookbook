#!/usr/bin/env python3
"""Generate the plain-text sources for dummy_data/.

Pure standard library, fixed seed, no dependencies. Writes the text formats
(FASTA, FASTQ, SAM, VCF, BED, GTF). build_dummy_data.sh then compiles them
into the binary/indexed formats with samtools, bgzip and tabix.

The toy genome is deliberately shaped so the cookbook's traps are visible:

  * chr1:4000-5000 has zero read coverage, so `samtools depth` and
    `samtools depth -a` return different means.
  * secondary (0x100) and supplementary (0x800) alignments are present, so
    `-F 4` and `-F 0x904` return different counts.
  * GTF attributes use Ensembl ordering (gene_id, gene_version, gene_name...),
    so `cut -d';' -f3` yields gene_version, not gene_name.
  * genes.bed contains overlapping features, so `bedtools merge` has work to do.
"""

import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "dummy_data")

CONTIGS = [("chr1", 10000), ("chr2", 5000)]
READ_LEN = 100
FRAG_LEN = 300
MAX_FRAG = 480
SEED = 42

rng = random.Random(SEED)

# --------------------------------------------------------------------------
# reference
# --------------------------------------------------------------------------

def make_genome():
    return {name: "".join(rng.choice("ACGT") for _ in range(length))
            for name, length in CONTIGS}


def revcomp(seq):
    return seq.translate(str.maketrans("ACGTN", "TGCAN"))[::-1]


def write_fasta(genome, path, width=60):
    with open(path, "w") as fh:
        for name, length in CONTIGS:
            fh.write(">%s toy contig length=%d\n" % (name, length))
            seq = genome[name]
            for i in range(0, len(seq), width):
                fh.write(seq[i:i + width] + "\n")


# --------------------------------------------------------------------------
# reads: paired-end, drawn from defined covered intervals
# --------------------------------------------------------------------------

# (contig, start, end, n_pairs) - 0-based half-open. Gaps between these are
# intentionally left at zero coverage.
COVERED = [
    ("chr1", 1000, 4000, 60),
    ("chr1", 5000, 8000, 50),
    ("chr1", 8000, 9800, 10),   # deliberately sparse
    ("chr2",  500, 2500, 40),
]


def mutate(seq, rate=0.005):
    """Introduce occasional mismatches so the BAM is not a perfect copy."""
    out = []
    for base in seq:
        if rng.random() < rate:
            out.append(rng.choice([b for b in "ACGT" if b != base]))
        else:
            out.append(base)
    return "".join(out)


def qual_string(length, good=True):
    if good:
        return "I" * length
    return "".join(rng.choice("!#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHI")
                   for _ in range(length))


class Read:
    """One SAM record."""

    def __init__(self, qname, flag, rname, pos, mapq, cigar, rnext, pnext,
                 tlen, seq, qual, tags=""):
        self.qname, self.flag, self.rname, self.pos = qname, flag, rname, pos
        self.mapq, self.cigar, self.rnext, self.pnext = mapq, cigar, rnext, pnext
        self.tlen, self.seq, self.qual, self.tags = tlen, seq, qual, tags

    def line(self):
        fields = [self.qname, str(self.flag), self.rname, str(self.pos),
                  str(self.mapq), self.cigar, self.rnext, str(self.pnext),
                  str(self.tlen), self.seq, self.qual]
        if self.tags:
            fields.append(self.tags)
        return "\t".join(fields)


def make_reads(genome):
    """Return (sam_records, fastq_r1, fastq_r2)."""
    records, fq1, fq2 = [], [], []
    counter = 0

    def pair(contig, start, mapq=60, dup=False, low_qual=False, frag=None):
        """Emit a proper pair starting at 0-based `start`.

        Fragment length is drawn from a normal distribution rather than fixed,
        so `samtools stats` reports a realistic insert-size distribution.
        """
        nonlocal counter
        counter += 1
        name = "READ%05d" % counter
        ref = genome[contig]
        if frag is None:
            frag = int(round(rng.gauss(FRAG_LEN, 40)))
            frag = max(READ_LEN + 20, min(frag, MAX_FRAG))
        r1_start = start
        r2_start = start + frag - READ_LEN
        r1_seq = mutate(ref[r1_start:r1_start + READ_LEN])
        r2_seq = mutate(ref[r2_start:r2_start + READ_LEN])
        q1 = qual_string(READ_LEN, good=not low_qual)
        q2 = qual_string(READ_LEN, good=not low_qual)

        flag1, flag2 = 99, 147           # proper pair, R1 fwd / R2 rev
        if dup:
            flag1 += 1024
            flag2 += 1024
        cig = "%dM" % READ_LEN
        # SAM POS is 1-based
        records.append(Read(name, flag1, contig, r1_start + 1, mapq, cig,
                            "=", r2_start + 1, frag, r1_seq, q1, "NM:i:0"))
        records.append(Read(name, flag2, contig, r2_start + 1, mapq, cig,
                            "=", r1_start + 1, -frag, r2_seq, q2, "NM:i:0"))
        # FASTQ stores the original read orientation: R2 is reverse complemented
        fq1.append((name, r1_seq, q1))
        fq2.append((name, revcomp(r2_seq), q2[::-1]))
        return name, contig, r1_start, frag

    placed = []
    for contig, start, end, n in COVERED:
        span = end - start - MAX_FRAG
        for _ in range(n):
            offset = rng.randrange(0, max(span, 1))
            # a tenth of the reads get low mapping quality
            mapq = 60 if rng.random() > 0.1 else rng.randrange(0, 11)
            low_qual = rng.random() < 0.05
            placed.append(pair(contig, start + offset, mapq=mapq,
                               low_qual=low_qual))

    # PCR duplicates: re-emit five existing pairs, same coordinates and same
    # fragment length, with the 0x400 flag set
    for name, contig, start, frag in rng.sample(placed, 5):
        pair(contig, start, dup=True, frag=frag)

    # secondary alignments (0x100) - same read, alternative locus
    for i in range(4):
        counter += 1
        name = "READ%05d" % counter
        contig = "chr1"
        start = rng.randrange(1000, 3000)
        seq = mutate(genome[contig][start:start + READ_LEN], rate=0.02)
        records.append(Read(name, 256 + 1 + 64, contig, start + 1, 0,
                            "%dM" % READ_LEN, "=", start + 1, 0, seq,
                            qual_string(READ_LEN), "NM:i:2"))

    # supplementary alignments (0x800) - split read
    for i in range(3):
        counter += 1
        name = "READ%05d" % counter
        contig = "chr2"
        start = rng.randrange(600, 2000)
        # 50M50S: the query is still READ_LEN long, half of it soft-clipped
        aligned = mutate(genome[contig][start:start + 50])
        clipped = "".join(rng.choice("ACGT") for _ in range(READ_LEN - 50))
        records.append(Read(name, 2048 + 1 + 64, contig, start + 1, 60,
                            "50M50S", "=", start + 1, 0, aligned + clipped,
                            qual_string(READ_LEN),
                            "SA:Z:chr1,1000,+,50M50S,60,0"))

    # unmapped pairs (0x4 / 0x8)
    for i in range(6):
        counter += 1
        name = "READ%05d" % counter
        seq = "".join(rng.choice("ACGT") for _ in range(READ_LEN))
        qual = qual_string(READ_LEN)
        records.append(Read(name, 77, "*", 0, 0, "*", "*", 0, 0, seq, qual))
        records.append(Read(name, 141, "*", 0, 0, "*", "*", 0, 0,
                            revcomp(seq), qual[::-1]))
        fq1.append((name, seq, qual))
        fq2.append((name, revcomp(seq), qual[::-1]))

    return records, fq1, fq2


def write_sam(records, path):
    with open(path, "w") as fh:
        fh.write("@HD\tVN:1.6\tSO:unsorted\n")
        for name, length in CONTIGS:
            fh.write("@SQ\tSN:%s\tLN:%d\n" % (name, length))
        fh.write("@RG\tID:toy\tSM:SAMPLE1\tPL:ILLUMINA\tLB:lib1\n")
        fh.write("@PG\tID:make_dummy_data\tPN:make_dummy_data\tVN:1.0\n")
        for rec in records:
            fh.write(rec.line() + "\n")


def write_fastq(reads, path, mate):
    with open(path, "w") as fh:
        for name, seq, qual in reads:
            fh.write("@%s/%d\n%s\n+\n%s\n" % (name, mate, seq, qual))


# --------------------------------------------------------------------------
# genes: BED (0-based half-open) and GTF (1-based inclusive)
# --------------------------------------------------------------------------

# name, contig, start(0-based), end, strand. GENE1/GENE2 and GENE5/GENE6
# overlap on purpose so `bedtools merge` collapses them.
GENES = [
    ("GENE1", "chr1", 1200, 2400, "+"),
    ("GENE2", "chr1", 2200, 3600, "+"),
    ("GENE3", "chr1", 5200, 6800, "-"),
    ("GENE4", "chr1", 8100, 8900, "+"),
    ("GENE5", "chr2",  600, 1800, "+"),
    ("GENE6", "chr2", 1700, 2400, "-"),
]


def write_bed(path):
    with open(path, "w") as fh:
        for i, (name, contig, start, end, strand) in enumerate(GENES, 1):
            fh.write("%s\t%d\t%d\t%s\t%d\t%s\n"
                     % (contig, start, end, name, 100 * i, strand))


# Genes that carry no gene_name attribute, as novel and lncRNA genes routinely
# do in real Ensembl/GENCODE annotations. Their absence shifts every later
# attribute by one, which is what breaks positional `cut -d';' -f3` parsing.
UNNAMED = {"GENE4", "GENE6"}


def write_gtf(path):
    """Ensembl attribute ordering: gene_id, gene_version, gene_name, ..."""
    with open(path, "w") as fh:
        fh.write("#!genome-build toy1\n")
        fh.write("#!genebuild-last-updated 2024-01\n")
        for idx, (name, contig, start, end, strand) in enumerate(GENES, 1):
            gid = "TOYG%08d" % idx
            tid = "TOYT%08d" % idx
            named = name not in UNNAMED
            name_attr = ('gene_name "%s"; ' % name) if named else ""
            biotype = "protein_coding" if named else "lncRNA"
            gene_attrs = (
                'gene_id "%s"; gene_version "1"; %s'
                'gene_source "toy"; gene_biotype "%s";'
                % (gid, name_attr, biotype))
            tx_attrs = (
                'gene_id "%s"; gene_version "1"; transcript_id "%s"; '
                'transcript_version "1"; %sgene_source "toy"; '
                'gene_biotype "%s"; transcript_name "%s-201";'
                % (gid, tid, name_attr, biotype, name))
            fh.write("\t".join([contig, "toy", "gene", str(start + 1),
                                str(end), ".", strand, ".", gene_attrs]) + "\n")
            fh.write("\t".join([contig, "toy", "transcript", str(start + 1),
                                str(end), ".", strand, ".", tx_attrs]) + "\n")
            # three exons per gene, evenly spaced inside the gene body
            span = end - start
            step = span // 5
            for exon_no in range(1, 4):
                ex_start = start + (exon_no - 1) * 2 * step
                ex_end = min(ex_start + step, end)
                attrs = tx_attrs + ' exon_number "%d"; exon_id "TOYE%08d%02d";' \
                    % (exon_no, idx, exon_no)
                fh.write("\t".join([contig, "toy", "exon", str(ex_start + 1),
                                    str(ex_end), ".", strand, ".",
                                    attrs]) + "\n")


# --------------------------------------------------------------------------
# variants
# --------------------------------------------------------------------------

SAMPLES = ["HG001", "HG002", "HG003"]


def write_vcf(genome, path):
    rows = []
    # place most variants inside genes, a handful outside
    positions = []
    for name, contig, start, end, strand in GENES:
        for _ in range(5):
            positions.append((contig, rng.randrange(start + 10, end - 10)))
    for _ in range(8):
        positions.append(("chr1", rng.randrange(100, 900)))
    for _ in range(4):
        positions.append(("chr2", rng.randrange(2600, 4900)))

    seen = set()
    for contig, pos0 in sorted(positions, key=lambda x: (x[0], x[1])):
        if (contig, pos0) in seen:
            continue
        seen.add((contig, pos0))
        ref = genome[contig][pos0]
        kind = rng.random()
        if kind < 0.70:                                   # SNP
            alt = rng.choice([b for b in "ACGT" if b != ref])
        elif kind < 0.85:                                 # insertion
            alt = ref + "".join(rng.choice("ACGT") for _ in range(rng.randrange(1, 4)))
        elif kind < 0.95:                                 # deletion
            ref = genome[contig][pos0:pos0 + 2]
            alt = ref[0]
        else:                                             # multi-allelic
            others = [b for b in "ACGT" if b != ref]
            alt = ",".join(rng.sample(others, 2))

        qual = round(rng.uniform(3, 900), 1)
        filt = "PASS" if qual >= 30 else "LowQual"
        depth = rng.randrange(5, 80)
        n_alt = len(alt.split(","))
        # AF is Number=A in the header, so it needs one value per ALT allele
        af = ",".join(str(round(rng.uniform(0.05, 0.95), 3))
                      for _ in range(n_alt))
        info = "DP=%d;AF=%s;NS=%d" % (depth, af, len(SAMPLES))

        fmts = []
        for _ in SAMPLES:
            if n_alt > 1:
                gt = rng.choice(["0/1", "0/2", "1/2", "0/0"])
            else:
                gt = rng.choice(["0/0", "0/1", "1/1", "./."])
            gq = rng.randrange(3, 99)
            dp = rng.randrange(3, 60)
            fmts.append("%s:%d:%d" % (gt, gq, dp))

        rows.append((contig, pos0 + 1, ".", ref, alt, qual, filt, info,
                     "GT:GQ:DP", fmts))

    with open(path, "w") as fh:
        fh.write("##fileformat=VCFv4.2\n")
        fh.write("##source=make_dummy_data.py\n")
        fh.write('##reference=file://ref.fa\n')
        for name, length in CONTIGS:
            fh.write("##contig=<ID=%s,length=%d>\n" % (name, length))
        fh.write('##FILTER=<ID=LowQual,Description="QUAL below 30">\n')
        fh.write('##INFO=<ID=DP,Number=1,Type=Integer,Description="Total depth">\n')
        fh.write('##INFO=<ID=AF,Number=A,Type=Float,Description="Allele frequency">\n')
        fh.write('##INFO=<ID=NS,Number=1,Type=Integer,Description="Number of samples">\n')
        fh.write('##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n')
        fh.write('##FORMAT=<ID=GQ,Number=1,Type=Integer,Description="Genotype quality">\n')
        fh.write('##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read depth">\n')
        fh.write("#" + "\t".join(["CHROM", "POS", "ID", "REF", "ALT", "QUAL",
                                  "FILTER", "INFO", "FORMAT"] + SAMPLES) + "\n")
        for contig, pos, vid, ref, alt, qual, filt, info, fmt, fmts in rows:
            fh.write("\t".join([contig, str(pos), vid, ref, alt, str(qual),
                                filt, info, fmt] + fmts) + "\n")
    return len(rows)


# --------------------------------------------------------------------------

def main():
    os.makedirs(OUT, exist_ok=True)
    genome = make_genome()

    write_fasta(genome, os.path.join(OUT, "ref.fa"))
    records, fq1, fq2 = make_reads(genome)
    write_sam(records, os.path.join(OUT, "aligned.sam"))
    write_fastq(fq1, os.path.join(OUT, "reads_R1.fq"), 1)
    write_fastq(fq2, os.path.join(OUT, "reads_R2.fq"), 2)
    write_bed(os.path.join(OUT, "genes.bed"))
    write_gtf(os.path.join(OUT, "annotation.gtf"))
    n_var = write_vcf(genome, os.path.join(OUT, "variants.vcf"))

    print("ref.fa          %d contigs" % len(CONTIGS))
    print("aligned.sam     %d records" % len(records))
    print("reads_R1.fq     %d reads" % len(fq1))
    print("reads_R2.fq     %d reads" % len(fq2))
    print("genes.bed       %d features" % len(GENES))
    print("annotation.gtf  %d genes" % len(GENES))
    print("variants.vcf    %d variants, %d samples" % (n_var, len(SAMPLES)))


if __name__ == "__main__":
    main()
