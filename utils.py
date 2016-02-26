import sys, os, time, ConfigParser

def restart():
    time.sleep(2)
    execfile('premiumizer.py', globals(), globals())
    
def update():
    del sys.argv[1:]
    time.sleep(2)
    from PyGitUp import gitup
    gitup.run()
    prem_config = ConfigParser.RawConfigParser()
    default_config = ConfigParser.RawConfigParser()
    runningdir = os.path.split(os.path.abspath(os.path.realpath(sys.argv[0])))[0] + '/'
    prem_config.read(runningdir+'settings.cfg')
    default_config.read(runningdir+'settings.cfg.tpl')

    if prem_config.getfloat('update', 'req_version') < default_config.getfloat('update', 'req_version'):
        import pip
        pip.main(['install', '-r', runningdir+'requirements.txt'])
        prem_config.set('update', 'updated', 1)
        with open('settings.cfg', 'w') as configfile:
            prem_config.write(configfile)
    if prem_config.getfloat('update', 'config_version') < default_config.getfloat('update', 'config_version'):
        import shutil
        os.rename(runningdir+'settings.cfg', runningdir+'settings.cfg.old')
        shutil.copy(runningdir+'settings.cfg.tpl', runningdir+'settings.cfg')
    execfile('premiumizer.py', globals(), globals())

    

arg = sys.argv[1:]

if arg == ['--restart']:
    restart()
elif arg == ['--update']:
    update()


