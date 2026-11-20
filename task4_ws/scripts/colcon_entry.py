#!/usr/bin/env python3
"""Run colcon with a process-local child watcher for the Humble build host."""

import asyncio
import sys


def main():
    # The default threaded watcher stalled during setup.py command discovery in
    # this restricted Linux/Python 3.10 execution environment. Keep the alternate
    # watcher local to this process; no installed colcon files are modified.
    if sys.platform == "linux" and sys.version_info < (3, 12):
        asyncio.set_child_watcher(asyncio.SafeChildWatcher())
    from colcon_core.command import main as colcon_main

    sys.argv[0] = "colcon"
    return colcon_main()


if __name__ == "__main__":
    raise SystemExit(main())
