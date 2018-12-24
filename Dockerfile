FROM python:2.7
COPY requirements.txt /premiumizer/
RUN find /usr/local/lib/python2.7/site-packages -mindepth 1 -maxdepth 1 > /filelist \
    && pip install -r premiumizer/requirements.txt \
    && xargs rm -rf < /filelist \
    && apt-get install tzdata

FROM python:2.7-alpine
RUN apk --no-cache add shadow \
    && addgroup -S -g 6006 premiumizer \
    && adduser -S -D -u 6006 -G premiumizer -s /bin/sh premiumizer
COPY --from=0 /usr/local/lib/python2.7/site-packages /usr/local/lib/python2.7/site-packages/
COPY --from=0 /usr/share/zoneinfo /usr/share/zoneinfo/
COPY . /premiumizer/
RUN chmod -R 777 /premiumizer && sed -i "s/127.0.0.1/0.0.0.0/g" premiumizer/settings.cfg.tpl
WORKDIR /premiumizer
EXPOSE 5000
ENTRYPOINT ["./docker-entrypoint.sh"]
