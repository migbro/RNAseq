#!/usr/bin/env python
import sys
import os
sys.path.append('/home/ubuntu/TOOLS/Scripts/alignment')
sys.path.append('/home/ubuntu/TOOLS/Scripts/utility')
from date_time import date_time
import subprocess
import json
from log import log
from job_manager import job_manager


def parse_config(json_config):
    config_data = json.loads(open(json_config, 'r').read())
    return config_data['tools']['java'], config_data['params']['ram'], config_data['tools']['picard'],\
           config_data['refs']['refFlat'], config_data['refs']['rRNA_intervals'], config_data['params']['strand'],\
           config_data['tools']['express'], config_data['refs']['express']


def qc_bam(sample, config_file, ref_mnt):
    job_list = []
    loc = sample + '.bam_qc.log'
    if os.path.isdir('LOGS'):
        loc = 'LOGS/' + loc
    (java, ram, picard, refFlat, intervals, strand, express, transcriptome) = parse_config(config_file)
    # for now setting default strand to NONE
    st_dict = {'N': 'NONE', 'fr-stranded': 'FIRST_READ_TRANSCRIPTION_STRAND',
               'rf-stranded': 'SECOND_READ_TRANSCRIPTION_STRAND'}

    refFlat = ref_mnt + '/' + refFlat
    intervals = ref_mnt + '/' + intervals
    transcriptome = ref_mnt + '/' + transcriptome
    picard_cmd = java + ' -Xmx' + ram + 'g ' + picard + ' CollectRnaSeqMetrics REF_FLAT=' + refFlat + ' STRAND=' \
                 + st_dict[strand] + ' CHART=' + sample + '.pos_v_cov.pdf I=' + sample + '.Aligned.out.bam O=' + sample\
                 + '.picard_RNAseq_qc.txt RIBOSOMAL_INTERVALS=' + intervals
    job_list.append(picard_cmd)
    log(loc, date_time() + picard_cmd + '\n')
    if strand == 'N':
        express_cmd = express + ' ' + transcriptome + ' ' + sample + '.Aligned.toTranscriptome.out.bam' \
                    ' --no-update-check -m ' + x + ' -s ' + s + ' --logtostderr 2>> ' + loc
    else:
        express_cmd = express + ' ' + transcriptome + ' ' + sample + '.Aligned.toTranscriptome.out.bam' \
                    ' --no-update-check --' + strand + ' -m ' + x + ' -s ' + s + ' --logtostderr 2>> ' + loc
    log(loc, date_time() + express_cmd + '\n')
    job_list.append(express_cmd)
    job_manager(job_list, '2')
    rename_express_out = 'mv results.xprs ' + sample + '.express_quantification.txt; mv params.xprs ' + sample\
                         + '.params.xprs'
    subprocess.call(rename_express_out, shell=True)
    log(loc, date_time() + 'Completed qc.  Renaming files\n')
    return 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Bam qc from STAR output')
    parser.add_argument('-sa', '--sample', action='store', dest='sample', help='Sample/project name prefix')
    parser.add_argument('-j', '--json', action='store', dest='config_file',
                        help='JSON config file containing tool and reference locations')
    parser.add_argument('-m', '--mount', action='store', dest='ref_mnt',
                        help='Drive mount location.  Example would be /mnt/cinder/REFS_XXX')
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    inputs = parser.parse_args()

    sample = inputs.sample
    config_file = inputs.config_file
    ref_mnt = inputs.ref_mnt
    qc_bam(sample, config_file, ref_mnt)


if __name__ == "__main__":
    main()
