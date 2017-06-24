FROM python:3.6-alpine
ADD . /tmp/src
RUN apk --update add --no-cache --virtual .build-deps \
    libffi-dev \
    openssl-dev \
    build-base \
  && pip install --upgrade pip \
  && pip install /tmp/src/dist/talkbot-0.0.1.tar.gz \
  && apk del .build-deps \
  && rm -rf /tmp/src \
  && rm -rf /root/.cache
WORKDIR /srv/
CMD ["talk_bot", "run"]
