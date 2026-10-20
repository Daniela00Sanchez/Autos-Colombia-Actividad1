# Autos Colombia — Iteración 1

Aplicación web académica de **gestión de entradas y salidas de carros y motocicletas**.

**Tecnologías:** Python, Flask, SQLite, HTML y CSS.

## Alcance

Permite consultar placas previamente registradas, validar su autorización y fecha de vigencia, registrar entradas y salidas, registrar novedades de vehículos estacionados, consultar el historial y mostrar la ocupación del parqueadero. Utiliza una capacidad total preconfigurada y **no asigna celdas fijas**.

Esta iteración **no implementa** gestión de usuarios, gestión de celdas ni gestión de pagos. Los registros autorizados y las fechas de vigencia son datos precargados para las pruebas. El sistema no cobra, no genera facturas ni renueva mensualidades.

## Inicio rápido (Windows, con Python instalado)

Abre la carpeta del proyecto en Visual Studio Code y su terminal. Ejecuta:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Abre `http://127.0.0.1:5000` en el navegador. Para detener el servidor, presiona `Ctrl+C` en la terminal. No utilices permisos de administrador ni desactives la seguridad de Windows.

El programa crea al inicio su propia base SQLite en `data/Autos_Colombia_Iteracion1.sqlite`, copiando el esquema y los registros ficticios incluidos. **No altera la base SQLite guardada en otros entregables.**

## Casos de prueba

- `MNV345`: carro registrado y autorizado, inicialmente fuera; úsalo para registrar una entrada y una salida.
- `KLP482`: carro inicialmente estacionado; úsalo para registrar una salida.
- `TQR73F`: moto inicialmente estacionada; úsala para registrar una novedad.
- `NOP999`: no autorizado; debe rechazarse su entrada.
- `VNC777`: vigencia vencida; debe rechazarse su entrada.
- Una segunda entrada con la misma placa activa debe ser rechazada.

Comprobación automatizada (sin necesitar Flask):

```powershell
python -m unittest discover -s tests -v
```

## Organización

```text
app.py               Rutas web y formularios
servicios.py         Lógica de negocio: validaciones, entradas, salidas, novedades
bd.py                Conexión e inicialización de la base SQLite
templates/           Seis pantallas HTML
static/estilos.css   Estilos de las pantallas
data/                Esquema y datos de ejemplo
tests/               Pruebas automáticas
```

## Reglas importantes

- Los vehículos deben existir en la tabla precargada `vehiculo`, tener `autorizado=1` y vigencia no vencida.
- Solamente puede existir un movimiento abierto por placa.
- No se puede ingresar si el parqueadero llegó a su capacidad máxima.
- La hora de entrada, salida y novedad se registra automáticamente en UTC−5 (Colombia).
- Las novedades se vinculan a una entrada activa de un vehículo.
- La misma placa puede tener muchas entradas y salidas a lo largo del tiempo.
- No se administra el día de cobro ni se actualizan pagos: solo se verifica la `vigencia_hasta` precargada.

**Nota de seguridad:** prototipo académico local para pruebas, sin autenticación de operadores. No se debe exponer públicamente en Internet ni utilizar con información personal real.
