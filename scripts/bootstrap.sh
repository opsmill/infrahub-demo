#!/bin/bash
BRANCH=${1:-main}

echo "Load schemas"
uv run infrahubctl schema load schemas --branch $BRANCH

echo "Load menu"
uv run infrahubctl menu load menu --branch $BRANCH

echo "Load initial data"
uv run infrahubctl object load objects/bootstrap/ --branch $BRANCH

echo "Load security data"
uv run infrahubctl object load objects/security/ --branch $BRANCH

# echo "Add demo repository"
# uv run infrahubctl repository add DEMO https://github.com/opsmill/infrahub-demo.git --ref main --read-only

echo "Add event actions"
sleep 30
uv run infrahubctl object load objects/events/ --branch $BRANCH

