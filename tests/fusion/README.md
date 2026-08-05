# Fusion Laboratory

Laboratorio de fusión de obras musicales de OSAP. Es la herramienta que
**observa, mide y explica** el motor antes de cambiarlo. La CLI de OSAP es solo
un consumidor; toda la evolución del matcher se hace aquí contra datos reales.

## Estructura (separación de responsabilidades)

```
tests/fusion/
  parser.py     → ¿qué campos saco?      (extract_metadata)
  normalizer.py → ¿qué valor normalizado? (RepresentationIdentity, 7 campos)
  matcher.py    → ¿fusiona o no?          (reglas con prioridad → MergeDecision)
  explain.py    → ¿por qué?               (cadena de evidencias)
  identity.py   → identidad rica por rep (con confianza, para --identity)
  fusion_test.py→ CLI: vistas del laboratorio
  capture.py    → guarda una consulta real como golden dataset
  weights.yaml  → pesos/umbral tunables (sin recompilar)
  golden dataset/  → casos sintéticos de regresión (a1-a4, merge_cases)
```

El **parser** y el **normalizer** viven en `src/osap` (motor real); el lab los
consume. El **matcher** es un procedimiento de reglas sobre campos ya
normalizados (sin regexes, solo igualdades) y emite un `MergeDecision` con
evidencia.

## Vistas

```powershell
cd tests/fusion
python fusion_test.py mozart.yaml                 # trace del flujo por rep
python fusion_test.py mozart.yaml --group         # WORK 1..N
python fusion_test.py mozart.yaml --diff          # diferencias por campo
python fusion_test.py mozart.yaml --trace         # DECISION por pareja
python fusion_test.py mozart.yaml --fields        # campos de cada obra + SOURCE
python fusion_test.py mozart.yaml --identity      # identidad por rep
python fusion_test.py mozart.yaml --explain       # por qué se fusionó / no
python fusion_test.py <dir> --statistics          # presencia de campos (rápido, por fichero)
python fusion_test.py <casos> --measure           # precisión + TP/FP/FN
```

## Golden datasets

`tests/golden/` contiene **capturas reales** de `osap resolve --composer X`
(capturadas una vez con `capture.py`, sin volver a consultar red):
mozart, bach, beethoven, schubert, vivaldi, haendel, palestrina, victoria,
faure, brahms, verdi, bruckner, byrd, tallis, monteverdi, rutter +
`pathological.yaml` (casos frontera con etiqueta `work` para TP/FP/FN).

## Regla de regresión

Cuando una fusión falle: primero se añade el caso al golden dataset; después se
ajusta el motor. Nunca al revés. Así cada error real queda como prueba
permanente y el motor evoluciona con datos, no por intuición.

## Observación real (marzo 2026, 1258 reps, 17 ficheros)

- compositor presente 98.4%
- **catálogo presente 27.7%**  → el núcleo `{composer, catalog}` solo cubre ~1/4
- número presente 20.4%
- movimiento presente 4.3%
- tonalidad presente 11.0%
- **744 de 1167 obras (64%) dependen solo del título**

Conclusión: el catálogo es el dato más fuerte pero escaso; el sistema apoya
mucho en compositor + título + número. La KnowledgeBase (K550≈No40) reduciría
esa dependencia del título.
