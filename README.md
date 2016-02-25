# Premiumizer

Premiumizer is a download management tool for premiumize.me cloud downloads.

  - Web interface to manage premiumize.me cloud downloads
  - Category based automatic downloader of finished cloud tasks to local file system
  - Integrates with SickRage, CouchPotato, ... (BlackHole)
  - Integrates with nzbToMedia (post processing)

## About premiumize.me
Premiumize.me combines anonymous cloud torrent downloads, usenet and premium hosters in one subscription. Cloud torrent downloads are cached, meaning if some other premiumize.me member downloaded the torrent through premiumize.me before, you can immediately download the files from that torrent over HTTPS at top speeds.

More info and get your account [right here](https://www.premiumize.me/ref/198754075).

## How does this thing work?
This tool will monitor your download tasks on premiumize.me.
Once the download in the cloud finishes and the download task has a category that needs to be automatically downloaded premiumizer will start downloading all the files to your local premiumizer server. Download tasks without a category will not be automatically downloaded to the local server. 
You can add/change a category whilst it's downloading through the web interface, but third party tools like CouchPotato and SickRage will automatically submit download tasks with a specific category. 

When enabled, premiumizer can inform nzbToMedia whenever the local download is finished.
Categories can be setup through the web interface's setup page.

## Web Interface
By default, premiumizer's web interface listens on port 5000.
When premiumizer is running you can access it at http://localhost:5000/ 
If premiumizer is running on a different PC replace localhost with that computer's IP.

## Installation
### Synology
Package coming soon(ish).

### Windows, Linux, OS X

Requirement: git, Python 2.7 (with pip+virtualenv)

Windows:

Installation:


Download premiumizer unzip/rename to c:\premiumizer
```
https://github.com/piejanssens/premiumizer/archive/master.zip
```

Download python 2.7.11 install to default location: C:\python27
```
https://www.python.org/ftp/python/2.7.11/python-2.7.11.msi
```


Open command prompt (winkey + R, type cmd) & input:
```
C:\Python27\Scripts\pip.exe install virtualenv
C:\Python27\Scripts\virtualenv.exe c:\premiumizer\env
C:\premiumizer\env\Scripts\activate.bat
pip install -r C:\premiumizer\requirements.txt
```

Running:
Open command prompt or create .bat file:
```
c:\premiumizer\env\Scripts\activate.bat
cd C:\premiumizer
python premiumizer.py
```

OS X: Install [brew](http://brew.sh/), use brew to install python

1. ```git clone
https://github.com/piejanssens/premiumizer.git```
2. ```cd premiumizer```
3. ```virtualenv virtualenv```
4. ```source virtualenv/bin/activate```
5. ```pip install requirements.txt```
6. ```./premiumizer.py```

Now use your browser to access [http://localhost:5000/](http://localhost:5000/).
Extra: Google how you can turn it into a service and run it in background

## Updating
There is no automatic updater in place yet. You need to "git pull" the latest changes.

## Settings
Once you can access the premiumizer web interface make sure you head over to the settings page.

## Development
Want to contribute? Great!
Just fork the github repo, do some awesome stuff and create a pull request.
