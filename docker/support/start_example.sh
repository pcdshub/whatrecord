#!/bin/bash
# Note: this is meant to be run from docker via docker-compose and not on its
# own.

[ -z ${WHATRECORD_API_PORT} ] && echo "API port unset?" && exit 1;

echo Installing dev whatrecord from your source tree...

if [ -d /usr/local/src/dev-whatrecord ]; then
  cd /usr/local/src/dev-whatrecord
  pip install .
fi

echo Cache contents:
ls -la /var/lib/whatrecord/cache

echo Startup scripts to use:
STARTUP_SCRIPTS=${STARTUP_SCRIPTS-/usr/local/src/whatrecord/whatrecord/tests/iocs/*/st.cmd}

ls -la ${STARTUP_SCRIPTS}

echo Running API server on port ${WHATRECORD_API_PORT}...
whatrecord server \
  --port=${WHATRECORD_API_PORT} \
  --gateway-config=/usr/share/whatrecord/support/gateway/ \
  --scripts ${STARTUP_SCRIPTS}
