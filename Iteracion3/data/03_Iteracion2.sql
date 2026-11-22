-- Nuevas tablas de la Iteración 2; se agregan sin reemplazar la Iteración 1.
CREATE TABLE IF NOT EXISTS usuario (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 usuario TEXT NOT NULL UNIQUE COLLATE NOCASE,
 nombre TEXT NOT NULL,
 clave_hash TEXT NOT NULL,
 rol TEXT NOT NULL CHECK (rol IN ('administrador','operador')),
 activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0,1)),
 creado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS celda (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 codigo TEXT NOT NULL UNIQUE COLLATE NOCASE,
 activa INTEGER NOT NULL DEFAULT 1 CHECK (activa IN (0,1))
);
CREATE TABLE IF NOT EXISTS sesion_activa (
 token_hash TEXT PRIMARY KEY,
 usuario_id INTEGER NOT NULL REFERENCES usuario(id),
 inicio TEXT NOT NULL,
 ultimo_uso TEXT NOT NULL,
 vencimiento TEXT NOT NULL,
 cerrada INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_sesion_usuario ON sesion_activa(usuario_id);
CREATE TABLE IF NOT EXISTS auditoria (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 usuario_id INTEGER REFERENCES usuario(id),
 accion TEXT NOT NULL,
 entidad TEXT NOT NULL,
 referencia TEXT NOT NULL,
 antes TEXT,
 despues TEXT,
 fecha_hora TEXT NOT NULL
);
