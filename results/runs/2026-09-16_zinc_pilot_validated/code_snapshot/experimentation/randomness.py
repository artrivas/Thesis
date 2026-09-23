"""Versioned, purpose-separated deterministic random stream identities."""
from dataclasses import asdict
import hashlib
import json

STREAM_PROTOCOL = "sha256_streams_v1"
LEGACY_PROTOCOL = "legacy_seed_plus_index"


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def derive_seed(master_seed, purpose, *identity):
    payload = [STREAM_PROTOCOL, master_seed, purpose, *identity]
    return int.from_bytes(hashlib.sha256(canonical_json(payload).encode()).digest(), "big")


def dataset_identity(config):
    payload = asdict(config)
    for key in ("seed", "master_seed", "randomness_protocol", "data_root", "num_graphs"):
        payload.pop(key, None)
    return payload


def graph_stream(config, purpose, graph_id, perturbation=None):
    if config.randomness_protocol != STREAM_PROTOCOL:
        raise ValueError(f"Unsupported stream protocol: {config.randomness_protocol}")
    return derive_seed(config.master_seed, purpose, dataset_identity(config),
                       config.seed, graph_id, perturbation)
