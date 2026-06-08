"""
Processors Package
=================

Processor classes for each workflow stage.

This package provides:
- ProcessorBase: Abstract base class for all processors
- ProcessorResult: Standard result object
- WorkflowContext: Shared dependencies container
- BasecallerProcessor: Dorado basecalling
- DemuxProcessor: Dorado demultiplexing
- NanoTelProcessor: NanoTel telomere analysis
- AlignmentProcessor: Dorado alignment
- RAnalyzer: R analysis pipeline
"""

from .base import ProcessorBase, ProcessorResult, WorkflowContext
from .basecaller import BasecallerProcessor
from .demuxer import DemuxProcessor
from .aligner import AlignmentProcessor
from .nanotel import NanoTelProcessor
from .r_analyzer import RAnalyzer
from .bam_to_fastq import BamToFastqProcessor

__all__ = ['ProcessorBase', 'ProcessorResult', 'WorkflowContext',
           'BasecallerProcessor', 'DemuxProcessor', 'AlignmentProcessor',
           'NanoTelProcessor', 'RAnalyzer', 'BamToFastqProcessor']