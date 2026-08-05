# Golden dataset real de OSAP

Aquí se guardan los resultados reales de consultas, capturados **una sola vez**,
para desarrollar el motor de fusión **sin volver a consultar Internet**.

## Flujo de trabajo

1. **Capturar** (una vez por consulta):
   ```powershell
   python tests/fusion/capture.py --composer Mozart
   python tests/fusion/capture.py --title "Ave Verum Corpus"
   ```
   → genera `tests/golden/<slug>_<fecha>.yaml` con TODAS las representaciones
   recibidas (title / composer / provider / format).

2. **Desarrollar contra ese fichero** (sin red):
   ```powershell
   cd tests/fusion
   python fusion_test.py ../golden/mozart_2026_08_02.yaml          # trace del flujo
   python fusion_test.py ../golden/mozart_2026_08_02.yaml --group   # agrupación
   python fusion_test.py ../golden/mozart_2026_08_02.yaml --diff    # diferencias
   python fusion_test.py ../golden/mozart_2026_08_02.yaml --trace   # DECISION por pareja
   ```

3. **Regla de regresión**: cuando una fusión falle, NO se corrige el algoritmo
   directamente. Primero se añade el caso al golden dataset (o al
   `tests/fusion/golden dataset/merge_cases.yaml`) y después se ajusta el motor.
   Así cada error real queda como prueba permanente.

## Por qué

- **Reproducible**: el problema deja de depender de la red y de los proveedores.
- **Comparable**: cada cambio del algoritmo tiene una respuesta objetiva:
  el laboratorio dice exactamente qué casos mejoran y cuáles empeoran.
- **Evolución segura**: cuando todos los casos del golden pasen, se integra el
  nuevo motor en `osap resolve`. La CLI es solo un **consumidor** del motor.

## Estructura

```
tests/golden/                        # volcados reales (capturados una vez)
tests/fusion/golden dataset/         # casos sintéticos + regresión (a1-a4, merge_cases)
tests/fusion/fusion_test.py          # laboratorio (flujo / --group / --diff / --trace)
tests/fusion/capture.py              # genera un golden dataset desde osap resolve
tests/fusion/mozart.yaml             # ejemplo de volcado crudo
```
