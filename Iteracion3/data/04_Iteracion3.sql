-- AUTOS COLOMBIA - ITERACIÓN 3
-- Pagos de mensualidad registrados desde una sesión del sistema.
CREATE TABLE IF NOT EXISTS pago_mensualidad (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_recibo TEXT UNIQUE,
    token_operacion TEXT NOT NULL UNIQUE,
    placa TEXT NOT NULL REFERENCES vehiculo(placa) ON UPDATE CASCADE ON DELETE RESTRICT,
    importe_pesos INTEGER NOT NULL CHECK (importe_pesos > 0),
    medio_pago TEXT NOT NULL CHECK (medio_pago IN ('EFECTIVO','TRANSFERENCIA','OTRO')),
    referencia_pago TEXT NOT NULL DEFAULT '',
    fecha_pago TEXT NOT NULL,
    inicio_periodo TEXT NOT NULL,
    fin_periodo TEXT NOT NULL,
    dia_ancla INTEGER NOT NULL CHECK (dia_ancla BETWEEN 1 AND 31),
    vigencia_anterior TEXT NOT NULL,
    habilitada_desde_anterior TEXT,
    registrado_por_id INTEGER NOT NULL REFERENCES usuario(id),
    estado TEXT NOT NULL DEFAULT 'REGISTRADO' CHECK (estado IN ('REGISTRADO','ANULADO')),
    fecha_anulacion TEXT,
    anulado_por_id INTEGER REFERENCES usuario(id),
    motivo_anulacion TEXT,
    CHECK (fin_periodo >= inicio_periodo)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pago_periodo_vigente
    ON pago_mensualidad(placa,inicio_periodo) WHERE estado='REGISTRADO';
CREATE INDEX IF NOT EXISTS idx_pagos_placa ON pago_mensualidad(placa,id DESC);
