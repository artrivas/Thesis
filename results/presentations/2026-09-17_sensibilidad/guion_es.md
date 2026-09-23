# Sensibilidad a perturbaciones estructurales

[Presentación editada en Google Slides](https://docs.google.com/presentation/d/1ZE-LmtIFOjXrr09gFOXzKS_KyRU5YGX1mrZFI4sAn7w/edit)

Guion de la versión final: 14 diapositivas, centradas en BA, ER y SBM. Las notas incluyen las condiciones experimentales y las fuentes.

## 1. Sensibilidad a perturbaciones estructurales

BA: respuesta temprana y pérdida de resolución

Controles del kernel y de estructura comunitaria

**Notas del orador**

Conclusión principal: respuesta temprana y resolución de severidad pueden divergir. En BA, GraphStats reacciona con fuerza al principio, pero el score disminuye al seguir añadiendo aristas. Los controles del kernel y las comparaciones comunitarias en ER y SBM ayudan a explicar esta respuesta. No comparamos potencia estadística sin calibración. Estructura inspirada en Chua et al. (2025): https://www.lesswrong.com/posts/i3b9uQfjJjJkwZF4f/tips-on-empirical-research-slides

## 2. Adiciones, mecanismos y comunidades

Adiciones en BA: 5 minutos

Kernel y ancho de banda: 5 minutos

Comunidades en ER y SBM: 5 minutos

Decisiones y preguntas: 3 minutos

**Notas del orador**

Prioridad: evaluar la hipótesis de pérdida de resolución ante adiciones y explicar sus mecanismos con controles. Los tiempos son orientativos para una reunión de avance. La última sección plantea qué calibrar antes de comparar sensibilidad de detección.

## 3. Resultados corregidos y sensibilidad

3 réplicas por configuración, con 100 grafos cada una.

11 valores de α sobre los mismos grafos de referencia.

Las curvas describen respuesta y resolución de severidad.

La potencia de detección requiere calibración adicional.

**Notas del orador**

Resultados corregidos exclusivamente. BA y ER son pilotos sintéticos. SBM es un control adicional corregido. Cada configuración tiene tres réplicas de 100 grafos. Los valores de α comparten grafos y no son observaciones independientes. Mostramos las tres réplicas, sin intervalos binomiales ni afirmaciones de significación. Fuentes: results/analysis/2026-09-16_structural_insights y results/analysis/2026-09-17_mmd_explanation.

## 4. En BA, más aristas pueden dar un score menor

![En BA, más aristas pueden dar un score menor](//wsl.localhost/Ubuntu/home/artrivas/Thesis/results/presentations/2026-09-17_sensibilidad/ba_adiciones.png)

**Notas del orador**

BA corregido, 50 nodos y 97 aristas originales. Tres réplicas de 100 grafos. El máximo aparece en α = 0,3 tras 29 adiciones. Al llegar a 97 adiciones, el score cae 12,8 % en inserción aleatoria y 16,3 % en cierre de triángulos. Menor score no significa menor distancia de edición. Fuente: addition_sensitivity.json.

## 5. GraphStats responde antes que WL en BA

![GraphStats responde antes que WL en BA](//wsl.localhost/Ubuntu/home/artrivas/Thesis/results/presentations/2026-09-17_sensibilidad/respuesta_temprana.png)

**Notas del orador**

BA, cierre de triángulos, tres réplicas. En α = 0,1, GraphStats alcanza el 57,8 % de su máximo medio y WL el 8,4 %. Cada curva se normaliza por su propio máximo, por lo que comparamos forma, no magnitud ni potencia. Respuesta temprana y resolución de severidad son propiedades distintas. Detectar a un nivel de falsos positivos fijado exige calibración con referencias independientes. Fuente: kernel_substitutions.json.

## 6. MMD usa dos geometrías diferentes

GraphStats

9 estadísticas sin estandarizar y kernel RBF, σ = 10.

WL

Histogramas de grados y vecindarios y kernel lineal.

El kernel determina qué discrepancias mide MMD.

**Notas del orador**

GraphStats usa el estimador sesgado MMD² = Kxx + Kyy − 2Kxy con kernel gaussiano. WL usa MMD² lineal, que equivale a la distancia euclidiana al cuadrado entre medias de histogramas. El kernel lineal no detecta en general cambios de momentos superiores de la distribución de características. Fuente: Gretton et al. (2012), https://www.jmlr.org/papers/volume13/gretton12a/gretton12a.pdf . Implementación y controles: results/analysis/2026-09-17_mmd_explanation.

## 7. El ancho de banda cambia la respuesta

![El ancho de banda cambia la respuesta](//wsl.localhost/Ubuntu/home/artrivas/Thesis/results/presentations/2026-09-17_sensibilidad/ancho_de_banda.png)

**Notas del orador**

Control exploratorio sobre los mismos grafos BA y descriptores. Solo cambiamos σ. Un ancho de banda mayor desplaza la transición, pero σ = 100 no queda validado como óptimo general. Fijar σ entre intensidades mantiene la misma regla de medida. Importa su relación con la escala de los conteos crudos. O’Bray et al. (2022), https://arxiv.org/pdf/2106.01098 . Datos: kernel_substitutions.json.

## 8. El score cae aunque los cambios aumentan

BA, cierre de triángulos: α = 0,3 frente a α = 1

MMD²: 1,591 frente a 1,332

Kyy: 0,767 frente a 0,507, con Kxy ≈ 0

Desplazamiento de descriptores: 47,2 frente a 189,4

MMD² = Kxx + Kyy − 2Kxy, con Kxx constante

**Notas del orador**

Kxx: similitud media dentro de la colección original. Kyy: dentro de la perturbada. Kxy: entre colecciones. Al quedar Kxy casi en cero, la disminución de Kyy reduce MMD². La distancia euclidiana media de cada par de descriptores sigue aumentando. Esto explica la pérdida de resolución en esta trayectoria sin suponer que los grafos regresen hacia el original. Valores reconstruidos sobre registros corregidos. Fuente: mechanism_decompositions.json.

## 9. La ordenación comunitaria depende del dataset

Mediana de Spearman entre score y α positivo

ER: GraphStats −0,12 y WL 0,70

SBM: GraphStats 0,93 y WL 0,50

WL ordena mejor en ER y GraphStats en este SBM.

Estos valores describen ordenación, no potencia.

**Notas del orador**

Correlaciones por réplica y mediana de las tres, sin agrupar todos los puntos como independientes. Excluimos α = 0 porque las copias idénticas fuerzan score cero. ER no tiene comunidades plantadas. SBM sí las tiene y este resultado procede de un control adicional corregido. No concluimos que un método identifique mejor comunidades ni que tenga mayor potencia. Las escalas brutas de GraphStats y WL no son comparables. Fuente: community_comparison.json.

## 10. Los triángulos dominan la respuesta en SBM

![Los triángulos dominan la respuesta en SBM](//wsl.localhost/Ubuntu/home/artrivas/Thesis/results/presentations/2026-09-17_sensibilidad/control_triangulos_sbm.png)

**Notas del orador**

SBM, debilitamiento de comunidades, α = 1, ancho de banda 10, tres réplicas. Al omitir el conteo de triángulos, MMD² pasa de 0,317344 a 0,000846. Los triángulos medios bajan de 27,38 a 15,70. La respuesta mide una consecuencia estructural de la intervención, sin identificar directamente la partición. Las omisiones cambian la geometría del kernel y no equivalen a importancias causales aditivas. Barras: medias. Puntos: réplicas. Fuente: community_descriptor_ablation.json.

## 11. WL detecta cambios en los vecindarios

Grado 3: vecinos {1,1,4} frente a {2,2,2}.

WL distingue estos patrones tras un refinamiento.

En BA, 186 de 300 trayectorias individuales retroceden

al menos una vez, aunque crezca el score agregado.

El grado aporta el 98,4 % del score WL final en BA.

**Notas del orador**

El ejemplo de vecindarios es conceptual. WL deriva sus características de la topología, por lo que un cambio estructural altera sus histogramas. La implementación usa grados iniciales y tres rondas, sin etiquetas de comunidades ni atributos químicos. Los valores 186/300 y 98,4 % corresponden a BA con cierre de triángulos. La primera cifra indica algún descenso entre intensidades positivas consecutivas de la distancia individual. La segunda es una descomposición por niveles del kernel lineal. Fuente: Shervashidze et al. (2011), https://jmlr.org/papers/volume12/shervashidze11a/shervashidze11a.pdf . Datos: graph_trajectory_diagnostics.json y mechanism_decompositions.json.

## 12. Decisiones para evaluar sensibilidad

Calibrar umbrales con colecciones sin perturbación.

Fijar escalas y σ usando muestras de referencia.

Comparar comunidades preservando los grados.

Ampliar réplicas antes de generalizar.

¿Priorizamos detectar cambios pequeños

o distinguir grados de perturbación?

**Notas del orador**

Propuestas, no resultados ya ejecutados. La calibración debe usar referencias independientes y respetar el diseño emparejado a lo largo de α. Evitar elegir σ solo porque ordena bien estas curvas. La reconexión actual conserva aristas, pero no grados. La campaña completa corregida no se ha ejecutado. Hipótesis respaldada: con descriptores sin estandarizar y RBF σ = 10, grandes desplazamientos por adiciones pueden reducir la resolución del score en BA.

## 13. Anexo: el kernel cambia la forma de la curva

![Anexo: el kernel cambia la forma de la curva](//wsl.localhost/Ubuntu/home/artrivas/Thesis/results/presentations/2026-09-17_sensibilidad/control_del_kernel.png)

**Notas del orador**

Control exploratorio sobre BA con cierre de triángulos. Con los mismos descriptores GraphStats, el kernel lineal elimina el pico temprano observado con RBF. En α = 0,1 alcanza el 0,55 % de su máximo frente al 57,8 % de RBF. Para WL, el ancho RBF usa la mediana de distancias positivas entre representaciones originales por réplica, aproximadamente 19,7–19,9, fijo a lo largo de α. Cada curva se normaliza por su propio máximo. Las configuraciones oficiales no cambian. Fuente: kernel_substitutions.json.

## 14. Anexo: comunidades en ER, réplica por réplica

![Anexo: comunidades en ER, réplica por réplica](//wsl.localhost/Ubuntu/home/artrivas/Thesis/results/presentations/2026-09-17_sensibilidad/comunidades_er.png)

**Notas del orador**

ER no tiene partición plantada. La media de triángulos cambia poco, de 33,71 a 33,41, y el número de aristas permanece igual. WL puede registrar cambios en patrones de vecindario que no alteran mucho estos resúmenes. Pero aproximadamente el 99,7 % de las etiquetas de sus rondas profundas son exclusivas en estos conjuntos. Incluso muestras independientes sin perturbación aportan aproximadamente 1,0 por ronda profunda. Por eso una puntuación positiva no demuestra un efecto comunitario. Las pocas referencias disponibles ilustran el mecanismo y no calibran un test. Fuente: community_comparison.json y wl_resolution_diagnostic.json.
