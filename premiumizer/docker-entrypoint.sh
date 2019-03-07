#!/usr/bin/env sh

PUID=${PUID:-6006}
PGID=${PGID:-6006}

groupmod -o -g "$PGID" premiumizer
usermod -o -u "$PUID" premiumizer

ln -sf ./premiumizer/conf /conf

su - premiumizer -p -c 'python ./premiumizer/premiumizer.py'
