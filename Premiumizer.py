#! /usr/bin/env python
import ConfigParser
import hashlib
import json
import logging
import os
import shelve
import shutil
import sys
import unicodedata
from logging.handlers import RotatingFileHandler
from string import ascii_letters, digits

import bencode
import gevent
import pyperclip
import requests
import six
from apscheduler.schedulers.gevent import GeventScheduler
from chardet import detect
from flask import Flask, flash, request, redirect, url_for, render_template, send_from_directory
from flask.ext.login import LoginManager, login_required, login_user, logout_user, UserMixin
from flask.ext.socketio import SocketIO, emit
from flask_apscheduler import APScheduler
from pySmartDL import SmartDL
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer
from werkzeug.utils import secure_filename

from DownloadTask import DownloadTask

# "https://www.premiumize.me/static/api/torrent.html"

print '------------------------------------------------------------------------------------------------------------'
print '|                                                                                                           |'
print '-------------------------------------------WELCOME TO PREMIUMIZER-------------------------------------------'
print '|                                                                                                           |'
print '------------------------------------------------------------------------------------------------------------'
# Initialize config values
prem_config = ConfigParser.RawConfigParser()
runningdir = os.path.split(os.path.abspath(os.path.realpath(sys.argv[0])))[0] + '/'
if not os.path.isfile(runningdir + 'settings.cfg'):
    shutil.copy(runningdir + 'settings.cfg.tpl', runningdir + 'settings.cfg')
prem_config.read(runningdir + 'settings.cfg')
active_interval = prem_config.getint('global', 'active_interval')
idle_interval = prem_config.getint('global', 'idle_interval')
debug_enabled = prem_config.getboolean('global', 'debug_enabled')

# Initialize logging
syslog = logging.StreamHandler()
if debug_enabled:
    logger = logging.getLogger('')
    logger.setLevel(logging.DEBUG)
    formatterdebug = logging.Formatter('%(asctime)-20s %(name)-41s: %(levelname)-8s : %(message)s',
                                       datefmt='%m-%d %H:%M:%S')
    syslog.setFormatter(formatterdebug)
    logger.addHandler(syslog)
    print '------------------------------------------------------------------------------------------------------------'
    print '|                                                                                                           |'
    print '------------------------PREMIUMIZER IS RUNNING IN DEBUG MODE, THIS IS NOT RECOMMENDED-----------------------'
    print '|                                                                                                           |'
    print '------------------------------------------------------------------------------------------------------------'
    logger.info('----------------------------------')
    logger.info('----------------------------------')
    logger.info('----------------------------------')
    logger.info('DEBUG Logger Initialized')
    handler = logging.handlers.RotatingFileHandler(runningdir + 'premiumizerDEBUG.log', maxBytes=(20 * 1024),
                                                   backupCount=5)
    handler.setFormatter(formatterdebug)
    logger.addHandler(handler)
    logger.info('DEBUG Logfile Initialized')
else:
    logger = logging.getLogger("Rotating log")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)-s: %(levelname)-s : %(message)s', datefmt='%m-%d %H:%M:%S')
    syslog.setFormatter(formatter)
    logger.addHandler(syslog)
    logger.info('-------------------------------------------------------------------------------------')
    logger.info('-------------------------------------------------------------------------------------')
    logger.info('-------------------------------------------------------------------------------------')
    logger.info('Logger Initialized')
    if prem_config.getboolean('global', 'logfile_enabled'):
        handler = logging.handlers.RotatingFileHandler(runningdir + 'premiumizer.log', maxBytes=(20 * 1024),
                                                       backupCount=5)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.info('Logfile Initialized')


# Catch uncaught exceptions in log
def uncaught_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, SystemExit or KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = uncaught_exception

# Logging filters for debugging, default is 1
log_apscheduler = 1
log_flask = 1


class ErrorFilter(logging.Filter):
    def __init__(self, *errorfilter):
        self.errorfilter = [logging.Filter(name) for name in errorfilter]

    def filter(self, record):
        return not any(f.filter(record) for f in self.errorfilter)


if not log_apscheduler:
    syslog.addFilter(ErrorFilter('apscheduler'))

if not log_flask:
    syslog.addFilter(
        ErrorFilter('engineio', 'socketio', 'geventwebsocket.handler', 'requests.packages.urllib3.connectionpool'))

# Check if premiumizer has been updated
if prem_config.getboolean('update', 'updated'):
    logger.info('Premiumizer has been updated!!')
    logger.info('*************************************************************************************')
    logger.info('---------------------------Premiumizer has been updated!!----------------------------')
    logger.info('*************************************************************************************')
    if os.path.isfile(runningdir + 'settings.cfg.old'):
        logger.info('*************************************************************************************')
        logger.info('-------Settings file has been updated/wiped, old settings file renamed to .old-------')
        logger.info('*************************************************************************************')
    prem_config.set('update', 'updated', '0')
    with open(runningdir + 'settings.cfg', 'w') as configfile:
        prem_config.write(configfile)

#
logger.info('Running at %s', runningdir)


# noinspection PyAttributeOutsideInit
class PremConfig:
    def __init__(self):
        self.check_config()

    def check_config(self):
        logger.debug('Checking config')
        self.web_login_enabled = prem_config.getboolean('security', 'login_enabled')
        if self.web_login_enabled:
            logger.debug('Premiumizer login is enabled')
            self.web_username = prem_config.get('security', 'username')
            self.web_password = prem_config.get('security', 'password')

        self.prem_customer_id = prem_config.get('premiumize', 'customer_id')
        self.prem_pin = prem_config.get('premiumize', 'pin')
        self.remove_cloud = prem_config.getboolean('downloads', 'remove_cloud')
        self.download_enabled = prem_config.getboolean('downloads', 'download_enabled')
        self.copylink_toclipboard = prem_config.getboolean('downloads', 'copylink_toclipboard')
        if self.copylink_toclipboard:
            self.download_enabled = 0
        self.download_categories = prem_config.get('downloads', 'download_categories').split(',')
        if self.download_enabled:
            self.download_location = prem_config.get('downloads', 'download_location')
            logger.info('Downloads are enabled & saved to: %s', self.download_location)
            if not os.path.exists(self.download_location):
                logger.info('Creating Download Path at: %s', self.download_location)
                os.makedirs(self.download_location)
            for x in self.download_categories:
                self.sub = self.download_location + '/' + x
                if not os.path.exists(self.sub):
                    logger.info('Creating download subdirectory at: %s', self.sub)
                    os.makedirs(self.sub)

        if self.download_enabled or self.copylink_toclipboard:
            self.download_ext = prem_config.get('downloads', 'download_ext').split(',')
            self.download_size = (prem_config.getint('downloads', 'download_size') * 1000000)
        self.watchdir_enabled = prem_config.getboolean('upload', 'watchdir_enabled')
        if self.watchdir_enabled:
            self.watchdir_location = prem_config.get('upload', 'watchdir_location')
            logger.info('Watchdir is enabled at: %s', self.watchdir_location)
            if not os.path.exists(self.watchdir_location):
                logger.info('Creating watchdir Path at %s', self.watchdir_location)
                os.makedirs(self.watchdir_location)
            for x in self.download_categories:
                self.sub = self.watchdir_location + '/' + x
                if not os.path.exists(self.sub):
                    logger.info('Creating watchdir subdirectory at: %s ', self.sub)
                    os.makedirs(self.sub)
        self.nzbtomedia_enabled = prem_config.getboolean('nzbtomedia', 'nzbtomedia_enabled')
        if self.nzbtomedia_enabled:
            self.nzbtomedia_location = prem_config.get('nzbtomedia', 'nzbtomedia_location')

        logger.debug('Checking config done')


cfg = PremConfig()

#
logger.debug('Initializing Flask')
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config.update(DEBUG=debug_enabled)

socketio = SocketIO(app)

app.config['LOGIN_DISABLED'] = not cfg.web_login_enabled
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
logger.debug('Flask initialized')

# Initializer Database
logger.debug('Initialize Database')
db = shelve.open(runningdir + 'premiumizer.db')
tasks = []
downloading = False
downloader = None
total_size_downloaded = None
logger.debug('Database initialized')


#

class User(UserMixin):
    def __init__(self, userid, password):
        self.id = userid
        self.password = password


def to_unicode(original, *args):
    try:
        if isinstance(original, unicode):
            return original
        else:
            try:
                return six.text_type(original, *args)
            except:
                try:
                    detected = detect(original)
                    try:
                        if detected.get('confidence') > 0.8:
                            return original.decode(detected.get('encoding'))
                    except:
                        pass

                    return ek(original, *args)
                except:
                    raise
    except:
        logger.error('Unable to decode value "%s..." : %s ', (repr(original)[:20], traceback.format_exc()))
        return 'ERROR DECODING STRING'


def ek(original, *args):
    if isinstance(original, (str, unicode)):
        try:
            return original.decode('UTF-8', 'ignore')
        except UnicodeDecodeError:
            raise
    return original


#
def clean_name(original):
    valid_chars = "-_.() %s%s" % (ascii_letters, digits)
    cleaned_filename = unicodedata.normalize('NFKD', to_unicode(original)).encode('ASCII', 'ignore')
    valid_string = ''.join(c for c in cleaned_filename if c in valid_chars)
    return ' '.join(valid_string.split())


def notify_nzbtomedia(task):
    if os.path.isfile(cfg.nzbtomedia_location):
        # noinspection PyArgumentList
        os.system(cfg.nzbtomedia_location,
                  task.download_location + ' ' + task.name + ' ' + task.category + ' ' + task.hash)
        logger.info('Send to nzbtomedia: %s', task.name)
    else:
        logger.error('Error unable to locate nzbToMedia.py')


def get_download_stats(task):
    logger.debug('Updating Download Stats')
    if downloader and downloader.get_status() == 'downloading':
        size_downloaded = total_size_downloaded + downloader.get_dl_size()
        progress = round(float(size_downloaded) * 100 / task.size, 1)
        speed = downloader.get_speed(human=True)
        task.update(speed=speed, progress=progress)
    else:
        logger.debug('Want to update stats, but downloader does not exist yet.')


def download_file(task, full_path, url):
    logger.debug('def download_file started')
    logger.info('Downloading file: %s', full_path)
    if not os.path.isfile(full_path):
        global downloader
        downloader = SmartDL(url, full_path, progress_bar=False, logger=logger)
        downloader.start(blocking=False)
        while not downloader.isFinished():
            get_download_stats(task)
            gevent.sleep(5)
        if downloader.isSuccessful():
            global total_size_downloaded
            total_size_downloaded += downloader.get_dl_size()
            logger.info('Finished downloading file: %s', full_path)
        else:
            logger.error('Error while downloading file from: %s', full_path)
            for e in downloader.get_errors():
                logger.error(str(e))
    else:
        logger.info('File not downloaded it already exists at: %s', full_path)


# TODO continue log statements

def process_dir(task, path, dir_content):
    logger.debug('def processing_dir started')
    if not dir_content:
        return None
    for x in dir_content:
        type = dir_content[x]['type']
        if type == 'dir':
            new_path = os.path.join(path, clean_name(x))
            process_dir(task, new_path, dir_content[x]['children'])
        elif type == 'file':
            if dir_content[x]['size'] >= cfg.download_size:
                if cfg.download_ext is None or dir_content[x]['url'].lower().endswith(tuple(cfg.download_ext)):
                    if cfg.download_enabled:
                        if not os.path.exists(path):
                            os.makedirs(path)
                        download_file(task, path + '/' + clean_name(x),
                                      dir_content[x]['url'])
                    elif cfg.copylink_toclipboard:
                        logger.info('Link copied to clipboard for: %s', dir_content[x]['name'])
                        pyperclip.copy(dir_content[x]['url'])


#
def download_task(task):
    logger.debug('def download_task started')
    global downloading
    base_path = cfg.download_location
    if task.category:
        base_path = os.path.join(base_path, task.category)
    payload = {'customer_id': cfg.prem_customer_id, 'pin': cfg.prem_pin,
               'hash': task.hash}
    r = requests.post("https://www.premiumize.me/torrent/browse", payload)
    global total_size_downloaded
    total_size_downloaded = 0
    downloading = True
    process_dir(task, base_path, json.loads(r.content)['data']['content'])
    task.update(local_status='finished', progress=100)
    downloading = False
    if cfg.nzbtomedia_enabled:
        notify_nzbtomedia(task)
    if cfg.remove_cloud:
        payload = {'customer_id': cfg.prem_customer_id, 'pin': cfg.prem_pin, 'hash': task.hash}
        r = requests.post("https://www.premiumize.me/torrent/delete", payload)
        responsedict = json.loads(r.content)
        if responsedict['status'] == "success":
            logger.info('Torrent removed from cloud: %s', task.name)
        else:
            logger.info('Torrent could not be removed from cloud: %s', task.name)
            logger.info(responsedict['message'])
        payload = {'customer_id': cfg.prem_customer_id, 'pin': cfg.prem_pin}
        r = requests.post("https://www.premiumize.me/torrent/list", payload)
        response_content = json.loads(r.content)
        if response_content['status'] == "success":
            torrents = response_content['torrents']
            parse_tasks(torrents)


def update():
    logger.debug('Updating')
    idle = True
    update_interval = idle_interval
    payload = {'customer_id': cfg.prem_customer_id, 'pin': cfg.prem_pin}
    r = requests.post("https://www.premiumize.me/torrent/list", payload)
    response_content = json.loads(r.content)
    if response_content['status'] == "success":
        if response_content['torrents']:
            torrents = response_content['torrents']
            idle = parse_tasks(torrents)
        else:
            socketio.emit('tasks_updated', {})
            update_interval *= 2
    else:
        socketio.emit('premiumize_connect_error', {})
    if not idle:
        update_interval = active_interval
    scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=update_interval)


def parse_tasks(torrents):
    logger.debug('def parse_task started')
    hashes_online = []
    hashes_local = []
    idle = True
    for task in tasks:
        hashes_local.append(task.hash)
    for torrent in torrents:
        if torrent['status'] == "downloading":
            idle = False
        task = get_task(torrent['hash'].encode("utf-8"))
        if not task:
            task = DownloadTask(socketio.emit, torrent['hash'].encode("utf-8"), torrent['size'], torrent['name'], '')
            task.update(progress=torrent['percent_done'], cloud_status=torrent['status'], speed=torrent['speed_down'])
            tasks.append(task)
        elif task.local_status != 'finished':
            if task.cloud_status == 'uploading':
                task.update(progress=torrent['percent_done'], cloud_status=torrent['status'], name=torrent['name'],
                            size=torrent['size'])
            elif task.cloud_status == 'finished' and task.local_status != 'finished':
                if (cfg.download_enabled or cfg.copylink_toclipboard) and (task.category in cfg.download_categories):
                    if not downloading:
                        task.update(progress=torrent['percent_done'], cloud_status=torrent['status'],
                                    local_status='downloading', size=torrent['size'])
                        scheduler.scheduler.add_job(download_task, args=(task,), replace_existing=True, max_instances=1)
                    elif task.local_status != 'downloading':
                        task.update(progress=torrent['percent_done'], cloud_status=torrent['status'],
                                    local_status='queued')
                else:
                    task.update(progress=torrent['percent_done'], cloud_status=torrent['status'],
                                local_status='finished')
            else:
                task.update(progress=torrent['percent_done'], cloud_status=torrent['status'], name=torrent['name'],
                            speed=torrent['speed_down'])
                if task.cloud_status == 'finished':
                    parse_tasks(torrents)
        else:
            task.update()
        hashes_online.append(task.hash)
        task.callback = None
        db[task.hash] = task
        task.callback = socketio.emit

    # Delete local task.hash that are removed from cloud
    hash_diff = [aa for aa in hashes_local if aa not in set(hashes_online)]
    for task_hash in hash_diff:
        for task in tasks:
            if task.hash == task_hash:
                tasks.remove(task)
                del db[task_hash]
                break
    db.sync()
    socketio.emit('tasks_updated', {})
    return idle


def get_task(hash):
    logger.debug('def get_task started')
    for task in tasks:
        if task.hash == hash:
            return task
    return None


def add_task(hash, name, category):
    logger.debug('def add_task started')
    tasks.append(DownloadTask(socketio.emit, hash, 0, name, category))


def upload_torrent(filename):
    logger.debug('def upload_torrent started')
    payload = {'customer_id': cfg.prem_customer_id, 'pin': cfg.prem_pin}
    files = {'file': open(filename, 'rb')}
    r = requests.post("https://www.premiumize.me/torrent/add", payload, files=files)
    response_content = json.loads(r.content)
    if response_content['status'] == "success":
        logger.debug('Upload successful: %s', filename)
        scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=0)
        return True
    else:
        return False


def upload_magnet(magnet):
    logger.debug('def upload_magnet started')
    payload = {'customer_id': cfg.prem_customer_id, 'pin': cfg.prem_pin, 'url': magnet}
    r = requests.post("https://www.premiumize.me/torrent/add", payload)
    response_content = json.loads(r.content)
    if response_content['status'] == "success":
        logger.debug('Upload magnet successful')
        scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=0)
        return True
    else:
        return False


def send_categories():
    logger.debug('def send_categories started')
    emit('download_categories', {'data': cfg.download_categories})


class MyHandler(PatternMatchingEventHandler):
    patterns = ["*.torrent"]

    def process(self, event):
        if event.event_type == 'created' and event.is_directory is False:
            gevent.sleep(2)
            torrent_file = event.src_path
            logger.debug('New torrent file detected at: %s', torrent_file)
            # Open torrent file to get hash
            metainfo = bencode.bdecode(open(torrent_file, 'rb').read())
            info = metainfo['info']
            name = info['name']
            hash = hashlib.sha1(bencode.bencode(info)).hexdigest()
            dirname = os.path.basename(os.path.normpath(os.path.dirname(torrent_file)))
            if dirname in cfg.download_categories:
                category = dirname
            else:
                category = ''
            add_task(hash, name, category)
            logger.info('Uploading torrent to the cloud: %s', torrent_file)
            upload_torrent(event.src_path)
            logger.debug('Deleting torrent from watchdir: %s', torrent_file)
            os.remove(torrent_file)

    def on_created(self, event):
        self.process(event)


def load_tasks():
    for hash in db.keys():
        task = db[hash.encode("utf-8")]
        task.callback = socketio.emit
        tasks.append(task)


def watchdir():
    try:
        logger.debug('Initializing watchdog')
        observer = Observer()
        observer.schedule(MyHandler(), path=cfg.watchdir_location, recursive=True)
        observer.start()
        logger.info('Watchdir initialized')
        for dirpath, dirs, files in os.walk(cfg.watchdir_location):
            for filename in files:
                fname = os.path.join(dirpath, filename)
                if fname.endswith('.torrent'):
                    fname2 = fname.replace('.torrent', '2.torrent')
                    shutil.copy(fname, fname2)
                    os.remove(fname)
    except:
        raise


# Flask
@app.route('/')
@login_required
def home():
    return render_template('index.html', debug_enabled=debug_enabled)


@app.route('/upload', methods=["POST"])
@login_required
def upload():
    if request.files:
        torrent_file = request.files['file']
        filename = secure_filename(torrent_file.filename)
        if not os.path.isdir(runningdir + 'tmp'):
            os.makedirs(runningdir + 'tmp')
        torrent_file.save(os.path.join(runningdir + 'tmp', filename))
        upload_torrent(runningdir + 'tmp/' + filename)
    elif request.data:
        upload_magnet(request.data)
    return 'OK'


@app.route('/settings', methods=["POST", "GET"])
@login_required
def settings():
    if request.method == 'POST':
        if 'Restart' in request.form.values():
            logger.info('Restarting')
            from subprocess import Popen
            Popen(['python', 'utils.py', '--restart'], shell=False, stdin=None, stdout=None, stderr=None,
                  close_fds=True)
            sys.exit()
        elif 'Shutdown' in request.form.values():
            logger.info('Shutdown recieved')
            sys.exit()
        elif 'Update' in request.form.values():
            logger.info('Update - will restart')
            from subprocess import Popen
            Popen(['python', 'utils.py', '--update'], shell=False, stdin=None, stdout=None, stderr=None, close_fds=True)
            sys.exit()
        else:
            global prem_config
            if request.form.get('debug_enabled'):
                prem_config.set('global', 'debug_enabled', '1')
            else:
                prem_config.set('global', 'debug_enabled', '0')
            if request.form.get('logfile_enabled'):
                prem_config.set('global', 'logfile_enabled', '1')
            else:
                prem_config.set('global', 'logfile_enabled', '0')
            if request.form.get('login_enabled'):
                prem_config.set('security', 'login_enabled', '1')
            else:
                prem_config.set('security', 'login_enabled', '0')
            if request.form.get('download_enabled'):
                prem_config.set('downloads', 'download_enabled', '1')
            else:
                prem_config.set('downloads', 'download_enabled', '0')
            if request.form.get('remove_cloud'):
                prem_config.set('downloads', 'remove_cloud', '1')
            else:
                prem_config.set('downloads', 'remove_cloud', '0')
            if request.form.get('copylink_toclipboard'):
                prem_config.set('downloads', 'copylink_toclipboard', '1')
                prem_config.set('downloads', 'download_enabled', '0')
            else:
                prem_config.set('downloads', 'copylink_toclipboard', '0')
            if request.form.get('watchdir_enabled'):
                prem_config.set('upload', 'watchdir_enabled', '1')
                watchdir()
            else:
                prem_config.set('upload', 'watchdir_enabled', '0')
            if request.form.get('nzbtomedia_enabled'):
                prem_config.set('nzbtomedia', 'nzbtomedia_enabled', '1')
            else:
                prem_config.set('nzbtomedia', 'nzbtomedia_enabled', '0')
            prem_config.set('global', 'server_port', request.form.get('server_port'))
            prem_config.set('security', 'username', request.form.get('username'))
            prem_config.set('security', 'password', request.form.get('password'))
            prem_config.set('premiumize', 'customer_id', request.form.get('customer_id'))
            prem_config.set('premiumize', 'pin', request.form.get('pin'))
            prem_config.set('downloads', 'download_categories', request.form.get('download_categories'))
            prem_config.set('downloads', 'download_location', request.form.get('download_location'))
            prem_config.set('downloads', 'download_ext', request.form.get('download_ext'))
            prem_config.set('downloads', 'download_size', request.form.get('download_size'))
            prem_config.set('upload', 'watchdir_location', request.form.get('watchdir_location'))
            prem_config.set('nzbtomedia', 'nzbtomedia_location', request.form.get('nzbtomedia_location'))
            with open(runningdir + 'settings.cfg', 'w') as configfile:  # save
                prem_config.write(configfile)
            cfg.check_config()

    return render_template('settings.html', settings=prem_config)


@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    username = request.form['username']
    password = request.form['password']
    if username == cfg.web_username and password == cfg.web_password:
        login_user(User(username, password))
        return redirect(url_for('home'))
    else:
        flash('Username or password incorrect')
        return 'nope'


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/list')
@login_required
def list():
    payload = {'customer_id': cfg.prem_customer_id, 'pin': cfg.prem_pin}
    r = requests.get("https://www.premiumize.me/torrent/list", params=payload)
    return r.text


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'img/favicon.ico')


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@login_manager.user_loader
def load_user(userid):
    return User(cfg.web_username, cfg.web_password)


@socketio.on('delete_task')
def delete_task(message):
    payload = {'customer_id': cfg.prem_customer_id, 'pin': cfg.prem_pin,
               'hash': message['data']}
    r = requests.post("https://www.premiumize.me/torrent/delete", payload)
    responsedict = json.loads(r.content)
    if responsedict['status'] == "success":
        emit('delete_success', {'data': message['data']})
    else:
        emit('delete_failed', {'data': message['data']})


@socketio.on('connect')
def test_message():
    emit('hello_client', {'data': 'Server says hello!'})


@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected')


@socketio.on('hello_server')
def hello_server(message):
    send_categories()
    scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=0)
    print(message['data'])


@socketio.on('message')
def handle_message(message):
    print('received message: ' + message)


@socketio.on('json')
def handle_json(json):
    print('received json: ' + str(json))


@socketio.on('change_category')
def change_category(message):
    data = message['data']
    task = get_task(data['hash'])
    task.update(category=data['category'])


# Start watchdog if watchdir is enabled
if cfg.watchdir_enabled:
    watchdir()

# start the server with the 'run()' method
if __name__ == '__main__':
    try:
        load_tasks()
        scheduler = APScheduler(GeventScheduler())
        scheduler.init_app(app)
        scheduler.scheduler.add_job(update, 'interval', id='update',
                                    seconds=active_interval, max_instances=1)
        scheduler.start()
        socketio.run(app, port=prem_config.getint('global', 'server_port'), use_reloader=False)
    except:
        raise
