# syntax=docker/dockerfile:1.4
# vi: syntax=Dockerfile

FROM python:3.10.7-bullseye

RUN apt-get -y update && \
    apt-get -y install build-essential graphviz gdb && \
    apt-get clean

ARG SDIST
ARG PIP_EXTRAS

WORKDIR /root

COPY . /usr/local/src/whatrecord
RUN pip install /usr/local/src/whatrecord ${PIP_EXTRAS}

WORKDIR /ioc

RUN echo 'whatrecord parse iocBoot/ioc-*/st.cmd' >> ~/.bash_history
RUN echo 'whatrecord lint iocBoot/ioc-*/st.cmd' >> ~/.bash_history
RUN echo "pytest -v $(python -c 'import os, whatrecord; print(os.path.dirname(whatrecord.__file__))')" >> ~/.bash_history

CMD ["whatrecord", "--help"]
