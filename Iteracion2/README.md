# Autos Colombia - Iteración 2

## Descripción
Esta segunda iteración continúa el sistema de parqueadero desarrollado en la primera actividad. Se agregó la gestión de usuarios y celdas para controlar el acceso de los empleados y registrar quién realiza cada operación.

## Funcionalidades
- Inicio de sesión con usuario y contraseña.
- Dos perfiles: administrador y operador.
- Registro de vehículos, entradas y salidas.
- Administración de usuarios y celdas.
- Consulta de disponibilidad del parqueadero.
- Registro de acciones realizadas por los empleados.
- Control de permisos según el perfil.

## Tecnologías utilizadas
Python, Flask, SQLite, HTML y CSS.

## Ejecución
1. Instalar las dependencias: `python -m pip install -r requirements.txt`
2. Configurar el administrador inicial: `python configurar_admin.py`
3. Ejecutar la aplicación: `python app.py`
4. Abrir `http://127.0.0.1:5000`

## Pruebas
Se ejecutaron 28 pruebas automáticas con resultado satisfactorio mediante `python -m unittest discover -s tests -v`.
