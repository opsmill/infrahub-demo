# Minimal Reproduction: Object Template Duplicate Interface Bug

This document provides step-by-step instructions to reproduce the duplicate interface bug when using object templates with physical devices in Infrahub.

## Bug Description

When creating a `DcimPhysicalDevice` with an `object_template` that defines interfaces, Infrahub creates **duplicate interfaces**. For example, if the template defines 2 interfaces (`eth0` and `eth1`), the device ends up with 4 interfaces (two copies of each).

This causes the SDK's `client.get()` method to fail with `IndexError: More than 1 node returned` when attempting to query a specific interface by name.

## Impact

- Generators fail when trying to create connections between devices
- Data integrity issues with duplicate interfaces
- SDK operations fail when expecting a single interface

## Prerequisites

- Infrahub running locally (any version that supports object templates)
- Schemas already loaded
- Python environment with infrahub-sdk installed

## Reproduction Steps

### Step 0: Ensure Infrahub is running

Start Infrahub if it's not already running:

```bash
uv run invoke start
```

Wait for all containers to be healthy (check with `docker ps`).

### Step 1: Load minimal test schema

Load the minimal schema (this is completely isolated from the main demo schemas):

```bash
uv run infrahubctl schema load schemas-test --branch main
```

This loads only the bare minimum schemas needed for the test:
- LocationBuilding
- OrganizationManufacturer
- DcimPlatform
- DcimDeviceType
- DcimPhysicalDevice
- DcimPhysicalInterface
- TemplateDcimPhysicalDevice
- TemplateDcimPhysicalInterface
- TopologyDataCenter

### Step 2: Load minimal test data

Load the minimal test data (location, device type, and object template):

```bash
uv run infrahubctl object load objects/test/ --branch main
```

This creates:
- 1 location: `TEST-LOCATION`
- 1 manufacturer: `TestVendor`
- 1 platform: `TestOS`
- 1 device type: `TEST-DEVICE-TYPE`
- 1 object template: `TEST-DEVICE-TEMPLATE` (defines 2 interfaces: eth0, eth1)

### Step 3: Create a test branch

```bash
uv run infrahubctl branch create test-bug
```

### Step 4: Load test topology

Load the test topology design on the branch:

```bash
uv run infrahubctl object load objects/test/test-topology.yml --branch test-bug
```

This creates a single `TopologyDataCenter` object named `TEST-DC`.

### Step 5: Run the minimal generator

Execute the test generator that reproduces the bug:

```bash
uv run infrahubctl generator test_minimal name=TEST-DC --branch test-bug
```

## Expected Behavior

The generator should:
1. Create a device named `test-dc-device-01`
2. Apply the object template
3. Result in **2 interfaces** (eth0, eth1)
4. Successfully query interface eth0 using `client.get()`
5. Output: `RESULT: ✓ PASS - No duplicates detected`

## Actual Behavior

The generator:
1. Creates a device named `test-dc-device-01`
2. Applies the object template
3. Results in **4 interfaces** (eth0, eth0, eth1, eth1) - duplicates!
4. Fails when attempting to query interface eth0
5. Error: `IndexError: More than 1 node returned`
6. Output: `RESULT: ✗ FAIL - Expected 2 interfaces, found 4`

## Example Output

```
============================================================
MINIMAL REPRODUCTION TEST FOR DUPLICATE INTERFACE BUG
============================================================
Creating test device for topology: TEST-DC
Step 1: Creating device 'test-dc-device-01' with object template...
✓ Device created with ID: <uuid>

Step 2: Querying interfaces for device 'test-dc-device-01'...
Total interfaces found: 4

Interface breakdown:
  eth0: ✗ DUPLICATE (2 copies)
  eth1: ✗ DUPLICATE (2 copies)

============================================================
RESULT: ✗ FAIL - Expected 2 interfaces, found 4
        Duplicate interfaces detected: True
============================================================

Step 3: Attempting to get interface 'eth0' (will fail with duplicates)...
✗ FAILED: More than 1 node returned
This is the bug - client.get() fails when duplicates exist
Error: More than 1 node returned
```

## Verification via GraphQL

You can verify the duplicates directly via GraphQL:

```bash
curl -X POST http://localhost:8000/graphql/test-bug \
  -H "Content-Type: application/json" \
  -H "X-INFRAHUB-KEY: 06438eb2-8019-4776-878c-0941b1f1d1ec" \
  -d '{
    "query": "query { DcimPhysicalInterface(device__name__value: \"test-dc-device-01\") { count edges { node { name { value } } } } }"
  }' | python3 -m json.tool
```

Expected: `"count": 2`
Actual: `"count": 4`

## Cleanup

To clean up after testing:

```bash
# Delete the test branch
uv run infrahubctl branch delete test-bug

# Optionally, remove test data from main branch
# (or just destroy and rebuild if you want a clean state)
```

## Root Cause Analysis

The bug appears to be in Infrahub's object template application logic. When a device is created with `allow_upsert=False` (or even with `allow_upsert=True`), the template's interface definitions are processed twice, resulting in duplicate interface creation.

This is likely a race condition or duplicate processing in the template instantiation code path within Infrahub's backend.

## Workarounds Attempted

1. **Sequential creation** - Still produces duplicates
2. **Disabling upsert** - Still produces duplicates
3. **Existence checking** - Can skip re-creation but doesn't prevent initial duplicates

## Recommendation

This appears to be a bug in Infrahub's core object template handling and should be reported to the Infrahub team with this minimal reproduction case.

## Test Files Created

**Schema:**
- `schemas-test/minimal.yml` - Minimal schema with only required node types

**Data:**
- `objects/test/01-location.yml` - Test location
- `objects/test/02-manufacturer.yml` - Test manufacturer
- `objects/test/03-platform.yml` - Test platform
- `objects/test/04-device-type.yml` - Test device type
- `objects/test/05-device-template.yml` - Object template with 2 interfaces
- `objects/test/test-topology.yml` - Test topology design

**Generator:**
- `generators/test/test_minimal_generator.py` - Minimal generator
- `queries/test/test_topology.gql` - Simple GraphQL query
- `.infrahub.yml` - Updated with test generator registration

All test files are isolated from the main demo and can be removed without affecting existing functionality.
