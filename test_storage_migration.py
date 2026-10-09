"""Regression checks for file renames and backward-compatible JSON fields."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import local_storage
from evaluation import Recommendation
from skills import SkillSuggestion
from test_interface import sample_listing


class StorageMigrationTests(unittest.TestCase):
    def test_legacy_files_move_without_content_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_bytes = b'{"puesto": "Test", "unknown": {"keep": true}}\n'
            results_bytes = b'{"version": 3, "evaluaciones": [], "custom": true}\n'
            (root / "perfil.json").write_bytes(profile_bytes)
            (root / ".datos").mkdir()
            (root / ".datos" / "evaluaciones.json").write_bytes(results_bytes)
            (root / ".datos" / "diagnostico.json").write_bytes(b'{}\n')
            with patch.object(local_storage, "PROFILE_FILE", root / "user_profile.json"), \
                 patch.object(local_storage, "EVALUATIONS_FILE", root / ".local_data" / "evaluations.json"):
                self.assertTrue(local_storage.load_profile()["unknown"]["keep"])
                self.assertTrue(local_storage.load_evaluations()["custom"])
            self.assertEqual((root / "user_profile.json").read_bytes(), profile_bytes)
            self.assertEqual((root / ".local_data" / "evaluations.json").read_bytes(), results_bytes)
            self.assertTrue((root / ".local_data" / "diagnostics.json").exists())
            local_storage.migrate_legacy_files(root)
            self.assertFalse((root / "perfil.json").exists())

    def test_existing_destinations_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "perfil.json").write_bytes(b'{"legacy": true}')
            (root / "user_profile.json").write_bytes(b'{"current": true}')
            local_storage.migrate_legacy_files(root)
            self.assertEqual((root / "perfil.json").read_bytes(), b'{"legacy": true}')
            self.assertEqual((root / "user_profile.json").read_bytes(), b'{"current": true}')

    def test_english_attributes_keep_legacy_wire_format(self):
        listing = sample_listing()
        saved = listing.model_dump()
        self.assertIn("puesto", saved)
        self.assertNotIn("role", saved)
        self.assertEqual(Recommendation.model_validate(saved).role, listing.role)
        self.assertEqual(json.loads(listing.model_dump_json()), saved)
        self.assertIn("puesto", Recommendation.model_json_schema()["properties"])
        suggestion = SkillSuggestion.model_validate({"skill": "SQL", "campo": "formacion",
            "entrada_id": "test", "cita": "SQL"})
        self.assertEqual(suggestion.entry_id, "test")
        self.assertEqual(suggestion.model_dump()["entrada_id"], "test")
        self.assertEqual(json.loads(json.dumps(saved)), saved)
