#!/usr/bin/env python3
"""
Create user accounts, roles, groups, and permissions in Infrahub for RBAC demo.

This script sets up a complete Role-Based Access Control (RBAC) demonstration
environment in Infrahub with predefined users, roles, groups, and permissions.
It showcases Infrahub's fine-grained permission system for controlling access
to schemas, objects, and operations.

What This Script Creates:
==========================

Permissions (7 total):
----------------------
Object Permissions (controls access to Infrahub objects):
- object:*:*:view:allow_all - View all objects (read-only access)
- object:*:*:create:deny - Deny object creation
- object:*:*:update:deny - Deny object updates
- object:*:*:delete:deny - Deny object deletion
- object:*:*:any:allow_all - Allow all operations on all objects

Global Permissions (controls system-wide capabilities):
- global:manage_schema:allow_all - Manage schema definitions
- global:review_proposed_change:allow_all - Review and approve proposed changes

Roles (2 total):
----------------
1. read-only-role:
   - Can view all objects
   - Cannot create, update, or delete objects
   - Suitable for auditors, viewers, or monitoring users

2. schema-reviewer-role:
   - Can manage schemas (add/modify schema definitions)
   - Can review and approve proposed changes
   - Has full permissions on all objects (create, read, update, delete)
   - Suitable for senior engineers, architects, or change approvers

Groups (2 total):
-----------------
1. read-only-users:
   - Description: "Users with read-only access to Infrahub"
   - Assigned role: read-only-role
   - Members: emma

2. schema-reviewers:
   - Description: "Users who can manage schemas and review proposed changes"
   - Assigned role: schema-reviewer-role
   - Members: otto

Users (2 total):
----------------
1. emma:
   - Username: emma
   - Password: emma123 (demo password - change in production!)
   - Account type: User
   - Group membership: read-only-users
   - Capabilities: Can view all data but cannot make changes

2. otto:
   - Username: otto
   - Password: otto123 (demo password - change in production!)
   - Account type: User
   - Group membership: schema-reviewers
   - Capabilities: Can manage schemas, review PCs, and modify all objects

Infrahub RBAC Hierarchy:
========================
The permission system follows this hierarchy:

Users → Groups → Roles → Permissions

- Users are assigned to Groups
- Groups have one or more Roles
- Roles contain one or more Permissions
- Permissions define specific allowed/denied actions

Permission Types:
=================

1. Object Permissions: Control access to Infrahub objects (devices, interfaces, etc.)
   Format: object:<namespace>:<name>:<action>:<decision>
   - namespace: Schema namespace (or * for all)
   - name: Object kind (or * for all)
   - action: create, view, update, delete, any
   - decision: allow_all, allow_default, allow_other, deny

2. Global Permissions: Control system-wide capabilities
   Format: global:<action>:<decision>
   - action: manage_schema, review_proposed_change, etc.
   - decision: allow_all, allow_default, allow_other, deny

Use Cases:
==========

Read-Only User (emma):
- Monitoring and auditing infrastructure state
- Viewing configurations without risk of accidental changes
- Reporting and documentation purposes
- Junior team members learning the system

Schema Reviewer (otto):
- Reviewing and approving infrastructure changes
- Managing schema evolution
- Senior engineers with change approval authority
- Architects defining data models

Execution Flow:
===============
1. Connect to Infrahub
2. Ensure permissions exist (create if missing)
3. Create roles and link to permissions
4. Create groups and link to roles
5. Create users and link to groups

Error Handling:
===============
- Gracefully handles already-existing objects (idempotent)
- Checks for uniqueness constraint violations
- Validates that permissions exist before creating roles
- Provides clear error messages with stack traces

Security Notes:
===============
⚠️  IMPORTANT: This script uses demo passwords (emma123, otto123).
    In production environments:
    - Use strong, randomly generated passwords
    - Store passwords in secure secret management systems
    - Enable MFA/2FA if available
    - Rotate passwords regularly
    - Follow your organization's security policies

Usage:
======
    # Run directly with Python
    python scripts/create_users_roles.py

    # Run via uv (recommended)
    uv run python scripts/create_users_roles.py

    # Called automatically by bootstrap script
    uv run invoke bootstrap

Exit Codes:
===========
    0: Successfully created all users, roles, groups, and permissions
    1: Failed to create (connection error, validation error, etc.)

Output:
=======
The script provides step-by-step progress output:
- Permission creation status (created or already exists)
- Role creation with permission assignments
- Group creation with role assignments
- User creation with group memberships
- Success confirmation with checkmark

Testing the Setup:
==================
After running this script, you can test the RBAC setup:

1. Log in as emma (read-only user):
   - Try to view objects (should work)
   - Try to create/update/delete objects (should be denied)

2. Log in as otto (schema reviewer):
   - Try to view objects (should work)
   - Try to create/update/delete objects (should work)
   - Try to manage schemas (should work)
   - Try to review proposed changes (should work)
"""

import asyncio
import sys

from infrahub_sdk import InfrahubClient

# ============================================================================
# PERMISSION LOOKUP UTILITIES
# ============================================================================


async def find_permission_by_identifier(
    client: InfrahubClient, identifier: str
) -> str | None:
    """
    Find a permission by its identifier string and return its UUID.

    Infrahub permissions are identified by structured strings that encode
    the permission type, scope, action, and decision. This function parses
    these identifier strings and queries Infrahub to find the corresponding
    permission object UUID.

    Permission Identifier Formats:
    ==============================

    Global Permissions:
        Format: global:<action>:<decision>
        Example: global:manage_schema:allow_all
        Components:
            - action: manage_schema, review_proposed_change, etc.
            - decision: allow_all, allow_default, allow_other, deny

    Object Permissions:
        Format: object:<namespace>:<name>:<action>:<decision>
        Example: object:*:*:view:allow_all
        Components:
            - namespace: Schema namespace (* for all namespaces)
            - name: Object kind (* for all objects)
            - action: create, view, update, delete, any
            - decision: allow_all, allow_default, allow_other, deny

    Decision Values:
    ================
    Infrahub stores decisions as integer values:
        1 = deny (explicitly deny access)
        2 = allow_default (allow with default permissions)
        4 = allow_other (allow for other users)
        6 = allow_all (allow for everyone)

    Args:
        client: Authenticated InfrahubClient instance
        identifier: Permission identifier string (e.g., "global:manage_schema:allow_all")

    Returns:
        Permission UUID if found, None if not found

    Example:
        >>> client = InfrahubClient()
        >>> perm_id = await find_permission_by_identifier(
        ...     client, "object:*:*:view:allow_all"
        ... )
        >>> print(perm_id)  # UUID like "a1b2c3d4-..."

    Raises:
        No exceptions raised - returns None if permission not found
    """
    # Map decision strings to Infrahub's internal integer values
    # These values are used in the GraphQL query filters
    decision_map = {"deny": 1, "allow_default": 2, "allow_other": 4, "allow_all": 6}

    # ========================================================================
    # Parse identifier and build GraphQL query
    # ========================================================================
    # Determine permission type by checking identifier prefix
    if identifier.startswith("global:"):
        # Global permission: global:<action>:<decision>
        kind = "CoreGlobalPermission"
        parts = identifier.split(":")
        action = parts[1]  # e.g., "manage_schema"
        decision_str = parts[2]  # e.g., "allow_all"
        decision_value = decision_map.get(decision_str, 6)  # Convert to int

        # Build GraphQL query to find global permission by action and decision
        query = f"""
        query {{
          {kind}(action__value: "{action}", decision__value: {decision_value}) {{
            edges {{
              node {{
                id
                identifier {{
                  value
                }}
              }}
            }}
          }}
        }}
        """
    else:
        # Object permission: object:<namespace>:<name>:<action>:<decision>
        kind = "CoreObjectPermission"
        parts = identifier.split(":")
        namespace = parts[1] if parts[1] != "*" else "*"  # e.g., "Dcim" or "*"
        name = parts[2] if parts[2] != "*" else "*"  # e.g., "Device" or "*"
        action = parts[3]  # e.g., "view", "create", "update", "delete", "any"
        decision_str = parts[4]  # e.g., "allow_all", "deny"
        decision_value = decision_map.get(decision_str, 6)  # Convert to int

        # Build GraphQL query to find object permission by namespace, name, action, and decision
        query = f"""
        query {{
          {kind}(namespace__value: "{namespace}", name__value: "{name}", action__value: "{action}", decision__value: {decision_value}) {{
            edges {{
              node {{
                id
                identifier {{
                  value
                }}
              }}
            }}
          }}
        }}
        """

    # Execute the GraphQL query to find the permission
    result = await client.execute_graphql(query=query)
    edges = result.get(kind, {}).get("edges", [])

    # Return the permission UUID if found, None otherwise
    if edges:
        return edges[0]["node"]["id"]

    return None


# ============================================================================
# PERMISSION CREATION
# ============================================================================


async def ensure_permissions_exist(client: InfrahubClient) -> None:
    """
    Ensure all required permissions exist in Infrahub before creating roles.

    This function creates the foundational permissions needed for the RBAC demo.
    Permissions are the lowest level of the access control hierarchy and define
    specific allowed or denied actions. Roles are built from these permissions.

    Why Permissions Must Exist First:
    ==================================
    Roles reference permissions by UUID. If we try to create a role before its
    permissions exist, the role creation will fail. This function ensures all
    required permissions are available before role creation begins.

    Idempotency:
    ============
    This function is idempotent - it can be run multiple times safely:
    - First checks if each permission already exists
    - Only creates permissions that are missing
    - Handles uniqueness constraint errors gracefully
    - Provides clear status for each permission (created or already exists)

    Permissions Created:
    ====================
    See module docstring for complete list of 7 permissions created.

    Args:
        client: Authenticated InfrahubClient instance

    Returns:
        None (prints status messages to stdout)

    Raises:
        Exceptions are caught and printed, but don't halt execution
        (allows partial success if some permissions already exist)
    """
    print("Ensuring required permissions exist...")

    # ========================================================================
    # Define Required Permissions
    # ========================================================================
    # List of (kind, data) tuples for permissions that must exist
    # These are referenced by roles created in the next step
    permissions_to_create = [
        # ====================================================================
        # Object Permissions (control access to Infrahub objects)
        # ====================================================================
        # namespace: "*" = all namespaces (Dcim, Ipam, Location, etc.)
        # name: "*" = all object types (Device, Interface, IPAddress, etc.)
        # decision: 6 = allow_all, 1 = deny
        ("CoreObjectPermission", {"namespace": "*", "name": "*", "action": "view", "decision": 6}),
        ("CoreObjectPermission", {"namespace": "*", "name": "*", "action": "create", "decision": 1}),
        ("CoreObjectPermission", {"namespace": "*", "name": "*", "action": "update", "decision": 1}),
        ("CoreObjectPermission", {"namespace": "*", "name": "*", "action": "delete", "decision": 1}),
        ("CoreObjectPermission", {"namespace": "*", "name": "*", "action": "any", "decision": 6}),
        # ====================================================================
        # Global Permissions (control system-wide capabilities)
        # ====================================================================
        ("CoreGlobalPermission", {"action": "manage_schema", "decision": 6}),
        ("CoreGlobalPermission", {"action": "review_proposed_change", "decision": 6}),
    ]

    # ========================================================================
    # Create Each Permission (with idempotency)
    # ========================================================================
    for kind, data in permissions_to_create:
        # Build identifier string for the permission
        # This is used to check if it already exists
        if kind == "CoreGlobalPermission":
            identifier = f"global:{data['action']}:allow_all"
        else:
            # Map integer decision values to string representation
            decision_map: dict[int, str] = {1: "deny", 6: "allow_all"}
            decision_value = data["decision"]
            assert isinstance(decision_value, int), "decision must be an integer"
            decision_str = decision_map.get(decision_value, "allow_all")
            identifier = f"object:{data['namespace']}:{data['name']}:{data['action']}:{decision_str}"

        # Check if permission already exists in Infrahub
        existing = await find_permission_by_identifier(client, identifier)
        if existing:
            print(f"  Permission {identifier} already exists")
        else:
            # Permission doesn't exist - create it
            try:
                perm = await client.create(kind=kind, data=data)
                await perm.save()
                print(f"  Created permission {identifier}")
            except Exception as e:
                # Handle uniqueness constraint violations gracefully
                # This can occur if permission was created between our check and create attempt
                error_msg = str(e)
                if "uniqueness constraint" in error_msg.lower():
                    print(f"  Permission {identifier} already exists (uniqueness constraint)")
                else:
                    # Other errors are printed but don't halt execution
                    print(f"  Failed to create permission {identifier}: {e}")


# ============================================================================
# ROLE CREATION
# ============================================================================


async def create_roles(client: InfrahubClient) -> dict[str, str]:
    """
    Create roles and return a mapping of role names to UUIDs.

    Roles are collections of permissions that define what users can do in Infrahub.
    This function creates two roles for the RBAC demo:
    1. read-only-role: Can view objects but cannot modify anything
    2. schema-reviewer-role: Can manage schemas and review proposed changes

    Roles in the RBAC Hierarchy:
    =============================
    Users → Groups → Roles → Permissions

    Roles sit between groups and permissions:
    - Groups assign roles to users
    - Roles contain one or more permissions
    - Permissions define specific allowed/denied actions

    Why Return Role IDs:
    ====================
    Groups need to reference roles by UUID when they're created.
    This function returns a dict mapping role names to UUIDs so that
    create_groups() can link groups to the correct roles.

    Idempotency:
    ============
    - Checks if each role already exists before creating
    - Returns existing role UUID if found
    - Safe to run multiple times

    Args:
        client: Authenticated InfrahubClient instance

    Returns:
        Dictionary mapping role names to UUIDs
        Example: {"read-only-role": "uuid-123", "schema-reviewer-role": "uuid-456"}

    Example:
        >>> role_ids = await create_roles(client)
        >>> print(role_ids["read-only-role"])
        "a1b2c3d4-e5f6-..."
    """
    print("\nCreating roles...")

    # ========================================================================
    # Define Role Configurations
    # ========================================================================
    # Each role maps to a list of permission identifiers
    # These identifiers are resolved to UUIDs using find_permission_by_identifier()
    roles_config = {
        # Read-only role: View everything, modify nothing
        "read-only-role": [
            "object:*:*:view:allow_all",  # Can view all objects
            "object:*:*:create:deny",  # Cannot create objects
            "object:*:*:update:deny",  # Cannot update objects
            "object:*:*:delete:deny",  # Cannot delete objects
        ],
        # Schema reviewer role: Full system access including schema management
        "schema-reviewer-role": [
            "global:manage_schema:allow_all",  # Can manage schema definitions
            "global:review_proposed_change:allow_all",  # Can review/approve PCs
            "object:*:*:any:allow_all",  # Full access to all objects (CRUD)
        ],
    }

    # Dictionary to store role name → UUID mappings
    role_ids = {}

    # ========================================================================
    # Create Each Role
    # ========================================================================
    for role_name, permission_identifiers in roles_config.items():
        # Resolve permission identifiers to UUIDs
        # Permissions must exist before we can reference them in roles
        permission_ids = []
        for perm_id in permission_identifiers:
            perm_uuid = await find_permission_by_identifier(client, perm_id)
            if perm_uuid:
                permission_ids.append(perm_uuid)
            else:
                # This shouldn't happen if ensure_permissions_exist() ran successfully
                print(f"  Error: Permission {perm_id} not found after creation attempt!")

        # Check if role already exists in Infrahub
        query = f"""
        query {{
          CoreAccountRole(name__value: "{role_name}") {{
            edges {{
              node {{
                id
              }}
            }}
          }}
        }}
        """

        result = await client.execute_graphql(query=query)
        edges = result.get("CoreAccountRole", {}).get("edges", [])

        if edges:
            # Role already exists - use existing UUID
            role_id = edges[0]["node"]["id"]
            print(f"  Role '{role_name}' already exists (ID: {role_id})")
            role_ids[role_name] = role_id
        else:
            # Role doesn't exist - create it with linked permissions
            role = await client.create(
                kind="CoreAccountRole",
                data={"name": role_name, "permissions": permission_ids},
            )
            await role.save()
            print(f"  Created role '{role_name}' (ID: {role.id})")
            role_ids[role_name] = role.id

    return role_ids


# ============================================================================
# GROUP CREATION
# ============================================================================


async def create_groups(
    client: InfrahubClient, role_ids: dict[str, str]
) -> dict[str, str]:
    """
    Create groups and return a mapping of group names to UUIDs.

    Groups are organizational units that assign roles to users. Instead of
    assigning permissions directly to users, Infrahub uses groups as an
    intermediate layer for easier management of user access.

    Groups in the RBAC Hierarchy:
    ==============================
    Users → Groups → Roles → Permissions

    Benefits of Using Groups:
    ==========================
    - Manage permissions for multiple users at once
    - Users can belong to multiple groups (inherit multiple roles)
    - Changes to group roles automatically affect all members
    - Organizational structure mirrors team structure

    Why Return Group IDs:
    =====================
    Users need to reference groups by UUID when they're created.
    This function returns a dict mapping group names to UUIDs so that
    create_users() can assign users to the correct groups.

    Idempotency:
    ============
    - Checks if each group already exists before creating
    - Returns existing group UUID if found
    - Safe to run multiple times

    Args:
        client: Authenticated InfrahubClient instance
        role_ids: Dict mapping role names to UUIDs (from create_roles())

    Returns:
        Dictionary mapping group names to UUIDs
        Example: {"read-only-users": "uuid-123", "schema-reviewers": "uuid-456"}

    Example:
        >>> role_ids = await create_roles(client)
        >>> group_ids = await create_groups(client, role_ids)
        >>> print(group_ids["read-only-users"])
        "a1b2c3d4-e5f6-..."
    """
    print("\nCreating groups...")

    # ========================================================================
    # Define Group Configurations
    # ========================================================================
    # Each group has a description and list of role names
    # Role names are resolved to UUIDs using the role_ids parameter
    groups_config = {
        "read-only-users": {
            "description": "Users with read-only access to Infrahub",
            "roles": ["read-only-role"],  # Assigned role(s)
        },
        "schema-reviewers": {
            "description": "Users who can manage schemas and review proposed changes",
            "roles": ["schema-reviewer-role"],  # Assigned role(s)
        },
    }

    # Dictionary to store group name → UUID mappings
    group_ids = {}

    # ========================================================================
    # Create Each Group
    # ========================================================================
    for group_name, config in groups_config.items():
        # Resolve role names to UUIDs using the role_ids dict
        # Roles must exist before we can reference them in groups
        role_id_list = [role_ids[role_name] for role_name in config["roles"]]

        # Check if group already exists in Infrahub
        query = f"""
        query {{
          CoreAccountGroup(name__value: "{group_name}") {{
            edges {{
              node {{
                id
              }}
            }}
          }}
        }}
        """

        result = await client.execute_graphql(query=query)
        edges = result.get("CoreAccountGroup", {}).get("edges", [])

        if edges:
            # Group already exists - use existing UUID
            group_id = edges[0]["node"]["id"]
            print(f"  Group '{group_name}' already exists (ID: {group_id})")
            group_ids[group_name] = group_id
        else:
            # Group doesn't exist - create it with linked roles
            group = await client.create(
                kind="CoreAccountGroup",
                data={
                    "name": group_name,
                    "description": config["description"],
                    "roles": role_id_list,
                },
            )
            await group.save()
            print(f"  Created group '{group_name}' (ID: {group.id})")
            group_ids[group_name] = group.id

    return group_ids


# ============================================================================
# USER CREATION
# ============================================================================


async def create_users(client: InfrahubClient, group_ids: dict[str, str]) -> None:
    """
    Create user accounts with group memberships.

    This function creates the actual user accounts that can log into Infrahub.
    Users are assigned to groups, which in turn provide roles and permissions.

    Users in the RBAC Hierarchy:
    =============================
    Users → Groups → Roles → Permissions

    Users are at the top of the hierarchy:
    - Users belong to one or more groups
    - Groups provide roles to users
    - Roles grant permissions to users
    - Permissions define what users can actually do

    Security Considerations:
    ========================
    ⚠️  This function uses hardcoded demo passwords (emma123, otto123).
        In production:
        - Use strong, randomly generated passwords
        - Store passwords in secure secret management systems (Vault, AWS Secrets Manager, etc.)
        - Enable MFA/2FA if available
        - Enforce password rotation policies
        - Never commit passwords to version control

    Idempotency:
    ============
    - Checks if each user already exists before creating
    - Skips creation if user found
    - Safe to run multiple times

    Args:
        client: Authenticated InfrahubClient instance
        group_ids: Dict mapping group names to UUIDs (from create_groups())

    Returns:
        None (prints status messages to stdout)

    Example:
        >>> role_ids = await create_roles(client)
        >>> group_ids = await create_groups(client, role_ids)
        >>> await create_users(client, group_ids)
        Creating users...
          Created user 'emma' (ID: uuid-123)
          Created user 'otto' (ID: uuid-456)
    """
    print("\nCreating users...")

    # ========================================================================
    # Define User Configurations
    # ========================================================================
    # Each user has password, account type, description, and group memberships
    # ⚠️  DEMO PASSWORDS - DO NOT USE IN PRODUCTION
    users_config = {
        "emma": {
            "password": "emma123",  # ⚠️  DEMO PASSWORD
            "account_type": "User",
            "description": "Read-only user account",
            "groups": ["read-only-users"],  # Read-only access
        },
        "otto": {
            "password": "otto123",  # ⚠️  DEMO PASSWORD
            "account_type": "User",
            "description": "Schema reviewer with full object permissions",
            "groups": ["schema-reviewers"],  # Full access including schema management
        },
    }

    # ========================================================================
    # Create Each User
    # ========================================================================
    for username, config in users_config.items():
        # Resolve group names to UUIDs using the group_ids dict
        # Groups must exist before we can assign users to them
        group_id_list = [group_ids[group_name] for group_name in config["groups"]]

        # Check if user already exists in Infrahub
        query = f"""
        query {{
          CoreAccount(name__value: "{username}") {{
            edges {{
              node {{
                id
              }}
            }}
          }}
        }}
        """

        result = await client.execute_graphql(query=query)
        edges = result.get("CoreAccount", {}).get("edges", [])

        if edges:
            # User already exists - skip creation
            user_id = edges[0]["node"]["id"]
            print(f"  User '{username}' already exists (ID: {user_id})")
        else:
            # User doesn't exist - create it with group membership
            user = await client.create(
                kind="CoreAccount",
                data={
                    "name": username,
                    "password": config["password"],  # ⚠️  Demo password
                    "account_type": config["account_type"],
                    "description": config["description"],
                    "member_of_groups": group_id_list,  # Assign to groups
                },
            )
            await user.save()
            print(f"  Created user '{username}' (ID: {user.id})")


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================


async def main() -> int:
    """
    Main orchestrator function to create complete RBAC setup.

    This function coordinates the creation of all RBAC components in the
    correct dependency order. Each component must be created before the
    components that depend on it.

    Execution Order (Critical):
    ============================
    1. Permissions (no dependencies)
    2. Roles (depend on permissions)
    3. Groups (depend on roles)
    4. Users (depend on groups)

    Why Order Matters:
    ==================
    - Roles reference permissions by UUID
    - Groups reference roles by UUID
    - Users reference groups by UUID
    If we create in the wrong order, UUIDs won't exist and creation will fail.

    Error Handling:
    ===============
    - Catches all exceptions and prints stack trace
    - Returns 1 on error (indicates failure to caller)
    - Individual creation functions handle idempotency gracefully

    Returns:
        0 on success, 1 on failure

    Example:
        >>> exit_code = await main()
        Ensuring required permissions exist...
          Created permission object:*:*:view:allow_all
          ...
        Creating roles...
          Created role 'read-only-role' (ID: uuid-123)
          ...
        Creating groups...
          Created group 'read-only-users' (ID: uuid-456)
          ...
        Creating users...
          Created user 'emma' (ID: uuid-789)
          ...
        ✓ Successfully created users, roles, and groups!
    """
    try:
        # Connect to Infrahub using environment variables
        # INFRAHUB_ADDRESS and INFRAHUB_API_TOKEN
        client = InfrahubClient()

        # ====================================================================
        # Step 1: Ensure Permissions Exist
        # ====================================================================
        # Permissions are the foundation of the RBAC system
        # They must be created first before roles can reference them
        await ensure_permissions_exist(client)

        # ====================================================================
        # Step 2: Create Roles
        # ====================================================================
        # Roles are collections of permissions
        # They reference permissions by UUID and return role UUIDs
        role_ids = await create_roles(client)

        # ====================================================================
        # Step 3: Create Groups
        # ====================================================================
        # Groups assign roles to users
        # They reference roles by UUID and return group UUIDs
        group_ids = await create_groups(client, role_ids)

        # ====================================================================
        # Step 4: Create Users
        # ====================================================================
        # Users are assigned to groups to receive permissions
        # They reference groups by UUID
        await create_users(client, group_ids)

        # Success! All RBAC components created
        print("\n✓ Successfully created users, roles, and groups!")
        return 0

    except Exception as e:
        # Error occurred - print diagnostic information
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================
# This section handles script execution from the command line.
# The script runs the async main() function and exits with its return code.

if __name__ == "__main__":
    # Execute the async main function using asyncio.run()
    # This handles the async event loop setup and teardown automatically
    # Exit with the return code from main (0 = success, 1 = failure)
    sys.exit(asyncio.run(main()))
