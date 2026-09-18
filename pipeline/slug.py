"""Tiny CLI: print the slug for a topic string, used by OpenClaw skills to
compute a consistent run-directory name across pipeline stages.

    python -m pipeline.slug "<topic>"
"""
import sys

from .utils import slugify

if __name__ == "__main__":
    print(slugify(sys.argv[1]))
