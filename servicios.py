"""Reglas del parqueadero: entrada, salida, consultas, novedades (sin pagos/usuarios/celdas)."""
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from bd import conectar

HORA_COLOMBIA = timezone(timedelta(hours=-5))
TIPOS_NOVEDAD = ('Observacion general', 'Estado del vehiculo', 'Incidencia')


class ErrorNegocio(ValueError):
    pass


def ahora():
    """Hora local de Colombia en formato SQLite ISO 8601."""
    return datetime.now(HORA_COLOMBIA).strftime('%Y-%m-%d %H:%M:%S')


def normalizar_placa(valor):
    placa = (valor or '').strip().upper().replace(' ', '')
    if not re.fullmatch(r'[A-Z0-9]{5,8}', placa):
        raise ErrorNegocio('Ingresa una placa válida, por ejemplo MNV345 o TQR73F.')
    return placa


def dict_fila(fila):
    return dict(fila) if fila else None


def cupos(bd):
    total = bd.execute('SELECT capacidad_total FROM configuracion WHERE id=1').fetchone()
    if not total:
        raise ErrorNegocio('No se encontró la configuración de capacidad.')
    dentro = bd.execute('SELECT COUNT(*) FROM movimiento WHERE fecha_hora_salida IS NULL').fetchone()[0]
    return {'capacidad': total[0], 'dentro': dentro, 'disponibles': total[0]-dentro}


def consultar_placa(placa, ruta=None, momento=None):
    placa = normalizar_placa(placa)
    momento = momento or ahora()
    with conectar(ruta) as bd:
        vehiculo = dict_fila(bd.execute('SELECT * FROM vehiculo WHERE placa=?', (placa,)).fetchone())
        movimiento = dict_fila(bd.execute('''SELECT * FROM movimiento WHERE placa=?
            AND fecha_hora_salida IS NULL LIMIT 1''', (placa,)).fetchone())
        estado_cupos = cupos(bd)
    if not vehiculo:
        return {'placa': placa, 'registrado': False, 'vehiculo': None, 'movimiento': None,
                'vigente': False, 'puede_entrar': False, 'cupos': estado_cupos}
    vigente = vehiculo['vigencia_hasta'] >= momento[:10]
    return {'placa': placa, 'registrado': True, 'vehiculo': vehiculo,
            'movimiento': movimiento, 'vigente': vigente, 'cupos': estado_cupos,
            'puede_entrar': bool(vehiculo['autorizado'] and vigente
                                and movimiento is None and estado_cupos['disponibles'] > 0)}


def registrar_entrada(placa, ruta=None, momento=None):
    placa = normalizar_placa(placa)
    momento = momento or ahora()
    with conectar(ruta) as bd:
        bd.execute('BEGIN IMMEDIATE')
        vehiculo = bd.execute('SELECT * FROM vehiculo WHERE placa=?', (placa,)).fetchone()
        if not vehiculo:
            raise ErrorNegocio('Placa no registrada. Solo ingresan vehículos previamente autorizados.')
        if not vehiculo['autorizado']:
            raise ErrorNegocio('El vehículo no está autorizado para ingresar.')
        if vehiculo['vigencia_hasta'] < momento[:10]:
            raise ErrorNegocio('La mensualidad no está vigente. Comunícate con administración.')
        activo = bd.execute('SELECT 1 FROM movimiento WHERE placa=? AND fecha_hora_salida IS NULL', (placa,)).fetchone()
        if activo:
            raise ErrorNegocio('El vehículo ya está dentro; no puede registrarse otra entrada.')
        if cupos(bd)['disponibles'] < 1:
            raise ErrorNegocio('No hay cupos disponibles.')
        try:
            resultado = bd.execute('INSERT INTO movimiento (placa, fecha_hora_entrada) VALUES (?, ?)', (placa, momento))
        except sqlite3.IntegrityError as exc:
            raise ErrorNegocio('No fue posible registrar la entrada: ' + str(exc)) from exc
        bd.commit()
        return {'id_movimiento': resultado.lastrowid, 'placa': placa, 'fecha_hora_entrada': momento}


def registrar_salida(placa, ruta=None, momento=None):
    placa = normalizar_placa(placa)
    momento = momento or ahora()
    with conectar(ruta) as bd:
        bd.execute('BEGIN IMMEDIATE')
        movimiento = bd.execute('SELECT * FROM movimiento WHERE placa=? AND fecha_hora_salida IS NULL', (placa,)).fetchone()
        if not movimiento:
            raise ErrorNegocio('No existe una entrada activa para esa placa.')
        if momento <= movimiento['fecha_hora_entrada']:
            raise ErrorNegocio('La salida debe ser posterior a la entrada.')
        try:
            bd.execute('UPDATE movimiento SET fecha_hora_salida=? WHERE id_movimiento=? AND fecha_hora_salida IS NULL',
                       (momento, movimiento['id_movimiento']))
        except sqlite3.IntegrityError as exc:
            raise ErrorNegocio('No se pudo registrar la salida: ' + str(exc)) from exc
        bd.commit()
        return {'id_movimiento': movimiento['id_movimiento'], 'placa': placa, 'fecha_hora_salida': momento}


def registrar_novedad(placa, tipo, descripcion, ruta=None, momento=None):
    placa = normalizar_placa(placa)
    tipo = (tipo or '').strip()
    descripcion = (descripcion or '').strip()
    if tipo not in TIPOS_NOVEDAD:
        raise ErrorNegocio('Selecciona un tipo de novedad válido.')
    if len(descripcion) < 5 or len(descripcion) > 500:
        raise ErrorNegocio('La descripción debe tener entre 5 y 500 caracteres.')
    momento = momento or ahora()
    with conectar(ruta) as bd:
        bd.execute('BEGIN IMMEDIATE')
        activo = bd.execute('SELECT id_movimiento FROM movimiento WHERE placa=? AND fecha_hora_salida IS NULL', (placa,)).fetchone()
        if not activo:
            raise ErrorNegocio('La placa no tiene una entrada activa; no puede registrarse la novedad.')
        registro = bd.execute('''INSERT INTO novedad (id_movimiento, tipo, descripcion, fecha_hora_registro)
            VALUES (?, ?, ?, ?)''', (activo['id_movimiento'], tipo, descripcion, momento))
        bd.commit()
        return {'id_novedad': registro.lastrowid, 'placa': placa}


def resumen(ruta=None):
    with conectar(ruta) as bd:
        datos = cupos(bd)
        datos['carros'] = bd.execute('''SELECT COUNT(*) FROM movimiento m JOIN vehiculo v ON m.placa=v.placa
          WHERE m.fecha_hora_salida IS NULL AND v.tipo='CARRO' ''').fetchone()[0]
        datos['motos'] = bd.execute('''SELECT COUNT(*) FROM movimiento m JOIN vehiculo v ON m.placa=v.placa
          WHERE m.fecha_hora_salida IS NULL AND v.tipo='MOTO' ''').fetchone()[0]
        datos['vehiculos'] = [dict(x) for x in bd.execute('''SELECT m.placa, v.tipo, m.fecha_hora_entrada,
          m.id_movimiento FROM movimiento m JOIN vehiculo v ON m.placa=v.placa
          WHERE m.fecha_hora_salida IS NULL ORDER BY m.fecha_hora_entrada DESC LIMIT 10''').fetchall()]
    return datos


def historial(placa='', desde='', hasta='', ruta=None):
    condiciones = []
    params = []
    if placa and placa.strip():
        condiciones.append('m.placa=?')
        params.append(normalizar_placa(placa))
    for texto, valor in (('desde', desde), ('hasta', hasta)):
        if valor:
            try:
                datetime.strptime(valor, '%Y-%m-%d')
            except ValueError as exc:
                raise ErrorNegocio('La fecha "' + texto + '" no es válida.') from exc
            condiciones.append('date(m.fecha_hora_entrada) ' + ('>=' if texto == 'desde' else '<=') + ' ?')
            params.append(valor)
    if desde and hasta and desde > hasta:
        raise ErrorNegocio('La fecha inicial debe ser anterior o igual a la final.')
    where = ('WHERE ' + ' AND '.join(condiciones)) if condiciones else ''
    with conectar(ruta) as bd:
        return [dict(x) for x in bd.execute('''SELECT m.id_movimiento, m.placa, v.tipo,
          m.fecha_hora_entrada, m.fecha_hora_salida FROM movimiento m
          JOIN vehiculo v ON v.placa=m.placa ''' + where + '''
          ORDER BY m.fecha_hora_entrada DESC LIMIT 150''', params).fetchall()]


def novedades_recientes(ruta=None):
    with conectar(ruta) as bd:
        return [dict(x) for x in bd.execute('''SELECT n.*, m.placa, v.tipo AS tipo_vehiculo
          FROM novedad n JOIN movimiento m ON m.id_movimiento=n.id_movimiento
          JOIN vehiculo v ON v.placa=m.placa
          ORDER BY n.id_novedad DESC LIMIT 12''').fetchall()]
