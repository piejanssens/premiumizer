#from gevent import monkey; monkey.patch_thread(threading=True, _threading_local=True, Event=False)
import os, sys, json
import time
import logging

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), 'lib')))

import shelve
import ConfigParser
import requests 
from threading import Thread, Timer, Event
from werkzeug import secure_filename
from flask import Flask, flash, request, redirect, url_for, render_template, send_from_directory
from flask.ext.login import LoginManager, login_required, login_user, logout_user, UserMixin
from flask.ext.socketio import SocketIO, emit
from flask_apscheduler import APScheduler, views
from apscheduler.schedulers.gevent import GeventScheduler
from DownloadTask import DownloadTask
#pip install greenlet, apscheduler
import unicodedata
from string import ascii_letters, digits
import six
import os
from chardet import detect
import datetime
import logging
from logging.handlers import RotatingFileHandler

# "https://www.premiumize.me/static/api/torrent.html"


prem_config = ConfigParser.RawConfigParser()
if  not os.path.isfile('settings.cfg'):
    import shutil
    shutil.copy('settings.cfg.tpl', 'settings.cfg')

prem_config.read('settings.cfg')

logger = logging.getLogger("Rotating Log")

# add a rotating handler
logger.addHandler(RotatingFileHandler('premiumizer.log', maxBytes=(20*1024), backupCount=5))

# add a formatter
syslog = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)s : %(message)s')
syslog.setFormatter(formatter)
logger.addHandler(syslog)

if prem_config.getboolean('global', 'debug_enabled'):
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

logger.info('Logger Initialized')

if prem_config.getboolean('downloads', 'download_enabled'):
    download_path = prem_config.get('downloads', 'download_location')
    if not os.path.exists(download_path):
        logger.info('Creating Download Path at %s', download_path)
        os.makedirs(download_path)
        
if prem_config.getboolean('upload', 'watchdir_enabled'):
    upload_path = prem_config.get('upload', 'watchdir_location')
    if not os.path.exists(upload_path):
        logger.info('Creating Upload Path at %s', upload_path)
        os.makedirs(upload_path)

logger.info('Initializing Flask')
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config.update(
    DEBUG = prem_config.getboolean('global', 'debug_enabled'),
)

socketio = SocketIO(app)

app.config['LOGIN_DISABLED'] = not prem_config.getboolean('security', 'login_enabled')
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

db = shelve.open('premiumizer.db')
tasks = []
downloading = False
downloader = None
total_size_downloaded = None

#
class User(UserMixin):
    def __init__(self, userid, password):
        self.id = userid
        self.password = password

def toUnicode(original, *args):
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


# watchdir
def watchdir():
    print 'watchdir'
    path_to_watch = prem_config.get('upload', 'watchdir_location')
    before = dict ([(f, None) for f in os.listdir (path_to_watch)])
    while 1:
      time.sleep ((prem_config.getint('global', 'idle_interval')))
      after = dict ([(f, None) for f in os.listdir (path_to_watch)])
      added = [f for f in after if not f in before]
      if added:
          time.sleep(2)
          logger.info('Uploading torrent to the cloud: %s', ", ".join (added))
          filepath = upload_path + "/" + ''.join(added)
          upload_torrent(filepath)
          logger.debug('Deleting torrent from the watchdir: %s', ", ".join (added))
          os.remove(filepath)


def watchdir_win32():
    path_to_watch = prem_config.get('upload', 'watchdir_location')
    change_handle = win32file.FindFirstChangeNotification (
        path_to_watch,
        0,
        win32con.FILE_NOTIFY_CHANGE_FILE_NAME
    )
    try:
        old_path_contents = dict ([(f, None) for f in os.listdir (path_to_watch)])
        while 1:
            result = win32event.WaitForSingleObject (change_handle, 500)
            if result == win32con.WAIT_OBJECT_0:
                new_path_contents = dict ([(f, None) for f in os.listdir (path_to_watch)])
                added = [f for f in new_path_contents if not f in old_path_contents]
                if added:
                    time.sleep(2)
                    logger.info('Uploading torrent to the cloud: %s', ", ".join (added))
                    filepath = upload_path + "/" + ''.join(added)
                    upload_torrent(filepath)
                    os.remove(filepath)
                    logger.debug('Deleting torrent from the watchdir: %s', ", ".join (added))
                old_path_contents = new_path_contents
                win32file.FindNextChangeNotification (change_handle)
    finally: win32file.FindCloseChangeNotification (change_handle)

def watchdir_linux2():
    i = inotify.adapters.Inotify()
    i.add_watch((prem_config.get('upload', 'watchdir_location')))
    try:
        for event in i.event_gen():
            if event is IN_CREATE:
                time.sleep(2)
                (header, type_names, watch_path, filename) = event
                logger.info('Uploading torrent to the cloud: %s', filename)
                filepath = upload_path + "/" + filename
                upload_torrent(filepath)
                os.remove(filepath)
                logger.debug('Deleting torrent from the watchdir: %s', filename)
    finally:
        i.remove_watch((prem_config.get('upload', 'watchdir_location')))

#
def clean_name(original):
    valid_chars = "-_.() %s%s" % (ascii_letters, digits)
    cleaned_filename = unicodedata.normalize('NFKD', toUnicode(original)).encode('ASCII', 'ignore')
    valid_string = ''.join(c for c in cleaned_filename if c in valid_chars)
    return ' '.join(valid_string.split())


def notify_nzbtomedia(task):
    full_path = prem_config.get('nzbtomedia', 'nzbtomedia_location')
    if os.path.isfile(full_path):
        os.system(full_path, task.download_location + ' ' + task.name + ' ' + task.category + ' ' + task.hash)
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
        logger.debug('Want to update stats, but downloader doesn\'t exist yet.')


def download_file(task, full_path, url):
        logger.info('Downloading file from: %s', full_path)
        global downloader
        downloader = SmartDL(url, full_path, progress_bar=False, logger=logger)
        stat_job = scheduler.scheduler.add_job(get_download_stats, args=(task,), trigger='interval', seconds=1, max_instances=1, next_run_time=datetime.datetime.now())
        downloader.start(blocking=True)
        while not downloader.isFinished():
            print('wrong! waiting for downloader before finished')
        stat_job.remove()
        if downloader.isSuccessful():
            global total_size_downloaded
            total_size_downloaded += downloader.get_dl_size()
            logger.info('Finished downloading file from: %s', full_path)
        else:
            logger.error('Error while downloading file from: %s', full_path)
            for e in downloader.get_errors():
                logger.error(str(e))

#TODO continue log statements

def process_dir(task, path, new_name, dir_content):
    if not dir_content:
        return None
    new_path = os.path.join(path, new_name)
    if not os.path.exists(new_path):
        os.makedirs(new_path)
    for x in dir_content:
        type = dir_content[x]['type']
        if type == 'dir':
            process_dir(task, new_path, clean_name(x), dir_content[x]['children'])
        elif type == 'file':
            download_file(task, new_path + '/' + clean_name(x), dir_content[x]['url'].replace('https', 'http', 1))
    
# Copy links to clipboard        
def getlinks_task(task):
    global downloading
    payload = {'customer_id': prem_config.get('premiumize', 'customer_id'), 'pin': prem_config.get('premiumize', 'pin'), 'hash': task.hash}
    r = requests.post("https://www.premiumize.me/torrent/browse", payload)
    downloading = True
    process_dir_links(task, clean_name(task.name), json.loads(r.content)['data']['content'])
    task.update(local_status='finished', progress=100)
    downloading = False


def process_dir_links(task, new_name, dir_content):
    if not dir_content:
        return None
    for x in dir_content:
        type = dir_content[x]['type']
        if type == 'dir':
            process_dir_links(task, clean_name(x), dir_content[x]['children'])
        elif type == 'file':
            if dir_content[x]['url'].lower().endswith(('.mkv', 'mp4')) and dir_content[x]['size'] > 100000000:
                logger.info('Link copied to clipboard for: %s', dir_content[x]['name'])
                pyperclip.copy(dir_content[x]['url'])

#                
def download_task(task):
    global downloading
    base_path = prem_config.get('downloads', 'download_location')
    if task.category:
        base_path = os.path.join(base_path, task.category)
    task.download_location = os.path.join(base_path, clean_name(task.name))
    payload = {'customer_id': prem_config.get('premiumize', 'customer_id'), 'pin': prem_config.get('premiumize', 'pin'), 'hash': task.hash}
    r = requests.post("https://www.premiumize.me/torrent/browse", payload)
    global total_size_downloaded
    total_size_downloaded = 0
    downloading = True
    process_dir(task, base_path, clean_name(task.name), json.loads(r.content)['data']['content'])
    task.update(local_status='finished', progress=100)
    downloading = False
    if prem_config.getboolean('nzbtomedia', 'nzbtomedia_enabled'):
        notify_nzbtomedia(task)


def update():
    logger.debug('Updating')
    global update_interval
    idle = True
    payload = {'customer_id': prem_config.get('premiumize', 'customer_id'), 'pin': prem_config.get('premiumize', 'pin')}
    r = requests.post("https://www.premiumize.me/torrent/list", payload)
    response_content = json.loads(r.content)
    if response_content['status'] == "success":
        torrents = response_content['torrents']
        idle = parse_tasks(torrents)
    else:
        socketio.emit('premiumize_connect_error', {})
    if idle:
        update_interval = prem_config.getint('global', 'idle_interval')
    else:
        update_interval = prem_config.getint('global', 'active_interval')
    scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=update_interval)


def parse_tasks(torrents):
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
            task = DownloadTask(socketio.emit, torrent['hash'].encode("utf-8"), torrent['size'], torrent['name'], 'tv') #TODO
            task.update(progress=torrent['percent_done'], cloud_status=torrent['status'], speed=torrent['speed_down'])
            tasks.append(task)
        elif task.local_status != 'finished':
            if task.cloud_status == 'uploading':
                task.update(progress=torrent['percent_done'], cloud_status=torrent['status'], name=torrent['name'], size=torrent['size'])
            elif task.cloud_status == 'finished' and task.local_status != 'finished':
                if prem_config.getboolean('downloads', 'download_enabled') and task.category \
                        and task.category in prem_config.get('downloads', 'download_categories').split(','):
                    if not downloading:
                        task.update(progress=torrent['percent_done'], cloud_status=torrent['status'], local_status='downloading')
                        scheduler.scheduler.add_job(download_task, args=(task,), replace_existing=True, max_instances=1)
                    elif task.local_status != 'downloading':
                        task.update(progress=torrent['percent_done'], cloud_status=torrent['status'], local_status='queued') 
                elif prem_config.getboolean('downloads', 'copylink_toclipboard'):
                    getlinks_task(task)
                else:
                    task.update(progress=torrent['percent_done'], cloud_status=torrent['status'], local_status='finished')
            else:
                task.update(progress=torrent['percent_done'], cloud_status=torrent['status'], name=torrent['name'], speed=torrent['speed_down'])
        else:
            task.update()
        hashes_online.append(task.hash)
        task.callback = None
        db[task.hash] = task
        task.callback = socketio.emit

#   Delete local tasks that are removed from cloud
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
    for task in tasks:
        if task.hash == hash:
            return task
    return None


def add_task(hash, name, category):
    tasks.append(DownloadTask(0,0,hash,name,'upload',category))


def upload_torrent(filename):
    payload = {'customer_id': prem_config.get('premiumize', 'customer_id'), 'pin': prem_config.get('premiumize', 'pin')}
    files = {'file': open(filename, 'rb')}
    r = requests.post("https://www.premiumize.me/torrent/add", payload, files=files)
    response_content = json.loads(r.content)
    if response_content['status'] == "success":
        torrents = response_content['torrents']
        parse_tasks(torrents)
        if not prem_config.getboolean('upload', 'watchdir_enabled'):
            os.remove(filename)
        return True
    else:
        return False


def upload_magnet(magnet):
    payload = {'customer_id': prem_config.get('premiumize', 'customer_id'), 'pin': prem_config.get('premiumize', 'pin'), 'url': magnet}
    r = requests.post("https://www.premiumize.me/torrent/add", payload)
    response_content = json.loads(r.content)
    if response_content['status'] == "success":
        torrents = response_content['torrents']
        parse_tasks(torrents)
        return True
    else:
        return False


def send_categories():
    emit('download_categories', {'data': prem_config.get('downloads', 'download_categories').split(',')})


# Flask
@app.route('/')
@login_required
def home():
    return render_template('index.html')


@app.route('/upload', methods=["POST"])
@login_required
def upload():
    if request.files:
        torrent_file = request.files['file']
        filename = secure_filename(torrent_file.filename)
        if not os.path.isdir('tmp'):
            os.makedirs('tmp')
        torrent_file.save(os.path.join('tmp', filename))
        upload_torrent('tmp/'+filename)
    elif request.data:
        upload_magnet(request.data)
    return 'OK'


@app.route('/settings', methods=["POST", "GET"])
@login_required
def settings():
    if request.method == 'POST':
        if 'Reboot' in request.form.values():
            from subprocess import Popen
            Popen(['python', 'restart.py'], shell=False,stdin=None,stdout=None,stderr=None,close_fds=True)
            sys.exit()
        elif 'Shutdown' in request.form.values():
            sys.exit()
        else:
            global prem_config
            if request.form.get('debug_enabled'):
                prem_config.set('global', 'debug_enabled', 1)
            else:
                prem_config.set('global', 'debug_enabled', 0)
            if request.form.get('login_enabled'):
                prem_config.set('security', 'login_enabled', 1)
            else:
                prem_config.set('security', 'login_enabled', 0)
            if request.form.get('download_enabled'):
                prem_config.set('downloads', 'download_enabled', 1)
            else:
                prem_config.set('downloads', 'download_enabled', 0)
            if request.form.get('copylink_toclipboard'):
                prem_config.set('downloads', 'copylink_toclipboard ', 1)
            else:
                prem_config.set('downloads', 'copylink_toclipboard ', 0)
            if request.form.get('watchdir_enabled'):
                prem_config.set('upload', 'watchdir_enabled', 1)
            else:
                prem_config.set('upload', 'watchdir_enabled', 0)
            if request.form.get('nzbtomedia_enabled'):
                prem_config.set('nzbtomedia', 'nzbtomedia_enabled', 1)
            else:
                prem_config.set('nzbtomedia', 'nzbtomedia_enabled', 0)
            prem_config.set('global', 'server_port', request.form.get('server_port'))
            prem_config.set('security', 'username',  request.form.get('username'))
            prem_config.set('security', 'password',  request.form.get('password'))
            prem_config.set('premiumize', 'customer_id',  request.form.get('customer_id'))
            prem_config.set('premiumize', 'pin',  request.form.get('pin'))
            prem_config.set('downloads', 'download_categories',  request.form.get('download_categories'))
            prem_config.set('downloads', 'download_location',  request.form.get('download_location'))
            prem_config.set('upload', 'watchdir_location',  request.form.get('watchdir_location'))
            prem_config.set('nzbtomedia', 'nzbtomedia_location',  request.form.get('nzbtomedia_location'))
            with open('settings.cfg', 'w') as configfile:    # save
                prem_config.write(configfile)
    return render_template('settings.html', settings=prem_config)

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    username = request.form['username']
    password = request.form['password']
    if username == prem_config.get('security', 'username') and password == prem_config.get('security', 'password'):
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
    payload = {'customer_id': prem_config.get('premiumize', 'customer_id'), 'pin': prem_config.get('premiumize', 'pin')}
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
    return User(prem_config.get('security', 'username'), prem_config.get('security', 'password'))


@socketio.on('delete_task')
def delete_task(message):
    payload = {'customer_id': prem_config.get('premiumize', 'customer_id'), 'pin': prem_config.get('premiumize', 'pin'), 'hash': message['data']}
    r = requests.post("https://www.premiumize.me/torrent/delete", payload)
    responseDict = json.loads(r.content)
    if responseDict['status'] == "success":
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

def load_tasks():
    for hash in db.keys():
        task = db[hash.encode("utf-8")]
        task.callback = socketio.emit
        tasks.append(task)

# Load downloads module if enabled
if prem_config.getboolean('downloads', 'download_enabled'):
    from pySmartDL import SmartDL
    
# Load copylinks to clipboard module if enabled
if prem_config.getboolean('downloads', 'copylink_toclipboard'):
    import pyperclip

# Start the watchdir thread if enabled
if prem_config.getboolean('upload', 'watchdir_enabled'):
    if sys.platform == 'win32':
        import win32file, win32event, win32con
        t = Thread(target=watchdir_win32)
    #elif sys.platform == 'linux2':
    #    import inotify.adapters
    #    t = Thread(target=watchdir_linux2)
    else:
        t = Thread(target=watchdir)
    t.daemon = True
    t.start()
# start the server with the 'run()' method
if __name__ == '__main__':
    load_tasks()
    scheduler = APScheduler(GeventScheduler())
    scheduler.init_app(app)
    scheduler.scheduler.add_job(update, 'interval', id='update', seconds=prem_config.getint('global', 'active_interval'), max_instances=1)
    scheduler.start()
    socketio.run(app, port=prem_config.getint('global', 'server_port'))
