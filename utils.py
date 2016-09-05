import ConfigParser
import os
import subprocess
import sys
import time

runningdir = os.path.split(os.path.abspath(os.path.realpath(sys.argv[0])))[0]


def restart():
    time.sleep(4)
    execfile(os.path.join(runningdir, 'premiumizer.py'), globals(), globals())


def update():
    del sys.argv[1:]
    time.sleep(2)
    subprocess.call(['git', '-C', runningdir + 'nzbtomedia', 'pull'])
    subprocess.call(['git', '-C', runningdir, 'pull'])

    prem_config = ConfigParser.RawConfigParser()
    default_config = ConfigParser.RawConfigParser()
    prem_config.read(runningdir + 'settings.cfg')
    default_config.read(runningdir + 'settings.cfg.tpl')

    if prem_config.getfloat('update', 'req_version') < default_config.getfloat('update', 'req_version'):
        import pip
        pip.main(['install', '-r', runningdir + 'requirements.txt'])
        prem_config.set('update', 'updated', '1')
        prem_config.set('update', 'req_version', (default_config.getfloat('update', 'req_version')))
        with open('settings.cfg', 'w') as configfile:
            prem_config.write(configfile)
    if prem_config.getfloat('update', 'config_version') < default_config.getfloat('update', 'config_version'):
        import shutil
        shutil.copy(runningdir + 'settings.cfg', runningdir + 'settings.cfg.old2')
        shutil.copy(runningdir + 'settings.cfg.tpl', runningdir + 'settings.cfg')
        prem_config.read(runningdir + 'settings.cfg.old2')
        default_config.read(runningdir + 'settings.cfg')
        for section in prem_config.sections():
            if section in default_config.sections():
                for key in prem_config.options(section):
                    if key in default_config.options(section):
                        default_config.set(section, key, (prem_config.get(section, key)))
        with open(runningdir + 'settings.cfg', 'w') as configfile:
            default_config.write(configfile)

    if os_arg == '--windows':
        pass
    else:
        time.sleep(3)
        execfile(os.path.join(runningdir, 'premiumizer.py'), globals(), globals())


try:
    option_arg = sys.argv[1]
except:
    sys.exit()
try:
    os_arg = sys.argv[2]
except:
    os_arg = ''
if os_arg == '--windows':
    rootdir = runningdir[:-12]

if sys.argv[1] == '--restart':
    restart()
elif sys.argv[1] == '--update':
    update()
