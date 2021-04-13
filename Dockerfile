FROM python:3.7-alpine as base
FROM base as builder

RUN mkdir /install
WORKDIR /install
COPY requirements.txt ./premiumizer /install/

RUN apk add --update --no-cache libffi-dev openssl-dev python3-dev py-pip build-base tzdata
RUN pip install --no-cache-dir --prefix /install -r requirements.txt

FROM base

RUN apk add --update --no-cache su-exec shadow libstdc++ \
	&& addgroup -S -g 6006 premiumizer \
	&& adduser -S -D -u 6006 -G premiumizer -s /bin/sh premiumizer

COPY --from=builder /install /usr/local
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo
COPY premiumizer /app

WORKDIR /app
VOLUME /conf
EXPOSE 5000

ENTRYPOINT ["/bin/sh","/app/docker-entrypoint.sh"]
CMD ["/usr/local/bin/python", "/app/premiumizer.py"]
