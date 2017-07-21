FROM python:3.6-alpine
ADD ./requirements.txt /tmp/requirements.txt
RUN echo "http://nl.alpinelinux.org/alpine/edge/community/" >> /etc/apk/repositories \
  && apk --update add --no-cache --virtual .build-deps \
    libffi-dev \
    openssl-dev \
    build-base \
    gfortran \
    jpeg-dev \
    lcms-dev \
    lapack-dev \
  && pip install --upgrade pip "numpy>=1.13,<1.14" \
  && pip install -r /tmp/requirements.txt \
  && apk del .build-deps \
  && rm -rf /tmp/requirements.txt \
  && rm -rf /root/.cache
WORKDIR /srv/
CMD ["talk_bot", "run"]
EXPOSE 443
