-- Agregar campo fecha_inicio a la tabla simulation_variables
-- Este campo permite especificar la fecha de inicio de aplicación de cada variable

ALTER TABLE simulation_variables 
ADD COLUMN fecha_inicio DATE NULL COMMENT 'Fecha de inicio de aplicación de la variable';

-- Índice para mejorar el rendimiento en consultas por fecha
CREATE INDEX idx_simulation_variables_fecha_inicio ON simulation_variables(fecha_inicio);
