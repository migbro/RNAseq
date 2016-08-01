#!/usr/bin/env python
import sys

sys.path.append('/home/ubuntu/TOOLS/Scripts/utility')
from date_time import date_time
from log import log
import subprocess


def filter_wrap(mmu_filter, star_tool, genome_ref, end1, end2, sample, log_dir, threads):
    meta = sample.split('_')
    RGRP = "ID:" + sample + "\tLB:" + meta[0] + "\tPU:" + meta[4] + "\tSM:" + meta[0] + "\tPL:illumina"
    star_cmd = star_tool + " --runMode alignReads --twopassMode Basic --outSAMattrRGline " + RGRP \
               + " --outFileNamePrefix " + sample + ".mmu_filt. --runThreadN " + threads + " --genomeDir " + genome_ref\
               + " --readFilesIn " + end1 + " " + end2 + " --readFilesCommand zcat --outSAMtype BAM Unsorted" \
                " --outFilterType BySJout --outFilterMultimapNmax 20 --alignSJoverhangMin 8 --alignSJDBoverhangMin 1" \
                " --outFilterMismatchNmax 0" + " --alignIntronMin 20 --alignIntronMax 1000000 --alignMatesGapMax" \
                " 1000000 --outSAMunmapped Within"
    loc = log_dir + sample + ".mmu.star.pe.log"
    log(loc, date_time() + star_cmd + '\n')
    check = subprocess.call(star_cmd, shell=True)
    if check != 0:
        log(loc + date_time() + 'Star alignment against mouse genome failed\n')
        exit(1)
    filter_cmd =  mmu_filter + " -s " + sample + " -b " + sample + ".mmu_filt.Aligned.out.bam -o " + sample \
                  + ".filtered"
    check = subprocess.call(filter_cmd, shell=True)
    if check != 0:
        log(loc, date_time() + "Filtering failed\n")
        exit(1)
    log(loc, date_time() + 'Filtering completed, replacing fastq file\n')
    rn_fq = 'mv ' + sample + '.filtered_1.fq.gz ' + end1 + '; mv ' + sample + '.filtered_2.fq.gz ' + end2
    check = subprocess.call(rn_fq, shell=True)
    if check != 0:
        log(loc, date_time() + 'File rename failed\n' + rn_fq + '\n')
        exit(1)
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Mouse read filter alignment module. Fairly PDX-specific process.')
    parser.add_argument('-mmu', '--mmu_filter', action='store', dest='mmu_filter',
                        help='Location of bam filter tool.')
    parser.add_argument('-s', '--star', action='store', dest='star_tool',
                        help='Location of STAR alignment tool.  Version 2.4.2a preferred.')
    parser.add_argument('-g', '--genome_reference', action='store', dest='genome_ref', help='Location of star genome'
                                                                                            ' reference file')
    parser.add_argument('-f1', '--file1', action='store', dest='end1', help='First of paired-end fastq file')
    parser.add_argument('-f2', '--file2', action='store', dest='end2', help='Second of paired-end fastq file')
    parser.add_argument('-sa', '--sample', action='store', dest='sample', help='Sample/project name prefix')
    parser.add_argument('-l', '--log', action='store', dest='log_dir', help='LOG directory location')
    parser.add_argument('-t', '--threads', action='store', dest='threads',
                        help='Number of threads to use.  8 recommended for standard vm')

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    inputs = parser.parse_args()
    (mmu_filter, star_tool, genome_ref, end1, end2, sample, log_dir, threads) = (
        inputs.mmu_filter, inputs.star_tool, inputs.genome_ref, inputs.end1, inputs.end2, inputs.sample,
        inputs.log_dir, inputs.threads)
    filter_wrap(mmu_filter, star_tool, genome_ref, end1, end2, sample, log_dir, threads)