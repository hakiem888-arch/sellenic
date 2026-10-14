"""Regression tests for persistent deletion and first-use evaluation."""
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest
from modules.growth_engine import ResearchStore
from modules.growth_ui import normalize_report

RESEARCH = '''
from types import SimpleNamespace
from modules.growth_ui import research_page
research_page(SimpleNamespace())
'''
EVALUATION = '''
from types import SimpleNamespace
from modules.growth_ui import evaluation_page
evaluation_page(SimpleNamespace())
'''

class UsabilityTest(unittest.TestCase):
    def assert_clean(self, app):
        self.assertEqual([e.message for e in app.exception], [])

    def test_delete_video_and_manual_reference_across_sessions(self):
        with tempfile.TemporaryDirectory() as path, patch.dict(os.environ, {'NICHE_HUNTER_DATA_DIR':path}):
            db=ResearchStore(path)
            db.save('watchlist','video_1',{'video':{'id':'video_1','title':'Video'},'note':'Keep until deleted'})
            db.save('watchlist','manual_1',{'video':{'title':'Niche tanpa video ID','kind':'Niche'},'note':'Catatan'})
            app=AppTest.from_string(RESEARCH,default_timeout=30).run()
            app.text_area(key='note_video_1').set_value('Catatan yang belum disimpan').run()
            app.button(key='del_watch_video_1').click().run()
            self.assert_clean(app)
            self.assertTrue(any('berhasil dihapus' in s.value for s in app.success))
            self.assertEqual([r['id'] for r in ResearchStore(path).list('watchlist')],['manual_1'])
            self.assertFalse(any(b.key=='del_watch_video_1' for b in app.button))
            # A new browser session must see the same committed list.
            second=AppTest.from_string(RESEARCH,default_timeout=30).run()
            second.button(key='del_watch_manual_1').click().run()
            self.assert_clean(second)
            self.assertEqual(db.list('watchlist'),[])
            second.run(); self.assertEqual(db.list('watchlist'),[])
            self.assertTrue(any('0 referensi' in c.value for c in second.caption))

    def test_deletion_failure_is_visible_and_keeps_reference(self):
        with tempfile.TemporaryDirectory() as path, patch.dict(os.environ,{'NICHE_HUNTER_DATA_DIR':path}):
            db=ResearchStore(path);db.save('watchlist','a',{'video':{'title':'Referensi'},'note':''})
            app=AppTest.from_string(RESEARCH,default_timeout=30).run()
            with patch.object(ResearchStore,'delete',side_effect=sqlite3.OperationalError('locked')):
                app.button(key='del_watch_a').click().run()
            self.assert_clean(app)
            self.assertEqual(len(db.list('watchlist')),1)
            self.assertTrue(any('Data belum terhapus' in e.value for e in app.error))

    def test_demo_evaluation_without_credentials_or_upload(self):
        app=AppTest.from_string(EVALUATION,default_timeout=30).run()
        app.radio(key='evaluation_source').set_value('Coba contoh simulasi').run()
        self.assertTrue(any('Data simulasi' in w.value for w in app.warning))
        next(b for b in app.button if b.label=='Analisis laporan').click().run()
        self.assert_clean(app)
        self.assertEqual(next(m.value for m in app.metric if m.label=='Total views'),'4,500')
        app.radio(key='evaluation_source').set_value('Unggah CSV saya').run()
        self.assertEqual(len(app.metric),0)

    def test_indonesian_csv_numbers_and_total_id(self):
        frame=pd.DataFrame({'Konten':['Total','v1','v2'],'Judul video':['','A','B'],
                            'Penayangan':['','1.200','500'],'Rasio klik-tayang tayangan (%)':['','4,5','2,1'],
                            'Persentase penayangan rata-rata (%)':['','125,3','46,5']})
        result=normalize_report(frame, number_format='indonesia')
        self.assertEqual(len(result),2)
        self.assertEqual(result['views'].sum(),1700)
        self.assertEqual(list(result['ctr']),[4.5,2.1])
        self.assertEqual(result['retention'].max(),125.3)

    def test_international_thousands_and_invalid_numbers(self):
        frame=pd.DataFrame({'Title':['A'],'Views':['1,200'],'CTR (%)':['4.5%']})
        result=normalize_report(frame)
        self.assertEqual(result['views'].iloc[0],1200)
        self.assertEqual(result['ctr'].iloc[0],4.5)
        frame.loc[0,'Views']='inf'
        with self.assertRaises(ValueError): normalize_report(frame)

    def test_minimum_columns_do_not_require_ctr(self):
        result=normalize_report(pd.DataFrame({'Judul':['A'],'Penayangan':['12']}))
        self.assertEqual(result['views'].sum(),12)
        self.assertNotIn('ctr',result)
