"""Organism-specific KM presentation without changing scientific records."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from dorado_workflow.reports.demo_all_barcodes import demo_run
from dorado_workflow.reports.interactive.models import unavailable
from dorado_workflow.reports.overview.dashboard import render_screen
from dorado_workflow.reports.shared.organism import show_km
from dorado_workflow.reports.barcode.length_plots import _hide_completeness


class OrganismPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.example = demo_run()
        cls.example.barcodes = cls.example.barcodes[:1]
        barcode = cls.example.barcodes[0]
        barcode.reads = barcode.reads[:2]
        barcode.metrics['filtered_length_records'].value = barcode.metrics['filtered_length_records'].value[:2]
        barcode.metrics['amount_of_telomeres'].value = 2

    def test_human_omits_sections_and_keeps_read_browser(self):
        for name in ('human', ' Human ', 'HUMAN', 'Homo sapiens'):
            with self.subTest(organism=name):
                run = deepcopy(self.example)
                run.organism.value = name
                before = deepcopy(run)
                with patch('dorado_workflow.reports.reads.browser.saved_completeness') as completeness:
                    page = render_screen(run)
                completeness.assert_not_called()
                self.assertNotIn('Telomere Completeness &amp; Kaplan-Meier Estimate', page)
                self.assertIn('Telomere Length Distribution', page)
                self.assertIn('Telomere and Read Length per Read', page)
                self.assertIn('data-km-enabled="false"', page)
                self.assertIn('class="read-browser"', page)
                self.assertIn('Telomere Length by Barcode', page)
                self.assertEqual(run, before)

    def test_nonhuman_retains_all_three_sections(self):
        for name in ('mouse', 'zebrafish'):
            with self.subTest(organism=name):
                run = deepcopy(self.example)
                run.organism.value = name
                page = render_screen(run)
                self.assertIn('Telomere Completeness &amp; Kaplan-Meier Estimate', page)
                self.assertIn('Telomere Length Distribution', page)
                self.assertIn('Telomere and Read Length per Read', page)
                self.assertIn('data-km-enabled="true"', page)

    def test_unknown_organism_does_not_enable_km(self):
        run = deepcopy(self.example)
        run.organism = unavailable('Organism not recorded')
        self.assertFalse(show_km(run))

    def test_censoring_overlay_hidden_without_changing_counts_or_menu_targets(self):
        figure = {'data': [
            {'type': 'bar', 'x': [1000, 2000], 'y': [3, 4]},
            {'type': 'scatter', 'name': 'Smoothed observed lengths', 'y': [2, 3]},
            {'type': 'scatter', 'name': 'Censored reads (observed lengths)',
             'x': [1000], 'text': ['read1'], 'hovertemplate': 'Censored'}],
            'layout': {'meta': {'read_completeness': [{'read_id': 'read1', 'event': 0}]},
                       'annotations': [{'text': 'Final-filtered reads | exact | complete: 6 | censored: 1 | unknown: 0'}],
                       'updatemenus': [{'buttons': [{'args': [{'y': [[3, 4], [2, 3]]}, {}, [0, 1]]}]}]}}
        before = deepcopy(figure)
        _hide_completeness(figure)
        self.assertEqual(figure['data'][:2], before['data'][:2])
        self.assertEqual(figure['layout']['updatemenus'], before['layout']['updatemenus'])
        self.assertFalse(figure['data'][2]['visible'])
        self.assertNotIn('read_completeness', figure['layout']['meta'])
        self.assertEqual(figure['layout']['annotations'][0]['text'], 'Final-filtered reads | exact')


if __name__ == '__main__':
    unittest.main()
