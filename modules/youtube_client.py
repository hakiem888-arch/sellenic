"""Bounded public YouTube requests, TTL cache, redacted errors and call accounting."""
import copy
import hashlib
import json
import time
from types import SimpleNamespace
import requests


class YouTubeError(RuntimeError):
    pass


class YouTubeClient:
    RESOURCES = {'search', 'videos', 'channels', 'playlistItems'}

    def __init__(self, api_key, state=None, transport=None, ttl=300):
        if not api_key:
            raise YouTubeError('YouTube API key belum diatur di Secrets atau environment.')
        self.key, self.state = api_key, state if state is not None else {}
        self.transport, self.ttl = transport or requests, ttl

    def fetch(self, resource, force=False, **params):
        if resource not in self.RESOURCES:
            raise ValueError('Resource YouTube tidak didukung.')
        params = {k:v for k,v in params.items() if v is not None}
        fingerprint = hashlib.sha256((self.key+resource+json.dumps(params,sort_keys=True)).encode()).hexdigest()
        cache = self.state.setdefault('youtube_cache', {})
        usage = self.state.setdefault('youtube_usage', {'calls':0,'search':0,'cache_hits':0,'errors':0})
        now = time.monotonic()
        cached = cache.get(fingerprint)
        if not force and cached and now-cached['at'] < self.ttl:
            usage['cache_hits'] += 1
            return copy.deepcopy(cached['data'])
        for attempt in range(2):
            usage['calls'] += 1
            usage['search'] += int(resource == 'search')
            try:
                response = self.transport.get('https://www.googleapis.com/youtube/v3/'+resource,
                                              params={**params, 'key':self.key}, timeout=(5,25))
            except requests.RequestException:
                usage['errors'] += 1
                raise YouTubeError('Koneksi YouTube gagal atau melewati batas waktu. Coba lagi.') from None
            if response.status_code == 429 or response.status_code >= 500:
                usage['errors'] += 1
                if attempt == 0:
                    continue
            if response.status_code != 200:
                if response.status_code < 500 and response.status_code != 429:
                    usage['errors'] += 1
                if response.status_code == 403:
                    raise YouTubeError('YouTube menolak akses (403): periksa kuota, aktivasi API, atau pembatasan kunci. Tidak mengganti kunci otomatis.')
                raise YouTubeError(f'Permintaan YouTube gagal (HTTP {response.status_code}). Periksa konfigurasi dan masukan.')
            try:
                data = response.json()
                if not isinstance(data,dict) or not isinstance(data.get('items',[]),list) or 'error' in data:
                    raise ValueError()
            except (ValueError,TypeError):
                usage['errors'] += 1
                raise YouTubeError('Format respons YouTube tidak valid.') from None
            if len(cache) >= 250:
                cache.pop(next(iter(cache)))
            cache[fingerprint] = {'at': time.monotonic(), 'data': copy.deepcopy(data)}
            return data

    def __getattr__(self, name):
        if name not in self.RESOURCES:
            raise AttributeError(name)
        return lambda: SimpleNamespace(list=lambda **params: SimpleNamespace(execute=lambda: self.fetch(name,**params)))

    def recent_uploads(self, channel_id, limit=30):
        channel = self.fetch('channels',id=channel_id,part='contentDetails')
        if not channel.get('items'):
            return []
        playlist = channel['items'][0].get('contentDetails',{}).get('relatedPlaylists',{}).get('uploads')
        if not playlist:
            return []
        items = self.fetch('playlistItems',playlistId=playlist,part='contentDetails',maxResults=min(50,max(1,limit)))
        ids = [x.get('contentDetails',{}).get('videoId') for x in items.get('items',[])]
        ids = [x for x in ids if x]
        if not ids:
            return []
        return self.fetch('videos',id=','.join(ids),part='snippet,statistics,contentDetails').get('items',[])


def build(service, version, developerKey):
    """Small adapter for the existing app's resource.list().execute() calls."""
    if (service,version) != ('youtube','v3'):
        raise ValueError('Hanya YouTube Data API v3 yang didukung.')
    import streamlit as st
    return YouTubeClient(developerKey,st.session_state)
