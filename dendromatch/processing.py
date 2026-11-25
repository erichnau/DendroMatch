"""Transparent preprocessing in annual sample coordinates."""
import numpy as np
from scipy.ndimage import gaussian_filter1d

METHODS = ['Baillie–Pilcher (5-year)', 'Hollstein (log ratios)', 'First differences', 'Raw Pearson']

def smooth(values, sigma=0.0):
    """Optionally Gaussian-smooth in years. Zero leaves widths untouched."""
    a=np.asarray(values,float)
    return gaussian_filter1d(a,sigma,mode='nearest') if sigma > 0 else a.copy()

def transform(values, method):
    """Return transformed values and their offset from the first original ring.

    BP: ln(100*x/MA5), centred five-year mean; omit two endpoints per side.
    Hollstein: 100*log10(x[t]/x[t-1]); first output belongs to ring index 1.
    First differences use the same indexing. Raw Pearson retains all rings.
    """
    a=np.asarray(values,float)
    if method == METHODS[0]:
        return np.log(100*a[2:-2]/np.convolve(a,np.ones(5)/5,mode='valid')),2
    if method == METHODS[1]:
        return 100*np.diff(np.log10(a)),1
    if method == METHODS[2]:
        return np.diff(a),1
    if method == METHODS[3]:
        return a.copy(),0
    raise ValueError(f'Unknown method: {method}')

def normalise(values, mode='Z-score'):
    """Rescale display values only; this does not remove growth trends."""
    a=np.asarray(values,float)
    if mode == 'Z-score':
        sd=a.std()
        return (a-a.mean())/sd if sd>0 else a*0
    if mode == 'Mean division':
        return a/a.mean() if a.mean()!=0 else a*0
    return a.copy()
