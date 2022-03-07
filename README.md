# Premiumizer

![Docker Cloud Build Status](https://img.shields.io/docker/cloud/build/piejanssens/premiumizer) ![GitHub contributors](https://img.shields.io/github/contributors/piejanssens/premiumizer)

Premiumizer is a download management tool for premiumize.me cloud downloads, which allows automatic downloading to your personal computer/server.

- Web interface to manage premiumize.me downloads: cloud Torrent & Nzb and Filehosts links
- Category based automatic downloader of finished cloud tasks to local file system
- Picks up new taks through black hole
- Integrates with nzbToMedia (post processing)

Enjoying it so far? Great! If you want to show your appreciation, feel free to:

<a href="https://ko-fi.com/M4M7694D5"><img src="https://uploads-ssl.webflow.com/5c14e387dab576fe667689cf/5cbed8a4ae2b88347c06c923_BuyMeACoffee_blue-p-500.png" width="250px"></a>

## About premiumize.me

Premiumize.me combines anonymous cloud torrent downloads, usenet and premium hosters in one subscription. Cloud torrent downloads are cached, meaning if some other premiumize.me member downloaded the torrent through premiumize.me before, you can immediately download the files from that torrent over HTTPS at top speeds.

Get your account [right here](https://www.premiumize.me/ref/198754075).

## How does it work?

Premiumizer will monitor download tasks on premiumize.me.
Once the download in the cloud finishes and the download task has a category that needs to be automatically downloaded premiumizer will start downloading all the files to your local computer where premiumizer is running. Download tasks without a category will not be automatically downloaded locally. Categories can be setup through the web interface's setup page.

When enabled, premiumizer can inform nzbToMedia whenever the local download is finished.

## Web Interface

By default, premiumizer's web interface listens on port 5000.
When premiumizer is running you can access it at http://localhost:5000/

## Installation using Docker

We have provide images for `amd64` & `arm64v8`. If you have a different architecture, you can build this yourself using our Dockerfile.

You need to set the correct PUID and PGID equal to the user that has rw access to the mounted volumes.

```shell
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

### Synology DSM

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
11. Set the following environment variables:

- PUID (see step 3.)
- PGID (see step 3.)
- TZ (e.g. Europe/London)

#### Updating images on Synology

1. Stop the container
2. Right click the container: Action -> Clear/Rest
3. Under 'Registry': Download the piejanssens/premiumizer image (this will pull in the latest image)
4. Start the container

## Windows Installer

[PremiumizerInstaller](https://github.com/neox387/PremiumizerInstaller/releases)

Open services.msc & edit Premiumizer service to logon using your account that is an administrator.

## Manual Installation

Required: Git & Python 3 (with pip)

### Windows

```shell
git clone https://github.com/piejanssens/premiumizer.git C:\Premiumizer
python -m pip install --upgrade pip
python -m pip install -pywin32
python -m pip install -r c:\Premiumizer\requirements.txt
python C:\Premiumizer\premiumizer\premiumizer.py
```

### Unix / macOS

```shell
$ brew install python3
$ git clone https://github.com/piejanssens/premiumizer.git premiumizer
$ cd premiumizer
$ pip install -r requirements.txt
$ python premiumizer/premiumizer.py
```

## Updating

Update from the settings page / enable automatic updates
Update button & changes will be displayed when an update is available.

## Settings

Once you can access the premiumizer web interface make sure you head over to the settings page.

## Development

Want to contribute? Great!
Just fork the github repo, do some awesome stuff and create a pull request.

Report issues or feature enhancements/requests on the [Issues](https://github.com/piejanssens/premiumizer/issues) page
