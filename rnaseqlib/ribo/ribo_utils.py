##
## Utilities for Ribo-Seq data
##
import os
import sys
import time

import rnaseqlib
import rnaseqlib.utils as utils
import rnaseqlib.fastq_utils as fastq_utils

import scipy
from scipy.stats.stats import zscore

from numpy import *

def rstrip_stretch(s, letter):
    """
    Strip (from right) consecutive stretch of letters.
    """
    stripped_s = ""
    first = True
    for l in s[::-1]:
        if first:
            if l == letter:
                continue
            else:
                stripped_s += l
                first = False
        else:
            stripped_s += l
    return stripped_s[::-1]

def compute_te(ribo_rpkms, rna_rpkms,
               na_val=NaN):
    """
    Calculate translational efficiency (TE), i.e.

      ribo_rpkm / rna_rpkms

    Takes lists/vectors as input.

    If rna_rpkm is 0 then TE is undefined.

    - ribo_rpkms: ribo-seq RPKMs
    - rna_rpkms: rna-seq RPKMs
    - na_val: NA value to use
    """
    if len(ribo_rpkms) != len(rna_rpkms):
        raise Exception, "Error: compute_te requires same length " \
                         "vectors as input."
    te = []
    for ribo, rna in zip(ribo_rpkms, rna_rpkms):
        te_val = na_val
        if rna != 0:
            # If the RNA is detectable, define
            # the TE
            if ribo == 0:
                te_val = 0
            else:
                te_val = ribo / float(rna)
        te.append(te_val)
    return te
    

def trim_polyA_ends(fastq_filename,
                    output_dir,
                    compressed=False,
                    min_polyA_len=3,
                    min_read_len=22):
    """
    Trim polyA ends from reads.
    """
    print "Trimming polyA trails from: %s" %(fastq_filename)
    # Strip the trailing extension
    output_basename = ".".join(os.path.basename(fastq_filename).split(".")[0:-1])
    output_basename = "%s.trimmed_polyA.fastq.gz" %(output_basename)
    output_filename = os.path.join(output_dir, output_basename)
    utils.make_dir(output_dir)
    if os.path.isfile(output_filename):
        print "SKIPPING: %s already exists!" %(output_filename)
        return output_filename
    print "  - Outputting trimmed sequences to: %s" %(output_filename)
    input_file = fastq_utils.read_open_fastq(fastq_filename)
    output_file = fastq_utils.write_open_fastq(output_filename)
    t1 = time.time()
    for line in fastq_utils.read_fastq(input_file):
        header, seq, header2, qual = line
        if seq.endswith("A"):
            # Skip sequences that do not end with at least N
            # many As
            if seq[-min_polyA_len:] != ("A" * min_polyA_len):
                continue
            # Get sequence stripped of contiguous strech of polyAs
            stripped_seq = rstrip_stretch(seq, "A")
            if len(stripped_seq) < min_read_len:
                # Skip altogether reads that are shorter than
                # the required length after trimming
                continue
            # Strip the quality scores to match trimmed sequence
            new_qual = qual[0:len(stripped_seq)]
            new_rec = (header, stripped_seq, header2, new_qual)
            # Write the record with trimmed sequence back out to file
            fastq_utils.write_fastq(output_file, new_rec)
    t2 = time.time()
    print "Trimming took %.2f mins." %((t2 - t1)/60.)
    output_file.close()
    return output_filename
            

def compute_read_len_dist():
    """
    Compute distribution of read lengths.
    """
    pass


if __name__ == "__main__":
    test_file = "/home/yarden/jaen/test_ribo.fastq"
    trim_polyA_ends(test_file, "/home/yarden/jaen/test_polyA/")
    
