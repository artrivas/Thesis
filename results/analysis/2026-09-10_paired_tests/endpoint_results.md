# Paired statistical results — alpha 0.1 to 1.0

Exploratory, conditional on independent seed trajectories. All p-values below are two-sided and Holm-adjusted over the full 2,376-slot contrast/method family. A dash means the method was withheld by the diagnostic screen, not p=1. Mean changes are in each workflow's own units. Sign direction counts include all 24 seeds. Intervals are pointwise 95%, not multiplicity-adjusted.

| Dataset | Perturbation | Workflow | Alpha low → high | Mean change | Mean change 95% CI (t eligible only) | + / − / zero | t adjusted p | Wilcoxon adjusted p | Sign adjusted p |
|---|---|---|---|---:|---|---|---:|---:|---:|
| BA | community weakening | Diversity | 0.1 → 1.0 | +9.02701 | [8.7629, 9.2911] | 24 / 0 / 0 | 4.48e-25 | 0.000243 | 0.000243 |
| BA | community weakening | NetLSD | 0.1 → 1.0 | +0.28845 | [0.27777, 0.29913] | 24 / 0 / 0 | 9.61e-23 | 0.000243 | 0.000243 |
| BA | community weakening | GraphStats | 0.1 → 1.0 | +0.191833 | [0.18227, 0.2014] | 24 / 0 / 0 | 8.45e-20 | — | 0.000243 |
| BA | community weakening | WL | 0.1 → 1.0 | +249.85 | [244.66, 255.04] | 24 / 0 / 0 | 1.79e-28 | 0.000243 | 0.000243 |
| BA | edge deletion | Diversity | 0.1 → 1.0 | +161.395 | [161.31, 161.48] | 24 / 0 / 0 | 8.02e-65 | 0.000243 | 0.000243 |
| BA | edge deletion | NetLSD | 0.1 → 1.0 | +10.521 | [10.518, 10.524] | 24 / 0 / 0 | 1.43e-70 | 0.000243 | 0.000243 |
| BA | edge deletion | GraphStats | 0.1 → 1.0 | +1.16725 | — | 24 / 0 / 0 | — | 0.000243 | 0.000243 |
| BA | edge deletion | WL | 0.1 → 1.0 | +10692.5 | [10690, 10695] | 24 / 0 / 0 | 6.21e-73 | 0.000243 | 0.000243 |
| BA | edge insertion | Diversity | 0.1 → 1.0 | +9.87232 | [9.835, 9.9096] | 24 / 0 / 0 | 1.86e-45 | 0.000243 | 0.000243 |
| BA | edge insertion | NetLSD | 0.1 → 1.0 | +0.168601 | [0.16785, 0.16935] | 24 / 0 / 0 | 8.68e-44 | — | 0.000243 |
| BA | edge insertion | GraphStats | 0.1 → 1.0 | +0.757386 | [0.7443, 0.77047] | 24 / 0 / 0 | 2.64e-30 | — | 0.000243 |
| BA | edge insertion | WL | 0.1 → 1.0 | +701.457 | [698.24, 704.68] | 24 / 0 / 0 | 1.59e-43 | 0.000243 | 0.000243 |
| BA | hub modification | Diversity | 0.1 → 1.0 | +10.0663 | [9.7895, 10.343] | 24 / 0 / 0 | 1.08e-25 | 0.000243 | 0.000243 |
| BA | hub modification | NetLSD | 0.1 → 1.0 | +0.332095 | [0.32133, 0.34286] | 24 / 0 / 0 | 4.62e-24 | 0.000243 | 0.000243 |
| BA | hub modification | GraphStats | 0.1 → 1.0 | +0.0434737 | — | 24 / 0 / 0 | — | — | 0.000243 |
| BA | hub modification | WL | 0.1 → 1.0 | +210.513 | — | 24 / 0 / 0 | — | 0.000243 | 0.000243 |
| BA | triangle deletion | Diversity | 0.1 → 1.0 | +55.2218 | [54.545, 55.899] | 24 / 0 / 0 | 1.02e-33 | 0.000243 | 0.000243 |
| BA | triangle deletion | NetLSD | 0.1 → 1.0 | +1.93179 | [1.9037, 1.9599] | 24 / 0 / 0 | 5.13e-32 | — | 0.000243 |
| BA | triangle deletion | GraphStats | 0.1 → 1.0 | +0.537236 | — | 24 / 0 / 0 | — | — | 0.000243 |
| BA | triangle deletion | WL | 0.1 → 1.0 | +323.385 | [314.02, 332.74] | 24 / 0 / 0 | 3.51e-25 | — | 0.000243 |
| BA | triangle insertion | Diversity | 0.1 → 1.0 | +8.5806 | [8.5431, 8.6181] | 24 / 0 / 0 | 5.24e-44 | 0.000243 | 0.000243 |
| BA | triangle insertion | NetLSD | 0.1 → 1.0 | +0.160634 | — | 24 / 0 / 0 | — | 0.000243 | 0.000243 |
| BA | triangle insertion | GraphStats | 0.1 → 1.0 | +0.401888 | — | 24 / 0 / 0 | — | — | 0.000243 |
| BA | triangle insertion | WL | 0.1 → 1.0 | +565.947 | — | 24 / 0 / 0 | — | — | 0.000243 |
| ER | community weakening | Diversity | 0.1 → 1.0 | +0.194995 | [0.10849, 0.2815] | 18 / 6 / 0 | 0.112 | — | 1 |
| ER | community weakening | NetLSD | 0.1 → 1.0 | +0.00402086 | — | 20 / 4 / 0 | — | — | 1 |
| ER | community weakening | GraphStats | 0.1 → 1.0 | +0.000576285 | [-0.00041928, 0.0015718] | 16 / 8 / 0 | 1 | — | 1 |
| ER | community weakening | WL | 0.1 → 1.0 | +0.737125 | — | 23 / 1 / 0 | — | 0.000263 | 0.00323 |
| ER | edge deletion | Diversity | 0.1 → 1.0 | +170.004 | [169.89, 170.12] | 24 / 0 / 0 | 1.53e-62 | — | 0.000243 |
| ER | edge deletion | NetLSD | 0.1 → 1.0 | +10.6183 | [10.615, 10.622] | 24 / 0 / 0 | 2.69e-70 | 0.000243 | 0.000243 |
| ER | edge deletion | GraphStats | 0.1 → 1.0 | +1.14793 | [1.1408, 1.1551] | 24 / 0 / 0 | 1.74e-40 | 0.000243 | 0.000243 |
| ER | edge deletion | WL | 0.1 → 1.0 | +10262.3 | — | 24 / 0 / 0 | — | 0.000243 | 0.000243 |
| ER | edge insertion | Diversity | 0.1 → 1.0 | +7.5254 | [7.4681, 7.5827] | 24 / 0 / 0 | 1.78e-38 | 0.000243 | 0.000243 |
| ER | edge insertion | NetLSD | 0.1 → 1.0 | +0.132925 | [0.13159, 0.13426] | 24 / 0 / 0 | 9.82e-36 | — | 0.000243 |
| ER | edge insertion | GraphStats | 0.1 → 1.0 | +0.291017 | — | 24 / 0 / 0 | — | — | 0.000243 |
| ER | edge insertion | WL | 0.1 → 1.0 | +374.818 | — | 24 / 0 / 0 | — | 0.000243 | 0.000243 |
| ER | hub modification | Diversity | 0.1 → 1.0 | +0.153959 | [0.077483, 0.23044] | 20 / 4 / 0 | 0.384 | 0.213 | 1 |
| ER | hub modification | NetLSD | 0.1 → 1.0 | +0.00458914 | [0.0019597, 0.0072186] | 18 / 6 / 0 | 1 | 1 | 1 |
| ER | hub modification | GraphStats | 0.1 → 1.0 | +0.0142598 | [0.011066, 0.017453] | 24 / 0 / 0 | 6.83e-06 | — | 0.000243 |
| ER | hub modification | WL | 0.1 → 1.0 | +0.583392 | — | 21 / 3 / 0 | — | 0.00886 | 0.287 |
| ER | triangle deletion | Diversity | 0.1 → 1.0 | +30.7117 | [30.209, 31.214] | 24 / 0 / 0 | 7.59e-31 | 0.000243 | 0.000243 |
| ER | triangle deletion | NetLSD | 0.1 → 1.0 | +0.764669 | [0.74803, 0.78131] | 24 / 0 / 0 | 5.16e-28 | — | 0.000243 |
| ER | triangle deletion | GraphStats | 0.1 → 1.0 | +0.607482 | [0.59285, 0.62212] | 24 / 0 / 0 | 5.3e-27 | 0.000243 | 0.000243 |
| ER | triangle deletion | WL | 0.1 → 1.0 | +356.812 | — | 24 / 0 / 0 | — | 0.000243 | 0.000243 |
| ER | triangle insertion | Diversity | 0.1 → 1.0 | +6.70961 | [6.6905, 6.7287] | 24 / 0 / 0 | 2.81e-48 | 0.000243 | 0.000243 |
| ER | triangle insertion | NetLSD | 0.1 → 1.0 | +0.124551 | [0.12416, 0.12494] | 24 / 0 / 0 | 1.97e-47 | — | 0.000243 |
| ER | triangle insertion | GraphStats | 0.1 → 1.0 | +0.120724 | [0.11273, 0.12872] | 24 / 0 / 0 | 5.17e-17 | 0.000243 | 0.000243 |
| ER | triangle insertion | WL | 0.1 → 1.0 | +272.094 | — | 24 / 0 / 0 | — | — | 0.000243 |
| SBM | community weakening | Diversity | 0.1 → 1.0 | +0.525673 | — | 24 / 0 / 0 | — | 0.000243 | 0.000243 |
| SBM | community weakening | NetLSD | 0.1 → 1.0 | +0.0150378 | — | 24 / 0 / 0 | — | — | 0.000243 |
| SBM | community weakening | GraphStats | 0.1 → 1.0 | +0.298293 | — | 24 / 0 / 0 | — | — | 0.000243 |
| SBM | community weakening | WL | 0.1 → 1.0 | +1.01452 | [0.73494, 1.2941] | 23 / 1 / 0 | 0.000243 | — | 0.00323 |
| SBM | edge deletion | Diversity | 0.1 → 1.0 | +161.67 | [161.47, 161.87] | 24 / 0 / 0 | 1.51e-56 | — | 0.000243 |
| SBM | edge deletion | NetLSD | 0.1 → 1.0 | +10.4712 | — | 24 / 0 / 0 | — | 0.000243 | 0.000243 |
| SBM | edge deletion | GraphStats | 0.1 → 1.0 | +1.21106 | [1.2038, 1.2183] | 24 / 0 / 0 | 6.4e-41 | — | 0.000243 |
| SBM | edge deletion | WL | 0.1 → 1.0 | +10254.3 | [10245, 10264] | 24 / 0 / 0 | 1.76e-59 | 0.000243 | 0.000243 |
| SBM | edge insertion | Diversity | 0.1 → 1.0 | +11.1426 | [11.02, 11.266] | 24 / 0 / 0 | 9.2e-35 | — | 0.000243 |
| SBM | edge insertion | NetLSD | 0.1 → 1.0 | +0.204563 | [0.20115, 0.20797] | 24 / 0 / 0 | 1.16e-30 | — | 0.000243 |
| SBM | edge insertion | GraphStats | 0.1 → 1.0 | +0.412732 | [0.40705, 0.41842] | 24 / 0 / 0 | 1.46e-32 | 0.000243 | 0.000243 |
| SBM | edge insertion | WL | 0.1 → 1.0 | +390.057 | [386.43, 393.68] | 24 / 0 / 0 | 1.74e-36 | — | 0.000243 |
| SBM | hub modification | Diversity | 0.1 → 1.0 | +0.225162 | — | 20 / 4 / 0 | — | — | 1 |
| SBM | hub modification | NetLSD | 0.1 → 1.0 | +0.0110474 | — | 22 / 2 / 0 | — | — | 0.038 |
| SBM | hub modification | GraphStats | 0.1 → 1.0 | +0.0124205 | — | 24 / 0 / 0 | — | — | 0.000243 |
| SBM | hub modification | WL | 0.1 → 1.0 | +1.17907 | — | 24 / 0 / 0 | — | 0.000243 | 0.000243 |
| SBM | triangle deletion | Diversity | 0.1 → 1.0 | +42.1076 | — | 24 / 0 / 0 | — | — | 0.000243 |
| SBM | triangle deletion | NetLSD | 0.1 → 1.0 | +1.20247 | — | 24 / 0 / 0 | — | 0.000243 | 0.000243 |
| SBM | triangle deletion | GraphStats | 0.1 → 1.0 | +0.701379 | [0.68397, 0.71878] | 24 / 0 / 0 | 1.04e-26 | 0.000243 | 0.000243 |
| SBM | triangle deletion | WL | 0.1 → 1.0 | +391.5 | [384.18, 398.82] | 24 / 0 / 0 | 1.6e-29 | — | 0.000243 |
| SBM | triangle insertion | Diversity | 0.1 → 1.0 | +9.19271 | [9.1645, 9.221] | 24 / 0 / 0 | 1.6e-47 | — | 0.000243 |
| SBM | triangle insertion | NetLSD | 0.1 → 1.0 | +0.170758 | [0.17027, 0.17124] | 24 / 0 / 0 | 2.66e-48 | — | 0.000243 |
| SBM | triangle insertion | GraphStats | 0.1 → 1.0 | +0.243647 | — | 24 / 0 / 0 | — | 0.000243 | 0.000243 |
| SBM | triangle insertion | WL | 0.1 → 1.0 | +278.284 | — | 24 / 0 / 0 | — | 0.000243 | 0.000243 |
