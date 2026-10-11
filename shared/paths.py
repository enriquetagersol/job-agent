"""Resolve the stable project root for private data, environment files and employment-agent instructions. Feature packages share this path so file moves never relocate stored data."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
