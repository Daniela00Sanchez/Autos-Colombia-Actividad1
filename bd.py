"""SQLite de la iteracion 1. Trabaja con una copia LOCAL de la base."""
from pathlib import Path
import sqlite3
from contextlib import contextmanager

RAIZ = Path(__file__).resolve().parent
RUTA_BD = RAIZ / 'data' / 'Autos_Colombia_Iteracion1.sqlite'


@contextmanager
def conectar(ruta=None):
    destino = str(ruta or RUTA_BD)
    bd = sqlite3.connect(destino, timeout=10)
    try:
        bd.row_factory = sqlite3.Row
        bd.execute('PRAGMA foreign_keys = ON')
        with bd:
            yield bd
    finally:
        bd.close()


def inicializar(ruta=None):
    destino = Path(ruta or RUTA_BD)
    destino.parent.mkdir(parents=True, exist_ok=True)
    esquema = (RAIZ/'data'/'01_Esquema_SQLite.sql').read_text(encoding='utf-8')
    ejemplos = (RAIZ/'data'/'02_Datos_Ejemplo.sql').read_text(encoding='utf-8')
    with conectar(destino) as bd:
        # CREATE IF NOT EXISTS e INSERT OR IGNORE permiten reiniciar sin borrar movimientos.
        bd.executescript(esquema)
        bd.executescript(ejemplos)
        comprobacion = bd.execute('PRAGMA integrity_check').fetchone()[0]
        if comprobacion != 'ok':
            raise RuntimeError('La base de datos necesita revisión: ' + comprobacion)
        bd.commit()
    return destino
