# whatrecord

## Installing

```
$ pip install whatrecord
```

## Starting the server

### Starting the backend API server

With the provided test-suite IOCs:

```
$ whatrecord server --scripts whatrecord/tests/iocs/*/st.cmd
```

Gateway configuration among others can be specified separately, if available.

### Starting the frontend

Install dependencies:
```
$ conda install -c conda-forge nodejs
$ cd frontend
$ yarn install
```

Compile and hot-reloads for development:
```
$ yarn serve
```

### Tweaking frontend settings

In ``frontend/.env.local``:

```
API_HOST=localhost
API_PORT=8898
FRONTEND_PORT=8899
WHATRECORD_PLUGINS=happi twincat_pytmc

# The following is accessible in the vue frontend:
VUE_APP_WHATRECORD_PLUGINS=$WHATRECORD_PLUGINS
```
