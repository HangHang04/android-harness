from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from android_harness.errors import HarnessError
from android_harness.skill_bundle import install_skill, skill_text


class SkillBundleTests(unittest.TestCase):
    def test_skill_text_has_required_frontmatter(self) -> None:
        text = skill_text()
        self.assertTrue(text.startswith("---\nname: android-harness\n"))
        self.assertIn("description:", text)

    def test_install_copies_complete_bundle_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "android-harness"

            installed = install_skill(destination)
            self.assertEqual("installed", installed["status"])
            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertTrue((destination / "agents" / "openai.yaml").is_file())
            self.assertTrue(
                (destination / "references" / "wireless-debugging.md").is_file()
            )
            self.assertTrue(
                (destination / "scripts" / "invoke-android-harness.ps1").is_file()
            )

            unchanged = install_skill(destination)
            self.assertEqual("unchanged", unchanged["status"])

    def test_install_refuses_a_different_existing_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "android-harness"
            destination.mkdir()
            (destination / "SKILL.md").write_text("different", encoding="utf-8")

            with self.assertRaises(HarnessError) as caught:
                install_skill(destination)

            self.assertEqual("skill_destination_exists", caught.exception.kind)

    def test_install_requires_the_expected_directory_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "wrong-name"

            with self.assertRaises(HarnessError) as caught:
                install_skill(destination)

            self.assertEqual("invalid_skill_destination", caught.exception.kind)


if __name__ == "__main__":
    unittest.main()
