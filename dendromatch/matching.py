"""Full-overlap, date-unconstrained crossdating engine, independent of Qt."""
from dataclasses import replace
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from .models import SearchOutput, Match
from .processing import smooth, transform, METHODS

class Cancelled(Exception):
    """Raised when a background search is cancelled."""

def search(sample, references, settings, cancelled=lambda:False, progress=lambda x:None):
    """Slide the selected sample interval across each reference without gaps.

    Every candidate has the same selected-interval length. The complete sample
    can extend beyond a reference if a shorter interval is being searched.
    Preprocessing is performed independently on each candidate window, avoiding
    any use of reference values outside the selected overlap. Smoothing also
    operates on these exact windows. All supplied sample calendar dates are ignored.
    """
    sample.validate()
    n=len(sample.values);lo=settings.first;hi=settings.last
    if not 0<=lo<=hi<n:
        raise ValueError('Select a valid sample ring interval.')
    if settings.min_start>settings.max_start:
        raise ValueError('Start-year bounds are reversed.')
    if settings.smoothing_sigma<0 or settings.min_pairs<3:
        raise ValueError('Invalid smoothing or minimum pair count.')
    b=np.asarray(sample.values,float)[lo:hi+1]
    y,offset=transform(smooth(b,settings.smoothing_sigma),settings.method)
    if len(y)<settings.min_pairs:
        raise ValueError(f'Only {len(y)} pairs remain after processing; lower the minimum or use a longer interval.')
    yn=y-y.mean();norm=np.linalg.norm(yn)
    if norm<1e-12:
        raise ValueError('Selected sample interval has no usable variation.')
    output=SearchOutput(replace(settings),replace(sample,values=sample.values.copy()),[])
    if settings.smoothing_sigma:
        output.warnings.append('Pre-smoothing was enabled. It can suppress annual dating information and inflate dependence.')
    if settings.method==METHODS[3]:
        output.warnings.append('Raw Pearson can favour broad growth trends over annual agreement.')
    for ri,ref in enumerate(references):
        if cancelled():raise Cancelled()
        ref.validate(reference=True)
        output.references.append(replace(ref,values=ref.values.copy()))
        a=np.asarray(ref.values,float)
        if len(a)<len(b):
            output.warnings.append(f'{ref.name}: shorter than selected interval; skipped.')
            continue
        windows=sliding_window_view(a,len(b))
        for i,window in enumerate(windows):
            if i%100==0 and cancelled():raise Cancelled()
            fullstart=ref.start_year+i-lo
            if not settings.min_start<=fullstart<=settings.max_start:continue
            x,_=transform(smooth(window,settings.smoothing_sigma),settings.method)
            xn=x-x.mean();denom=np.linalg.norm(xn)*norm
            if denom<1e-12:continue
            r=float(np.clip(np.dot(xn,yn)/denom,-1,1))
            t=r*np.sqrt((len(y)-2)/max(1e-15,1-r*r))
            # Direction agreement: any tied change contributes half a match.
            glk=float(100*np.mean((np.sign(np.diff(window))*np.sign(np.diff(b))+1)/2))
            output.results.append(Match(ref.name,fullstart,fullstart+n-1,
                fullstart+lo,fullstart+hi,len(y),r,float(t),glk))
        progress(int((ri+1)/len(references)*100))
    output.results.sort(key=lambda m:m.r,reverse=True)
    if not output.results:raise ValueError('No valid placements within the chosen bounds.')
    return output

def segment_check(sample, ref, placement, method, window=50, step=25):
    """Check overlapping blocks at a chosen full-sample placement and ±10 years.

    Reports local consistency, not independent confirmation of a selected date.
    Only segments that fully fit in the reference are scored.
    """
    rows=[]; a=np.asarray(ref.values,float); b=np.asarray(sample.values,float)
    for lo in range(0,len(b)-window+1,step):
        y,_=transform(b[lo:lo+window],method); y-=y.mean();yn=np.linalg.norm(y)
        candidates={}
        for lag in range(-10,11):
            i=placement+lo+lag-ref.start_year
            if i<0 or i+window>len(a):continue
            x,_=transform(a[i:i+window],method);x-=x.mean();den=np.linalg.norm(x)*yn
            if den>1e-12:candidates[lag]=float(x@y/den)
        if candidates:
            best=max(candidates,key=candidates.get)
            rows.append(dict(first_ring=lo+1,last_ring=lo+window,calendar_start=placement+lo,
                r_at_placement=candidates.get(0,float('nan')),best_local_shift=best,best_local_r=candidates[best]))
    return rows
