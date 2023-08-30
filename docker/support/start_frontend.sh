#!/bin/sh
#
WHATRECORD_FRONTEND_PORT=${WHATRECORD_FRONTEND_PORT-8896}
WHATRECORD_FRONTEND_MODE=${WHATRECORD_FRONTEND_MODE-development}

echo "* Installing frontend dependencies..."
yarn install
yarn build

if [ $WHATRECORD_FRONTEND_MODE == "development" ]; then
  echo "* Running the development server on port ${WHATRECORD_FRONTEND_PORT}."
  yarn dev --port "${WHATRECORD_FRONTEND_PORT}" --host --mode="${WHATRECORD_FRONTEND_MODE}"
else
  yarn build --mode="${WHATRECORD_FRONTEND_MODE}"
  yarn serve --port "${WHATRECORD_FRONTEND_PORT}" --host --strictPort --mode="${WHATRECORD_FRONTEND_MODE}"
fi
