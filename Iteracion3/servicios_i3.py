"""Registro de pagos y vigencias de mensualidad de Autos Colombia."""
import calendar
import secrets
import sqlite3
from datetime import datetime, date, timedelta
from bd import conectar
from servicios import ErrorNegocio, ahora, normalizar_placa
from servicios_i2 import auditar

MEDIOS_PAGO = ('EFECTIVO', 'TRANSFERENCIA', 'OTRO')


def fecha_iso(valor):
    try:
        fecha = date.fromisoformat(str(valor))
        if fecha.isoformat() != str(valor):
            raise ValueError()
        return fecha
    except (ValueError, TypeError):
        raise ErrorNegocio('La fecha de inicio debe ser válida (AAAA-MM-DD).')


def inicio_mes_siguiente(actual, ancla):
    """Vuelve al día pactado sin desplazarlo por meses cortos."""
    mes = actual.month + 1
    ano = actual.year
    if mes == 13:
        mes, ano = 1, ano + 1
    return date(ano, mes, min(ancla, calendar.monthrange(ano, mes)[1]))


def _datos_siguiente(bd, placa, primera_fecha=None):
    veh = bd.execute('SELECT * FROM vehiculo WHERE placa=?', (placa,)).fetchone()
    if not veh:
        raise ErrorNegocio('La placa no está registrada.')
    ultimo = bd.execute('''SELECT * FROM pago_mensualidad
        WHERE placa=? AND estado='REGISTRADO' ORDER BY id DESC LIMIT 1''', (placa,)).fetchone()
    if ultimo:
        ancla = ultimo['dia_ancla']
        inicio = inicio_mes_siguiente(fecha_iso(ultimo['inicio_periodo']), ancla)
    elif veh['vigencia_hasta'] > '1900-01-01':
        inicio = fecha_iso(veh['vigencia_hasta']) + timedelta(days=1)
        ancla = inicio.day
    else:
        if not primera_fecha:
            return None
        inicio = fecha_iso(primera_fecha)
        ancla = inicio.day
    fin = inicio_mes_siguiente(inicio, ancla) - timedelta(days=1)
    return {'placa': placa, 'inicio': inicio.isoformat(), 'fin': fin.isoformat(),
            'dia_ancla': ancla, 'es_primero': (ultimo is None and veh['vigencia_hasta'] == '1900-01-01')}


def previsualizar_periodo(placa, ruta=None, primera_fecha=None):
    placa = normalizar_placa(placa)
    with conectar(ruta) as bd:
        return _datos_siguiente(bd, placa, primera_fecha)


def registrar_pago(placa, importe, medio, actor_id, ruta=None, primera_fecha=None,
                   referencia='', momento=None, token_operacion=None):
    placa = normalizar_placa(placa)
    try:
        importe = int(str(importe).strip())
    except (TypeError, ValueError) as exc:
        raise ErrorNegocio('Escribe el valor del pago en pesos, sin decimales.') from exc
    if importe <= 0 or importe > 50000000:
        raise ErrorNegocio('El importe debe ser mayor que cero y no superar $50.000.000.')
    medio = (medio or '').strip().upper()
    if medio not in MEDIOS_PAGO:
        raise ErrorNegocio('Selecciona un medio de pago válido.')
    referencia = (referencia or '').strip()
    if len(referencia) > 80:
        raise ErrorNegocio('La referencia debe tener como máximo 80 caracteres.')
    momento = momento or ahora()
    token_operacion = token_operacion or secrets.token_urlsafe(24)
    if not 12 <= len(token_operacion) <= 90:
        raise ErrorNegocio('La referencia interna de la operación no es válida.')
    try:
        dia_pago = datetime.strptime(momento, '%Y-%m-%d %H:%M:%S').date()
    except ValueError as exc:
        raise ErrorNegocio('Fecha de registro no válida.') from exc
    with conectar(ruta) as bd:
        bd.execute('BEGIN IMMEDIATE')
        duplicado = bd.execute('SELECT id,placa,importe_pesos FROM pago_mensualidad WHERE token_operacion=?', (token_operacion,)).fetchone()
        if duplicado:
            if duplicado['placa'] == placa and duplicado['importe_pesos'] == importe:
                return duplicado['id']
            raise ErrorNegocio('Se reutilizó una referencia de operación distinta.')
        actor = bd.execute('SELECT activo,rol FROM usuario WHERE id=?', (actor_id,)).fetchone()
        if not actor or not actor['activo'] or actor['rol'] not in ('administrador','operador'):
            raise ErrorNegocio('No tienes permiso para registrar pagos.')
        veh = bd.execute('SELECT * FROM vehiculo WHERE placa=?', (placa,)).fetchone()
        if not veh:
            raise ErrorNegocio('El vehículo no existe; primero registra la placa.')
        periodo = _datos_siguiente(bd, placa, primera_fecha)
        if periodo is None:
            raise ErrorNegocio('Indica la fecha de inicio de la primera mensualidad.')
        # La mensualidad inicial debe tener una fecha convenida; las renovaciones
        # siempre usan el mismo calendario y no pueden alterarse en el formulario.
        if not periodo['es_primero'] and primera_fecha and primera_fecha != periodo['inicio']:
            raise ErrorNegocio('El inicio de la renovación es fijo y no se puede cambiar.')
        if periodo['fin'] < dia_pago.isoformat():
            raise ErrorNegocio('El período pendiente ya terminó; solicita revisar las mensualidades vencidas.')
        if periodo['es_primero'] and periodo['inicio'] < dia_pago.isoformat():
            raise ErrorNegocio('La primera mensualidad debe comenzar hoy o en una fecha posterior.')
        try:
            cur = bd.execute('''INSERT INTO pago_mensualidad
                (placa, importe_pesos, medio_pago, referencia_pago, token_operacion, fecha_pago,
                 inicio_periodo, fin_periodo, dia_ancla, vigencia_anterior,
                 habilitada_desde_anterior, registrado_por_id)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                 (placa,importe,medio,referencia,token_operacion,momento,periodo['inicio'],periodo['fin'],
                  periodo['dia_ancla'],veh['vigencia_hasta'],veh['habilitada_desde'],actor_id))
        except sqlite3.IntegrityError as exc:
            raise ErrorNegocio('Ya existe un pago para el período seleccionado.') from exc
        numero = f'AC-{cur.lastrowid:06d}'
        bd.execute('UPDATE pago_mensualidad SET numero_recibo=? WHERE id=?',(numero,cur.lastrowid))
        # Para renovaciones futuras, conserva el inicio original de una mensualidad
        # que aún no haya comenzado; para un vehículo nuevo, habilita desde el inicio pactado.
        if periodo['es_primero']:
            habilitada = periodo['inicio']
        else:
            habilitada = veh['habilitada_desde']
        bd.execute('UPDATE vehiculo SET vigencia_hasta=?, habilitada_desde=? WHERE placa=?',
                   (periodo['fin'],habilitada,placa))
        auditar(bd,actor_id,'REGISTRAR','pago',cur.lastrowid,
                despues={'recibo':numero,'placa':placa,'importe':importe,
                         'fecha_pago':momento,'inicio_periodo':periodo['inicio'],
                         'fin_periodo':periodo['fin']})
        return cur.lastrowid


def listar_pagos(placa=None, ruta=None, limite=150):
    filtros = ''
    parametros = []
    if placa:
        filtros = 'WHERE p.placa=?'
        parametros.append(normalizar_placa(placa))
    parametros.append(limite)
    with conectar(ruta) as bd:
        return [dict(x) for x in bd.execute(f'''SELECT p.*,u.usuario AS responsable
              FROM pago_mensualidad p JOIN usuario u ON u.id=p.registrado_por_id
              {filtros} ORDER BY p.id DESC LIMIT ?''', parametros)]


def obtener_pago(id_pago, ruta=None):
    with conectar(ruta) as bd:
        fila = bd.execute('''SELECT p.*,u.usuario AS responsable,u.nombre AS nombre_responsable
            FROM pago_mensualidad p JOIN usuario u ON u.id=p.registrado_por_id WHERE p.id=?''',
            (id_pago,)).fetchone()
        return dict(fila) if fila else None


def anular_pago(id_pago, motivo, actor_id, ruta=None, momento=None):
    motivo = (motivo or '').strip()
    if len(motivo)<8 or len(motivo)>250:
        raise ErrorNegocio('Indica el motivo de anulación (8 a 250 caracteres).')
    with conectar(ruta) as bd:
        bd.execute('BEGIN IMMEDIATE')
        actor=bd.execute('SELECT rol,activo FROM usuario WHERE id=?',(actor_id,)).fetchone()
        if not actor or not actor['activo'] or actor['rol']!='administrador':
            raise ErrorNegocio('Solo el administrador puede anular un pago.')
        pago=bd.execute('SELECT * FROM pago_mensualidad WHERE id=?',(id_pago,)).fetchone()
        if not pago or pago['estado']!='REGISTRADO':
            raise ErrorNegocio('El pago no existe o ya fue anulado.')
        posterior=bd.execute('''SELECT 1 FROM pago_mensualidad WHERE placa=?
            AND id>? AND estado='REGISTRADO' LIMIT 1''',(pago['placa'],id_pago)).fetchone()
        if posterior:
            raise ErrorNegocio('Primero deben revisarse los pagos posteriores de esta placa.')
        movimiento=bd.execute('''SELECT 1 FROM movimiento WHERE placa=? AND
            fecha_hora_entrada>=? AND fecha_hora_entrada<=? LIMIT 1''',
            (pago['placa'],pago['inicio_periodo']+' 00:00:00',pago['fin_periodo']+' 23:59:59')).fetchone()
        if movimiento:
            raise ErrorNegocio('Hay movimientos durante esa vigencia. La anulación requiere revisión administrativa.')
        bd.execute('''UPDATE pago_mensualidad SET estado='ANULADO',fecha_anulacion=?,
            anulado_por_id=?,motivo_anulacion=? WHERE id=?''', (momento or ahora(),actor_id,motivo,id_pago))
        bd.execute('UPDATE vehiculo SET vigencia_hasta=?, habilitada_desde=? WHERE placa=?',
                   (pago['vigencia_anterior'],pago['habilitada_desde_anterior'],pago['placa']))
        auditar(bd,actor_id,'ANULAR','pago',id_pago,
                antes={'recibo':pago['numero_recibo'],'estado':'REGISTRADO'},
                despues={'estado':'ANULADO','motivo':motivo})
