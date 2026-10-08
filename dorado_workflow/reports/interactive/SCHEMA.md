# NanoTel offline report contract — schema 1.0

This is a presentation adapter, not an analysis implementation. It never scans
sequences, selects calls, reruns filters, calls TVRs, or derives chromosome arms.
All source files remain untouched. The report is a standalone builder; no GUI,
pipeline completion or R code is modified.

## Build and open

```powershell
python -m dorado_workflow.reports.interactive "C:\path\to\run\results"
# Optional explicit metadata and alternative NEW/EMPTY destination:
python -m dorado_workflow.reports.interactive "C:\path\to\results" --metadata run-metadata.json --output report-preview
python -m unittest discover -s tests -p test_interactive_report.py -v
```

Open the resulting `report/index.html` directly in a browser. Move/copy the
**whole report directory**, including assets, when sharing. No HTTP server,
internet, CDN, remote fonts, fetch or ES modules are used. Plotly is bundled locally in assets/plotly.min.js. A restrictive
content security policy prohibits network connections. Generation refuses to
overwrite a nonempty directory. Source records are rendered with `textContent`,
never interpreted as markup. Report files contain scientific read identifiers
and provenance; sharing the directory shares those contents.

## Inputs and precedence

Point the importer at ONE run's results directory. Recognized sources:

* `barcode*_summary.csv`: detected summary records (not all sequencing reads).
* `filtered_summary*.csv`: explicit positive filtered-output membership only.
* `nanotel_summary_statistics.csv`: source-reported post-filtered counts,
  median length and mean density.
* `nanotel_summary.xlsx`: fallback `barcodeNN`, `filtered_barcodeNN` and
  `NanoTel Statistics` sheets; CSV wins if both exist for a given table.
* `mapped*barcode*.csv`: mapping rows joined within barcode using the existing
  cleaned-read-ID convention. Combined CSV takes precedence over its per-file
  components. Multiple alignments are retained; no primary alignment is chosen.

Ambiguous duplicate summaries/statistics/combined workbooks fail import, rather
than choosing an arbitrary result. Duplicate read IDs retain separate records
and warnings. Ambiguous/missing mapping joins are skipped with warnings. CSV
header-only input is an available empty record set. A missing source is not
equivalent to zero records. A workbook can synthesize an empty filtered sheet;
absence from it never establishes failure or a zero filtered population.

Known NanoTel log labels supply total input and detected telomeric counts only
when exactly one completed barcode log exists. FASTQ/BAM, density CSVs and
motif-interval files are not scanned. TVR percentage and molecule-level
methylation remain unavailable without an explicit supported export. Existing post-filtered counts
remain source-reported; record counts are labeled presentation aggregates.

## Optional metadata

This is explicit external context, not data inferred from filenames. Its JSON
file is hashed and registered as a provenance source. Supply only known values.
Do not claim the current GUI defaults describe a historical run.

```json
{
  "organism": "mouse",
  "settings": {"nanotel": {"min_density": 0.75}},
  "stages": {"summary_only": true, "mapping": false, "methylation": false},
  "mapping_coordinate_convention": "one_based_inclusive"
}
```

Mapping coordinate conventions: `unknown` (default), `one_based_inclusive`,
`zero_based_half_open`. The current Python aligner emits SAM-based inclusive
start/end values, but legacy Dorado tables may differ. Because mapping CSVs do
not identify their producer/version, an explicit convention is required to
normalize their coordinates. Without it, raw alignment values remain visible.

## Entity structure

The machine-readable `report-data.json` contains:

* **Run:** schema_version, id, label, organism Fact, settings Fact, stages map,
  barcodes list, sources list, metrics map, warnings list.
* **Barcode:** id, label, reads list, metrics map, evidence list, warnings list.
* **Read:** id, original_id, barcode_id, metrics map, calls map, filtering Fact,
  alignments Fact, tracks map, evidence list, warnings list.
* **Call:** reported_length Fact, density Fact, raw_interval Fact, interval Fact,
  original_read_orientation Fact. Keys `exact`, `mismatch`, `tvr_inclusive`
  preserve source methods; no implicit preferred call is defined.
* **Alignment:** reference, strand, mapq, chromosome, arm, raw and normalized
  interval Facts. Reference labels remain exact; Head/Tail does not imply p/q.
  SAM MAPQ 255 is unavailable rather than a quality score of 255.
* **Tracks:** density, motifs, tvr_regions, methylation Facts, reserved for later
  source-export adapters. No new calling or region merging occurs.

Every **Fact** has `status`, `value`, `reason`, `unit`, `population`, `origin`,
and `evidence`. Origins are `source_reported` or `presentation_aggregate`.
Units include bp, reads, records, barcodes and fraction. Density is kept as a
fraction; it is NOT labeled canonical or TVR percentage. Population strings
distinguish detected_summary_records, filtered_summary_records,
post_filtered_telomeres and imported_barcodes.

Availability states:

| Status | Meaning |
| --- | --- |
| available | Value exists; zero, false and empty collections are valid. |
| not_requested | Explicit metadata says the relevant stage/detail was disabled. |
| not_exported | No supported export/context supplies the value. |
| missing | Expected data is absent (for example an explicitly enabled stage). |
| invalid | Supplied values or associations cannot be interpreted safely. |
| not_applicable | Measurement does not apply, including SAM unavailable MAPQ. |

Unavailable Facts require `value: null` and a reason. Available Facts require
non-null values and provenance. A missing value is never silently coerced to 0.
Biological NA remains not_exported/unavailable; no failed-detection conclusion
is inferred. Unknown and malformed measurements stay distinguishable.

## Coordinates

* Normalized intervals are **0-based half-open**, `[start,end)`, in bp.
* Visible normalized positions are **1-based inclusive**, explicitly labeled:
  normalized `[0,120)` displays `1–120 bp`.
* NanoTel R summary intervals originate from IRanges and use 1-based inclusive
  coordinates. Their space is `nanotel_analyzed_read`, not original FASTQ or
  genomic coordinates. Reverse-complement/crop transforms are not recorded by
  these summaries, so original-read orientation remains unavailable.
* Reference intervals are a distinct `reference` space, associated with an
  exact reference label. No reference/read projection is attempted.
* Raw coordinate strings/numbers and their conventions remain preserved.
* Negative, reversed, non-integer or out-of-read-bounds intervals are invalid.
* Reported lengths remain authoritative. Disagreement with interval width emits
  a warning but never replaces the length or detected boundary.
* Relative positions, aligned density/TVR tracks and orientation transformations
  are deferred until explicit source associations/transforms exist.

## IDs, routing and provenance

IDs use kind plus full SHA-256 of a JSON tuple. Names are never URL/path pieces:

```
index.html#/run
index.html#/barcode/b-<64 lowercase hex digits>
index.html#/barcode/b-<64 lowercase hex digits>/read/r-<64 lowercase hex digits>
```

Barcode IDs hash the normalized barcode label. Read IDs hash barcode ID,
original read ID and duplicate occurrence ordinal. They are stable for the same
records; duplicate records are intentionally not asserted to be one molecule.
The run ID hashes the directory label and is report-local, not a global run UUID.
Every route checks barcode/read membership before loading/rendering. Unknown
routes show a recoverable error. Hash routing supports reload and Back/Forward.

Each Source records a report-local ID, relative path (or external metadata
basename), format, optional Excel sheet, and SHA-256 of the source file. Evidence
records source ID, 1-based row (header is row 1), and relevant source columns.
Source-reported statistics retain their source evidence. Presentation counts
cite the source table. Source files need not remain present to explore a report.

`assets/data/run.js` contains the run index without read arrays. Each barcode's
read data is in `assets/data/b-<hash>.js`, loaded by a classic local script tag.
Only known hash IDs can request these files. Missing chunks show an error and
link back to overview. The read table renders 50 records at a time. Generation
still loads imported records in memory; very large runs need a later streaming
adapter rather than silently truncating records.

## Validation boundaries

Model validation checks schema version, ID uniqueness/syntax, barcode ownership,
availability contracts, evidence references, positive source-row numbers and
finite JSON values. Adapters additionally check input structure, numeric ranges,
coordinate bounds and duplicate/ambiguous associations. Scientific correctness
of the upstream call is outside the report's responsibility. No existing
scientific outputs are rewritten or deleted.


## Dashboard presentation extension

The `dashboard` object is included in run.js and report-data.json. It contains
metric Facts, per-barcode filtered-length records and reference heatmap cells.
Plotly is installed as a Python dependency; its JavaScript bundle is copied into
the report at generation time. Viewing the report remains completely offline.

* Input counts are read from `Total reads in sample:` in a single completed
  `nanotel_barcodeNN.log`, with source line numbers and hashes.
* Detected counts come from `Number of reads which identified as Telomeric:`.
* Post-filtered counts come from the existing statistics table. Their sum is
  shown separately from pre-filter detected counts.
* The displayed post-filtered fraction is sum(filtered counts) / sum(input counts).
  It is unavailable if any barcode lacks either value; a zero denominator is
  not applicable. No unweighted average of percentages is used.
* Distribution values come from `Telomere_length_mismatch` in the existing
  filtered tables, the same column the R summary uses. No thresholds are rerun.
  Duplicate/missing identifiers, invalid lengths or a count disagreement with
  source statistics make that distribution unavailable.
* The overall median pools those filtered per-read lengths across ALL barcodes.
  It never averages barcode medians; incomplete input makes it unavailable.
* R may strip header annotations from read IDs. Exact IDs take precedence;
  first-token joins are permitted only when unambiguous within a barcode.
* Heatmap cells show the median existing filtered telomere length for each
  source reference label. Multiple mappings are retained. Each molecule counts
  at most once per reference, but can contribute to several references. Missing
  mappings remain gaps; they do not become zero-length values. Reference counts
  are not chromosome counts or genome coverage estimates.
* TVR composition is explicitly unavailable without motif exports. Density
  fields are never substituted for TVR/canonical percentages.

`reports/r_pipeline_config.json` supplies recorded settings and enabled stages
when present. A unique `Organism:` value from the main run log may supply the
organism. Explicit --metadata fields override the automatic metadata. Provenance
is preserved for both. No current application default is used for historical runs.

Run/Barcode pages now include offline interactive charts. Clicking a count bar
or heatmap cell opens its barcode; clicking a length point with an unambiguous
read link opens that read. The table and breadcrumbs remain available. Technical
source details are collapsed by default so they do not dominate the dashboard.


### Exported read-density samples

Non-summary NanoTel runs export `report_details/barcodeNN_read*_density.csv`
from the existing plot data frames. Columns: `read_id`, `method` (`exact`,
`mismatch`, `tvr_inclusive`), `start`, `end`, `density`, `convention`, `space`.
Source windows are 1-based inclusive in `nanotel_analyzed_read`; imported
`tracks.density` samples use 0-based half-open start/end and a density fraction.
The importer requires an unambiguous full read ID within the barcode, finite
fractions in [0,1], valid intervals within the exported read length, known
methods, and unique method/window starts. Invalid samples invalidate that
read's entire density track. Evidence retains source hashes and CSV rows.
No density calculation occurs in the report. This additive export does not
change detection or filtering and is skipped in summary-only mode. Older
outputs must be rerun to obtain these samples. Exact TVR calls, motif
composition, chromosome-arm annotations and original-read orientation remain
unavailable until explicitly exported; TVR-inclusive density is not TVR content.


### Motif-level search matches

`report_details/[barcodeNN_]readN_motifs.csv` preserves matches before NanoTel
unions their ranges. Each row includes read_id, method, record_type, motif,
matched_sequence, start, end, role (canonical/tvr), max_mismatch, convention
(one_based_inclusive) and space (nanotel_analyzed_read). A search_complete
sentinel identifies each exported method, including zero-match searches.
Missing files are not zero matches. Unknown methods, malformed intervals,
invalid sequence text and incomplete exports invalidate the track.

`tracks.motifs.value` contains `methods` and `matches`, normalized to zero-based
half-open intervals. Matches retain their method and overlap: they are not
merged TVR regions. The report shows the searched motif separately from the
observed sequence because mismatches and ambiguity codes may differ. Counts
are across the whole analyzed read; no percentage or repeat-count inference
is made. Canonical classification means membership in the supplied canonical
pattern list. A configured TVR motif can overlap canonical matches.

The existing scalar TVR branch's union behavior is unchanged: recorded search
hits are not a claim that every hit contributed to the density calculation.
For recovered exports, motif_recovery.json records the saved FASTA hashes,
NanoTel code hash and search settings and is included in source provenance.
