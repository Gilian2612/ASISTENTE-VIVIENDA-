# Precio y arriendo estimado

Este documento explica de dónde sale la variable **`precio`** del recomendador y el **arriendo estimado** que se usa para el filtro de presupuesto.

Código: [`src/ETL/precio.py`](../src/ETL/precio.py) y [`src/ETL/calibracion.py`](../src/ETL/calibracion.py) · Datos: columnas `avaluo_ph_m2`, `manzanas_ph`, `avaluo_fuente`, `arriendo_avaluo`, `arriendo_estimado` y `precio` de [`data/zonas.csv`](../data/zonas.csv); muestra de anuncios en [`data/calibracion_arriendos.csv`](../data/calibracion_arriendos.csv).

## Resumen

| Qué | Cómo se obtiene | ¿Dato oficial? |
|---|---|---|
| **Precio relativo** entre UPZ (variable `precio` del KNN) | Mediana del avalúo catastral por m² de apartamentos de cada UPZ | ✅ Sí (Catastro Bogotá) |
| **Arriendo en pesos** (filtro de presupuesto) | Avalúo → valor comercial → arriendo con la tasa de renta del Observatorio Técnico Catastral | ⚠️ Estimación con supuestos documentados |
| **Calibración** del arriendo en pesos | Factor de corrección calculado con anuncios reales de Metrocuadrado y Fincaraíz recogidos a mano | ✅ Datos de mercado (muestra) |

## 1. Fuente: avalúo catastral de apartamentos

- **Entidad:** Unidad Administrativa Especial de Catastro Distrital (UAECD), Catastro Bogotá.
- **Servicio (ArcGIS REST, público y sin clave):**
  `https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services/catastro/medavalcatphmz/MapServer/1`
- **Capa:** *Mediana del avalúo catastral por m² de predios en PH por manzana según grupo de uso económico*.
- **Campo usado:** `AV_CAT_PH_RESIDENCIAL`, la mediana del avalúo catastral por m² de predios en **propiedad horizontal residencial** (apartamentos), en COP.
- **Vigencia usada:** **2026**, con 14.957 manzanas con dato. La capa trae las vigencias de 2017 a 2026; el ETL filtra solo 2026.
- También está publicado en [Datos Abiertos Bogotá](https://datosabiertos.bogota.gov.co/dataset/med-aval-cat-ph-mz-bogota-d-c-por-grupo-economico).

### De manzana a UPZ

1. Cada manzana se asigna a la UPZ donde cae su centroide.
2. El valor de la UPZ es la **mediana** de sus manzanas. Se usa la mediana y no el promedio para que unas pocas manzanas atípicas no muevan el resultado.
3. Si la UPZ tiene **menos de 3 manzanas** con apartamentos, se usa la mediana de **su localidad** (columna `avaluo_fuente = localidad`), y si tampoco hay datos, la de la ciudad. Hoy esto pasa en 6 de las 112 UPZ, casi todas dotacionales o rurales: Parque Entrenubes, El Mochuelo, Jardín Botánico, Aeropuerto El Dorado, Paseo de los Libertadores y San Isidro–Patios.

### Variable `precio` del KNN

```
precio = 1 − (avalúo/m² de la UPZ ÷ percentil 95 de las UPZ residenciales), recortado a [0, 1]
```

1 = la más barata y 0 = la más cara. Es la misma normalización que usan las demás variables.

## 2. Arriendo estimado (COP / mes)

```
arriendo ≈ (avalúo/m² ÷ relación avalúo/comercial) × área típica × tasa de renta anual ÷ 12
```

| Parámetro | Valor | Fuente / justificación |
|---|---|---|
| Tasa de renta (canon / valor comercial) | **6,2 % anual** | Observatorio Técnico Catastral (OTC, UAECD), [*Tasa de renta inmobiliaria: rentabilidad del arriendo de vivienda en Bogotá*](https://www.catastrobogota.gov.co/sites/default/files/archivos/20221230_rentabilidad_final.pdf). Se calcula con ofertas reales de venta y arriendo; la tasa oscila alrededor del 6,2 % anual, y en apartamentos va entre 5,9 % y 6,3 % según el estrato |
| Relación avalúo catastral / valor comercial | **85 %** | En Bogotá el avalúo catastral está [entre el 70 % y el 100 %](https://www.minuto60.com/bogota/cuales-fueron-las-zonas-bogota-que-mas-se-valorizaron-2025-estudio-revela-cifras/5341) del valor comercial; el [marco legal general](https://actualicese.com/incremento-de-los-avaluos-catastrales-2025/) es 60 %–100 %. Se usa el punto medio |
| Área típica del apartamento | **60 m²** | Supuesto del proyecto |

**Ejemplo:** avalúo de 2.550.000 COP/m² → valor comercial 3.000.000 COP/m² → × 60 m² = 180 M → × 6,2 % ÷ 12 ≈ **930.000 COP/mes**.

El valor se redondea a miles de pesos y queda en la columna `arriendo_avaluo`. Los tres parámetros son constantes en `src/ETL/precio.py` (`TASA_RENTA_ANUAL`, `RELACION_AVALUO_COMERCIAL`, `AREA_TIPICA_M2`) y se pueden ajustar.

## 3. Calibración con anuncios de Metrocuadrado y Fincaraíz

El valor en pesos del paso anterior puede quedar desplazado frente al mercado. Para corregirlo se usa una **muestra de anuncios reales recogida a mano**.

> **¿Por qué a mano y no con scraping?** Metrocuadrado tiene protección anti-bots (Incapsula) y Fincaraíz bloquea scrapers en su `robots.txt`. Tampoco se pudo confirmar que sus términos de uso permitan la extracción automática. Una muestra pequeña copiada a mano es suficiente para calcular un factor y evita esos problemas.

### Cómo recoger la muestra

Llena [`data/calibracion_arriendos.csv`](../data/calibracion_arriendos.csv), con un anuncio por fila:

| Columna | Qué poner | Ejemplo |
|---|---|---|
| `fuente` | `metrocuadrado` o `fincaraiz` | `fincaraiz` |
| `fecha` | Fecha de consulta (AAAA-MM-DD) | `2026-11-20` |
| `url` | Link del anuncio (para trazabilidad) | `https://www.fincaraiz.com.co/...` |
| `upz` | Nombre o código de la UPZ (ver columna `nombre` / `codigo_upz` de `data/zonas.csv`) | `Chapinero` o `99` |
| `area_m2` | Área privada del apartamento | `58` |
| `canon_cop` | Arriendo mensual **sin administración** | `1850000` |

Recomendaciones:
- **Solo apartamentos** (la base es el avalúo de propiedad horizontal), de 30 a 120 m².
- **Mínimo 20 anuncios en al menos 5 UPZ;** idealmente 40 a 60 en 10 a 15 UPZ de distintos estratos, mitad de cada portal.
- Si el anuncio solo trae el barrio, ubícalo en una UPZ con el mapa de [mapas.bogota.gov.co](https://mapas.bogota.gov.co).
- Se aceptan formatos como `1.850.000`, `$ 1,850,000` o `62,5`.

### Cómo se calcula

1. Cada anuncio se lleva a un apartamento de 60 m²: `canon_60 = canon ÷ área × 60`.
2. Razón del anuncio: `canon_60 ÷ arriendo_avaluo` de su UPZ.
3. **Factor = mediana de las razones**; la mediana hace que unos pocos anuncios atípicos no cambien el resultado.
4. `arriendo_estimado = arriendo_avaluo × factor`, redondeado a miles.

El factor es uno solo para toda la ciudad, así que **no cambia el orden entre UPZ** (la variable `precio`); solo corrige el valor en pesos que usa el filtro de presupuesto. Si la muestra no alcanza el mínimo, no se aplica (`arriendo_estimado = arriendo_avaluo`) y el reporte dice por qué. Los anuncios inválidos se descartan, indicando la línea y el motivo.

### Cómo correrla

```bash
cd src && python3 -m ETL.calibracion        # recalibra data/zonas.csv sin volver a descargar las fuentes
```

Ejemplo de reporte:

```
Anuncios usados: 42 en 12 UPZ
  fincaraiz: 21 anuncios, factor 1.58
  metrocuadrado: 21 anuncios, factor 1.49
Factor (mediana): 1.53  [p25 1.31 - p75 1.79]
✓ Calibración aplicada: arriendo_estimado = arriendo_avaluo × 1.53
```

`python3 -m ETL.construir_zonas` también aplica la calibración al final, si el archivo tiene anuncios.

## 4. Limitaciones

- **Es una estimación, no un precio de mercado.** No existe en datos abiertos un canon de arriendo por UPZ. El Visor Inmobiliario y el OTC tienen ofertas, pero no se publican por UPZ.
- **Sin calibrar, los valores en pesos podrían estar por debajo del mercado.** Comparados con precios de arriendo habituales parecen bajos (por ejemplo, Chapinero ≈ 1,3 M). Probablemente el avalúo catastral de apartamentos esté más lejos del valor comercial que el 85 % supuesto. Para eso está la calibración de la sección 3. **El orden entre UPZ (`precio`) no se ve afectado** en ningún caso.
- **El factor de calibración es único.** Si la subestimación es distinta en estratos altos y bajos, un factor único no la corrige del todo; el reporte por portal y los cuartiles ayudan a verlo. Con una muestra grande se podría calibrar por estrato o por localidad.
- **La muestra es manual y pequeña.** Su calidad depende de que los anuncios sean apartamentos, con canon sin administración y la UPZ correcta.
- Otra opción para el valor absoluto: solicitar al OTC las ofertas de arriendo por UPZ (observatoriotecnicocatastral@catastrobogota.gov.co).
- **Tasa de renta única.** El OTC reporta tasas algo más altas en estratos bajos; hoy se usa un solo valor para toda la ciudad.
- **Solo apartamentos (PH).** Las casas, fuera de propiedad horizontal, no entran en esta capa.

## 5. Cómo actualizar

```bash
cd src && python3 -m ETL.construir_zonas      # descarga y regenera data/zonas.csv
python3 -m ETL.calibracion                    # (desde src/) solo recalibra con data/calibracion_arriendos.csv
pytest -m integration --no-cov                # verifica las fuentes reales
```

Para usar otra vigencia, cambia `VIGENCIA` en `src/ETL/precio.py`.
