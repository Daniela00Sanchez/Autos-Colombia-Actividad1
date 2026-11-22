"""Pruebas del registro de mensualidades y los pagos anticipados."""
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bd import conectar, inicializar
from servicios import ErrorNegocio, consultar_placa, registrar_entrada
from servicios_i2 import crear_administrador_inicial, crear_operador, crear_vehiculo
from servicios_i3 import (registrar_pago, listar_pagos, obtener_pago,
                          previsualizar_periodo, anular_pago, inicio_mes_siguiente)

class PruebasPagos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'autos.sqlite'
        inicializar(self.db)
        crear_administrador_inicial('admin01','Admin Prueba','ClaveSegura2026!',self.db)
        with conectar(self.db) as bd:
            self.admin = bd.execute("SELECT id FROM usuario WHERE usuario='admin01'").fetchone()['id']
        self.op = crear_operador('Operador Uno','op01','ClaveSegura2026!',self.admin,self.db)
        crear_vehiculo('PRB902','CARRO',True,'1900-01-01',self.op,self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def pago(self, **kw):
        return registrar_pago('PRB902', 120000,'EFECTIVO',self.op,self.db,
                              primera_fecha=kw.pop('primera_fecha',None),
                              momento=kw.pop('momento','2026-11-22 15:10:00'), **kw)

    def test_pago_anticipado_fechas_diferentes(self):
        idp=self.pago(primera_fecha='2026-12-01')
        p=obtener_pago(idp,self.db)
        self.assertEqual((p['fecha_pago'][:10],p['inicio_periodo'],p['fin_periodo']),
                         ('2026-11-22','2026-12-01','2026-12-31'))
        self.assertEqual(p['responsable'],'op01')

    def test_vigencia_futura_no_autoriza_antes(self):
        self.pago(primera_fecha='2026-12-01')
        self.assertFalse(consultar_placa('PRB902',self.db,'2026-11-24 10:00:00')['puede_entrar'])
        self.assertTrue(consultar_placa('PRB902',self.db,'2026-12-01 10:00:00')['puede_entrar'])

    def test_no_hay_entrada_sin_pago(self):
        self.assertFalse(consultar_placa('PRB902',self.db,'2026-11-22 10:00:00')['puede_entrar'])
        with self.assertRaises(ErrorNegocio):
            registrar_entrada('PRB902',self.db,'2026-11-22 10:00:00',usuario_id=self.op)

    def test_no_permite_entrada_antes_del_inicio_pagado(self):
        self.pago(primera_fecha='2026-12-01')
        with self.assertRaises(ErrorNegocio):
            registrar_entrada('PRB902',self.db,'2026-11-28 10:00:00',usuario_id=self.op)

    def test_pago_temprano_no_mueve_siguiente_periodo(self):
        self.pago(primera_fecha='2026-12-01')
        segundo=self.pago(momento='2026-11-23 10:00:00')
        p=obtener_pago(segundo,self.db)
        self.assertEqual((p['inicio_periodo'],p['fin_periodo']),('2027-01-01','2027-01-31'))

    def test_no_permite_alterar_inicio_renovacion(self):
        self.pago(primera_fecha='2026-12-01')
        with self.assertRaises(ErrorNegocio):
            self.pago(primera_fecha='2026-12-23')

    def test_no_crear_pago_doble_por_reintento(self):
        p1=self.pago(primera_fecha='2026-12-01',token_operacion='opprueba123456789')
        p2=self.pago(primera_fecha='2026-12-01',token_operacion='opprueba123456789')
        self.assertEqual(p1,p2)
        self.assertEqual(len(listar_pagos('PRB902',self.db)),1)

    def test_ref_pago_unica_no_reutiliza_para_otra_placa(self):
        self.pago(primera_fecha='2026-12-01',token_operacion='operacion12345678')
        crear_vehiculo('PRB903','CARRO',True,'1900-01-01',self.op,self.db)
        with self.assertRaises(ErrorNegocio):
            registrar_pago('PRB903',120000,'EFECTIVO',self.op,self.db,
                           primera_fecha='2026-12-01',token_operacion='operacion12345678')

    def test_no_permite_importe_negativo(self):
        with self.assertRaises(ErrorNegocio):
            registrar_pago('PRB902',-100,'EFECTIVO',self.op,self.db,
                           primera_fecha='2026-12-01',momento='2026-11-22 09:00:00')

    def test_anulacion_exclusiva_administrador(self):
        p=self.pago(primera_fecha='2026-12-01')
        with self.assertRaises(ErrorNegocio):
            anular_pago(p,'Error de digitacion',self.op,self.db)
        anular_pago(p,'Error de digitacion',self.admin,self.db)
        self.assertEqual(obtener_pago(p,self.db)['estado'],'ANULADO')
        with conectar(self.db) as bd:
            vig=bd.execute("SELECT vigencia_hasta FROM vehiculo WHERE placa='PRB902'").fetchone()[0]
        self.assertEqual(vig,'1900-01-01')

    def test_historial_conserva_pago_anulado(self):
        p=self.pago(primera_fecha='2026-12-01')
        anular_pago(p,'Correccion administrativa',self.admin,self.db)
        self.assertEqual(len(listar_pagos('PRB902',self.db)),1)
        self.assertEqual(listar_pagos('PRB902',self.db)[0]['estado'],'ANULADO')

    def test_ancora_31_se_recupera_despues_febrero(self):
        jan=date(2027,1,31)
        feb=inicio_mes_siguiente(jan,31)
        mar=inicio_mes_siguiente(feb,31)
        self.assertEqual((feb.isoformat(),mar.isoformat()),('2027-02-28','2027-03-31'))

    def test_datos_pago_auditoria(self):
        self.pago(primera_fecha='2026-12-01')
        with conectar(self.db) as bd:
            registro=bd.execute("SELECT usuario_id,entidad,accion FROM auditoria WHERE entidad='pago'").fetchone()
        self.assertEqual(tuple(registro),(self.op,'pago','REGISTRAR'))

    def test_migracion_idempotente(self):
        self.pago(primera_fecha='2026-12-01')
        inicializar(self.db)
        self.assertEqual(len(listar_pagos('PRB902',self.db)),1)

    def test_vehiculo_legacy_renueva_despues_de_vigencia(self):
        crear_vehiculo('LEG123','CARRO',True,'2026-11-30',self.op,self.db)
        periodo=previsualizar_periodo('LEG123',self.db)
        self.assertEqual((periodo['inicio'],periodo['fin']),('2026-12-01','2026-12-31'))

if __name__=='__main__': unittest.main()
