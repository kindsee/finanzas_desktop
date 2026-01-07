-- Migración: Crear tabla simulation_variables
-- Fecha: 2026-01-04
-- Descripción: Crea tabla para almacenar variables de simulación

CREATE TABLE IF NOT EXISTS simulation_variables (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    descripcion VARCHAR(255) NOT NULL,
    cuenta_id INTEGER NOT NULL,
    importe DECIMAL(15, 2) NOT NULL,
    frecuencia VARCHAR(50) NOT NULL,
    activo INTEGER DEFAULT 1,
    FOREIGN KEY (cuenta_id) REFERENCES account (id)
);

-- Verificar creación
SELECT 'Tabla simulation_variables creada correctamente' AS resultado;
