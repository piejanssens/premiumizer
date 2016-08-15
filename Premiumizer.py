#! /usr/bin/env python
import ConfigParser
import datetime
import hashlib
import json
import logging
import os
import re
import shelve
import shutil
import smtplib
import subprocess
import sys
import time
import unicodedata
from email.mime.text import MIMEText
from logging.handlers import RotatingFileHandler
from string import ascii_letters, digits

import bencode
import gevent
import myjdapi
import requests
import six
from apscheduler.schedulers.gevent import GeventScheduler
from chardet import detect
from flask import Flask, flash, request, redirect, url_for, render_template, send_from_directory
from flask_apscheduler import APScheduler
from flask_login import LoginManager, login_required, login_user, logout_user, UserMixin
from flask_socketio import SocketIO, emit
from gevent import local
from pySmartDL import SmartDL, utils
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer
from werkzeug.utils import secure_filename

from DownloadTask import DownloadTask

# "https://www.premiumize.me/api"
print ('------------------------------------------------------------------------------------------------------------')
print ('|                                                                                                           |')
print ('-------------------------------------------WELCOME TO PREMIUMIZER-------------------------------------------')
print ('|                                                                                                           |')
print ('------------------------------------------------------------------------------------------------------------')
# Initialize config values
prem_config = ConfigParser.RawConfigParser()
runningdir = os.path.split(os.path.abspath(os.path.realpath(sys.argv[0])))[0] + '/'
rootdir = runningdir[:-12]
try:
    os_arg = sys.argv[1]
except:
    os_arg = ''
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
    print ('---------------------------------------------------------------------------------------------------------')
    print ('|                                                                                                        |')
    print ('------------------------PREMIUMIZER IS RUNNING IN DEBUG MODE, THIS IS NOT RECOMMENDED--------------------')
    print ('|                                                                                                        |')
    print ('---------------------------------------------------------------------------------------------------------')
    logger.info('----------------------------------')
    logger.info('----------------------------------')
    logger.info('----------------------------------')
    logger.info('DEBUG Logger Initialized')
    handler = logging.handlers.RotatingFileHandler(runningdir + 'premiumizerDEBUG.log', maxBytes=(500 * 1024))
    handler.setFormatter(formatterdebug)
    logger.addHandler(handler)
    logger.info('DEBUG Logfile Initialized')
else:
    logger = logging.getLogger("Rotating log")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)-s: %(levelname)-s : %(message)s', datefmt='%m-%d %H:%M:%S')
    syslog.setFormatter(formatter)
    logger.addHandler(syslog)
    logging.getLogger('apscheduler.executors').addHandler(logging.NullHandler())
    logger.info('-------------------------------------------------------------------------------------')
    logger.info('-------------------------------------------------------------------------------------')
    logger.info('-------------------------------------------------------------------------------------')
    logger.info('Logger Initialized')
    handler = logging.handlers.RotatingFileHandler(runningdir + 'premiumizer.log', maxBytes=(500 * 1024))
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.info('Logfile Initialized')


# Catch uncaught exceptions in log
def uncaught_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, (SystemExit, KeyboardInterrupt)):
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
    logger.info('*************************************************************************************')
    logger.info('---------------------------Premiumizer has been updated!!----------------------------')
    logger.info('*************************************************************************************')
    if os.path.isfile(runningdir + 'settings.cfg.old2'):
        logger.info('*************************************************************************************')
        logger.info('-------Settings file has been updated, old settings file renamed to .old-------')
        logger.info('*************************************************************************************')
    try:
        os.rename(runningdir + 'settings.cfg.old2', runningdir + 'settings.cfg.old')
    except:
        logger.error('Could not rename old settings file')
    prem_config.set('update', 'updated', '0')
    with open(runningdir + 'settings.cfg', 'w') as configfile:
        prem_config.write(configfile)

#
logger.info('Running at %s', runningdir)


# noinspection PyAttributeOutsideInit
class PremConfig:
    def __init__(self):
        self.jd_connected = 0
        self.check_config()

    def check_config(self):
        logger.debug('Initializing config')
        self.bind_ip = prem_config.get('global', 'bind_ip')
        self.web_login_enabled = prem_config.getboolean('security', 'login_enabled')
        if self.web_login_enabled:
            logger.debug('Premiumizer login is enabled')
            self.web_username = prem_config.get('security', 'username')
            self.web_password = prem_config.get('security', 'password')

        self.update_available = 0
        self.update_localcommit = ''
        self.update_diffcommit = ''
        self.update_status = ''
        self.update_date = prem_config.get('update', 'update_date')
        self.auto_update = prem_config.getboolean('update', 'auto_update')
        self.prem_customer_id = prem_config.get('premiumize', 'customer_id')
        self.prem_pin = prem_config.get('premiumize', 'pin')
        self.remove_cloud = prem_config.getboolean('downloads', 'remove_cloud')
        self.download_enabled = prem_config.getboolean('downloads', 'download_enabled')
        if self.download_enabled:
            self.download_builtin = 1
        self.download_max = prem_config.getint('downloads', 'download_max')
        self.download_location = prem_config.get('downloads', 'download_location')
        if os.path.isfile(runningdir + 'nzbtomedia/NzbToMedia.py'):
            self.nzbtomedia_location = (runningdir + 'nzbtomedia/NzbToMedia.py')
            self.nzbtomedia_builtin = 1
        else:
            self.nzbtomedia_location = prem_config.get('downloads', 'nzbtomedia_location')
        self.jd_enabled = prem_config.getboolean('downloads', 'jd_enabled')
        self.jd_username = prem_config.get('downloads', 'jd_username')
        self.jd_password = prem_config.get('downloads', 'jd_password')
        self.jd_device = prem_config.get('downloads', 'jd_device')
        if self.jd_enabled:
            self.download_builtin = 0
            if not self.jd_connected:
                self.jd = myjdapi.Myjdapi()
                try:
                    self.jd.set_app_key('https://git.io/vaDti')
                    self.jd.connect(self.jd_username, self.jd_password)
                    self.jd_connected = 1
                except:
                    logger.error('Could not connect to My Jdownloader')
                    self.jd_connected = 0
                try:
                    self.jd.get_device(self.jd_device)
                except:
                    logger.error('Could not get device name for My Jdownloader')

        self.watchdir_enabled = prem_config.getboolean('upload', 'watchdir_enabled')
        self.watchdir_location = prem_config.get('upload', 'watchdir_location')
        if self.watchdir_enabled:
            logger.info('Watchdir is enabled at: %s', self.watchdir_location)
            if not os.path.exists(self.watchdir_location):
                os.makedirs(self.watchdir_location)

        self.categories = []
        self.download_categories = ''
        for x in range(1, 6):
            y = prem_config.get('categories', ('cat_name' + str([x])))
            z = prem_config.get('categories', ('cat_dir' + str([x])))
            if y != '':
                cat_name = y
                if z == '':
                    cat_dir = self.download_location + '/' + y
                else:
                    cat_dir = z
                cat_ext = prem_config.get('categories', ('cat_ext' + str([x]))).split(',')
                cat_delsample = prem_config.getboolean('categories', ('cat_delsample' + str([x])))
                cat_nzbtomedia = prem_config.getboolean('categories', ('cat_nzbtomedia' + str([x])))
                cat = {'name': cat_name, 'dir': cat_dir, 'ext': cat_ext, 'delsample': cat_delsample,
                       'nzb': cat_nzbtomedia}
                self.categories.append(cat)
                self.download_categories += str(cat_name + ',')
                if self.download_enabled:
                    if not os.path.exists(cat_dir):
                        logger.info('Creating Download Path at: %s', cat_dir)
                        os.makedirs(cat_dir)
                if self.watchdir_enabled:
                    sub = self.watchdir_location + '/' + cat_name
                    if not os.path.exists(sub):
                        logger.info('Creating watchdir Path at %s', sub)
                        os.makedirs(sub)
        self.download_categories = self.download_categories[:-1]
        self.download_categories = self.download_categories.split(',')

        self.email_enabled = prem_config.getboolean('notifications', 'email_enabled')
        if self.email_enabled:
            self.email_on_failure = prem_config.getboolean('notifications', 'email_on_failure')
            self.email_from = prem_config.get('notifications', 'email_from')
            self.email_to = prem_config.get('notifications', 'email_to')
            self.email_server = prem_config.get('notifications', 'email_server')
            self.email_port = prem_config.getint('notifications', 'email_port')
            self.email_encryption = prem_config.getboolean('notifications', 'email_encryption')
            self.email_username = prem_config.get('notifications', 'email_username')
            self.email_password = prem_config.get('notifications', 'email_password')

        logger.debug('Initializing config complete')


cfg = PremConfig()


# Automatic update checker
def check_update(auto_update=cfg.auto_update):
    logger.debug('def check_update started')

    time_job = scheduler.scheduler.get_job('check_update').next_run_time.replace(tzinfo=None)
    time_now = datetime.datetime.now()
    diff = time_job - time_now
    diff = 21600 - diff.total_seconds()
    if (diff > 120) or (cfg.update_status == ''):
        try:
            subprocess.check_call(['git', '-C', runningdir, 'fetch'])
        except:
            cfg.update_status = 'failed'
            logger.error('Update failed: could not git fetch: %s', runningdir)
        if cfg.update_status != 'failed':
            cfg.update_localcommit = subprocess.check_output(
                ['git', '-C', runningdir, 'log', '-n', '1', '--pretty=format:%h'])
            local_branch = str(
                subprocess.check_output(['git', '-C', runningdir, 'rev-parse', '--abbrev-ref', 'HEAD'])).rstrip('\n')
            remote_commit = subprocess.check_output(
                ['git', '-C', runningdir, 'log', '-n', '1', 'origin/' + local_branch, '--pretty=format:%h'])

            if cfg.update_localcommit != remote_commit:
                cfg.update_diffcommit = subprocess.check_output(
                    ['git', '-C', runningdir, 'log', '--oneline', local_branch + '..origin/' + local_branch])

                cfg.update_available = 1
                cfg.update_status = 'Update Available !!'
                if auto_update:
                    for task in tasks:
                        if task.local_status == (
                                            'downloading' or 'queued' or 'failed: download' or 'failed: nzbtomedia'):
                            scheduler.scheduler.reschedule_job('check_update', trigger='interval', minutes=30)
                            logger.info(
                                'Tried to update but downloads are not done or failed, trying again in 30 minutes')
                            cfg.update_status = \
                                'Update available, but not yet updated because downloads are not done or failed'
                            return
                    update_self()
            else:
                cfg.update_status = 'No update available, last time checked: ' + datetime.datetime.now().strftime(
                    "%d-%m %H:%M:%S") + ' --- last time updated: ' + cfg.update_date
        scheduler.scheduler.reschedule_job('check_update', trigger='interval', hours=6)


# noinspection PyProtectedMember
def update_self():
    logger.debug('def update_self started')
    logger.info('Update - will restart')
    cfg.update_date = datetime.datetime.now().strftime("%d-%m %H:%M:%S")
    prem_config.set('update', 'update_date', cfg.update_date)
    with open(runningdir + 'settings.cfg', 'w') as configfile:  # save
        prem_config.write(configfile)
    scheduler.shutdown(wait=False)
    socketio.stop()
    if os_arg == '--windows':
        subprocess.call(['python', runningdir + 'utils.py', '--update', '--windows'])
        os._exit(1)
    else:
        subprocess.Popen(['python', runningdir + 'utils.py', '--update'], shell=False, close_fds=True)
        os._exit(1)


# noinspection PyProtectedMember
def restart():
    logger.info('Restarting')
    scheduler.shutdown(wait=False)
    socketio.stop()
    if os_arg == '--windows':
        # windows service will automatically restart on 'failure'
        os._exit(1)
    else:
        subprocess.Popen(['python', runningdir + 'utils.py', '--restart'], shell=False, close_fds=True)
        os._exit(1)


# noinspection PyProtectedMember
def shutdown():
    logger.info('Shutdown recieved')
    scheduler.shutdown(wait=False)
    socketio.stop()
    if os_arg == '--windows':
        subprocess.call([rootdir + 'Installer/nssm.exe', 'stop', 'Premiumizer'])
    else:
        os._exit(1)


#
logger.debug('Initializing Flask')
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config.update(DEBUG=debug_enabled)
app.logger.addHandler(handler)
socketio = SocketIO(app)

app.config['LOGIN_DISABLED'] = not cfg.web_login_enabled
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
logger.debug('Initializing Flask complete')

# Initialise Database
logger.debug('Initializing Database')
db = shelve.open(runningdir + 'premiumizer.db')
logger.debug('Initializing Database complete')

# Initialise Globals
tasks = []
greenlet = local.local()
client_connected = 0
prem_session = requests.Session()


#
def gevent_sleep_time():
    global client_connected
    if client_connected:
        gevent.sleep(2)
    else:
        gevent.sleep(10)


class User(UserMixin):
    def __init__(self, userid, password):
        self.id = userid
        self.password = password


def to_unicode(original, *args):
    logger.debug('def to_unicode started')
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
    logger.debug('def ek started')
    if isinstance(original, (str, unicode)):
        try:
            return original.decode('UTF-8', 'ignore')
        except UnicodeDecodeError:
            raise
    return original


#
def clean_name(original):
    logger.debug('def clean_name started')
    valid_chars = "-_.() %s%s" % (ascii_letters, digits)
    cleaned_filename = unicodedata.normalize('NFKD', to_unicode(original)).encode('ASCII', 'ignore')
    valid_string = ''.join(c for c in cleaned_filename if c in valid_chars)
    return ' '.join(valid_string.split())


def notify_nzbtomedia():
    logger.debug('def notify_nzbtomedia started')
    if os.path.isfile(cfg.nzbtomedia_location):
        try:
            subprocess.check_output(
                ['python', cfg.nzbtomedia_location, greenlet.task.dldir, greenlet.task.name, greenlet.task.category,
                 greenlet.task.hash, 'generic'],
                stderr=subprocess.STDOUT, shell=False)
            returncode = 0
            logger.info('Send to nzbtomedia: %s', greenlet.task.name)
        except subprocess.CalledProcessError as e:
            logger.error('nzbtomedia failed for %s', greenlet.task.name)
            errorstr = ''
            tmp = str.splitlines(e.output)
            for line in tmp:
                if '[ERROR]' in line:
                    errorstr += line
            logger.error('%s: output: %s', greenlet.task.name, errorstr)
            returncode = 1
    else:
        logger.error('Error unable to locate nzbToMedia.py for: %s', greenlet.task.name)
        returncode = 1
    return returncode


def email(status):
    logger.debug('def email started')
    if status == 'download success':
        subject = 'Success for "%s"' % greenlet.task.name
        text = 'Download of "%s" has successfully completed.' % greenlet.task.name
        text += '\nStatus: SUCCESS'
        text += '\n\nStatistics:'
        text += '\nDownloaded size: %s' % utils.sizeof_human(greenlet.task.size)
        text += '\nDownload Time: %s' % utils.time_human(greenlet.task.dltime, fmt_short=True)
        text += '\nAverage download speed: %s' % greenlet.avgspeed
        text += '\n\nFiles:'
        for download in greenlet.download_list:
            text += '\n' + os.path.basename(download['path'])

    elif status == 'download failed':
        subject = 'Failure for "%s"' % greenlet.task.name
        text = 'Download of "%s" has failed.' % greenlet.task.name
        text += '\nStatus: FAILED\nError: %s' % greenlet.task.local_status
        text += '\n\nLog:\n'
        try:
            if debug_enabled:
                log = 'premiumizerDEBUG.log'
            else:
                log = 'premiumizer.log'
            with open(runningdir + log, 'r') as f:
                for line in f:
                    if greenlet.task.name in line:
                        text += line
        except:
            text += 'could not add log'

    else:
        subject = status
        text = status

    # Create message
    msg = MIMEText(text)
    msg['Subject'] = subject
    msg['From'] = cfg.email_from
    msg['To'] = cfg.email_to
    msg['Date'] = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg['X-Application'] = 'Premiumizer'

    # Send message
    try:
        smtp = smtplib.SMTP(cfg.email_server, cfg.email_port)

        if cfg.email_encryption:
            smtp.starttls()

        if cfg.email_username != '' and cfg.email_password != '':
            smtp.login(cfg.email_username, cfg.email_password)

        smtp.sendmail(cfg.email_from, cfg.email_to, msg.as_string())

        smtp.quit()
        if subject != status:
            logger.info('Email send for: %s', greenlet.task.name)
        else:
            logger.info('Email send for: %s', status)
    except Exception as err:
        if subject != status:
            logger.error('Email error for: %s error: %s', greenlet.task.name, err)
        else:
            logger.info('Email send for: %s', status)


def jd_query_package(jd, package_id):
    count = 0
    package = jd.downloads.query_packages([{"status": True, "bytesTotal": True, "bytesLoaded": True,
                                            "speed": True, "eta": True, "packageUUIDs": [package_id]}])

    while isinstance(package, bool):
        gevent.sleep(5)
        package = jd.downloads.query_packages([{"status": True, "bytesTotal": True, "bytesLoaded": True,
                                                "speed": True, "eta": True, "packageUUIDs": [package_id]}])
        count += 1
        if count == 12:
            package = {'status': 'Failed'}
            logger.error('JD did not return package status for: %s', greenlet.task.name)

    while 'status' not in package:
        try:
            package = package[0]
            if 'status' in package:
                break
        except:
            pass
        gevent.sleep(5)
        package = jd.downloads.query_packages([{"status": True, "bytesTotal": True, "bytesLoaded": True,
                                                "speed": True, "eta": True, "packageUUIDs": [package_id]}])
        count += 1
        if count == 24:
            package = {'status': 'Failed'}
            logger.error('JD did not return package status for: %s', greenlet.task.name)
    else:
        package['status'] = 'Failed'
        logger.error('JD did not return package status for: %s', greenlet.task.name)
    return package


def get_download_stats_jd(jd, package_name):
    count = 0
    gevent.sleep(10)
    start_time = time.time()
    query_packages = jd.downloads.query_packages()
    while not len(query_packages):
        gevent.sleep(5)
        query_packages = jd.downloads.query_packages()
        count += 1
        if count == 10:
            logger.error('Could not find package in JD for: %s', greenlet.task.name)
            return 1
    while not any(package['name'] in package_name for package in query_packages):
        gevent.sleep(5)
        query_packages = jd.downloads.query_packages()
        count += 1
        if count == 10:
            logger.error('Could not find package in JD for: %s', greenlet.task.name)
            return 1

    for package in query_packages:
        if package['name'] in package_name:
            package_id = str(package['uuid'])
            package = jd_query_package(jd, package_id)
            while package['status'] != 'Finished' and package['status'] != 'Failed':
                if greenlet.task.local_status == 'stopped':
                    try:
                        jd.downloads.cleanup("DELETE_ALL", "REMOVE_LINKS_ONLY", "ALL", packages_ids=[package_id])
                    except:
                        logger.error('Could not delete package in JD for : %s', greenlet.task.name)
                        pass
                    return 1
                try:
                    speed = package['speed']
                except:
                    speed = 0
                if speed == 0:
                    eta = ''
                else:
                    eta = " " + utils.time_human(package['eta'], fmt_short=True)
                try:
                    bytestotal = package["bytesTotal"]
                except:
                    logger.error('JD did not return package bytesTotal for: %s', greenlet.task.name)
                    return 1
                progress = round(float(package['bytesLoaded']) * 100 / package["bytesTotal"], 1)
                greenlet.task.update(speed=(utils.sizeof_human(speed) + '/s --- ' + utils.sizeof_human(
                    package['bytesLoaded']) + ' / ' + utils.sizeof_human(package['bytesTotal'])), progress=progress,
                                     eta=eta)
                gevent_sleep_time()
                package = jd_query_package(jd, package_id)
            # cfg.jd.disconnect()

            if package['status'] == 'Failed':
                logger.error('JD returned failed for: %s', greenlet.task.name)
                return 1
            stop_time = time.time()
            dltime = int(stop_time - start_time)
            greenlet.task.update(dltime=dltime)

            try:
                jd.downloads.cleanup("DELETE_FINISHED", "REMOVE_LINKS_ONLY", "ALL", packages_ids=[package_id])
            except:
                logger.error('Could not delete package in JD for: %s', greenlet.task.name)
                pass
            return 0


def get_download_stats(downloader, total_size_downloaded):
    logger.debug('def get_download_stats started')
    if downloader.get_status() == 'downloading':
        size_downloaded = total_size_downloaded + downloader.get_dl_size()
        progress = round(float(size_downloaded) * 100 / greenlet.task.size, 1)
        speed = downloader.get_speed(human=False)
        if speed == 0:
            eta = ''
        else:
            tmp = (greenlet.task.size - size_downloaded) / speed
            eta = ' ' + utils.time_human(tmp, fmt_short=True)
        greenlet.task.update(speed=(
            utils.sizeof_human(speed) + '/s --- ' + utils.sizeof_human(size_downloaded) + ' / ' + utils.sizeof_human(
                greenlet.task.size)), progress=progress, eta=eta)

    elif downloader.get_status() == 'combining':
        greenlet.task.update(speed='', eta=' Combining files')
    elif downloader.get_status() == 'paused':
        greenlet.task.update(speed='', eta=' Download paused')
    else:
        logger.debug('Want to update stats, but downloader status is invalid.')


def download_file():
    logger.debug('def download_file started')
    files_downloaded = 0
    total_size_downloaded = 0
    dltime = 0
    returncode = 0
    if cfg.jd_enabled:
        try:
            cfg.jd.reconnect()
            jd = cfg.jd.get_device(cfg.jd_device)
            cfg.jd_connected = 1
        except:
            try:
                cfg.jd = myjdapi.Myjdapi()
                cfg.jd.connect(cfg.jd_username, cfg.jd_password)
                jd = cfg.jd.get_device(cfg.jd_device)
                cfg.jd_connected = 1
            except:
                logger.error(
                    'Could not connect to My Jdownloader check username/password & device name, task failed: %s',
                    greenlet.task.name)
                cfg.jd_connected = 0
                return 1
        query_links = jd.downloads.query_links()
        package_name = str(re.sub('[^0-9a-zA-Z]+', ' ', greenlet.task.name).lower())

    for download in greenlet.download_list:
        logger.debug('Downloading file: %s', download['path'])
        if not os.path.isfile(download['path']):
            files_downloaded = 1
            if cfg.download_builtin:
                downloader = SmartDL(download['url'], download['path'], progress_bar=False, logger=logger,
                                     threads_count=1)
                downloader.start(blocking=False)
                while not downloader.isFinished():
                    get_download_stats(downloader, total_size_downloaded)
                    gevent_sleep_time()
                    # if greenlet.task.local_status == "paused":            #   When paused to long
                    #   downloader.pause()                                  #   PysmartDl fails with WARNING :
                    #   while greenlet.task.local_status == "paused":       #   Diff between downloaded files and expected
                    #       gevent_sleep_time()                               #   filesizes is .... Retrying...
                    #   downloader.unpause()
                    if greenlet.task.local_status == "stopped":
                        while not downloader.isFinished():  # Have to use while loop
                            downloader.stop()  # does not stop when called once ..
                            gevent.sleep(0.5)  # let's hammer the stop call..
                        return 1
                if downloader.isSuccessful():
                    dltime += downloader.get_dl_time()
                    total_size_downloaded += downloader.get_dl_size()
                    logger.debug('Finished downloading file: %s', download['path'])
                    greenlet.task.update(dltime=dltime)
                else:
                    logger.error('Error for %s: while downloading file: %s', greenlet.task.name, download['path'])
                    for e in downloader.get_errors():
                        logger.error(str(greenlet.task.name + ": " + e))
                    returncode = 1
            elif cfg.jd_connected:
                url = str(download['url'])
                filename = os.path.basename(download['path'])
                if len(query_links):
                    if any(link['name'] == filename for link in query_links):
                        continue
                jd.linkgrabber.add_links([{"autostart": True, "links": url, "packageName": package_name,
                                           "destinationFolder": greenlet.task.dldir, "overwritePackagizerRules": True}])
        else:
            logger.info('File not downloaded it already exists at: %s', download['path'])

    if cfg.jd_enabled and files_downloaded:
        if cfg.jd_connected:
            returncode = get_download_stats_jd(jd, package_name)

    return returncode


def is_sample(dir_content):
    media_extensions = [".mkv", ".avi", ".divx", ".xvid", ".mov", ".wmv", ".mp4", ".mpg", ".mpeg", ".vob", ".iso"]
    media_size = 150 * 1024 * 1024
    if dir_content['size'] < media_size:
        if dir_content['url'].lower().endswith(tuple(media_extensions)):
            if ('sample' or 'rarbg.com' in dir_content['url'].lower()) and (
                        'sample' not in greenlet.task.name.lower()):
                return True
    return False


def process_dir(dir_content, path, change_dldir=1):
    logger.debug('def processing_dir started')
    if not dir_content:
        return None
    for x in dir_content:
        type = dir_content[x]['type']
        if type == 'dir':
            new_path = os.path.join(path, clean_name(x))
            if change_dldir:
                greenlet.task.update(dldir=new_path)
            process_dir(dir_content[x]['children'], new_path, 0)
        elif type == 'file':
            if dir_content[x]['url'].lower().endswith(tuple(greenlet.task.dlext)):
                if greenlet.task.delsample:
                    sample = is_sample(dir_content[x])
                    if sample:
                        greenlet.size_remove += dir_content[x]['size']
                        continue
                if cfg.download_enabled:
                    if not os.path.exists(path):
                        os.makedirs(path)
                    download = {'path': path + '/' + clean_name(x), 'url': dir_content[x]['url']}
                    greenlet.download_list.append(download)
            else:
                greenlet.size_remove += dir_content[x]['size']


def download_process():
    logger.debug('def download_process started')
    returncode = 0
    greenlet.download_list = []
    greenlet.size_remove = 0
    payload = {'customer_id': cfg.prem_customer_id, 'pin': cfg.prem_pin,
               'hash': greenlet.task.hash}
    r = prem_connection("post", "https://www.premiumize.me/api/torrent/browse", payload)
    if r == 'failed':
        return 1
    greenlet.task.update(local_status='downloading', progress=0, speed='', eta='')
    process_dir(json.loads(r.content)['content'], greenlet.task.dldir)
    if greenlet.size_remove is not 0:
        greenlet.task.update(size=(greenlet.task.size - greenlet.size_remove))
    logger.info('Downloading: %s', greenlet.task.name)
    if greenlet.download_list:
        returncode = download_file()
    else:
        logger.error('Error for %s: Nothing to download .. Filtered out or bad torrent ?')
        returncode = 1
    return returncode


def download_task(task):
    logger.debug('def download_task started')
    greenlet.task = task
    greenlet.failed = 0
    failed = download_process()
    if failed and task.local_status != 'stopped':
        dldir = get_cat_var(task.category)
        dldir = dldir[0]
        task.update(local_status='failed: download retrying', dldir=dldir)
        logger.warning('Retrying failed download in 10 minutes for: %s', task.name)
        gevent.sleep(600)
        failed = download_process()
        if failed:
            task.update(local_status='failed: download')
    if task.dlnzbtomedia and not failed:
        failed = notify_nzbtomedia()
        if failed:
            task.update(local_status='failed: nzbtomedia')

    if cfg.remove_cloud and not failed:
        payload = {'customer_id': cfg.prem_customer_id, 'pin': cfg.prem_pin, 'type': 'torrent', 'id': task.hash}
        r = prem_connection("post", "https://www.premiumize.me/api/transfer/delete", payload)
        if r != 'failed':
            responsedict = json.loads(r.content)
            if responsedict['status'] == "success":
                logger.info('Automatically Deleted: %s from cloud', task.name)
                socketio.emit('delete_success', {'data': task.hash})
            else:
                msg = 'Torrent could not be removed from cloud: %s, message: %s' % (task.name, responsedict['message'])
                logger.error(msg)
                logger.info(responsedict['message'])
                if cfg.email_enabled:
                    email(msg)
                socketio.emit('delete_failed', {'data': task.hash})
        else:
            logger.error('Torrent could not be removed from cloud: %s', task.name)
            socketio.emit('delete_failed', {'data': task.hash})

    if not failed:
        if not cfg.remove_cloud:
            task.update(progress=100, local_status='finished')
        try:
            greenlet.avgspeed = str(utils.sizeof_human((task.size / task.dltime)) + '/s')
        except:
            greenlet.avgspeed = "0"
        logger.info('Download finished: %s size: %s time: %s speed: %s location: %s', task.name,
                    utils.sizeof_human(task.size), utils.time_human(task.dltime, fmt_short=True), greenlet.avgspeed,
                    task.dldir)
    if cfg.email_enabled and task.local_status != 'stopped':
        if not failed:
            if not cfg.email_on_failure:
                email('download success')
        else:
            email('download failed')
    if task.local_status == 'stopped':
        logger.warning('Download stopped for: %s', greenlet.task.name)
        try:
            shutil.rmtree(task.dldir)
        except:
            logger.warning('Could not delete folder for: %s', greenlet.task.name)
        task.update(progress=100, category='', local_status='waiting')
    scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=3)


def prem_connection(method, url, payload, files=None):
    logger.debug('def prem_connection started')
    r = None
    r_count = 0
    while r is None:
        r_count += 1
        try:
            if method == 'post':
                r = prem_session.post(url, payload, timeout=5)
            elif method == 'postfile':
                r = prem_session.post(url, payload, files=files, timeout=5)
            elif method == 'get':
                r = prem_session.get(url, params=payload, timeout=5)
        except:
            logger.warning('Connection to premiumize.me timed out')
            if r_count == 10:
                logger.error('Connection to premiumize.me timed out 10 times')
                if cfg.email_enabled:
                    email('premiumize.me connection error')
                return 'failed'
            pass
            gevent.sleep(3)
    return r


def update():
    logger.debug('def update started')
    idle = True
    update_interval = idle_interval
    payload = {'customer_id': cfg.prem_customer_id, 'pin': cfg.prem_pin}
    r = prem_connection("post", "https://www.premiumize.me/api/transfer/list", payload)
    if r != 'failed':
        response_content = json.loads(r.content)
        if response_content['status'] == "success":
            if not response_content['transfers']:
                update_interval *= 3
            transfers = response_content['transfers']
            idle = parse_tasks(transfers)
        else:
            socketio.emit('premiumize_connect_error', {})
    else:
        logger.error('premiumize.me connection error')
        socketio.emit('premiumize_connect_error', {})
    if not idle:
        update_interval = active_interval
    scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=update_interval)


def parse_tasks(transfers):
    logger.debug('def parse_task started')
    hashes_online = []
    hashes_local = []
    idle = True
    for task in tasks:
        hashes_local.append(task.hash)
    for transfer in transfers:
        task = get_task(transfer['hash'].encode("utf-8"))
        if not task:
            add_task(transfer['hash'].encode("utf-8"), transfer['size'], transfer['name'], '')
            task = get_task(transfer['hash'].encode("utf-8"))
            hashes_local.append(task.hash)
            task.update(progress=(int(transfer['progress']*100)), cloud_status=transfer['status'], speed=transfer['speed_down'])
        if task.local_status is None:
            if task.cloud_status != 'finished':
                if transfer['eta'] is None or 0:
                    eta = ''
                else:
                    eta = utils.time_human(transfer['eta'], fmt_short=True)
                if transfer['speed_down'] is None or 0:
                    speed = ''
                else:
                    speed = utils.sizeof_human(transfer['speed_down']) + '/s '
                task.update(progress=(int(transfer['progress']*100)), cloud_status=transfer['status'], name=transfer['name'],
                            size=transfer['size'], speed=speed, eta=eta)
                idle = False
            if task.cloud_status == 'finished':
                if cfg.download_enabled:
                    if task.category in cfg.download_categories:
                        if not task.local_status == ('queued' or 'downloading'):
                            task.update(local_status='queued')
                            gevent.sleep(3)
                            scheduler.scheduler.add_job(download_task, args=(task,), name=task.name,
                                                        misfire_grace_time=7200, coalesce=False, max_instances=1,
                                                        jobstore='downloads', executor='downloads',
                                                        replace_existing=True)
                    elif task.category == '':
                        task.update(local_status='waiting')
                else:
                    task.update(local_status='finished', speed=None)
        else:
            task.update(cloud_status=transfer['status'])

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


# noinspection PyUnboundLocalVariable
def get_cat_var(category):
    logger.debug('def get_cat_var started')
    if category != '':
        for cat in cfg.categories:
            if cat['name'] == category:
                dldir = cat['dir']
                dlext = cat['ext']
                delsample = cat['delsample']
                dlnzbtomedia = cat['nzb']
    else:
        dldir = None
        dlext = None
        delsample = 0
        dlnzbtomedia = 0
    return dldir, dlext, delsample, dlnzbtomedia


def add_task(hash, size, name, category):
    logger.debug('def add_task started')
    dldir, dlext, delsample, dlnzbtomedia = get_cat_var(category)
    task = DownloadTask(socketio.emit, hash, size, name, category, dldir, dlext, delsample, dlnzbtomedia)
    tasks.append(task)
    logger.info('Added: %s', task.name)
    scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=3)


def upload_torrent(filename):
    logger.debug('def upload_torrent started')
    payload = {'customer_id': cfg.prem_customer_id, 'pin': cfg.prem_pin, 'type': 'torrent'}
    files = {'src': open(filename, 'rb')}
    logger.debug('Uploading torrent to the cloud: %s', filename)
    r = prem_connection("postfile", "https://www.premiumize.me/api/transfer/create", payload, files)
    if r != 'failed':
        response_content = json.loads(r.content)
        if response_content['status'] == "success":
            logger.debug('Upload successful: %s', filename)
            return 0
        else:
            msg = 'Upload of torrent: %s failed, message: %s' % (filename, response_content['message'])
            logger.error(msg)
            if cfg.email_enabled:
                email(msg)
            return 1
    else:
        return 1


def upload_magnet(magnet):
    logger.debug('def upload_magnet started')
    payload = {'customer_id': cfg.prem_customer_id, 'pin': cfg.prem_pin, 'type': 'torrent', 'src': magnet}
    r = prem_connection("post", "https://www.premiumize.me/api/transfer/create", payload)
    if r != 'failed':
        response_content = json.loads(r.content)
        if response_content['status'] == "success":
            logger.debug('Upload magnet successful')
            return 0
        else:
            msg = 'Upload of torrent: %s failed, message: %s' % (magnet, response_content['message'])
            logger.error(msg)
            if cfg.email_enabled:
                email(msg)
            return 1
    else:
        return 1

def upload_nzb(filename):
    logger.debug('def upload_nzb started')
    payload = {'customer_id': cfg.prem_customer_id, 'pin': cfg.prem_pin, 'type': 'nzb'}
    files = {'src': open(filename, 'rb')}
    logger.debug('Uploading nzb to the cloud: %s', filename)
    r = prem_connection("postfile", "https://www.premiumize.me/api/transfer/create", payload, files)
    if r != 'failed':
        response_content = json.loads(r.content)
        if response_content['status'] == "success":
            logger.debug('Upload successful: %s', filename)
            return 0
        else:
            msg = 'Upload of nzb: %s failed, message: %s' % (filename, response_content['message'])
            logger.error(msg)
            if cfg.email_enabled:
                email(msg)
            return 1
    else:
        return 1

def send_categories():
    logger.debug('def send_categories started')
    emit('download_categories', {'data': cfg.download_categories})


class MyHandler(PatternMatchingEventHandler):
    patterns = ["*.torrent", "*.magnet", "*.nzb"]

    # noinspection PyMethodMayBeStatic
    def process(self, event):
        if event.event_type == 'created' and event.is_directory is False:
            gevent.sleep(1)
            watchdir_file = event.src_path
            logger.debug('New torrent file detected at: %s', watchdir_file)
            dirname = os.path.basename(os.path.normpath(os.path.dirname(watchdir_file)))
            if dirname in cfg.download_categories:
                category = dirname
            else:
                category = ''

            if watchdir_file.endswith('.torrent'):
                hash, name = torrent_metainfo(watchdir_file)
                add_task(hash, 0, name, category)
                failed = upload_torrent(watchdir_file)
            elif watchdir_file.endswith('.magnet'):
                with open(watchdir_file) as f:
                    magnet = f.read()
                    if not magnet:
                        logger.error('Magnet file empty? for: %s', watchdir_file)
                        return
                    else:
                        try:
                            hash = re.search('btih:(.+?)&', magnet).group(1)
                            name = re.search('&dn=(.+?)&', magnet).group(1)
                        except AttributeError:
                            logger.error('Extracting hash / name from .magnet failed for: %s', watchdir_file)
                            return
                        add_task(hash, 0, name, category)
                        failed = upload_magnet(magnet)
            elif watchdir_file.endswith('.nzb'):
                hash = hash_file(watchdir_file)
                name = os.path.basename(watchdir_file)
                add_task(hash, 0, name, category)
                failed = upload_nzb(watchdir_file)

            if not failed:
                logger.debug('Deleting torrent from watchdir: %s', watchdir_file)
                os.remove(watchdir_file)

    def on_created(self, event):
        self.process(event)

def hash_file(filename):
   """"This function returns the SHA-1 hash
   of the file passed into it"""

   # make a hash object
   h = hashlib.sha1()

   # open file for reading in binary mode
   with open(filename,'rb') as file:

       # loop till the end of the file
       chunk = 0
       while chunk != b'':
           # read only 1024 bytes at a time
           chunk = file.read(1024)
           h.update(chunk)

   # return the hex representation of digest
   return h.hexdigest()

def torrent_metainfo(torrent):
    logger.debug('def torrent_metainfo started')
    metainfo = bencode.bdecode(open(torrent, 'rb').read())
    info = metainfo['info']
    name = info['name']
    hash = hashlib.sha1(bencode.bencode(info)).hexdigest()
    return hash, name


def load_tasks():
    logger.debug('def load_tasks started')
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
        logger.info('Initializing watchdog complete')
        for dirpath, dirs, files in os.walk(cfg.watchdir_location):
            for filename in files:
                fname = os.path.join(dirpath, filename)
                if fname.endswith('.torrent'):
                    fname2 = fname.replace('.torrent', '2.torrent')
                    shutil.copy(fname, fname2)
                    os.remove(fname)
                elif fname.endswith('.magnet'):
                    fname2 = fname.replace('.magnet', '2.magnet')
                    shutil.copy(fname, fname2)
                    os.remove(fname)
                elif fname.endswith('.nzb'):
                    fname2 = fname.replace('.nzb', '2.nzb')
                    shutil.copy(fname, fname2)
                    os.remove(fname)
    except:
        raise


# Flask
@app.route('/')
@login_required
def home():
    return render_template('index.html', debug_enabled=debug_enabled, update_available=cfg.update_available)


@app.route('/upload', methods=["POST"])
@login_required
def upload():
    if request.files:
        torrent_file = request.files['file']
        filename = secure_filename(torrent_file.filename)
        if not os.path.isdir(runningdir + 'tmp'):
            os.makedirs(runningdir + 'tmp')
        torrent_file.save(os.path.join(runningdir + 'tmp', filename))
        torrent = runningdir + 'tmp' + '/' + filename
        failed = upload_torrent(torrent)
        if not failed:
            hash, name = torrent_metainfo(torrent)
            add_task(hash, 0, name, '')
            os.remove(torrent)
    elif request.data:
        upload_magnet(request.data)
        scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=3)
    return 'OK'


@app.route('/history')
@login_required
def history():
    taskad = ""
    taskdel = ""
    taskdl = ""
    try:
        with open(runningdir + 'premiumizer.log', 'r') as f:
            for line in f:
                if 'Added:' in line:
                    taskad += line
                if 'Deleted:' in line:
                    taskdel += line
                if 'Download finished:' in line:
                    taskdl += line
    except:
        taskad = 'History is based on premiumizer.log file, error opening or it does not exist.'
    return render_template("history.html", taskad=taskad, taskdel=taskdel, taskdl=taskdl)


@app.route('/settings', methods=["POST", "GET"])
@login_required
def settings():
    if request.method == 'POST':
        if 'Restart' in request.form.values():
            gevent.spawn_later(1, restart)
            return 'Restarting, please try and refresh the page in a few seconds...'
        elif 'Shutdown' in request.form.values():
            gevent.spawn_later(1, shutdown)
            return 'Shutting down...'
        elif 'Update' in request.form.values():
            gevent.spawn_later(1, update_self)
            return 'Updating, please try and refresh the page in a few seconds...'
        else:
            global prem_config
            enable_watchdir = 0
            if request.form.get('debug_enabled'):
                prem_config.set('global', 'debug_enabled', '1')
            else:
                prem_config.set('global', 'debug_enabled', '0')
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
            if request.form.get('jd_enabled'):
                prem_config.set('downloads', 'jd_enabled', '1')
            else:
                prem_config.set('downloads', 'jd_enabled', '0')
            if request.form.get('watchdir_enabled'):
                prem_config.set('upload', 'watchdir_enabled', '1')
                if not cfg.watchdir_enabled:
                    enable_watchdir = 1
            else:
                prem_config.set('upload', 'watchdir_enabled', '0')

            if request.form.get('email_enabled'):
                prem_config.set('notifications', 'email_enabled', '1')
            else:
                prem_config.set('notifications', 'email_enabled', '0')
            if request.form.get('email_on_failure'):
                prem_config.set('notifications', 'email_on_failure', '1')
            else:
                prem_config.set('notifications', 'email_on_failure', '0')
            if request.form.get('email_encryption'):
                prem_config.set('notifications', 'email_encryption', '1')
            else:
                prem_config.set('notifications', 'email_encryption', '0')
            if request.form.get('auto_update'):
                prem_config.set('update', 'auto_update', '1')
            else:
                prem_config.set('update', 'auto_update', '0')

            prem_config.set('downloads', 'jd_username', request.form.get('jd_username'))
            prem_config.set('downloads', 'jd_password', request.form.get('jd_password'))
            prem_config.set('downloads', 'jd_device', request.form.get('jd_device'))
            prem_config.set('notifications', 'email_from', request.form.get('email_from'))
            prem_config.set('notifications', 'email_to', request.form.get('email_to'))
            prem_config.set('notifications', 'email_server', request.form.get('email_server'))
            prem_config.set('notifications', 'email_port', request.form.get('email_port'))
            prem_config.set('notifications', 'email_username', request.form.get('email_username'))
            prem_config.set('notifications', 'email_password', request.form.get('email_password'))
            prem_config.set('global', 'server_port', request.form.get('server_port'))
            prem_config.set('global', 'bind_ip', request.form.get('bind_ip'))
            prem_config.set('global', 'idle_interval', request.form.get('idle_interval'))
            prem_config.set('security', 'username', request.form.get('username'))
            prem_config.set('security', 'password', request.form.get('password'))
            prem_config.set('premiumize', 'customer_id', request.form.get('customer_id'))
            prem_config.set('premiumize', 'pin', request.form.get('pin'))
            prem_config.set('downloads', 'download_location', request.form.get('download_location'))
            prem_config.set('downloads', 'download_max', request.form.get('download_max'))
            prem_config.set('upload', 'watchdir_location', request.form.get('watchdir_location'))
            prem_config.set('downloads', 'nzbtomedia_location', request.form.get('nzbtomedia_location'))
            for x in range(1, 6):
                prem_config.set('categories', ('cat_name' + str([x])), request.form.get('cat_name' + str([x])))
                prem_config.set('categories', ('cat_dir' + str([x])), request.form.get('cat_dir' + str([x])))
                prem_config.set('categories', ('cat_ext' + str([x])), request.form.get('cat_ext' + str([x])))
                if request.form.get('cat_delsample' + str([x])):
                    prem_config.set('categories', ('cat_delsample' + str([x])), '1')
                else:
                    prem_config.set('categories', ('cat_delsample' + str([x])), '0')
                if request.form.get('cat_nzbtomedia' + str([x])):
                    prem_config.set('categories', ('cat_nzbtomedia' + str([x])), '1')
                else:
                    prem_config.set('categories', ('cat_nzbtomedia' + str([x])), '0')

            with open(runningdir + 'settings.cfg', 'w') as configfile:  # save
                prem_config.write(configfile)
            logger.info('Settings saved, reloading configuration')
            cfg.check_config()
            if enable_watchdir:
                watchdir()
    check_update(0)
    return render_template('settings.html', settings=prem_config, cfg=cfg)


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


@app.route('/log', methods=["GET", "POST"])
@login_required
def log():
    if request.method == 'POST':
        if 'Clear' in request.form.values():
            try:
                with open(runningdir + 'premiumizer.log', 'w'):
                    pass
            except:
                pass
            try:
                with open(runningdir + 'premiumizerDEBUG.log', 'w'):
                    pass
            except:
                pass
            logger.info('Logfile Cleared')
    try:
        with open(runningdir + 'premiumizer.log', "r") as f:
            log = f.read()
    except:
        log = 'Error opening logfile'

    try:
        with open(runningdir + 'premiumizerDEBUG.log', "r") as f:
            debuglog = f.read()
    except:
        debuglog = 'no debug log file'
    return render_template("log.html", log=log, debuglog=debuglog)


@app.route('/about')
@login_required
def about():
    return render_template("about.html")


@app.route('/list')
@login_required
def list():
    payload = {'customer_id': cfg.prem_customer_id, 'pin': cfg.prem_pin}
    r = prem_connection("get", "https://www.premiumize.me/api/transfer/list", payload)
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
    task = get_task(message['data'])
    if task.local_status != 'stopped':
        task.update(local_status='stopped')
    payload = {'customer_id': cfg.prem_customer_id, 'pin': cfg.prem_pin, 'type': 'torrent', 'id': message['data']}
    r = prem_connection("post", "https://www.premiumize.me/api/transfer/delete", payload)
    if r != 'failed':
        responsedict = json.loads(r.content)
        task = get_task(message['data'])
        if responsedict['status'] == "success":
            logger.info('Deleted: %s from the cloud', task.name)
            emit('delete_success', {'data': message['data']})
            scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=3)
        else:
            msg = 'Unable to delete torrent from cloud for: %s, message: %s' % (task.name, responsedict['message'])
            logger.error(msg)
            if cfg.email_enabled:
                email(msg)
            emit('delete_failed', {'data': message['data']})
    else:
        emit('delete_failed')


# @socketio.on('pause_task')
# def pause_task(message):
#    task = get_task(message['data'])
#    if task.local_status != 'paused':
#        task.update(local_status='paused')
#    elif task.local_status == 'paused':
#        task.update(local_status='downloading')


@socketio.on('stop_task')
def stop_task(message):
    task = get_task(message['data'])
    if task.local_status != 'stopped':
        task.update(local_status='stopped')


@socketio.on('connect')
def test_message():
    global client_connected
    client_connected = 1
    emit('hello_client', {'data': 'Server says hello!'})


@socketio.on('disconnect')
def test_disconnect():
    global client_connected
    client_connected = 0
    print('Client disconnected')


@socketio.on('hello_server')
def hello_server(message):
    send_categories()
    scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=1)
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
    dldir, dlext, delsample, dlnzbtomedia = get_cat_var(data['category'])
    task.update(local_status=None, process=None, speed=None, category=data['category'], dldir=dldir, dlext=dlext,
                delsample=delsample,
                dlnzbtomedia=dlnzbtomedia)
    scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=3)


# Start watchdog if watchdir is enabled
if cfg.watchdir_enabled:
    watchdir()

# start the server with the 'run()' method
logger.info('Starting server on %s:%s ', prem_config.get('global', 'bind_ip'),
            prem_config.getint('global', 'server_port'))
if __name__ == '__main__':
    try:
        load_tasks()
        scheduler = APScheduler(GeventScheduler())
        scheduler.init_app(app)
        scheduler.scheduler.add_jobstore('memory', alias='downloads')
        scheduler.scheduler.add_executor('threadpool', alias='downloads', max_workers=cfg.download_max)
        scheduler.start()
        scheduler.scheduler.add_job(update, 'interval', id='update',
                                    seconds=active_interval, replace_existing=True, max_instances=1, coalesce=True)
        scheduler.scheduler.add_job(check_update, 'interval', id='check_update',
                                    seconds=1, replace_existing=True, max_instances=1, coalesce=True)

        socketio.run(app, host=prem_config.get('global', 'bind_ip'), port=prem_config.getint('global', 'server_port'),
                     use_reloader=False)
    except:
        raise
