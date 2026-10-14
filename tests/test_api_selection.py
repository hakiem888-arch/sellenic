"""Regression: a backend write must never target an instantiated widget key."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest


class APISelectionTest(unittest.TestCase):
    def test_two_keys_search_trending_and_navigation(self):
        calls=[]
        def fetch(client,resource,**params):
            calls.append((client.key,resource))
            return {'items':[{'id':{'videoId':'dQw4w9WgXcQ'}}]} if resource=='search' else {'items':[]}
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ',{'NICHE_HUNTER_DATA_DIR':folder}), patch('modules.youtube_client.YouTubeClient.fetch',fetch):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
            app.secrets['YOUTUBE_API_KEYS']=['TEST_FIRST','TEST_SECOND']
            app.run()
            app.selectbox(key='youtube_api_selector').set_value(1).run()
            self.assertEqual(app.session_state['current_api_index'],1)
            app.text_input(key='field_video_query').set_value('python')
            next(b for b in app.button if b.label=='Cari video').click().run()
            self.assertEqual(list(app.exception),[])
            self.assertEqual(list(app.error),[])
            self.assertIn(('TEST_SECOND','search'),calls)
            self.assertIn(('TEST_SECOND','videos'),calls)
            app.radio(key='nav_section').set_value('Studio').run()
            app.radio(key='nav_section').set_value('Video').run()
            self.assertEqual(app.selectbox(key='youtube_api_selector').value,1)
            app.selectbox(key='youtube_api_selector').set_value(0).run()
            app.radio(key='nav_Video').set_value('Trending').run()
            next(b for b in app.button if b.label=='Lihat trending').click().run()
            self.assertEqual(list(app.exception),[])
            self.assertEqual(list(app.error),[])
            self.assertEqual(calls[-1],('TEST_FIRST','videos'))

    def test_shrinking_configured_keys_clamps_selection(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ',{'NICHE_HUNTER_DATA_DIR':folder}):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
            app.secrets['YOUTUBE_API_KEYS']=['TEST_FIRST','TEST_SECOND']
            app.run()
            app.selectbox(key='youtube_api_selector').set_value(1).run()
            app.secrets['YOUTUBE_API_KEYS']=['TEST_FIRST']
            app.run()
            self.assertEqual(list(app.exception),[])
            self.assertEqual(app.session_state['current_api_index'],0)


if __name__=='__main__':unittest.main()
