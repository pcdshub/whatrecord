# syntax=docker/dockerfile:1.4
# vi: syntax=Dockerfile

FROM python:3.10.7-bullseye

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get -y update && \
    apt-get -y install build-essential graphviz gdb libldap2-dev libsasl2-dev && \
    apt-get clean

ARG SDIST
ARG PIP_EXTRAS

WORKDIR /root

COPY . /usr/local/src/whatrecord
RUN pip install /usr/local/src/whatrecord -r /usr/local/src/whatrecord/dev-requirements.txt ${PIP_EXTRAS}

# Hack - we don't include this in the package because it's big:
RUN cp -r /usr/local/src/whatrecord/whatrecord/tests/blark_root /usr/local/lib/python3.10/site-packages/whatrecord/tests/

WORKDIR /ioc

RUN echo 'whatrecord parse iocBoot/ioc-*/st.cmd' >> ~/.bash_history
RUN echo 'whatrecord lint iocBoot/ioc-*/st.cmd' >> ~/.bash_history
RUN echo "pytest -v --pyargs whatrecord" >> ~/.bash_history

CMD ["whatrecord", "--help"]
