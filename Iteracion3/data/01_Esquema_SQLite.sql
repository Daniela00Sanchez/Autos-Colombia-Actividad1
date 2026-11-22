-- AUTOS COLOMBIA - ITERACIÓN 1
-- Modelo físico SQLite. Solo entradas y salidas de carros y motos.
-- No contiene módulos de usuarios, celdas o pagos.
-- SQLite almacena fechas/horas en formato ISO 8601.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS vehiculo (
    placa TEXT PRIMARY KEY,
    tipo TEXT NOT NULL CHECK (tipo IN ('CARRO', 'MOTO')),
    autorizado INTEGER NOT NULL DEFAULT 1 CHECK (autorizado IN (0, 1)),
    vigencia_hasta TEXT NOT NULL CHECK (
        length(vigencia_hasta) = 10 AND date(vigencia_hasta) IS NOT NULL
    )
);

CREATE TABLE IF NOT EXISTS configuracion (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    capacidad_total INTEGER NOT NULL CHECK (capacidad_total > 0)
);

CREATE TABLE IF NOT EXISTS movimiento (
    id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
    placa TEXT NOT NULL,
    fecha_hora_entrada TEXT NOT NULL CHECK (
        datetime(fecha_hora_entrada) IS NOT NULL
    ),
    fecha_hora_salida TEXT CHECK (
        fecha_hora_salida IS NULL OR
        (datetime(fecha_hora_salida) IS NOT NULL AND
         datetime(fecha_hora_salida) > datetime(fecha_hora_entrada))
    ),
    FOREIGN KEY (placa) REFERENCES vehiculo(placa)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS novedad (
    id_novedad INTEGER PRIMARY KEY AUTOINCREMENT,
    id_movimiento INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    descripcion TEXT NOT NULL CHECK (length(trim(descripcion)) > 0),
    fecha_hora_registro TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_movimiento) REFERENCES movimiento(id_movimiento)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

-- Una placa solo puede tener una estancia abierta a la vez.
CREATE UNIQUE INDEX IF NOT EXISTS uq_movimiento_placa_activa
    ON movimiento(placa) WHERE fecha_hora_salida IS NULL;
CREATE INDEX IF NOT EXISTS idx_movimiento_entrada
    ON movimiento(fecha_hora_entrada);
CREATE INDEX IF NOT EXISTS idx_novedad_movimiento
    ON novedad(id_movimiento);

-- Solo se permite ingresar a vehículos preautorizados y vigentes.
CREATE TRIGGER IF NOT EXISTS trg_validar_entrada
BEFORE INSERT ON movimiento
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1 FROM vehiculo
            WHERE placa = NEW.placa
              AND autorizado = 1
              AND vigencia_hasta >= date(NEW.fecha_hora_entrada)
        ) THEN RAISE(ABORT, 'Vehiculo no registrado, no autorizado o vencido')
    END;

    SELECT CASE
        WHEN (SELECT count(*) FROM movimiento WHERE fecha_hora_salida IS NULL)
           >= (SELECT capacidad_total FROM configuracion WHERE id = 1)
        THEN RAISE(ABORT, 'No hay cupos disponibles')
    END;
END;
