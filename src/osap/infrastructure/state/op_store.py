"""Base de datos operativa de osap-api (MySQL).

Aloja SOLO estado operativo del propio osap-api, nunca una copia del catálogo de
osap-storage. Contiene: sugerencias de fuentes/proveedores y su auditoría, proveedores
dinámicos + configuración de conectores, y configuración operativa persistente.

`OpStore` es una factoría: intenta usar MySQL y, si no está disponible (usuario/BD sin
crear en el entorno), degrada a un almacén en memoria para no tumbar el servicio.

Facade (F5.2): la implementación vive en `src/osap/infrastructure/state/op/`.
"""

from __future__ import annotations

from src.osap.infrastructure.state.op import _MemoryStore, _MysqlStore, _now, build_op_store

__all__ = ["build_op_store", "_MemoryStore", "_MysqlStore", "_now"]
