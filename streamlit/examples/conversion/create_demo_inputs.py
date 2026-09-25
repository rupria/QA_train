"""Generate a tiny engine project and non-installable APK/IPA ZIP fixtures."""
from pathlib import Path
import argparse
import json
import plistlib
import zipfile


def create_inputs(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    project = output / "unity_project"
    (project / "Assets" / "Scripts").mkdir(parents=True)
    (project / "ProjectSettings").mkdir()
    (project / "Library").mkdir()
    (project / "Assets" / "Scripts" / "LoginPolicy.cs").write_text(
        "public static class LoginPolicy { public static bool Allowed(int age) => age <= 30; }\n", encoding="utf-8")
    (project / "ProjectSettings" / "ProjectVersion.txt").write_text("m_EditorVersion: 6000.0.0f1\n", encoding="utf-8")
    (project / "Library" / "cache.bin").write_bytes(b"fixture engine cache")
    apk = output / "package_fixture.apk"
    with zipfile.ZipFile(apk, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("AndroidManifest.xml", '<manifest package="example.qa.fixture"/>')
        archive.writestr("classes.dex", b"dex\n035\x00" + b"\x00" * 104)
        archive.writestr("lib/arm64-v8a/libil2cpp.so", b"\x7fELF" + b"fixture; not executable")
        archive.writestr("assets/bin/Data/il2cpp_data/Metadata/global-metadata.dat", b"fixture metadata")
        archive.writestr("res/values/strings.xml", "<resources><string name='app_name'>QA fixture</string></resources>")
    ipa = output / "ios_package_fixture.ipa"
    with zipfile.ZipFile(ipa, "w", zipfile.ZIP_DEFLATED) as archive:
        info = {"CFBundleIdentifier": "example.qa.fixture", "CFBundleDisplayName": "QA fixture",
                "CFBundleShortVersionString": "1.0", "CFBundleVersion": "1", "CFBundleExecutable": "QAFixture",
                "MinimumOSVersion": "15.0"}
        archive.writestr("Payload/QAFixture.app/Info.plist", plistlib.dumps(info, fmt=plistlib.FMT_BINARY))
        archive.writestr("Payload/QAFixture.app/QAFixture", b"\xcf\xfa\xed\xfe" + b"fixture; not executable")
        archive.writestr("Payload/QAFixture.app/Frameworks/Example.framework/Example", b"\xcf\xfa\xed\xfe" + b"framework fixture")
        archive.writestr("Payload/QAFixture.app/_CodeSignature/CodeResources", b"unverified signature fixture")
        archive.writestr("Payload/QAFixture.app/embedded.mobileprovision", b"unverified provisioning fixture")
    (output / "README.txt").write_text(
        "Synthetic fixtures only. APK and IPA fixtures are ZIPs, not installable Android/iOS builds.\n"
        "C# / DEX / ELF / Mach-O magic contents are for input classification and extraction checks, not execution or decompilation.\n",
        encoding="utf-8")
    return {"engine_project": str(project), "apk_fixture": str(apk), "ipa_fixture": str(ipa)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="A new folder outside any source input")
    args = parser.parse_args()
    print(json.dumps(create_inputs(args.output), ensure_ascii=False, indent=2))
