"""Evidence-based flow interpretation through verified, session-owned inputs."""
from __future__ import annotations

import copy
import io
import json
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
from ast_runtime import AST_ROOT
import artifact_conversion as conversion
import qa_web_service as web


def project_source(multiplier=10, receiver="receive"):
    return (f"def calculate_reward(level):\n    return level * {multiplier}\n\n"
            f"def {receiver}(player, amount):\n    player.balance = amount\n\n"
            "def claim(player, level):\n    reward = calculate_reward(level)\n"
            f"    {receiver}(player, reward)\n    return reward\n\n"
            "raise RuntimeError('Analyzed source must never execute')\n")


def project_zip(source):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("app.py", source)
    return data.getvalue()


def mapping():
    return {"features": [{"id": "REWARD", "name": "보상 지급",
        "entry_points": [{"file": "app.py", "symbol": "claim"}], "tc_ids": ["TC-REWARD-001"]}]}


class FlowServiceTests(unittest.TestCase):
    def setUp(self):
        self.parent = ROOT / ".test_tmp"
        self.parent.mkdir(exist_ok=True)
        self.work = self.parent / ("flow_service_" + uuid4().hex)
        self.work.mkdir()
        self.addCleanup(self.cleanup)
        self.environment = patch.dict(os.environ, {"QA_WEB_WORKSPACE": str(self.work), "QA_WEB_ALLOW_LOCAL": "1"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.session = web.new_session()
        self.base = web.prepare_upload(self.session, "project.zip", project_zip(project_source(10)))
        self.target = web.prepare_upload(self.session, "project.zip", project_zip(project_source(20)))
        self.report = web.compare_prepared(self.session, self.base, self.target, features_json=mapping())
        self.change = next(c for c in self.report["changes"] if c["symbol"] == "calculate_reward")

    def cleanup(self):
        expected = self.work.absolute()
        if (self.work.resolve() != expected or expected.parent != self.parent.resolve()
                or conversion._is_reparse(self.work)):
            raise RuntimeError("Unsafe flow-service fixture cleanup")
        shutil.rmtree(expected)

    def interpret(self, **overrides):
        from qa_flow_service import interpret_prepared
        values = dict(session=self.session, base_manifest=self.base, target_manifest=self.target,
            comparison_report=self.report, change_id=self.change["id"], max_depth=10)
        values.update(overrides)
        return interpret_prepared(values["session"], values["base_manifest"], values["target_manifest"],
            values["comparison_report"], values["change_id"], max_depth=values["max_depth"])

    def test_actual_project_flow_with_feature_mapping_does_not_execute_source(self):
        result = self.interpret()
        self.assertEqual(result["mode"], "flow")
        self.assertEqual(result["change_id"], self.change["id"])
        self.assertTrue(result["run_id"])
        self.assertEqual(result["root_symbol"]["id"], "app.py::calculate_reward")
        self.assertEqual(set(result["versions"]), {"base", "target"})
        for version in result["versions"].values():
            self.assertTrue(version["nodes"])
            self.assertTrue(version["edges"])
            self.assertIn("unresolved", version)
            self.assertIn("truncated", version)
            kinds = {edge["kind"] for edge in version["edges"]}
            self.assertTrue({"return", "assignment", "value_argument", "parameter_binding", "attribute_write"}.issubset(kinds))
            graph = json.dumps(version, ensure_ascii=False)
            for evidence in ("calculate_reward", "reward", "receive", "balance", "app.py"):
                self.assertIn(evidence, graph)
        self.assertEqual([f["id"] for f in result["features"]], ["REWARD"])
        self.assertEqual(result["features"][0]["tc_ids"], ["TC-REWARD-001"])
        self.assertTrue(result["features"][0]["flow_evidence"])
        self.assertTrue(result["limitations"])
        self.assertEqual((Path(self.base["output_path"]) / "content" / "app.py").read_text(encoding="utf-8"), project_source(10))

    def test_changed_receiver_creates_distinct_version_connections(self):
        target = web.prepare_upload(self.session, "project.zip", project_zip(project_source(20, "save_reward")))
        report = web.compare_prepared(self.session, self.base, target, features_json=mapping())
        change = next(c for c in report["changes"] if c["symbol"] == "calculate_reward")
        result = self.interpret(target_manifest=target, comparison_report=report, change_id=change["id"])
        self.assertTrue(result["connection_changes"]["added"])
        self.assertTrue(result["connection_changes"]["deleted"])
        self.assertIn("save_reward", json.dumps(result["versions"]["target"]))

    def test_unknown_callback_is_explicitly_unresolved_without_invented_receiver(self):
        source = project_source(20).replace("def claim(player, level):", "def claim(player, level, callback):")
        source = source.replace("receive(player, reward)", "callback(player, reward)")
        target = web.prepare_upload(self.session, "project.zip", project_zip(source))
        report = web.compare_prepared(self.session, self.base, target)
        change = next(c for c in report["changes"] if c["symbol"] == "calculate_reward")
        result = self.interpret(target_manifest=target, comparison_report=report, change_id=change["id"])
        graph = result["versions"]["target"]
        self.assertIn("callback", json.dumps(graph["unresolved"]))
        bindings = [edge for edge in graph["edges"] if edge["kind"] == "parameter_binding"]
        self.assertFalse(any("receive" in json.dumps(edge) for edge in bindings))

    def test_other_session_cannot_interpret_prepared_inputs(self):
        with self.assertRaises(ValueError):
            self.interpret(session=web.new_session())

    def test_modified_prepared_source_is_rejected(self):
        (Path(self.target["output_path"]) / "content" / "app.py").write_text("def changed(): return 99\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.interpret()

    def test_report_bound_to_different_snapshot_is_rejected(self):
        report = copy.deepcopy(self.report)
        report["conversion_inputs"]["target"]["snapshot_path"] = self.base["output_path"]
        with self.assertRaises(ValueError):
            self.interpret(comparison_report=report)

    def test_report_without_conversion_provenance_is_rejected(self):
        report = copy.deepcopy(self.report)
        report.pop("conversion_inputs")
        with self.assertRaises(ValueError):
            self.interpret(comparison_report=report)

    def test_unrecognized_change_id_is_rejected(self):
        with self.assertRaises(ValueError):
            self.interpret(change_id="CODE-NOT-IN-THIS-REPORT")

    def test_malformed_conversion_provenance_is_rejected(self):
        for inputs in (None, [], "invalid", {"base": None}, {"base": []}):
            with self.subTest(inputs=inputs):
                report = copy.deepcopy(self.report)
                report["conversion_inputs"] = inputs
                with self.assertRaises(ValueError):
                    self.interpret(comparison_report=report)

    def test_inventory_report_cannot_be_interpreted_as_source_flow(self):
        inventory = web.compare_inventory(self.base, self.target)
        with self.assertRaises(ValueError):
            self.interpret(comparison_report=inventory)

    def test_apk_payload_is_never_reclassified_as_original_source(self):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr("AndroidManifest.xml", "Synthetic package fixture")
            archive.writestr("assets/app.py", project_source(20))
        package = web.prepare_upload(self.session, "fixture.apk", payload.getvalue())
        report = copy.deepcopy(self.report)
        report["conversion_inputs"]["target"]["snapshot_path"] = package["output_path"]
        with self.assertRaises(ValueError):
            self.interpret(target_manifest=package, comparison_report=report)

    def test_depth_limits_reject_invalid_values(self):
        for depth in (0, 31, 101):
            with self.subTest(depth=depth), self.assertRaises(ValueError):
                self.interpret(max_depth=depth)

    def test_limited_traversal_explicitly_marks_incomplete_connections(self):
        result = self.interpret(max_depth=1)
        self.assertTrue(any(version["truncated"] for version in result["versions"].values()))


if __name__ == "__main__":
    unittest.main()
