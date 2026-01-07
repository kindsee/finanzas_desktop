-- Migración: Añadir campo visible a la tabla account
-- Fecha: 2026-01-07
-- Descripción: Añade columna para controlar visibilidad de cuentas en la UI

-- Añadir columna a la tabla account
ALTER TABLE account 
ADD COLUMN visible INTEGER DEFAULT 1;

-- Verificar cambios
SELECT 'Columna visible añadida correctamente a account' AS resultado;
