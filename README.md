# DendroMatch 0.1

A Python desktop workbench for exploratory tree-ring crossdating. Load reference chronologies and a sample, inspect the measurements, search selected intervals, compare candidate placements and export the analysis. Original measurements remain unchanged. Developed as a companion to DendroTrace; no CT volume is needed to test this matching application.

## Open in PyCharm

1. Extract the entire ZIP to a writable folder.
2. In PyCharm choose **Open** and select the `DendroMatch` folder containing `main.py`.
3. Select/create a project virtual environment with Python 3.11 or 3.12.
4. In the terminal using that environment run `python -m pip install -r requirements.txt`.
5. Run `main.py`, or use the shared **DendroMatch** run configuration. A second configuration opens the Oppland/Vågå example automatically.

No local interpreter path or virtual environment is bundled. Windows/PyCharm itself has not been tested here; automated desktop checks were run under offscreen Linux. You can run the same source from a terminal using `python main.py`.

## First demonstration

Click **Load Oppland/Vågå example**, then **Run matching**. The bundled sample is the conventional laboratory series supplied for the specimen scanned in Prague. It contains 334 annual widths, with supplied dates 1292–1625. OPPLAND0 contains 1,150 reference values, 837–1986. Both series retain their supplied numeric values, with units explicitly unconfirmed.

The default Baillie–Pilcher search tests 817 complete-overlap placements. It recovers **1292–1625**, r ≈ 0.330834, t ≈ 6.349, using 330 processed pairs. Sample date metadata are ignored by the engine. No dates are accepted automatically, and a last measured ring is not labelled a felling date.

## Main workflow

### Reference library and imports

**Import reference** accepts CSV, TSV, text, XLS or XLSX. A preview asks for the width column, optional year column and first data row. Years must be consecutive, increasing integers. If a reference has no year column, enter its first year explicitly. Sample imports can omit years and use consecutive row order.

Only the first Excel sheet is read. Export other sheets as CSV first. Text files disguised as `.xls`, including the supplied Opplandskurven file, are detected correctly. Dot and decimal-comma numeric values are supported when the delimiter separates them unambiguously. Headerless files require first data row 1. Interior missing widths, zero/negative widths, invalid values and nonconsecutive years are rejected rather than silently compressing annual time.

For Opplandskurven: import columns **1 (year), 2 (reference)** for OPPLAND0; separately import **4 (year), 5 (sample)** for Vågå, starting at row 2. Trailing blanks in the shorter sample columns are permitted.

For a DendroTrace `_widths.csv`, import `width_mm` if calibrated, otherwise `width_px`. Choose **None — consecutive rows** for calendar years. Do not select `relative_ring_number` as a calendar-year column. Add original source, units, species, region and relevant notes during import. **Details** and **Inspect sample** show the retained metadata and exact numeric values. Metadata are not automatically interpreted as constraints.

Reference names must be unique. Check the references to include in a search. Highlight a reference to inspect its complete curve. **Save library / Load library** stores and merges reusable reference collections, including data and provenance. It does not contact any external repository or imply permission to redistribute third-party reference data.

### Interval selection

Ring numbers are one-based in the GUI. Set first/last rings, or Shift-drag across the lower input plot. Only that interval is used for matching. Full overlap means **all rings in the chosen interval** fit inside each candidate reference window. The remainder of a partially selected sample may extend outside the reference.

Year bounds always apply to the **first ring of the COMPLETE sample**, even when matching a subsection. Results separately show the selected interval's calendar coverage. Example: matching rings 101–200 at years 1392–1491 implies a complete-sample start of 1292. No sample dates guide candidate selection.

### Matching methods

All candidates are ranked by descending Pearson correlation of the selected transformed series. Pair counts are constant for a given interval/method, so t ranking is equivalent to r ranking. Results combine all checked references; the table shows the top 1,000 candidates and exports contain every candidate.

- **Baillie–Pilcher (5-year)**: centred five-year moving mean MA5; transform `ln(100 * width / MA5)`. Two rings at each endpoint are omitted from scoring. A 334-ring selection therefore yields 330 pairs.
- **Hollstein (log ratios)**: `100 * log10(width[t] / width[t-1])`, yielding one fewer pair. Equivalent correlations arise from any constant scaling of natural-log differences.
- **First differences**: `width[t] - width[t-1]`, one fewer pair.
- **Raw Pearson**: no annual-change transformation. Useful for comparison, but broad growth trends can produce high correlations at incorrect placements.

The conventional t score is `r * sqrt((N-2) / (1-r²))`. It is a match score, not a confidence probability. Perfect correlations are numerically capped in this formula. No significance thresholds, automatic dating decisions, search-wide probability estimates or claims of independent confirmation are generated.

**GLK %** is directional agreement calculated from original successive widths using `100 * mean((sign(dx)*sign(dy)+1)/2)`. Tied changes contribute half a match, including simultaneous ties. It is descriptive; no GLK p-value is calculated. This column is not the ranking criterion.

**Pre-smoothing** is optional Gaussian smoothing in years, default OFF. It is applied separately to the exact sample interval and each reference window before the selected transformation. It can suppress real annual information and increase serial dependence; smoothed scores should not be treated as equivalent to unsmoothed results.

### Candidate review and diagnostics

Select a results row to update both alignment plots and the segment diagnostic. The upper alignment plot shows original values, optionally rescaled by z-score or mean division. This display setting never changes the search. The lower plot shows matching-method outputs, separately z-scored for visual comparison. Numeric r/t are calculated before this display scaling.

The search-score tab shows every candidate for each reference. Clicking near a peak selects the nearest point among the top 1,000 listed results. Use **Candidate alignment** to review the selected row. Standard Matplotlib toolbar controls provide pan, zoom and image saving.

**Segment check** inspects the entire sample using 50-ring windows, stepping 25 rings, including regions outside a selected matching interval where they fit in the reference. It compares the candidate placement with shifts of ±10 years. Nonzero labels identify stronger local alternatives. The segment check uses the selected method but **no optional pre-smoothing**. Final incomplete blocks are omitted. A locally stronger alternative is a flag to inspect, not an automatic missing-ring diagnosis. Whole-sample dates extrapolated from a small interval require particular care.

### Projects and exports

**Save project** embeds the original sample and all references, search settings, checked reference names, display normalisation and project notes. Source files are not needed when reopening. Results are deliberately recomputed with **Run matching**. Selected candidate row, zoom/pan and tab positions are not currently saved.

Numerical input changes clear stale matches. Display scaling does not. Searches run in a background thread; a status-bar button allows cancellation. Unsaved changes prompt before replacing/closing a project.

**Export results** creates a fresh timestamped directory containing:

- `candidates.csv`: all tested placements and scores, in ranked order.
- `selected_overlap.csv`: original measurements aligned at the selected candidate.
- `processed_overlap.csv`: exact transformed values used for that candidate's score.
- `segments.csv`: local consistency checks for the candidate.
- `analysis.json`: embedded inputs, search definition, selected candidate, notes and limitations.
- `selected_alignment.png` and `search_scores.png`: figures from the current analysis.

**Export graph** saves the active plot as PNG, PDF or SVG. Exported data and plots describe the selected candidate, not an accepted dating.

## Structure

- `main.py`: entry point.
- `dendromatch/models.py`: data and result classes.
- `dendromatch/dataio.py`: table parsing and CSV exports.
- `dendromatch/processing.py`: transformations, smoothing and display scaling.
- `dendromatch/matching.py`: searching and segment diagnostics; no GUI dependencies.
- `dendromatch/project.py`: portable JSON persistence and reference libraries.
- `dendromatch/ui/import_dialog.py`: explicit-column importer.
- `dendromatch/ui/main_window.py`: views, worker thread and interactions.
- `tests/`: known-data regressions, synthetic indexing and desktop workflow checks.

The processing core can later be reused from DendroTrace or a Slicer module. The code is separated by responsibility and includes module/class/function docstrings. The prototype does not yet include type annotations throughout or a formal packaging release pipeline.

## Testing

Run `python -m unittest discover -v` from the project root. Tests cover the supplied known-age match, ignoring supplied dates, scale invariance, subsection-to-calendar indexing, cancellation, a hand-calculated BP transform, missing-data rejection, project roundtrip, candidate selection, original and processed exports, stale-result clearing and the background worker. Headless GUI tests use `QT_QPA_PLATFORM=offscreen`.

## Scope and next development

This release supports one sample at a time against multiple references. It does not include automatic missing/false-ring edits, raw acquisition data, sample composites, Tucson RWL/CRN or Heidelberg FH import, detrending splines/AR models, surrogate confidence tests, felling-date estimation or independent-reference verification. References are local files, not a bundled national database. Future editions could add these around validated core functions.

For the CT comparison, begin by importing the conventionally measured Vågå series as a dated reference and a CT-derived width sequence as the sample. The same timber can have different widths on different radii, so compare measurement paths and acquisition geometry as well as scores.

## Method references

- Baillie & Pilcher transform: https://docs.ropensci.org/fellingdater/reference/trs_tbp_transform.html
- Hollstein transform: https://docs.ropensci.org/fellingdater/reference/trs_tho_transform.html
- Dendrochronological reporting guidance: https://archaeologydataservice.ac.uk/help-guidance/guides-to-good-practice_old/data-collection-and-fieldwork/dendrochronology/aims-and-objectives/background-to-the-guide/

The bundled Oppland/Vågå data were supplied by the user. Species, exact width units, chronology processing and reference independence are not established by the file itself.
