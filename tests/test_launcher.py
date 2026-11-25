import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import launcher


class LauncherTests(unittest.TestCase):
    def test_game_profiles_have_separate_prefixes(self):
        profiles = [launcher.load_profile(launcher.ROOT / f"profiles/{name}.json")
                    for name in ("lethal-company", "counter-strike-2")]
        prefixes = [launcher.settings(profile)[0] for profile in profiles]
        self.assertNotEqual(*prefixes)
        self.assertEqual(profiles[0]["steam_app_id"], "1966720")
        self.assertEqual(profiles[1]["steam_app_id"], "730")

    def test_blank_profile_cannot_launch_a_game(self):
        with self.assertRaisesRegex(ValueError, "steam_app_id"):
            launcher.load_profile(launcher.ROOT / "profiles/blank.json")

    def test_init_does_not_overwrite_existing_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "game.json"
            path.write_text("keep this")
            with self.assertRaises(FileExistsError):
                launcher.main(["init", "--output", str(path)])
            self.assertEqual(path.read_text(), "keep this")

    def test_rejects_executable_path_escape(self):
        for value in ("../game.exe", "/game.exe", "C:/game.exe", "..\\game.exe", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                launcher.relative_path(value)

    def test_plan_never_starts_a_process(self):
        with patch("subprocess.run") as run, contextlib.redirect_stdout(io.StringIO()):
            launcher.main(["plan", "--profile", str(launcher.ROOT / "profiles/lethal-company.json")])
        run.assert_not_called()

    def test_home_is_not_a_valid_prefix(self):
        with self.assertRaises(ValueError):
            launcher.settings({"name": "test", "prefix": str(Path.home())})

    def test_manifest_install_must_be_complete_and_contained(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            apps = prefix / "drive_c/Program Files (x86)/Steam/steamapps"
            apps.mkdir(parents=True)
            manifest = apps / "appmanifest_1.acf"
            for state, folder in [(1026, "Game"), (4, "..")]:
                manifest.write_text(f'"StateFlags" "{state}"\n"installdir" "{folder}"')
                with self.assertRaises(ValueError):
                    launcher.game_folder(prefix, "1")
            manifest.write_text('"StateFlags" "4"\n"installdir" "Game"')
            self.assertEqual(launcher.game_folder(prefix, "1"), (apps / "common/Game").resolve())

    def test_steam_workaround_requires_explicit_consent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wine = root / "wine"
            wine.touch()
            profile = launcher.load_profile(launcher.ROOT / "profiles/lethal-company.json")
            profile.update(wine_binary=str(wine), prefix=str(root / "prefix"))
            path = root / "profile.json"
            path.write_text(json.dumps(profile))
            with patch.object(launcher.sys, "platform", "darwin"), patch("platform.machine", return_value="arm64"), patch("subprocess.run") as run:
                with self.assertRaisesRegex(ValueError, "allow-steam-workaround"):
                    launcher.main(["steam", "--profile", str(path)])
            run.assert_not_called()

    def test_checksum_failure_keeps_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "download"
            target.write_bytes(b"original")
            def retrieve(url, path):
                Path(path).write_bytes(b"incorrect")
            with patch("urllib.request.urlretrieve", side_effect=retrieve):
                with self.assertRaisesRegex(ValueError, "Checksum"):
                    launcher.download("https://example.invalid/file", target, "0" * 64)
            self.assertEqual(target.read_bytes(), b"original")
            self.assertFalse(target.with_name("download.partial").exists())

    def test_wrapper_preserves_and_checks_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / "assets"
            assets.mkdir()
            wrapper = assets / "steamwebhelper.exe"
            wrapper.write_bytes(b"wrapper")
            helper = root / "prefix/drive_c/Program Files (x86)/Steam/bin/cef/cef.win64/steamwebhelper.exe"
            helper.parent.mkdir(parents=True)
            original_bytes = b"v" * 600000
            helper.write_bytes(original_bytes)
            with patch.object(launcher, "ASSETS", assets):
                launcher.apply_steam_fix(root / "prefix")
                launcher.apply_steam_fix(root / "prefix")
                backup = helper.with_name("steamwebhelper_real.exe")
                self.assertEqual(backup.read_bytes(), original_bytes)
                backup.unlink()
                with self.assertRaisesRegex(ValueError, "Original"):
                    launcher.apply_steam_fix(root / "prefix")


if __name__ == "__main__":
    unittest.main()
