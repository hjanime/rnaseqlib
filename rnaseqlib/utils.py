##
## Utilities
##
import os
import sys
import time

from os.path import basename
from urlparse import urlsplit

import itertools
import logging

def get_logger(logger_name, log_outdir,
               level=logging.INFO,
               include_stdout=True):
    """
    Return a logging object.
    """
    logger = logging.getLogger(logger_name)
    formatter = \
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                          datefmt='%m/%d/%Y %I:%M:%S %p')
    log_filename = os.path.join(log_outdir, "%s.log" %(logger_name))
    fh = logging.FileHandler(log_filename)
    fh.setLevel(level)
    fh.setFormatter(formatter)    
    logger.addHandler(fh)
    logging.root.setLevel(level)
    # Optionally add handler that streams all logs
    # to stdout
    if include_stdout:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    logger.info("Created logger %s" %(logger_name))
    return logger


def make_dir(dirpath):
    if os.path.isfile(dirpath):
        print "Error: %s is a file!" %(dirpath)
        sys.exit(1)
    # Try to make the directory
    try:
        os.makedirs(dirpath)
    except OSError:
        pass

    
def gunzip_file(filename, output_dir,
                ext=".txt",
                force=True,
                unless_exists=True):
    """
    Unzip the file into the given output directory.

    If file ends with .gz, strip the .gz. Otherwise,
    add a .txt at the end.
    """
    print "Unzipping: %s into directory %s" %(filename,
                                              output_dir)
    if filename.endswith(".gz"):
        unzipped_filename = filename[0:-3]
    else:
        unzipped_filename = "%s.%s" %(filename,
                                      ext)
    print "  - Unzipped filename: %s" %(unzipped_filename)
    if unless_exists and os.path.isfile(unzipped_filename):
        print "  - File exists, skipping.."
        return unzipped_filename
    os.chdir(output_dir)
    gunzip = "gunzip "
    if force:
        gunzip += "--force"
    os.system("%s %s > %s" %(gunzip,
                             filename,
                             unzipped_filename))
    return unzipped_filename
    
    
def pathify(filename):
    return os.path.abspath(os.path.expanduser(filename))


def url2name(url):
    return basename(urlsplit(url)[2])


def which(program):
    """
    Check if program exists on path.
    """
    def is_exe(fpath):
        if not os.path.isfile(fpath):
            return False
        elif not os.access(fpath, os.X_OK):
            # If the file exists but is not executable, warn
            # the user
            print "WARNING: Found %s but it is not executable." %(fpath)
            print "Please ensure %s is executable." %(fpath)
            print "On Unix, use something like: "
            print "  chmod +x %s" %(fpath)
            time.sleep(10)
            return False
        return True
    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None
            

def count_lines(fname, skipstart="#"):
    """
    Return number of lines in file.

    Skip liens starting with 'skipstart'.
    """
    num_lines = 0
    for line in open(fname):
        if line.startswith(skipstart): continue
        num_lines += 1
    return num_lines

##
## Misc. utilities for manipulating strings/lists
##
def iter_by_pair(l, step=2):
    """
    Return an iterator over pairs in the list 'l'.

    'step' determines the number of elements to advance
    the pair iterator by.
    """
    return itertools.izip(l, l[1::step])


def unique_list(l):
    """
    Return unique list, with consistent ordering.
    """
    seen = {}
    uniq_l = []
    for elt in l:
        if elt in seen: continue
        uniq_l.append(elt)
        seen[elt] = True
    return uniq_l


def get_pairwise_from_sets(first_samples, second_samples):
    seen_pairs = []
    for sample_pair in itertools.product(first_samples,
                                         second_samples):
        sample1, sample2 = sample_pair
        if (sample_pair in seen_pairs) or (sample1 == sample2) or \
            ((sample2, sample1) in seen_pairs):
            continue
        seen_pairs.append(sample_pair)
    return seen_pairs
    
        
def get_pairwise_comparisons(samples):
    """
    Return pairwise comparisons between samples.
    """
    return get_pairwise_from_sets(samples, samples)


def abs_fold_change(fold_changes):
    """
    Get the absolute fold change.
    """
    abs_fc = map(lambda v: \
                 1/float(v) if v <= 1 else v,
                 fold_changes)
    return abs_fc
    

def pathify(filename):
    return os.path.abspath(os.path.expanduser(filename))





    



