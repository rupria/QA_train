"""Headless UI checks for interpreting only the current comparison's evidence."""
from __future__ import annotations

import io
import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from streamlit.testing.v1 import AppTest
import artifact_conversion as conversion
import qa_web_service as web
from test_flow_service import mapping, project_source, project_zip


class Uploaded(io.BytesIO):
    def __init__(self, name, data):
        super().__init__(data)
        self.name, self.size = name, len(data)


class FlowUiTests(unittest.TestCase):
    def setUp(self):
        self.parent = ROOT / ".test_tmp"
        self.parent.mkdir(exist_ok=True)
        self.work = self.parent / ("flow_ui_" + uuid4().hex)
        self.work.mkdir()
        self.addCleanup(self.cleanup)
        self.environment = patch.dict(os.environ, {"QA_WEB_WORKSPACE": str(self.work), "QA_WEB_ALLOW_LOCAL": "1"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=20).run()
        self.assert_clean()

    def cleanup(self):
        expected = self.work.absolute()
        if (self.work.resolve() != expected or expected.parent != self.parent.resolve()
                or conversion._is_reparse(self.work)):
            raise RuntimeError("Unsafe flow-UI fixture cleanup")
        shutil.rmtree(expected)

    def assert_clean(self):
        self.assertEqual(list(self.app.exception), [])

    def flow_view(self):
        # Native tabs keep their input widgets mounted; AppTest sees all panes.
        self.app.run()
        self.assert_clean()

    def prepared_compare(self, extra_change=False):
        session = self.app.session_state.work_session
        sources = [project_source(10), project_source(20)]
        if extra_change:
            sources[1] += "\ndef extra():\n    return 99\n"
        manifests = [web.prepare_upload(session, "project.zip", project_zip(source)) for source in sources]
        self.app.session_state.snapshots = [{"label": f"Ver.{side}", "manifest": m} for side, m in zip(("A", "B"), manifests)]
        self.app.run()
        for side, manifest in zip(("base", "target"), manifests):
            self.app.segmented_control(key=f"{side}_method").set_value("준비된 입력").run()
            self.app.selectbox(key=f"{side}_snapshot").select(manifest["id"]).run()
        self.app.button(key="run_pair").click().run()
        self.assert_clean()
        return self.app.session_state.pair_analysis

    def run_flow(self, extra_change=False):
        comparison = self.prepared_compare(extra_change=extra_change)
        self.flow_view()
        change = next(c for c in comparison["report"]["changes"] if c["symbol"] == "calculate_reward")
        self.app.selectbox(key="flow_change").select(change["id"]).run()
        self.app.button(key="interpret_flow").click().run()
        self.assert_clean()
        return self.app.session_state.flow_result

    def download_keys(self):
        return {item.key for item in self.app.get("download_button")}

    def test_no_comparison_has_no_interpret_action_or_downloads(self):
        self.flow_view()
        self.assertTrue(self.app.info or self.app.warning)
        self.assertFalse(any(button.key == "interpret_flow" for button in self.app.button))
        self.assertNotIn("flow_json", self.download_keys())

    def test_actual_flow_has_version_switches_and_downloads_without_reprocessing(self):
        import flow_ui
        with patch.object(flow_ui, "interpret_prepared", wraps=flow_ui.interpret_prepared) as interpret:
            result = self.run_flow()
            self.assertEqual(result["interpretation"]["mode"], "flow")
            text = "\n".join(item.value for item in self.app.markdown)
            self.assertIn("변경 지점의 값 의존이 receive", text)
            self.assertIn("player.balance", text)
            self.assertIn("calculate_reward", text)
            self.assertIn("변수 reward", text)
            self.assertEqual(interpret.call_count, 1)
            self.assertIn("flow_json", self.download_keys())
            self.assertIn("flow_md", self.download_keys())
            for version in ("Ver.A", "Ver.B", "연결 차이"):
                self.app.segmented_control(key="flow_version").set_value(version).run()
                self.assert_clean()
                self.assertEqual(interpret.call_count, 1)

    def test_changed_depth_hides_old_interpretation_downloads(self):
        self.run_flow()
        self.app.slider(key="flow_depth").set_value(2).run()
        self.assert_clean()
        self.assertNotIn("flow_json", self.download_keys())
        self.assertTrue(self.app.info or self.app.warning)

    def test_changed_code_selection_hides_old_interpretation_downloads(self):
        self.run_flow(extra_change=True)
        change = next(c for c in self.app.session_state.pair_analysis["report"]["changes"] if c["symbol"] == "extra")
        self.app.selectbox(key="flow_change").select(change["id"]).run()
        self.assert_clean()
        self.assertNotIn("flow_json", self.download_keys())
        self.assertTrue(self.app.info or self.app.warning)

    def test_changed_pair_selection_blocks_old_interpretation(self):
        self.run_flow()
        self.app.run()
        self.app.selectbox(key="target_snapshot").select(self.app.session_state.snapshots[0]["manifest"]["id"]).run()
        self.flow_view()
        self.assertNotIn("flow_json", self.download_keys())
        self.assertFalse(any(button.key == "interpret_flow" for button in self.app.button))
        self.assertTrue(self.app.info or self.app.warning)

    def test_package_inventory_comparison_has_no_source_interpret_action(self):
        session = self.app.session_state.work_session
        manifests = []
        for level in (1, 2):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr("AndroidManifest.xml", "Synthetic fixture")
                archive.writestr("assets/settings.json", '{"level":' + str(level) + "}")
            manifests.append(web.prepare_upload(session, "fixture.apk", buffer.getvalue()))
        self.app.session_state.snapshots = [{"label": f"Package {i}", "manifest": m} for i, m in enumerate(manifests)]
        self.app.run()
        for side, manifest in zip(("base", "target"), manifests):
            self.app.segmented_control(key=f"{side}_method").set_value("준비된 입력").run()
            self.app.selectbox(key=f"{side}_snapshot").select(manifest["id"]).run()
        self.app.button(key="run_pair").click().run()
        self.assert_clean()
        self.flow_view()
        self.assertTrue(self.app.info or self.app.warning)
        self.assertFalse(any(button.key == "interpret_flow" for button in self.app.button))
        self.assertNotIn("flow_json", self.download_keys())


if __name__ == "__main__":
    unittest.main()
