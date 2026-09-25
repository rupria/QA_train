from __future__ import annotations

import hashlib
import json
import plistlib
import shutil
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from uuid import uuid4
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import artifact_conversion
import ipa_support
from artifact_conversion import convert_input
from code_comparison import build_comparison


class IpaConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp_root = ROOT / ".test_tmp"
        self.temp_root.mkdir(exist_ok=True)
        self.work = self.temp_root / f"ipa_{uuid4().hex}"
        self.work.mkdir()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        if self.work.resolve().parent != self.temp_root.resolve() or self.work.is_symlink() or self.work.is_junction():
            raise RuntimeError("Refusing cleanup outside the test workspace")
        shutil.rmtree(self.work)

    def archive(self, entries, name="fixture.ipa"):
        path = self.work / name
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for key, data in entries:
                archive.writestr(key, data)
        return path

    def app(self, name="Game", *, metadata=None, binary=False, executable=True):
        info = {"CFBundleIdentifier": f"example.qa.{name.lower()}", "CFBundleDisplayName": name,
                "CFBundleShortVersionString": "1.2.3", "CFBundleVersion": "42",
                "MinimumOSVersion": "15.0", "CFBundleExecutable": name}
        info.update(metadata or {})
        fmt = plistlib.FMT_BINARY if binary else plistlib.FMT_XML
        entries = [(f"Payload/{name}.app/Info.plist", plistlib.dumps(info, fmt=fmt))]
        if executable:
            entries.append((f"Payload/{name}.app/{name}", b"\xcf\xfa\xed\xfe" + b"fixture; not executable"))
        return entries

    def test_xml_and_binary_plist_auto_detection_and_package_capabilities(self):
        for binary in (False, True):
            with self.subTest(binary=binary):
                source = self.archive(self.app(binary=binary), name=f"fixture{binary}.IPA")
                before = source.read_bytes()
                out = self.work / f"snapshot{binary}"
                result = convert_input(source, output=out)
                self.assertEqual(result["source"]["kind"], "ipa")
                self.assertEqual(result["status"], "prepared")
                self.assertEqual(result["representation"], "package_payload")
                self.assertEqual(result["source"]["sha256"], hashlib.sha256(before).hexdigest())
                self.assertEqual(source.read_bytes(), before)
                self.assertTrue(result["capabilities"]["package_inventory"])
                for flag in ("original_source", "python_ast", "restored_source"):
                    self.assertFalse(result["capabilities"][flag])
                app = result["package"]["applications"][0]
                self.assertEqual(app["bundle_identifier"], "example.qa.game")
                self.assertEqual(app["version"], "1.2.3")
                self.assertEqual(app["build"], "42")
                self.assertEqual(app["minimum_os_version"], "15.0")
                self.assertEqual(app["executable_path"], "Payload/Game.app/Game")
                self.assertTrue((out / "content/Payload/Game.app/Info.plist").is_file())
                self.assertFalse(result["restoration"]["original_equivalence"])
                with self.assertRaisesRegex(ValueError, "IPA"):
                    build_comparison(out, out)

    def test_all_top_level_apps_and_framework_extension_profile_files_preserved(self):
        entries = self.app() + self.app(name="Other", binary=True)
        extras = {
            "Payload/Game.app/Frameworks/Example.framework/Example": b"\xca\xfe\xba\xbe" + b"fixture fat candidate",
            "Payload/Game.app/PlugIns/Share.appex/Info.plist": plistlib.dumps({"CFBundleIdentifier": "example.qa.share"}),
            "Payload/Game.app/_CodeSignature/CodeResources": b"signature fixture; not verified",
            "Payload/Game.app/embedded.mobileprovision": b"profile fixture; not verified",
            "SwiftSupport/iphoneos/libswiftCore.dylib": b"\xcf\xfa\xed\xfe" + b"fixture",
        }
        entries += list(extras.items())
        source = self.archive(entries)
        out = self.work / "snapshot"
        result = convert_input(source, kind="ipa", output=out)
        self.assertEqual({app["bundle_path"] for app in result["package"]["applications"]}, {"Payload/Game.app", "Payload/Other.app"})
        self.assertTrue(set(extras).issubset({file["path"] for file in result["files"]}))
        for key, data in extras.items():
            self.assertEqual((out / "content" / key).read_bytes(), data)
        self.assertFalse(result["capabilities"]["restored_source"])

    def test_malformed_non_dict_or_oversized_plist_is_partial_with_payload_preserved(self):
        bad_date = b'''<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict><key>CFBundleExecutable</key><string>Game</string>
<key>unrelated_date</key><date>not-a-date</date></dict></plist>'''
        invalid = [b"broken plist", plistlib.dumps(["not a dictionary"]), bad_date]
        for i, data in enumerate(invalid):
            source = self.archive([(key, data if key.endswith("Info.plist") else value) for key, value in self.app()], name=f"broken{i}.ipa")
            out = self.work / f"snapshot{i}"
            result = convert_input(source, output=out)
            self.assertEqual(result["status"], "partial")
            self.assertTrue((out / "content/Payload/Game.app/Info.plist").is_file())
            self.assertTrue(result["warnings"])
            self.assertEqual(len(result["package"]["applications"]), 1)
        source = self.archive(self.app(), name="large.ipa")
        with mock.patch.object(ipa_support, "MAX_IPA_PLIST_BYTES", 8):
            result = convert_input(source, output=self.work / "large")
        self.assertEqual(result["status"], "partial")

    def test_missing_executable_and_bad_signature_are_reported_as_partial(self):
        for i, entries in enumerate((self.app(executable=False), [(key, b"not mach-o" if key.endswith("/Game") else data) for key, data in self.app()])):
            with self.subTest(i=i):
                result = convert_input(self.archive(entries, name=f"missing{i}.ipa"), output=self.work / f"out{i}")
                self.assertEqual(result["status"], "partial")
                self.assertTrue(result["warnings"])
                self.assertFalse(result["capabilities"]["restored_source"])
        mismatch = self.archive(self.app(metadata={"CFBundleExecutable": "game"}), name="case.ipa")
        result = convert_input(mismatch, output=self.work / "case")
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["warnings"])

    def test_executable_metadata_cannot_escape_bundle_or_invoke_a_program(self):
        outside = self.work / "outside"
        outside.write_bytes(b"keep outside file")
        for i, value in enumerate(("../outside", "/outside", "C:/outside", "Game/child", "Game\\child", "Game:stream", {"nested": "value"})):
            with self.subTest(value=value):
                result = convert_input(self.archive(self.app(metadata={"CFBundleExecutable": value}), name=f"unsafe{i}.ipa"), output=self.work / f"out{i}")
                self.assertEqual(result["status"], "partial")
                self.assertIsNone(result["package"]["applications"][0]["executable_path"])
                self.assertEqual(outside.read_bytes(), b"keep outside file")

    def test_top_level_app_missing_plist_is_not_silently_omitted(self):
        source = self.archive(self.app() + [("Payload/Other.app/Other", b"\xcf\xfa\xed\xfe")])
        result = convert_input(source, output=self.work / "snapshot")
        self.assertEqual(result["status"], "partial")
        self.assertEqual({app["bundle_path"] for app in result["package"]["applications"]}, {"Payload/Game.app", "Payload/Other.app"})

    def test_ipa_layout_requires_payload_app_with_direct_info_plist(self):
        for i, entries in enumerate(([('Info.plist', plistlib.dumps({}))], [('Payload/Game.app/Resources/Info.plist', plistlib.dumps({}))])):
            source = self.archive(entries, name=f"layout{i}.ipa")
            out = self.work / f"out{i}"
            with self.assertRaises(ValueError):
                convert_input(source, output=out)
            self.assertFalse(out.exists())

    def test_ipa_reuses_zip_path_collision_symlink_and_size_protection(self):
        bad_sets = [[("../outside", "bad")], [("Payload/Game.app/a", "a"), ("Payload/Game.app/A", "b")],
                    [("Payload/Game.app/a", "file"), ("Payload/Game.app/a/child", "nested")]]
        for i, bad in enumerate(bad_sets):
            source = self.archive(self.app() + bad, name=f"bad{i}.ipa")
            with self.assertRaises(ValueError):
                convert_input(source, output=self.work / f"out{i}")
        link = zipfile.ZipInfo("Payload/Game.app/link")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        source = self.archive(self.app() + [(link, "../../outside")], name="link.ipa")
        with self.assertRaises(ValueError):
            convert_input(source, output=self.work / "link")
        source = self.archive(self.app(), name="limit.ipa")
        with mock.patch.object(artifact_conversion, "MAX_APK_MEMBERS", 1):
            with self.assertRaisesRegex(ValueError, "limit"):
                convert_input(source, output=self.work / "limit")

    def test_ipa_source_root_and_jadx_are_rejected(self):
        source = self.archive(self.app())
        for kwargs in ({"source_root": "Payload"}, {"jadx": "any-tool"}):
            with self.assertRaises(ValueError):
                convert_input(source, output=self.work / "bad", **kwargs)
        self.assertFalse((self.work / "bad").exists())

    def test_ipa_cli_reports_partial_metadata_with_exit_two(self):
        source = self.archive(self.app(executable=False))
        out = self.work / "snapshot"
        result = subprocess.run([sys.executable, "-B", str(ROOT / "ast_analyzer.py"), "convert", str(source), "--kind", "ipa", "--output", str(out)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2, result.stderr)
        data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "partial")


if __name__ == "__main__":
    unittest.main()
