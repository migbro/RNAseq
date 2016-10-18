#!/usr/bin/env python
import sys
sys.path.append('/home/ubuntu/TOOLS/Scripts/alignment')
sys.path.append('/home/ubuntu/TOOLS/Scripts/annotation')
sys.path.append('/home/ubuntu/TOOLS/Scripts/utility')
from date_time import date_time
from log import log
from job_manager import job_manager
from novosort_merge_pe import novosort_merge_pe
import subprocess
import json
from vep_annot_vcf import annot_gatk_haplotype


def parse_config(json_config):
    config_data = json.loads(open(json_config, 'r').read())
    try:
        return config_data['refs']['cont'], config_data['refs']['obj'], config_data['refs']['capture_flag'], \
               config_data['refs']['cap_bed'], config_data['tools']['bedtools'], config_data['tools']['samtools'], \
               config_data['tools']['java'], config_data['tools']['gatk'], config_data['params']['threads'], \
               config_data['refs']['samtools']
    except:
        try:
            sys.stderr.write(date_time() + 'Accessing keys failed.  Attempting to output current keys:\n')
            for key in config_data:
                sys.stderr.write(key + '\n')
                for subkey in config_data[key]:
                    sys.stderr.write(key + ":" + subkey + ":" + config_data[key][subkey] + '\n')
            exit(1)
        except:
            sys.stderr.write(date_time() + 'Could not read config file ' + json_config + '\n')
            exit(1)


def filter_bam(bedtools, cap_bed, sample_list, out_suffix, th):
    job_list = []
    for sample in sample_list:
        loc = sample + '.bedtools.intersect.log'
        bam = sample + out_suffix
        filt_cmd = bedtools + ' intersect -abam ' + bam + ' -b ' + cap_bed + ' -wa -header 2> ' + loc + ' > ' + bam \
                   + 'FILTERED; mv ' + bam + ' FILTERED ' + bam + ';'
        job_list.append(filt_cmd)
    check = job_manager(job_list, th)
    if check == 0:
        return 0
    else:
        sys.stderr.write(date_time() + 'Bam filtering by capture regions failed\n')
        return 1


def splitNtrim(java, gatk, sample_list, out_suffix, fasta, th):
    cmd_list = []
    for sample in sample_list:
        bam = sample_list + out_suffix
        loc = sample + '.gatk.SplitNCigarReads.log'
        split_cmd = java + ' -jar ' + gatk + ' -T SplitNCigarReads -R ' + fasta + ' -I ' + bam + ' -o ' + sample \
                    + '.merged.split.bam -rf ReassignOneMappingQuality -RMQF 255 -RMQT 60  -U ALLOW_N_CIGAR_READS 2> '\
                    + loc
        cmd_list.append(split_cmd)
    rflag = job_manager(cmd_list, th)
    if rflag == 0:
        return 0
    else:
        sys.stderr.write(date_time() + 'Split and trim failed for set\n')
        return 1


def base_recal(java, gatk, sample_list, th, fasta):
    for sample in sample_list:
        loc = sample + '.gatk.BaseRecalibrator.log'
        bam = sample + '.merged.split.bam'
        recal_cmd = java + ' -jar ' + gatk + ' -nct ' + th + ' -T BaseRecalibrator -I ' + bam + ' -o ' + sample \
                    + '_recal_data.table -R ' + fasta + ' 2> ' + loc
        log(loc, date_time() + recal_cmd + '\n')
        rflag = subprocess.call(recal_cmd, shell=True)
        if rflag != 0:
            sys.stderr.write(date_time() + 'Base recal failed for ' + sample + '\n')
            return 1
        loc = sample + '.gatk.PrintReads.log'
        new_bam_cmd = java + ' -jar ' + gatk + ' -nct ' + th + ' -T PrintReads -I ' + bam + ' -BQSR ' + sample \
                      + '_recal_data.table -o ' + sample + '.recalibrated.bam 2> ' + loc
        log(loc, date_time() + new_bam_cmd + '\n')
        rflag = subprocess.call(new_bam_cmd, shell=True)
        if rflag == 0:
            rm_old_bam = 'rm ' + bam
            subprocess.call(rm_old_bam, shell=True)
            return 0
        else:
            sys.stderr.write('Print recalibrated bam failed for sample ' + sample + '\n')
            return 1


def the_big_show(java, gatk, sample_list, th, fasta):
    filt_vcf_jobs = []
    for sample in sample_list:
        bam = sample + '.recalibrated.bam'
        loc = sample + '.gatk.HaplotypeCaller.log'
        haplo_cmd = java + ' -jar ' + gatk + ' -nct ' + th + ' -T HaplotypeCaller -I ' + bam + ' -R ' + fasta \
                    + ' -o ' + sample + '_haplo_calls.vcf -dontUseSoftClippedBases -stand_call_conf 20.0' \
                                        ' -stand_emit_conf 20.0 2> ' + loc
        log(loc, date_time() + haplo_cmd + '\n')
        rflag = subprocess.call(haplo_cmd, shell=True)
        if rflag != 0:
            log(loc, date_time() + 'Haplotype calls failed for ' + sample + '\n')
            return 1
        loc = sample + '.gatk.VariantFiltration.log'
        filt_vcf_cmd = java + ' -jar ' + gatk + ' -nct ' + th + ' -T VariantFiltration -R ' + fasta + ' -V ' + sample\
                       + '_haplo_calls.vcf  -window 35 -cluster 3 -filterName FS -filter "FS > 30.0" -filterName QD ' \
                         '-filter "QD < 2.0" -o ' + sample + '.haplo_filtered.vcf 2> ' + loc
        filt_vcf_jobs.append(filt_vcf_cmd)
    rflag = job_manager(filt_vcf_jobs, th)
    sys.stderr.write(date_time() + 'Filtering variants\n')
    if rflag != 0:
        sys.stderr.write(date_time() + 'Variant filtering jobs failed\n')
        return 1
    else:
        return 0


def create_somatic_vcf(bedtools, pairs, th):
    intersect_jobs = []
    for pair in pairs:
        cur = pair.split('_')
        loc = pair + '.bedtools.intersect.log'
        bed_int = bedtools + ' intersect -a ' + cur[0] + ' -b ' + cur[1] + ' -wa -header -sorted > ' + pair \
                  + '.haplo_somatic.vcf 2> ' + loc
        intersect_jobs.append(bed_int)
    rflag = job_manager(intersect_jobs, th)
    if rflag != 0:
        sys.stderr.write(date_time() + 'Somatic vcf by intersect failed\n')
    else:
        return 0


def gatk_call(sample_pairs, config_file, ref_mnt):
    mk_dir = 'mkdir BAMS LOGS ANALYSIS ANNOTATION REPORTS'
    subprocess.call(mk_dir, shell=True)
    (cont, obj, cflag, cap_bed, bedtools, samtools, java, gatk, th, fasta) = parse_config(config_file)
    cap_bed = ref_mnt + '/' + cap_bed
    fasta = ref_mnt + '/' + fasta

    sample_list = 'sample_list.txt'
    slist = []
    pairs = []
    fh = open(sample_pairs, 'r')
    sl = open(sample_list, 'w')
    temp = {}
    for line in fh:
        cur = line.rstrip('\n').split('\t')
        pairs.append(cur[0])
        if cur[1] not in temp:
            sl.write(cur[1] + '\n')
            temp[cur[1]] = 1
            slist.append(cur[1])
        if cur[2] not in temp:
            sl.write(cur[2] + '\n')
            temp[cur[2]] = 1
            slist.append(cur[2])
    sl.close()
    fh .close()
    del temp
    in_suffix = '.Aligned.sortedByCoord.out.bam'
    out_suffix = '.merged.sortedByCoord.bam'
    sort_type = 'coordinate'
    check = novosort_merge_pe(sample_list, config_file, in_suffix, out_suffix, sort_type)
    if check == 0:
        sys.stderr.write(date_time() + 'File download and merge complete!\n')
        # rm unmerged bams, no longer needed
        rm_bam = 'rm -rf ' + obj
        subprocess.call(rm_bam, shell=True)
    else:
        sys.stderr.write(date_time() + 'File download and merge failed!\n')
        exit(1)

    if cflag == 'Y':
        sys.stderr.write(date_time() + 'Capture flag detected.  Filtering bams by capture regions\n')
        rflag = filter_bam(bedtools, cap_bed, slist, out_suffix, th)
        if rflag != 0:
            sys.stderr.write(date_time() + 'Filter bam failed!\n')
            exit(1)
        else:
            sys.stderr.write(date_time() + 'Filtering complete\n')
    check = splitNtrim(java, gatk, slist, out_suffix, fasta, th)
    if check != 0:
        sys.stderr.write(date_time() + 'Split n trim failed\n')
        exit(1)

    check = base_recal(java, gatk, slist, th, fasta)
    if check != 0:
        sys.stderr.write(date_time() + 'Base recal failed\n')
    check = the_big_show(java, gatk, sample_list, th, fasta)
    if check != 0:
        sys.stderr.write(date_time() + 'Haplotype calls failed\n')
    check = create_somatic_vcf(bedtools, pairs, th)
    if check != 0:
        sys.stderr.write(date_time() + 'somatic vcf creation failed\n')
    check = annot_gatk_haplotype(config_file, sample_pairs, ref_mnt)
    if check != 0:
        sys.stderr.write(date_time() + 'VEP annotation of vcf failed\n')
    mv_files = 'mv *.bam *.bai BAMS; mv *.log LOGS; mv *vep* ANNOTATION; mv *.vcf ANALYSIS; mv *.xls REPORTS'
    subprocess.call(mv_files, shell=True)
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Use GATK haplotype caller best practices for mutation calls')
    parser.add_argument('-sp', '--pairs', action='store', dest='pairs', help='Sample piars')
    parser.add_argument('-j', '--json', action='store', dest='config_file',
                        help='JSON config file containing tool and reference locations')
    parser.add_argument('-m', '--mount', action='store', dest='ref_mnt',
                        help='Drive mount location.  Example would be /mnt/cinder/REFS_XXX')

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    inputs = parser.parse_args()

    pairs = inputs.pairs
    config_file = inputs.config_file
    ref_mnt = inputs.ref_mnt

    gatk_call(pairs, config_file, ref_mnt)