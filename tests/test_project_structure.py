"""Verify stable package paths and documentation contracts after code moves.

These offline checks prevent private data relocation and missing module descriptions.
"""
import ast
from pathlib import Path
import unittest
from shared.paths import PROJECT_ROOT
from shared.local_storage import PROFILE_FILE, EVALUATIONS_FILE
from jobs.agent import BASE_DIR


class ProjectStructureTests(unittest.TestCase):
    def test_private_paths_remain_at_root(self):
        self.assertEqual(PROFILE_FILE, PROJECT_ROOT / 'user_profile.json')
        self.assertEqual(EVALUATIONS_FILE, PROJECT_ROOT / '.local_data' / 'evaluations.json')
        self.assertEqual(BASE_DIR, PROJECT_ROOT)
        self.assertTrue((BASE_DIR / 'agent_instructions.md').is_file())

    def test_own_modules_have_responsibility_docstrings(self):
        paths = list(PROJECT_ROOT.glob('*.py'))
        for folder in ('profiles', 'jobs', 'chat', 'memory', 'resumes', 'shared', 'tests'):
            paths.extend((PROJECT_ROOT / folder).glob('*.py'))
        for path in paths:
            with self.subTest(path=path.relative_to(PROJECT_ROOT)):
                self.assertTrue(path.read_text().startswith('"""'))
                self.assertTrue(ast.get_docstring(ast.parse(path.read_text())))
