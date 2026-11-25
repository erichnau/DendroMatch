"""Serializable data structures shared by the matching engine and interface."""
from dataclasses import dataclass, field, asdict
import numpy as np

@dataclass
class Series:
    """One consecutive annual series. References require a start year.

    Samples may carry an existing date, but search never uses it to select a lag.
    Values are retained in their original units; no automatic conversion occurs.
    """
    name: str
    values: list[float]
    start_year: int | None = None
    species: str = ''
    region: str = ''
    units: str = 'unspecified'
    source: str = ''
    notes: str = ''

    def validate(self, reference=False):
        """Reject unusable data before a search or project write."""
        a = np.asarray(self.values, float)
        if a.ndim != 1 or len(a) < 10 or not np.isfinite(a).all() or (a <= 0).any():
            raise ValueError(f'{self.name}: need at least 10 finite, positive consecutive widths.')
        if not self.name.strip():
            raise ValueError('A series name is required.')
        if reference and self.start_year is None:
            raise ValueError(f'{self.name}: reference needs a calendar start year.')
        if self.start_year is not None and (isinstance(self.start_year, bool) or int(self.start_year) != self.start_year):
            raise ValueError('Start year must be an integer.')

    @property
    def end_year(self):
        """Return the calendar year of the last value, when dated."""
        return None if self.start_year is None else self.start_year + len(self.values)-1

@dataclass
class SearchSettings:
    """One reproducible search definition; interval indices are zero-based inclusive."""
    method: str = 'Baillie–Pilcher (5-year)'
    first: int = 0
    last: int = 333
    min_start: int = 0
    max_start: int = 3000
    smoothing_sigma: float = 0.0
    min_pairs: int = 50

@dataclass
class Match:
    """A candidate placement; t is a score, never a dating probability."""
    reference: str
    sample_start: int
    sample_end: int
    interval_start: int
    interval_end: int
    pairs: int
    r: float
    t: float
    glk: float

@dataclass
class SearchOutput:
    """All candidate results with settings and exact source snapshots."""
    settings: SearchSettings
    sample: Series
    references: list[Series]
    results: list[Match] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
