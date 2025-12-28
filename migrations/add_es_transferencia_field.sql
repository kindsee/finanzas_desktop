-- Migración: Añadir campo es_transferencia a Transaction y FixedExpense
-- Fecha: 2025-12-28
-- Descripción: Añade columna para identificar transferencias entre cuentas

-- Añadir columna a la tabla transaction
ALTER TABLE transaction 
ADD COLUMN es_transferencia INTEGER DEFAULT 0;

-- Añadir columna a la tabla fixed_expense
ALTER TABLE fixed_expense 
ADD COLUMN es_transferencia INTEGER DEFAULT 0;

-- Verificar cambios
SELECT 'Columnas añadidas correctamente' AS resultado;
