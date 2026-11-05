#!/usr/bin/env python3
"""Create and verify board-specific provenance for build artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

J313_GUEST_CONTRACT = {
    "layout_version": 1,
    "phys_base": "0x850000000",
    "ram_end": "0xa00000000",
    "virtual_fb_base": "0x85f000000",
    "virtual_fb_width": 2560,
    "virtual_fb_height": 1600,
    "virtual_fb_stride": 10240,
    "cpu_count": 8,
}

J413_GUEST_CONTRACT = {
    **J313_GUEST_CONTRACT,
    "virtual_fb_base": "0x85e000000",
    "virtual_fb_height": 1664,
}
GUEST_CONTRACTS = {"j313": J313_GUEST_CONTRACT, "j413": J413_GUEST_CONTRACT}

ARTIFACT_ROLES = {
    "boot.bin": "standalone-bootstrap",
    "m1n1-stage0.bin": "autonomous-stage0",
    "m1n1-stage1.bin": "autonomous-stage1",
    "m1n1.macho": "assisted-chainload",
    "J313_EFI.fd": "guest-firmware",
    "J413_EFI.fd": "guest-firmware",
}

M1N1_BUILD_TAG_MARKER = b"##m1n1_ver##"
M1N1_BUILD_TAG_PATTERN = re.compile(rb"[ -~]+")


class ManifestError(RuntimeError):
    pass


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], check=False, capture_output=True, text=True
    )
    if result.returncode:
        raise ManifestError(result.stderr.strip() or f"git failed in {root}")
    return result.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _m1n1_build_tag(path: Path) -> str:
    """Read the identity compiled into m1n1 by version.sh."""
    data = path.read_bytes()
    offsets = []
    start = 0
    while True:
        offset = data.find(M1N1_BUILD_TAG_MARKER, start)
        if offset < 0:
            break
        offsets.append(offset)
        start = offset + len(M1N1_BUILD_TAG_MARKER)
    if len(offsets) != 1:
        raise ManifestError(
            f"m1n1 build identity marker count is {len(offsets)}, expected 1: {path}"
        )
    value = data[offsets[0] + len(M1N1_BUILD_TAG_MARKER):]
    match = M1N1_BUILD_TAG_PATTERN.match(value)
    if match is None:
        raise ManifestError(f"m1n1 build identity is empty: {path}")
    return match.group().decode("ascii")


def _validate_m1n1_build_identity(
    path: Path, source_commit: str, *, expected_tag: str | None = None
) -> str:
    tag = _m1n1_build_tag(path)
    if tag.endswith("-dirty"):
        raise ManifestError(f"m1n1 build identity is dirty: {tag}")
    required = expected_tag if expected_tag is not None else source_commit[:7]
    if tag != required:
        raise ManifestError(
            f"m1n1 build identity mismatch: expected {required}, got {tag}"
        )
    return tag


def _clean_revision(root: Path) -> str:
    if _git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ManifestError(f"tracked source is dirty: {root}")
    return _git(root, "rev-parse", "HEAD")


def _source_revision(root: Path, *, allow_dirty: bool) -> dict:
    commit = _git(root, "rev-parse", "HEAD")
    dirty = bool(_git(root, "status", "--porcelain", "--untracked-files=no"))
    if dirty and not allow_dirty:
        raise ManifestError(f"tracked source is dirty: {root}")
    result = {"commit": commit, "dirty": dirty}
    if dirty:
        diff = subprocess.run(
            ["git", "-C", str(root), "diff", "--binary", "HEAD"],
            check=True, capture_output=True,
        ).stdout
        result["diff_sha256"] = hashlib.sha256(diff).hexdigest()
    return result


def create_manifest(
    root: Path,
    artifact_dir: Path,
    profile: str,
    display: str,
    debug: str,
    artifact_names: list[str],
    *,
    compiler: str,
    allow_dirty: bool = False,
    artifact_roles: dict[str, str] | None = None,
    capabilities: tuple[str, ...] = (),
    platform: str = "j313",
) -> Path:
    root = root.resolve()
    artifact_dir = artifact_dir.resolve()
    if profile not in {"release", "debug"}:
        raise ManifestError(f"unsupported profile: {profile}")
    if allow_dirty and profile != "debug":
        raise ManifestError("dirty source is allowed only for debug artifacts")
    if not compiler.strip():
        raise ManifestError("compiler identity is empty")
    if platform not in GUEST_CONTRACTS:
        raise ManifestError(f"unsupported platform: {platform}")
    if platform == "j413" and profile != "debug":
        raise ManifestError("J413 has no hardware-qualified release; use debug")
    normalized_capabilities = sorted(set(capabilities))
    for capability in normalized_capabilities:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", capability):
            raise ManifestError(f"invalid capability: {capability}")
    expected_contract = GUEST_CONTRACTS[platform]
    layout_path = root / "config" / f"{platform}-guest-layout.json"
    try:
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestError(f"cannot read guest layout: {layout_path}") from error
    guest_contract = {key: layout.get(key) for key in expected_contract}
    if guest_contract != expected_contract:
        raise ManifestError(f"guest layout does not match the {platform} build contract")
    root_revision = _source_revision(root, allow_dirty=allow_dirty)
    revisions = {
        "root_commit": root_revision["commit"],
        "source_dirty": root_revision["dirty"],
    }
    if root_revision["dirty"]:
        revisions["root_diff_sha256"] = root_revision["diff_sha256"]
    for name in ("m1n1_windows", "mu"):
        path = root / name
        if (path / ".git").exists() or (path / ".git").is_file():
            revision = _source_revision(path, allow_dirty=allow_dirty)
            revisions[f"{name}_commit"] = revision["commit"]
            revisions[f"{name}_dirty"] = revision["dirty"]
            if revision["dirty"]:
                revisions[f"{name}_diff_sha256"] = revision["diff_sha256"]
    roles = ARTIFACT_ROLES if artifact_roles is None else artifact_roles
    artifacts = {}
    for name in artifact_names:
        path = artifact_dir / name
        if not path.is_file():
            raise ManifestError(f"artifact is missing: {path}")
        record = {"size": path.stat().st_size, "sha256": _sha256(path)}
        if name in roles:
            record["role"] = roles[name]
        if name == "m1n1.macho" and revisions.get("m1n1_windows_commit"):
            if not revisions.get("m1n1_windows_dirty", False):
                record["build_tag"] = _validate_m1n1_build_identity(
                    path, revisions["m1n1_windows_commit"]
                )
        artifacts[name] = record
    data = {
        "format_version": 2,
        "platform": platform,
        "profile": profile,
        "display": display,
        "debug": debug,
        "compiler": compiler,
        "guest_layout_sha256": _sha256(layout_path),
        "guest_contract": guest_contract,
        "capabilities": normalized_capabilities,
        **revisions,
        "artifacts": artifacts,
    }
    if platform == "j413":
        overlay_dir = root / "platforms/j413/mu"
        if not overlay_dir.is_dir():
            raise ManifestError("J413 firmware source overlay is missing")
        from tools.j413_platform import overlay_sha256
        data["platform_overlay_sha256"] = overlay_sha256(root)
        from tools.j413_direct_setup import RELATIVE, target_uuid
        if (overlay_dir / RELATIVE).exists():
            data["direct_setup"] = {"mode": "single-gpt-volume", "partition_uuid": target_uuid(root),
                                    "loader_path": "\\EFI\\BOOT\\BOOTAA64.EFI"}
        if "boot.bin" in artifacts:
            from tools.j413_platform import m1n1_sources_sha256
            data["platform_m1n1_sources_sha256"] = m1n1_sources_sha256(root)
            data["qualification"] = "experimental-source-contract-no-hardware-launch"
    path = artifact_dir / "MANIFEST.json"
    temporary = path.with_suffix(".json.new")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def verify_manifest(
    path: Path,
    expected_profile: str | None = None,
    expected_roles: dict[str, str] | None = None,
    expected_display: str | None = None,
    expected_debug: str | None = None,
    expected_platform: str | None = None,
    required_capabilities: tuple[str, ...] = (),
) -> dict:
    path = path.resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestError(f"cannot read manifest: {path}") from error
    platform = data.get("platform", "j313")
    if data.get("format_version") != 2 or platform not in GUEST_CONTRACTS:
        raise ManifestError("unsupported artifact manifest")
    if expected_platform is not None and platform != expected_platform:
        raise ManifestError(f"platform mismatch: expected {expected_platform}, got {platform}")
    if platform == "j413" and data.get("profile") != "debug":
        raise ManifestError("J413 has no hardware-qualified release")
    if platform == "j413" and len(data.get("platform_overlay_sha256", "")) != 64:
        raise ManifestError("J413 firmware source overlay provenance is missing")
    if "direct_setup" in data:
        import uuid
        target = data["direct_setup"]
        try:
            identity = uuid.UUID(target["partition_uuid"])
            valid = (isinstance(target, dict) and platform == "j413" and identity.int != 0 and
                     target["partition_uuid"] == str(identity).upper() and target["mode"] == "single-gpt-volume" and
                     target["loader_path"] == "\\EFI\\BOOT\\BOOTAA64.EFI")
        except (ValueError, KeyError, TypeError, AttributeError):
            valid = False
        if not valid:
            raise ManifestError("Invalid direct Setup target contract")
    if platform == "j413" and "boot.bin" in data.get("artifacts", {}):
        if len(data.get("platform_m1n1_sources_sha256", "")) != 64 or data.get("qualification") != "experimental-source-contract-no-hardware-launch":
            raise ManifestError("J413 experimental boot source provenance is missing")
    if expected_profile is not None and data.get("profile") != expected_profile:
        raise ManifestError(
            f"profile mismatch: expected {expected_profile}, got {data.get('profile')}"
        )
    if expected_display is not None and data.get("display") != expected_display:
        raise ManifestError(
            f"display mode mismatch: expected {expected_display}, got {data.get('display')}"
        )
    if expected_debug is not None and data.get("debug") != expected_debug:
        raise ManifestError(
            f"debug mode mismatch: expected {expected_debug}, got {data.get('debug')}"
        )
    capabilities = data.get("capabilities", [])
    if not isinstance(capabilities, list):
        raise ManifestError("invalid manifest capabilities")
    missing_capabilities = sorted(set(required_capabilities) - set(capabilities))
    if missing_capabilities:
        raise ManifestError(
            "missing capability: " + ", ".join(missing_capabilities)
        )
    if not data.get("compiler") or len(data.get("guest_layout_sha256", "")) != 64:
        raise ManifestError("incomplete artifact provenance")
    if data.get("guest_contract") != GUEST_CONTRACTS[platform]:
        raise ManifestError("guest contract mismatch")
    for name, record in data.get("artifacts", {}).items():
        artifact = path.parent / name
        if not artifact.is_file():
            raise ManifestError(f"artifact is missing: {artifact}")
        if artifact.stat().st_size != record.get("size") or _sha256(artifact) != record.get("sha256"):
            raise ManifestError(f"artifact hash mismatch: {artifact}")
        if name == "m1n1.macho" and data.get("m1n1_windows_commit"):
            _validate_m1n1_build_identity(
                artifact,
                data["m1n1_windows_commit"],
                expected_tag=record.get("build_tag"),
            )
    for name, role in (expected_roles or {}).items():
        if data.get("artifacts", {}).get(name, {}).get("role") != role:
            raise ManifestError(f"artifact role mismatch: {name} is not {role}")
    if not data.get("artifacts"):
        raise ManifestError("manifest contains no artifacts")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--root", type=Path, required=True)
    create.add_argument("--directory", type=Path, required=True)
    create.add_argument("--profile", choices=("release", "debug"), required=True)
    create.add_argument("--display", required=True)
    create.add_argument("--debug", required=True)
    create.add_argument("--compiler", required=True)
    create.add_argument("--allow-dirty", action="store_true")
    create.add_argument("--capability", action="append", default=[])
    create.add_argument("--platform", choices=tuple(GUEST_CONTRACTS), default="j313")
    create.add_argument("artifacts", nargs="+")
    verify = subparsers.add_parser("verify")
    verify.add_argument("manifest", type=Path)
    verify.add_argument("--profile", choices=("release", "debug"))
    verify.add_argument("--display")
    verify.add_argument("--debug")
    verify.add_argument("--platform", choices=tuple(GUEST_CONTRACTS))
    verify.add_argument("--require-role", action="append", default=[], metavar="NAME=ROLE")
    verify.add_argument("--require-capability", action="append", default=[])
    args = parser.parse_args()
    try:
        if args.command == "create":
            print(
                create_manifest(
                    args.root,
                    args.directory,
                    args.profile,
                    args.display,
                    args.debug,
                    args.artifacts,
                    compiler=args.compiler,
                    allow_dirty=args.allow_dirty,
                    capabilities=tuple(args.capability),
                    platform=args.platform,
                )
            )
        else:
            roles = {}
            for value in args.require_role:
                if "=" not in value:
                    raise ManifestError(f"invalid artifact role requirement: {value}")
                name, role = value.split("=", 1)
                if not name or not role:
                    raise ManifestError(f"invalid artifact role requirement: {value}")
                roles[name] = role
            data = verify_manifest(
                args.manifest, args.profile, roles,
                expected_display=args.display, expected_debug=args.debug,
                expected_platform=args.platform,
                required_capabilities=tuple(args.require_capability),
            )
            print(f"validated {data['platform']} {data['profile']} artifacts")
    except ManifestError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
