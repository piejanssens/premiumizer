FROM python:3-alpine

WORKDIR /app
COPY requirements.txt requirements.txt
COPY premiumizer .

RUN apk add --update --no-cache libffi-dev openssl-dev python3-dev py-pip build-base tzdata ffmpeg p7zip su-exec shadow libstdc++
RUN pip install --no-cache-dir -r requirements.txt

RUN addgroup -S -g 6006 premiumizer
RUN adduser -S -D -u 6006 -G premiumizer -s /bin/sh premiumizer

VOLUME /conf
EXPOSE 5000

ENTRYPOINT ["/bin/sh","docker-entrypoint.sh"]
CMD ["/usr/local/bin/python", "premiumizer.py"]
