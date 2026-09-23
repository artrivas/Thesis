"""Prepare Spanish scientific figures from verified analysis outputs for Slides."""
from pathlib import Path
import json
import hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'results/analysis/2026-09-17_mmd_explanation'
OUT = ROOT / 'results/presentations/2026-09-17_sensibilidad'
ORANGE, BLUE, GREEN, GRAY = '#d86222', '#1769aa', '#26846a', '#75808b'
INPUTS = ['addition_sensitivity.json', 'kernel_substitutions.json',
          'community_comparison.json', 'community_descriptor_ablation.json']


def save(fig, name):
    fig.savefig(OUT / f'{name}.png', dpi=180, facecolor='white')
    fig.savefig(OUT / f'{name}.svg', facecolor='white')
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    addition, kernels, communities, ablations = [json.loads((SOURCE / n).read_text()) for n in INPUTS]
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 16,
                        'axes.spines.top': False, 'axes.spines.right': False,
                        'axes.labelsize': 17, 'axes.titlesize': 18, 'legend.fontsize': 13})
    alpha = np.round(np.linspace(0, 1, 11), 1)
    for ds, name in [('barabasi_albert', 'ba_adiciones'), ('zinc', 'zinc_adiciones')]:
        fig, axes = plt.subplots(1, 2, figsize=(13.4, 5.4), layout='constrained')
        for ax, pt, title in zip(axes, ['edge_insertion', 'triangle_insertion'],
                                 ['Inserción aleatoria de aristas', 'Inserción que cierra triángulos']):
            setting = next(s for s in addition['settings'] if s['dataset'] == ds and s['perturbation'] == pt)
            vals = []
            for seed in range(3):
                rows = sorted([r for r in setting['records'] if r['seed'] == seed], key=lambda r:r['alpha'])
                values = [r['score'] for r in rows]; vals.append(values)
                ax.plot(alpha, values, color=ORANGE, alpha=.28, lw=1.5)
            mean = np.mean(vals, axis=0)
            ax.plot(alpha, mean, color=ORANGE, lw=3, marker='o', ms=5)
            ax.set(title=title, xlabel='Intensidad de perturbación α', ylabel='MMD² de GraphStats')
            ax.set_ylim(0, mean.max() * 1.3); ax.grid(alpha=.17)
            drop = 100 * setting['endpoint_drop_fraction']
            label = f'Caída desde el máximo: {drop:.1f} %' if ds == 'barabasi_albert' else f'ρ mediana: {setting["median_positive_alpha_spearman"]:.2f}'
            ax.text(.04, .96, label.replace('.', ','), transform=ax.transAxes, va='top')
        fig.supxlabel('Líneas finas: 3 réplicas de 100 grafos. Línea gruesa: media. RBF con σ = 10.', fontsize=13)
        save(fig, name)

    def mean_field(key):
        return np.array([np.mean([r[key] for r in kernels if r['alpha'] == a]) for a in alpha])
    fig, ax = plt.subplots(figsize=(13.4, 5.4), layout='constrained')
    for key, label, color in [('graphstats_rbf10', 'GraphStats + RBF', ORANGE), ('wl_linear', 'WL + kernel lineal', BLUE)]:
        vals = mean_field(key)
        ax.plot(alpha, vals / vals.max(), color=color, lw=3, marker='o', label=label)
    ax.set(xlabel='Intensidad de perturbación α', ylabel='Puntuación / máximo de su media', ylim=(0, 1.12))
    ax.legend(loc='lower right'); ax.grid(alpha=.17)
    ax.annotate('57,8 %', xy=(.1, .578), xytext=(.02, .78), color=ORANGE)
    ax.annotate('8,4 %', xy=(.1, .084), xytext=(.14, .11), color=BLUE)
    fig.supxlabel('BA, cierre de triángulos. Media de 3 réplicas. La normalización compara la forma de las curvas.', fontsize=13)
    save(fig, 'respuesta_temprana')

    fig, ax = plt.subplots(figsize=(13.4, 5.4), layout='constrained')
    for b, col in [('3.0', GRAY), ('10.0', ORANGE), ('30.0', GREEN), ('100.0', BLUE)]:
        vals = [np.mean([r['graphstats_bandwidth_scores'][b] for r in kernels if r['alpha'] == a]) for a in alpha]
        ax.plot(alpha, vals, color=col, lw=3, label=f'σ = {float(b):g}')
    ax.set(xlabel='Intensidad de perturbación α', ylabel='MMD² de GraphStats'); ax.grid(alpha=.17); ax.legend(ncol=2)
    fig.supxlabel('Mismos grafos BA y descriptores. Solo cambia el ancho de banda. Media de 3 réplicas.', fontsize=13)
    save(fig, 'ancho_de_banda')

    fig, axes = plt.subplots(1, 2, figsize=(13.4, 5.4), layout='constrained')
    for ax, title, keys in [(axes[0], 'Mismos descriptores GraphStats', [('graphstats_rbf10','RBF, σ = 10',ORANGE), ('graphstats_linear','Lineal',BLUE)]),
                            (axes[1], 'Mismos histogramas WL', [('wl_linear','Lineal',BLUE), ('wl_rbf_reference_median','RBF, σ de referencia',GREEN)])]:
        for key, label, color in keys:
            vals=mean_field(key); ax.plot(alpha, vals/vals.max(), color=color, label=label, lw=3)
        ax.set(title=title, xlabel='Intensidad de perturbación α', ylabel='Puntuación / máximo de su media')
        ax.legend(); ax.grid(alpha=.17)
    fig.supxlabel('BA, cierre de triángulos. Control exploratorio. Cada curva usa su propio máximo.', fontsize=13)
    save(fig, 'control_del_kernel')

    for ds, name in [('erdos_renyi','comunidades_er'), ('stochastic_block_model','comunidades_sbm'), ('zinc','comunidades_zinc')]:
        fig, axes=plt.subplots(1,2,figsize=(13.4,5.4),layout='constrained')
        for ax, wf, label, color in zip(axes,['structural_statistics_mmd','wl_subtree_kernel_mmd'],['GraphStats + RBF','WL + kernel lineal'],[ORANGE,BLUE]):
            row=next(r for r in communities if r['dataset']==ds and r['workflow']==wf)
            for values in row['trajectories']:ax.plot(alpha,values,color=color,alpha=.3,lw=1.5)
            ax.plot(alpha,row['mean'],color=color,lw=3,marker='o',ms=5)
            ax.set(title=label,xlabel='Intensidad de perturbación α',ylabel='MMD² (escala propia)'); ax.grid(alpha=.17)
        fig.supxlabel('Debilitamiento de comunidades. Líneas finas: réplicas. Línea gruesa: media. Escalas distintas.',fontsize=13)
        save(fig,name)

    rs=[r for r in ablations['records'] if r['dataset']=='stochastic_block_model']
    fig, ax=plt.subplots(figsize=(13.4,5.4),layout='constrained')
    fields=['full_rbf10','without_triangle_count_rbf10','triangle_count_only_rbf10']
    means=[np.mean([r[k] for r in rs]) for k in fields]
    bars=ax.bar(range(3),means,color=[ORANGE,BLUE,GREEN],width=.6)
    for i,k in enumerate(fields):ax.scatter([i-.06,i,i+.06],[r[k] for r in rs],s=35,c='#233747',zorder=3)
    for i,k in enumerate(fields):
        label=f'{means[i]:.6f}'.replace('.', ',')
        ax.text(i,max(r[k] for r in rs)+.02,label,ha='center',va='bottom',fontsize=17)
    ax.set_xticks(range(3),['Los 9 descriptores','Sin conteo de triángulos','Solo conteo de triángulos'])
    ax.set(ylabel='MMD² de GraphStats',ylim=(0,.54));ax.grid(axis='y',alpha=.17);ax.set_axisbelow(True)
    fig.supxlabel('Mismos grafos SBM. α = 1 y σ = 10. Barras: media. Puntos: 3 réplicas.',fontsize=13)
    save(fig,'control_triangulos_sbm')

    manifest={'sources':{n:hashlib.sha256((SOURCE/n).read_bytes()).hexdigest() for n in INPUTS},
              'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'figures':[p.name for p in sorted(OUT.glob('*.png'))],
              'note':'Spanish scientific charts from existing corrected results. No new experiments.'}
    (OUT/'figures_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Created {len(manifest["figures"])} Spanish figures in {OUT}')


if __name__=='__main__':main()
