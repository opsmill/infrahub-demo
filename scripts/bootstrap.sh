#!/bin/bash
BRANCH=${1:-main}
INFRAHUB_ADDRESS=${INFRAHUB_ADDRESS:-http://localhost:8000}

echo ""
echo "============================================================"
echo "  Infrahub Demo Bootstrap"
echo "============================================================"
echo "  Branch: $BRANCH"
echo "============================================================"
echo ""

# Check if Infrahub is ready
echo "Checking if Infrahub is ready..."
MAX_RETRIES=30
RETRY_COUNT=0
SLEEP_TIME=2

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s -f -o /dev/null "${INFRAHUB_ADDRESS}/api/schema"; then
        echo "✓ Infrahub is ready!"
        echo ""
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        echo ""
        echo "✗ ERROR: Infrahub is not responding after ${MAX_RETRIES} attempts"
        echo "  Please ensure Infrahub is running with: uv run invoke start"
        echo "  Check container status with: docker ps"
        echo ""
        exit 1
    fi

    echo -n "."
    sleep $SLEEP_TIME
done

echo "[1/7] Loading schemas..."
uv run infrahubctl schema load schemas --branch $BRANCH
echo "✓ Schemas loaded successfully"
echo ""

echo "[2/7] Loading menu definitions..."
uv run infrahubctl menu load menu --branch $BRANCH
echo "✓ Menu loaded successfully"
echo ""

echo "[3/7] Loading bootstrap data (locations, platforms, roles, etc.)..."
uv run infrahubctl object load objects/bootstrap/ --branch $BRANCH
echo "✓ Bootstrap data loaded successfully"
echo ""

echo "[4/7] Loading security data (zones, policies, rules)..."
uv run infrahubctl object load objects/security/ --branch $BRANCH
echo "✓ Security data loaded successfully"
echo ""

echo "[5/7] Populating security relationships..."
uv run python scripts/populate_security_relationships.py
echo "✓ Security relationships populated successfully"
echo ""

echo "[6/7] Adding demo repository..."
uv run infrahubctl repository add DEMO https://github.com/opsmill/infrahub-demo.git --ref main --read-only --ref main || echo "⚠ Repository already exists, skipping..."
echo "✓ Repository added"
echo ""

echo "[7/7] Waiting for repository sync (120 seconds)..."
for i in {1..12}; do
    echo -n "."
    sleep 10
done
echo ""
echo "✓ Repository sync complete"
echo ""

echo "Loading event actions..."
uv run infrahubctl object load objects/events/ --branch $BRANCH
echo "✓ Event actions loaded successfully"
echo ""

echo "============================================================"
echo "  Bootstrap Complete!"
echo "============================================================"
echo "  All data has been loaded into Infrahub"
echo "  Branch: $BRANCH"
echo "  Next steps:"
echo "    - Create a branch: uv run infrahubctl branch create <name>"
echo "    - Load a DC design: uv run infrahubctl object load objects/dc-arista-s.yml --branch <name>"
echo "============================================================"
echo ""

