FROM python:3.7-alpine as base

FROM base as builder

RUN mkdir /install
WORKDIR /install

COPY requirements.txt ./premiumizer /install/

RUN apk add --update --virtual build-dependencies libffi-dev openssl-dev python-dev py-pip build-base
RUN pip install --prefix /install -r requirements.txt

FROM base

COPY --from=builder /install /usr/local
COPY premiumizer /app

WORKDIR /app

EXPOSE 5000
CMD ["python", "/app/premiumizer.py"]
