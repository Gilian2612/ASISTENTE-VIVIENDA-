<a id="top"></a>

<div align="center">

# Housing Suggestions in Bogotá

# Sugerencias de Vivienda en Bogotá

[English](#english) | [Español](#español)

</div>

---

<a id="english"></a>

# English

**Weighted KNN recommender for Bogotá zones (UPZ).**
PTIA Project — Group 01 · Nicolás Prieto · William Santiago Ruiz Medina
Escuela Colombiana de Ingeniería Julio Garavito — Systems Engineering Department

> Current status: **Milestone 2** (interface prototype + solution progress). Zone data is **sample data**; the real dataset will be built in Milestone 3.

[↑ Back to top](#top) · [Ir a Español](#español)

## What is it and what problem does it solve?

People moving to Bogotá, or within it, rarely know which criteria to use when choosing a neighborhood (transport, safety, price, proximity to universities, green areas) and end up deciding based on other people's opinions. Real-estate portals help find a specific property, but not translate a lifestyle into an area of the city.

This system takes **what matters to the user** and **their maximum rent budget**, and returns the **3 zones of Bogotá that best match their profile**, with a similarity percentage. It recommends *where to look*, not *which property to take*.

## Goals

### Main goal

Develop a recommendation system based on K-Nearest Neighbors (KNN) that, from the importance a user assigns to public transport, safety, rent price, proximity to universities and green areas, plus their maximum budget, recommends the three Bogotá zones that best fit their profile, with a similarity percentage and an explanation for each recommendation, so that the decision of where to live is based on objective data rather than third-party opinions.

### Quantitative goals

- Build a dataset of at least **20 zones** (UPZ or neighborhoods) of Bogotá with the 5 normalized variables and documented sources.
- On at least **10 test profiles**, ensure that in **80%** of cases the top 3 includes a suitable zone.
- Over **70%** of test users rate the recommendation as useful (4 or 5 out of 5).
- Response time under **10 seconds**.

### Qualitative goal

- **Explainability:** each recommendation must show which variables justify it and which are not met (e.g. `Transport ✓`, `High price ✗`).

## How does it work?

1. **Data:** each zone is a point in a 5-dimensional space: transport, safety, price, universities and green areas, normalized to `[0, 1]` where **1 is always the best** (price is inverted: cheaper means closer to 1). Each zone also has its average rent in COP.
2. **User input:** the importance (1–5) of each variable and a maximum rent budget.
3. **Hard filter:** zones whose average rent exceeds the budget are discarded.
4. **Query:** the ideal profile is `q = (1, 1, 1, 1, 1)` and the weights `w` come from the user's importances.
5. **Weighted Euclidean distance:**

   ```
   d(z) = sqrt( Σ wᵢ · (zᵢ − 1)² )
   ```

6. **Ranking and similarity:** the K = 3 closest zones are taken and the distance is converted to a percentage:

   ```
   similarity = (1 − d / d_max) · 100        with d_max = sqrt(Σ wᵢ)
   ```

7. **Explanation:** for the most important variables, ✓ is shown if the zone's value is high (≥ 0.6) and ✗ if it is low (≤ 0.4).

Why KNN: the problem is literally "find the zones most similar to what I want"; it is explainable (distance decomposes per variable), needs no training or labels, and truly personalizes (same data, different weights, different result).

## Use cases

| Case | Description |
|---|---|
| **UC1** Enter preferences | Five sliders (1–5) and maximum budget |
| **UC2** View recommended neighborhoods | Top 3 with similarity % and ✓/✗ tags |
| **UC3** View neighborhood detail (*include*) | Value of each variable, rent and locality |
| **UC4** Compare neighborhoods (*extend*) | Side-by-side table of two zones |

```
Preferences (UC1) ──► Recommended zones (UC2) ──► Detail (UC3)
                              │                        │
                              └──► Compare (UC4) ◄─────┘
```

## Architecture

| Component | Responsibility |
|---|---|
| **Data module (ETL)** | Obtain, clean, merge and normalize data per zone (`zonas.csv`). *Pending (Milestone 3).* |
| **Weighted KNN engine** | Filter by budget, compute distances and return the K closest zones. |
| **Interface (UI)** | Capture preferences and show results, detail and comparison. |
| **Explanation module** | Convert distances into similarity and generate ✓/✗ tags. |

## Repository structure

```
.
├── FRONT/
│   └── index.html          # Interface prototype (HTML + CSS + JS, no dependencies)
├── KNN/
│   └── knn.py              # KNN engine in Python (standard library only)
├── tests/
│   └── test_knn.py         # Unit tests (pytest)
├── DOCS/                   # Project documents: milestones, guidelines, template, 5y6.md
├── Plantilla_Proyectos_PTIA_ECI_LaTeX/  # LaTeX report template
├── SSFOTOSPPT/             # Screenshots used in presentations
├── pyproject.toml          # pytest and coverage configuration
└── requirements-dev.txt    # Development dependencies
```

The full justification (scope, methodological design, tools and architecture) is in `DOCS/5y6.md` and the milestone documents in `DOCS/`.

## How to run

### Interface prototype

Open `FRONT/index.html` in a browser; no installation needed. The KNN engine is implemented in JavaScript with the same formulas and a simulated dataset of 22 UPZ. "Save search", "View available properties" and the map are **simulated**.

### KNN engine in Python

Requires Python 3 and uses only the standard library:

```bash
python3 -m KNN.knn
```

As a library:

```python
from KNN.knn import recomendar

# Order: transport, safety, price, universities, green areas
recomendar([5, 4, 3, 5, 2], presupuesto=1_800_000, k=3)
# -> [(zone, similarity %), ...]
```

### Tests and coverage

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

`pytest` produces coverage reports (terminal, `htmlcov/` and `coverage.xml`) and fails if coverage drops below 90%.

## Scope

**Included:** Bogotá only; analysis unit is the UPZ (or a representative set of neighborhoods); five variables; top 3 with zone comparison.

**Out of scope:** home purchase, specific properties, real-time prices, proximity to the user's exact workplace, schools, parking and other cities.

## Roadmap

| Milestone | Content | Status |
|---|---|---|
| **1. Exploration** | Context and relevance, paper prototype | ✅ |
| **2. Problem and progress** | Scope, methodological design, interface prototype, first KNN engine | ⏳ In progress |
| **3. Solution and evaluation** | Real dataset (DANE, Bogotá Open Data, Security Secretariat, TransMilenio, IDRD, housing portals), migration to pandas + scikit-learn, API (Flask/FastAPI), explanation module and evaluation | Pending |

## Technologies

Python 3 · pytest / pytest-cov · HTML, CSS and JavaScript. Planned for Milestone 3: pandas, scikit-learn, NumPy and Flask or FastAPI.

---

<a id="español"></a>

# Español

**Recomendador de zonas (UPZ) de Bogotá basado en KNN ponderado.**
Proyecto PTIA — Grupo 01 · Nicolás Prieto · William Santiago Ruiz Medina
Escuela Colombiana de Ingeniería Julio Garavito — Departamento de Ingeniería de Sistemas

> Estado actual: **Hito 2** (prototipo de interfaz + avance de la solución). Los datos de zonas son **de ejemplo**; el dataset real se construirá en el Hito 3.

[↑ Volver arriba](#top) · [Go to English](#english)

## ¿Qué es y qué problema resuelve?

Quien se muda a Bogotá, o dentro de ella, rara vez sabe qué criterios usar para elegir en qué zona vivir (transporte, seguridad, precio, cercanía a universidades, zonas verdes) y termina decidiendo por opiniones de terceros. Los portales inmobiliarios ayudan a encontrar un inmueble concreto, pero no a traducir un estilo de vida en una zona de la ciudad.

Este sistema recibe **qué le importa al usuario** y **cuánto puede pagar de arriendo**, y devuelve las **3 zonas de Bogotá más afines a su perfil**, con un porcentaje de similitud. Recomienda *dónde buscar*, no *qué inmueble tomar*.

## Objetivos

### Objetivo principal

Desarrollar un sistema de recomendación basado en K vecinos más cercanos (KNN) que, a partir de la importancia que un usuario le asigna al transporte público, la seguridad, el precio de arriendo, la cercanía a universidades y las zonas verdes, y de su presupuesto máximo, recomiende las tres zonas de Bogotá más afines a su perfil, con un porcentaje de similitud y una explicación de cada recomendación, para que la decisión de dónde vivir se base en datos objetivos y no en opiniones de terceros.

### Objetivos cuantitativos

- Construir un dataset con al menos **20 zonas** (UPZ o barrios) de Bogotá, con las 5 variables normalizadas y fuentes documentadas.
- En al menos **10 perfiles de prueba**, lograr que en el **80 %** de los casos el top 3 incluya una zona considerada adecuada.
- Que más del **70 %** de los usuarios de prueba califiquen la recomendación como útil (4 o 5 de 5).
- Tiempo de respuesta menor a **10 segundos**.

### Objetivo cualitativo

- **Explicabilidad:** cada recomendación debe mostrar qué variables la justifican y cuáles no se cumplen (por ejemplo, `Transporte ✓`, `Precio alto ✗`).

## ¿Cómo funciona?

1. **Datos:** cada zona es un punto en un espacio de 5 dimensiones: transporte, seguridad, precio, universidades y zonas verdes, normalizadas en `[0, 1]` donde **1 siempre es lo mejor** (el precio se invierte: más barato, más cercano a 1). Cada zona tiene además su arriendo promedio en COP.
2. **Entrada del usuario:** la importancia (1–5) de cada variable y un presupuesto máximo de arriendo.
3. **Filtro duro:** se descartan las zonas cuyo arriendo promedio supera el presupuesto.
4. **Consulta:** el perfil ideal es `q = (1, 1, 1, 1, 1)` y los pesos `w` salen de las importancias del usuario.
5. **Distancia euclidiana ponderada:**

   ```
   d(z) = sqrt( Σ wᵢ · (zᵢ − 1)² )
   ```

6. **Ranking y similitud:** se toman las K = 3 zonas más cercanas y se convierte la distancia en porcentaje:

   ```
   similitud = (1 − d / d_max) · 100        con d_max = sqrt(Σ wᵢ)
   ```

7. **Explicación:** para las variables más importantes se marca ✓ si el valor de la zona es alto (≥ 0,6) y ✗ si es bajo (≤ 0,4).

Por qué KNN: el problema es literalmente "encontrar las zonas más parecidas a lo que quiero"; es explicable (la distancia se descompone por variable), no requiere entrenamiento ni etiquetas, y personaliza de verdad (mismos datos, distintos pesos, distinto resultado).

## Casos de uso

| Caso | Descripción |
|---|---|
| **CU1** Ingresar preferencias | Cinco sliders (1–5) y presupuesto máximo |
| **CU2** Ver barrios recomendados | Top 3 con % de similitud y etiquetas ✓/✗ |
| **CU3** Ver detalle del barrio (*include*) | Valor de cada variable, arriendo y localidad |
| **CU4** Comparar barrios (*extend*) | Tabla lado a lado de dos zonas |

```
Preferencias (CU1) ──► Barrios recomendados (CU2) ──► Detalle (CU3)
                              │                          │
                              └──► Comparar (CU4) ◄──────┘
```

## Arquitectura

| Componente | Responsabilidad |
|---|---|
| **Módulo de datos (ETL)** | Obtener, limpiar, unificar y normalizar datos por zona (`zonas.csv`). *Pendiente (Hito 3).* |
| **Motor KNN ponderado** | Filtrar por presupuesto, calcular distancias y devolver las K zonas más cercanas. |
| **Interfaz (UI)** | Capturar preferencias y mostrar resultados, detalle y comparación. |
| **Módulo de explicación** | Convertir distancias en similitud y generar etiquetas ✓/✗. |

## Estructura del repositorio

```
.
├── FRONT/
│   └── index.html          # Prototipo de interfaz (HTML + CSS + JS, sin dependencias)
├── KNN/
│   └── knn.py              # Motor KNN en Python (solo librería estándar)
├── tests/
│   └── test_knn.py         # Pruebas unitarias (pytest)
├── DOCS/                   # Documentos del proyecto: hitos, lineamientos, plantilla y 5y6.md
├── Plantilla_Proyectos_PTIA_ECI_LaTeX/  # Plantilla LaTeX del informe
├── SSFOTOSPPT/             # Capturas usadas en las presentaciones
├── pyproject.toml          # Configuración de pytest y cobertura
└── requirements-dev.txt    # Dependencias de desarrollo
```

La justificación completa (alcance, diseño metodológico, herramientas y arquitectura) está en `DOCS/5y6.md` y en los documentos de hitos de `DOCS/`.

## Cómo ejecutarlo

### Prototipo de interfaz

Abre `FRONT/index.html` en el navegador; no requiere instalación. El motor KNN está implementado en JavaScript con las mismas fórmulas y un dataset simulado de 22 UPZ. «Guardar búsqueda», «Ver inmuebles disponibles» y el mapa están **simulados**.

### Motor KNN en Python

Requiere Python 3 y solo usa la librería estándar:

```bash
python3 -m KNN.knn
```

Uso como librería:

```python
from KNN.knn import recomendar

# Orden: transporte, seguridad, precio, universidades, verdes
recomendar([5, 4, 3, 5, 2], presupuesto=1_800_000, k=3)
# -> [(zona, similitud %), ...]
```

### Pruebas y cobertura

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

`pytest` genera reportes de cobertura (terminal, `htmlcov/` y `coverage.xml`) y falla si la cobertura baja del 90 %.

## Alcance

**Incluye:** solo Bogotá; unidad de análisis por UPZ (o conjunto representativo de barrios); cinco variables; top 3 con comparación entre zonas.

**Fuera de alcance:** compra de vivienda, inmuebles específicos, precios en tiempo real, cercanía al lugar de trabajo exacto, colegios, garaje y otras ciudades.

## Hoja de ruta

| Hito | Contenido | Estado |
|---|---|---|
| **1. Exploración** | Contexto y relevancia, prototipo de papel | ✅ |
| **2. Problema y avance** | Alcance, diseño metodológico, prototipo de interfaz, primer motor KNN | ⏳ En curso |
| **3. Solución y evaluación** | Dataset real (DANE, Datos Abiertos Bogotá, Secretaría de Seguridad, TransMilenio, IDRD, portales de vivienda), migración a pandas + scikit-learn, API (Flask/FastAPI), módulo de explicación y evaluación | Pendiente |

## Tecnologías

Python 3 · pytest / pytest-cov · HTML, CSS y JavaScript. Previstas para el Hito 3: pandas, scikit-learn, NumPy y Flask o FastAPI.
