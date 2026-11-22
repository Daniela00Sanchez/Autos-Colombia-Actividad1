import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    from app import crear_app
except ModuleNotFoundError as exc:
    if exc.name != 'flask': raise
    crear_app = None
from bd import conectar, inicializar
from servicios import ErrorNegocio, registrar_entrada, registrar_salida, resumen
from servicios_i2 import (crear_administrador_inicial, crear_operador, autenticar, abrir_sesion,
   validar_sesion, cambiar_operador, crear_vehiculo, corregir_vehiculo, crear_celda,
   editar_celda, listar_celdas, disponibles, ver_auditoria, operadores_conectados,
   anular_movimiento, eliminar_celda, eliminar_operador, eliminar_vehiculo)

class PruebasIteracion2(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/'autos.sqlite'
        inicializar(self.db)
        crear_administrador_inicial('admin01','Administrador principal','ClavePrincipal2026!',self.db)
        with conectar(self.db) as bd:
            self.admin=bd.execute("SELECT id FROM usuario WHERE usuario='admin01'").fetchone()['id']
        self.op1=crear_operador('Operador Uno','operador01','ClaveOperador2026!',self.admin,self.db)
        self.app=crear_app(self.db,pruebas=True) if crear_app else None

    def tearDown(self): self.tmp.cleanup()

    def web_login(self,usuario,clave):
        if self.app is None:
            self.skipTest('La interfaz web requiere Flask instalado.')
        web=self.app.test_client()
        web.get('/login')
        with web.session_transaction() as ses: csrf=ses['_csrf']
        response=web.post('/login',data={'usuario':usuario,'clave':clave,'_csrf':csrf},follow_redirects=False)
        return web,response

    def csrf(self,web):
        with web.session_transaction() as ses: return ses['_csrf']

    def test_cuentas_no_exponen_claves_y_roles(self):
        with conectar(self.db) as bd:
            f=bd.execute("SELECT clave_hash FROM usuario WHERE usuario='admin01'").fetchone()
        self.assertNotIn('ClavePrincipal2026!',f['clave_hash'])
        self.assertEqual(autenticar('admin01','ClavePrincipal2026!',self.db)['rol'],'administrador')
        self.assertIsNone(autenticar('admin01','mal',self.db))

    def test_no_se_crea_otro_admin_por_terminal(self):
        with self.assertRaises(ErrorNegocio):
            crear_administrador_inicial('nuevo','Nuevo Admin','ClaveValida2026!',self.db)

    def test_operador_no_puede_administrar(self):
        web,res=self.web_login('operador01','ClaveOperador2026!')
        self.assertEqual(res.status_code,302)
        for ruta in ('/usuarios','/auditoria','/novedades','/vehiculos/MNV345/corregir'):
            self.assertEqual(web.get(ruta).status_code,403,ruta)
        self.assertEqual(web.get('/celdas').status_code,200)
        self.assertEqual(web.post('/celdas/nueva',data={'codigo':'C-99','_csrf':self.csrf(web)}).status_code,403)
        self.assertEqual(web.post('/usuarios/nuevo',data={'nombre':'Alguien','usuario':'xoxo','clave':'ClaveLarga2026!','_csrf':self.csrf(web)}).status_code,403)

    def test_dos_operadores_simultaneos(self):
        op2=crear_operador('Operador Dos','operador02','ClaveOperadorDos2026!',self.admin,self.db)
        uno,r1=self.web_login('operador01','ClaveOperador2026!')
        dos,r2=self.web_login('operador02','ClaveOperadorDos2026!')
        self.assertEqual(r1.status_code,302)
        self.assertEqual(r2.status_code,302)
        self.assertEqual(len(operadores_conectados(self.db)),2)
        self.assertEqual(uno.get('/').status_code,200)
        self.assertEqual(dos.get('/').status_code,200)
        uno.post('/salir',data={'_csrf':self.csrf(uno)})
        self.assertEqual(len(operadores_conectados(self.db)),1)
        self.assertEqual(dos.get('/').status_code,200)

    def test_crear_placa_y_correccion_registradas(self):
        web,res=self.web_login('operador01','ClaveOperador2026!')
        respuesta=web.post('/vehiculos/nuevo',data={'placa':'abc123','tipo':'CARRO','autorizado':'1',
                  'vigencia':'2030-12-31','_csrf':self.csrf(web)})
        self.assertEqual(respuesta.status_code,302)
        with self.assertRaises(ErrorNegocio):
            crear_vehiculo('ABC123','CARRO',True,'2030-12-31',self.op1,self.db)
        corregir_vehiculo('ABC123','ABC124','MOTO',1,'2030-12-31',self.admin,self.db)
        with conectar(self.db) as bd:
            self.assertTrue(bd.execute("SELECT 1 FROM vehiculo WHERE placa='ABC124'").fetchone())
        acciones=[x['accion'] for x in ver_auditoria(self.db) if x['entidad']=='vehiculo']
        self.assertIn('CREAR',acciones)
        self.assertIn('CORREGIR',acciones)

    def test_celda_ocupada_no_se_desactiva(self):
        c=next(x for x in listar_celdas(self.db) if x['placa'])
        with self.assertRaises(ErrorNegocio):
            editar_celda(c['id'],c['codigo'],False,self.admin,self.db)
        c=disponibles(self.db)[0]
        editar_celda(c['id'],c['codigo'],False,self.admin,self.db)
        self.assertNotIn(c['id'],[x['id'] for x in disponibles(self.db)])

    def test_dos_operadores_no_ocupan_misma_celda(self):
        op2=crear_operador('Operador Dos','operador02','ClaveOperadorDos2026!',self.admin,self.db)
        crear_vehiculo('HJK123','CARRO',True,'2030-12-31',self.op1,self.db)
        crear_vehiculo('HJK124','CARRO',True,'2030-12-31',op2,self.db)
        c=disponibles(self.db)[0]['id']
        def intento(placa,usuario):
            try:
                registrar_entrada(placa,self.db,'2026-11-15 12:00:00',celda_id=c,usuario_id=usuario)
                return 'guardado'
            except ErrorNegocio:
                return 'rechazado'
        with ThreadPoolExecutor(max_workers=2) as ex:
            resultados=list(ex.map(lambda p:intento(*p),[('HJK123',self.op1),('HJK124',op2)]))
        self.assertCountEqual(resultados,['guardado','rechazado'])
        with conectar(self.db) as bd:
            ocupados=bd.execute('SELECT COUNT(*) FROM movimiento WHERE celda_id=? AND fecha_hora_salida IS NULL',(c,)).fetchone()[0]
        self.assertEqual(ocupados,1)

    def test_entrada_y_salida_con_responsables(self):
        crear_vehiculo('JJK234','CARRO',1,'2030-12-31',self.op1,self.db)
        c=disponibles(self.db)[0]['id']
        registrar_entrada('JJK234',self.db,'2026-11-15 10:00:00',celda_id=c,usuario_id=self.op1)
        registrar_salida('JJK234',self.db,'2026-11-15 10:45:00',usuario_id=self.admin)
        with conectar(self.db) as bd:
            f=bd.execute("SELECT entrada_usuario_id,salida_usuario_id FROM movimiento WHERE placa='JJK234'").fetchone()
        self.assertEqual((f['entrada_usuario_id'],f['salida_usuario_id']),(self.op1,self.admin))
        self.assertIn(c,[x['id'] for x in disponibles(self.db)])

    def test_desactivar_operador_cierra_sesion(self):
        token=abrir_sesion(self.op1,self.db)
        self.assertIsNotNone(validar_sesion(token,self.db))
        cambiar_operador(self.op1,'Operador Uno','',False,self.admin,self.db)
        self.assertIsNone(validar_sesion(token,self.db))
        self.assertIsNone(autenticar('operador01','ClaveOperador2026!',self.db))

    def test_admin_anula_sin_borrar_historia(self):
        anular_movimiento(1,self.admin,self.db)
        with conectar(self.db) as bd:
            f=bd.execute('SELECT anulado,fecha_hora_salida FROM movimiento WHERE id_movimiento=1').fetchone()
        self.assertEqual(f['anulado'],1)
        self.assertIsNotNone(f['fecha_hora_salida'])
        self.assertTrue(any(x['accion']=='ANULAR' for x in ver_auditoria(self.db)))

    def test_solo_admin_puede_cambiar_celda(self):
        with self.assertRaises(ErrorNegocio):
            crear_celda('C-99',self.op1,self.db)
        c=disponibles(self.db)[0]
        with self.assertRaises(ErrorNegocio):
            editar_celda(c['id'],c['codigo'],False,self.op1,self.db)
        with self.assertRaises(ErrorNegocio):
            eliminar_operador(self.op1,self.op1,self.db)

    def test_eliminar_solo_celdas_y_vehiculos_sin_historial(self):
        crear_celda('C-99',self.admin,self.db)
        libre=next(c for c in listar_celdas(self.db) if c['codigo']=='C-99')
        eliminar_celda(libre['id'],self.admin,self.db)
        self.assertFalse(any(c['codigo']=='C-99' for c in listar_celdas(self.db)))
        with self.assertRaises(ErrorNegocio):
            eliminar_celda(1,self.admin,self.db)
        crear_vehiculo('QWER99','CARRO',True,'2030-12-31',self.op1,self.db)
        eliminar_vehiculo('QWER99',self.admin,self.db)
        with self.assertRaises(ErrorNegocio):
            eliminar_vehiculo('TQR73F',self.admin,self.db)

    def test_csrf_protege_formularios(self):
        web,r=self.web_login('admin01','ClavePrincipal2026!')
        self.assertEqual(web.post('/usuarios/nuevo',data={'usuario':'otro'}).status_code,400)

    def test_estructura_reinicio_conserva_cambios(self):
        crear_celda('C-99',self.admin,self.db)
        antes=len(listar_celdas(self.db))
        inicializar(self.db)
        self.assertEqual(len(listar_celdas(self.db)),antes)
        self.assertEqual(resumen(self.db)['dentro'],13)

if __name__=='__main__': unittest.main()
