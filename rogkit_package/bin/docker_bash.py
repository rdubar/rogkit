#!/usr/bin/env python3
"""
Docker container bash accessor.

Quickly access bash shells in running Docker containers with fuzzy name matching.
Supports auto-selection when only one container is running.
"""
import subprocess
import sys


def get_running_containers():
    """Get list of running Docker containers with ID, image, and name."""
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.ID}} {{.Image}} {{.Names}}"],
        capture_output=True, text=True
    )
    containers = [
        line.strip().split(maxsplit=2)
        for line in result.stdout.strip().split("\n")
        if line.strip()
    ]
    return containers

def bash_into_container(container_id):
    """Execute interactive bash session in specified Docker container."""
    print(f"Bashing into container {container_id}…")
    subprocess.run(["docker", "exec", "-it", container_id, "bash"])

def main():
    """CLI entry point for Docker bash accessor."""
    print("Docker BASH Tool...")
    containers = get_running_containers()

    if not containers:
        print("No running containers.")
        sys.exit(1)

    match = None
    args = sys.argv[1:]

    if "-1" in args:
        print(f"Using the first running container of {len(containers)}. containers.")
        match = containers[0]

    elif args:
        query = args[0].lower()
        matches = [c for c in containers if query in c[1].lower() or query in c[2].lower()]
        if len(matches) == 1:
            match = matches[0]
        elif matches:
            print("Multiple matches:")
            for c in matches:
                print(f"{c[0]} | {c[1]} | {c[2]}")
            print("Use `-1` to bash into the first match.")
            sys.exit(0)
        else:
            print(f"No matches for '{query}'.")
            sys.exit(1)

    elif len(containers) == 1:
        match = containers[0]

    else:
        print("Multiple running containers:")
        for c in containers:
            print(f"{c[0]} | {c[1]} | {c[2]}")
        print("Use `-1` to bash into the first one or provide a name filter.")
        sys.exit(0)

    bash_into_container(match[0])

if __name__ == "__main__":
    main()