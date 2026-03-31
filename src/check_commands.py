"""Entry point for the command-check workflow. Checks for /brief commands, runs digest if found."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot_commands import checkForCommands
from src.main import run


def main():
    print("Checking for Telegram commands...")
    commands = checkForCommands()

    if commands:
        print(f"Found {len(commands)} command(s) — running digest!")
        run()
    else:
        print("No commands found. Nothing to do.")


if __name__ == "__main__":
    main()
