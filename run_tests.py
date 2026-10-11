"""Run the offline test suite with network access blocked. Discover packaged tests and isolate diagnostic writes from the user’s actual local data."""

from contextlib import ExitStack
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch


def main():
    root = str(Path(__file__).resolve().parent)
    with ExitStack() as guards:
        for target in ('socket.socket.connect', 'socket.socket.connect_ex',
                       'socket.create_connection', 'socket.getaddrinfo',
                       'httpx.HTTPTransport.handle_request', 'httpx.AsyncHTTPTransport.handle_async_request'):
            guards.enter_context(patch(target, side_effect=AssertionError(
                'Network access is forbidden in offline tests; mock external services.')))
        diagnostic_directory = guards.enter_context(tempfile.TemporaryDirectory())
        guards.enter_context(patch('shared.diagnostics.BASE_DIR', Path(diagnostic_directory)))
        suite = unittest.defaultTestLoader.discover(str(Path(root) / 'tests'), pattern='test_*.py', top_level_dir=root)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
