#!/usr/bin/env python3
import sys
sys.path.append('/cephfs/users/mbrown/PIPELINES/RNAseq/')
import json
from utility.job_manager import job_manager
import subprocess


def parse_config(config_file):
    config_data = json.loads(open(config_file, 'r').read())
    return config_data['refs']['project'], config_data['refs']['align_dir']


def qc_bam_pipe(sample_list, config_file, ref_mnt):
    (cont, obj) = parse_config(config_file)
    job_list = []
    log_dir = 'LOGS/'
    src_cmd = '. ~/.novarc;'
    create_start_dirs = 'mkdir LOGS QC'
    subprocess.call(create_start_dirs, shell=True)
    for sample in open(sample_list):
        sample = sample.rstrip('\n')
        parts = sample.split('_')
        bam = sample + '.Aligned.sortedByCoord.out.bam'
        dl_list = (log_dir + sample + '.cutadapt.log', log_dir + sample + '.Log.final.out', 'QC/' + sample
                   + '_subset.insert_metrics.hist', 'QC/' + sample + '_1_sequence_fastqc/fastqc_data.txt', 'BAMS/'
                   + bam)
        dl_cmd = src_cmd
        prefix = obj + '/' + parts[0] + '/'
        for fn in dl_list:
            dl_cmd += 'swift download ' + cont + ' ' + prefix + fn + ';'
        mv_cmd = 'mv ' + prefix + dl_list[2] + ' .;mv ' + prefix + dl_list[4] + ' .;mv ' + prefix + dl_list[0] \
                 + ' LOGS/;mv ' + prefix + dl_list[1] + ' LOGS;mv ' + prefix + 'QC/' + sample + '* QC/;'
        qc_cmd = '~/TOOLS/Scripts/alignment/qc_bam.py -sa ' + sample + ' -j ' + config_file + ' -m ' + ref_mnt + ';'
        rm_cmd = 'rm ' + bam + ';'
        parse_qc_cmd = '~/TOOLS/Scripts/alignment/parse_qc.py -j ' + config_file + ' -sa ' + sample + ';'
        full_cmd = dl_cmd + mv_cmd + qc_cmd + rm_cmd + parse_qc_cmd
        job_list.append(full_cmd)
    job_manager(job_list, 4)



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
    qc_bam_pipe(sample, config_file, ref_mnt)


if __name__ == "__main__":
    main()
