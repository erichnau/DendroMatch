"""Explicit-column table import and auditable CSV output."""
from pathlib import Path
import csv,io,json
import numpy as np
from .models import Series

def read_table(path):
    """Read CSV/TSV or the first sheet of XLS/XLSX into strings.

    The historic Oppland .xls is tab-separated text, detected by signature.
    Additional Excel sheets can be exported as CSV before importing.
    """
    path=Path(path);data=path.read_bytes()
    if data.startswith(b'PK') or data.startswith(bytes.fromhex('D0CF11E0')):
        import pandas as pd
        df=pd.read_excel(path,header=None,dtype=str).fillna('')
        rows=df.values.tolist()
    else:
        try:text=data.decode('utf-8-sig')
        except UnicodeDecodeError:text=data.decode('latin1')
        try:dialect=csv.Sniffer().sniff(text[:10000],delimiters='\t,;')
        except csv.Error:dialect=csv.excel_tab
        rows=list(csv.reader(io.StringIO(text),dialect))
    if not rows:raise ValueError('The file is empty.')
    width=max(map(len,rows));return [r+['']*(width-len(r)) for r in rows]

def series_from_table(rows, value_col, year_col, first_data_row, name, metadata=None):
    """Import selected columns without silently skipping interior missing rings.

    Leading and trailing blank pairs are permitted for side-by-side series.
    With no year column, row order defines successive sample rings.
    """
    selected=[]
    for row in rows[first_data_row:]:
        value=row[value_col].strip(); year=row[year_col].strip() if year_col is not None else ''
        selected.append((year,value))
    while selected and not any(selected[0]):selected.pop(0)
    while selected and not any(selected[-1]):selected.pop()
    values=[];years=[]
    for year,value in selected:
        if not value:raise ValueError('Missing width inside series. Resolve gaps explicitly before importing.')
        try:values.append(float(value.replace(',','.')))
        except ValueError:raise ValueError(f'Not a numeric width: {value!r}. Check columns and first data row.')
        if year_col is not None:
            try:
                y=float(year)
                if not y.is_integer():raise ValueError()
                years.append(int(y))
            except ValueError:raise ValueError(f'Invalid calendar year: {year!r}.')
    if years and np.any(np.diff(years)!=1):
        raise ValueError('Years must increase consecutively by one; sort or resolve gaps first.')
    s=Series(name,values,years[0] if years else None,**(metadata or {}));s.validate();return s

def write_csv(path, header, rows):
    """Write UTF-8 CSV with BOM for convenient opening in Excel."""
    with Path(path).open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.writer(stream);writer.writerow(header);writer.writerows(rows)
