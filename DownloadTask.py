import time

import requests


class DownloadTask:
    def __init__(self, callback, hash, size, name, category, dldir, dlext, dlsize, dlnzbtomedia):
        self.progress = None
        self.speed = None
        self.size = size
        self.hash = hash
        self.name = name
        self.category = category
        self.timestamp = int(time.time())
        self.previous_timestamp = None
        self.speed = None
        self.cloud_status = None
        self.cloud_ratio = None
        self.local_status = None
        self.eta = None
        self.callback = callback
        self.dldir = dldir
        self.dlext = dlext
        self.dlsize = dlsize
        self.dlnzbtomedia = dlnzbtomedia

    def update(self, **kwargs):
        self.previous_timestamp = self.timestamp
        self.timestamp = int(time.time())
        if 'progress' in kwargs:
            self.progress = kwargs.get('progress')
        if 'cloud_status' in kwargs:
            self.cloud_status = kwargs.get('cloud_status')
        if 'local_status' in kwargs:
            self.local_status = kwargs.get('local_status')
        if 'name' in kwargs:
            self.name = kwargs.get('name')
        if 'size' in kwargs:
            self.size = kwargs.get('size')
        if self.cloud_status == "finished" and not self.local_status:
            self.progress = 100
        if 'speed' in kwargs:
            self.speed = kwargs.get('speed')
        if 'eta' in kwargs:
            self.eta = kwargs.get('eta')
        if 'category' in kwargs:
            self.category = kwargs.get('category')
        if 'dldir' in kwargs:
            self.dldir = kwargs.get('dldir')
        if 'dlext' in kwargs:
            self.dlext = kwargs.get('dlext')
        if 'dlsize' in kwargs:
            self.dlsize = kwargs.get('dlsize')
        if 'dlnzbtomedia' in kwargs:
            self.dlnzbtomedia = kwargs.get('dlnzbtomedia')
        self.callback('update_task', {'task': self.get_json()})

    def delete(self):
        payload = {'customer_id': 'value1', 'pin': 'value2', 'hash': self.hash}
        r = requests.post("https://www.premiumize.me/torrent/delete")
        if r.text['status'] == "success":
            return True
        else:
            return False

    def download(self):
        payload = {'customer_id': 'value1', 'pin': 'value2', 'hash': self.hash}
        r = requests.post("https://www.premiumize.me/torrent/browse")
        if r.text['status'] == "success":
            return True
        else:
            return False

    def get_json(self):
        return {'progress': self.progress, 'speed': self.speed, 'size': self.size, 'eta': self.eta, 'hash': self.hash,
                'name': self.name,
                'cloud_status': self.cloud_status, 'local_status': self.local_status, 'category': self.category}
