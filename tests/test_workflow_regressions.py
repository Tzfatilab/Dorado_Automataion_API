import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dorado_workflow.main import cmd_fastq_workflow
from dorado_workflow.operators.workflow_operator import WorkflowOperator
from dorado_workflow.processors.aligner import AlignmentProcessor
from dorado_workflow.processors.base import ProcessorResult
from dorado_workflow.utils.command_executor import CommandExecutor
from dorado_workflow.utils.cancellation import WorkflowCancelled
from dorado_workflow.utils.logger import WorkflowLogger
from dorado_workflow.processors.nanotel import NanoTelProcessor


class WorkflowRegressionTests(unittest.TestCase):
    def test_nanotel_cancellation_stops_barcodes_without_errors(self):
        processor = NanoTelProcessor.__new__(NanoTelProcessor)
        processor.context = SimpleNamespace(logger=Mock(), barcode_manager=Mock(),
                                            command_executor=Mock())
        processor.validate_inputs = Mock(return_value=True)
        processor._create_barcode_tasks = Mock(return_value=[
            {'barcode': barcode, 'fastq_count': 1} for barcode in ('barcode02', 'barcode19')
        ])
        processor._build_command = Mock(return_value='unused')
        processor.context.command_executor.execute.side_effect = WorkflowCancelled()
        with self.assertRaises(WorkflowCancelled):
            processor.execute('unused')
        processor._build_command.assert_called_once()
        processor.context.barcode_manager.register_failure.assert_not_called()
        processor.context.logger.error.assert_not_called()
        processor.context.logger.warning.assert_not_called()
        messages = str(processor.context.logger.info.call_args_list)
        self.assertNotIn('barcode19', messages)

    def test_real_nanotel_errors_are_still_reported(self):
        processor = NanoTelProcessor.__new__(NanoTelProcessor)
        processor.context = SimpleNamespace(logger=Mock(), barcode_manager=Mock(),
                                            command_executor=Mock())
        processor._build_command = Mock(return_value='unused')
        processor.context.command_executor.execute.side_effect = RuntimeError('R failed')
        result = processor._process_barcodes_sequential([{'barcode': 'barcode02', 'fastq_count': 1}])
        self.assertEqual(result, {'barcode02': False})
        processor.context.logger.error.assert_called_once()
        processor.context.barcode_manager.register_failure.assert_called_once()

    def test_cancelled_command_has_cancelled_history_without_error(self):
        logger = WorkflowLogger.__new__(WorkflowLogger)
        logger.command_lock = threading.Lock()
        logger.executed_commands = []
        logger.info = Mock()
        logger.error = Mock()
        logger.debug = Mock()
        executor = CommandExecutor(logger)
        with patch.object(executor, 'popen', side_effect=WorkflowCancelled()):
            with self.assertRaises(WorkflowCancelled):
                executor.execute('unused', stream_output=True)
        self.assertEqual(logger.executed_commands[0]['status'], 'cancelled')
        logger.error.assert_not_called()

    def test_fastq_cli_dispatches_to_existing_workflow(self):
        args = SimpleNamespace(trial_name='trial', output_dir='out', config=None,
                               organism='mouse', input='fastqs')
        operator = Mock(spec=WorkflowOperator)
        with patch('dorado_workflow.main.setup_context'), patch(
                'dorado_workflow.main.WorkflowOperator', return_value=operator):
            for success, expected in [(True, 0), (False, 1)]:
                operator.run_nanotel_workflow.return_value = success
                self.assertEqual(cmd_fastq_workflow(args), expected)
        operator.run_nanotel_workflow.assert_called_with(
            path_input='fastqs', organism='mouse', run_mapping=True)

    def test_cancel_between_stages_prevents_next_processor(self):
        executor = CommandExecutor(Mock())
        cancelled = threading.Event()
        executor.stop_callback = cancelled.is_set
        operator = WorkflowOperator.__new__(WorkflowOperator)
        operator.context = SimpleNamespace(command_executor=executor, logger=Mock())
        operator.results = {}
        first = Mock()
        first.execute.side_effect = lambda: (cancelled.set() or ProcessorResult(True))
        with self.assertRaisesRegex(RuntimeError, 'Cancelled by user'):
            operator._run_step('first', 'first', first)
        second = Mock()
        with self.assertRaisesRegex(RuntimeError, 'Cancelled by user'):
            operator._run_step('second', 'second', second)
        second.execute.assert_not_called()

    def test_cancel_silent_commands_and_children(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            child = folder / 'child.py'
            child.write_text('import time, pathlib, sys\ntime.sleep(2)\n'
                             'pathlib.Path(sys.argv[1]).write_text("survived")\n')
            parent = folder / 'parent.py'
            parent.write_text('import subprocess, sys, time\n'
                              'subprocess.Popen([sys.executable, sys.argv[1], sys.argv[2]])\n'
                              'time.sleep(30)\n')
            for mode in ('stream', 'capture', 'plain', 'direct'):
                with self.subTest(mode=mode):
                    marker = folder / mode
                    executor = CommandExecutor(Mock())
                    stopped = threading.Event()
                    executor.stop_callback = stopped.is_set
                    args = [sys.executable, str(parent), str(child), str(marker)]
                    command = subprocess.list2cmdline(args) if os.name == 'nt' else __import__('shlex').join(args)
                    timer = threading.Timer(0.5, stopped.set)
                    timer.start()
                    start = time.monotonic()
                    try:
                        with self.assertRaisesRegex(RuntimeError, 'Cancelled by user'):
                            if mode == 'direct':
                                executor.run_process(args, capture_output=True)
                            else:
                                executor.execute(command, stream_output=mode == 'stream',
                                                 capture_output=mode == 'capture')
                    finally:
                        timer.cancel()
                    self.assertLess(time.monotonic() - start, 5)
            time.sleep(2)
            for mode in ('stream', 'capture', 'plain', 'direct'):
                self.assertFalse((folder / mode).exists(), f'{mode}: child survived cancellation')

    @unittest.skipUnless(shutil.which('samtools') and shutil.which('minimap2'), 'alignment tools required')
    def test_alignment_preserves_modifications_on_both_strands(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            randomizer = random.Random(42)
            sequence = ''.join(randomizer.choice('ACGT') for _ in range(3000))
            reference = folder / 'reference.fa'
            reference.write_text('>chr1\n' + sequence + '\n')
            forward = sequence[500:2000]
            reverse = forward.translate(str.maketrans('ACGT', 'TGCA'))[::-1]
            sam = folder / 'barcode01.sam'
            sam.write_text('@HD\tVN:1.6\n' + ''.join(
                f'{name}\t4\t*\t0\t0\t*\t*\t0\t0\t{seq}\t{"I" * len(seq)}\tMM:Z:C+m,0;\tML:B:C,255\tMN:i:1500\n'
                for name, seq in [('forward', forward), ('reverse', reverse)]))
            bam = folder / 'barcode01.bam'
            subprocess.run(['samtools', 'view', '-b', '-o', str(bam), str(sam)], check=True)
            processor = AlignmentProcessor.__new__(AlignmentProcessor)
            processor.context = SimpleNamespace(logger=Mock(), command_executor=CommandExecutor(Mock()))
            output = folder / 'aligned.bam'
            processor._align_one_file(bam, output, reference, 'map-ont', 'bam')
            result = subprocess.run(['samtools', 'view', '-F', '2308', str(output)],
                                    check=True, capture_output=True, text=True)
            reads = {line.split('\t')[0]: line.split('\t') for line in result.stdout.splitlines()}
            self.assertEqual(set(reads), {'forward', 'reverse'})
            self.assertFalse(int(reads['forward'][1]) & 16)
            self.assertTrue(int(reads['reverse'][1]) & 16)
            for fields in reads.values():
                self.assertIn('MM:Z:C+m,0;', fields)
                self.assertIn('ML:B:C,255', fields)
                self.assertIn('MN:i:1500', fields)


if __name__ == '__main__':
    unittest.main()
