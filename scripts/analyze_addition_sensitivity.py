"""Describe addition-response sensitivity using saved corrected diagnostics only."""
from pathlib import Path
import hashlib
import json
import numpy as np
from scipy.stats import spearmanr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'results/analysis/2026-09-16_structural_insights'
OUT = ROOT / 'results/analysis/2026-09-17_mmd_explanation'


def main():
    names = ['targeted_probes.json', 'mechanism_decompositions.json', 'cell_structure.json']
    probes, mechanisms, structures = [json.loads((SOURCE / n).read_text()) for n in names]
    alpha = np.round(np.linspace(0, 1, 11), 1)
    summaries = []
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout='constrained', sharex=True)
    for ax, (ds, pt) in zip(axes.flat, [(d, p) for d in ['barabasi_albert', 'zinc']
                                       for p in ['edge_insertion', 'triangle_insertion']]):
        source = probes if ds == 'barabasi_albert' else mechanisms
        rows = [r for r in source if r['dataset'] == ds and r['perturbation'] == pt]
        assert len(rows) == 33, (ds, pt, len(rows))
        scores, edits, correlations, records = [], [], [], []
        for seed in range(3):
            rs = sorted([r for r in rows if r['seed'] == seed], key=lambda r: r['alpha'])
            assert np.allclose([r['alpha'] for r in rs], alpha)
            vals = np.array([r['kernel']['score'] for r in rs])
            es = [r['realized_edits'] if ds == 'barabasi_albert' else
                  next(s['mean_raw_edits'] for s in structures if
                       (s['dataset'], s['perturbation'], s['seed'], s['alpha']) ==
                       (ds, pt, seed, r['alpha'])) for r in rs]
            assert np.all(np.diff(es) >= -1e-10), 'Edit budget not increasing'
            scores.append(vals); edits.append(es)
            correlations.append(float(spearmanr(alpha[1:], vals[1:]).statistic))
            ax.plot(alpha, vals, color='#d86222', alpha=.3, lw=1)
            records.extend({'seed': seed, 'alpha': float(a), 'score': float(v),
                            'mean_realized_edits': float(e), 'kernel': r['kernel']}
                           for a, v, e, r in zip(alpha, vals, es, rs))
        mean = np.mean(scores, axis=0); peak = int(np.argmax(mean))
        result = {'dataset': ds, 'perturbation': pt, 'source': 'additional corrected probe' if
                  ds == 'barabasi_albert' else 'corrected ZINC pilot',
                  'early_fraction_of_mean_peak': float(mean[1] / mean[peak]),
                  'mean_peak_alpha': float(alpha[peak]), 'mean_peak_score': float(mean[peak]),
                  'mean_endpoint_score': float(mean[-1]),
                  'endpoint_drop_fraction': float((mean[peak] - mean[-1]) / mean[peak]),
                  'positive_alpha_spearman_by_replicate': correlations,
                  'median_positive_alpha_spearman': float(np.median(correlations)),
                  'mean_edits_at_peak': float(np.mean(edits, axis=0)[peak]),
                  'mean_edits_at_endpoint': float(np.mean(edits, axis=0)[-1]),
                  'records': records}
        summaries.append(result)
        ax.plot(alpha, mean, color='#d86222', marker='o', lw=2, label='GraphStats mean; thin: replicates')
        ax.set(title=f"{'BA (corrected probe)' if ds == 'barabasi_albert' else 'ZINC (corrected pilot)'}: {pt.replace('_', ' ')}",
               ylabel='GraphStats RBF MMD² (bandwidth 10)', xlabel='Alpha')
        ax.set_ylim(0, max(mean) * 1.28)
        ax.text(.03, .97, f"Early response: {result['early_fraction_of_mean_peak']:.1%} of peak\n"
                f"Peak → endpoint drop: {result['endpoint_drop_fraction']:.1%}",
                transform=ax.transAxes, va='top', fontsize=9)
        ax.grid(alpha=.18)
    fig.suptitle('Sensitivity to additions: early response and later severity resolution\n'
                 'Three replicates × 100 graphs per setting; raw score axes differ; no detection-power claims', fontsize=12)
    fig.savefig(OUT / 'addition_sensitivity.png', dpi=180)
    plt.close(fig)
    output = {'input_sha256': {str((SOURCE / n).relative_to(ROOT)):
                              hashlib.sha256((SOURCE / n).read_bytes()).hexdigest() for n in names},
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'settings': summaries}
    (OUT / 'addition_sensitivity.json').write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
    print(json.dumps([{k: v for k, v in s.items() if k != 'records'} for s in summaries], indent=2))


if __name__ == '__main__':
    main()
