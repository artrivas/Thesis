"""Import the official benchmark ZINC subset into a portable, checked JSON cache.

Only this importer needs torch (CPU is sufficient); experiment runtime does not.
The restricted legacy-pickle reader delegates tensor storage to weights-only load.
"""
import argparse
from collections import OrderedDict
import gzip
import hashlib
import io
import json
from pathlib import Path
import pickle
import sys
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from experimentation.randomness import canonical_json
from experimentation.zinc_dataset import CACHE_SCHEMA, validate_record

SOURCE_URL = "https://www.dropbox.com/s/feo9qle74kg48gy/molecules.zip?dl=1"
INDEX_REVISION = "b6c407712fa576e9699555e1e035d1e327ccae6c"
INDEX_URL = "https://raw.githubusercontent.com/graphdeeplearning/benchmarking-gnns/" + INDEX_REVISION + "/data/molecules/{}.index"
EXPECTED = {"train": 10000, "val": 1000, "test": 1000}


def download(url, path):
    if path.exists():
        return
    temporary = path.with_suffix(path.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "Thesis-ZINC-importer/1"})
    with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
        total = 0
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
            total += len(chunk)
            if total % (50 * 1024**2) == 0:
                print(f"Downloaded {total // 1024**2} MiB", flush=True)
    temporary.replace(path)


class TensorUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        import torch
        if (module, name) == ("torch.storage", "_load_from_bytes"):
            return lambda data: torch.load(io.BytesIO(data), map_location="cpu", weights_only=True)
        if module == "torch._utils" and name in ("_rebuild_tensor", "_rebuild_tensor_v2"):
            return getattr(torch._utils, name)
        if (module, name) == ("collections", "OrderedDict"):
            return OrderedDict
        raise pickle.UnpicklingError(f"Unsupported pickle global {module}.{name}")


def convert_molecule(molecule, split, index):
    atoms = molecule["atom_type"].reshape(-1).tolist()
    bonds = molecule["bond_type"].tolist()
    n = len(atoms)
    if len(bonds) != n or any(len(row) != n for row in bonds):
        raise ValueError("Source adjacency/atom size mismatch")
    edges, types = [], []
    for u in range(n):
        if bonds[u][u] != 0:
            raise ValueError("Unsupported ZINC self-loop")
        for v in range(u + 1, n):
            if bonds[u][v] != bonds[v][u]:
                raise ValueError("Asymmetric source bond matrix")
            if bonds[u][v]:
                edges.append([u, v])
                types.append(int(bonds[u][v]))
    record = {"source_id": f"zinc-benchmark:{split}:{index}", "num_nodes": n,
              "atom_types": [int(a) for a in atoms], "edges": edges, "bond_types": types,
              "source_target_unused": molecule["logP_SA_cycle_normalized"].reshape(-1).tolist()}
    validate_record(record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="data")
    args = parser.parse_args()
    root = Path(args.data_root) / "ZINC"
    raw = root / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    if (root / "manifest.json").exists():
        from experimentation.datasets import SyntheticDatasetConfig
        from experimentation.zinc_dataset import resolve_zinc_config, records_for_split
        for split in EXPECTED:
            cfg = resolve_zinc_config(SyntheticDatasetConfig("zinc", data_root=args.data_root,
                dataset_variant="subset12k", dataset_split=split))
            records_for_split(cfg)
        print("Existing ZINC cache verified; no files changed.")
        return
    archive = raw / "molecules.zip"
    download(SOURCE_URL, archive)
    provenance = {"archive_url": SOURCE_URL, "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                  "index_revision": INDEX_REVISION, "indices": {}}
    splits = {}
    with zipfile.ZipFile(archive) as handle:
        for split, count in EXPECTED.items():
            index_path = raw / f"{split}.index"
            download(INDEX_URL.format(split), index_path)
            index_bytes = index_path.read_bytes()
            indices = [int(i) for i in index_bytes.decode().strip().strip(",").split(",")]
            if len(indices) != count or len(set(indices)) != count:
                raise ValueError(f"Unexpected {split} subset count/duplicate indices")
            provenance["indices"][split] = {"url": INDEX_URL.format(split),
                "sha256": hashlib.sha256(index_bytes).hexdigest()}
            print(f"Converting {split}: {count} graphs", flush=True)
            with handle.open(f"molecules/{split}.pickle") as source:
                molecules = TensorUnpickler(source).load()
            records = [convert_molecule(molecules[index], split, index) for index in indices]
            del molecules
            content = gzip.compress(("\n".join(canonical_json(r) for r in records) + "\n").encode(), mtime=0)
            filename = f"{split}.jsonl.gz"
            temporary = root / (filename + ".tmp")
            temporary.write_bytes(content)
            temporary.replace(root / filename)
            splits[split] = {"file": filename, "count": count, "sha256": hashlib.sha256(content).hexdigest()}
    manifest = {"schema": CACHE_SCHEMA, "variant": "subset12k", "splits": splits,
                "fingerprint": hashlib.sha256(canonical_json(splits).encode()).hexdigest(), "provenance": provenance}
    temporary = root / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    temporary.replace(root / "manifest.json")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
