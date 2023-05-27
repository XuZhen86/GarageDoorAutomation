FROM python:3.11.3

WORKDIR /app
ADD . /app
RUN pip3 install --use-pep517 .
