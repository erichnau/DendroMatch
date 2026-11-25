"""Portable project and reference-library persistence with atomic writes."""
from pathlib import Path
from dataclasses import asdict
import json
from .models import Series, SearchSettings

def write_json(path,data):
    """Replace a JSON file only after its complete new content is written."""
    path=Path(path);tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    tmp.replace(path)

def save_project(path,sample,references,settings,display_mode='Z-score',notes='',checked_references=None):
    """Embed data and settings; search results are recomputed on reopening."""
    write_json(path,dict(format='DendroMatch',version=1,sample=asdict(sample) if sample else None,
        references=[asdict(r) for r in references],settings=asdict(settings),display_mode=display_mode,notes=notes,checked_references=checked_references if checked_references is not None else [r.name for r in references]))

def load_project(path):
    """Validate all embedded series before returning a new session."""
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('format')!='DendroMatch' or data.get('version')!=1:raise ValueError('Unsupported DendroMatch project.')
    sample=Series(**data['sample']) if data.get('sample') else None
    refs=[Series(**r) for r in data['references']]
    if sample:sample.validate()
    for ref in refs:ref.validate(True)
    if len({r.name for r in refs})!=len(refs):raise ValueError('Duplicate reference names.')
    return sample,refs,SearchSettings(**data['settings']),data.get('display_mode','Z-score'),data.get('notes',''),data.get('checked_references',[r.name for r in refs])

def save_library(path,references):
    """Save a reusable reference collection with provenance and units."""
    write_json(path,dict(format='DendroMatch library',version=1,references=[asdict(r) for r in references]))

def load_library(path):
    """Read a reusable collection; the caller resolves name conflicts."""
    d=json.loads(Path(path).read_text(encoding='utf-8'))
    if d.get('format')!='DendroMatch library' or d.get('version')!=1:raise ValueError('Unsupported library.')
    refs=[Series(**r) for r in d['references']]
    for r in refs:r.validate(True)
    return refs
