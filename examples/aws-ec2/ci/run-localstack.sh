#!/bin/bash
set -eu

LOCALSTACK_VERSION=3.1

SCRIPTDIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
cd "$SCRIPTDIR"

if command -v podman; then
  CONTAINER=podman
else
  CONTAINER=docker
fi

$CONTAINER run --rm --name localstack -p 4566:4566 \
  -e SERVICES=ec2,iam,sts \
  -v ./patch-entrypoint.sh:/usr/local/bin/patch-entrypoint.sh:ro,z \
  --entrypoint patch-entrypoint.sh "$@" localstack/localstack:$LOCALSTACK_VERSION
