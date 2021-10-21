# Server / client

### Starting the backend API server

With the provided test-suite IOCs:

```bash
$ whatrecord server --scripts whatrecord/tests/iocs/*/st.cmd
```

Gateway configuration among others can be specified separately, if available.

### Starting the frontend

Install dependencies:
```bash
$ conda install -c conda-forge nodejs
$ cd frontend
$ yarn install
```

Compile and reload automatically when frontend files change:
```bash
$ yarn serve
```

Or alternatively compile and minify for production:
```
$ yarn build
```

### Tweaking frontend settings

In ``frontend/.env.local``:

```bash
API_HOST=localhost
API_PORT=8898
FRONTEND_PORT=8899
WHATRECORD_PLUGINS=happi twincat_pytmc

# The following is accessible in the vue frontend:
VUE_APP_WHATRECORD_PLUGINS=$WHATRECORD_PLUGINS
```

## General flow

Using the core tools:
* Load up all EPICS IOCs listed in IOC manager
    - Load the startup scripts
    - Load all the databases and supported files
* Provide a backend service for querying the information
* Based on the backend server, provide a frontend for easy access to that information
    - vue.js-based frontend single-page application
    - Search for records/IOCs/etc by name and dig into the details...


## API

::: whatrecord.ioc_finder
::: whatrecord.client
::: whatrecord.server
::: whatrecord.server.common
::: whatrecord.server.server
::: whatrecord.server.util
