# Premiumizer

Premiumizer is a download management tool for premiumize.me cloud downloads.

  - Web interface to manage premiumize.me downloads: cloud Torrent & Nzb and Filehosts links
  - Category based automatic downloader of finished cloud tasks to local file system
  - Picks up new taks through black hole
  - Integrates with nzbToMedia (post processing)

## About premiumize.me
Premiumize.me combines anonymous cloud torrent downloads, usenet and premium hosters in one subscription. Cloud torrent downloads are cached, meaning if some other premiumize.me member downloaded the torrent through premiumize.me before, you can immediately download the files from that torrent over HTTPS at top speeds.

Get your account [right here](https://www.premiumize.me/ref/198754075).

## How does this thing work?
This tool will monitor your download tasks on premiumize.me.
Once the download in the cloud finishes and the download task has a category that needs to be automatically downloaded premiumizer will start downloading all the files to your local premiumizer server. Download tasks without a category will not be automatically downloaded to the local server. 
You can add/change a category whilst it's downloading through the web interface, but third party tools like CouchPotato and SickRage will automatically submit download tasks with a specific category. 

When enabled, premiumizer can inform nzbToMedia whenever the local download is finished.
Categories can be setup through the web interface's setup page.

## Web Interface
By default, premiumizer's web interface listens on port 5000.
When premiumizer is running you can access it at http://localhost:5000/ 

## Installation

### Requirements
Required: Git & Python 3 (with pip)
Optional: [virtualenv](https://pypi.python.org/pypi/virtualenv) & [NzbToMedia](https://github.com/clinton-hall/nzbToMedia) version 10.14+

### Synology
Follow Docker instructions.

### Windows
#### Installer
[PremiumizerInstaller](https://github.com/neox387/PremiumizerInstaller/releases)

Open services.msc & edit Premiumizer service to logon using your account that is an administrator.

#### Manual

1. Install [Git](https://git-scm.com/download/win)
2. Install [Python](https://www.python.org/downloads/) Check Add Python to PATH
3. WIN+R cmd
```
git clone https://github.com/piejanssens/premiumizer.git C:\Premiumizer
python -m pip install --upgrade pip
python -m pip install -r c:\Premiumizer\requirements.txt
python C:\Premiumizer\premiumizer\premiumizer.py
```

### Unix / macOS

1. Install Python 3 (e.g. using [brew](http://brew.sh/))
2. Open Terminal
```
$ brew install python3
$ git clone https://github.com/piejanssens/premiumizer.git premiumizer
$ cd premiumizer
$ pip install virtualenv
$ virtualenv -p /usr/local/bin/python3 env
$ source env/bin/activate
$ pip install -r requirements.txt
$ python premiumizer/premiumizer.py
```

### Docker

### Supported Architectures
Based on [this](https://github.com/cgiraldo/docker-hello-multiarch) approach, we support `amd64`, `arm32v7` & `arm64v8`.

Our image has a multiarch manifest, so by pulling `piejanssens/premiumizer:latest` it should retrieve the correct image for your arch, but you can also pull specific arch via tags.

| Architecture | Tag |
| :----: | --- |
| x86-64 | amd64 |
| arm64 | arm64v8 |
| armhf | arm32v7 |

#### General
You need to set the correct PUID and PGID equal to the user that has rw access to the mounted volumes.

##### Command line
```
docker run \
  --name premiumizer \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Europe/London \
  -p 5000:5000 \
  -v /path/to/conf:/conf \
  -v /path/to/blackhole:/blackhole \
  -v /path/to/downloads:/downloads \
  --restart unless-stopped \
  piejanssens/premiumizer
```
##### docker-compose
```
---
version: "3.6"
services:
  premiumizer:
    image: piejanssens/premiumizer
    container_name: premiumizer
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/London
    volumes:
      - /path/to/conf:/conf
      - /path/to/blackhole:/blackhole
      - /path/to/downloads:/downloads
    ports:
      - 5000:5000
    restart: unless-stopped
```

#### Synology DSM
1. Create a folder using File Station where Premiumizer can store its config and logs (e.g. /volume1/docker/premiumizer)
2. Identify (or create) the locations for blackhole and downloads that Premiumizer will use
3. SSH into your syno and figure out the PUID and PGID of the user that has access to these folders
4. Open Docker app
5. Under 'Registry': Download the piejanssens/premiumizer image
6. Under 'Image': Select the image and click 'launch'
7. Map a port of your chosing to '5000' (e.g. Chosing 5555 to 5000, means your Premiumizer will be accessible through 5555)
8. Map your blackhole folder to '/blackhole'
9. Map your downloads folder to '/downloads'
10. Map your premiumizer conf folder to '/conf'
11. Set the following environment variables
-- PUID (see step 3.)
-- PGID (see step 3.)
-- TZ (e.g. Europe/London)

##### Updating
1. Under 'Container': Stop the container
2. Under 'Container': Action -> Clear
2. Under 'Registry': Download the piejanssens/premiumizer image (this will pull in the latest image)
3. Under 'Container': Start the container 

## Updating
Update from the settings page / enable automatic updates
Update button & changes will be displayed when an update is available.

## Settings
Once you can access the premiumizer web interface make sure you head over to the settings page.

## Development
Want to contribute? Great!
Just fork the github repo, do some awesome stuff and create a pull request.

Report issues or feature enhancements/requests on the [Issues](https://github.com/piejanssens/premiumizer/issues) page
