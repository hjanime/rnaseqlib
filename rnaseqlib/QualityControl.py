import os
import sys
import time

import logging

import csv

import rnaseqlib
import rnaseqlib.fastq_utils as fastq_utils
import rnaseqlib.mapping.bedtools_utils as bedtools_utils
import rnaseqlib.utils as utils

import pandas
import pysam

from collections import defaultdict


class QualityControl:
    """ 
    Quality control object. Defined for
    RNA-Seq sample.
    """
    def __init__(self, sample, pipeline):
        # Pipeline instance that the sample is attached to
        self.pipeline = pipeline
        self.sample = sample
        self.settings_info = pipeline.settings_info
        # Define logger
        self.logger = utils.get_logger("QualityControl.%s" %(sample.label),
                                       self.pipeline.pipeline_outdirs["logs"])
        # QC header: order of QC fields to be outputted
        self.regions_header = ["num_ribo",
                               "num_exons",
                               "num_cds",
                               "num_introns",
                               "num_3p_utr",
                               "num_5p_utr"]
        self.qc_stats_header = ["percent_mapped",
                                "percent_ribo",
                                "percent_exons",
                                "percent_cds",     
                                "percent_introns"]
        self.qc_header = ["num_reads", 
                          "num_mapped",
                          "num_unique_mapped"] + self.qc_stats_header + self.regions_header
        # QC results
        self.na_val = "NA"
        self.qc_results = defaultdict(lambda: self.na_val)
        # QC output dir
        self.qc_outdir = self.pipeline.pipeline_outdirs["qc"]
        # QC filename for this sample
        self.sample_outdir = os.path.join(self.qc_outdir,
                                          self.sample.label)
        utils.make_dir(self.sample_outdir)
        # Regions output dir
        self.regions_outdir = os.path.join(self.sample_outdir, "regions")
        utils.make_dir(self.regions_outdir)
        self.qc_filename = os.path.join(self.sample_outdir,
                                        "%s.qc.txt" %(self.sample.label))
        self.qc_loaded = False
        # use ensGene gene table for QC computations
        self.gene_table = self.pipeline.rna_base.gene_tables["ensGene"]
        # Load QC information if file corresponding to sample already exists
        self.load_qc_from_file()


    def load_qc_from_file(self):
        """
        Load QC data from file if already present.
        """
        self.logger.info("Attempting to load QC from file...")
        if os.path.isfile(self.qc_filename):
            self.logger.info("Loaded: %s" %(self.qc_filename))
            qc_in = csv.DictReader(open(self.qc_filename, "r"),
                                   delimiter="\t")
            # Load existing header
            self.qc_header = qc_in.fieldnames
            # Load QC field values
            self.qc_results = qc_in.next()
            self.qc_loaded = True
            

    def get_num_reads(self):
        """
        Return number of reads in FASTQ file.

        For single-end samples, returns a single number.

        For paired-end samples, return a comma-separated
        pair of numbers: 'num_left_mate,num_right_mate'
        """
        self.logger.info("Getting number of reads.")
        if self.sample.paired:
            self.logger.info("Getting number of paired-end reads.")
            # Paired-end
            mate_reads = []
            for mate_rawdata in self.sample.rawdata:
                num_reads = 0
                fastq_entries = \
                    fastq_utils.get_fastq_entries(mate_rawdata.reads_filename)
                for entry in fastq_entries:
                    num_reads += 1
                mate_reads.append(num_reads)
            pair_num_reads = ",".join(map(str, mate_reads))
            return pair_num_reads
        else:
            self.logger.info("Getting number of single-end reads.")
            num_reads = 0
            # Single-end
            fastq_entries = \
                fastq_utils.get_fastq_entries(self.sample.rawdata.reads_filename)
            for entry in fastq_entries:
                num_reads += 1
            return num_reads

            
    def get_num_mapped(self):
        """
        Get number of mapped reads, not counting duplicates, i.e.
        reads that have alignments in the BAM file.
        """
        self.logger.info("Getting number of mapped reads.")        
        num_mapped = count_nondup_reads(self.sample.bam_filename)
        return num_mapped


    def get_num_unique_mapped(self):
        self.logger.info("Getting number of unique reads.")
        num_unique_mapped = \
            count_nondup_reads(self.sample.unique_bam_filename)
        return num_unique_mapped
    

    def get_exon_intergenic_ratio(self):
        self.logger.info("Getting exon intergenic ratio.")
        return 0
    

    def get_exon_intron_ratio(self):
        pass
    

    def get_num_ribo(self, chr_ribo="chrRibo"):
        """
        Compute the number of ribosomal mapping reads per
        sample.

        - chr_ribo denotes the name of the ribosome containing
          chromosome.
        """
        self.logger.info("Getting number of ribosomal reads..")
        bamfile = pysam.Samfile(self.sample.bam_filename, "rb")
        # Retrieve all reads on the ribo chromosome
        ribo_reads = bamfile.fetch(reference=chr_ribo,
                                   start=None,
                                   end=None)
        # Count reads (fetch returns an iterator)
        # Do not count duplicates
        num_ribo = count_nondup_reads(ribo_reads)
        return num_ribo


    def get_qc(self):
        return self.qc_results
    

    def get_num_exons(self):
        """
        Return number of reads mapping to exons.
        """
        self.logger.info("Getting number of exonic reads..")
        merged_exons_filename = os.path.join(self.gene_table.exons_dir,
                                             "ensGene.merged_exons.bed")
        output_basename = "region.merged_exons.bed"
        merged_exons_map_fname = os.path.join(self.regions_outdir,
                                              output_basename)
        num_exons_reads = 0
        result = \
            bedtools_utils.count_reads_matching_intervals(self.sample.ribosub_bam_filename,
                                                          merged_exons_filename,
                                                          merged_exons_map_fname)
        if result is None:
            self.logger.warning("Mapping to exons failed.")
        else:
            self.logger.info("Found bedtools output file for exons.")
            num_exons_reads = result
        return num_exons_reads

    
    def get_num_introns(self):
        """
        Return number of reads mapping to introns.
        """
        self.logger.info("Getting number of intronic reads..")
        introns_filename = os.path.join(self.gene_table.introns_dir,
                                        "ensGene.introns.bed")
        self.logger.info("Reading: %s" %(introns_filename))
        output_basename = "region.introns.bed"
        introns_map_fname = os.path.join(self.regions_outdir,
                                         output_basename)
        num_introns_reads = 0
        result = \
            bedtools_utils.count_reads_matching_intervals(self.sample.ribosub_bam_filename,
                                                          introns_filename,
                                                          introns_map_fname)
        if result is None:
            self.logger.warning("Mapping to introns failed.")
            return num_introns_reads
        else:
            self.logger.info("Found bedtools output file for introns.")
            num_introns_reads = result
        return num_introns_reads 


    def get_num_3p_utrs(self):
        """
        Return number of reads mapping to 3' UTRs.
        """
        self.logger.info("Getting number of 3\' UTRs reads..")
        return 0

    
    def get_num_5p_utrs(self):
        """
        Return number of reads mapping to 5' UTRs.
        """
        self.logger.info("Getting number of 5\' UTRs reads..")
        return 0
    

    def get_num_cds(self):
        """
        Return number of reads mapping to CDS regions.
        """
        self.logger.info("Getting number of CDS reads..")
        return 0

    
    def compute_regions(self):
        """
        Compute number of reads mapping to various regions.
        """
        self.logger.info("Computing reads in regions..")
        # Dictionary mapping regions to number of reads mapping
        # to them
        self.region_funcs = [("num_ribo", self.get_num_ribo),
                             ("num_exons", self.get_num_exons),
                             ("num_cds", self.get_num_cds),
                             ("num_introns", self.get_num_introns),
                             ("num_3p_utr", self.get_num_3p_utrs),
                             ("num_5p_utr", self.get_num_5p_utrs)]
        # Get the number of reads in each region and add these
        # to QC results
        for region_name, region_func in self.region_funcs:
            self.qc_results[region_name] = region_func()
        

    def compute_basic_qc(self):
        """
        Compute basic QC stats like number of reads mapped.
        """
        self.qc_results["num_reads"] = self.get_num_reads()
        self.qc_results["num_mapped"] = self.get_num_mapped()
        self.qc_results["num_unique_mapped"] = self.get_num_unique_mapped()


    def get_percent_mapped(self):
        percent_mapped = 0
        if self.qc_results["num_mapped"] == self.na_val:
            return percent_mapped
        if self.sample.paired:
            # For paired-end samples, divide the number of mapped
            # reads by the smaller of the two numbers of left mate
            # and right mates
            pair_denom = min(map(int,
                                 self.qc_results["num_reads"].split(",")))
            percent_mapped = \
                self.qc_results["num_mapped"] / pair_denom
        else:
            percent_mapped = \
                self.qc_results["num_mapped"] / self.qc_results["num_reads"]
        return percent_mapped


    def get_percent_unique(self):
        percent_unique = 0
        if self.qc_results["num_unique_mapped"] == self.na_val:
            return percent_unique
        percent_unique = \
            self.qc_results["num_unique_mapped"] / self.qc_results["num_mapped"]
        return percent_unique

    
    def get_percent_ribo(self):
        percent_ribo = 0
        if self.qc_results["num_ribo"] == self.na_val:
            return percent_ribo
        percent_ribo = \
            self.qc_results["num_ribo"] / self.qc_results["num_mapped"]
        return 0

    
    def get_percent_exons(self):
        percent_exons = 0
        if self.qc_results["num_exons"] == self.na_val:
            return percent_exons
        percent_exons = \
            float(self.qc_results["num_exons"]) / self.qc_results["num_mapped"]
        return percent_exons


    def get_percent_introns(self):
        percent_introns = 0
        if self.qc_results["num_introns"] == self.na_val:
            return percent_introns
        percent_introns = \
            float(self.qc_results["num_introns"]) / self.qc_results["num_mapped"]
        return percent_introns


    def get_percent_cds(self):
        percent_cds = 0
        if self.qc_results["num_cds"] == self.na_val:
            return percent_cds
        percent_cds = \
                float(self.qc_results["num_cds"]) / self.qc_results["num_mapped"]
        return percent_cds


    def compute_qc_stats(self):
        """
        Compute various statistics from the QC numbers we have.
        """
        # Check that the number of reads mapped is non-zero
        if (self.qc_results["num_mapped"] == self.na_val) or \
           (self.qc_results["num_mapped"] == 0):
            self.logger.critical("Cannot compute QC stats since number of reads "
                                 "mapped is not available!")
            self.logger.critical("num_mapped = %s" \
                                 %(str(self.qc_results["num_mapped"])))
            sys.exit(1)
        self.qc_stat_funcs = [("percent_unique", self.get_percent_unique),
                              ("percent_mapped", self.get_percent_mapped),
                              ("percent_ribo", self.get_percent_ribo),
                              ("percent_exons", self.get_percent_exons),
                              ("percent_introns", self.get_percent_introns),
                              ("percent_cds", self.get_percent_cds)]
        for stat_name, stat_func in self.qc_stat_funcs:
            self.qc_results[stat_name] = stat_func()
        

    def compute_qc(self):
        """
        Compute all QC metrics for sample.
        """
        self.logger.info("Computing QC for sample: %s" %(self.sample.label))
        # BAM-related statistics
        # First check that BAM file is present
        if (self.sample.bam_filename is None) or \
           (not os.path.isfile(self.sample.bam_filename)):
            print "WARNING: Cannot find BAM filename for %s" %(self.sample.label)
        else:
            # Basic QC stats
            self.compute_basic_qc()
            # Number of reads in various regions
            self.compute_regions()
            # Compute statistics from these results
            self.compute_qc_stats()
        # Set that QC results were loaded
        self.qc_loaded = True
        return self.qc_results
        
        
    def output_qc(self):
        """
        Output QC metrics for sample.
        """
        if os.path.isfile(self.qc_filename):
            print "SKIPPING %s, since %s already exists..." %(self.sample.label,
                                                              self.qc_filename)
            return None
        # Header for QC output file for sample
        qc_df = pandas.DataFrame([self.qc_results])
        # Write QC information as csv
        qc_df.to_csv(self.qc_filename,
                     cols=self.qc_header,
                     sep="\t",
                     index=False)
        

    def get_seq_cycle_profile(self, fastq_filename,
                              first_n_seqs=None):#sample):
        """
        Compute the average 'N' bases (unable to sequence)
        as a function of the position of the read.
        """
        fastq_file = fastq_utils.read_open_fastq(fastq_filename)
        fastq_entries = fastq_utils.read_fastq(fastq_file)
        # Mapping from position in read to number of Ns
        num_n_bases = defaultdict(int)
        # Mapping from position in read to total number of
        # reads in that position
        num_reads = defaultdict(int)
        num_entries = 0
        print "Computing sequence cycle profile for: %s" %(fastq_filename)
        if first_n_seqs != None:
            print "Looking at first %d sequences only" %(first_n_seqs)
        for entry in fastq_entries:
            if first_n_seqs != None:
                # Stop at requested number of entries if asked to
                if num_entries >= first_n_seqs:
                    break
            header1, seq, header2, qual = entry
            seq_len = len(seq)
            for n in range(seq_len):
                if seq[n] == "N":
                    # Record occurrences of N
                    num_n_bases[n] += 1
                num_reads[n] += 1
            num_entries += 1
        # Compute percentage of N along each position
        percent_n = []
        for base_pos in range(max(num_reads.keys())):
            curr_percent_n = float(num_n_bases[base_pos]) / num_reads[base_pos]
            percent_n.append(curr_percent_n)
        return percent_n

        
class QCStats:
    """
    Represntation of QC stats for a set of samples.
    """
    def __init__(self, samples, qc_header, qc_objects,
                 sample_header="sample"):
        self.samples = samples
        self.sample_header = sample_header
        self.qc_objects = qc_objects
        self.qc_stats = None
        self.qc_header = qc_header


    def output_qc(self, output_filename):
        """
        Output QC to file.
        """
        print "Outputting QC information for all samples..."
        self.compile_qc(self.samples)
        self.to_csv(output_filename)


    def compile_qc(self):
        """
        Combined the QC output of a given set of samples
        into one object.
        """
        if len(self.samples) == 0:
            print "Error: No samples given to compile QC from!"
            sys.exit(1)
        qc_entries = []
        for sample in self.samples:
            # Copy sample's QC results
            sample_qc_results = self.qc_objects[sample.label].qc_results
            qc_entry = sample_qc_results.copy()
            # Record sample name
            qc_entry[self.sample_header] = sample.label
            qc_entries.append(qc_entry)
        self.qc_stats = pandas.DataFrame(qc_entries)
        return self.qc_stats
    

    def to_csv(self, output_filename):
        # Fetch QC header of first sample. Add to its
        # beginning a field for the sample name
        output_header = [self.sample_header] + self.qc_header
        for col in output_header:
            if col not in self.qc_stats.columns:
                print "WARNING: Could not find column %s in QC stats. " \
                      "Something probably went wrong in a previous " \
                      "step. Were your BAMs created successfully?" \
                      %(col)
        self.qc_stats.to_csv(output_filename,
                             sep="\t",
                             index=False,
                             cols=output_header)

##
## Misc. QC functions
##
def count_nondup_reads(bam_in):
    """
    Return number of BAM reads that appear in the file, excluding
    duplicates (i.e. only count unique read ids/QNAMEs.)

    Takes a filename or a stream.
    """
    bam_reads = bam_in
    if isinstance(bam_in, basestring):
        # We're passed a filename
        if not os.path.isfile(bam_in):
            print "WARNING: Could not find BAM file %s" %(bam_in)
            return 0
        else:
            bam_reads = pysam.Samfile(bam_in, "rb")
    bam_reads_ids = {}
    for read in bam_reads:
        bam_reads_ids[read.qname] = True
    num_reads = len(bam_reads_ids.keys())
    return num_reads
