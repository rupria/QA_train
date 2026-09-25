"""IPA bundle inventory and declared metadata, without execution or SDK tools."""
from __future__ import annotations

import plistlib
import stat
from pathlib import Path, PurePosixPath
from xml.parsers.expat import ExpatError


MAX_IPA_PLIST_BYTES = 1024 * 1024
MACH_MAGICS = {
    b"\xfe\xed\xfa\xce": "mach_o_32_big_endian_candidate",
    b"\xce\xfa\xed\xfe": "mach_o_32_little_endian_candidate",
    b"\xfe\xed\xfa\xcf": "mach_o_64_big_endian_candidate",
    b"\xcf\xfa\xed\xfe": "mach_o_64_little_endian_candidate",
    b"\xca\xfe\xba\xbe": "fat_big_endian_candidate",
    b"\xbe\xba\xfe\xca": "fat_little_endian_candidate",
    b"\xca\xfe\xba\xbf": "fat64_big_endian_candidate",
    b"\xbf\xba\xfe\xca": "fat64_little_endian_candidate",
}
_FIELDS = {
    "bundle_identifier": "CFBundleIdentifier", "display_name": "CFBundleDisplayName",
    "name": "CFBundleName", "version": "CFBundleShortVersionString",
    "build": "CFBundleVersion", "minimum_os_version": "MinimumOSVersion",
    "executable": "CFBundleExecutable",
}


def validate_ipa_layout(entries) -> list[str]:
    """Shared ZIP validation precedes this check; retain every top-level app."""
    bundles, valid_plists = set(), set()
    for entry, key in entries:
        parts = PurePosixPath(key).parts
        if len(parts) < 2 or parts[0] != "Payload" or not parts[1].endswith(".app"):
            continue
        if parts[1] == ".app":
            raise ValueError("IPA app bundle name must be nonempty.")
        bundle = "/".join(parts[:2])
        if len(parts) > 2 or entry.is_dir():
            bundles.add(bundle)
        if len(parts) == 3 and parts[2] == "Info.plist":
            if entry.is_dir():
                raise ValueError("IPA app Info.plist must be a file, not a directory.")
            valid_plists.add(bundle)
    if not valid_plists:
        raise ValueError("IPA requires Payload/<name>.app/Info.plist as a direct file.")
    return sorted(bundles)


def _bounded_file(content: Path, key: str) -> Path:
    root = content.resolve()
    candidate = content / key
    # Extracted paths are already ZIP-validated; this also bounds independent
    # callers and refuses any new links/reparse points created after extraction.
    if PurePosixPath(key).is_absolute() or ".." in PurePosixPath(key).parts or "\\" in key:
        raise ValueError("IPA file path is outside the package content.")
    for relative in candidate.relative_to(content).parents:
        parent = content / relative
        if parent.exists() and (parent.is_symlink() or parent.is_junction()):
            raise ValueError("IPA file path traverses a link/junction.")
    info = candidate.lstat()
    if (not stat.S_ISREG(info.st_mode) or candidate.is_symlink()
            or getattr(info, "st_file_attributes", 0) & 0x400
            or not candidate.resolve().is_relative_to(root)):
        raise ValueError("IPA metadata/binary candidate is not a regular bounded file.")
    return candidate


def _header(content: Path, key: str) -> bytes:
    with _bounded_file(content, key).open("rb") as reader:
        return reader.read(4)


def _executable_basename(value: str) -> bool:
    reserved = {"con", "prn", "aux", "nul", *[f"com{i}" for i in "123456789¹²³"],
                *[f"lpt{i}" for i in "123456789¹²³"]}
    return bool(value and value.strip() and value not in {".", ".."}
                and not value.endswith((".", " ")) and len(value) <= 255
                and not any(ord(c) < 32 or c in '/\\:<>"|?*' for c in value)
                and value.split(".", 1)[0].casefold() not in reserved)


def inspect_ipa(content: Path, manifest: dict, bundle_paths: list[str]) -> None:
    """Parse bounded top-level plist declarations and classify binary candidates."""
    content = Path(content).absolute()
    package = manifest["package"] = dict(format="IPA", application_scope="top_level_payload_apps",
        metadata_provenance="unverified_bundle_declarations", applications=[],
        signature_verification="not_performed", provisioning_verification="not_performed")
    warnings = manifest.setdefault("warnings", [])
    records = {record["path"]: record for record in manifest.get("files", [])}
    executable_paths = set()

    def warning(app, message):
        text = f"{app['bundle_path']}: {message}"
        app["warnings"].append(text)
        warnings.append(text)
        manifest["status"] = "partial"

    for bundle in sorted(bundle_paths):
        app = dict(bundle_path=bundle, **{key: None for key in _FIELDS},
                   executable_path=None, executable_format=None, metadata_status="unavailable",
                   executable_status="unavailable", encryption_status="unknown",
                   symbol_status="unknown", warnings=[])
        package["applications"].append(app)
        try:
            plist_path = _bounded_file(content, bundle + "/Info.plist")
            if plist_path.stat().st_size > MAX_IPA_PLIST_BYTES:
                raise ValueError("Info.plist exceeds the configured read-size limit.")
            with plist_path.open("rb") as reader:
                data = reader.read(MAX_IPA_PLIST_BYTES + 1)
            if len(data) > MAX_IPA_PLIST_BYTES:
                raise ValueError("Info.plist exceeds the configured read-size limit.")
            try:
                values = plistlib.loads(data)
            except (AttributeError, IndexError, KeyError) as exc:
                # Some malformed plist values (for example invalid XML dates)
                # escape plistlib as implementation exceptions. Bound this
                # conversion to the parser call, not the rest of inspection.
                raise ValueError(f"Malformed Info.plist: {exc}") from exc
            if not isinstance(values, dict):
                raise ValueError("Info.plist must contain a dictionary.")
            app["metadata_status"] = "parsed_unverified"
            app["plist_format"] = "binary" if data.startswith(b"bplist00") else "xml"
            for field, key in _FIELDS.items():
                value = values.get(key)
                if value is None:
                    continue
                if not isinstance(value, str):
                    warning(app, f"{key} is not a string; declaration omitted.")
                else:
                    app[field] = value
        except (OSError, ValueError, TypeError, OverflowError, ExpatError, RecursionError) as exc:
            warning(app, f"Info.plist metadata unavailable: {exc}")
            continue

        name = app["executable"]
        if name is None:
            warning(app, "CFBundleExecutable is missing or not a string.")
            continue
        if not _executable_basename(name):
            warning(app, "CFBundleExecutable must be a portable basename; path declaration rejected.")
            app["executable_status"] = "invalid_declaration"
            continue
        key = bundle + "/" + name
        app["executable_path"] = key
        if key not in records:
            app["executable_status"] = "missing_inventory_entry"
            warning(app, "Declared executable is missing from the exact-case package inventory; signature was not read.")
            continue
        executable_paths.add(key)
        try:
            header = _header(content, key)
            app["executable_format"] = MACH_MAGICS.get(header)
            if app["executable_format"] is None:
                app["executable_status"] = "unrecognized_signature"
                warning(app, "Declared executable has no recognized Mach-O/FAT magic; no binary restoration performed.")
            else:
                app["executable_status"] = "signature_candidate_only"
            if key in records:
                records[key]["role"] = "declared_app_executable"
        except (OSError, ValueError) as exc:
            warning(app, f"Declared executable unavailable: {exc}")

    for key, record in records.items():
        parts = PurePosixPath(key).parts
        suffix = PurePosixPath(key).suffix.lower()
        inside_app = len(parts) >= 3 and parts[0] == "Payload" and parts[1].endswith(".app")
        if "_CodeSignature" in parts:
            record.update(category="code_signature_data", verification="not_performed")
        elif suffix == ".mobileprovision":
            record.update(category="provisioning_profile", verification="not_performed")
        elif suffix == ".plist":
            record["category"] = "apple_bundle_plist" if inside_app else "apple_property_list"
        elif inside_app:
            framework = any(part.endswith(".framework") for part in parts[:-1])
            record["category"] = "declared_executable_candidate" if key in executable_paths else (
                "dynamic_library_candidate" if suffix == ".dylib" else (
                "framework_resource" if framework else "apple_bundle_resource")
            )
            if key in executable_paths or not suffix or suffix in {".dylib", ".so"}:
                try:
                    signature = MACH_MAGICS.get(_header(content, key))
                    if signature:
                        record.update(category="mach_o_or_fat_candidate", binary_format=signature,
                                      signature_only=True, encryption_status="unknown", symbol_status="unknown")
                except (OSError, ValueError) as exc:
                    warnings.append(f"{key}: binary candidate signature unavailable: {exc}")
                    manifest["status"] = "partial"
    warnings.append("IPA plist values are unverified bundle declarations, not Git/build provenance. Mach-O/FAT magic is a candidate signature only; encrypted/stripped state and source restoration were not determined.")
    warnings.append("Application metadata covers top-level Payload/*.app only. Nested apps/extensions/frameworks are preserved in file inventory; their metadata is not recursively interpreted. Signature/provisioning files were inventoried without verification.")
