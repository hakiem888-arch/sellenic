"""Regression and integration tests for the competitive upgrade. All API responses are fixtures."""
import ast
import io
import json
import math
import re
import sqlite3
import statistics
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from streamlit.testing.v1 import AppTest
from modules.growth_engine import ResearchStore, seo_audit
from modules.intelligence import (lifetime_vph, comparable_baseline, keyword_profile, phrase_clusters,
                                  parse_video_id, rank_observation, ctr_experiment, csv_bytes, balanced_ids)
from modules.youtube_client import YouTubeClient, YouTubeError

NOW=datetime(2026,10,14,tzinfo=timezone.utc)
ROOT=Path(__file__).resolve().parents[1]


def video(ident='v', views=1000, hours=24, channel='ch', duration=600):
    return {'id':ident,'raw_views':views,'raw_subs':1000,'published_full':(NOW-timedelta(hours=hours)).isoformat(),
            'channel_id':channel,'duration_seconds':duration,'title':'Belajar Python untuk pemula','description':'Tutorial dasar python'}


def backend_functions(names, **namespace):
    ns={'datetime':datetime,'timedelta':timedelta,'timezone':timezone,'math':math,'re':re,'statistics':statistics,
        'lifetime_vph':lifetime_vph,'comparable_baseline':comparable_baseline,**namespace}
    for node in ast.parse((ROOT/'app.py').read_text()).body:
        if isinstance(node,ast.FunctionDef) and node.name in names:
            exec(compile(ast.Module(body=[node],type_ignores=[]),'app.py','exec'),ns)
    return ns


class IntelligenceTest(unittest.TestCase):
    def test_numeric_vph_avoids_abbreviated_numbers(self):
        self.assertEqual(lifetime_vph(video(views=1200),NOW),50)
        self.assertIsNone(lifetime_vph(video(views='1.2K'),NOW))
        self.assertIsNone(lifetime_vph(video(hours=-1),NOW))

    def test_missing_dates_do_not_become_fresh_uploads(self):
        ns=backend_functions({'parse_yt_date'})
        with self.assertRaises(ValueError):ns['parse_yt_date']('not-a-date')
        self.assertEqual(ns['parse_yt_date']('2026-10-14T07:00:00+07:00'),datetime(2026,10,14))

    def test_outliers_exclude_self_age_format_and_other_channels(self):
        target=video('target',10000)
        peers=[target,video('a'),video('b'),video('c'),video('a'),video('old',1,hours=500),
               video('short',1,duration=60),video('other',1,channel='other')]
        result=comparable_baseline(target,peers,NOW)
        self.assertEqual(result['sample_size'],3)
        self.assertAlmostEqual(result['multiple'],10)
        self.assertEqual(result['peer_ids'],['a','b','c'])

    def test_no_outlier_without_sufficient_positive_baseline(self):
        self.assertIsNone(comparable_baseline(video(),[video('a')],NOW)['multiple'])
        self.assertIsNone(comparable_baseline(video(),[video(x,0) for x in 'abc'],NOW)['multiple'])

    def test_keyword_scores_deduplicate_and_require_evidence(self):
        rows=[video(str(i),channel='ch'+str(i%2)) for i in range(6)]
        profile=keyword_profile('belajar python',rows+[rows[0]],1000,NOW)
        self.assertEqual(profile['sample_size'],6)
        self.assertEqual(profile['title_coverage_pct'],100)
        self.assertTrue(0<=profile['opportunity']<=100)
        self.assertIsNotNone(profile['personal_opportunity'])
        self.assertIsNone(keyword_profile('python',rows[:3],now=NOW)['opportunity'])
        self.assertIsNone(keyword_profile('python',[],now=NOW)['opportunity'])
        with self.assertRaises(ValueError):keyword_profile('dan',rows,NOW)

    def test_phrases_use_video_frequency(self):
        rows=[video('a'),video('a'),video('b')]
        self.assertTrue(all(p['Video dalam sampel']==2 for p in phrase_clusters('python',rows)))

    def test_hidden_subscribers_are_not_personalization_evidence(self):
        rows=[{**video(str(i),channel=str(i)), 'subscriber_known':False} for i in range(6)]
        self.assertIsNone(keyword_profile('python',rows,1000,NOW)['personal_opportunity'])

    def test_video_urls_and_rank_boundaries(self):
        vid='dQw4w9WgXcQ'
        for url in [vid,'https://youtu.be/'+vid,'https://www.youtube.com/watch?v='+vid+'&t=20','https://youtube.com/shorts/'+vid]:
            self.assertEqual(parse_video_id(url),vid)
        for url in ['https://youtube.com.evil.test/watch?v='+vid,'https://example.org/'+vid,'invalid']:
            with self.assertRaises(ValueError):parse_video_id(url)
        items=[{'id':{'videoId':str(i)}} for i in range(50)]
        self.assertEqual(rank_observation('49',items)['position'],50)
        self.assertIsNone(rank_observation(vid,items)['position'])
        self.assertEqual(rank_observation(vid,[])['checked'],0)

    def test_ctr_intervals_and_insufficient_data(self):
        equal=ctr_experiment(1000,50,1000,50)
        self.assertLess(equal['difference_interval_pp'][0],0)
        self.assertGreater(equal['difference_interval_pp'][1],0)
        self.assertEqual(equal['difference_pp'],0)
        better=ctr_experiment(10000,500,10000,1000)
        self.assertGreater(better['difference_interval_pp'][0],0)
        self.assertEqual(better['relative_lift_pct'],100)
        self.assertIsNone(ctr_experiment(100,0,100,1)['relative_lift_pct'])
        self.assertEqual(ctr_experiment(10,1,10,9)['verdict'],'Data masih terbatas')
        for args in [(0,0,1,0),(1,2,1,0),(10,1.5,10,1),(10,float('nan'),10,1)]:
            with self.assertRaises(ValueError):ctr_experiment(*args)

    def test_csv_formula_injection_and_balanced_discovery(self):
        text=csv_bytes([{'title':'=HYPERLINK("bad")','views':10},{'title':'+bad','views':20}]).decode('utf-8-sig')
        self.assertIn("'=HYPERLINK",text)
        self.assertIn("'+bad",text)
        ids=balanced_ids([['a'+str(i) for i in range(50)],['b'+str(i) for i in range(50)]],50)
        self.assertEqual(sum(i.startswith('a') for i in ids),25)
        self.assertEqual(sum(i.startswith('b') for i in ids),25)

    def test_seo_limits_use_utf8_and_keep_relevance_distinct(self):
        result=seo_audit('X'*101,'é'*2501,['tag '*200],'python','python')
        self.assertEqual(result['description_bytes'],5002)
        self.assertEqual(len(result['blocking_issues']),3)
        self.assertTrue(seo_audit('python python python','',[],'python','')['warnings'])

    def test_interval_velocity_never_divided_by_lifetime_baseline(self):
        now=datetime.now(timezone.utc)
        rows=[{**video(x),'published_full':(now-timedelta(hours=24)).isoformat()} for x in 'abcd']
        target={**rows[0],'raw_views':10000,'vph':416,'ratio':1,'er':1}
        ns=backend_functions({'enrich_viral_longform','parse_yt_date','parse_iso_duration_seconds','shorts_confidence','breakout_label'},
            calculate_v2_velocity_and_acceleration=lambda _: (100000,10,10000,3),calculate_breakout_score=lambda _:42)
        ns['enrich_viral_longform']([target],'python',{'ch':{'videos':rows}})
        self.assertAlmostEqual(target['channel_breakout_multiple'],10,places=1)
        self.assertEqual(target['velocity_vph'],100000)

    def test_missing_baseline_contributes_zero(self):
        ns=backend_functions({'normalize_score','calculate_breakout_score'})
        row={'channel_breakout_multiple':10,'channel_baseline_samples':2}
        ns['calculate_breakout_score'](row)
        self.assertEqual(next(x['Kontribusi'] for x in row['score_components'] if x['Komponen']=='Perbandingan baseline'),0)


class ClientTest(unittest.TestCase):
    def response(self,status=200,data=None):
        return SimpleNamespace(status_code=status,json=lambda: data if data is not None else {'items':[]})

    def test_cache_key_isolated_by_query_region_and_key(self):
        state={};transport=Mock();transport.get.return_value=self.response(data={'items':[{'id':'a'}]})
        client=YouTubeClient('secret',state,transport)
        first=client.fetch('search',q='python',regionCode='ID');first['items'].clear()
        self.assertEqual(len(client.fetch('search',q='python',regionCode='ID')['items']),1)
        client.fetch('search',q='python',regionCode='US')
        YouTubeClient('other',state,transport).fetch('search',q='python',regionCode='ID')
        self.assertEqual(transport.get.call_count,3)
        self.assertEqual(state['youtube_usage']['cache_hits'],1)
        self.assertNotIn('secret',json.dumps(state))

    def test_force_refresh_and_timeout(self):
        transport=Mock();transport.get.return_value=self.response()
        client=YouTubeClient('secret',{},transport)
        client.fetch('search',q='x');client.fetch('search',q='x',force=True)
        self.assertEqual(transport.get.call_count,2)
        self.assertEqual(transport.get.call_args.kwargs['timeout'],(5,25))
        transport.get.side_effect=requests.Timeout('url?key=secret')
        with self.assertRaises(YouTubeError) as error:client.fetch('search',q='uncached')
        self.assertNotIn('secret',str(error.exception))

    def test_no_quota_rotation_and_bounded_transient_retry(self):
        transport=Mock();transport.get.return_value=self.response(403,{'error':{'message':'secret'}})
        client=YouTubeClient('secret',{},transport)
        with self.assertRaises(YouTubeError) as error:client.fetch('search',q='x')
        self.assertEqual(transport.get.call_count,1)
        self.assertNotIn('secret',str(error.exception))
        transport.reset_mock();transport.get.side_effect=[self.response(503),self.response(200)]
        client.fetch('videos',id='x')
        self.assertEqual(transport.get.call_count,2)

    def test_recent_uploads_never_uses_search_endpoint(self):
        transport=Mock();transport.get.side_effect=[
            self.response(data={'items':[{'contentDetails':{'relatedPlaylists':{'uploads':'PL'}}}]}),
            self.response(data={'items':[{'contentDetails':{'videoId':'v'}}]}),self.response(data={'items':[{'id':'v'}]})]
        rows=YouTubeClient('secret',{},transport).recent_uploads('UC',10)
        self.assertEqual(rows,[{'id':'v'}])
        self.assertEqual([c.args[0].rsplit('/',1)[-1] for c in transport.get.call_args_list],['channels','playlistItems','videos'])

    def test_bad_json_and_missing_key(self):
        with self.assertRaises(YouTubeError):YouTubeClient('')
        transport=Mock();transport.get.return_value=self.response(data=[])
        with self.assertRaises(YouTubeError):YouTubeClient('secret',{},transport).fetch('videos')


class PersistenceTest(unittest.TestCase):
    def test_new_records_survive_backup_and_old_backup_still_loads(self):
        with tempfile.TemporaryDirectory() as p, tempfile.TemporaryDirectory() as q:
            db=ResearchStore(p)
            track={'keyword':'python','video_id':'dQw4w9WgXcQ','region':'ID','language':'id','observations':[]}
            db.save('rank_track','r',track)
            for i in range(105):db.append_rank('r',{'position':i,'at':str(i)})
            db.save('planner','p',{'title':'Python','status':'Riset','due':'2026-10-14','priority':'Tinggi'})
            db.save('experiment','e',{'name':'test'})
            restored=ResearchStore(q);restored.restore(json.loads(db.export()))
            self.assertEqual(len(restored.list('rank_track')[0]['payload']['observations']),100)
            self.assertEqual(restored.list('planner')[0]['payload']['title'],'Python')
            self.assertEqual(len(restored.list('experiment')),1)
            restored.restore({'schema':1,'watchlist':[{'id':'w','payload':{'note':'legacy'}}]})
            self.assertEqual(len(restored.list('watchlist')),1)

    def test_restore_is_atomic_on_invalid_new_records(self):
        with tempfile.TemporaryDirectory() as p:
            db=ResearchStore(p)
            bad={'schema':2,'watchlist':[{'id':'w','payload':{}}],'planner':[{'id':'p','payload':{'status':'bad'}}]}
            with self.assertRaises(ValueError):db.restore(bad)
            self.assertEqual(db.list('watchlist'),[])


SCRIPT='''
from tests.fixtures_ui import SERVICES
from modules.simple_ui import render_app
render_app(SERVICES)
'''


class UpgradeUITest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict('os.environ',{'NICHE_HUNTER_DATA_DIR':self.temp.name});self.env.start()
        self.app=AppTest.from_string(SCRIPT,default_timeout=30).run()

    def tearDown(self):
        self.env.stop();self.temp.cleanup()

    def navigate(self,section,page):
        self.app.radio(key='nav_section').set_value(section).run()
        self.app.radio(key='nav_'+section).set_value(page).run()
        self.assertEqual([e.message for e in self.app.exception],[])

    def click(self,label):
        next(b for b in self.app.button if b.label==label).click().run()
        self.assertEqual([e.message for e in self.app.exception],[])

    def test_six_new_pages_start_without_credentials(self):
        for section,pages in [('Riset',['Keyword Lab','Radar kompetitor','Rank Tracker']),('Studio',['Kalender konten','Eksperimen CTR','Audit massal'])]:
            for page in pages:self.navigate(section,page)

    def test_planner_create_update_and_seo_handoff(self):
        self.navigate('Studio','Kalender konten')
        self.app.text_input(key='plan_new_title').set_value('Tutorial Python')
        self.app.text_input(key='plan_new_keyword').set_value('python')
        self.click('Simpan rencana')
        self.assertEqual(len(ResearchStore().list('planner')),1)
        next(x for x in self.app.selectbox if x.label=='Status').set_value('Produksi')
        self.click('Perbarui rencana')
        self.assertEqual(ResearchStore().list('planner')[0]['payload']['status'],'Produksi')
        self.click('Optimalkan rencana di SEO Studio')
        self.assertEqual(self.app.text_input(key='seo_keyword').value,'python')

    def test_rank_add_duplicate_and_live_mock_observation(self):
        self.navigate('Riset','Rank Tracker')
        self.app.text_input(key='rank_keyword').set_value('python')
        self.app.text_input(key='rank_video').set_value('https://youtu.be/dQw4w9WgXcQ')
        self.click('Tambahkan pelacakan');self.click('Tambahkan pelacakan')
        self.assertEqual(len(ResearchStore().list('rank_track')),1)
        client=Mock();client.fetch.return_value={'items':[{'id':{'videoId':'dQw4w9WgXcQ'}}]}
        with patch('modules.workspace_ui.client_for',return_value=client):self.click('Periksa posisi sekarang')
        self.assertEqual(ResearchStore().list('rank_track')[0]['payload']['observations'][0]['position'],1)
        client.fetch.side_effect=YouTubeError('Periksa kuota.')
        with patch('modules.workspace_ui.client_for',return_value=client):self.click('Periksa posisi sekarang')
        self.assertEqual(len(ResearchStore().list('rank_track')[0]['payload']['observations']),1)

    def test_experiment_persists_and_validates(self):
        self.navigate('Studio','Eksperimen CTR')
        self.app.text_input(key='experiment_name').set_value('Judul A vs B')
        self.click('Analisis eksperimen');self.click('Simpan eksperimen')
        self.assertEqual(len(ResearchStore().list('experiment')),1)
        self.assertEqual(len(self.app.metric),3)

    def test_keyword_renders_mock_results_and_planner_handoff(self):
        self.navigate('Riset','Keyword Lab')
        self.app.text_area(key='lab_seeds').set_value('python')
        rows=[{**video(str(i),channel=str(i)), 'views_fmt':'1K','channel':'Channel '+str(i),'link':'https://youtu.be/'+str(i)} for i in range(6)]
        client=Mock();client.fetch.side_effect=[{'items':[{'id':{'videoId':r['id']}} for r in rows]}, {'items':rows}]
        from tests.fixtures_ui import SERVICES
        with patch('modules.workspace_ui.client_for',return_value=client), patch.dict(SERVICES,{'process_video_response':lambda *args:rows}):
            self.click('Bandingkan kata kunci')
        self.click('Simpan riset keyword')
        self.assertEqual(len(ResearchStore().list('keyword')),1)
        self.click('Jadikan rencana konten')
        self.assertEqual(self.app.text_input(key='plan_new_title').value,'python')

    def test_competitor_radar_mock_and_invalid_input(self):
        self.navigate('Riset','Radar kompetitor')
        self.app.text_area(key='radar_channels').set_value('UC'+'a'*22)
        rows=[{**video(str(i)), 'published_full':(datetime.now(timezone.utc)-timedelta(hours=24)).isoformat(),
               'channel':'Channel simulasi','link':'https://youtu.be/'+str(i)} for i in range(5)]
        client=Mock();client.recent_uploads.return_value=rows
        from tests.fixtures_ui import SERVICES
        with patch('modules.workspace_ui.client_for',return_value=client),patch.dict(SERVICES,{'process_video_response':lambda *args:rows}):
            self.click('Analisis kompetitor')
        self.assertEqual(len(self.app.session_state['radar_result']['rows']),5)
        self.assertEqual(self.app.session_state['radar_result']['rows'][0]['peer_count'],4)

    def test_bulk_csv_audits_and_downloads_recommendations(self):
        class Upload(io.BytesIO):
            @property
            def size(self):return len(self.getvalue())
        upload=Upload(b'title,keyword,content\nBelajar Python,python,belajar python\nJudul lain,python,\n')
        script='''
from types import SimpleNamespace
from modules.workspace_ui import bulk_page
bulk_page(SimpleNamespace())
'''
        with patch('modules.workspace_ui.st.file_uploader',return_value=upload):
            app=AppTest.from_string(script).run()
            upload.seek(0)
            next(b for b in app.button if b.label=='Audit semua baris').click().run()
        self.assertEqual([e.message for e in app.exception],[])
        self.assertEqual(len(app.session_state['bulk_result']['rows']),2)
        self.assertEqual(app.session_state['bulk_result']['rows'][1]['priority'],'Lengkapi isi')

    def test_saving_watchlist_again_preserves_notes(self):
        db=ResearchStore();db.save('watchlist','v',{'video':{'id':'v','title':'Original'},'note':'Catatan penting'})
        from modules.growth_ui import save_watch
        save_watch({'id':'v','title':'Updated'})
        self.assertEqual(db.list('watchlist')[0]['payload']['note'],'Catatan penting')


if __name__=='__main__':unittest.main()
