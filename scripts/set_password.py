"""Set the Supervisor or Maintainer password (stored only as a hash).

    uv run python scripts/set_password.py supervisor
    uv run python scripts/set_password.py maintainer --data bench_data
"""

import argparse
import getpass
import sys
from pathlib import Path

from vision_station.api import AuthError, AuthService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("role", choices=["supervisor", "maintainer"])
    parser.add_argument("--data", type=Path, default=Path("bench_data"), help="the data folder (default: bench_data)")
    args = parser.parse_args()
    password = getpass.getpass("New password: ")
    if password != getpass.getpass("Again: "):
        print("The two passwords differ.")
        return 1
    try:
        AuthService(args.data / "system" / "users.json").set_password(args.role, password)
    except AuthError as exc:
        print(exc)
        return 1
    print(f"Password of the {args.role} set in {args.data / 'system' / 'users.json'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
