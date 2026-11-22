"""Usuarios, celdas y control de cambios de Autos Colombia."""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from bd import conectar
from servicios import ErrorNegocio, ahora, normalizar_placa, dict_fila

DURACION_SESION = timedelta(hours=8)

def generate_password_hash(clave):
    """Hash scrypt con sal aleatoria; no guarda la contraseña en texto claro."""
    salt=secrets.token_bytes(16)
    derivada=hashlib.scrypt(clave.encode('utf8'),salt=salt,n=2**14,r=8,p=1,dklen=32)
    return f'scrypt:16384:8:1${salt.hex()}${derivada.hex()}'

def check_password_hash(guardado,clave):
    try:
        parametros,sal,esperado=guardado.split('$')
        marca,n,r,p=parametros.split(':')
        if marca!='scrypt' or (int(n),int(r),int(p))!=(16384,8,1):
            return False
        derivada=hashlib.scrypt((clave or '').encode('utf8'),salt=bytes.fromhex(sal),
                                n=int(n),r=int(r),p=int(p),dklen=32)
        return hmac.compare_digest(derivada,bytes.fromhex(esperado))
    except (ValueError,TypeError,AttributeError):
        return False


def verificar_clave(clave):
    if not 10 <= len(clave or '') <= 128:
        raise ErrorNegocio('La contraseña debe tener entre 10 y 128 caracteres.')

def nombre_usuario(valor):
    val = (valor or '').strip().lower()
    if not re.fullmatch(r'[a-z0-9_.-]{3,30}', val):
        raise ErrorNegocio('El usuario debe tener entre 3 y 30 caracteres: letras, números, punto o guion.')
    return val

def auditar(bd, actor_id, accion, entidad, referencia, antes=None, despues=None):
    def serializar(obj):
        return json.dumps(obj, ensure_ascii=False, default=str, sort_keys=True) if obj is not None else None
    bd.execute('''INSERT INTO auditoria(usuario_id,accion,entidad,referencia,antes,despues,fecha_hora)
        VALUES(?,?,?,?,?,?,?)''', (actor_id, accion, entidad, str(referencia), serializar(antes), serializar(despues), ahora()))

def exigir_admin(bd, actor_id):
    autorizado=bd.execute('''SELECT 1 FROM usuario WHERE id=? AND rol='administrador' AND activo=1''',(actor_id,)).fetchone()
    if not autorizado:
        raise ErrorNegocio('Solo el administrador puede realizar esta operación.')


def crear_administrador_inicial(usuario, nombre, clave, ruta=None):
    usuario = nombre_usuario(usuario)
    nombre = (nombre or '').strip()
    verificar_clave(clave)
    if len(nombre) < 3 or len(nombre)>100:
        raise ErrorNegocio('Ingresa el nombre completo.')
    with conectar(ruta) as bd:
        bd.execute('BEGIN IMMEDIATE')
        if bd.execute("SELECT 1 FROM usuario WHERE rol='administrador'").fetchone():
            raise ErrorNegocio('Ya existe el administrador principal. No se creará otro desde la terminal.')
        bd.execute('INSERT INTO usuario(usuario,nombre,clave_hash,rol,creado_en) VALUES (?,?,?,?,?)',
                (usuario,nombre,generate_password_hash(clave),'administrador',ahora()))

def listar_usuarios(ruta=None):
    with conectar(ruta) as bd:
        return [dict(x) for x in bd.execute('''SELECT id, usuario, nombre, rol, activo, creado_en
           FROM usuario ORDER BY rol, nombre''')]

def crear_operador(nombre, usuario, clave, actor_id, ruta=None):
    nombre=(nombre or '').strip()
    usuario=nombre_usuario(usuario)
    verificar_clave(clave)
    if not 3 <= len(nombre) <= 100:
        raise ErrorNegocio('Escribe el nombre completo del operador.')
    with conectar(ruta) as bd:
        bd.execute('BEGIN IMMEDIATE')
        exigir_admin(bd,actor_id)
        try:
            cur=bd.execute('''INSERT INTO usuario(usuario,nombre,clave_hash,rol,creado_en)
                VALUES (?,?,?,'operador',?)''',(usuario,nombre,generate_password_hash(clave),ahora()))
        except sqlite3.IntegrityError as ex:
            raise ErrorNegocio('Ese nombre de usuario ya está registrado.') from ex
        auditar(bd,actor_id,'CREAR','usuario',cur.lastrowid,despues={'usuario':usuario,'nombre':nombre,'rol':'operador'})
        return cur.lastrowid

def cambiar_operador(id_,nombre,clave,activo,actor_id,ruta=None):
    nombre=(nombre or '').strip()
    if not 3 <= len(nombre) <=100:
        raise ErrorNegocio('Escribe un nombre válido.')
    if clave:
        verificar_clave(clave)
    with conectar(ruta) as bd:
        bd.execute('BEGIN IMMEDIATE')
        exigir_admin(bd,actor_id)
        old=dict_fila(bd.execute('SELECT id,usuario,nombre,rol,activo FROM usuario WHERE id=?',(id_,)).fetchone())
        if not old or old['rol']!='operador':
            raise ErrorNegocio('Solo se pueden editar las cuentas de operadores.')
        if clave:
            bd.execute('UPDATE usuario SET nombre=?,activo=?,clave_hash=? WHERE id=?',
                       (nombre, int(bool(activo)),generate_password_hash(clave),id_))
        else:
            bd.execute('UPDATE usuario SET nombre=?,activo=? WHERE id=?', (nombre,int(bool(activo)),id_))
        if not activo:
            bd.execute('UPDATE sesion_activa SET cerrada=1 WHERE usuario_id=?',(id_,))
        auditar(bd,actor_id,'MODIFICAR','usuario',id_,antes=old,
                despues={'usuario':old['usuario'],'nombre':nombre,'activo':int(bool(activo)),'clave_actualizada':bool(clave)})

def autenticar(usuario,clave,ruta=None):
    usuario=(usuario or '').strip()
    with conectar(ruta) as bd:
        fila=bd.execute('SELECT * FROM usuario WHERE usuario=? COLLATE NOCASE AND activo=1',(usuario,)).fetchone()
    if fila and check_password_hash(fila['clave_hash'],clave or ''):
        return dict(fila)
    return None

def _hash_token(token):
    return hashlib.sha256(token.encode('utf8')).hexdigest()

def abrir_sesion(usuario_id, ruta=None):
    token=secrets.token_urlsafe(32)
    fecha=ahora()
    final=(datetime.strptime(fecha,'%Y-%m-%d %H:%M:%S')+DURACION_SESION).strftime('%Y-%m-%d %H:%M:%S')
    with conectar(ruta) as bd:
        bd.execute('''INSERT INTO sesion_activa(token_hash,usuario_id,inicio,ultimo_uso,vencimiento)
            VALUES (?,?,?,?,?)''',(_hash_token(token),usuario_id,fecha,fecha,final))
    return token

def validar_sesion(token,ruta=None):
    if not token or len(token)>128:
        return None
    with conectar(ruta) as bd:
        fila=bd.execute('''SELECT u.id,u.usuario,u.nombre,u.rol FROM sesion_activa s JOIN usuario u
            ON s.usuario_id=u.id WHERE s.token_hash=? AND s.cerrada=0
            AND s.vencimiento>=? AND u.activo=1''',(_hash_token(token),ahora())).fetchone()
        if fila:
            bd.execute('UPDATE sesion_activa SET ultimo_uso=? WHERE token_hash=?',(ahora(),_hash_token(token)))
            return dict(fila)
    return None

def cerrar_sesion(token,ruta=None):
    if token:
        with conectar(ruta) as bd:
            bd.execute('UPDATE sesion_activa SET cerrada=1 WHERE token_hash=?',(_hash_token(token),))

def operadores_conectados(ruta=None):
    with conectar(ruta) as bd:
        return [dict(x) for x in bd.execute('''SELECT u.usuario,u.nombre,MAX(s.ultimo_uso) AS ultimo_uso
          FROM sesion_activa s JOIN usuario u ON u.id=s.usuario_id
          WHERE u.rol='operador' AND u.activo=1 AND s.cerrada=0 AND s.vencimiento>=?
          GROUP BY u.id ORDER BY u.usuario''',(ahora(),))]

def listar_celdas(ruta=None):
    with conectar(ruta) as bd:
        return [dict(x) for x in bd.execute('''SELECT c.id,c.codigo,c.activa,m.placa,
            m.fecha_hora_entrada AS entrada
            FROM celda c LEFT JOIN movimiento m ON m.celda_id=c.id AND m.fecha_hora_salida IS NULL
            ORDER BY c.codigo''')]

def disponibles(ruta=None):
    return [x for x in listar_celdas(ruta) if x['activa'] and x['placa'] is None]

def resumen_celdas(ruta=None):
    celdas=listar_celdas(ruta)
    return {'total':sum(bool(c['activa']) for c in celdas),
            'ocupadas':sum(c['placa'] is not None for c in celdas),
            'libres':sum(c['activa'] and c['placa'] is None for c in celdas),
            'inactivas':sum(not c['activa'] for c in celdas)}

def _codigo_celda(codigo):
    codigo=(codigo or '').strip().upper()
    if not re.fullmatch(r'[A-Z0-9-]{2,12}',codigo):
        raise ErrorNegocio('El código de celda debe tener entre 2 y 12 letras, números o guiones.')
    return codigo

def _sincronizar_capacidad(bd):
    numero=bd.execute('SELECT COUNT(*) FROM celda WHERE activa=1').fetchone()[0]
    # Un parqueadero con todos los espacios cerrados no admite entradas nuevas.
    if numero:
        bd.execute('UPDATE configuracion SET capacidad_total=? WHERE id=1',(numero,))

def crear_celda(codigo,actor_id,ruta=None):
    codigo=_codigo_celda(codigo)
    with conectar(ruta) as bd:
        bd.execute('BEGIN IMMEDIATE')
        exigir_admin(bd,actor_id)
        try:
            cur=bd.execute('INSERT INTO celda(codigo,activa) VALUES (?,1)',(codigo,))
        except sqlite3.IntegrityError as exc:
            raise ErrorNegocio('Esa celda ya está registrada.') from exc
        _sincronizar_capacidad(bd)
        auditar(bd,actor_id,'CREAR','celda',cur.lastrowid,despues={'codigo':codigo,'activa':1})

def editar_celda(id_,codigo,activa,actor_id,ruta=None):
    codigo=_codigo_celda(codigo)
    with conectar(ruta) as bd:
        bd.execute('BEGIN IMMEDIATE')
        exigir_admin(bd,actor_id)
        old=dict_fila(bd.execute('SELECT * FROM celda WHERE id=?',(id_,)).fetchone())
        if not old:
            raise ErrorNegocio('No existe esa celda.')
        ocupada=bd.execute('SELECT 1 FROM movimiento WHERE celda_id=? AND fecha_hora_salida IS NULL',(id_,)).fetchone()
        if ocupada and (not activa or codigo != old['codigo']):
            raise ErrorNegocio('La celda está ocupada. No puede modificarse ni desactivarse.')
        if not activa and bd.execute('SELECT COUNT(*) FROM celda WHERE activa=1').fetchone()[0] <= 1:
            raise ErrorNegocio('Debe permanecer al menos una celda activa.')
        try:
            bd.execute('UPDATE celda SET codigo=?,activa=? WHERE id=?',(codigo,int(bool(activa)),id_))
        except sqlite3.IntegrityError as exc:
            raise ErrorNegocio('Ese código ya existe.') from exc
        _sincronizar_capacidad(bd)
        auditar(bd,actor_id,'MODIFICAR','celda',id_,antes=old,despues={'codigo':codigo,'activa':int(bool(activa))})

def crear_vehiculo(placa,tipo,autorizado,vigencia,actor_id,ruta=None):
    placa=normalizar_placa(placa)
    tipo=(tipo or '').upper()
    if tipo not in ('CARRO','MOTO'):
        raise ErrorNegocio('Selecciona carro o moto.')
    try:
        datetime.strptime(vigencia or '', '%Y-%m-%d')
    except ValueError as exc:
        raise ErrorNegocio('Selecciona una fecha de vigencia válida.') from exc
    with conectar(ruta) as bd:
        bd.execute('BEGIN IMMEDIATE')
        try:
            bd.execute('INSERT INTO vehiculo(placa,tipo,autorizado,vigencia_hasta,creado_por_id) VALUES (?,?,?,?,?)',
                       (placa,tipo,int(bool(autorizado)),vigencia,actor_id))
        except sqlite3.IntegrityError as exc:
            raise ErrorNegocio('Esta placa ya existe. Solicita al administrador su corrección.') from exc
        auditar(bd,actor_id,'CREAR','vehiculo',placa,despues={'placa':placa,'tipo':tipo,'autorizado':bool(autorizado),'vigencia_hasta':vigencia})

def corregir_vehiculo(placa_original,placa_nueva,tipo,autorizado,vigencia,actor_id,ruta=None):
    anterior=normalizar_placa(placa_original)
    nueva=normalizar_placa(placa_nueva)
    if tipo not in ('CARRO','MOTO'):
        raise ErrorNegocio('Selecciona un tipo de vehículo válido.')
    try: datetime.strptime(vigencia or '', '%Y-%m-%d')
    except ValueError as exc: raise ErrorNegocio('Selecciona una fecha válida.') from exc
    with conectar(ruta) as bd:
        bd.execute('BEGIN IMMEDIATE')
        exigir_admin(bd,actor_id)
        old=dict_fila(bd.execute('SELECT placa,tipo,autorizado,vigencia_hasta FROM vehiculo WHERE placa=?',(anterior,)).fetchone())
        if not old:
            raise ErrorNegocio('No se encontró el vehículo.')
        try:
            bd.execute('UPDATE vehiculo SET placa=?,tipo=?,autorizado=?,vigencia_hasta=? WHERE placa=?',
                       (nueva,tipo,int(bool(autorizado)),vigencia,anterior))
        except sqlite3.IntegrityError as exc:
            raise ErrorNegocio('No es posible cambiar la placa: ya existe o hay un conflicto.') from exc
        auditar(bd,actor_id,'CORREGIR','vehiculo',anterior,antes=old,
                despues={'placa':nueva,'tipo':tipo,'autorizado':bool(autorizado),'vigencia_hasta':vigencia})

def ver_auditoria(ruta=None):
    with conectar(ruta) as bd:
        return [dict(x) for x in bd.execute('''SELECT a.id,a.accion,a.entidad,a.referencia,
          a.antes,a.despues,a.fecha_hora,COALESCE(u.usuario,'Datos iniciales') AS responsable
          FROM auditoria a LEFT JOIN usuario u ON u.id=a.usuario_id
          ORDER BY a.id DESC LIMIT 250''')]

def anular_movimiento(id_,actor_id,ruta=None):
    with conectar(ruta) as bd:
        bd.execute('BEGIN IMMEDIATE')
        exigir_admin(bd,actor_id)
        f=dict_fila(bd.execute('SELECT * FROM movimiento WHERE id_movimiento=?',(id_,)).fetchone())
        if not f or f['anulado']:
            raise ErrorNegocio('Ese registro no está disponible para anular.')
        # Se conserva el movimiento anulado para mantener historial; cierra estancia si está abierta.
        cierre=ahora()
        if f['fecha_hora_salida'] is None:
            if cierre<=f['fecha_hora_entrada']:
                raise ErrorNegocio('La fecha actual debe ser posterior a la entrada.')
            bd.execute('UPDATE movimiento SET anulado=1,fecha_hora_salida=?,salida_usuario_id=? WHERE id_movimiento=?',
                       (cierre,actor_id,id_))
        else:
            bd.execute('UPDATE movimiento SET anulado=1 WHERE id_movimiento=?',(id_,))
        auditar(bd,actor_id,'ANULAR','movimiento',id_,antes=f,despues={'anulado':True})

def eliminar_celda(id_,actor_id,ruta=None):
    """Elimina celdas sin historial; las utilizadas se deben desactivar."""
    with conectar(ruta) as bd:
        bd.execute('BEGIN IMMEDIATE')
        exigir_admin(bd,actor_id)
        vieja=dict_fila(bd.execute('SELECT * FROM celda WHERE id=?',(id_,)).fetchone())
        if not vieja:
            raise ErrorNegocio('No se encontró la celda.')
        if bd.execute('SELECT 1 FROM movimiento WHERE celda_id=?',(id_,)).fetchone():
            raise ErrorNegocio('La celda tiene historial de movimientos. Desactívala en lugar de eliminarla.')
        if vieja['activa'] and bd.execute('SELECT COUNT(*) FROM celda WHERE activa=1').fetchone()[0]<=1:
            raise ErrorNegocio('Debe quedar por lo menos una celda activa.')
        bd.execute('DELETE FROM celda WHERE id=?',(id_,))
        _sincronizar_capacidad(bd)
        auditar(bd,actor_id,'ELIMINAR','celda',id_,antes=vieja)


def eliminar_operador(id_,actor_id,ruta=None):
    """Retira el acceso de la cuenta, conservando el historial de auditoría."""
    with conectar(ruta) as bd:
        bd.execute('BEGIN IMMEDIATE')
        exigir_admin(bd,actor_id)
        antigua=dict_fila(bd.execute('''SELECT id,usuario,nombre,rol,activo
             FROM usuario WHERE id=?''',(id_,)).fetchone())
        if not antigua or antigua['rol']!='operador':
            raise ErrorNegocio('Solamente se pueden retirar cuentas de operadores.')
        if not antigua['activo']:
            raise ErrorNegocio('La cuenta ya está desactivada.')
        bd.execute('UPDATE usuario SET activo=0 WHERE id=?',(id_,))
        bd.execute('UPDATE sesion_activa SET cerrada=1 WHERE usuario_id=?',(id_,))
        auditar(bd,actor_id,'ELIMINAR_ACCESO','usuario',id_,antes=antigua,
                despues={'usuario':antigua['usuario'],'activo':False})


def eliminar_vehiculo(placa,actor_id,ruta=None):
    """Permite borrar una placa solo si no tiene movimientos relacionados."""
    placa=normalizar_placa(placa)
    with conectar(ruta) as bd:
        bd.execute('BEGIN IMMEDIATE')
        exigir_admin(bd,actor_id)
        vieja=dict_fila(bd.execute('SELECT placa,tipo,autorizado,vigencia_hasta FROM vehiculo WHERE placa=?',(placa,)).fetchone())
        if not vieja:
            raise ErrorNegocio('No existe ese vehículo.')
        if bd.execute('SELECT 1 FROM movimiento WHERE placa=?',(placa,)).fetchone():
            raise ErrorNegocio('Este vehículo tiene movimientos. No se puede borrar su historial.')
        bd.execute('DELETE FROM vehiculo WHERE placa=?',(placa,))
        auditar(bd,actor_id,'ELIMINAR','vehiculo',placa,antes=vieja)
