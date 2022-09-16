# What is this?

This directory contains a Dockerfile for standing up an example whatrecord
instance easily.

The docker-compose configuration starts up both a backend server and a frontend
server.  It is set to index the whatrecord package-provided test suite IOCs.

After building the image, you can run whatrecord directly (see below) to
parse or lint single files / IOCs / etc.

## Docker-compose usage

```bash
$ docker-compose up
```

Then open a browser to http://localhost:8896/

### Frontend server

Start the frontend alone by way of:

```bash
$ docker-compose up whatrecord-frontend
```

This won't be usable without the backend server, though.

### Backend server

Start the backend server example alone by way of:

```bash
$ docker-compose up whatrecord
```

### Clearing the cache

```bash
$ docker-compose down --volumes
```

## Standalone docker image

The standalone docker image can be used after building it via docker-compose.
The following would build the image and then run the internal test suite:

```bash
$ make build-image run-tests
```

### Exploring the image

This will open up a bash session for you to browse the image.

```bash
$ make inspect
```

### Parsing / linting tools

```bash
$ make
# Go to an IOC directory and:
$ docker run -v ${PWD}:/ioc -it pcdshub/whatrecord:latest whatrecord parse iocBoot/ioc-*/st.cmd
```
