FROM: python:3.6-alpine
RUN pip install dist/talkbot-0.0.1.tar.gz
CMD ["talk_bot", "run"]
