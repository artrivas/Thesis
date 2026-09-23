import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
import time
import tracemalloc
import torch
from experimentation.datasets import SyntheticDatasetConfig, generate_graph_distribution
import experimentation.workflows as w

torch.set_num_threads(1)
g = generate_graph_distribution(SyntheticDatasetConfig("barabasi_albert", num_graphs=1))[0]
tracemalloc.start()
start = time.perf_counter()
a = w.netlsd_signature(g, w.NETLSD_DEFAULT_TIMESCALES)
slow = time.perf_counter()-start
w._torch_device_name = lambda: "cpu"
start = time.perf_counter()
b = w.netlsd_signature(g, w.NETLSD_DEFAULT_TIMESCALES)
fast = time.perf_counter()-start
print({"reference_seconds": slow, "torch_cpu_seconds": fast, "max_signature_difference": max(abs(x-y) for x,y in zip(a,b))})
