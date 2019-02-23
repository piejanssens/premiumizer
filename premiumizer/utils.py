from configparser import ConfigParser
import logging
import os
import subprocess
import sys
import time

try:
    from pip import main as pipmain
except:
    from pip._internal import main as pipmain

runningdir = os.path.split(os.path.abspath(os.path.realpath(sys.argv[0])))[0]
rootdir = os.path.split(runningdir)[0]

# logging
log_format = '%(asctime)-20s %(name)-41s: %(levelname)-8s : %(message)s'
logging.basicConfig(filename=os.path.join(rootdir, 'logs', 'update.log'), level=logging.DEBUG, format=log_format,
                    datefmt='%m-%d %H:%M:%S')


def uncaught_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, (SystemExit, KeyboardInterrupt)):
        return
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    pass


sys.excepthook = uncaught_exception

logging.debug('runningdir = %s', runningdir)


def restart():
    logging.debug('def restart')
    time.sleep(4)
    exec(compile(open(os.path.join(rootdir, 'premiumizer', 'premiumizer.py'), "rb").read(), os.path.join(rootdir, 'premiumizer', 'premiumizer.py'), 'exec'), globals(), globals())


def update():
    logging.debug('def restart')
    del sys.argv[1:]
    time.sleep(2)
    logging.info('Git pull nzbtomedia & premiumizer')
    subprocess.call(['git', '-C', os.path.join(rootdir, 'nzbtomedia'), 'pull'])
    subprocess.call(['git', '-C', rootdir, 'pull'])

    prem_config = ConfigParser()
    default_config = ConfigParser()
    prem_config.read(os.path.join(rootdir, 'conf', 'settings.cfg'))
    default_config.read(os.path.join(rootdir, 'conf', 'settings.cfg.tpl'))

    prem_config.set('update', 'updated', '1')
    with open(os.path.join(rootdir, 'conf', 'settings.cfg'), 'w') as configfile:
        prem_config.write(configfile)
    if prem_config.getfloat('update', 'req_version') < default_config.getfloat('update', 'req_version'):
        logging.info('updating pip requirements')
        pipmain(['install', '-r', os.path.join(rootdir, 'requirements.txt')])
        prem_config.set('update', 'req_version', str(default_config.getfloat('update', 'req_version')))
        with open(os.path.join(rootdir, 'conf', 'settings.cfg'), 'w') as configfile:
            prem_config.write(configfile)
    if prem_config.getfloat('update', 'config_version') < default_config.getfloat('update', 'config_version'):
        logging.info('updating config file')
        import shutil
        shutil.copy(os.path.join(rootdir, 'conf', 'settings.cfg'), os.path.join(rootdir, 'conf', 'settings.cfg.old'))
        shutil.copy(os.path.join(rootdir, 'conf', 'settings.cfg.tpl'), os.path.join(rootdir, 'conf', 'settings.cfg'))
        prem_config.read(os.path.join(rootdir, 'conf', 'settings.cfg.old'))
        default_config.read(os.path.join(rootdir, 'conf', 'settings.cfg'))
        for section in prem_config.sections():
            if section in default_config.sections() and section != 'update':
                for key in prem_config.options(section):
                    if key in default_config.options(section):
                        default_config.set(section, key, (prem_config.get(section, key)))
        with open(os.path.join(rootdir, 'conf', 'settings.cfg'), 'w') as configfile:
            default_config.write(configfile)

    if os_arg == '--windows':
        pass
    else:
        time.sleep(3)
        exec(compile(open(os.path.join(rootdir, 'premiumizer', 'premiumizer.py'), "rb").read(), os.path.join(rootdir, 'premiumizer', 'premiumizer.py'), 'exec'), globals(), globals())


if len(sys.argv) == 3:
    option_arg = sys.argv[1]
    os_arg = sys.argv[2]
    if os_arg == '--windows':
        rootdir = runningdir[:-12]
    else:
        os_arg = ''
    if option_arg == '--restart':
        restart()
    elif option_arg == '--update':
        update()
else:
    sys.exit()
