#!/usr/bin/env python3
"""
Create user accounts, roles, and groups in Infrahub.

This script creates:
- Two roles: read-only-role and schema-reviewer-role
- Two groups: read-only-users and schema-reviewers
- Two users: emma (read-only) and otto (schema reviewer with full object permissions)

Usage:
    python scripts/create_users_roles.py
    uv run python scripts/create_users_roles.py
"""

import asyncio
import sys

from infrahub_sdk import InfrahubClient


async def find_permission_by_identifier(
    client: InfrahubClient, identifier: str
) -> str | None:
    """Find a permission by its identifier and return its ID."""
    # Map decision strings to integer values
    decision_map = {"deny": 1, "allow_default": 2, "allow_other": 4, "allow_all": 6}

    # Determine if it's a global or object permission
    if identifier.startswith("global:"):
        kind = "CoreGlobalPermission"
        parts = identifier.split(":")
        action = parts[1]
        decision_str = parts[2]
        decision_value = decision_map.get(decision_str, 6)

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
    else:  # object permission
        kind = "CoreObjectPermission"
        parts = identifier.split(":")
        namespace = parts[1] if parts[1] != "*" else "*"
        name = parts[2] if parts[2] != "*" else "*"
        action = parts[3]
        decision_str = parts[4]
        decision_value = decision_map.get(decision_str, 6)

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

    result = await client.execute_graphql(query=query)
    edges = result.get(kind, {}).get("edges", [])

    if edges:
        return edges[0]["node"]["id"]

    return None


async def ensure_permissions_exist(client: InfrahubClient) -> None:
    """Ensure required permissions exist in the database."""
    print("Ensuring required permissions exist...")

    # Define permissions that need to exist
    # Format: (kind, data)
    permissions_to_create = [
        # Object permissions
        ("CoreObjectPermission", {"namespace": "*", "name": "*", "action": "view", "decision": 6}),
        ("CoreObjectPermission", {"namespace": "*", "name": "*", "action": "create", "decision": 1}),
        ("CoreObjectPermission", {"namespace": "*", "name": "*", "action": "update", "decision": 1}),
        ("CoreObjectPermission", {"namespace": "*", "name": "*", "action": "delete", "decision": 1}),
        ("CoreObjectPermission", {"namespace": "*", "name": "*", "action": "any", "decision": 6}),
        # Global permissions
        ("CoreGlobalPermission", {"action": "manage_schema", "decision": 6}),
        ("CoreGlobalPermission", {"action": "review_proposed_change", "decision": 6}),
    ]

    for kind, data in permissions_to_create:
        # Check if permission already exists
        if kind == "CoreGlobalPermission":
            identifier = f"global:{data['action']}:allow_all"
        else:
            # Map decision to string
            decision_map: dict[int, str] = {1: "deny", 6: "allow_all"}
            decision_value = data["decision"]
            assert isinstance(decision_value, int), "decision must be an integer"
            decision_str = decision_map.get(decision_value, "allow_all")
            identifier = f"object:{data['namespace']}:{data['name']}:{data['action']}:{decision_str}"

        existing = await find_permission_by_identifier(client, identifier)
        if existing:
            print(f"  Permission {identifier} already exists")
        else:
            # Create the permission
            try:
                perm = await client.create(kind=kind, data=data)
                await perm.save()
                print(f"  Created permission {identifier}")
            except Exception as e:
                # Check if it's a uniqueness constraint error (permission already exists)
                error_msg = str(e)
                if "uniqueness constraint" in error_msg.lower():
                    print(f"  Permission {identifier} already exists (uniqueness constraint)")
                else:
                    print(f"  Failed to create permission {identifier}: {e}")


async def create_roles(client: InfrahubClient) -> dict[str, str]:
    """Create roles and return a mapping of role names to IDs."""
    print("\nCreating roles...")

    roles_config = {
        "read-only-role": [
            "object:*:*:view:allow_all",
            "object:*:*:create:deny",
            "object:*:*:update:deny",
            "object:*:*:delete:deny",
        ],
        "schema-reviewer-role": [
            "global:manage_schema:allow_all",
            "global:review_proposed_change:allow_all",
            "object:*:*:any:allow_all",
        ],
    }

    role_ids = {}

    for role_name, permission_identifiers in roles_config.items():
        # Find permission IDs by their identifiers
        permission_ids = []
        for perm_id in permission_identifiers:
            perm_uuid = await find_permission_by_identifier(client, perm_id)
            if perm_uuid:
                permission_ids.append(perm_uuid)
            else:
                print(f"  Error: Permission {perm_id} not found after creation attempt!")

        # Check if role already exists
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
            role_id = edges[0]["node"]["id"]
            print(f"  Role '{role_name}' already exists (ID: {role_id})")
            role_ids[role_name] = role_id
        else:
            # Create the role
            role = await client.create(
                kind="CoreAccountRole",
                data={"name": role_name, "permissions": permission_ids},
            )
            await role.save()
            print(f"  Created role '{role_name}' (ID: {role.id})")
            role_ids[role_name] = role.id

    return role_ids


async def create_groups(
    client: InfrahubClient, role_ids: dict[str, str]
) -> dict[str, str]:
    """Create groups and return a mapping of group names to IDs."""
    print("\nCreating groups...")

    groups_config = {
        "read-only-users": {
            "description": "Users with read-only access to Infrahub",
            "roles": ["read-only-role"],
        },
        "schema-reviewers": {
            "description": "Users who can manage schemas and review proposed changes",
            "roles": ["schema-reviewer-role"],
        },
    }

    group_ids = {}

    for group_name, config in groups_config.items():
        # Map role names to IDs
        role_id_list = [role_ids[role_name] for role_name in config["roles"]]

        # Check if group already exists
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
            group_id = edges[0]["node"]["id"]
            print(f"  Group '{group_name}' already exists (ID: {group_id})")
            group_ids[group_name] = group_id
        else:
            # Create the group
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


async def create_users(client: InfrahubClient, group_ids: dict[str, str]) -> None:
    """Create user accounts."""
    print("\nCreating users...")

    users_config = {
        "emma": {
            "password": "emma123",
            "account_type": "User",
            "description": "Read-only user account",
            "groups": ["read-only-users"],
        },
        "otto": {
            "password": "otto123",
            "account_type": "User",
            "description": "Schema reviewer with full object permissions",
            "groups": ["schema-reviewers"],
        },
    }

    for username, config in users_config.items():
        # Map group names to IDs
        group_id_list = [group_ids[group_name] for group_name in config["groups"]]

        # Check if user already exists
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
            user_id = edges[0]["node"]["id"]
            print(f"  User '{username}' already exists (ID: {user_id})")
        else:
            # Create the user
            user = await client.create(
                kind="CoreAccount",
                data={
                    "name": username,
                    "password": config["password"],
                    "account_type": config["account_type"],
                    "description": config["description"],
                    "member_of_groups": group_id_list,
                },
            )
            await user.save()
            print(f"  Created user '{username}' (ID: {user.id})")


async def main() -> int:
    """Main function to create users, roles, and groups."""
    try:
        client = InfrahubClient()

        # Ensure permissions exist first
        await ensure_permissions_exist(client)

        # Create roles (they reference permissions)
        role_ids = await create_roles(client)

        # Create groups (they reference roles)
        group_ids = await create_groups(client, role_ids)

        # Create users (they reference groups)
        await create_users(client, group_ids)

        print("\n✓ Successfully created users, roles, and groups!")
        return 0

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
