# Figuras finales — corrida `2026-07-03_merged`

Generadas por [`src/scripts/generate_final_figures.py`](../../../../scripts/generate_final_figures.py)
a partir de dos archivos únicamente:

- `../results/results.csv` (20.328 filas, `status=success`)
- `../evaluation/evaluation_summary.csv` (96 filas: 4 workflows × 4 datasets × 6 perturbaciones)

Ningún valor experimental fue recalculado ni alterado. Este set reemplaza,
para el capítulo de resultados, a `figure_1_score_vs_alpha.svg`,
`figure_2_paired_distance_vs_alpha.svg` y `figure_4_granularity_heatmap.svg`
(en `../figures/`), que quedan como artefactos automáticos del pipeline pero
no deben citarse en el texto de la tesis.

## Qué usar en el capítulo de Resultados

| Archivo | Úsalo para | Mensaje principal |
|---|---|---|
| `main_response_curves.pdf` | La figura central de "cómo responde cada workflow a α" | 8 paneles representativos (local / mesoscópico / global, sintético / real, control positivo / negativo). En 6 de 8 paneles solo se muestra `distribution_score`, porque para NetLSD y Diversity Curves esa curva y la de `paired_score` están correlacionadas >0.93 (ver diagnóstico de redundancia) — mostrar ambas ahí no aportaría nada nuevo. En los paneles "ER · edge insertion" y "BA · triangle insertion" se superpone además el `paired_score` de GraphStats+MMD (línea punteada): es la evidencia visual de que, para ese workflow, el score distribucional deja de ser monótono (r=0.51 y r=0.44 con su propio `paired_score`) mientras el score pareado sí sigue detectando el cambio — un hallazgo metodológico, no ruido. |
| `summary_performance_heatmap.pdf` | La tabla-resumen comparativa de los 4 workflows | Panel A: qué workflow es más sensible a qué tipo de perturbación (promediado entre datasets). Panel B: comparación multicriterio (sensibilidad, monotonicidad, detectabilidad pareada, robustez, eficiencia, interpretabilidad); el color siempre significa "mejor dentro de esa columna", el texto siempre es el valor real (nada se oculta, incluida la baja monotonicidad/sensibilidad de GraphStats+MMD). |
| `granularity_heatmap_refined.pdf` | La figura de granularidad estructural (reemplaza a `figure_4`) | Sensibilidad promedio por escala (local/mesoscópica/global) y promedio general, con workflows ordenados por familia metodológica (MMD-based vs. mean-shift-based) y luego por desempeño; columna "nivel" (alto/medio/bajo); marca `≈` + recuadro punteado en los valores casi idénticos entre WL+MMD, NetLSD y Diversity Curves, para que esa similitud se lea como un hallazgo explicado, no como ruido de la figura. |

## Qué mandar al apéndice

| Archivo | Úsalo para |
|---|---|
| `appendix_full_score_curves.pdf` | La matriz completa 4×6 de `distribution_score` vs α, para el lector que quiera verificar cualquier celda no incluida en la figura principal. |
| `appendix_full_paired_distance_curves.pdf` | La matriz completa 4×6 de `paired_score` vs α, con el mismo propósito. Referenciar desde el texto solo cuando se discuta una celda específica que no esté en `main_response_curves`. |

`figure_0_experiment_dashboard.svg`, `figure_3_mean_shift_vs_paired_shift.svg` y
`figure_5_runtime_comparison.svg` (en `../figures/`) siguen siendo diagnósticos
internos del pipeline; no se rediseñaron porque no se pidieron en este pase y
no forman parte de la narrativa de resultados.

## Diagnóstico de redundancia que motivó este rediseño

Correlación de Pearson entre las curvas `distribution_score(α)` y
`paired_score(α)` (medias por α, 96 combinaciones dataset×perturbación×workflow):

| Workflow | Correlación media | Mínimo |
|---|---|---|
| NetLSD | 0.997 | 0.953 |
| Diversity Curves | 0.994 | 0.933 |
| WL+MMD | 0.836 | 0.677 |
| GraphStats+MMD | 0.788 | **0.307** |

Para NetLSD y Diversity Curves, `figure_1` y `figure_2` originales contaban
prácticamente la misma historia dos veces (correlación >0.93 en las 24 celdas
de cada uno). Para GraphStats+MMD, en cambio, las dos curvas divergen
fuertemente en varias celdas (mínimo r=0.31, en `erdos_renyi · triangle_insertion`).
Por eso la solución no fue "elegir una curva y descartar la otra", sino
mostrar una sola curva por defecto y superponer la segunda solo donde
realmente aporta información distinta.

## Convenciones visuales (consistentes en las 5 figuras)

- Paleta Okabe-Ito (colorblind-safe): GraphStats+MMD `#0072B2`, WL+MMD `#E69F00`,
  NetLSD `#009E73`, Diversity Curves `#CC79A7`. Además cada workflow tiene un
  marcador distinto (○ □ △ ◇) para que las curvas se distingan también en
  impresión en blanco y negro.
- Nombres cortos en todos los ejes/leyendas/títulos: `GraphStats+MMD`,
  `WL+MMD`, `NetLSD`, `Diversity Curves`.
- Ticks de α siempre en `0, 0.25, 0.5, 0.75, 1.0`.
- Leyenda de workflow compartida una sola vez por figura (no repetida por panel).
- Cada archivo se guarda en `.pdf` (para LaTeX) y `.svg` (para edición).
