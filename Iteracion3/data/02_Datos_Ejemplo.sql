-- Datos ficticios para coincidir con los mockups del 15/10/2026.
-- No se crean ni se gestionan pagos o celdas.
INSERT OR IGNORE INTO configuracion (id, capacidad_total) VALUES (1, 20);

INSERT OR IGNORE INTO vehiculo (placa, tipo, autorizado, vigencia_hasta) VALUES ('KLP482', 'CARRO', 1, '2026-11-20');
INSERT OR IGNORE INTO vehiculo (placa, tipo, autorizado, vigencia_hasta) VALUES ('TQR73F', 'MOTO', 1, '2026-11-20');
INSERT OR IGNORE INTO vehiculo (placa, tipo, autorizado, vigencia_hasta) VALUES ('FZU219', 'CARRO', 1, '2026-11-20');
INSERT OR IGNORE INTO vehiculo (placa, tipo, autorizado, vigencia_hasta) VALUES ('JBD865', 'CARRO', 1, '2026-11-20');
INSERT OR IGNORE INTO vehiculo (placa, tipo, autorizado, vigencia_hasta) VALUES ('ABC527', 'CARRO', 1, '2026-11-20');
INSERT OR IGNORE INTO vehiculo (placa, tipo, autorizado, vigencia_hasta) VALUES ('DFG625', 'CARRO', 1, '2026-11-20');
INSERT OR IGNORE INTO vehiculo (placa, tipo, autorizado, vigencia_hasta) VALUES ('HXU932', 'CARRO', 1, '2026-11-20');
INSERT OR IGNORE INTO vehiculo (placa, tipo, autorizado, vigencia_hasta) VALUES ('LMN204', 'CARRO', 1, '2026-11-20');
INSERT OR IGNORE INTO vehiculo (placa, tipo, autorizado, vigencia_hasta) VALUES ('PQR581', 'CARRO', 1, '2026-11-20');
INSERT OR IGNORE INTO vehiculo (placa, tipo, autorizado, vigencia_hasta) VALUES ('STU936', 'CARRO', 1, '2026-11-20');
INSERT OR IGNORE INTO vehiculo (placa, tipo, autorizado, vigencia_hasta) VALUES ('BCR31E', 'MOTO', 1, '2026-11-20');
INSERT OR IGNORE INTO vehiculo (placa, tipo, autorizado, vigencia_hasta) VALUES ('HUY22D', 'MOTO', 1, '2026-11-20');
INSERT OR IGNORE INTO vehiculo (placa, tipo, autorizado, vigencia_hasta) VALUES ('LMN44G', 'MOTO', 1, '2026-11-20');
INSERT OR IGNORE INTO vehiculo (placa, tipo, autorizado, vigencia_hasta) VALUES ('MNV345', 'CARRO', 1, '2026-11-20');
INSERT OR IGNORE INTO vehiculo (placa, tipo, autorizado, vigencia_hasta) VALUES ('NOP999', 'CARRO', 0, '2026-11-20');
INSERT OR IGNORE INTO vehiculo (placa, tipo, autorizado, vigencia_hasta) VALUES ('VNC777', 'MOTO', 1, '2026-09-30');

INSERT OR IGNORE INTO movimiento (id_movimiento, placa, fecha_hora_entrada, fecha_hora_salida) VALUES (1, 'KLP482', '2026-10-15 07:36:00', NULL);
INSERT OR IGNORE INTO movimiento (id_movimiento, placa, fecha_hora_entrada, fecha_hora_salida) VALUES (2, 'TQR73F', '2026-10-15 08:42:00', NULL);
INSERT OR IGNORE INTO movimiento (id_movimiento, placa, fecha_hora_entrada, fecha_hora_salida) VALUES (3, 'FZU219', '2026-10-15 10:16:00', NULL);
INSERT OR IGNORE INTO movimiento (id_movimiento, placa, fecha_hora_entrada, fecha_hora_salida) VALUES (4, 'JBD865', '2026-10-14 07:12:00', '2026-10-14 18:05:00');
INSERT OR IGNORE INTO movimiento (id_movimiento, placa, fecha_hora_entrada, fecha_hora_salida) VALUES (5, 'JBD865', '2026-10-15 11:05:00', NULL);
INSERT OR IGNORE INTO movimiento (id_movimiento, placa, fecha_hora_entrada, fecha_hora_salida) VALUES (6, 'ABC527', '2026-10-15 06:20:00', NULL);
INSERT OR IGNORE INTO movimiento (id_movimiento, placa, fecha_hora_entrada, fecha_hora_salida) VALUES (7, 'DFG625', '2026-10-15 07:50:00', NULL);
INSERT OR IGNORE INTO movimiento (id_movimiento, placa, fecha_hora_entrada, fecha_hora_salida) VALUES (8, 'HXU932', '2026-10-15 08:12:00', NULL);
INSERT OR IGNORE INTO movimiento (id_movimiento, placa, fecha_hora_entrada, fecha_hora_salida) VALUES (9, 'LMN204', '2026-10-15 09:05:00', NULL);
INSERT OR IGNORE INTO movimiento (id_movimiento, placa, fecha_hora_entrada, fecha_hora_salida) VALUES (10, 'PQR581', '2026-10-15 09:24:00', NULL);
INSERT OR IGNORE INTO movimiento (id_movimiento, placa, fecha_hora_entrada, fecha_hora_salida) VALUES (11, 'STU936', '2026-10-15 11:32:00', NULL);
INSERT OR IGNORE INTO movimiento (id_movimiento, placa, fecha_hora_entrada, fecha_hora_salida) VALUES (12, 'BCR31E', '2026-10-15 07:15:00', NULL);
INSERT OR IGNORE INTO movimiento (id_movimiento, placa, fecha_hora_entrada, fecha_hora_salida) VALUES (13, 'HUY22D', '2026-10-15 10:24:00', NULL);
INSERT OR IGNORE INTO movimiento (id_movimiento, placa, fecha_hora_entrada, fecha_hora_salida) VALUES (14, 'LMN44G', '2026-10-15 12:41:00', NULL);
INSERT OR IGNORE INTO novedad (id_novedad, id_movimiento, tipo, descripcion, fecha_hora_registro) VALUES (1, 2, 'Observacion general', 'Se observa el retrovisor plegado al ingresar. Se deja constancia de la observacion.', '2026-10-15 08:43:00');
