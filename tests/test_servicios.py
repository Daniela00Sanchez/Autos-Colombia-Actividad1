import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bd import inicializar, conectar
from servicios import (ErrorNegocio, consultar_placa, registrar_entrada, registrar_salida,
                       registrar_novedad, historial, resumen)


class PruebasAutosColombia(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.db = Path(self.temporal.name) / 'test.sqlite'
        inicializar(self.db)

    def tearDown(self):
        self.temporal.cleanup()

    def test_datos_iniciales_coinciden(self):
        dato = resumen(self.db)
        self.assertEqual((dato['capacidad'], dato['dentro'], dato['carros'], dato['motos'], dato['disponibles']),
                         (20, 13, 9, 4, 7))

    def test_placa_precargada_puede_entrar(self):
        dato = consultar_placa('mnv345', self.db, '2026-10-19 09:00:00')
        self.assertTrue(dato['puede_entrar'])

    def test_placa_no_registrada_rechazada(self):
        with self.assertRaises(ErrorNegocio):
            registrar_entrada('ZZZ999', self.db, '2026-10-19 09:00:00')

    def test_no_autorizado_rechazado(self):
        with self.assertRaises(ErrorNegocio):
            registrar_entrada('NOP999', self.db, '2026-10-19 09:00:00')

    def test_vencido_rechazado(self):
        with self.assertRaises(ErrorNegocio):
            registrar_entrada('VNC777', self.db, '2026-10-19 09:00:00')

    def test_entrada_y_salida_normal(self):
        registrar_entrada('MNV345', self.db, '2026-10-19 09:00:00')
        self.assertEqual(resumen(self.db)['dentro'], 14)
        registrar_salida('MNV345', self.db, '2026-10-19 12:00:00')
        self.assertEqual(resumen(self.db)['dentro'], 13)
        movs = historial('MNV345', ruta=self.db)
        self.assertEqual(movs[0]['fecha_hora_salida'], '2026-10-19 12:00:00')

    def test_impedir_entrada_duplicada(self):
        registrar_entrada('MNV345', self.db, '2026-10-19 09:00:00')
        with self.assertRaises(ErrorNegocio):
            registrar_entrada('MNV345', self.db, '2026-10-19 09:05:00')

    def test_impedir_salida_sin_entrada(self):
        with self.assertRaises(ErrorNegocio):
            registrar_salida('MNV345', self.db, '2026-10-19 12:00:00')

    def test_impedir_salida_antes_de_entrada(self):
        with self.assertRaises(ErrorNegocio):
            registrar_salida('KLP482', self.db, '2026-10-14 12:00:00')

    def test_cupos_agotados(self):
        with conectar(self.db) as bd:
            bd.execute('UPDATE configuracion SET capacidad_total=13 WHERE id=1')
        with self.assertRaises(ErrorNegocio):
            registrar_entrada('MNV345', self.db, '2026-10-19 09:00:00')

    def test_novedad_guardada(self):
        n = registrar_novedad('TQR73F', 'Observacion general', 'Retrovisor plegado al ingresar.',
                              self.db, '2026-10-19 09:00:00')
        with conectar(self.db) as bd:
            f = bd.execute('SELECT id_novedad FROM novedad WHERE id_novedad=?', (n['id_novedad'],)).fetchone()
        self.assertIsNotNone(f)

    def test_novedad_sin_entrada_rechazada(self):
        with self.assertRaises(ErrorNegocio):
            registrar_novedad('MNV345', 'Observacion general', 'Observación de prueba.', self.db)

    def test_filtro_historial(self):
        movs = historial('JBD865', '2026-10-14', '2026-10-15', ruta=self.db)
        self.assertEqual(len(movs), 2)

    def test_reinicio_no_duplica_registros(self):
        inicializar(self.db)
        self.assertEqual(resumen(self.db)['dentro'], 13)


if __name__ == '__main__':
    unittest.main()
