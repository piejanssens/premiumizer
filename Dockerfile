FROM python:2.7
COPY requirements.txt /premiumizer/
RUN find /usr/local/lib/python2.7/site-packages -mindepth 1 -maxdepth 1 > /filelist \
    && pip install -r premiumizer/requirements.txt \
    && xargs rm -rf < /filelist

FROM python:2.7-alpine
RUN addgroup -S -g 6006 premiumizer \
    && adduser -S -D -u 6006 -G premiumizer premiumizer \
    && mkdir -m 777 /premiumizer \
    && chown -R 6006:6006 /premiumizer
USER premiumizer
COPY --chown=premiumizer:premiumizer --from=0 /usr/local/lib/python2.7/site-packages /usr/local/lib/python2.7/site-packages/ 
COPY --chown=premiumizer:premiumizer . /premiumizer/
WORKDIR /premiumizer
EXPOSE 5000
ENTRYPOINT ["python", "premiumizer.py"]
