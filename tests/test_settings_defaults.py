"""Portable settings and canonical TVR regression checks."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from dorado_gui.core.settings_store import SettingsStore, parse_patterns, validate_config

class SettingsDefaultsTests(unittest.TestCase):
    def test_canonical_rejected_and_defaults_clean(self):
        for text in ("TTAGGG", "ccctaa", "TCAGGG, TTAGGG"):
            with self.assertRaises(ValueError):
                parse_patterns(text)
        self.assertEqual(parse_patterns("tcaggg;TGAGGG"),["TCAGGG","TGAGGG"])
        with tempfile.TemporaryDirectory() as tmp:
            store=SettingsStore(Path(tmp)/"settings.json")
            validate_config(store.snapshot())
            config=store.snapshot()
            config["organism_specific"]["mouse"]["tvr_patterns"].append("TTAGGG")
            with self.assertRaises(ValueError): validate_config(config)

    def test_local_defaults_save_reload_and_legacy_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"settings.json"
            store=SettingsStore(file)
            for key in ("default_input_base","default_output_base"):
                self.assertTrue(Path(store.app_paths[key]).is_dir())
            self.assertTrue(Path(store.app_paths["nanotel_script"]).is_file())
            paths=copy.deepcopy(store.app_paths)
            paths["default_input_base"]=paths["default_output_base"]=tmp
            store.save_app_paths(paths)
            loaded=SettingsStore(file)
            self.assertIsNone(loaded.load_error)
            self.assertEqual(loaded.app_paths["default_input_base"],str(Path(tmp).resolve()))
            document=json.loads(file.read_text())
            document["app_paths"]["default_output_base"]=str(Path(tmp)/"other_computer")
            document["app_paths"].pop("default_input_base")
            document["profiles"]["Lab default"]["nanotel"]["tvr_patterns"].append("TTAGGG")
            file.write_text(json.dumps(document))
            migrated=SettingsStore(file)
            self.assertIsNone(migrated.load_error)
            self.assertEqual(migrated.app_paths["default_output_base"],str(Path.home()))
            self.assertNotIn("TTAGGG",migrated.snapshot()["nanotel"]["tvr_patterns"])
            self.assertIn("TTAGGG",json.loads(file.read_text())["profiles"]["Lab default"]["nanotel"]["tvr_patterns"])

if __name__ == "__main__": unittest.main()
