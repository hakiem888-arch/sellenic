import json
import ast
import math
import sqlite3
from datetime import datetime, timedelta
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest
from modules.growth_engine import ResearchStore, seo_audit, parse_chapters, gap_candidates, metadata_check
from modules.growth_ui import normalize_report, ai_package

SCRIPT='''
from tests.fixtures_ui import SERVICES
from modules.simple_ui import render_app
render_app(SERVICES)
'''

class GrowthTest(unittest.TestCase):
    def test_relevance_and_missing_content(self):
        weak=seo_audit('Judul panjang salah topik','Tidak sesuai',[],'relaksasi ibu hamil','')
        good=seo_audit('Relaksasi ibu hamil dengan napas dalam','Relaksasi ibu hamil',[],'relaksasi ibu hamil','Relaksasi ibu hamil')
        self.assertGreater(good['score'],weak['score']);self.assertTrue(weak['warnings'])
        self.assertEqual(good['checks'][4]['Poin'],25)
        self.assertEqual(metadata_check('Judul tentang topik tertentu','Deskripsi',[]),metadata_check('Judul tentang topik tertentu','Deskripsi',['a','b','c']))

    def test_chapters_do_not_invent_timestamps(self):
        for text in ['Tanpa waktu','00:10 Awal\n00:20 Tengah\n00:40 Akhir','00:00 Awal\n00:05 Tengah\n00:40 Akhir']:
            self.assertEqual(parse_chapters(text)[0],[])
        self.assertEqual(len(parse_chapters('00:00 Awal\n00:20 Tengah\n00:40 Akhir')[0]),3)

    def test_persistence_and_atomic_restore(self):
        with tempfile.TemporaryDirectory() as path:
            db=ResearchStore(path);db.save('watchlist','a',{'video':{'title':'Referensi'}})
            self.assertEqual(len(ResearchStore(path).list('watchlist')),1)
            backup=json.loads(db.export());broken=json.loads(db.export());broken['watchlist'].append({'id':'bad','payload':None})
            with self.assertRaises(ValueError): db.restore(broken)
            self.assertEqual(len(db.list('watchlist')),1)
            db.delete('watchlist','a');db.restore(backup)
            self.assertEqual(len(db.list('watchlist')),1)

    def test_history_limit(self):
        with tempfile.TemporaryDirectory() as path:
            db=ResearchStore(path)
            for i in range(40): db.save('history',str(i),{'query':str(i)})
            self.assertEqual(len(db.list('history')),30)

    def test_report_totals_and_validation(self):
        df=pd.DataFrame({'Video title':['Total','A','B'],'Views':[30,10,20], 'Impressions click-through rate (%)':[5,3,7],'Average percentage viewed (%)':[50,40,60]})
        frame=normalize_report(df);self.assertEqual(frame['views'].sum(),30);self.assertEqual(len(frame),2)
        df.loc[1,'Average percentage viewed (%)']=125
        self.assertEqual(normalize_report(df)['retention'].max(),125)
        df.loc[1,'Impressions click-through rate (%)']=101
        with self.assertRaises(ValueError):normalize_report(df)
        with self.assertRaises(ValueError):normalize_report(pd.DataFrame({'Views':[10]}))

    def test_gap_counts(self):
        result=gap_candidates('python',[{'title':'Tutorial langkah belajar python','description':''}])
        self.assertEqual(next(r for r in result if r['Sudut pembahasan']=='Langkah praktis')['Cakupan sampel'],1)

    def test_ai_failure_paths(self):
        self.assertIsNone(ai_package(SimpleNamespace(GEMINI_API_KEY=''),{})[0])
        with patch('modules.growth_ui.requests.post') as post:
            post.return_value=SimpleNamespace(ok=False,status_code=429)
            answer,error=ai_package(SimpleNamespace(GEMINI_API_KEY='dummy'),{'content':'Isi'})
            self.assertIsNone(answer);self.assertIn('429',error);self.assertNotIn('dummy',error)

    def click(self,app,label):
        next(b for b in app.button if b.label==label).click().run()
        self.assertEqual([e.message for e in app.exception],[])

    def test_studio_audit_save_and_navigation(self):
        with tempfile.TemporaryDirectory() as path,patch.dict('os.environ',{'NICHE_HUNTER_DATA_DIR':path}):
            app=AppTest.from_string(SCRIPT,default_timeout=30);app.secrets['YOUTUBE_API_KEY']='TEST_ONLY';app.run()
            app.radio(key='nav_section').set_value('Studio').run()
            app.text_input(key='seo_keyword').set_value('relaksasi ibu hamil')
            app.text_input(key='seo_title').set_value('Relaksasi ibu hamil dengan napas dalam')
            app.text_area(key='seo_content').set_value('Relaksasi ibu hamil dengan napas dalam.')
            self.click(app,'Audit dan siapkan brief');self.click(app,'Simpan brief ke ruang riset')
            self.assertEqual(len(ResearchStore(path).list('brief')),1)
            for page in ['Ruang riset','Evaluasi channel','SEO Studio']:
                app.radio(key='nav_Studio').set_value(page).run();self.assertEqual([e.message for e in app.exception],[])

    def test_search_watchlist_and_seo_handoff(self):
        with tempfile.TemporaryDirectory() as path,patch.dict('os.environ',{'NICHE_HUNTER_DATA_DIR':path}):
            app=AppTest.from_string(SCRIPT,default_timeout=30);app.secrets['YOUTUBE_API_KEY']='TEST_ONLY';app.run()
            app.text_input(key='field_video_query').set_value('simulasi');self.click(app,'Cari video')
            self.click(app,'Simpan watchlist');self.assertEqual(len(ResearchStore(path).list('watchlist')),1)
            self.assertEqual(len(ResearchStore(path).list('history')),1)
            self.click(app,'Optimalkan ide ini');self.assertEqual(app.radio(key='nav_section').value,'Studio')
            self.assertIn('Data simulasi',app.text_input(key='seo_title').value)

    def test_entrypoint_without_credentials(self):
        with tempfile.TemporaryDirectory() as path,patch.dict('os.environ',{'NICHE_HUNTER_DATA_DIR':path}):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
            self.assertEqual([e.message for e in app.exception],[])
            app.radio(key='nav_section').set_value('Studio').run();self.assertEqual([e.message for e in app.exception],[])


class SnapshotTest(unittest.TestCase):
    def backend(self, path):
        ns={'datetime':datetime,'sqlite3':sqlite3,'math':math,'SNAPSHOT_DB':str(Path(path)/'snapshots.db')}
        source=ast.parse((Path(__file__).resolve().parents[1]/'app.py').read_text())
        names={'init_snapshot_db','save_video_snapshots','get_snapshot_history','calculate_v2_velocity_and_acceleration','calculate_breakout_score','normalize_score'}
        for node in source.body:
            if isinstance(node,ast.FunctionDef) and node.name in names:
                exec(compile(ast.Module(body=[node],type_ignores=[]),'app.py','exec'),ns)
        ns['init_snapshot_db']()
        return ns

    def test_snapshot_interval_and_velocity(self):
        with tempfile.TemporaryDirectory() as path:
            ns=self.backend(path);video={'id':'v','views':300,'vph':50}
            ns['save_video_snapshots']([video]);ns['save_video_snapshots']([video])
            self.assertEqual(len(ns['get_snapshot_history']('v')),1)
            velocity,accel,previous,count=ns['calculate_v2_velocity_and_acceleration'](video)
            self.assertEqual((velocity,count),(50,0))
            with sqlite3.connect(ns['SNAPSHOT_DB']) as conn:
                conn.execute('DELETE FROM video_snapshots')
                for age,views in [(2,100),(1,200)]:
                    conn.execute('INSERT INTO video_snapshots(video_id,captured_at,views) VALUES(?,?,?)',('v',(datetime.utcnow()-timedelta(hours=age)).isoformat(),views))
            velocity,accel,previous,count=ns['calculate_v2_velocity_and_acceleration'](video)
            self.assertAlmostEqual(velocity,100,places=1);self.assertAlmostEqual(accel,1,places=1);self.assertEqual(count,2)

    def test_no_acceleration_points_without_evidence(self):
        with tempfile.TemporaryDirectory() as path:
            ns=self.backend(path)
            video={'velocity_vph':1000,'acceleration':10,'snapshot_count':0,'channel_baseline_samples':0}
            ns['calculate_breakout_score'](video)
            component=next(c for c in video['score_components'] if c['Komponen']=='Akselerasi')
            self.assertEqual(component['Kontribusi'],0);self.assertEqual(video['score_evidence'],'Terbatas')
            video['snapshot_count']=2;video['channel_baseline_samples']=5
            score=ns['calculate_breakout_score'](video)
            self.assertTrue(0<=score<=100);self.assertAlmostEqual(sum(c['Kontribusi'] for c in video['score_components']),score,delta=.3)

class ReportUITest(unittest.TestCase):
    def test_uploaded_report_mapping_and_chart(self):
        script='''
import io
from types import SimpleNamespace
from unittest.mock import patch
from modules.growth_ui import evaluation_page
class Upload(io.BytesIO):
    @property
    def size(self): return len(self.getvalue())
file=Upload(b'Video title,Views,Impressions click-through rate (%),Average percentage viewed (%)\\nTotal,300,5,60\\nA,100,4,40\\nB,200,6,80\\n')
with patch('streamlit.file_uploader',return_value=file):
    evaluation_page(SimpleNamespace())
'''
        app=AppTest.from_string(script,default_timeout=30).run()
        self.assertEqual([e.message for e in app.exception],[])
        next(b for b in app.button if b.label=='Analisis laporan').click().run()
        self.assertEqual([e.message for e in app.exception],[])
        self.assertEqual(len(app.session_state['owner_report']['frame']),2)
        self.assertEqual(next(m.value for m in app.metric if m.label=='Total views'),'300')
