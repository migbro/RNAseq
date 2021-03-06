#!/usr/bin/env python3
import sys


def filter_bam(index):
    # track entries and number of entries in list
    rct = 0
    fct = 0
    tx = {}
    for line in open(index, 'r'):
        if line[0] != '#' and line[0] != '\n':
            line = line.rstrip('\n')
            tx[line] = 1
    for line in sys.stdin:
        if line[0] == '@':
            sys.stdout.write(line)
            continue
        rct += 1
        info = line.rstrip('\n').split('\t')
        tx_id = info[2].split('.')
        if tx_id[0] in tx:
            fct += 1
            sys.stdout.write(line)
    sys.stderr.write(str(fct) + ' entries out of ' + str(rct) + ' kept.\n')


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Helper script to filter transcriptome bam by transcript.  '
                                                 'Pipe in sam input.  Intended for ENSEMBL input')
    parser.add_argument('-i', '--index', action='store', dest='index', help='Transcript list')
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    inputs = parser.parse_args()

    index = inputs.index
    filter_bam(index)
