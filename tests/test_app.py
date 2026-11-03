"""Smoke-Tests (unittest + streamlit.testing.v1.AppTest).

Laufen gegen temporäre Kopien von Workspace und Qdrant-Datenbank, damit weder eine
laufende App (Qdrant-Sperre) noch die echte Main.daml berührt werden.

Ausführen:  .venv/bin/python -m unittest discover -s tests -v
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import daml_runner  # noqa: E402
import lessons  # noqa: E402
import llm  # noqa: E402
import rag  # noqa: E402
import settings  # noqa: E402

SAMPLE_OUTPUT = """SDK 3.4.11 has been released!

Test Summary

daml/Main.daml:setup: ok, 1 active contracts, 2 transactions.
daml/Main.daml:broken: failed, 0 active contracts, 0 transactions.
Modules internal to this package:
- Internal templates
  1 defined
"""


class SandboxCase(unittest.TestCase):
    """Leitet alle Pfade auf ein temporäres Verzeichnis um."""

    def setUp(self):
        self._saved = {k: getattr(settings, k) for k in
                       ("QDRANT_PATH", "WORKSPACE_DIR", "DAML_FILE", "DAML_YAML")}
        self.tmp = Path(tempfile.mkdtemp(prefix="daml-sandbox-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        shutil.copytree(ROOT / "workspace", self.tmp / "workspace")
        settings.WORKSPACE_DIR = self.tmp / "workspace"
        settings.DAML_FILE = settings.WORKSPACE_DIR / "daml" / "Main.daml"
        settings.DAML_YAML = settings.WORKSPACE_DIR / "daml.yaml"
        settings.QDRANT_PATH = str(self.tmp / "qdrant")
        rag.close_client()
        self.addCleanup(self._restore)

    def _restore(self):
        rag.close_client()
        for key, value in self._saved.items():
            setattr(settings, key, value)


class ParsingTests(unittest.TestCase):
    def test_parse_test_summary(self):
        rows = daml_runner.parse_test_summary(SAMPLE_OUTPUT)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Script"], "daml/Main.daml:setup")
        self.assertEqual(rows[0]["Result"], "ok")
        self.assertEqual(rows[0]["Active contracts"], 1)
        self.assertEqual(rows[0]["Transactions"], 2)
        self.assertEqual(rows[1]["Result"], "failed, 0 active contracts, 0 transactions")

    def test_split_coverage(self):
        main, coverage = daml_runner.split_coverage(SAMPLE_OUTPUT)
        self.assertNotIn("Internal templates", main)
        self.assertTrue(coverage.startswith(settings.COVERAGE_MARKER))

    def test_trim_for_prompt_limits_length(self):
        long_output = "x" * (settings.MAX_OUTPUT_CHARS * 3)
        trimmed = daml_runner.trim_for_prompt(long_output)
        self.assertLessEqual(len(trimmed), settings.MAX_OUTPUT_CHARS + 20)
        self.assertNotIn("Internal templates", daml_runner.trim_for_prompt(SAMPLE_OUTPUT))

    def test_prompt_budget(self):
        payload = llm.build_user_payload("c" * 50000, "d" * 50000, "o" * 50000, "q" * 50000,
                                         settings.LOCAL_PROMPT_CHARS)
        self.assertLess(len(payload), settings.LOCAL_PROMPT_CHARS + 600)

    def test_run_rejects_unknown_command(self):
        with self.assertRaises(ValueError):
            daml_runner.run("rm -rf /")


class LessonTests(SandboxCase):
    def test_list_and_starter(self):
        names = lessons.list_lessons()
        self.assertIn("01_propose_accept.md", names)
        self.assertIsNotNone(lessons.starter_for("01_propose_accept.md"))
        self.assertIsNone(lessons.starter_for("99_missing.md"))

    def test_load_starter_creates_backup(self):
        daml_runner.write_source("-- my work\n")
        backup = lessons.load_starter("01_propose_accept.md")
        self.assertIsNotNone(backup)
        self.assertEqual(backup.read_text(encoding="utf-8"), "-- my work\n")
        self.assertIn("AssetProposal", daml_runner.read_source())


class RagTests(SandboxCase):
    def test_index_and_retrieve(self):
        self.assertEqual(rag.index_count(), 0)
        count = rag.build_index()
        self.assertGreaterEqual(count, 3)
        self.assertEqual(rag.index_count(), count)
        context = rag.retrieve("How does propose accept work with signatories?")
        self.assertIn("01_propose_accept.md", context)

    def test_lock_error_is_readable(self):
        rag.get_client()
        from qdrant_client import QdrantClient
        with self.assertRaises(RuntimeError):
            QdrantClient(path=settings.QDRANT_PATH)


@unittest.skipUnless(daml_runner.daml_available(), "daml SDK not installed")
class DamlTests(SandboxCase):
    def test_daml_test_runs_green(self):
        result = daml_runner.run("test")
        self.assertTrue(result.ok, result.output or result.error)
        rows = daml_runner.parse_test_summary(result.output)
        self.assertTrue(rows and rows[0]["Result"] == "ok")


class UiTests(SandboxCase):
    def _app(self):
        from streamlit.testing.v1 import AppTest
        return AppTest.from_file(str(ROOT / "src" / "app.py"), default_timeout=120)

    def test_all_tabs_render_without_exception(self):
        at = self._app().run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        self.assertEqual(len(at.tabs), 3)
        self.assertEqual(at.text_area[0].value, daml_runner.read_source())

    def test_ask_without_api_key_shows_error(self):
        at = self._app().run()
        at.sidebar.selectbox[0].select(settings.ANTHROPIC_PROVIDER).run()
        at.sidebar.text_input[0].set_value("").run()
        at.chat_input[0].set_value("What is a signatory?").run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        self.assertTrue(any("API key" in e.value for e in at.error))


if __name__ == "__main__":
    unittest.main()
