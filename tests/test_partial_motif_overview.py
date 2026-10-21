"""Partial motif availability must not hide complete barcode data."""
import json
import re
import unittest
from copy import deepcopy
from dorado_workflow.reports.overview.comparisons import overview_composition_section


class PartialMotifOverviewTests(unittest.TestCase):
    def setUp(self):
        self.rows = [dict(barcode='barcode01', total=2, with_tvr=1,
                          base_counts={'TTAGGG (canonical)': 90, 'TCAGGG': 10}),
                     dict(barcode='barcode02', total=8, with_tvr=1,
                          base_counts={'TTAGGG (canonical)': 300, 'TCAGGG': 100})]

    def test_partial_data_renders_weighted_available_population(self):
        data = dict(composition=self.rows, omitted=['barcode05', 'barcode06'])
        before = deepcopy(data)
        page = overview_composition_section(data)
        self.assertIn('TVR Composition - Available Barcodes', page)
        self.assertIn('Showing 2 barcodes and 10 post-filtered reads', page)
        self.assertIn('barcode05, barcode06', page)
        self.assertNotIn('Unavailable:', page)
        figure = json.loads(re.search(r'class="histogram-figure">(.*?)</script>', page, re.S)[1])
        pie = figure['data'][0]
        self.assertEqual(dict(zip(pie['labels'], pie['values'])),
                         {'TTAGGG (canonical)': 390, 'TCAGGG': 110, 'Unassigned bases': 0})
        self.assertIn('20.0%', figure['layout']['annotations'][0]['text'])
        self.assertIn('2 / 10 reads', figure['layout']['annotations'][0]['text'])
        self.assertEqual(data, before)

    def test_complete_data_keeps_all_barcode_title(self):
        page = overview_composition_section(dict(composition=self.rows, omitted=[]))
        self.assertIn('TVR Composition - All Barcodes', page)
        self.assertNotIn('Excluded because', page)

    def test_no_available_data_does_not_fabricate_graph(self):
        page = overview_composition_section(dict(composition=[], omitted=['barcode05']))
        self.assertIn('No barcodes have complete motif exports', page)
        self.assertNotIn('class="histogram-figure"', page)


if __name__ == '__main__':
    unittest.main()
