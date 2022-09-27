#! /usr/bin/env python
import configparser
import json
import logging
import os
import re
import shelve
import shutil
import signal
import smtplib
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xmlrpc.client
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from logging.handlers import RotatingFileHandler
from string import ascii_letters, digits

import apprise
import bencode
import gevent
import myjdapi
import requests
import six
from apscheduler.schedulers.gevent import GeventScheduler
from chardet import detect
from flask import (Flask, flash, redirect, render_template, request,
                   send_from_directory, url_for)
from flask_apscheduler import APScheduler
from flask_compress import Compress
from flask_login import (LoginManager, UserMixin, login_required, login_user,
                         logout_user)
from flask_socketio import SocketIO, emit
from gevent import local
from pySmartDL import SmartDL, utils
from watchdog import events
from watchdog.observers import Observer
from werkzeug.utils import secure_filename

import DownloadTask
from DownloadTask import DownloadTask

print('------------------------------------------------------------------------------------------------------------')
print('|                                                                                                           |')
print('-------------------------------------------WELCOME TO PREMIUMIZER-------------------------------------------')
print('|                                                                                                           |')
print('------------------------------------------------------------------------------------------------------------')
# Initialize config values
prem_config = configparser.ConfigParser()
runningdir = os.path.split(os.path.abspath(os.path.realpath(sys.argv[0])))[0]
rootdir = os.path.dirname(runningdir)
ConfDir = os.path.join(rootdir, 'conf')
LogsDir = os.path.join(ConfDir, 'logs')

print('Runtime at ', runningdir)
print('Root at ', rootdir)
print('Conf at ', ConfDir)
print('Logs at ', LogsDir)

os_arg = ''

if len(sys.argv) > 1:
    os_arg = sys.argv[1]
else:
    try:
        with open('/proc/1/cgroup', 'rt') as ifh:
            if 'docker' in ifh.read():
                os_arg = '--docker'
    except:
        pass

if not os.path.isdir(ConfDir):
    os.makedirs(ConfDir)
if not os.path.isfile(os.path.join(ConfDir, 'settings.cfg')):
    shutil.copy(os.path.join(runningdir, 'settings.cfg.tpl'), os.path.join(ConfDir, 'settings.cfg'))
try:
    prem_config.read(os.path.join(ConfDir, 'settings.cfg'), encoding='utf-8')
except Exception as e:
    print(str(e))
active_interval = prem_config.getint('global', 'active_interval')
idle_interval = prem_config.getint('global', 'idle_interval')
debug_enabled = prem_config.getboolean('global', 'debug_enabled')

# Initialize logging
if not os.path.isdir(LogsDir):
    os.makedirs(LogsDir)
syslog = logging.StreamHandler()
if debug_enabled:
    logger = logging.getLogger('')
    logger.setLevel(logging.DEBUG)
    formatterdebug = logging.Formatter('%(asctime)-20s %(name)-41s: %(levelname)-8s : %(message)s',
                                       datefmt='%m-%d %H:%M:%S')
    syslog.setFormatter(formatterdebug)
    logger.addHandler(syslog)
    print('---------------------------------------------------------------------------------------------------------')
    print('|                                                                                                        |')
    print('------------------------PREMIUMIZER IS RUNNING IN DEBUG MODE, THIS IS NOT RECOMMENDED--------------------')
    print('|                                                                                                        |')
    print('---------------------------------------------------------------------------------------------------------')
    logger.debug('----------------------------------')
    logger.debug('----------------------------------')
    logger.debug('----------------------------------')
    logger.debug('DEBUG Logger Initialized')
    handler = logging.handlers.RotatingFileHandler(os.path.join(LogsDir, 'premiumizerDEBUG.log'), maxBytes=(500 * 1024))
    handler.setFormatter(formatterdebug)
    logger.addHandler(handler)
    logger.debug('DEBUG Logfile Initialized')
else:
    logger = logging.getLogger("Rotating log")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)-s: %(levelname)-s : %(message)s', datefmt='%m-%d %H:%M:%S')
    syslog.setFormatter(formatter)
    logger.addHandler(syslog)
    logging.getLogger('apscheduler.executors').addHandler(logging.NullHandler())
    logger.debug('-------------------------------------------------------------------------------------')
    logger.debug('-------------------------------------------------------------------------------------')
    logger.debug('-------------------------------------------------------------------------------------')
    logger.debug('Logger Initialized')
    handler = logging.handlers.RotatingFileHandler(os.path.join(LogsDir, 'premiumizer.log'), maxBytes=(500 * 1024))
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.debug('Logfile Initialized')


# Catch uncaught exceptions in log
def uncaught_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, (SystemExit, KeyboardInterrupt)):
        return
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    pass


sys.excepthook = uncaught_exception


def terminateProcess(signalNumber, frame):
    logger.warning('My PID is: %s', os.getpid())
    logger.warning('Received Signal: %s', signalNumber)
    shutdown()


# Logging filters for debugging, default is 1
log_apscheduler = 1
log_flask = 1


class ReverseProxy(object):
    '''Wrap the application in this middleware and configure the
    front-end server to add these headers, to let you quietly bind
    this to a URL other than / and to an HTTP scheme that is
    different than what is used locally.

    In nginx:
    location /myprefix {
        proxy_pass       http://localhost:5000;
        proxy_set_header Host              $http_host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Script-Name /myprefix; or trough premiumizer settings
        }

    :param app: the WSGI application
    '''

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if not script_name:
            script_name = cfg.reverse_proxy_path
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info and path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        scheme = environ.get('HTTP_X_FORWARDED_PROTO', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)


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
    if os.path.isfile(os.path.join(LogsDir, 'premiumizer.log')):
        try:
            with open(os.path.join(LogsDir, 'premiumizer.log'), 'w'):
                pass
            logger.info('*************************************************************************************')
            logger.info('----------------Premiumizer.log file has been deleted as a precaution----------------')
            logger.info('*************************************************************************************')
        except:
            logger.error('Could not delete old premiumizer.log file')
    if os.path.isfile(os.path.join(LogsDir, 'premiumizerDEBUG.log')):
        try:
            with open(os.path.join(LogsDir, 'premiumizerDEBUG.log'), 'w'):
                pass
            logger.info('*************************************************************************************')
            logger.info('---------------PremiumizerDEBUG file has been deleted as a precaution----------------')
            logger.info('*************************************************************************************')
        except:
            logger.error('Could not delete old premiumizerDEBUG.log file')
    if os.path.isfile(os.path.join(ConfDir, 'database.db')) or os.path.isfile(os.path.join(ConfDir, 'database.db.dat')):
        success = 0
        try:
            os.remove(os.path.join(ConfDir, 'database.db'))
            success = 1
        except:
            try:
                os.remove(os.path.join(ConfDir, 'database.db.dat'))
                success = 1
            except:
                pass
            try:
                os.remove(os.path.join(ConfDir, 'database.db.bak'))
            except:
                pass
            try:
                os.remove(os.path.join(ConfDir, 'database.db.dir'))
            except:
                pass
        if success:
            logger.info('*************************************************************************************')
            logger.info('---------------Database file has been deleted as a precaution----------------')
            logger.info('*************************************************************************************')
    if os.path.isfile(os.path.join(rootdir, 'conf', 'settings.cfg.old')):
        logger.info('*************************************************************************************')
        logger.info('-------Settings file has been updated, old settings file renamed to .old-------')
        logger.info('*************************************************************************************')
    prem_config.set('update', 'updated', '0')
    with open(os.path.join(rootdir, 'conf', 'settings.cfg'), 'w') as configfile:
        prem_config.write(configfile)
    logger.info('*************************************************************************************')
    logger.info('---------------------------Premiumizer has been updated!!----------------------------')
    logger.info('*************************************************************************************')


# noinspection PyAttributeOutsideInit
class PremConfig:
    def __init__(self):
        self.jd_update_available = 0
        self.downloader_connection = 0
        self.jd_connected = 0
        self.aria2_connected = 0
        self.download_builtin = 0
        self.check_config()

    def check_config(self):
        logger.debug('Initializing config')
        default_config = configparser.ConfigParser()
        default_config.read(os.path.join(runningdir, 'settings.cfg.tpl'))
        if prem_config.getfloat('update', 'req_version') < default_config.getfloat('update', 'req_version'):
            try:
                logging.info('updating pip requirements')
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'])
                subprocess.check_call(
                    [sys.executable, '-m', 'pip', 'install', '-r', os.path.join(rootdir, 'requirements.txt')])
                prem_config.set('update', 'req_version', str(default_config.getfloat('update', 'req_version')))
                with open(os.path.join(ConfDir, 'settings.cfg'), 'w') as configfile:
                    prem_config.write(configfile)
                prem_config.read(os.path.join(ConfDir, 'settings.cfg'))
            except:
                logger.error('Could not update requirements')
                pass
        if prem_config.getfloat('update', 'config_version') < default_config.getfloat('update', 'config_version'):
            logging.info('updating config file')
            try:
                shutil.copy(os.path.join(ConfDir, 'settings.cfg'),
                            os.path.join(ConfDir, 'settings.cfg.old'))
                shutil.copy(os.path.join(runningdir, 'settings.cfg.tpl'),
                            os.path.join(ConfDir, 'settings.cfg'))
                prem_config.read(os.path.join(ConfDir, 'settings.cfg.old'))
                default_config.read(os.path.join(ConfDir, 'settings.cfg'))
                for section in prem_config.sections():
                    if section in default_config.sections() and section != 'update':
                        for key in prem_config.options(section):
                            value = prem_config.get(section, key)
                            if key in default_config.options(section) and value:
                                default_config.set(section, key, value)
                with open(os.path.join(ConfDir, 'settings.cfg'), 'w') as configfile:
                    default_config.write(configfile)
                prem_config.read(os.path.join(ConfDir, 'settings.cfg'))
            except:
                logger.error('Could not update settings file')
                pass
        self.jd_connected = 0
        self.aria2_connected = 0
        self.bind_ip = prem_config.get('global', 'bind_ip')
        self.reverse_proxy_path = prem_config.get('global', 'reverse_proxy_path')
        self.custom_domain = prem_config.get('global', 'custom_domain')
        self.web_login_enabled = prem_config.getboolean('security', 'login_enabled')
        self.web_username = prem_config.get('security', 'username')
        self.web_password = prem_config.get('security', 'password')
        self.update_available = 0
        self.update_localcommit = ''
        self.update_diffcommit = ''
        if os_arg == '--docker':
            self.update_status = 'UI updates are not supported in docker'
        else:
            self.update_status = ''
        self.update_date = prem_config.get('update', 'update_date')
        self.auto_update = prem_config.getboolean('update', 'auto_update')
        self.prem_apikey = prem_config.get('premiumize', 'apikey')
        self.remove_cloud = prem_config.getboolean('downloads', 'remove_cloud')
        self.remove_cloud_delay = prem_config.getint('downloads', 'remove_cloud_delay')
        self.seed_torrent = prem_config.getboolean('downloads', 'seed_torrent')
        self.download_all = prem_config.getboolean('downloads', 'download_all')
        self.download_enabled = prem_config.getboolean('downloads', 'download_enabled')
        self.time_shed = prem_config.getboolean('downloads', 'time_shed')
        self.time_shed_start = prem_config.get('downloads', 'time_shed_start')
        self.time_shed_stop = prem_config.get('downloads', 'time_shed_stop')
        self.download_location = prem_config.get('downloads', 'download_location')
        self.download_max = prem_config.getint('downloads', 'download_max')
        self.download_threads = prem_config.getint('downloads', 'download_threads')
        self.download_speed = prem_config.get('downloads', 'download_speed')
        self.download_rss = prem_config.getboolean('downloads', 'download_rss')
        self.jd_enabled = prem_config.getboolean('downloads', 'jd_enabled')
        self.aria2_enabled = prem_config.getboolean('downloads', 'aria2_enabled')
        if self.download_location == '' and self.download_enabled:
            self.download_enabled = 0
            logger.error('Downloads disabled because download location is empty')
        if self.download_speed == '0' and self.download_enabled:
            self.download_enabled = 0
            logger.error('Downloads disabled because download speed is 0')
        elif self.download_speed == '-1':
            self.download_speed = int(self.download_speed)
        else:
            self.download_speed = float(self.download_speed)
            self.download_speed = int(self.download_speed * 1048576)
        if self.jd_enabled:
            self.jd_username = prem_config.get('downloads', 'jd_username')
            self.jd_password = prem_config.get('downloads', 'jd_password')
            self.jd_device_name = prem_config.get('downloads', 'jd_device_name')
            try:
                self.jd = myjdapi.Myjdapi()
                self.jd.set_app_key('https://git.io/vaDti')
                self.jd.connect(self.jd_username, self.jd_password)
            except BaseException as e:
                logger.error('myjdapi : ' + str(e))
                logger.error('Could not connect to My JDownloader')
            try:
                self.jd_device = self.jd.get_device(self.jd_device_name)
                self.jd_connected = 1
                self.download_builtin = 0
                self.aria2_enabled = 0
            except BaseException as e:
                logger.error('myjdapi : ' + str(e))
                logger.error('Could not get device name (%s) for My JDownloader', self.jd_device_name)
                self.jd_connected = 0
            if self.jd_connected:
                try:
                    if self.download_speed == -1:
                        self.jd_device.toolbar.disable_downloadSpeedLimit()
                    else:
                        self.jd_device.toolbar.enable_downloadSpeedLimit()
                        self.download_speed = self.jd_device.toolbar.get_status().get('limitspeed')
                except:
                    logger.error('Could not enable JDownloader speed limit')

        elif self.aria2_enabled:
            self.aria2_host = prem_config.get('downloads', 'aria2_host')
            self.aria2_port = prem_config.get('downloads', 'aria2_port')
            self.aria2_token = "token:" + prem_config.get('downloads', 'aria2_secret')
            try:
                uri = ('http://' + self.aria2_host + ':' + self.aria2_port + '/rpc')
                self.aria = xmlrpc.client.ServerProxy(uri, allow_none=True)
                if self.download_speed == -1:
                    download_speed = 0
                else:
                    download_speed = str(self.download_speed // 1048576) + 'M'
                self.aria.aria2.changeGlobalOption(self.aria2_token, {'max-overall-download-limit': download_speed})
                self.aria2_connected = 1
                self.jd_enabled = 0
                self.download_builtin = 0
            except Exception as e:
                logger.error('Could not connect to aria2 RPC: %s --- message: %s', uri, e)
                self.aria2_connected = 0

        else:
            self.download_builtin = 1
        if os.path.isfile(os.path.join(rootdir, 'nzbtomedia', 'NzbToMedia.py')):
            self.nzbtomedia_location = (os.path.join(rootdir, 'nzbtomedia', 'NzbToMedia.py'))
            prem_config.set('downloads', 'nzbtomedia_location', self.nzbtomedia_location)
            with open(os.path.join(ConfDir, 'settings.cfg'), 'w') as configfile:
                prem_config.write(configfile)
        else:
            self.nzbtomedia_location = prem_config.get('downloads', 'nzbtomedia_location')
        self.watchdir_enabled = prem_config.getboolean('upload', 'watchdir_enabled')
        self.watchdir_location = prem_config.get('upload', 'watchdir_location')
        if self.watchdir_enabled:
            if not self.watchdir_location:
                logger.info('Watchdir location is empty, disabling watchdir')
                self.watchdir_enabled = 0
            else:
                self.watchdir_walk_enabled = prem_config.getboolean('upload', 'watchdir_walk_enabled')
                self.watchdir_walk_interval = prem_config.getint('upload', 'watchdir_walk_interval')
                if not os.path.exists(self.watchdir_location):
                    os.makedirs(self.watchdir_location)
                logger.info('Watchdir is enabled at: %s', self.watchdir_location)

        self.categories = []
        self.download_categories = ''
        try:
            for x in range(1, 99):
                cat_name = prem_config.get('categories', ('cat_name' + str([x])))
                cat_dir = prem_config.get('categories', ('cat_dir' + str([x])))
                if cat_name != '':
                    if cat_dir == '' or ('/' not in cat_dir and '\\' not in cat_dir):
                        if cat_name == 'default':
                            cat_dir = self.download_location
                        else:
                            cat_dir = os.path.join(self.download_location, cat_name)
                        prem_config.set('categories', ('cat_dir' + str([x])), cat_dir)
                        with open(os.path.join(ConfDir, 'settings.cfg'), 'w') as configfile:
                            prem_config.write(configfile)
                    cat_ext = prem_config.get('categories', ('cat_ext' + str([x]))).split(',')
                    cat_ext_blacklist = prem_config.getboolean('categories', ('cat_ext_blacklist' + str([x])))
                    cat_delsample = prem_config.getboolean('categories', ('cat_delsample' + str([x])))
                    cat_nzbtomedia = prem_config.getboolean('categories', ('cat_nzbtomedia' + str([x])))
                    cat = {'name': cat_name, 'dir': cat_dir, 'ext': cat_ext, 'ext_blacklist': cat_ext_blacklist,
                           'delsample': cat_delsample, 'nzb': cat_nzbtomedia}
                    self.categories.append(cat)
                    self.download_categories += str(cat_name + ',')
                    if self.download_enabled:
                        if not os.path.exists(cat_dir):
                            logger.info('Creating Download Path at: %s', cat_dir)
                            try:
                                os.makedirs(cat_dir)
                            except Exception as e:
                                logger.error('Downloads disabled cannot Create download directory: %s --- error: %s',
                                             cat_dir, e)
                                self.download_enabled = 0
                    if self.watchdir_enabled:
                        sub = os.path.join(self.watchdir_location, cat_name)
                        if not os.path.exists(sub):
                            logger.info('Creating watchdir Path at %s', sub)
                            try:
                                os.makedirs(sub)
                            except Exception as e:
                                logger.error('Cannot Create watchdir directory: %s --- error: %s', cat_dir, e)
                                self.watchdir_enabled = 0
        except:
            pass
        try:
            self.download_categories = self.download_categories[:-1]
            self.download_categories = self.download_categories.split(',')
        except Exception as e:
            self.download_categories = ''
            logger.error('Cannot set download_categories error: %s', e)

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

        self.apprise_enabled = prem_config.getboolean('notifications', 'apprise_enabled')
        if self.apprise_enabled:
            self.apprise_push_on_failure = prem_config.getboolean('notifications', 'apprise_push_on_failure')
            self.apprise_url = prem_config.get('notifications', 'apprise_url')

        logger.debug('Initializing config complete')


cfg = PremConfig()


def downloader_connection():
    connection = 0
    if cfg.jd_enabled:
        cfg.jd_connected = 0
        try:
            cfg.jd = myjdapi.Myjdapi()
            cfg.jd.set_app_key('https://git.io/vaDti')
            cfg.jd.connect(cfg.jd_username, cfg.jd_password)
            cfg.jd_connected = 1
        except BaseException as e:
            logger.error('myjdapi : ' + str(e))
            logger.error('Could not connect to My JDownloader')
        if cfg.jd_connected:
            try:
                cfg.jd_device = cfg.jd.get_device(cfg.jd_device_name)
                connection = 1
            except BaseException as e:
                cfg.jd_connected = 0
                logger.error('myjdapi : ' + str(e))
                logger.error('Could not get device name (%s) for My JDownloader', cfg.jd_device_name)
    elif cfg.aria2_enabled:
        cfg.aria2_connected = 0
        try:
            uri = ('http://' + cfg.aria2_host + ':' + cfg.aria2_port + '/rpc')
            cfg.aria = xmlrpc.client.ServerProxy(uri, allow_none=True)
            cfg.aria.aria2.getVersion(cfg.aria2_token)
            cfg.aria2_connected = 1
            connection = 1
        except Exception as e:
            logger.error('Could not connect to aria2 RPC: %s --- message: %s', uri, e)
            try:
                greenlet.task.update(eta=' Could not connect to aria2 RPC')
            except:
                pass
            connection = 0
    else:
        # pySmartDL
        connection = 1
    cfg.downloader_connection = connection
    return connection


# Automatic update checker
def check_update(auto_update=cfg.auto_update):
    logger.debug('def check_update started')
    time_job = scheduler.scheduler.get_job('check_update').next_run_time.replace(tzinfo=None)
    time_now = datetime.now()
    diff = time_job - time_now
    diff = 21600 - diff.total_seconds()
    if (diff > 120) or (cfg.update_status == ''):
        try:
            subprocess.check_call(['git', '-C', rootdir, 'fetch'])
        except:
            cfg.update_status = 'failed'
            logger.error('Update failed: could not git fetch: %s', rootdir)
        if cfg.update_status != 'failed':
            cfg.update_localcommit = subprocess.check_output(
                ['git', '-C', rootdir, 'log', '-n', '1', '--pretty=format:%h'], encoding='utf8').rstrip('\n')
            local_branch = subprocess.check_output(['git', '-C', rootdir, 'rev-parse', '--abbrev-ref', 'HEAD'],
                                                   encoding='utf8').rstrip('\n')
            remote_commit = subprocess.check_output(
                ['git', '-C', rootdir, 'log', '-n', '1', 'origin/' + local_branch, '--pretty=format:%h'],
                encoding='utf8').rstrip('\n')

            if cfg.update_localcommit != remote_commit:
                cfg.update_diffcommit = subprocess.check_output(
                    ['git', '-C', rootdir, 'log', '--oneline', local_branch + '..origin/' + local_branch],
                    encoding='utf8').rstrip('\n')

                cfg.update_available = 1
                cfg.update_status = 'Update Available !!'
                if auto_update:
                    for task in tasks:
                        if task.local_status == (
                                'downloading' or 'queued' or 'failed: download' or 'failed: nzbToMedia'):
                            scheduler.scheduler.reschedule_job('check_update', trigger='interval', minutes=30)
                            logger.info(
                                'Tried to update but downloads are not done or failed, trying again in 30 minutes')
                            cfg.update_status = \
                                'Update available, but not yet installed because downloads are not done or failed'
                            return
                    update_self()
            else:
                cfg.update_status = 'No update available --- last time checked: ' + datetime.now().strftime(
                    "%d-%m %H:%M:%S") + ' --- last time updated: ' + cfg.update_date
        if cfg.jd_enabled:
            try:
                cfg.jd_update_available = cfg.jd_device.update.update_available()
            except:
                downloader_connection()
                try:
                    cfg.jd_update_available = cfg.jd_device.update.update_available()
                except:
                    logger.error('JDownloader update check failed')
    scheduler.scheduler.reschedule_job('check_update', trigger='interval', hours=6)


# noinspection PyProtectedMember
def update_self():
    logger.debug('def update_self started')
    logger.info('Update - will restart')
    cfg.update_date = datetime.now().strftime("%d-%m %H:%M:%S")
    prem_config.set('update', 'update_date', cfg.update_date)
    with open(os.path.join(ConfDir, 'settings.cfg'), 'w') as configfile:
        prem_config.write(configfile)
    db.close()
    socketio.stop()
    if os_arg == '--windows':
        subprocess.call(['python', os.path.join(runningdir, 'utils.py'), '--update', '--windows'])
        os._exit(1)
    else:
        subprocess.Popen(['python', os.path.join(runningdir, 'utils.py'), '--update', '--none'],
                         shell=False,
                         close_fds=True)
        os._exit(1)


# noinspection PyProtectedMember
def restart():
    logger.info('Restarting')
    db.close()
    socketio.stop()
    if os_arg == '--windows':
        # windows service will automatically restart on 'failure'
        os._exit(1)
    else:
        subprocess.Popen(['python', os.path.join(runningdir, 'utils.py'), '--restart', '--none'],
                         shell=False,
                         close_fds=True)
        os._exit(1)


# noinspection PyProtectedMember
def shutdown():
    logger.info('Shutdown recieved')
    db.close()
    socketio.stop()
    if os_arg == '--windows':
        subprocess.call([os.path.join(os.path.dirname(rootdir), 'Installer', 'nssm.exe'), 'stop', 'Premiumizer'])
    else:
        os._exit(1)


#
logger.debug('Initializing Flask')
app = Flask(__name__)
app.wsgi_app = ReverseProxy(app.wsgi_app)
Compress(app)
app.config['SECRET_KEY'] = uuid.uuid4().hex
app.config.update(DEBUG=debug_enabled)
app.logger.addHandler(handler)
if cfg.custom_domain:
    cors = ['http://' + cfg.custom_domain, 'https://' + cfg.custom_domain,
            'http://localhost:' + str(prem_config.getint('global', 'server_port')),
            'http://127.0.0.1:' + str(prem_config.getint('global', 'server_port'))]
else:
    cors = '*'
socketio = SocketIO(app, async_mode='gevent', cors_allowed_origins=cors, path=cfg.reverse_proxy_path + '/socket.io')

app.config['LOGIN_DISABLED'] = not cfg.web_login_enabled
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
logger.debug('Initializing Flask complete')

# Initialise Database
logger.debug('Initializing Database')
if os.path.isfile(os.path.join(ConfDir, 'database.db')) or os.path.isfile(os.path.join(ConfDir, 'database.db.dat')):
    db = shelve.open(os.path.join(ConfDir, 'database.db'))
    if not db.keys():
        db.close()
        try:
            os.remove(os.path.join(ConfDir, 'database.db'))
        except:
            try:
                os.remove(os.path.join(ConfDir, 'database.db.dat'))
            except:
                pass
            try:
                os.remove(os.path.join(ConfDir, 'database.db.bak'))
            except:
                pass
            try:
                os.remove(os.path.join(ConfDir, 'database.db.dir'))
            except:
                pass
        db = shelve.open(os.path.join(ConfDir, 'database.db'))
        logger.debug('Database cleared')
else:
    db = shelve.open(os.path.join(ConfDir, 'database.db'))
logger.debug('Initializing Database complete')


class MyHandler(events.PatternMatchingEventHandler):
    patterns = ["*.torrent", "*.magnet", "*.nzb"]

    # noinspection PyMethodMayBeStatic
    def process(self, event):
        if cfg.watchdir_walk_enabled:
            scheduler.scheduler.get_job('walk_watchdir').pause()
        failed = 0
        name2 = ''
        if event.event_type == 'created' and event.is_directory is False:
            gevent.sleep(10)
            watchdir_file = event.src_path
            if not os.path.isfile(watchdir_file):
                logger.error(
                    'watchdir file %s no longer exists', watchdir_file)
                return
            logger.info('New watchdir file detected: %s', watchdir_file)
            dirname = os.path.basename(
                os.path.normpath(os.path.dirname(watchdir_file)))
            if dirname in cfg.download_categories:
                category = dirname
            else:
                category = ''
            if watchdir_file.endswith('.torrent'):
                id, name2 = upload_torrent(watchdir_file)
                if id == 'duplicate':
                    failed = 1
                    logger.debug(
                        'Deleting duplicate file from watchdir: %s', watchdir_file)
                    try:
                        gevent.sleep(3)
                        os.remove(watchdir_file)
                    except Exception as err:
                        logger.error('Could not remove duplicate file from watchdir: %s --- error: %s', watchdir_file,
                                     err)
                elif id == 'failed':
                    failed = 1
                else:
                    name = torrent_metainfo(watchdir_file)
                    if name2:
                        name = name2
                    type = 'Torrent'
                    task = add_task(id, 0, name, category, type=type)
            elif watchdir_file.endswith('.magnet'):
                with open(watchdir_file) as f:
                    magnet = f.read()
                    if not magnet:
                        logger.error('Magnet file empty? for: %s', watchdir_file)
                        return
                    else:
                        try:
                            name = re.search('&dn=(.+?)(&|.torrent)', magnet).group(1)
                        except AttributeError:
                            name = os.path.basename(watchdir_file).replace(".magnet", "")
                        name = name.replace('+', '%20')
                        id, name2 = upload_magnet(magnet)
                        if name2:
                            name = name2
                        if id == 'duplicate':
                            failed = 1
                            logger.debug('Deleting duplicate file from watchdir: %s', watchdir_file)
                            try:
                                f.close()
                                gevent.sleep(3)
                                os.remove(watchdir_file)
                            except Exception as err:
                                logger.error('Could not remove duplicate file from watchdir: %s --- error: %s',
                                             watchdir_file, err)
                        elif id == 'failed':
                            failed = 1
                        else:
                            type = 'Torrent'
                            task = add_task(id, 0, name, category, type=type)

            elif watchdir_file.endswith('.nzb'):
                id, name2 = upload_nzb(watchdir_file)
                if id == 'duplicate':
                    failed = 1
                    logger.debug(
                        'Deleting duplicate file from watchdir: %s', watchdir_file)
                    try:
                        gevent.sleep(3)
                        os.remove(watchdir_file)
                    except Exception as err:
                        logger.error('Could not remove duplicate file from watchdir: %s --- error: %s', watchdir_file,
                                     err)
                elif id == 'failed':
                    failed = 1
                else:
                    name = os.path.basename(watchdir_file)
                    name = os.path.splitext(name)[0]
                    if name2:
                        name = name2
                    type = 'NZB'
                    task = add_task(id, 0, name, category, type=type)
            else:
                logger.error('Watchdir file: %s --- is not a torrent/magnet/nzb', watchdir_file)
                failed = 1
            if not failed:
                gevent.sleep(5)
                failed = check_cloud_fail(id)
                if failed:
                    try:
                        if debug_enabled:
                            log = 'premiumizerDEBUG.log'
                        else:
                            log = 'premiumizer.log'
                        with open(os.path.join(LogsDir, log), 'r') as f:
                            for line in f:
                                if 'Retrying cloud upload in 10 minutes for: ' + name in line:
                                    scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=1)
                                    return
                    except:
                        scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=1)
                        return
                    logger.warning('Retrying cloud upload in 10 minutes for: %s', name)
                    scheduler.scheduler.add_job(retry_cloud, args=('watchdir', task), id=id, ame=(name + ' reupload'),
                                                misfire_grace_time=7200, jobstore='reupload', replace_existing=True,
                                                coalesce=True, next_run_time=(datetime.now() + timedelta(minutes=10)))
                else:
                    gevent.sleep(3)
                    logger.debug('Deleting file from watchdir: %s', watchdir_file)
                    try:
                        os.remove(watchdir_file)
                    except Exception as err:
                        logger.error(
                            'Could not remove file from watchdir: %s --- error: %s', watchdir_file, err)
                scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=1)
            if cfg.watchdir_walk_enabled:
                scheduler.scheduler.get_job('walk_watchdir').resume()
    def on_created(self, event):
        self.process(event)


def retry_cloud(method, task):
    delete_task(task)
    if method == 'watchdir':
        walk_watchdir()


def check_cloud_fail(id):
    payload = {'apikey': cfg.prem_apikey}
    r = prem_connection("post", "https://www.premiumize.me/api/transfer/list", payload)
    if 'failed' not in r:
        response_content_transfer = json.loads(r.content)
        if response_content_transfer['status'] == "success":
            transfers = response_content_transfer['transfers']
            for transfer in transfers:
                if transfer['id'] == id:
                    if transfer['status'] == 'error':
                        msg = 'Cloud error for: %s -- message: %s' % (transfer['name'], transfer['message'])
                        logger.error(msg)
                        send_notification('Cloud error', msg)
                        return 1
    return 0


# Initialise Globals
tasks = []
greenlet = local.local()
client_connected = 0
prem_session = requests.Session()
last_email = {'time': datetime.now() - timedelta(days=1), 'subject': ""}
jd_packages = {'time': datetime.now(), 'packages': []}
watchdog_handler = MyHandler()


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
        if isinstance(original, str):
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
        import traceback
        logger.error('Unable to decode value "%s..." : %s ', (repr(original)[:20], traceback.format_exc()))
        return 'ERROR DECODING STRING'


def ek(original, *args):
    logger.debug('def ek started')
    if isinstance(original, str):
        try:
            return original.decode('UTF-8', 'ignore')
        except UnicodeDecodeError:
            raise
    return original


#
def clean_name(original):
    logger.debug('def clean_name started')
    valid_chars = "#$+;=^`~'-_.,()[]{}&!@ %s%s" % (ascii_letters, digits)
    cleaned_filename = unicodedata.normalize('NFKD', to_unicode(original)).encode('ASCII', 'ignore').decode('utf8')
    valid_string = ''.join(c for c in cleaned_filename if c in valid_chars)
    return ' '.join(valid_string.split())


def notify_nzbtomedia():
    logger.debug('def notify_nzbtomedia started')
    if os.path.isfile(cfg.nzbtomedia_location):
        try:
            subprocess.check_output(
                ['python', cfg.nzbtomedia_location, greenlet.task.dldir, greenlet.task.name, greenlet.task.category,
                 greenlet.task.id, 'generic'],
                stderr=subprocess.STDOUT, shell=False, encoding='utf8').rstrip('\n')
            returncode = 0
            logger.info('Send to nzbToMedia: %s -- id: %s', greenlet.task.name, greenlet.task.id)
        except subprocess.CalledProcessError as e:
            logger.error('nzbToMedia failed for: %s -- id: %s', greenlet.task.name, greenlet.task.id)
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


def send_notification(subject, text=None, send_email=cfg.email_enabled, send_push=cfg.apprise_enabled):
    logger.debug('def send_notification started')
    if not (cfg.email_enabled or cfg.apprise_enabled):
        return
    global last_email
    if subject == 'download success':
        subject = 'Success for "%s"' % greenlet.task.name
        text = 'Download of %s: "%s" has successfully completed.' % (greenlet.task.type, greenlet.task.name)
        text += '\nStatus: SUCCESS'
        text += '\n\nStatistics:'
        text += '\nDownloaded size: %s' % utils.sizeof_human(greenlet.task.size)
        text += '\nDownload time: %s' % utils.time_human(greenlet.task.dltime, fmt_short=True)
        text += '\nDownload speed: %s' % greenlet.avgspeed
        text += '\n\nFiles:'
        for download in greenlet.task.download_list:
            text += '\n' + os.path.basename(download['combined_path'])
        text += '\n\nLocation:'
        text += '\n' + greenlet.task.dldir

    elif subject == 'download failed':
        subject = 'Failure for "%s"' % greenlet.task.name
        text = 'Download of %s: "%s" has failed.' % (greenlet.task.type, greenlet.task.name)
        text += '\nStatus: FAILED\nError: %s' % greenlet.task.local_status
        text += '\n\nLog:\n'
        try:
            if debug_enabled:
                log = 'premiumizerDEBUG.log'
            else:
                log = 'premiumizer.log'
            with open(os.path.join(LogsDir, log), 'r') as f:
                for line in f:
                    if greenlet.task.name in line:
                        text += line
        except:
            text += 'could not add log'

    else:
        if text is None:
            text = subject

    if datetime.now() - timedelta(hours=1) < last_email['time'] and subject == last_email['subject']:
        return
    last_email['time'] = datetime.now()
    last_email['subject'] = subject

    if send_email:
        # Create message
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = cfg.email_from
        msg['To'] = cfg.email_to
        msg['Date'] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
        msg['X-Application'] = 'Premiumizer'
        msg.attach(MIMEText(text, 'plain'))
        # Send message
        try:
            smtp = smtplib.SMTP(cfg.email_server, cfg.email_port)

            if cfg.email_encryption:
                smtp.starttls()

            if cfg.email_username != '' and cfg.email_password != '':
                smtp.login(cfg.email_username, cfg.email_password)

            smtp.sendmail(cfg.email_from, cfg.email_to, msg.as_string())

            smtp.quit()
            try:
                log = 'Email send for: %s -- id: %s' % (greenlet.task.name, greenlet.task.id)
            except:
                log = 'Email send for: %s' % subject
            logger.info(log)
        except Exception as err:
            try:
                log = 'Email error for: %s -- id: %s -- error: %s' % (greenlet.task.name, greenlet.task.id, err)
            except:
                log = 'Email error for: %s' % subject
                logger.info(log)
            logger.error(log)

    if send_push:
        try:
            apobj = apprise.Apprise()
            apobj.add(cfg.apprise_url)
            apobj.notify(body=text, title=subject)
            try:
                log = 'Push sent for: %s -- id: %s' % (greenlet.task.name, greenlet.task.id)
            except:
                log = 'Push sent for: %s' % subject
            logger.info(log)
        except Exception as err:
            try:
                log = 'Push error for: %s -- id: %s -- error: %s' % (greenlet.task.name, greenlet.task.id, err)
            except:
                log = 'Push error for: %s' % subject
                logger.info(log)
            logger.error('Could not send via Apprise: %s' % err)


def jd_query_packages(id=None):
    count = 0
    global jd_packages
    if client_connected:
        seconds = 2
    else:
        seconds = 10
    if jd_packages['time'] < (datetime.now() - timedelta(seconds=seconds)):
        jd_packages['time'] = datetime.now()
        try:
            response = cfg.jd_device.downloads.query_packages()
        except BaseException as e:
            downloader_connection()
            try:
                response = cfg.jd_device.downloads.query_packages()
            except:
                response = None
                logger.error('myjdapi : ' + str(e))
        while not response:
            gevent.sleep(5)
            if not jd_packages['time'] < (datetime.now() - timedelta(seconds=seconds)):
                response = jd_packages['packages']
            else:
                try:
                    response = cfg.jd_device.downloads.query_packages()
                except BaseException as e:
                    logger.error('myjdapi : ' + str(e))
            count += 1
            if count == 20:
                logger.error('JD did not return package status for: %s', greenlet.task.name)
                return False
        while not len(response):
            gevent.sleep(5)
            if not jd_packages['time'] < (datetime.now() - timedelta(seconds=seconds)):
                response = jd_packages['packages']
            else:
                try:
                    response = cfg.jd_device.downloads.query_packages()
                except BaseException as e:
                    logger.error('myjdapi : ' + str(e))
            count += 1
            if count == 12:
                logger.error('Could not find package in JD for: %s', greenlet.task.name)
                return False

        jd_packages['packages'] = response

    if id:
        for package in jd_packages['packages']:
            try:
                if id == str(package['uuid']):
                    while 'status' not in package:
                        try:
                            package = package[0]
                            if 'status' in package:
                                break
                        except:
                            pass
                        gevent.sleep(5)
                        try:
                            package = cfg.jd_device.downloads.query_packages([{"packageUUIDs": [id]}])
                        except BaseException as e:
                            logger.error('myjdapi : ' + str(e))
                        count += 1
                        if count == 24:
                            package = {'status': 'Failed'}
                            logger.error('JD did not return package status for: %s', greenlet.task.name)
                    return package
            except:
                return False

    return jd_packages['packages']


def get_download_stats_jd(package_name, package_ids):
    count = 0
    eta_status = ''
    total_speed = []
    total_eta = []
    total_progress = []
    total_bytesloaded = []
    total_bytestotal = []
    task_total_speed = 0
    task_total_eta = ''
    task_total_progress = 0
    task_total_bytesloaded = 0
    task_total_bytestotal = 0
    gevent.sleep(10)
    query_packages = jd_query_packages(package_ids)
    if not query_packages:
        return 1
    while not any(package['name'] in package_name for package in query_packages):
        gevent.sleep(5)
        query_packages = jd_query_packages(package_ids)
        count += 1
        if count == 10:
            logger.error('Could not find package in JD for: %s', greenlet.task.name)
            return 1
    start_time = time.time()

    while not task_total_progress == 100:
        task_total_speed = 0
        task_total_progress = 0
        task_total_bytesloaded = 0
        task_total_bytestotal = 0

        for x in range(len(total_bytestotal)):
            task_total_bytestotal += total_bytestotal[x]
            try:
                task_total_speed += total_speed[x]
                if not total_eta[x] == 'Finished':
                    task_total_eta = total_eta[x]
                task_total_progress += total_progress[x]
                task_total_bytesloaded += total_bytesloaded[x]

            except:
                pass
        try:
            task_total_progress = round((task_total_bytesloaded / task_total_bytestotal) * 100, 1)
        except:
            task_total_progress = 0
        try:
            if eta_status:
                task_total_eta = eta_status
            elif len(package_ids) > 1:
                try:
                    task_total_eta = utils.time_human(
                        (task_total_bytestotal - task_total_bytesloaded) / task_total_speed, fmt_short=True)
                except:
                    pass
            greenlet.task.update(speed=(utils.sizeof_human(task_total_speed) + '/s --- '), dlsize=utils.sizeof_human(
                task_total_bytesloaded) + ' / ' + utils.sizeof_human(
                task_total_bytestotal) + ' --- ', progress=task_total_progress, eta=task_total_eta)
        except:
            pass
        eta_status = ''
        if task_total_progress == 100:
            continue
        for count, package in enumerate(query_packages):
            if package['name'] in package_name:
                if str(package['uuid']) not in package_ids:
                    package_ids.append(str(package['uuid']))
                try:
                    x = package['status']
                except:
                    if package['bytesLoaded'] == 0:
                        try:
                            total_bytestotal[count] = package["bytesTotal"]
                        except:
                            total_bytestotal.append(package["bytesTotal"])
                        continue
                    logger.error('JDownloader did not return package[status]')
                    return 1
                if package['status'] == 'Failed':
                    logger.error('JD returned failed for: %s', greenlet.task.name)
                    greenlet.task.update(eta=' JD returned failed')
                    return 1
                if greenlet.task.local_status == 'stopped':
                    try:
                        cfg.jd_device.downloads.cleanup("DELETE_ALL", "REMOVE_LINKS_AND_DELETE_FILES", "SELECTED",
                                                        package_ids=package_ids)
                    except BaseException as e:
                        logger.error('myjdapi : ' + str(e))
                        logger.error('Could not delete package in JD for : %s', greenlet.task.name)
                        pass
                    return 1
                if greenlet.task.local_status == 'paused':
                    try:
                        cfg.jd_device.downloads.set_enabled(0, package_ids=package_ids)
                        logger.warning('Download paused for: %s', greenlet.task.name)
                    except BaseException as e:
                        logger.error('myjdapi : ' + str(e))
                        logger.error('Could not pause/disable package in JD for : %s', greenlet.task.name)
                        break
                    while greenlet.task.local_status == 'paused':
                        gevent_sleep_time()
                    if greenlet.task.local_status != 'downloading':
                        continue
                    try:
                        cfg.jd_device.downloads.force_download(package_ids=package_ids)
                        logger.info('Download resumed for: %s', greenlet.task.name)
                    except BaseException as e:
                        logger.error('myjdapi : ' + str(e))
                        logger.error('Could not unpause/enable package in JD for : %s', greenlet.task.name)
                try:
                    speed = package['speed']
                except:
                    speed = 0
                if speed == 0:
                    if 'Download' not in package['status']:
                        eta = package['status']
                    else:
                        eta = ' '
                else:
                    eta = " " + utils.time_human(package['eta'], fmt_short=True)

                if len(eta) > 10 and eta != 'Skipped - File already exists' and not eta_status:
                    eta_status = eta
                try:
                    bytestotal = package["bytesTotal"]
                except:
                    logger.error('JD did not return package bytesTotal for: %s', greenlet.task.name)
                    return 1
                try:
                    package_finished = package['finished']
                except:
                    package_finished = False
                if package_finished or package['status'] == 'Skipped - File already exists':
                    tmp_total_progress = 100
                else:
                    tmp_total_progress = round(float(package['bytesLoaded']) * 100 / package["bytesTotal"], 1)
                try:
                    total_speed[count] = speed
                    total_eta[count] = eta
                    total_progress[count] = tmp_total_progress
                    total_bytesloaded[count] = package['bytesLoaded']
                    total_bytestotal[count] = bytestotal
                except:
                    total_speed.append(speed)
                    total_eta.append(eta)
                    total_progress.append(tmp_total_progress)
                    total_bytesloaded.append(package['bytesLoaded'])
                    total_bytestotal.append(bytestotal)
            try:
                while 'Extracting' in package['status']:
                    try:
                        eta = package['status'].split('ETA: ', 1)[1].split(')', 1)[0]
                    except:
                        eta = ''
                    greenlet.task.update(speed=" ", progress=99, eta=' Extracting ' + eta)
                    gevent_sleep_time()
            except:
                pass
        gevent_sleep_time()
        query_packages = jd_query_packages(package_ids)

    stop_time = time.time()
    dltime = int(stop_time - start_time)
    greenlet.task.update(dltime=dltime)
    try:
        cfg.jd_device.downloads.cleanup("DELETE_ALL", "REMOVE_LINKS_ONLY", "SELECTED", package_ids=package_ids)
    except BaseException as e:
        logger.error('myjdapi : ' + str(e))
        logger.error('Could not delete packages in JD for: %s', greenlet.task.name)
        pass
    return 0


def get_download_stats(downloader, total_size_downloaded):
    logger.debug('def get_download_stats started')
    if downloader.get_status() == 'downloading':
        size_downloaded = total_size_downloaded + downloader.get_dl_size()
        progress = round(float(size_downloaded) * 100 / greenlet.task.size, 1)
        speed = downloader.get_speed(human=False)
        if speed == 0:
            eta = ' '
        else:
            tmp = (greenlet.task.size - size_downloaded) / speed
            eta = ' ' + utils.time_human(tmp, fmt_short=True)
        greenlet.task.update(speed=utils.sizeof_human(speed) + '/s --- ',
                             dlsize=utils.sizeof_human(size_downloaded) + ' / ' + utils.sizeof_human(
                                 greenlet.task.size) + ' --- ', progress=progress, eta=eta)

    elif downloader.get_status() == 'combining':
        greenlet.task.update(progress=99, speed=' ', eta=' Combining files')
    elif downloader.get_status() == 'paused':
        greenlet.task.update(progress=99, speed=' ', eta=' Download paused')
    else:
        logger.debug('Want to update stats, but downloader status is invalid.')


def get_download_stats_aria2(aria2_download, total_size_downloaded):
    logger.debug('def get_download_stats_aria2 started')
    if aria2_download['status'] == 'active':
        size_downloaded = total_size_downloaded + int(aria2_download['completedLength'])
        progress = round(float(size_downloaded) * 100 / greenlet.task.size, 1)
        speed = int(aria2_download['downloadSpeed'])
        if speed == 0:
            eta = ' '
        else:
            tmp = (greenlet.task.size - size_downloaded) / speed
            eta = ' ' + utils.time_human(tmp, fmt_short=True)
        greenlet.task.update(speed=utils.sizeof_human(speed) + '/s --- ',
                             dlsize=utils.sizeof_human(size_downloaded) + ' / ' + utils.sizeof_human(
                                 greenlet.task.size) + ' --- ', progress=progress, eta=eta)
    else:
        logger.debug('Want to update stats, but downloader status is invalid.')


def download_file():
    logger.debug('def download_file started')
    count = 0
    files_downloaded = 0
    total_size_downloaded = 0
    dltime = 0
    returncode = 0
    package_ids = []
    if cfg.jd_enabled:
        try:
            query_links = cfg.jd_device.downloads.query_links()
        except BaseException as e:
            downloader_connection()
            if cfg.jd_connected:
                try:
                    query_links = cfg.jd_device.downloads.query_links()
                except BaseException as e:
                    query_links = False
                while query_links is False:
                    gevent.sleep(5)
                    query_links = cfg.jd_device.downloads.query_links()
                    count = + 1
                    if count == 5:
                        logger.error('myjdapi : ' + str(e))
                        greenlet.task.update(eta=' ' + str(e))
                        return 1
            else:
                return 1
    if cfg.aria2_enabled:
        downloader_connection()
        if not cfg.aria2_connected:
            return 1

    for download in greenlet.task.download_list:
        if greenlet.task.type == 'Filehost':
            payload = {'apikey': cfg.prem_apikey, 'src': download['url']}
            r = prem_connection("post", "https://www.premiumize.me/api/transfer/directdl", payload)
            response_content = json.loads(r.content)
            try:
                download['url'] = response_content['location']
            except:
                return 1
            download['combined_path'] = os.path.join(greenlet.task.dldir, download['combined_path'])
        logger.debug('Downloading file: %s', download['combined_path'])
        if not os.path.isfile(download['combined_path']) and not os.path.isfile(
                os.path.join(greenlet.task.dldir, download['name'])):
            url = str(download['url'])
            files_downloaded = 1
            if cfg.download_builtin:
                downloader = SmartDL(url, download['combined_path'], progress_bar=False, logger=logger,
                                     threads=cfg.download_threads, fix_urls=False)
                downloader.start(blocking=False)
                while not downloader.isFinished():
                    if cfg.download_speed != -1:
                        jobs = len(scheduler.scheduler._lookup_executor('downloads')._instances)
                        if jobs != 0:
                            downloader.limit_speed(cfg.download_speed / jobs)
                        else:
                            downloader.limit_speed(cfg.download_speed)
                    get_download_stats(downloader, total_size_downloaded)
                    if greenlet.task.local_status == "paused":
                        downloader.pause()
                        while greenlet.task.local_status == "paused":
                            gevent_sleep_time()
                        downloader.unpause()
                    if greenlet.task.local_status == "stopped":
                        downloader.stop()
                        return 1
                    gevent_sleep_time()
                if downloader.isSuccessful():
                    dltime += downloader.get_dl_time()
                    total_size_downloaded += downloader.get_dl_size()
                    logger.debug('Finished downloading file: %s', download['combined_path'])
                    greenlet.task.update(dltime=dltime)
                else:
                    logger.error('Error for %s: while downloading file: %s', greenlet.task.name,
                                 download['combined_path'])
                    for e in downloader.get_errors():
                        logger.error(str(greenlet.task.name + ": " + e))
                    returncode = 1

            elif cfg.jd_enabled:
                if cfg.jd_connected:
                    if len(query_links):
                        if any(link['name'] == download['name'] for link in query_links):
                            download['download_ok'] = False
                            continue
            elif cfg.aria2_enabled:
                if cfg.aria2_connected:
                    transfers = cfg.aria.aria2.tellActive(cfg.aria2_token) + cfg.aria.aria2.tellWaiting(cfg.aria2_token,
                                                                                                        -1,
                                                                                                        99) + cfg.aria.aria2.tellStopped(
                        cfg.aria2_token, -1, 99)
                    if len(transfers):
                        if any(transfer['dir'] == download['combined_path'] for transfer in transfers):
                            continue
                    start_time = time.time()
                    try:
                        options = {'dir': os.path.dirname(download['combined_path'])}
                        gid = cfg.aria.aria2.addUri(cfg.aria2_token, [url], options)
                    except BaseException as e:
                        gid = 0
                        logger.error('aria2 error: %s --- for: %s', str(e.message), greenlet.task.name)
                    aria2_download = cfg.aria.aria2.tellStatus(cfg.aria2_token, gid)
                    while not aria2_download["status"] == 'complete':
                        if aria2_download['status'] == 'error':
                            logger.error('aria2 error for %s: while downloading file: %s', greenlet.task.name,
                                         download['combined_path'])
                            greenlet.task.update(eta=' aria2 error')
                            return 1
                        elif greenlet.task.local_status == "paused":
                            cfg.aria.aria2.pause(cfg.aria2_token, gid)
                            logger.warning('Download paused for: %s', greenlet.task.name)
                            while greenlet.task.local_status == "paused":
                                gevent_sleep_time()
                            cfg.aria.aria2.unpause(cfg.aria2_token, gid)
                            logger.info('Download resumed for: %s', greenlet.task.name)
                        elif greenlet.task.local_status == "stopped":
                            cfg.aria.aria2.remove(cfg.aria2_token, gid)
                            return 1
                        get_download_stats_aria2(aria2_download, total_size_downloaded)
                        gevent_sleep_time()
                        aria2_download = cfg.aria.aria2.tellStatus(cfg.aria2_token, gid)
                    stop_time = time.time()
                    dltime = int(stop_time - start_time)
                    total_size_downloaded += int(aria2_download['totalLength'])
                    cfg.aria.aria2.removeDownloadResult(cfg.aria2_token, gid)
                    logger.debug('Finished downloading file: %s', download['combined_path'])
                    greenlet.task.update(dltime=greenlet.task.dltime + dltime)

        else:
            logger.info('File not downloaded it already exists at: %s', download['combined_path'])

    if cfg.jd_enabled and files_downloaded:
        if cfg.jd_connected:
            folder_downloadlist = []
            for x in greenlet.task.download_list:
                if x['download_ok']:
                    tmp = x['url']
                    x['url'] = f'"{tmp}"'
                    ok = 0
                    for z in folder_downloadlist:
                        if x['path'] == z['path']:
                            z['url'] += x['url']
                            ok = 1
                            break
                    if not ok:
                        folder_downloadlist.append(x)

            package_name = 'Premiumizer_ ' + clean_name(greenlet.task.name)
            if not len(folder_downloadlist):
                logger.error('Nothing to download / link already exists ? for : %s', greenlet.task.name)
            for download in folder_downloadlist:
                try:
                    url = str(download['url'])
                    jd_jobid = cfg.jd_device.linkgrabber.add_links(
                        [{"assignJobID": True, "autostart": True, "links": url,
                          "packageName": package_name,
                          "destinationFolder": (download['path']),
                          "overwritePackagizerRules": True}])
                    package_ids.append(jd_jobid['id'])
                except BaseException as e:
                    logger.error('myjdapi error: ' + str(e))
            returncode = get_download_stats_jd(package_name, package_ids)

    return returncode


def is_sample(dir_content):
    media_extensions = [".mkv", ".avi", ".divx", ".xvid", ".mov", ".wmv", ".mp4", ".mpg", ".mpeg", ".vob", ".iso"]
    media_size = 150 * 1024 * 1024
    if dir_content['size'] < media_size:
        if dir_content['link'].lower().endswith(tuple(media_extensions)):
            if ('sample' or 'rarbg.com' in dir_content['url'].lower()) and (
                    'sample' not in greenlet.task.name.lower()):
                return True
    return False


def process_dir(dir_content, path):
    logger.debug('def processing_dir started')
    download_list = greenlet.task.download_list
    if not dir_content:
        return None
    for x in dir_content:
        download_file_continue = 0
        type = x['type']
        if type == 'folder':
            logger.debug('Processing subfolder: %s', x['name'])
            subdir_path = os.path.join(path, clean_name(x['name']))
            if not os.path.exists(subdir_path):
                logger.debug('Creating subfolder: %s', x['name'])
                os.makedirs(subdir_path)
            r = prem_connection("post", "https://www.premiumize.me/api/folder/list",
                                {'apikey': cfg.prem_apikey, 'id': x['id']})
            subdir_content = json.loads(r.content)['content']
            process_dir(subdir_content, subdir_path)
        elif type == 'file':
            if greenlet.task.dlext_blacklist:
                if greenlet.task.dlext[0] == '' or not x['link'].lower().endswith(tuple(greenlet.task.dlext)):
                    download_file_continue = 1
                else:
                    logger.debug('Skipping download of file %s because extension is blacklisted', x['name'])
            else:
                if x['link'].lower().endswith(tuple(greenlet.task.dlext)):
                    download_file_continue = 1
                else:
                    logger.debug('Skipping download of file %s because extension is not whitelisted', x['name'])
            if download_file_continue:
                if greenlet.task.delsample:
                    sample = is_sample(x)
                    if sample:
                        continue
                logger.debug('Starting download of file %s to directory %s', x['name'], path)
                download = {'id': x['id'], 'name': x['name'], 'path': path, 'size': x['size'], 'download_ok': True,
                            'combined_path': os.path.join(path, clean_name(x['name'])), 'url': x['link']}
                download_list.append(download)
                total_size = greenlet.task.size
                total_size += x['size']
                greenlet.task.update(download_list=download_list, size=total_size)


def download_process():
    logger.debug('def download_process started')
    returncode = 0
    if greenlet.task.type != 'Filehost':
        greenlet.task.update(local_status='downloading', progress=0, speed=' ', eta=' ', size=0, download_list=[])
    else:
        greenlet.task.update(local_status='downloading', progress=0, speed=' ', eta=' ')
    name = clean_name(greenlet.task.name)
    if not greenlet.task.dldir.endswith(name):
        greenlet.task.dldir = os.path.join(greenlet.task.dldir, name)
    if not greenlet.task.type == 'Filehost':
        if greenlet.task.file_id:
            r = prem_connection("post", "https://www.premiumize.me/api/folder/list",
                                {'apikey': cfg.prem_apikey})

            def is_match(folder_list_item):
                return folder_list_item['id'] == greenlet.task.file_id

            dir_content = [next(filter(is_match, json.loads(r.content)['content']))]
        else:
            r = prem_connection("post", "https://www.premiumize.me/api/folder/list",
                                {'apikey': cfg.prem_apikey, 'id': greenlet.task.folder_id})
            dir_content = json.loads(r.content)['content']
        if 'failed' in r:
            return 1
        if not dir_content:
            logger.debug('Could not find any content to download for task %s', greenlet.task.name)
        else:
            process_dir(dir_content, greenlet.task.dldir)
    if greenlet.task.download_list:
        logger.info('Downloading: %s -- id: %s', greenlet.task.name, greenlet.task.id)
        returncode = download_file()
    else:
        logger.error('Error for %s: Nothing to download .. Filtered out or bad torrent/nzb ?', greenlet.task.name)
        returncode = 1
    if returncode == 0:
        greenlet.task.update(progress=100, speed=' ', eta=' ')
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
            logger.error('Download failed for: %s -- id: %s', task.name, task.id)
    elif task.local_status == 'stopped':
        logger.warning('Download stopped for: %s', greenlet.task.name)
        task.update(progress=100)
        gevent.sleep(3)
        try:
            shutil.rmtree(task.dldir)
        except:
            if not cfg.jd_enabled:
                logger.warning('Could not delete folder for: %s', greenlet.task.name)
        if task.progress == 100:
            task.update(category='', local_status='waiting')
            scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=1)
            return
    if not failed:
        try:
            greenlet.avgspeed = str(utils.sizeof_human((task.size / task.dltime)) + '/s')
        except:
            greenlet.avgspeed = "0"
        logger.info('Download finished: %s -- id: %s -- info: %s --  %s --  %s -- location: %s', task.name, task.id,
                    utils.sizeof_human(task.size), greenlet.avgspeed, utils.time_human(task.dltime, fmt_short=True),
                    task.dldir)
        if task.dlnzbtomedia:
            failed = notify_nzbtomedia()
            if failed:
                task.update(local_status='failed: nzbToMedia')

    if task.local_status != 'stopped' and task.local_status != 'waiting' and task.local_status != 'paused':
        if not failed:
            send_notification(
                'download success',
                send_email=cfg.email_enabled and not cfg.email_on_failure,
                send_push=cfg.apprise_enabled and not cfg.apprise_push_on_failure
            )
        else:
            send_notification('download failed')

    if cfg.remove_cloud:
        if not failed:
            if cfg.seed_torrent:
                if task.cloud_status != 'seeding':
                    delete_task(task.id)
                else:
                    task.update(eta='Seeding', speed='', dlsize='', local_status='finished_seeding', progress=99)
            elif cfg.remove_cloud_delay != 0 and task.type != 'Filehost':
                scheduler.scheduler.add_job(delete_task, args=(task.id,), name=task.name, id=task.name,
                                            misfire_grace_time=7200, coalesce=False, jobstore='remove_cloud',
                                            replace_existing=True,
                                            next_run_time=(datetime.now() + timedelta(hours=cfg.remove_cloud_delay)))
                time = (scheduler.scheduler.get_job(task.name).next_run_time.replace(tzinfo=None) - datetime.now())
                time = str(time).split('.', 2)[0]
                task.update(eta='Deleting from the cloud in' + time, speed='', dlsize='',
                            local_status='finished_waiting', progress=99)
            else:
                delete_task(task.id)
    else:
        task.update(local_status='finished')

    scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=1)


def prem_connection(method, url, payload, files=None):
    logger.debug('def prem_connection started')
    r = None
    r_count = 0
    while r is None:
        r_count += 1
        try:
            if method == 'post':
                r = prem_session.post(url, payload, timeout=60)
            elif method == 'postfile':
                r = prem_session.post(url, payload, files=files, timeout=60)
            elif method == 'get':
                r = prem_session.get(url, params=payload, timeout=60)
            if 'Not logged in. Please log in first' in r.text:
                msg = 'premiumize.me login error: %s' % r.text
                logger.error(msg)
                send_notification('Premiumize.me login error', msg)
                return 'failed: premiumize.me login error'
            if r.status_code != 200:
                raise Exception('status_code != 200')
        except:
            if r_count == 3:
                try:
                    message = r.text
                except:
                    message = ' '
                try:
                    msg = 'premiumize.me error: %s for: %s' % (message, greenlet.task.name)
                except:
                    msg = 'premiumize.me error: %s' % message
                logger.error(msg)
                send_notification('Premiumize.me error', msg)
                return 'failed'
            gevent.sleep(3)
            r = None
            continue
    return r


def update():
    logger.debug('def update started')
    idle = True
    if client_connected:
        update_interval = 3
    else:
        update_interval = idle_interval
    payload = {'apikey': cfg.prem_apikey}
    r = prem_connection("post", "https://www.premiumize.me/api/transfer/list", payload)
    if 'failed' not in r:
        response_content = json.loads(r.content)
        if response_content['status'] == "success":
            if not response_content['transfers']:
                update_interval = 30
            transfers = response_content['transfers']
            idle = parse_tasks(transfers)
        else:
            socketio.emit('premiumize_connect_error', {})
    else:
        socketio.emit('premiumize_connect_error', {})
    if not idle:
        update_interval = active_interval
    scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=update_interval)


def parse_tasks(transfers):
    logger.debug('def parse_task started')
    id_online = []
    id_local = []
    idle = True
    for task in tasks:
        id_local.append(task.id)
        if task.type == 'Filehost':
            try:
                x = db[task.id]
            except:
                task.callback = None
                db[task.id] = task
                task.callback = socketio.emit
            task.update()
    for transfer in reversed(transfers):
        if transfer['name'] is None or transfer['name'] == 0:
            name = 'Loading name'
        else:
            name = transfer['name']
        eta = ' '
        speed = ' '
        size = ' '
        task = get_task(transfer['id'], name)
        try:
            name = urllib.parse.unquote(name)
            name = clean_name(name)
            if 'download.php?id=' in name:
                name = name.split("&f=", 1)[1]
            if name.endswith('.torrent'):
                name = name.split('.torrent', 1)[0]
            elif name.endswith('.nzb'):
                name = name.split('.nzb', 1)[0]
        except:
            pass
        try:
            if 'ETA is' in transfer['message']:
                eta = transfer['message'].split("ETA is", 1)[1]
            elif 'peers,' in transfer['message'] or 'peer,' in transfer['message'] or 'usenet,' in transfer['message']:
                eta = transfer['message'].rsplit(',', 2)[2]
            elif transfer['message']:
                eta = transfer['message']
        except:
            pass
        try:
            if 'Downloading at' in transfer['message']:
                speed = transfer['message'].split("Downloading at", 1)[1].split(". ", 1)[0]
            elif 'peers,' in transfer['message'] or 'peer,' in transfer['message'] or 'usenet,' in transfer['message']:
                speed = transfer['message'].rsplit(',', 2)[0]
        except:
            pass
        try:
            if '% of' in transfer['message']:
                size = transfer['message'].split("of ", 1)[1].split(" finished", 1)[0]
                progress = int(transfer['message'].split("s.", 1)[1].split("% of", 1)[0])
            elif 'peers,' in transfer['message'] or 'peer,' in transfer['message'] or 'usenet,' in transfer['message']:
                size = transfer['message'].rsplit(',', 2)[1]
                progress = int(round(float(transfer['progress']) * 100))
            else:
                progress = int(round(float(transfer['progress']) * 100))
        except:
            if transfer['progress']:
                progress = int(round(float(transfer['progress']) * 100))
            else:
                progress = 100
        try:
            folder_id = transfer['folder_id']
        except:
            folder_id = None
        try:
            file_id = transfer['file_id']
        except:
            file_id = None
        if not task:
            if cfg.download_all:
                add_task(transfer['id'], size, name, 'default', folder_id=folder_id)
            else:
                add_task(transfer['id'], size, name, '', folder_id=folder_id)
            task = get_task(transfer['id'], name)
            id_local.append(task.id)
            task.update(name=name, progress=progress, cloud_status=transfer['status'], dlsize=size + ' --- ',
                        speed=speed + ' --- ', eta=eta, file_id=file_id)
        if task.local_status is None:
            if task.cloud_status != 'finished' and task.cloud_status != 'seeding':
                task.update(name=name, progress=progress, cloud_status=transfer['status'], dlsize=size + ' --- ',
                            speed=speed + ' --- ', eta=eta, folder_id=folder_id, file_id=file_id)
                idle = False
            elif task.cloud_status == 'finished' or task.cloud_status == 'seeding':
                if cfg.download_enabled and downloader_connection():
                    if task.category == '':
                        if cfg.download_rss and transfer['folder_id']:
                            try:
                                r = prem_connection("post", "https://www.premiumize.me/api/folder/list",
                                                    {'apikey': cfg.prem_apikey, 'id': transfer['folder_id'],
                                                     'includebreadcrumbs': 1})
                                breadcrumbs = json.loads(r.content)['breadcrumbs']
                                if len(breadcrumbs) > 1:
                                    if breadcrumbs[1]['name'] == 'Feed Downloads':
                                        if breadcrumbs[2]['name'] in cfg.download_categories:
                                            dldir, dlext, dlext_blacklist, delsample, dlnzbtomedia = get_cat_var(
                                                breadcrumbs[2]['name'])
                                            task.update(name=name, cloud_status=transfer['status'], local_status=None,
                                                        process=None, speed=None, category=breadcrumbs[2]['name'],
                                                        dldir=dldir, dlext=dlext, dlext_blacklist=dlext_blacklist,
                                                        delsample=delsample, dlnzbtomedia=dlnzbtomedia, type='RSS')
                                        else:
                                            logger.warning('RSS feed name not in categories: %s',
                                                           breadcrumbs[2]['name'])
                            except BaseException as e:
                                logger.error('RSS download failed: ' + str(e))
                                pass
                        elif cfg.download_all:
                            task.update(name=name, cloud_status=transfer['status'], category='default')
                    if task.category in cfg.download_categories:
                        if not task.local_status == ('queued' or 'downloading'):
                            task.update(name=name, cloud_status=transfer['status'], local_status='queued',
                                        folder_id=folder_id,
                                        file_id=file_id, dlsize='')
                            gevent.sleep(3)
                            if cfg.time_shed:
                                shed_start = datetime.strptime(cfg.time_shed_start, "%H:%M")
                                time_now = datetime.strptime((datetime.now().strftime("%H:%M")), "%H:%M")
                                shed_stop = datetime.strptime(cfg.time_shed_stop, "%H:%M")
                                if not shed_start <= time_now <= shed_stop:
                                    tdelta = shed_start - time_now
                                    tdelta = tdelta.seconds
                                    runtime = datetime.now() + timedelta(seconds=tdelta)
                                    scheduler.scheduler.add_job(download_task, args=(task,), name=task.name, id=task.id,
                                                                misfire_grace_time=7200, coalesce=False,
                                                                max_instances=1, jobstore='downloads',
                                                                executor='downloads', replace_existing=True,
                                                                next_run_time=runtime)
                                    logger.info('Starting download task: %s -- id: %s -- at: %s ', task.name, task.id,
                                                runtime)
                            else:
                                scheduler.scheduler.add_job(download_task, args=(task,), name=task.name, id=task.id,
                                                            misfire_grace_time=7200, coalesce=False, max_instances=1,
                                                            jobstore='downloads', executor='downloads',
                                                            replace_existing=True)
                    elif task.category == '':
                        task.update(name=name, cloud_status=transfer['status'], local_status='waiting', progress=100,
                                    folder_id=folder_id, file_id=file_id)
                else:
                    if cfg.download_enabled and not cfg.downloader_connection:
                        msg = 'Download failure due to downloader connection error while trying to download: %s ' % task.name
                        logger.error(msg)
                        send_notification('Downloader connection error', msg)
                    task.update(name=name, cloud_status=transfer['status'], local_status='download_disabled',
                                speed=None, folder_id=folder_id, file_id=file_id)
        else:
            if task.local_status == 'downloading':
                if task.name not in str(scheduler.scheduler.get_jobs('check_downloads')):
                    scheduler.scheduler.add_job(check_downloads, args=(task.dlsize, task.id, task.name), id=task.id,
                                                name=(task.name + ' check_downloads'), misfire_grace_time=7200,
                                                jobstore='check_downloads', replace_existing=True, max_instances=1,
                                                coalesce=True, next_run_time=(datetime.now() + timedelta(minutes=10)))
            elif task.local_status == 'finished_seeding':
                if transfer['status'] == 'finished':
                    delete_task(task.id)
                else:
                    task.update(name=name, cloud_status=transfer['status'], eta=eta)
            elif task.local_status == 'finished_waiting':
                try:
                    time = (scheduler.scheduler.get_job(task.name).next_run_time.replace(tzinfo=None) - datetime.now())
                    time = str(time).split('.', 2)[0]
                    task.update(name=name, cloud_status=transfer['status'], eta='Deleting from cloud in: ' + time)
                except:
                    delete_task(task.id)
            task.update(name=name, cloud_status=transfer['status'], folder_id=folder_id, file_id=file_id)
        id_online.append(task.id)
        task.callback = None
        db[task.id] = task
        task.callback = socketio.emit

    # Delete local task.id that are removed from cloud
    id_diff = [aa for aa in id_local if aa not in set(id_online)]
    for task_id in id_diff:
        for task in tasks:
            if task.type != 'Filehost' and task.id == task_id:
                tasks.remove(task)
                try:
                    del db[task_id]
                except:
                    pass
    db.sync()
    socketio.emit('tasks_updated', {})
    return idle


def check_downloads(dlsize, id, name):
    logger.debug('def check_downloads started')
    try:
        task = get_task(id, name)
    except:
        return
    if task.local_status == 'downloading':
        if dlsize == task.dlsize:
            dldir = get_cat_var(task.category)
            dldir = dldir[0]
            task.update(local_status=None, dldir=dldir)
            msg = 'Download: %s stuck restarting task' % task.name
            logger.warning(msg)
            send_notification('Download stuck', msg)
            scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=1)


def get_task(id, name=None):
    logger.debug('def get_task started')
    for task in tasks:
        if task.id == id:
            return task
        elif task.name == name:
            task.update(id=id)
            return task
    return None


# noinspection PyUnboundLocalVariable
def get_cat_var(category):
    logger.debug('def get_cat_var started')
    dldir = None
    dlext = None
    dlext_blacklist = None
    delsample = 0
    dlnzbtomedia = 0
    if any(cat['name'] == category for cat in cfg.categories):
        for cat in cfg.categories:
            if cat['name'] == category:
                dldir = cat['dir']
                dlext = cat['ext']
                dlext_blacklist = cat['ext_blacklist']
                delsample = cat['delsample']
                dlnzbtomedia = cat['nzb']
    else:
        if category != '':
            logger.debug('%s not found in categories', category)
    return dldir, dlext, dlext_blacklist, delsample, dlnzbtomedia


def add_task(id, size, name, category, type='', folder_id=None):
    logger.debug('def add_task started')
    exists = get_task(id, name)
    if not exists:
        dldir, dlext, dlext_blacklist, delsample, dlnzbtomedia = get_cat_var(category)
        try:
            name = urllib.parse.unquote(name)
            name = clean_name(name)
            if 'download.php?id=' in name:
                name = name.split("&f=", 1)[1]
            if name.endswith('.torrent'):
                name = name.split('.torrent', 1)[0]
                type = 'Torrent'
            elif name.endswith('.nzb'):
                name = name.split('.nzb', 1)[0]
                type = 'NZB'
        except:
            pass
        task = DownloadTask(socketio.emit, id, folder_id, size, name, category, dldir, dlext, dlext_blacklist,
                            delsample, dlnzbtomedia, type)
        tasks.append(task)
        if not task.type == 'Filehost':
            logger.info('Added: %s -- Category: %s -- Type: %s -- id: %s', task.name, task.category, task.type, task.id)
    else:
        task = 'duplicate'
    return task


def upload_torrent(torrent):
    logger.debug('def upload_torrent started')
    payload = {'apikey': cfg.prem_apikey}
    files = {'src': open(torrent, 'rb')}
    logger.debug('Uploading torrent to the cloud: %s', torrent)
    r = prem_connection("postfile", "https://www.premiumize.me/api/transfer/create", payload, files)
    if 'failed' not in r:
        response_content = json.loads(r.content)
        if response_content['status'] == "success":
            logger.debug('Upload successful: %s', torrent)
            return response_content['id'], response_content['name']
        elif response_content['message'] == \
                'An error occured. Please try again and contact customer service if the problem persists.':
            gevent.sleep(10)
            r = prem_connection("postfile", "https://www.premiumize.me/api/transfer/create", payload, files)
            if 'failed' not in r:
                response_content = json.loads(r.content)
                if response_content['status'] == \
                        "success" or response_content['message'] == 'You already added this job.':
                    logger.debug('Upload successful: %s', torrent)
                    return response_content['id'], ''
        else:
            msg = 'Upload of torrent: %s failed, message: %s' % (torrent, response_content['message'])
            logger.error(msg)
            if response_content['message'] == 'You already added this job.':
                return 'duplicate', ''
            send_notification('Upload of torrent failed', msg)
            return 'failed', ''
    else:
        return 'failed', ''


def upload_magnet(magnet):
    logger.debug('def upload_magnet started')
    payload = {'apikey': cfg.prem_apikey, 'src': magnet}
    r = prem_connection("post", "https://www.premiumize.me/api/transfer/create", payload)
    if 'failed' not in r:
        response_content = json.loads(r.content)
        if response_content['status'] == "success":
            logger.debug('Upload magnet successful')
            return response_content['id'], response_content['name']
        elif response_content[
            'message'] == 'An error occured. Please try again and contact customer service if the problem persists.':
            gevent.sleep(10)
            r = prem_connection("post", "https://www.premiumize.me/api/transfer/create", payload)
            if 'failed' not in r:
                response_content = json.loads(r.content)
                if response_content['status'] == "success" or response_content[
                    'message'] == 'You already added this job.':
                    logger.debug('Upload magnet successful')
                    return response_content['id'], ''
        else:
            msg = 'Upload of magnet: %s failed, message: %s' % (magnet, response_content['message'])
            logger.error(msg)
            if response_content['message'] == 'You already added this job.':
                return 'duplicate', ''
            send_notification('Upload of magnet failed', msg)
            return 'failed', ''
    else:
        return 'failed', ''


def upload_filehost(urls):
    logger.debug('def upload_filehost started')
    download_list = []
    id = uuid.uuid4().hex
    total_filesize = 0
    failed = 0
    name = ''
    task = add_task(id, 0, name, '', type='Filehost')
    if task == 'duplicate':
        return
    for url in urls.splitlines():
        payload = {'apikey': cfg.prem_apikey, 'src': url}
        r = prem_connection("post", "https://www.premiumize.me/api/transfer/directdl", payload)
        try:
            response_content = json.loads(r.content)
            if response_content['status'] == 'success':
                full_name = response_content['filename']
                if name == '':
                    name = os.path.splitext(full_name)[0]
                    if full_name.endswith('.part1'):
                        name = name.split('.part1', 1)[0]
                    elif full_name.endswith('.part01'):
                        name = name.split('.part01', 1)[0]
                download = {'path': clean_name(full_name), 'url': url}
                download_list.append(download)
                try:
                    filesize = response_content['filesize']
                    total_filesize += filesize
                except:
                    pass
            else:
                failed = 1
                logger.error('Filehost error: %s for %s', response_content['message'], urls)
        except:
            failed = 1
            try:
                logger.error('Filehost error: %s for %s', r.text, urls)
            except:
                logger.error('Filehost error for %s', urls)
            break
    logger.info('Added: %s -- Category: %s -- Type: %s -- id: %s', name, task.category, task.type, task.id)
    if failed:
        try:
            eta = r.text
        except:
            eta = ""
        task.update(name=urls, local_status='failed: Filehost', cloud_status='finished', speed="", progress=0, eta=eta)
    else:
        task.update(name=name, local_status='waiting', cloud_status='finished', progress=100,
                    download_list=download_list, size=total_filesize)


def upload_nzb(filename):
    logger.debug('def upload_nzb started')
    payload = {'apikey': cfg.prem_apikey}
    files = {'src': open(filename, 'rb')}
    logger.debug('Uploading nzb to the cloud: %s', filename)
    r = prem_connection("postfile", "https://www.premiumize.me/api/transfer/create", payload, files)
    if 'failed' not in r:
        response_content = json.loads(r.content)
        if response_content['status'] == "success":
            logger.debug('Upload nzb successful: %s', filename)
            return response_content['id'], response_content['name']
        elif response_content[
            'message'] == 'An error occured. Please try again and contact customer service if the problem persists.':
            gevent.sleep(10)
            r = prem_connection("postfile", "https://www.premiumize.me/api/transfer/create", payload, files)
            if 'failed' not in r:
                response_content = json.loads(r.content)
                if response_content['status'] == "success" or response_content[
                    'message'] == 'You already added this job.':
                    logger.debug('Upload nzb successful: %s', filename)
                    return response_content['id'], ''
        else:
            msg = 'Upload of nzb: %s failed, message: %s' % (filename, response_content['message'])
            logger.error(msg)
            if response_content['message'] == 'You already added this job.':
                return 'duplicate', ''
            send_notification('Upload of nzb failed', msg)
            return 'failed', ''
    else:
        return 'failed', ''


def walk_watchdir():
    global watchdog_handler
    logger.debug('def walk_watchdir started')
    for dirpath, dirs, files in os.walk(cfg.watchdir_location):
        for file in files:
            filepath = os.path.join(dirpath, file)
            watchdog_handler.on_created(events.FileCreatedEvent(filepath))
    if cfg.watchdir_walk_enabled:
        interval = cfg.watchdir_walk_interval
        scheduler.scheduler.reschedule_job('walk_watchdir', trigger='interval', seconds=interval)


def torrent_metainfo(torrent):
    logger.debug('def torrent_metainfo started')
    with open(torrent, 'rb') as f:
        torrent_data = f.read()
    metainfo = bencode.bdecode(torrent_data)
    name = metainfo['info']['name']
    return name


def load_tasks():
    logger.debug('def load_tasks started')
    for id in db.keys():
        task = db[id]
        task.callback = socketio.emit
        tasks.append(task)
    for task in tasks:
        if task.local_status == 'downloading' or task.local_status == 'queued':
            task.update(local_status=None)


def watchdir():
    try:
        global watchdog_handler
        logger.debug('Initializing watchdog')
        observer = Observer()
        observer.schedule(watchdog_handler, path=cfg.watchdir_location, recursive=True)
        observer.start()
        logger.debug('Initializing watchdog complete')
        if cfg.watchdir_walk_enabled:
            scheduler.scheduler.add_job(walk_watchdir, 'interval', id='walk_watchdir', seconds=active_interval,
                                        replace_existing=True, max_instances=1, coalesce=True)
        else:
            walk_watchdir()

    except:
        raise


# Flask
@app.route('/')
@login_required
def home():
    if cfg.jd_enabled:
        if not cfg.jd_connected:
            downloader_connection()
        try:
            download_speed = cfg.jd_device.toolbar.get_status().get('limitspeed')
            if download_speed == 0:
                cfg.download_speed = -1
            else:
                cfg.download_speed = download_speed
        except:
            pass
    if cfg.aria2_enabled and not cfg.aria2_connected:
        downloader_connection()
    if not cfg.download_speed == -1:
        download_speed = utils.sizeof_human(cfg.download_speed)
    else:
        download_speed = cfg.download_speed
    return render_template('index.html', download_speed=download_speed, debug_enabled=debug_enabled, cfg=cfg)


@app.route('/upload', methods=["POST"])
@login_required
def upload():
    failed = 0
    if request.files:
        upload_file = request.files['file']
        filename = secure_filename(upload_file.filename)
        tmp = os.path.join(ConfDir, 'tmp')
        if not os.path.isdir(tmp):
            os.makedirs(tmp)
        upload_file.save(os.path.join(tmp, filename))
        upload_file = os.path.join(tmp, filename)
        if upload_file.endswith('.torrent'):
            failed = upload_torrent(upload_file)
        if upload_file.endswith('.nzb'):
            failed = upload_nzb(upload_file)
        if upload_file.endswith('.magnet'):
            with open(upload_file) as f:
                magnet = f.read()
                failed = upload_magnet(magnet)
        if failed != 'failed':
            try:
                os.remove(upload_file)
            except Exception as err:
                logger.error('Could not remove file from tmp: %s --- error: %s', upload_file, err)
    elif request.data:
        if request.data.decode('utf-8').startswith('magnet:'):
            upload_magnet(request.data.decode('utf-8'))
        else:
            upload_filehost(request.data.decode('utf-8'))
    scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=1)
    return 'OK'


def history_update(history, line, status, success):
    if status == 'check_name':
        try:
            id = line.split("id: ", 1)[1].splitlines()[0]
            taskname = line.split("Downloading: ", 1)[1].splitlines()[0].split(" --", 1)[0]
        except:
            return
        for item in history:
            if item['id'] == id:
                if item['name'] != taskname:
                    item['name'] = taskname
                return
    else:
        for item in history:
            if item['id'] in line:
                item[status] = success
                return


@app.route('/history')
@login_required
def history():
    history = []
    try:
        if debug_enabled:
            log = 'premiumizerDEBUG.log'
        else:
            log = 'premiumizer.log'
        with open(os.path.join(LogsDir, log), 'r') as f:
            for line in f:
                if 'Added:' in line:
                    taskname = line.split("Added: ", 1)[1].splitlines()[0].split(" --", 1)[0]
                    if debug_enabled:
                        taskdate = line.split("root", 1)[0].splitlines()[0]
                    else:
                        taskdate = line.split(": INFO ", 1)[0].splitlines()[0]
                    taskcat = line.split("Category: ", 1)[1].splitlines()[0].split(" --", 1)[0]
                    tasktype = line.split("Type: ", 1)[1].splitlines()[0].split(" --", 1)[0]
                    id = line.split("id: ", 1)[1].splitlines()[0]
                    history.append(
                        {'id': id, 'date': taskdate, 'name': taskname, 'category': taskcat, 'type': tasktype,
                         'downloaded': '', 'deleted': '', 'nzbtomedia': '', 'email': '', 'info': '', })
                elif 'Downloading:' in line:
                    history_update(history, line, 'check_name', '')
                elif 'Download finished:' in line:
                    taskinfo = line.split(" -- info: ", 1)[1].split(" -- location:", 1)[0].replace(' -- ', '\n')
                    history_update(history, line, 'downloaded', '1')
                    history_update(history, line, 'info', taskinfo)
                elif 'Deleted' in line:
                    history_update(history, line, 'deleted', '1')
                elif 'Send to nzbToMedia:' in line:
                    history_update(history, line, 'nzbtomedia', '1')
                elif 'Email send for:' in line:
                    history_update(history, line, 'email', '1')
                elif 'Category set to:' in line:
                    taskcat = line.split("Category set to: ", 1)[1].splitlines()[0]
                    history_update(history, line, 'category', taskcat)
                elif 'Download failed for:' in line:
                    history_update(history, line, 'downloaded', '0')
                elif 'Download could not be deleted from the cloud for:' in line:
                    history_update(history, line, 'deleted', '0')
                elif 'nzbToMedia failed for:' in line or 'Error unable to locate nzbToMedia.py for:' in line:
                    history_update(history, line, 'nzbtomedia', '0')
                elif 'Email error for:' in line:
                    history_update(history, line, 'email', '0')
    except:
        history = ['History is based on premiumizer.log file, error opening or it does not exist.']
    return render_template("history.html", history=history)


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
        elif 'Check for update' in request.form.values():
            if not os_arg == '--docker':
                check_update(0)
        elif 'Update Premiumizer' in request.form.values():
            gevent.spawn_later(1, update_self)
            return 'Updating, please try and refresh the page in a few seconds...'
        elif 'Update JDownloader' in request.form.values():
            try:
                cfg.jd_device.update.restart_and_update()
                flash('JDownloader update started', 'info')
                cfg.jd_update_available = 0
            except:
                logger.error('JDownloader update failed')
                flash('JDownloader update failed', 'info')
                cfg.jd_update_available = 1
        elif 'Send Test Notification' in request.form.values():
            send_notification('Test notification from Premiumizer!')
            flash('Notification sent!', 'info')
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
            if request.form.get('time_shed'):
                prem_config.set('downloads', 'time_shed', '1')
            else:
                prem_config.set('downloads', 'time_shed', '0')
            if request.form.get('download_enabled'):
                prem_config.set('downloads', 'download_enabled', '1')
            else:
                prem_config.set('downloads', 'download_enabled', '0')
            if request.form.get('download_all'):
                prem_config.set('downloads', 'download_all', '1')
            else:
                prem_config.set('downloads', 'download_all', '0')
            if request.form.get('download_rss'):
                prem_config.set('downloads', 'download_rss', '1')
            else:
                prem_config.set('downloads', 'download_rss', '0')
            if request.form.get('remove_cloud'):
                prem_config.set('downloads', 'remove_cloud', '1')
            else:
                prem_config.set('downloads', 'remove_cloud', '0')
            if request.form.get('seed_torrent'):
                prem_config.set('downloads', 'seed_torrent', '1')
            else:
                prem_config.set('downloads', 'seed_torrent', '0')
            if request.form.get('jd_enabled'):
                prem_config.set('downloads', 'jd_enabled', '1')
                prem_config.set('downloads', 'aria2_enabled', '0')
            else:
                prem_config.set('downloads', 'jd_enabled', '0')
            if request.form.get('aria2_enabled'):
                prem_config.set('downloads', 'aria2_enabled', '1')
                prem_config.set('downloads', 'jd_enabled', '0')
            else:
                prem_config.set('downloads', 'aria2_enabled', '0')
            if request.form.get('watchdir_enabled') and request.form.get('watchdir_location'):
                prem_config.set('upload', 'watchdir_enabled', '1')
                if not cfg.watchdir_enabled:
                    enable_watchdir = 1
            else:
                prem_config.set('upload', 'watchdir_enabled', '0')
            if request.form.get('watchdir_walk_enabled'):
                prem_config.set('upload', 'watchdir_walk_enabled', '1')
            else:
                prem_config.set('upload', 'watchdir_walk_enabled', '0')
            prem_config.set('upload', 'watchdir_walk_interval', request.form.get('watchdir_walk_interval'))
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
            if request.form.get('apprise_enabled'):
                prem_config.set('notifications', 'apprise_enabled', '1')
            else:
                prem_config.set('notifications', 'apprise_enabled', '0')
            if request.form.get('apprise_push_on_failure'):
                prem_config.set('notifications', 'apprise_push_on_failure', '1')
            else:
                prem_config.set('notifications', 'apprise_push_on_failure', '0')

            prem_config.set('downloads', 'jd_username', request.form.get('jd_username'))
            prem_config.set('downloads', 'jd_password', request.form.get('jd_password'))
            prem_config.set('downloads', 'jd_device_name', request.form.get('jd_device_name'))
            prem_config.set('downloads', 'aria2_host', request.form.get('aria2_host'))
            prem_config.set('downloads', 'aria2_port', request.form.get('aria2_port'))
            prem_config.set('downloads', 'aria2_secret', request.form.get('aria2_secret'))
            prem_config.set('notifications', 'email_from', request.form.get('email_from'))
            prem_config.set('notifications', 'email_to', request.form.get('email_to'))
            prem_config.set('notifications', 'email_server', request.form.get('email_server'))
            prem_config.set('notifications', 'email_port', request.form.get('email_port'))
            prem_config.set('notifications', 'email_username', request.form.get('email_username'))
            prem_config.set('notifications', 'email_password', request.form.get('email_password'))
            prem_config.set('notifications', 'apprise_url', request.form.get('apprise_url'))
            prem_config.set('global', 'server_port', request.form.get('server_port'))
            prem_config.set('global', 'bind_ip', request.form.get('bind_ip'))
            prem_config.set('global', 'reverse_proxy_path', request.form.get('reverse_proxy_path'))
            prem_config.set('global', 'custom_domain', request.form.get('custom_domain'))
            prem_config.set('global', 'idle_interval', request.form.get('idle_interval'))
            prem_config.set('security', 'username', request.form.get('username'))
            prem_config.set('security', 'password', request.form.get('password'))
            prem_config.set('premiumize', 'apikey', request.form.get('apikey'))
            prem_config.set('downloads', 'time_shed_start', request.form.get('time_shed_start'))
            prem_config.set('downloads', 'time_shed_stop', request.form.get('time_shed_stop'))
            prem_config.set('downloads', 'download_location', request.form.get('download_location'))
            prem_config.set('downloads', 'download_max', request.form.get('download_max'))
            prem_config.set('downloads', 'download_threads', request.form.get('download_threads'))
            prem_config.set('downloads', 'download_speed', request.form.get('download_speed'))
            prem_config.set('downloads', 'remove_cloud_delay', request.form.get('remove_cloud_delay'))
            prem_config.set('upload', 'watchdir_location', request.form.get('watchdir_location'))
            prem_config.set('downloads', 'nzbtomedia_location', request.form.get('nzbtomedia_location'))
            for x in range(1, 7):
                prem_config.set('categories', ('cat_name' + str([x])), request.form.get('cat_name' + str([x])))
                prem_config.set('categories', ('cat_dir' + str([x])), request.form.get('cat_dir' + str([x])))
                prem_config.set('categories', ('cat_ext' + str([x])), request.form.get('cat_ext' + str([x])))
                if request.form.get('cat_ext_blacklist' + str([x])):
                    prem_config.set('categories', ('cat_ext_blacklist' + str([x])), '1')
                else:
                    prem_config.set('categories', ('cat_ext_blacklist' + str([x])), '0')
                if request.form.get('cat_delsample' + str([x])):
                    prem_config.set('categories', ('cat_delsample' + str([x])), '1')
                else:
                    prem_config.set('categories', ('cat_delsample' + str([x])), '0')
                if request.form.get('cat_nzbtomedia' + str([x])):
                    prem_config.set('categories', ('cat_nzbtomedia' + str([x])), '1')
                else:
                    prem_config.set('categories', ('cat_nzbtomedia' + str([x])), '0')

            with open(os.path.join(ConfDir, 'settings.cfg'), 'w') as configfile:
                prem_config.write(configfile)
            logger.info('Settings saved, reloading configuration')
            cfg.check_config()
            if enable_watchdir:
                gevent.spawn_later(2, watchdir)
            flash('settings saved', 'info')
    # get_prem_folders()
    categories_amount = len(cfg.download_categories) + 1
    if categories_amount < 7:
        categories_amount = 7
    return render_template('settings.html', settings=prem_config, cfg=cfg, categories_amount=categories_amount)


def get_prem_folders():
    root = {}
    r = prem_connection("post", "https://www.premiumize.me/api/folder/list", {'apikey': cfg.prem_apikey})
    r = json.loads(r.content)
    root = {'folder_id': r['folder_id']}
    if len(r['content']):
        if any(x['type'] == 'folder' for x in r['content']):
            for x in r['content']:
                r = prem_connection("post", "https://www.premiumize.me/api/folder/list",
                                    {'apikey': cfg.prem_apikey, 'id': x['id'], 'includebreadcrumbs': 1})
                r = json.loads(r.content)
                root[r['breadcrumbs'][1]['name']] = {'folder_id': r['folder_id']}
                if len(r['content']):
                    if any(x['type'] == 'folder' for x in r['content']):
                        for x in r['content']:
                            r = prem_connection("post", "https://www.premiumize.me/api/folder/list",
                                                {'apikey': cfg.prem_apikey, 'id': x['id'], 'includebreadcrumbs': 1})
                            breadcrumbs = json.loads(r.content)['breadcrumbs']
                            r = json.loads(r.content)
                            root[breadcrumbs[1]['name']][breadcrumbs[2]['name']] = {'folder_id': r['folder_id']}
                    if len(r['content']):
                        if any(x['type'] == 'folder' for x in r['content']):
                            for x in r['content']:
                                r = prem_connection("post", "https://www.premiumize.me/api/folder/list",
                                                    {'apikey': cfg.prem_apikey, 'id': x['id'], 'includebreadcrumbs': 1})
                                breadcrumbs = json.loads(r.content)['breadcrumbs']
                                r = json.loads(r.content)
                                root[breadcrumbs[1]['name']][breadcrumbs[2]['name']][breadcrumbs[3]['name']] = {
                                    'folder_id': r['folder_id']}
                        if len(r['content']):
                            if any(x['type'] == 'folder' for x in r['content']):
                                for x in r['content']:
                                    r = prem_connection("post", "https://www.premiumize.me/api/folder/list",
                                                        {'apikey': cfg.prem_apikey, 'id': x['id'],
                                                         'includebreadcrumbs': 1})
                                    breadcrumbs = json.loads(r.content)['breadcrumbs']
                                    r = json.loads(r.content)
                                    root[breadcrumbs[1]['name']][breadcrumbs[2]['name']][breadcrumbs[3]['name']][
                                        breadcrumbs[4]['name']] = {'folder_id': r['folder_id']}


def redirect_dest(fallback):
    dest = request.args.get('next')[1:]
    try:
        dest_url = url_for(dest)
    except:
        return redirect(fallback)
    return redirect(dest_url)


@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    username = request.form['username']
    password = request.form['password']
    if username == cfg.web_username and password == cfg.web_password:
        login_user(User(username, password))
        return redirect_dest(fallback=url_for('home'))
    else:
        flash('Username or password incorrect', 'error')
        return render_template('login.html')


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
                with open(os.path.join(LogsDir, 'premiumizer.log'), 'w'):
                    pass
            except:
                pass
            try:
                with open(os.path.join(LogsDir, 'premiumizerDEBUG.log'), 'w'):
                    pass
            except:
                pass
            logger.info('Logfile Cleared')
    try:
        with open(os.path.join(LogsDir, 'premiumizer.log'), "r") as f:
            log = str(f.read())
    except:
        log = 'Error opening premiumizer.log or not available'

    try:
        with open(os.path.join(LogsDir, 'premiumizerDEBUG.log'), "r") as f:
            debuglog = str(f.read())
    except:
        debuglog = 'Error opening premiumizerDEBUG.log or not available'
    return render_template("log.html", log=log, debuglog=debuglog)


@app.route('/about')
@login_required
def about():
    return render_template("about.html")


@app.route('/list')
@login_required
def list():
    payload = {'apikey': cfg.prem_apikey}
    r = prem_connection("get", "https://www.premiumize.me/api/transfer/list", payload)
    return r.text


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static', 'img'), 'favicon.ico')


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@login_manager.user_loader
def load_user(userid):
    return User(cfg.web_username, cfg.web_password)


@socketio.on('delete_all_failed_tasks')
def delete_all_failed_tasks():
    # get all tasks based on cloud status
    failed_tasks = []
    for task in tasks:
        if task.cloud_status == 'error':
            failed_tasks.append(task)
    # delete all failed tasks
    for task in failed_tasks:
        delete_task(task.id)


@socketio.on('delete_task')
def delete_task(message):
    try:
        id = message['data']
    except:
        id = message
    task = get_task(id)
    if not task:
        socketio.emit('delete_success', {'data': id})
        scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=3)
        return
    try:
        if task.local_status != 'stopped':
            task.update(local_status='stopped')
            if cfg.download_builtin and task.local_status == 'downloading':
                gevent.sleep(8)
    except:
        pass
    if task.type == 'Filehost':
        try:
            tasks.remove(task)
            del db[task.id]
            db.sync()
            socketio.emit('delete_success', {'data': id})
            msg = 'Deleted from the database: %s' % task.name
            logger.info(msg)
        except:
            msg = 'Download could not be deleted from the database: %s' % task.name
            logger.error(msg)
            send_notification('Download could not be deleted', msg)
            socketio.emit('delete_failed', {'data': id})
    else:
        payload = {'apikey': cfg.prem_apikey, 'id': task.id}
        r = prem_connection("post", "https://www.premiumize.me/api/transfer/delete", payload)
        if 'failed' not in r:
            responsedict = json.loads(r.content)
            if responsedict['status'] == "success":
                logger.info('Deleted from the cloud: %s -- id: %s', task.name, task.id)
                socketio.emit('delete_success', {'data': id})
            else:
                msg = 'Download could not be deleted from the cloud for: %s -- id: %s -- message: %s' % (
                    task.name, task.id, responsedict['message'])
                logger.error(msg)
                send_notification('Download could not be deleted', msg)
                socketio.emit('delete_failed', {'data': id})
        else:
            logger.error('Download could not be removed from cloud: %s', task.name)
            socketio.emit('delete_failed', {'data': id})
    scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=3)


@socketio.on('pause_resume_task')
def pause_task(message):
    task = get_task(message['data'])
    if task.local_status != 'paused':
        task.update(local_status='paused', speed='--- ', eta='')
    elif task.local_status == 'paused':
        task.update(local_status='downloading')


@socketio.on('stop_task')
def stop_task(message):
    task = get_task(message['data'])
    if task.local_status != 'stopped':
        task.update(dlsize='', progress=100, local_status='stopped')


@socketio.on('connect')
def test_message():
    global client_connected
    client_connected = 1
    logger.debug('Client connected')
    emit('download_categories', {'data': cfg.download_categories})
    scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=1)


@socketio.on('disconnect')
def test_disconnect():
    global client_connected
    client_connected = 0
    logger.debug('Client disconnected')


@socketio.on('message')
def handle_message(message):
    print(('received message: ' + message))


@socketio.on('json')
def handle_json(json):
    print(('received json: ' + str(json)))


@socketio.on('change_category')
def change_category(message):
    data = message['data']
    task = get_task(data['id'])
    dldir, dlext, dlext_blacklist, delsample, dlnzbtomedia = get_cat_var(data['category'])
    if task.type == 'Filehost':
        if task.local_status != 'failed: Filehost':
            task.update(local_status=None, process=None, speed=None, category=data['category'], dldir=dldir,
                        dlext=dlext, dlext_blacklist=dlext_blacklist, delsample=delsample, dlnzbtomedia=dlnzbtomedia)
            if cfg.download_enabled:
                if task.category in cfg.download_categories:
                    if not task.local_status == ('queued' or 'downloading'):
                        task.update(local_status='queued')
                        gevent.sleep(3)
                        scheduler.scheduler.add_job(download_task, args=(task,), name=task.name, id=task.id,
                                                    misfire_grace_time=7200, coalesce=False, max_instances=1,
                                                    jobstore='downloads', executor='downloads', replace_existing=True)
    else:
        task.update(local_status=None, process=None, speed=None, category=data['category'], dldir=dldir, dlext=dlext,
                    dlext_blacklist=dlext_blacklist, delsample=delsample, dlnzbtomedia=dlnzbtomedia)
        logger.info('Task: %s -- id: %s -- Category set to: %s', task.name, task.id, task.category)
        scheduler.scheduler.reschedule_job('update', trigger='interval', seconds=1)


# start the server with the 'run()' method
logger.info('Starting server on %s:%s ', prem_config.get('global', 'bind_ip'),
            prem_config.getint('global', 'server_port'))
if __name__ == '__main__':
    signal.signal(signal.SIGINT, terminateProcess)
    signal.signal(signal.SIGTERM, terminateProcess)
    try:
        load_tasks()
        scheduler = APScheduler(GeventScheduler())
        scheduler.init_app(app)
        scheduler.scheduler.add_jobstore('memory', alias='downloads')
        scheduler.scheduler.add_jobstore('memory', alias='check_downloads')
        scheduler.scheduler.add_jobstore('memory', alias='remove_cloud')
        scheduler.scheduler.add_jobstore('memory', alias='reupload')
        scheduler.scheduler.add_executor('threadpool', alias='downloads', max_workers=cfg.download_max)
        scheduler.start()
        scheduler.scheduler.add_job(update, 'interval', id='update',
                                    seconds=active_interval, replace_existing=True, max_instances=1, coalesce=True)
        if not os_arg == '--docker':
            scheduler.scheduler.add_job(check_update, 'interval', id='check_update', seconds=1, replace_existing=True,
                                        max_instances=1, coalesce=True)
        if cfg.watchdir_enabled:
            gevent.spawn_later(2, watchdir)
        socketio.run(app, host=prem_config.get('global', 'bind_ip'), port=prem_config.getint('global', 'server_port'),
                     use_reloader=False)
    except:
        raise
