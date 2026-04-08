import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "deep_analyze.py"
ANALYSIS_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "灵均Kikky_analysis.json"


class DeepAnalyzeCliTest(unittest.TestCase):
    def test_default_mode_keeps_legacy_docx_and_generates_skill_folder_contract(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    str(ANALYSIS_FIXTURE),
                    "灵均Kikky",
                    "-o",
                    tmpdir,
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                self.fail(
                    "deep_analyze.py should succeed in default mode.\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            output_dir = Path(tmpdir)
            process_dir = output_dir / "_过程文件" / "原始素材"

            for name in [
                "灵均Kikky_博主深度拆解.docx",
                "灵均Kikky_内容公式总结.docx",
                "灵均Kikky_选题素材库.docx",
                "灵均Kikky_全量笔记结构化分析.docx",
            ]:
                self.assertTrue((output_dir / name).exists(), name)

            self.assertTrue((process_dir / "灵均Kikky_数据底稿.md").exists())
            task_path = process_dir / "灵均Kikky_AI蒸馏任务.md"
            self.assertTrue(task_path.exists())
            self.assertFalse((process_dir / "灵均Kikky_AI深度分析Prompt.md").exists())

            content = task_path.read_text(encoding="utf-8")
            self.assertIn("灵均Kikky_创作指南.skill/", content)
            self.assertIn("SKILL.md", content)
            self.assertNotIn("**输出文件名**：`灵均Kikky_创作指南.skill.md`", content)

    def test_mode_b_switches_distill_task_to_creative_gene_skill_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    str(ANALYSIS_FIXTURE),
                    "灵均Kikky",
                    "-o",
                    tmpdir,
                    "--mode",
                    "B",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                self.fail(
                    "deep_analyze.py should succeed in mode B.\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            task_path = Path(tmpdir) / "_过程文件" / "原始素材" / "灵均Kikky_AI蒸馏任务.md"
            content = task_path.read_text(encoding="utf-8")
            self.assertIn("灵均Kikky_创作基因.skill/", content)
            self.assertIn("SKILL.md", content)
            self.assertIn("你的思考模式", content)
            self.assertNotIn("**输出文件名**：`灵均Kikky_创作指南.skill.md`", content)


if __name__ == "__main__":
    unittest.main()
