"""Offscreen desktop workflow tests; no Windows IDE automation is implied."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import csv,tempfile,time,unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from dendromatch.ui.main_window import MainWindow
from dendromatch.matching import search
from dendromatch.project import load_project,save_project

class DesktopTests(unittest.TestCase):
    """Exercise candidate review, background search, exports and invalidation."""
    @classmethod
    def setUpClass(cls):
        """Share a single Qt application across desktop tests."""
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        """Open the bundled example without a file chooser."""
        self.w=MainWindow();self.w.example();self.w.error=lambda msg: self.fail(str(msg));self.w.show();self.app.processEvents()
    def tearDown(self):
        """Close without unsaved-change dialogs."""
        self.w.dirty=False;self.w.close()
    def test_review_export_and_staleness(self):
        """Changing selection and display works; numerical edits clear results."""
        w=self.w;w.search_ready(search(w.sample,w.references,w.settings()))
        w.table.selectRow(1);self.app.processEvents();self.assertEqual(w.selected()[0].sample_start,1501)
        w.table.selectRow(0);w.display.setCurrentText('Original values');self.app.processEvents()
        with tempfile.TemporaryDirectory() as folder:
            w.export_to(folder)
            with (Path(folder)/'candidates.csv').open(encoding='utf-8-sig') as f:
                rows=list(csv.DictReader(f));self.assertEqual(len(rows),817);self.assertEqual(rows[0]['sample_start'],'1292')
            with (Path(folder)/'selected_overlap.csv').open(encoding='utf-8-sig') as f:
                rows=list(csv.DictReader(f));self.assertEqual(len(rows),334);self.assertEqual(rows[0]['sample_original'],'111.0')
            project=Path(folder)/'p.json';save_project(project,w.sample,w.references,w.settings(),checked_references=[])
            w.load_path(project);self.assertEqual(w.refs.item(0).checkState(),Qt.CheckState.Unchecked)
        w.search_ready(search(w.sample,w.references,w.settings()));w.first.setValue(2)
        self.assertIsNone(w.output);self.assertEqual(w.table.rowCount(),0)
    def test_worker_search(self):
        """Background search returns and restores editable controls."""
        w=self.w;w.run_search();deadline=time.monotonic()+15
        while w.worker is not None and time.monotonic()<deadline:self.app.processEvents()
        self.assertIsNone(w.worker);self.assertIsNotNone(w.output)
        self.assertEqual(w.selected()[0].sample_start,1292);self.assertTrue(w.centralWidget().isEnabled())

if __name__=='__main__':unittest.main()
