import time


class DownloadTask:
    def __init__(self, callback, id, folder_id, size, name, category, dldir, dlext, delsample, dlnzbtomedia):
        self.progress = None
        self.speed = None
        self.size = size
        self.id = id
        self.folder_id = folder_id
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
        self.delsample = delsample
        self.dlnzbtomedia = dlnzbtomedia
        self.dltime = 0
        self.dlsize = ''
        self.download_list = []

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
        if 'delsample' in kwargs:
            self.delsample = kwargs.get('delsample')
        if 'dlnzbtomedia' in kwargs:
            self.dlnzbtomedia = kwargs.get('dlnzbtomedia')
        if 'dltime' in kwargs:
            self.dltime = kwargs.get('dltime')
        if 'dlsize' in kwargs:
            self.dlsize = kwargs.get('dlsize')
        if 'id' in kwargs:
            self.id = kwargs.get('id')
        if 'folder_id' in kwargs:
            self.folder_id = kwargs.get('folder_id')
        if 'download_list' in kwargs:
            self.download_list = kwargs.get('download_list')
        self.callback('update_task', {'task': self.get_json()})

    def get_json(self):
        return {'progress': self.progress, 'speed': self.speed, 'dlsize': self.dlsize, 'eta': self.eta, 'id': self.id,
                'folder_id': self.folder_id, 'name': self.name, 'cloud_status': self.cloud_status,
                'local_status': self.local_status, 'category': self.category}
