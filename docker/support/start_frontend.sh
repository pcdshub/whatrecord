#!/bin/sh
#
WHATRECORD_FRONTEND_PORT=${WHATRECORD_FRONTEND_PORT-8896}

echo "* Installing frontend dependencies..."
yarn install
echo "* Performing first build of frontend pages"
yarn build
echo "* Monitoring frontend files in the background to rebuild automatically when they update."
yarn build --watch &
echo "* Running the development server on port ${WHATRECORD_FRONTEND_PORT}."
yarn serve --port "${WHATRECORD_FRONTEND_PORT}" --host --strictPort  # --debug --logLevel debug
