#!/bin/bash
# Note: this is meant to be run from docker via docker-compose and not on its
# own.

[ -z ${API_PORT} ] && echo "API port unset?" && exit 1;

echo Cache contents:
ls -la /var/lib/whatrecord/cache

echo Startup scripts to use:
ls -la /usr/local/src/whatrecord/whatrecord/tests/iocs/*/st.cmd

echo Running API server on port ${API_PORT}...
whatrecord server \
  --port=${API_PORT} \
  --gateway-config=/usr/share/whatrecord/support/gateway/ \
  --scripts /usr/local/src/whatrecord/whatrecord/tests/iocs/*/st.cmd
