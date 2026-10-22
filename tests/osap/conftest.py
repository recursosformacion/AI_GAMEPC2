"""Aísla la suite de la configuración local del desarrollador.

Los tests que construyen la app real (`create_platform_app()`) leerían `osap.toml`, que en
desarrollo puede apuntar por túnel a la BD de producción (`dev_mode = 1`). La suite debe ser
determinista y no depender de la red ni escribir en producción: se fuerza una configuración
de test (dev local, BD inalcanzable → los stores degradan a memoria).
"""

import os
from pathlib import Path

_TEST_CONFIG = Path(__file__).with_name("osap.test.toml")

os.environ["OSAP_CONFIG"] = str(_TEST_CONFIG)
os.environ["OSAP_ENV"] = "development"
