# Quick Test - Object Template Bug Reproduction

**TL;DR:** This is the fastest way to reproduce the duplicate interface bug.

## One-line summary

Creating a device with an object template results in duplicate interfaces being created.

## Quick reproduction (5 steps)

```bash
# 0. Ensure Infrahub is running
uv run invoke start

# 1. Load minimal test schema (only 9 node types)
uv run infrahubctl schema load schemas-test --branch main

# 2. Load test data (1 location, 1 device type, 1 template with 2 interfaces)
uv run infrahubctl object load objects/test/ --branch main

# 3. Create test branch
uv run infrahubctl branch create test-bug

# 4. Load test topology
uv run infrahubctl object load objects/test/test-topology.yml --branch test-bug

# 5. Run test generator (this will show the bug)
uv run infrahubctl generator test_minimal name=TEST-DC --branch test-bug
```

## Expected vs Actual

**Expected:** Device has 2 interfaces (eth0, eth1)
**Actual with minimal schema:** Device has 2 interfaces (eth0, eth1) ✓

**Note:** This minimal reproduction case does NOT reproduce the duplicate interface bug as of this test. The bug may have been fixed, or it may require the more complex schema inheritance present in the full demo schemas (`inherit_from: DcimGenericDevice`).

To test with the full schemas, see the main demo workflow in `BUG_REPRODUCTION.md`.

## See full details

For complete documentation, see [BUG_REPRODUCTION.md](./BUG_REPRODUCTION.md)
