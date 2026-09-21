"""篩(agent/skill/junk)の回帰テスト。依存は stdlib のみ(unittest)。

    python3 -m unittest tests.test_sieves
    (または py/ から PYTHONPATH=.. python3 -m unittest tests.test_sieves)
"""
from __future__ import annotations

import unittest

from furui.buckets import guess_agent, guess_junk, guess_skill


class AgentSieveTest(unittest.TestCase):
    def test_persona_names_are_agent(self):
        # 「人名ならエージェント」: persona 命名で Jev を呼ばず確定する
        for rel in [
            "mito-coordinator/",
            "garden-agent/",
            "architecture-agent/",
            "strategic-advisors/",
            "advisors/",
            "advisors_meeting/",
        ]:
            self.assertEqual(guess_agent(rel, "dir contains src, tests"), "name is persona (" + rel.rstrip("/") + ")")

    def test_clean_names_are_not_agent(self):
        for rel in ["web/", "voodoo/", "sakura-macros/", "fast-go/", "tests/", "nix/"]:
            self.assertIsNone(guess_agent(rel, "dir contains src"))

    def test_junk_zone_marker(self):
        # Windows Zone.Identifier は恒久ゴミ。ふるいにかける前に捨てる
        self.assertEqual(
            guess_junk("docs/SKILL.md:Zone.Identifier"),
            "windows-zone-marker",
        )


class SkillSieveTest(unittest.TestCase):
    def test_cli_tools_are_skill(self):
        # 「CLI メインでスキルがくっついてくる」: 名前/文面で確定できるもの
        self.assertEqual(guess_skill("sakura-macros/", "dir contains ai-assist.js"), "name is CLI/tool (sakura-macros)")
        self.assertEqual(guess_skill("jev-video-pipeline/", "dir contains make_video.sh"), "name is CLI/tool (jev-video-pipeline)")
        self.assertEqual(
            guess_skill("fast-go/", "A colorful terminal speed test with a TUI."),
            "desc shows a CLI command/script",
        )

    def test_listing_does_not_hint_skill(self):
        # 「dir contains ... cli ...」の一覧は CLI 証拠にならない(誤爆防止)
        self.assertIsNone(guess_skill("tests/", "dir contains acp, agent, ci, cli, computer_use"))

    def test_plain_dirs_are_not_skill(self):
        self.assertIsNone(guess_skill("web/", "dir contains src, public"))
        self.assertIsNone(guess_skill("insights/", "dir contains 20260529_ajax.md, keywords"))

    def test_skill_and_agent_do_not_collide(self):
        # garden-agent は「agent」が先勝ち(agent 篩が skill 篩より先に走る)
        rel = "garden-agent/"
        self.assertEqual(guess_agent(rel, "dir contains garden-scan.sh"), "name is persona (" + rel.rstrip("/") + ")")
        self.assertIsNone(guess_skill(rel, "dir contains garden-scan.sh"))


if __name__ == "__main__":
    unittest.main()