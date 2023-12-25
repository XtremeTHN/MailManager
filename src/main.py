from modules.ui import GmailApplication
import sys
import os
import argparse

parser = argparse.ArgumentParser(prog="gmail", description="A gtk4 and libadwaita gmail client")

parser.add_argument("--theme", help="Sets the gtk theme. You can pass this argument or declare GTK_THEME environment variable")

args = parser.parse_args()

if __name__ == "__main__":
    app = GmailApplication(args.theme)
    app.run()