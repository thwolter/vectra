FROM ubuntu:latest
LABEL authors="thomas"

ENTRYPOINT ["top", "-b"]
