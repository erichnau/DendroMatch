"""Table preview and explicit column selection for measurement imports."""
from pathlib import Path
from PySide6 import QtWidgets as Q
from ..dataio import read_table,series_from_table

class ImportDialog(Q.QDialog):
    """Preview a table and map its year/width columns to one annual series."""
    def __init__(self,path,reference=False,parent=None):
        """Load a table without changing the current project."""
        super().__init__(parent);self.rows=read_table(path);self.reference=reference;self.result_series=None
        self.setWindowTitle('Import reference' if reference else 'Import sample');self.resize(850,650)
        layout=Q.QVBoxLayout(self);form=Q.QFormLayout();layout.addLayout(form)
        self.name=Q.QLineEdit(Path(path).stem);form.addRow('Name',self.name)
        self.year=Q.QComboBox();self.value=Q.QComboBox();self.year.addItem('None — consecutive rows',None)
        for i in range(len(self.rows[0])):
            label=f'{i+1}: {self.rows[0][i][:60]}'
            self.year.addItem(label,i);self.value.addItem(label,i)
        if len(self.rows[0])>1:self.year.setCurrentIndex(1);self.value.setCurrentIndex(1)
        form.addRow('Calendar-year column (optional for samples)',self.year);form.addRow('Width column',self.value)
        self.first=Q.QSpinBox();self.first.setRange(1,len(self.rows));self.first.setValue(2)
        form.addRow('First data row (1-based)',self.first)
        self.start=Q.QSpinBox();self.start.setRange(-10000,10000);self.start.setValue(1000)
        form.addRow('Reference start year if no year column',self.start)
        self.metadata={}
        for key,label,default in [('species','Species',''),('region','Region',''),('units','Units (no conversion)','unspecified'),('source','Source / permission',str(path)),('notes','Notes','')]:
            w=Q.QLineEdit(default);self.metadata[key]=w;form.addRow(label,w)
        table=Q.QTableWidget(min(len(self.rows),30),len(self.rows[0]))
        table.setHorizontalHeaderLabels([str(i+1) for i in range(len(self.rows[0]))])
        for i,row in enumerate(self.rows[:30]):
            for j,v in enumerate(row):table.setItem(i,j,Q.QTableWidgetItem(v))
        table.setEditTriggers(Q.QAbstractItemView.EditTrigger.NoEditTriggers);layout.addWidget(table)
        hint=Q.QLabel('Preview: first 30 rows. No rows are silently removed inside a series.\nSample calendar dates are retained as metadata but never constrain matching.');layout.addWidget(hint)
        buttons=Q.QDialogButtonBox(Q.QDialogButtonBox.StandardButton.Ok|Q.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept_data);buttons.rejected.connect(self.reject);layout.addWidget(buttons)

    def accept_data(self):
        """Validate selected columns before closing the dialog."""
        try:
            s=series_from_table(self.rows,self.value.currentData(),self.year.currentData(),self.first.value()-1,self.name.text(),{k:w.text() for k,w in self.metadata.items()})
            if self.reference and s.start_year is None:s.start_year=self.start.value()
            s.validate(self.reference);self.result_series=s;self.accept()
        except Exception as e:Q.QMessageBox.warning(self,'Import',str(e))
