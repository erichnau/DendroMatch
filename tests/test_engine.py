"""Regression tests for lag indexing, processing and portable data handling."""
import unittest,tempfile
from pathlib import Path
import numpy as np
from dendromatch.models import Series,SearchSettings
from dendromatch.processing import METHODS,transform
from dendromatch.matching import search,segment_check,Cancelled
from dendromatch.project import load_project,save_project
from dendromatch.dataio import series_from_table,read_table

EXAMPLE=Path(__file__).resolve().parents[1]/'examples'/'Oppland_Vaga.dmatch.json'

class EngineTests(unittest.TestCase):
    """Check known data and deliberately constructed failure cases."""
    def test_known_age_and_dates_ignored(self):
        """Reproduce the Vågå search without using its calendar labels."""
        sample,refs,settings,_,_,_=load_project(EXAMPLE)
        for method in METHODS[:3]:
            settings.method=method;sample.start_year=9999
            out=search(sample,refs,settings)
            self.assertEqual(len(out.results),817)
            self.assertEqual(out.results[0].sample_start,1292)
            self.assertEqual(out.results[0].sample_end,1625)
        settings.method=METHODS[0]
        best=search(sample,refs,settings).results[0]
        self.assertAlmostEqual(best.r,.330834400042422,12)
        self.assertAlmostEqual(best.t,6.349196531199149,10)

    def test_subset_mapping_and_scale(self):
        """Partial-interval searches report the full sample's start correctly."""
        rng=np.random.default_rng(6);data=rng.lognormal(0,.3,400)
        ref=Series('R',data.tolist(),1000)
        sample=Series('S',(data[123:223]*100).tolist())
        for method in METHODS:
            settings=SearchSettings(method=method,first=20,last=85,min_pairs=30)
            out=search(sample,[ref],settings);m=out.results[0]
            self.assertEqual(m.sample_start,1123);self.assertEqual(m.interval_start,1143)
            self.assertAlmostEqual(m.r,1.,12)
        self.assertTrue(segment_check(sample,ref,1123,METHODS[0]))

    def test_transforms_and_validation(self):
        """Verify a hand-calculated BP value and reject invalid data."""
        x=np.array([1,2,4,2,1,3,2],float)
        bp,off=transform(x,METHODS[0]);self.assertEqual(off,2)
        self.assertAlmostEqual(bp[0],np.log(100*4/2))
        for invalid in [[1]*60,[0]*60]:
            with self.assertRaises(ValueError):search(Series('S',invalid),[Series('R',[1,2]*100,1000)],SearchSettings(last=59))
        with self.assertRaises(Cancelled):
            search(Series('S',[1,2]*30),[Series('R',[1,2]*100,1000)],SearchSettings(last=59),cancelled=lambda:True)

    def test_import_and_project_roundtrip(self):
        """Preserve source data and reject missing years/widths."""
        rows=[['year','ref','','year','sample']]+[[str(1000+i),str(i+1),'',str(1300+i),str(i+2)] for i in range(20)]
        s=series_from_table(rows,4,3,1,'sample');r=series_from_table(rows,1,0,1,'ref')
        self.assertEqual(s.start_year,1300)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'x.json';save_project(path,s,[r],SearchSettings(last=19))
            a,b,_,_,_,_=load_project(path);self.assertEqual(a.values,s.values);self.assertEqual(b[0].values,r.values)
            tab=Path(folder)/'fake.xls';tab.write_text('year\tvalue\n'+'\n'.join(f'{1000+i}\t{i+1}' for i in range(20)))
            self.assertEqual(len(read_table(tab)),21)
        bad=[row.copy() for row in rows];bad[8][4]=''
        with self.assertRaises(ValueError):series_from_table(bad,4,3,1,'bad')
        bad=[row.copy() for row in rows];bad[8][3]='5000'
        with self.assertRaises(ValueError):series_from_table(bad,4,3,1,'bad')

if __name__=='__main__':unittest.main()
