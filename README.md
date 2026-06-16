# Punto de Equilibrio y Rentabilidad Comercial

V1 enfocada en carga, normalizacion, validacion y deteccion del nivel de
analisis habilitado.

## Ejecucion

```powershell
streamlit run app.py
```

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

## Niveles

- `NIVEL_1_GLOBAL`: EERR valido sin detalle de ventas.
- `NIVEL_1_GLOBAL_CON_ADVERTENCIA`: ventas cargadas sin requisitos suficientes.
- `NIVEL_2_COMERCIAL`: EERR y ventas con costos validos, conservando advertencias.
