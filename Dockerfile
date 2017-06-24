FROM python:3.6-alpine
ADD ./requirements.txt /tmp/requirements.txt
RUN apk --update add --no-cache --virtual .build-deps \
    libffi-dev \
    openssl-dev \
    build-base \
  && pip install --upgrade pip \
  && pip install -r /tmp/requirements.txt \
  && apk del .build-deps \
  && rm -rf /tmp/requirements.txt \
  && rm -rf /root/.cache
WORKDIR /srv/
CMD ["talk_bot", "run"]
