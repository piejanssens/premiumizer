# Premiumizer

Premiumizer is a download management tool for premiumize.me cloud downloads.

  - Web interface to manage premiumize.me downloads: cloud Torrent & Nzb and Filehosts links
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
When premiumizer is running you can access it at http://127.0.0.1:5000/ 
If premiumizer is running on a different PC replace Bind ip in settings with that computer's IP.

Support for reverse proxy:
nginx example:
```
...
##PREMIUMIZER
    location /premiumizer {
        proxy_pass http://'ip':port;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Script-Name /premiumizer;

    }

    location /socket.io {
        proxy_pass http://'ip'/socket.io;
        proxy_redirect off;
        proxy_buffering off;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
...
```

## Installation

### Requirements
Git & Python 2.7 (with pip)

Optional: 

[virtualenv](https://pypi.python.org/pypi/virtualenv)

[NzbToMedia](https://github.com/clinton-hall/nzbToMedia) version 10.14 & higher


### Synology
Package coming soon(ish).

### Windows
Automatic installation:

Use the [PremiumizerInstaller](https://github.com/neox387/PremiumizerInstaller/releases)

Open services.msc & edit Premiumizer service to logon using your account that is an administrator.

Edit autoProcessMedia.cfg.spc & save it to autoProcessMedia.cfg


Manual installation:

Install [Git](https://git-scm.com/download/win) &  select: Use git from the windows command prompt.

Download [Python](https://www.python.org/ftp/python/2.7.11/python-2.7.11.msi)

1. ```git clonehttps://github.com/piejanssens/premiumizer.git [to a folder]```
2. ```pip.exe install virtualenv```
3. ```virtualenv [your folder]\env```
4. ```env\Scripts\activate.bat```
5. ```pip install -r requirements.txt```
6. ```python premiumizer.py```

Optional:
Install NzbToMedia & pywin32 & Microsoft Visual c++ python compiler:

4. ```git clone https://github.com/clinton-hall/nzbToMedia.git [your folder]\nzbtomedia```
5. ```easy_install pywin32```


### OS X
Install [brew](http://brew.sh/), use brew to install python

1. ```git clone https://github.com/piejanssens/premiumizer.git```
2. ```cd premiumizer```
3. ```virtualenv virtualenv```
4. ```source virtualenv/bin/activate```
5. ```pip install -r requirements.txt```
6. ```./premiumizer.py```

Now use your browser to access [http://127.0.0.1:5000/](http://127.0.0.1:5000/)

Extra: Google how you can turn it into a service and run it in background

### Docker
Build the image and run the container:
1. ```git clone https://github.com/piejanssens/premiumizer.git```
2. ```cd premiumizer```
3. ```docker build -t REPO/TAG . ```
4. ```docker run -d -p 5000:5000 -e TZ=Europe/London -e PUID=1000 -e PGID=1000 -v <host_path>:/premiumizer/conf -v <host_path>:/blackhole -v <host_path>:/downloads REPO/TAG```
Manually setting PUID and PGID might be necessary for the bind-mounts (depends on your permission setup).

## Updating
Update from the settings page / enable automatic updates
Update button & changes will be displayed when an update is available.


## Settings
Once you can access the premiumizer web interface make sure you head over to the settings page.

## Development
Want to contribute? Great!
Just fork the github repo, do some awesome stuff and create a pull request.

Report issues or feature enhancements/requests on the [Issues](https://github.com/piejanssens/premiumizer/issues) page