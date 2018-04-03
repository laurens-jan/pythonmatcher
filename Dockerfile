FROM python:3-alpine

ARG APP_NAME=pythonmatcher

ADD ${APP_NAME} /src/${APP_NAME}
ADD requirements.txt /src
WORKDIR /src

RUN pip install -r requirements.txt

CMD [ "python", "./pythonmatcher/run.py" ]