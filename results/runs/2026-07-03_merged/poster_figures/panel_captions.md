# Panel captions (for poster layout, not embedded in the figure)

**A. Local edge deletion** (consistent detection)

In SBM, all workflows respond monotonically to edge deletion, but their response speed differs. This confirms that local edge perturbations are detectable, while still revealing different sensitivity thresholds.

**B. Triangle insertion** (method disagreement)

Triangle insertion separates response profiles: GraphStats+MMD saturates early, while WLFeatures+MMD, NetLSD, and DiversityCurveDistance provide a more gradual sensitivity curve.

**C. Hub modification on real graphs** (real-data saturation)

On IMDB-BINARY, hub modification produces early saturation, especially for GraphStats+MMD, while other workflows converge after intermediate perturbation levels.

**D. Hub modification in ER** (unstable global signal)

In structureless ER graphs, hub modification produces rapid saturation and large seed variability, suggesting that global perturbations can become unstable or hard to interpret.

**E. Ground-truth community weakening** (ground-truth community signal)

In SBM, community weakening produces a meaningful mesoscopic signal because the partition is part of the generative process. WLFeatures+MMD reacts early, while GraphStats+MMD responds more slowly.

**F. Detected-community weakening** (pseudo-community signal)

In IMDB-BINARY, detected communities provide an operational mesoscopic signal, but they should be interpreted as pseudo-labels rather than ground truth.

**Shared note (place once under the whole figure):** Scores are normalized within each workflow to compare response profiles, not absolute distance magnitudes.