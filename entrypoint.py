"""Docker container entrypoint (§7, §8).

Docker starts this as root because the bind-mounted data volume may need a
one-time ownership fix: on first start the host's ``data/`` directory is owned
by whoever ran ``compose up`` — or by root, if Docker created it because it was
missing. A server that runs permanently under its own account cannot chown
files, so the repair has to happen before privileges are dropped.

The fixup is a single recursive pass over the volume (milliseconds at this
scale), then this process drops uid/gid for good and execs uvicorn in its
place. The long-running server therefore always runs as ``jobtracker``, never
root (§8) — verifiable with ``ps``/``/proc`` inside the container.

Local development does not use this file; it is wired in only by the
Dockerfile's ENTRYPOINT.
"""

import os
import pwd
import shutil
import sys

APP_USER = "jobtracker"


def fix_data_ownership(data_dir: str, user_info: pwd.struct_passwd) -> None:
    """Make *data_dir* and everything inside it owned by the app user.

    No-op when ownership is already correct (every boot after the first).
    Only called while running as root, from :func:`main`.
    """
    os.makedirs(data_dir, exist_ok=True)
    st = os.stat(data_dir)
    if st.st_uid == user_info.pw_uid and st.st_gid == user_info.pw_gid:
        return

    for dirpath, dirnames, filenames in os.walk(data_dir):
        for name in (*dirnames, *filenames):
            os.chown(os.path.join(dirpath, name), user_info.pw_uid, user_info.pw_gid)
    os.chown(data_dir, user_info.pw_uid, user_info.pw_gid)
    # Guarantee the owner-write bit survives whatever mode the host had.
    os.chmod(data_dir, st.st_mode | 0o200)


def main() -> None:
    if os.geteuid() == 0:
        user_info = pwd.getpwnam(APP_USER)
        fix_data_ownership(os.getenv("DATA_DIR", "/app/data"), user_info)

        # Drop privileges for good (no supplementary groups), then replace this
        # process with uvicorn — the server itself never runs as root.
        os.setgroups([])
        os.setgid(user_info.pw_gid)
        os.setuid(user_info.pw_uid)

    uvicorn = shutil.which("uvicorn")
    if uvicorn is None:
        sys.exit(f"{__file__}: 'uvicorn' not found on PATH; refusing to start.")
    # cwd stays /code (the Dockerfile WORKDIR), so `app.main` imports cleanly.
    os.execv(uvicorn, ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])


if __name__ == "__main__":
    main()
