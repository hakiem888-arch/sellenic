"""Run from the project directory: python -m unittest tests.test_ui -v."""
import unittest
from streamlit.testing.v1 import AppTest

SCRIPT='''
import streamlit as st
from tests.fixtures_ui import SERVICES
from modules.simple_ui import render_app
render_app(SERVICES)
'''

class UITest(unittest.TestCase):
    def app(self):
        app=AppTest.from_string(SCRIPT, default_timeout=30)
        app.secrets['YOUTUBE_API_KEY']='TEST_ONLY'
        app.run()
        self.ok(app)
        return app

    def ok(self, app):
        self.assertEqual([e.message for e in app.exception], [])

    def click(self, app, label):
        buttons=[b for b in app.button if b.label==label]
        self.assertTrue(buttons, label)
        buttons[0].click().run()
        self.ok(app)

    def search(self, app, query='kata uji'):
        app.text_input(key='field_video_query').set_value(query)
        self.click(app, 'Cari video')

    def test_all_seven_modes(self):
        app=self.app()
        for section, pages in [('Video',['Pencarian','Trending','Viral Intelligence']), ('Channel',['Direktori','Analisis','Perbandingan']), ('Artis',['Perbandingan artis'])]:
            app.radio(key='nav_section').set_value(section).run()
            for page in pages:
                if section!='Artis':
                    app.radio(key='nav_'+section).set_value(page).run()
                self.ok(app)
                self.assertTrue(app.title)

    def test_search_filters_forward_and_survive_navigation(self):
        app=self.app()
        app.selectbox(key='field_video_duration').set_value('Medium (4-20m)')
        app.selectbox(key='field_video_license').set_value('Creative Commons')
        app.selectbox(key='field_video_sort').set_value('Skor SEO Terbaik (Custom)')
        self.search(app)
        call=app.session_state['test_calls']['search'][-1]
        self.assertEqual(call['duration'],'medium')
        self.assertEqual(call['license_type'],'creativeCommon')
        self.assertEqual(call['sort_order'],'seo_custom')
        self.assertEqual(len(app.session_state['video_results_bundle']['rows']),13)
        self.assertEqual(len([b for b in app.button if b.label=='Analisis channel']),6)
        app.selectbox(key='field_video_results_bundle_page').set_value(3).run()
        self.assertEqual(len([b for b in app.button if b.label=='Analisis channel']),1)
        app.radio(key='nav_section').set_value('Channel').run()
        app.radio(key='nav_section').set_value('Video').run()
        self.assertEqual(app.text_input(key='field_video_query').value,'kata uji')
        self.assertEqual(app.selectbox(key='field_video_duration').value,'Medium (4-20m)')
        self.ok(app)

    def test_search_and_trending_are_isolated(self):
        app=self.app(); self.search(app)
        app.radio(key='nav_Video').set_value('Trending').run()
        self.click(app,'Lihat trending')
        self.assertEqual(len(app.session_state['trending_results_bundle']['rows']),3)
        self.assertEqual(len(app.session_state['video_results_bundle']['rows']),13)
        app.radio(key='nav_Video').set_value('Pencarian').run()
        self.assertEqual(app.session_state['video_results_bundle']['query'],'kata uji')
        self.ok(app)

    def test_autocomplete_updates_search_field(self):
        app=self.app()
        app.text_input(key='field_video_query').set_value('rain')
        self.click(app,'Saran kata kunci')
        self.click(app,'Gunakan kata kunci')
        self.assertEqual(app.text_input(key='field_video_query').value,'rain fokus')
        self.click(app,'Cari video')
        self.assertEqual(app.session_state['test_calls']['search'][-1]['query'],'rain fokus')

    def test_ai_is_scoped_and_survives_rerun(self):
        app=self.app(); self.search(app)
        self.click(app,'Analisis Channel DNA')
        dna=[m.value for m in app.markdown if 'Analisis khusus channel1' in m.value]
        self.assertEqual(len(dna),1)
        app.radio(key='video_view').set_value('Tabel').run()
        self.assertEqual(app.session_state['test_calls']['dna'], ['channel1'])
        self.assertTrue(any('Analisis khusus channel1' in m.value for m in app.markdown))
        self.click(app,'Buat 5 ide konten')
        app.radio(key='video_view').set_value('Kartu').run()
        self.assertTrue(any('Ide simulasi untuk kata uji' in m.value for m in app.markdown))

    def test_analysis_navigation_and_cache(self):
        app=self.app(); self.search(app)
        self.click(app,'Analisis channel')
        self.assertEqual(app.radio(key='nav_section').value,'Channel')
        self.assertEqual(app.radio(key='nav_Channel').value,'Analisis')
        self.assertEqual(app.session_state['test_calls']['deep'],['channel1'])
        app.run(); self.ok(app)
        self.assertEqual(app.session_state['test_calls']['deep'],['channel1'])
        self.click(app,'Perbarui data')
        self.assertEqual(len(app.session_state['test_calls']['deep']),2)

    def test_full_comparison_does_not_evict_channel(self):
        app=self.app()
        app.session_state['compare_list']=['channel1','channel2','channel3','channel4']
        self.search(app)
        app.button(key='compare_video_sample5').click().run(); self.ok(app)
        self.assertEqual(app.session_state['compare_list'],['channel1','channel2','channel3','channel4'])
        self.assertTrue(any('Hapus salah satu' in i.value for i in app.info))
        self.assertEqual(len(app.session_state['test_calls']['deep']),4)

    def test_viral_candidates_and_ai(self):
        app=self.app(); app.radio(key='nav_Video').set_value('Viral Intelligence').run()
        app.text_input(key='field_viral_query').set_value('ide uji')
        self.click(app,'Cari kandidat')
        self.assertEqual(len(app.session_state['viral_bundle']['rows']),13)
        app.selectbox(key='field_viral_candidate').set_value(12).run(); self.ok(app)
        self.click(app,'Kembangkan peluang dengan AI')
        self.click(app,'Analisis kandidat dengan AI')
        self.assertEqual(len(app.session_state['test_calls']['viral']),1)
        app.session_state['viral_bundle']['rows'] = app.session_state['viral_bundle']['rows'][:2]
        app.run(); self.ok(app)
        self.assertEqual(app.selectbox(key='field_viral_candidate').value,0)

    def test_directory_and_artist_flows(self):
        app=self.app(); app.radio(key='nav_section').set_value('Channel').run()
        app.text_input(key='field_directory_query').set_value('cover')
        self.click(app,'Cari channel')
        self.assertEqual(len(app.session_state['directory_bundle']['rows']),6)
        app.radio(key='nav_section').set_value('Artis').run()
        app.text_input(key='field_artist_1').set_value('Alpha')
        app.text_input(key='field_artist_2').set_value(' alpha ')
        self.click(app,'Bandingkan artis')
        self.assertTrue(app.warning)
        app.text_input(key='field_artist_2').set_value('Beta')
        app.text_input(key='field_artist_3').set_value('Alpha')
        self.click(app,'Bandingkan artis')
        self.assertEqual(app.session_state['test_calls']['artist'],['Alpha','Beta'])
        app.selectbox(key='field_artist_chart').set_value('Rerata VPH').run(); self.ok(app)

    def test_blank_search_does_not_call_api(self):
        app=self.app()
        self.click(app,'Cari video')
        self.assertTrue(app.warning)
        self.assertNotIn('test_calls',app.session_state)

if __name__=='__main__':
    unittest.main()
