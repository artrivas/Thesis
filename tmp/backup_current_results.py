"""Create a separate, hash-verified snapshot without changing source results."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
source = root / "results"
destination = root / "archive/results_snapshots/2026-09-16_before_randomness_fix"
if destination.exists():
    raise FileExistsError(f"Refusing to overwrite snapshot: {destination}")


def inventory(directory):
    entries = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Unexpected symbolic link: {path}")
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            entries.append({"path": path.relative_to(directory).as_posix(),
                            "bytes": path.stat().st_size, "sha256": digest.hexdigest()})
    return entries


before = inventory(source)
total_bytes = sum(entry["bytes"] for entry in before)
if shutil.disk_usage(root).free < total_bytes + 10 * 1024**2:
    raise OSError("Insufficient free space for the snapshot")
destination.mkdir(parents=True, exist_ok=False)
shutil.copytree(source, destination / "results", copy_function=shutil.copy2)
copied = inventory(destination / "results")
after = inventory(source)
if before != copied or before != after:
    raise RuntimeError("Snapshot verification failed or source changed during copying")
manifest = {
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "source": str(source), "destination": str(destination / "results"),
    "file_count": len(before), "total_bytes": total_bytes,
    "verification": "All copied paths, sizes, and SHA-256 hashes match source before and after copy",
    "scope": "Entire results directory: runs, legacy outputs, analyses, figures, and documentation",
    "files": before,
}
(destination / "snapshot_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
(destination / "README.md").write_text(
    "# Results snapshot before randomness correction\n\n"
    "Complete copy of the repository's results directory. Source files were not modified.\n\n"
    f"Verified {len(before):,} files ({total_bytes:,} bytes) using SHA-256 against the source before and after copying.\n\n"
    "See snapshot_manifest.json for every relative path and hash. This is a local copy on the same storage, not an off-device backup.\n",
    encoding="utf-8",
)
print(json.dumps({key: value for key, value in manifest.items() if key != "files"}, indent=2))
