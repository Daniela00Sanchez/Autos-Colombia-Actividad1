"""Inicialización y migración local de SQLite; no borra registros existentes."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

RAIZ = Path(__file__).resolve().parent
RUTA_BD = RAIZ / 'data' / 'Autos_Colombia_Iteracion2.sqlite'

@contextmanager
def conectar(ruta=None):
    bd = sqlite3.connect(str(ruta or RUTA_BD), timeout=20)
    bd.row_factory = sqlite3.Row
    bd.execute('PRAGMA foreign_keys=ON')
    bd.execute('PRAGMA busy_timeout=20000')
    try:
        with bd:
            yield bd
    finally:
        bd.close()

def agregar_columna(bd, tabla, columna, definicion):
    columnas = {r['name'] for r in bd.execute(f'PRAGMA table_info({tabla})')}
    if columna not in columnas:
        bd.execute(f'ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}')

def inicializar(ruta=None):
    destino = Path(ruta or RUTA_BD)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with conectar(destino) as bd:
        existente = bd.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='vehiculo'").fetchone()
        bd.executescript((RAIZ/'data'/'01_Esquema_SQLite.sql').read_text(encoding='utf-8'))
        if not existente:
            bd.executescript((RAIZ/'data'/'02_Datos_Ejemplo.sql').read_text(encoding='utf-8'))
        bd.executescript((RAIZ/'data'/'03_Iteracion2.sql').read_text(encoding='utf-8'))
        agregar_columna(bd, 'movimiento', 'celda_id', 'INTEGER REFERENCES celda(id)')
        agregar_columna(bd, 'movimiento', 'entrada_usuario_id', 'INTEGER REFERENCES usuario(id)')
        agregar_columna(bd, 'movimiento', 'salida_usuario_id', 'INTEGER REFERENCES usuario(id)')
        agregar_columna(bd, 'movimiento', 'anulado', 'INTEGER NOT NULL DEFAULT 0')
        agregar_columna(bd, 'vehiculo', 'creado_por_id', 'INTEGER REFERENCES usuario(id)')
        agregar_columna(bd, 'novedad', 'usuario_id', 'INTEGER REFERENCES usuario(id)')
        bd.execute('''CREATE UNIQUE INDEX IF NOT EXISTS uq_movimiento_celda_activa
            ON movimiento(celda_id) WHERE fecha_hora_salida IS NULL AND celda_id IS NOT NULL''')
        bd.execute('CREATE INDEX IF NOT EXISTS idx_auditoria_fecha ON auditoria(id DESC)')
        # Para datos de ejemplo de la primera iteración: asignación inicial orientativa.
        if bd.execute('SELECT COUNT(*) FROM celda').fetchone()[0] == 0:
            cap = bd.execute('SELECT capacidad_total FROM configuracion WHERE id=1').fetchone()
            for n in range(1, (cap[0] if cap else 20)+1):
                bd.execute('INSERT INTO celda (codigo, activa) VALUES (?,1)', (f'C-{n:02}',))
        movimientos = bd.execute('''SELECT id_movimiento FROM movimiento
                WHERE fecha_hora_salida IS NULL AND celda_id IS NULL ORDER BY id_movimiento''').fetchall()
        for m in movimientos:
            libre = bd.execute('''SELECT c.id FROM celda c WHERE c.activa=1 AND NOT EXISTS
                (SELECT 1 FROM movimiento x WHERE x.celda_id=c.id AND x.fecha_hora_salida IS NULL)
                ORDER BY c.codigo LIMIT 1''').fetchone()
            if libre:
                bd.execute('UPDATE movimiento SET celda_id=? WHERE id_movimiento=?', (libre['id'], m['id_movimiento']))
        verificacion = bd.execute('PRAGMA integrity_check').fetchone()[0]
        if verificacion != 'ok':
            raise RuntimeError('Revisar la base de datos: ' + verificacion)
    return destino
