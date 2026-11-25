"""Desktop crossdating workbench with background search and linked result views."""
import copy
from pathlib import Path
from dataclasses import asdict,fields
import numpy as np
from PySide6 import QtWidgets as Q,QtCore as C
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg,NavigationToolbar2QT
from ..models import SearchSettings
from ..processing import METHODS,transform,smooth,normalise
from ..matching import search,segment_check,Cancelled
from ..project import save_project,load_project,save_library,load_library,write_json
from ..dataio import write_csv
from .import_dialog import ImportDialog

class Plot(Q.QWidget):
    """A Matplotlib canvas with standard pan, zoom and graph export tools."""
    def __init__(self,count=1,parent=None):
        """Create vertically stacked axes."""
        super().__init__(parent);layout=Q.QVBoxLayout(self)
        self.figure=Figure(layout='constrained');self.canvas=FigureCanvasQTAgg(self.figure)
        self.axes=np.atleast_1d(self.figure.subplots(count,1))
        layout.addWidget(NavigationToolbar2QT(self.canvas,self));layout.addWidget(self.canvas)

class Worker(C.QThread):
    """Run numerical searches without blocking the interface."""
    ready=C.Signal(object);failure=C.Signal(str);progress=C.Signal(int)
    def __init__(self,sample,refs,settings,parent=None):
        """Freeze input data to prevent changes during computation."""
        super().__init__(parent);self.args=copy.deepcopy((sample,refs,settings))
    def run(self):
        """Execute the independent matching engine and deliver its result."""
        try:self.ready.emit(search(*self.args,cancelled=self.isInterruptionRequested,progress=self.progress.emit))
        except Cancelled:self.failure.emit('Search cancelled.')
        except Exception as e:self.failure.emit(str(e))

class MainWindow(Q.QMainWindow):
    """Coordinate imports, search settings, candidate review and project state."""
    def __init__(self):
        """Build a blank workbench; no dating is silently accepted."""
        super().__init__();self.resize(1550,1000);self.setWindowTitle('DendroMatch 0.1 — exploratory crossdating')
        self.sample=None;self.references=[];self.output=None;self.worker=None;self.dirty=False;self.path=None;self.loading=False
        self.build_ui();self.update_overview()

    def build_ui(self):
        """Create file tools, reference browser, plots and matching controls."""
        bar=self.addToolBar('Project')
        for title,slot in [('Open project',self.open_project),('Save project',self.save),('Load Oppland/Vågå example',self.example),('Import reference',lambda:self.import_series(True)),('Import sample',lambda:self.import_series(False)),('Export results',self.export_results),('Export graph',self.export_graph)]:
            bar.addAction(title,slot)
        splitter=Q.QSplitter();self.setCentralWidget(splitter)
        left=Q.QWidget();left.setMinimumWidth(295);left.setMaximumWidth(380);ll=Q.QVBoxLayout(left)
        ll.addWidget(Q.QLabel('REFERENCE LIBRARY — check curves to search'))
        self.refs=Q.QListWidget();self.refs.itemChanged.connect(self.invalidate);self.refs.currentRowChanged.connect(self.update_overview);ll.addWidget(self.refs,2)
        row=Q.QHBoxLayout();ll.addLayout(row)
        for title,slot in [('Details',self.reference_details),('Remove',self.remove_reference),('Load library',self.open_library),('Save library',self.save_ref_library)]:
            b=Q.QPushButton(title);b.clicked.connect(slot);row.addWidget(b)
        self.sample_label=Q.QLabel('No sample loaded');self.sample_label.setWordWrap(True);ll.addWidget(self.sample_label)
        b=Q.QPushButton('Inspect sample data / metadata');b.clicked.connect(self.sample_details);ll.addWidget(b)
        form=Q.QFormLayout();ll.addLayout(form)
        self.method=Q.QComboBox();self.method.addItems(METHODS);form.addRow('Matching method',self.method)
        self.first=Q.QSpinBox();self.last=Q.QSpinBox()
        for w in (self.first,self.last):w.setRange(1,100000)
        self.last.setValue(334)
        form.addRow('First sample ring',self.first);form.addRow('Last sample ring',self.last)
        self.min_start=Q.QSpinBox();self.max_start=Q.QSpinBox()
        for w in (self.min_start,self.max_start):w.setRange(-10000,10000)
        self.max_start.setValue(3000)
        form.addRow('Full sample start ≥',self.min_start);form.addRow('Full sample start ≤',self.max_start)
        self.pairs=Q.QSpinBox();self.pairs.setRange(3,10000);self.pairs.setValue(50);form.addRow('Minimum processed pairs',self.pairs)
        self.sigma=Q.QDoubleSpinBox();self.sigma.setRange(0,20);self.sigma.setDecimals(1);self.sigma.setSingleStep(.5)
        form.addRow('Pre-smoothing σ (years)',self.sigma)
        for w in (self.first,self.last,self.min_start,self.max_start,self.pairs,self.sigma):
            w.setKeyboardTracking(False);w.valueChanged.connect(self.invalidate)
        self.method.currentTextChanged.connect(self.invalidate)
        self.display=Q.QComboBox();self.display.addItems(['Z-score','Original values','Mean division']);form.addRow('Overlay display scale',self.display)
        self.display.currentTextChanged.connect(self.display_changed)
        self.run_button=Q.QPushButton('Run matching');self.run_button.clicked.connect(self.run_search);ll.addWidget(self.run_button)
        self.cancel=Q.QPushButton('Cancel search');self.cancel.clicked.connect(self.cancel_search);self.cancel.setEnabled(False);ll.addWidget(self.cancel)
        self.progress=Q.QProgressBar();ll.addWidget(self.progress)
        self.notes=Q.QPlainTextEdit();self.notes.setPlaceholderText('Project notes: interpretation, reference independence, sample condition…');self.notes.textChanged.connect(self.mark_dirty);self.notes.setMaximumHeight(90);ll.addWidget(self.notes)
        hint=Q.QLabel('Search uses the selected consecutive rings with full overlap. Sample dates never guide the search.\n\nSmoothing defaults to OFF. BP5 and log ratios emphasise annual changes. Display normalisation does not detrend.\n\nScores are not confidence percentages. Check replication, segment consistency and whether the sample contributed to a reference.');hint.setWordWrap(True);ll.addWidget(hint)
        splitter.addWidget(left)
        right=Q.QSplitter(C.Qt.Orientation.Vertical);splitter.addWidget(right)
        self.tabs=Q.QTabWidget();right.addWidget(self.tabs)
        self.overview=Plot(2);self.alignment=Plot(2);self.scores=Plot();self.segments=Plot()
        for plot,label in [(self.overview,'Input curves'),(self.alignment,'Candidate alignment'),(self.scores,'Search scores'),(self.segments,'Segment check')]:self.tabs.addTab(plot,label)
        self.scores.canvas.mpl_connect('button_press_event',self.score_clicked)
        self.overview.canvas.mpl_connect('button_press_event',self.range_press)
        self.overview.canvas.mpl_connect('button_release_event',self.range_release)
        self.range_anchor=None
        self.table=Q.QTableWidget(0,9);self.table.setHorizontalHeaderLabels(['Rank','Reference','Sample start','Sample end','Interval years','Pairs','r','t score','GLK %'])
        self.table.setSelectionBehavior(Q.QAbstractItemView.SelectionBehavior.SelectRows);self.table.setEditTriggers(Q.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.review_candidate);self.table.horizontalHeader().setStretchLastSection(True)
        right.addWidget(self.table);right.setSizes([680,240]);splitter.setSizes([340,1210])
        self.statusBar().showMessage('Load the supplied example or import a reference and sample.')

    def settings(self):
        """Read controls into a plain serializable search definition."""
        return SearchSettings(self.method.currentText(),self.first.value()-1,self.last.value()-1,self.min_start.value(),self.max_start.value(),self.sigma.value(),self.pairs.value())

    def mark_dirty(self,*_):
        """Mark editable project state as changed."""
        if not self.loading:self.dirty=True

    def display_changed(self,*_):
        """Change plot scaling without invalidating numerical matching results."""
        self.mark_dirty();self.review_candidate()

    def invalidate(self,*_):
        """Remove stale matches whenever data selection or search settings change."""
        if self.loading:return
        self.dirty=True;self.output=None;self.table.setRowCount(0)
        for plot in (self.alignment,self.scores,self.segments):
            for ax in plot.axes:ax.clear()
            plot.canvas.draw_idle()
        self.update_overview();self.statusBar().showMessage('Inputs changed. Run matching to calculate fresh results.')

    def set_inputs(self,sample,refs,settings=None,display='Z-score',notes='',checked=None):
        """Replace a session after its data have been validated."""
        self.loading=True;self.sample=sample;self.references=refs;self.refs.clear()
        for ref in refs:
            item=Q.QListWidgetItem(ref.name);item.setFlags(item.flags()|C.Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(C.Qt.CheckState.Checked if checked is None or ref.name in checked else C.Qt.CheckState.Unchecked);self.refs.addItem(item)
        if refs:self.refs.setCurrentRow(0)
        if sample:
            for w in (self.first,self.last):w.setMaximum(len(sample.values))
        s=settings or SearchSettings(last=len(sample.values)-1 if sample else 333)
        self.method.setCurrentText(s.method);self.first.setValue(s.first+1);self.last.setValue(s.last+1)
        self.min_start.setValue(s.min_start);self.max_start.setValue(s.max_start);self.sigma.setValue(s.smoothing_sigma);self.pairs.setValue(s.min_pairs)
        self.display.setCurrentText(display);self.notes.setPlainText(notes);self.loading=False;self.invalidate()

    def update_overview(self,*_):
        """Show reference in calendar years and sample in relative ring numbers."""
        for ax in self.overview.axes:ax.clear()
        i=self.refs.currentRow()
        if 0<=i<len(self.references):
            ref=self.references[i];ax=self.overview.axes[0];ax.plot(np.arange(len(ref.values))+ref.start_year,ref.values,lw=.9)
            ax.set_title(f'{ref.name} · {ref.start_year}–{ref.end_year}');ax.set_ylabel(ref.units);ax.set_xlabel('Calendar year')
        if self.sample:
            s=self.sample;ax=self.overview.axes[1];ax.plot(np.arange(len(s.values))+1,s.values,color='#C46A12',lw=1)
            ax.axvspan(self.first.value(),self.last.value(),color='#2463A6',alpha=.12)
            ax.set_title(f'{s.name} · {len(s.values)} rings · shift-drag to select interval');ax.set_xlabel('Relative ring number (1-based)');ax.set_ylabel(s.units)
            self.sample_label.setText(f'Sample: {s.name}\n{len(s.values)} widths · {s.units}\nExisting dates: {s.start_year}–{s.end_year}' if s.start_year is not None else f'Sample: {s.name}\n{len(s.values)} widths · {s.units}\nUndated')
        for ax in self.overview.axes:ax.grid(alpha=.2)
        self.overview.canvas.draw_idle()

    def range_press(self,event):
        """Start interval selection only with Shift on the sample plot."""
        if event.inaxes is self.overview.axes[1] and event.key=='shift' and event.xdata is not None:self.range_anchor=event.xdata

    def range_release(self,event):
        """Convert the dragged range into bounded, inclusive ring numbers."""
        if self.range_anchor is None:return
        anchor=self.range_anchor;self.range_anchor=None
        if event.inaxes is not self.overview.axes[1] or not self.sample:return
        a,b=sorted([int(round(anchor)),int(round(event.xdata))]);a=max(1,min(a,len(self.sample.values)));b=max(a,min(b,len(self.sample.values)))
        self.first.setValue(a);self.last.setValue(b)

    def import_series(self,reference):
        """Import a reference or sample using an explicit table-column mapping."""
        path,_=Q.QFileDialog.getOpenFileName(self,'Import measurements','','Tables (*.csv *.tsv *.txt *.xls *.xlsx);;All files (*)')
        if not path:return
        try:
            dialog=ImportDialog(path,reference,self)
            if dialog.exec()!=Q.QDialog.DialogCode.Accepted:return
            s=dialog.result_series
            if reference:
                if s.name in [r.name for r in self.references]:raise ValueError('Reference name already exists. Use a unique name.')
                self.references.append(s);item=Q.QListWidgetItem(s.name);item.setFlags(item.flags()|C.Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(C.Qt.CheckState.Checked);self.refs.addItem(item);self.refs.setCurrentRow(len(self.references)-1)
            else:
                self.sample=s
                self.loading=True
                for w in (self.first,self.last):w.setMaximum(len(s.values))
                self.first.setValue(1);self.last.setValue(len(s.values));self.loading=False
            self.invalidate()
        except Exception as e:self.error(e)

    def remove_reference(self):
        """Remove a selected reference from this project, without altering source files."""
        i=self.refs.currentRow()
        if i>=0:self.references.pop(i);self.refs.takeItem(i);self.invalidate()

    def show_series(self,series):
        """Display exact original values and provenance without editing them."""
        dialog=Q.QDialog(self);dialog.setWindowTitle(series.name);dialog.resize(600,650);layout=Q.QVBoxLayout(dialog)
        label=Q.QLabel('\n'.join(f'{k}: {v}' for k,v in asdict(series).items() if k!='values'));label.setWordWrap(True);layout.addWidget(label)
        table=Q.QTableWidget(len(series.values),3);table.setHorizontalHeaderLabels(['Ring','Calendar year','Original value'])
        for i,v in enumerate(series.values):
            for j,text in enumerate([str(i+1),str(series.start_year+i) if series.start_year is not None else '',str(v)]):table.setItem(i,j,Q.QTableWidgetItem(text))
        table.setEditTriggers(Q.QAbstractItemView.EditTrigger.NoEditTriggers);layout.addWidget(table);dialog.exec()

    def reference_details(self):
        """Inspect the selected reference metadata and measurements."""
        i=self.refs.currentRow()
        if i>=0:self.show_series(self.references[i])

    def sample_details(self):
        """Inspect sample metadata and measurements."""
        if self.sample:self.show_series(self.sample)

    def run_search(self):
        """Launch a background full-overlap search of checked references."""
        if not self.sample:self.error('Import a sample first.');return
        refs=[r for i,r in enumerate(self.references) if self.refs.item(i).checkState()==C.Qt.CheckState.Checked]
        if not refs:self.error('Check at least one reference.');return
        self.output=None;self.table.setRowCount(0);self.progress.setValue(0)
        for plot in (self.alignment,self.scores,self.segments):
            for ax in plot.axes:ax.clear()
            plot.canvas.draw_idle()
        self.worker=Worker(self.sample,refs,self.settings(),self)
        self.worker.ready.connect(self.search_ready);self.worker.failure.connect(self.search_failed);self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self.search_finished);self.set_busy(True);self.worker.start()

    def set_busy(self,busy):
        """Prevent project mutations while a frozen search is running."""
        self.centralWidget().setEnabled(not busy)
        # Cancellation remains available from the status bar while central controls are disabled.
        if busy:
            self.stop_button=Q.QPushButton('Cancel search');self.stop_button.clicked.connect(self.cancel_search);self.statusBar().addPermanentWidget(self.stop_button)
        elif hasattr(self,'stop_button'):
            self.statusBar().removeWidget(self.stop_button);self.stop_button.deleteLater();del self.stop_button
        for toolbar in self.findChildren(Q.QToolBar):toolbar.setEnabled(not busy)
        self.cancel.setEnabled(busy)

    def cancel_search(self):
        """Request cooperative cancellation at the next search checkpoint."""
        if self.worker:self.worker.requestInterruption()

    def search_finished(self):
        """Re-enable editing after the worker has completed."""
        self.set_busy(False);self.worker=None

    def search_failed(self,message):
        """Report a failed or cancelled search without stale results."""
        self.statusBar().showMessage(message)
        if message!='Search cancelled.':self.error(message)

    def search_ready(self,output):
        """Populate a ranked candidate list from a frozen numerical result."""
        self.output=output;self.table.blockSignals(True)
        visible=output.results[:1000];self.table.setRowCount(len(visible))
        for i,m in enumerate(visible):
            values=[i+1,m.reference,m.sample_start,m.sample_end,f'{m.interval_start}–{m.interval_end}',m.pairs,f'{m.r:.4f}',f'{m.t:.3f}',f'{m.glk:.1f}']
            for j,v in enumerate(values):self.table.setItem(i,j,Q.QTableWidgetItem(str(v)))
        self.table.blockSignals(False);self.table.resizeColumnsToContents();self.table.selectRow(0)
        self.draw_scores();self.tabs.setCurrentWidget(self.scores)
        self.statusBar().showMessage(f'{len(output.results)} candidates tested; top {len(visible)} listed. '+ ' '.join(output.warnings))

    def selected(self):
        """Return the currently reviewed candidate and reference snapshot."""
        row=self.table.currentRow()
        if not self.output or row<0:return None,None
        m=self.output.results[row];ref=next(r for r in self.output.references if r.name==m.reference);return m,ref

    def draw_scores(self):
        """Plot score versus full-sample start year for every searched reference."""
        ax=self.scores.axes[0];ax.clear()
        if not self.output:return
        for ref in self.output.references:
            matches=sorted([m for m in self.output.results if m.reference==ref.name],key=lambda m:m.sample_start)
            if matches:ax.plot([m.sample_start for m in matches],[m.r for m in matches],lw=.8,label=ref.name)
        ax.set_title(f'{self.output.settings.method} · {len(self.output.results)} tested placements')
        ax.set_xlabel('Candidate year of FIRST ring of complete sample');ax.set_ylabel('Correlation r');ax.legend();ax.grid(alpha=.2);self.scores.canvas.draw_idle()

    def score_clicked(self,event):
        """Select the nearest plotted candidate among the displayed top 1,000."""
        if not self.output or event.inaxes is None or event.xdata is None or event.canvas.toolbar.mode:return
        options=self.output.results[:1000]
        i=min(range(len(options)),key=lambda i:np.linalg.norm(event.inaxes.transData.transform([options[i].sample_start,options[i].r])-[event.x,event.y]))
        self.table.selectRow(i)

    def review_candidate(self):
        """Show original and processed overlaps plus local segment consistency."""
        m,ref=self.selected()
        if m is None:return
        out=self.output;s=out.settings;b=np.asarray(out.sample.values)[s.first:s.last+1]
        i=m.interval_start-ref.start_year;a=np.asarray(ref.values)[i:i+len(b)]
        years=np.arange(len(b))+m.interval_start;mode=self.display.currentText()
        for ax in self.alignment.axes:ax.clear()
        ax=self.alignment.axes[0]
        ax.plot(years,normalise(a,mode),label=ref.name,lw=1);ax.plot(years,normalise(b,mode),label=out.sample.name,lw=1,alpha=.8)
        ax.set_title(f'Candidate {m.sample_start}–{m.sample_end} · original widths · {mode}');ax.set_ylabel(mode);ax.legend(fontsize=9)
        x,off=transform(smooth(a,s.smoothing_sigma),s.method);y,_=transform(smooth(b,s.smoothing_sigma),s.method)
        ax=self.alignment.axes[1];ax.plot(years[off:off+len(x)],normalise(x),label=ref.name,lw=1);ax.plot(years[off:off+len(y)],normalise(y),label=out.sample.name,lw=1,alpha=.8)
        ax.set_title(f'{s.method} · r={m.r:.3f} · t={m.t:.2f} · {m.pairs} pairs');ax.set_ylabel('Processed z-score');ax.set_xlabel('Calendar year');ax.legend(fontsize=9)
        for ax in self.alignment.axes:ax.grid(alpha=.2)
        self.alignment.canvas.draw_idle()
        rows=segment_check(out.sample,ref,m.sample_start,s.method)
        ax=self.segments.axes[0];ax.clear()
        if rows:
            xx=[r['calendar_start']+24.5 for r in rows]
            ax.plot(xx,[r['r_at_placement'] for r in rows],'-o',label='At candidate date',ms=4)
            ax.plot(xx,[r['best_local_r'] for r in rows],'--',label='Best within ±10 years',alpha=.6)
            for x,r in zip(xx,rows):
                if r['best_local_shift']!=0:ax.annotate(f"{r['best_local_shift']:+d}",(x,r['r_at_placement']),xytext=(0,8),textcoords='offset points',fontsize=8)
            ax.legend()
        ax.set_title('50-ring blocks, 25-ring step · entire sample · no optional pre-smoothing\nLabels indicate a better local shift; this is a diagnostic, not confirmation.',fontsize=10)
        ax.set_xlabel('Block midpoint at candidate calendar placement');ax.set_ylabel('Correlation r');ax.axhline(0,color='gray',lw=.6);ax.grid(alpha=.2);self.segments.canvas.draw_idle()

    def confirm_discard(self):
        """Protect unsaved project edits before loading another session."""
        return not self.dirty or Q.QMessageBox.question(self,'Unsaved project','Discard unsaved project changes?',Q.QMessageBox.StandardButton.Yes|Q.QMessageBox.StandardButton.No,Q.QMessageBox.StandardButton.No)==Q.QMessageBox.StandardButton.Yes

    def example(self):
        """Open the bundled known-age Oppland/Vågå validation project."""
        if self.confirm_discard():self.load_path(Path(__file__).resolve().parents[2]/'examples'/'Oppland_Vaga.dmatch.json')

    def load_path(self,path):
        """Read a project atomically; numerical results require a fresh search."""
        try:
            sample,refs,settings,display,notes,checked=load_project(path);self.set_inputs(sample,refs,settings,display,notes,checked);self.path=Path(path);self.dirty=False
        except Exception as e:self.error(e)

    def open_project(self):
        """Select a saved project without modifying its source measurements."""
        if not self.confirm_discard():return
        name,_=Q.QFileDialog.getOpenFileName(self,'Open project','','DendroMatch (*.json)')
        if name:self.load_path(name)

    def save(self):
        """Save embedded measurements, search settings, display scale and notes."""
        name,_=Q.QFileDialog.getSaveFileName(self,'Save project',str(self.path or 'project.dmatch.json'),'DendroMatch (*.json)')
        if name:
            if not name.endswith('.json'):name+='.dmatch.json'
            try:
                save_project(name,self.sample,self.references,self.settings(),self.display.currentText(),self.notes.toPlainText(),[r.name for i,r in enumerate(self.references) if self.refs.item(i).checkState()==C.Qt.CheckState.Checked]);self.path=Path(name);self.dirty=False;self.statusBar().showMessage('Project saved; all original data embedded.')
            except Exception as e:self.error(e)

    def open_library(self):
        """Merge a saved reference collection, rejecting ambiguous names."""
        name,_=Q.QFileDialog.getOpenFileName(self,'Load reference library','','Library (*.json)')
        if not name:return
        try:
            refs=load_library(name);names=[r.name for r in self.references+refs]
            if len(set(names))!=len(names):raise ValueError('Duplicate reference names. Import with unique names.')
            self.set_inputs(self.sample,self.references+refs,self.settings(),self.display.currentText(),self.notes.toPlainText())
        except Exception as e:self.error(e)

    def save_ref_library(self):
        """Export all loaded references as a reusable portable collection."""
        name,_=Q.QFileDialog.getSaveFileName(self,'Save reference library','references.json','Library (*.json)')
        if name:
            try:save_library(name,self.references)
            except Exception as e:self.error(e)

    def export_to(self,directory):
        """Export all candidates, reviewed overlap, segments and provenance."""
        m,ref=self.selected()
        if m is None:raise ValueError('Run a search and select a candidate first.')
        directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);out=self.output;s=out.settings
        write_csv(directory/'candidates.csv',[f.name for f in fields(m)],[[getattr(r,f.name) for f in fields(r)] for r in out.results])
        b=np.asarray(out.sample.values)[s.first:s.last+1];i=m.interval_start-ref.start_year;a=np.asarray(ref.values)[i:i+len(b)]
        write_csv(directory/'selected_overlap.csv',['calendar_year','sample_ring','reference_original','sample_original'],[[m.interval_start+j,s.first+j+1,float(x),float(y)] for j,(x,y) in enumerate(zip(a,b))])
        x,off=transform(smooth(a,s.smoothing_sigma),s.method);y,_=transform(smooth(b,s.smoothing_sigma),s.method)
        write_csv(directory/'processed_overlap.csv',['calendar_year','reference_processed','sample_processed'],[[m.interval_start+off+j,float(u),float(v)] for j,(u,v) in enumerate(zip(x,y))])
        rows=segment_check(out.sample,ref,m.sample_start,s.method)
        keys=['first_ring','last_ring','calendar_start','r_at_placement','best_local_shift','best_local_r']
        write_csv(directory/'segments.csv',keys,[[r[k] for k in keys] for r in rows])
        write_json(directory/'analysis.json',dict(application='DendroMatch 0.1.0',settings=asdict(s),sample=asdict(out.sample),references=[asdict(r) for r in out.references],selected_candidate=asdict(m),warnings=out.warnings,notes=self.notes.toPlainText(),interpretation='Exploratory candidate. No dating confidence probability or felling date is assigned. GLK ties count as half. Segment check uses no optional smoothing.'))
        self.alignment.figure.savefig(directory/'selected_alignment.png',dpi=180);self.scores.figure.savefig(directory/'search_scores.png',dpi=180)

    def export_results(self):
        """Choose a destination for a complete, auditable analysis export."""
        if not self.output:self.error('Run a search first.');return
        folder=Q.QFileDialog.getExistingDirectory(self,'Choose parent directory for analysis export')
        if folder:
            # Always create a fresh subdirectory, avoiding accidental overwrite.
            import datetime
            target=Path(folder)/datetime.datetime.now().strftime('DendroMatch_%Y%m%d_%H%M%S_%f')
            try:self.export_to(target);self.statusBar().showMessage(f'Exported analysis to {target}')
            except Exception as e:self.error(e)

    def export_graph(self):
        """Save the active plot in a raster or vector format."""
        name,_=Q.QFileDialog.getSaveFileName(self,'Export active graph','DendroMatch.png','PNG (*.png);;PDF (*.pdf);;SVG (*.svg)')
        if name:
            try:self.tabs.currentWidget().figure.savefig(name,dpi=200)
            except Exception as e:self.error(e)

    def error(self,error):
        """Show a recoverable user-facing error."""
        Q.QMessageBox.warning(self,'DendroMatch',str(error))

    def closeEvent(self,event):
        """Cancel active work safely or protect unsaved session changes."""
        if self.worker and self.worker.isRunning():
            self.cancel_search();self.statusBar().showMessage('Cancelling search; close again when it has stopped.');event.ignore();return
        event.accept() if self.confirm_discard() else event.ignore()
