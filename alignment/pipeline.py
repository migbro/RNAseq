#!/usr/bin/env python
import sys

sys.path.append('/home/ubuntu/TOOLS/Scripts/alignment')
sys.path.append('/home/ubuntu/TOOLS/Scripts/utility')
import os
import re
from date_time import date_time
import subprocess
import json
from log import log
from cutadapter import cutadapter
from fastqc import fastqc
from bwt2_pe import bwt2_pe
from novosort_sort_pe import novosort_sort_pe
from picard_insert_size import picard_insert_size
from align_stats import align_stats
from star import star
from report import report
from upload_to_swift import upload_to_swift
from subprocess import call
import pdb


class Pipeline():
    def __init__(self, end1, end2, json_config, ref_mnt):
        self.json_config = json_config
        self.end1 = end1
        self.end2 = end2
        self.status = 0
        self.ref_mnt = ref_mnt
        self.parse_config()

    def parse_config(self):
        self.config_data = json.loads(open(self.json_config, 'r').read())
        s = re.match('^(\S+)_1_sequence\.txt\.gz$', self.end1)
        if s:
            self.sample = s.group(1)
        else:
            s = re.match('(^\S+)_\D*\d\.f\w*q\.gz$', self.end1)
            self.sample = s.group(1)
        self.loc = 'LOGS/' + self.sample + '.pipe.log'
        HGACID = self.sample.split("_")
        self.bid = HGACID[0]
        self.fastqc_tool = self.config_data['tools']['fastqc']
        self.java_tool = self.config_data['tools']['java']
        self.picard_tool = self.config_data['tools']['picard']
        self.novosort = self.config_data['tools']['novosort']
        self.bwt2_tool = self.config_data['tools']['bwt2']
        self.bwt2_ref = self.ref_mnt + '/' + self.config_data['refs']['bwt2']
        self.samtools_tool = self.config_data['tools']['samtools']
        self.picard_tmp = 'picard_tmp'
        self.star_tool = self.config_data['tools']['star']
        self.genome_ref = self.ref_mnt + '/' + self.config_data['refs']['genome']
        self.samtools_ref = self.ref_mnt + '/' + self.config_data['refs']['samtools']
        self.htseq_count = self.config_data['tools']['htseq-count']
        self.gtf_ref = self.ref_mnt + '/' + self.config_data['refs']['gtf']
        self.tx = self.ref_mnt + '/' + self.config_data['refs']['transcriptome']
        self.obj = self.config_data['refs']['obj']
        self.cont = self.config_data['refs']['cont']
        self.threads = self.config_data['params']['threads']
        self.ram = self.config_data['params']['ram']
        self.pipeline()

    def pipeline(self):
        log_dir = 'LOGS/'
        if os.path.isdir(log_dir) == False:
            mk_log_dir = 'mkdir ' + log_dir
            call(mk_log_dir, shell=True)
            log(self.loc, date_time() + 'Made log directory ' + log_dir + "\n")
        fq_dir = 'TRIMMED_FQ'
        if os.path.isdir(fq_dir) == False:
            mk_fq_dir = 'mkdir ' + fq_dir
            call(mk_fq_dir, shell=True)
            log(self.loc, date_time() + 'Made fastq trimmed directory ' + fq_dir + "\n")
        os.chdir(fq_dir)
        mv_fq = 'mv ../LOGS .'
        call(mv_fq, shell=True)
        log(self.loc, date_time() + 'Changed into ' + fq_dir + " and moved log directory there\n")
        # create TOPHAT_OUT, QC, and CUFFLINKS_RES directories if they don't exist already
        star_dir = 'STAR_OUT/'
        bam_dir = 'BAMS/'
        qc_dir = 'QC/'
        rpt_dir = 'REPORTS/'
        if os.path.isdir(star_dir) == False:
            mk_star_dir = 'mkdir ' + star_dir
            call(mk_star_dir, shell=True)
            log(self.loc, date_time() + 'Made star output directory ' + star_dir + "\n")
        if os.path.isdir(bam_dir) == False:
            mk_bam_dir = 'mkdir ' + bam_dir
            call(mk_bam_dir, shell=True)
            log(self.loc, date_time() + 'Made bam output directory ' + bam_dir + "\n")
        if os.path.isdir(qc_dir) == False:
            mk_qc_dir = 'mkdir ' + qc_dir
            call(mk_qc_dir, shell=True)
            log(self.loc, date_time() + 'Made qc directory ' + qc_dir + "\n")
            #       if os.path.isdir(rpt_dir) == False:
            #           mk_rpt_dir='mkdir ' + rpt_dir
            #           call(mk_rpt_dir,shell=True)
            #           log(self.loc,date_time() + 'Made reports directory ' + rpt_dir + "\n")
        log(self.loc,
            date_time() + "Starting alignment qc for paired end sample files " + self.end1 + " and " + self.end2 + "\n")
        # inputs

        SAMPLES = {}
        SAMPLES[self.sample] = {}
        SAMPLES[self.sample]['f1'] = self.end1
        SAMPLES[self.sample]['f2'] = self.end2
        # remove adapters

        check = cutadapter(self.sample, self.end1, self.end2, self.json_config)
        if (check != 0):
            log(self.loc, date_time() + 'cutadapt failure for ' + self.sample + '\n')
            exit(1)
        # remove original fastqs as they are no longer needed
        rm_fq = 'rm ../' + self.end1 + ' ../' + self.end2
        log(self.loc, date_time() + 'deleting untrimmed fastqs, no longer needed\n' + rm_fq + '\n')
        call(rm_fq, shell=True)
        # start fastqc, will run while insert size being calculated
        end_ss1 = self.sample + '_1.subset.fastq'
        end_ss2 = self.sample + '_2.subset.fastq'
        subset = self.sample + '_subset'

        ss_cmd = 'gunzip -c ' + self.end1 + ' | head -n 400000 > ' + end_ss1
        subprocess.call(ss_cmd, shell=True)
        ss_cmd = 'gunzip -c ' + self.end2 + ' | head -n 400000 > ' + end_ss2
        subprocess.call(ss_cmd, shell=True)
        # check certain key processes

        check = bwt2_pe(self.bwt2_tool, self.tx, end_ss1, end_ss2, self.samtools_tool, self.samtools_ref, subset,
                        self.threads, log_dir)
        if (check != 0):
            log(self.loc, date_time() + 'Bowtie2 failure for ' + self.sample + '\n')
            self.status = 1
            exit(1)
        check = novosort_sort_pe(self.novosort, subset, log_dir, self.threads,
                                 self.ram)  # rest won't run until completed
        if (check != 0):
            log(self.loc, date_time() + 'novosort sort failure for ' + self.sample + '\n')
            self.status = 1
            exit(1)
        (x, s) = picard_insert_size(self.java_tool, self.picard_tool, subset, log_dir)
        log(self.loc, date_time() + 'Running qc on fastq file\n')
        fastqc(self.fastqc_tool, self.sample, self.end1, self.end2, self.threads)
        log(self.loc, date_time() + 'Performing star alignment ' + self.sample + '\n')
        star(self.star_tool, self.genome_ref, self.end1, self.end2, (self.sample + '.'), log_dir, self.threads)
        #        align_stats(self.sample)
        #        report(self.sample,self.gtf_ref,cout)

        # move outputs to correct directories and upload
        log(self.loc, date_time() + 'Organizing outputs\n')
        mv_bams = 'mv *.bam *.bai ' + bam_dir
        call(mv_bams, shell=True)
        mv_star = 'mv *.out *.tab ' + star_dir
        call(mv_star, shell=True)
        mv_sub = 'mv *subset* ' + qc_dir
        call(mv_sub, shell=True)
        #       mv_rpt='mv *.txt REPORTS/'
        #       call(mv_rpt,shell=True)
        #        org_mv='mv BAMS STAR_OUT QC REPORTS LOGS ../'
        org_mv = 'mv BAMS STAR_OUT QC LOGS ../'
        call(org_mv, shell=True)
        os.chdir('../../')
        sys.stderr.write(date_time() + 'Uploading results for ' + self.sample + '\n')
        check = upload_to_swift(self.cont, self.obj)
        if (check != 0):
            sys.stderr.write(date_time() + 'Upload failure for ' + self.sample + '\n')
            self.status = 1
            exit(1)
        sys.stderr.write(date_time() + 'Pipeline complete for ' + self.sample + '\n')
        self.status = 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description='RNA alignment paired-end QC pipeline')
    parser.add_argument('-f1', '--file1', action='store', dest='end1', help='First fastq file')
    parser.add_argument('-f2', '--file2', action='store', dest='end2', help='Second fastq file')
    parser.add_argument('-j', '--json', action='store', dest='config_file',
                        help='JSON config file containing tool and reference locations')
    parser.add_argument('-m', '--mount', action='store', dest='ref_mnt',
                        help='Drive mount location.  Example would be /mnt/cinder/REFS_XXX')
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    inputs = parser.parse_args()

    end1 = inputs.end1
    end2 = inputs.end2
    config_file = inputs.config_file
    ref_mnt = inputs.ref_mnt
    Pipeline(end1, end2, config_file, ref_mnt)


if __name__ == "__main__":
    main()
