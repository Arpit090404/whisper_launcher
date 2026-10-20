"""PyInstaller entry point for Cassette.

Keeping this outside the package lets PyInstaller import the package normally,
so package-relative imports continue to work in a frozen executable.
"""
from voicelaunch.app import run

if __name__ == "__main__":
    raise SystemExit(run())
