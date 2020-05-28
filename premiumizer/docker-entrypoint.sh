#!/usr/bin/env sh

PUID=${PUID:-6006}
PGID=${PGID:-6006}

groupmod -o -g "$PGID" premiumizer || true
usermod -o -u "$PUID" premiumizer || true

chown -R premiumizer:premiumizer /conf || true

exec su-exec premiumizer "$@"
