#!/bin/sh

PROJECT_NAME="dreadfort"
PROJECT_VERSION="$(cat VERSION)"

python build.py dreadfort
fpm -d "python" -d "python-dev" -v "${PROJECT_VERSION}" -n "${PROJECT_NAME}" -t deb --after-install ./pkg/post_install.deb.sh --after-remove ./pkg/post_remove.deb.sh -s tar "./${PROJECT_NAME}_${PROJECT_VERSION}.tar.gz"
