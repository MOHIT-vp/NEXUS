"""
Create a Placement Cell (officer) or admin account. Students sign up on the website.

    cd backend && venv/bin/python -m scripts.create_user --role placement_officer --email tpo@college.edu --name "TPO"

The password is asked for without echo (or read from the CREATE_USER_PASSWORD environment variable).
"""
import argparse
import asyncio
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session_factory  # noqa: E402
from app.services.auth import create_user, get_user_by_email  # noqa: E402


async def _create(email: str, name: str, role: str, password: str) -> None:
    async with async_session_factory() as db:
        if await get_user_by_email(db, email):
            sys.exit(f"An account with {email} already exists.")
        user = await create_user(db, email=email, password=password, full_name=name, role=role)
        await db.commit()
        print(f"Created {role} account {user.email}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--role", choices=["placement_officer", "admin"], default="placement_officer")
    args = p.parse_args()
    password = os.environ.get("CREATE_USER_PASSWORD") or getpass.getpass("Password: ")
    if len(password) < 8:
        sys.exit("Password must be at least 8 characters.")
    asyncio.run(_create(args.email, args.name, args.role, password))


if __name__ == "__main__":
    main()
