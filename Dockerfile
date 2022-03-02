FROM python:3-alpine

RUN apk add --update --no-cache libffi-dev openssl-dev python3-dev py-pip build-base tzdata ffmpeg unrar p7zip su-exec shadow libstdc++
RUN pip install --no-cache-dir --prefix /install -r requirements.txt

RUN mkdir /install
WORKDIR /install
COPY requirements.txt ./premiumizer /install/

RUN addgroup -S -g 6006 premiumizer
RUN adduser -S -D -u 6006 -G premiumizer -s /bin/sh premiumizer

COPY /install /usr/local
COPY /usr/share/zoneinfo /usr/share/zoneinfo
COPY premiumizer /app

WORKDIR /app
VOLUME /conf
EXPOSE 5000

ENTRYPOINT ["/bin/sh","/app/docker-entrypoint.sh"]
CMD ["/usr/local/bin/python", "/app/premiumizer.py"]
