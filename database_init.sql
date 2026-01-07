-- ========================================================================
-- SCRIPT DE INICIALIZACIÓN DE BASE DE DATOS - Finanzas Desktop
-- ========================================================================
-- Fecha: 2026-01-07
-- Descripción: Crea todas las tablas necesarias desde cero
-- Base de datos: MySQL/MariaDB
-- ========================================================================

-- Crear base de datos si no existe
CREATE DATABASE IF NOT EXISTS MMFDatabase CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE MMFDatabase;

-- ========================================================================
-- TABLA: account (Cuentas bancarias)
-- ========================================================================
CREATE TABLE IF NOT EXISTS account (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL,
    saldo_inicial DECIMAL(12, 2) NOT NULL,
    visible INTEGER DEFAULT 1 COMMENT '1=visible en UI, 0=oculta',
    INDEX idx_visible (visible)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Cuentas bancarias del usuario';

-- ========================================================================
-- TABLA: transaction (Transacciones únicas)
-- ========================================================================
CREATE TABLE IF NOT EXISTS transaction (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    cuenta_id INTEGER NOT NULL,
    fecha DATE NOT NULL,
    descripcion VARCHAR(255) NOT NULL,
    monto DECIMAL(12, 2) NOT NULL,
    es_transferencia INTEGER DEFAULT 0 COMMENT '0=gasto/ingreso normal, 1=transferencia entre cuentas',
    FOREIGN KEY (cuenta_id) REFERENCES account (id) ON DELETE CASCADE,
    INDEX idx_cuenta_fecha (cuenta_id, fecha),
    INDEX idx_fecha (fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Transacciones únicas (ingresos/gastos)';

-- ========================================================================
-- TABLA: adjustment (Ajustes de reconciliación)
-- ========================================================================
CREATE TABLE IF NOT EXISTS adjustment (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    cuenta_id INTEGER NOT NULL,
    fecha DATE NOT NULL,
    monto_ajuste DOUBLE NOT NULL,
    descripcion VARCHAR(255),
    FOREIGN KEY (cuenta_id) REFERENCES account (id) ON DELETE CASCADE,
    INDEX idx_cuenta_fecha (cuenta_id, fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Ajustes de reconciliación/consolidación';

-- ========================================================================
-- TABLA: fixed_expense (Gastos/Ingresos recurrentes)
-- ========================================================================
CREATE TABLE IF NOT EXISTS fixed_expense (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    cuenta_id INTEGER NOT NULL,
    descripcion VARCHAR(100) NOT NULL,
    monto DECIMAL(10, 2) NOT NULL,
    frecuencia ENUM('semanal', 'mensual', 'trimestral', 'semestral', 'anual') NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE DEFAULT NULL COMMENT 'NULL = sin fecha fin (recurrente indefinido)',
    es_transferencia INTEGER DEFAULT 0 COMMENT '0=gasto/ingreso normal, 1=transferencia entre cuentas',
    FOREIGN KEY (cuenta_id) REFERENCES account (id) ON DELETE CASCADE,
    INDEX idx_cuenta (cuenta_id),
    INDEX idx_fechas (fecha_inicio, fecha_fin)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Gastos e ingresos recurrentes';

-- ========================================================================
-- TABLA: mortgage (Hipotecas/Préstamos)
-- ========================================================================
CREATE TABLE IF NOT EXISTS mortgage (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    tipo VARCHAR(20) NOT NULL COMMENT 'fijo o variable',
    fecha_inicio DATE NOT NULL,
    capital_inicial DOUBLE NOT NULL,
    cuotas_totales INTEGER NOT NULL,
    valor_actual_propiedad DOUBLE DEFAULT NULL COMMENT 'Valor actual de la propiedad (opcional)',
    INDEX idx_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Hipotecas y préstamos';

-- ========================================================================
-- TABLA: mortgage_interest (Períodos de interés de hipoteca)
-- ========================================================================
CREATE TABLE IF NOT EXISTS mortgage_interest (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    mortgage_id INTEGER NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    capital_inicio DOUBLE NOT NULL,
    capital_fin DOUBLE NOT NULL,
    interes DOUBLE NOT NULL COMMENT 'Tasa de interés del período',
    interes_total DECIMAL(15, 2) DEFAULT 0 COMMENT 'Total de intereses pagados en el período',
    amortizacion_total DECIMAL(15, 2) DEFAULT 0 COMMENT 'Total amortizado en el período',
    FOREIGN KEY (mortgage_id) REFERENCES mortgage (id) ON DELETE CASCADE,
    INDEX idx_mortgage (mortgage_id),
    INDEX idx_fechas (fecha_inicio, fecha_fin)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Períodos de interés para hipotecas';

-- ========================================================================
-- TABLA: holding_plan (Planes de inversión)
-- ========================================================================
CREATE TABLE IF NOT EXISTS holding_plan (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(120) NOT NULL UNIQUE,
    descripcion VARCHAR(255) DEFAULT NULL,
    INDEX idx_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Planes de inversión (carteras)';

-- ========================================================================
-- TABLA: holding (Valores/Activos en cartera)
-- ========================================================================
CREATE TABLE IF NOT EXISTS holding (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    plan_id INTEGER DEFAULT NULL,
    ticker VARCHAR(50) NOT NULL COMMENT 'Símbolo del ticker (ej: AAPL, SAN.MC)',
    exchange VARCHAR(30) DEFAULT NULL COMMENT 'Mercado (NASDAQ, BME, etc)',
    moneda VARCHAR(8) DEFAULT 'USD',
    cantidad DOUBLE NOT NULL DEFAULT 0.0 COMMENT 'Cantidad total del activo',
    last_price DOUBLE DEFAULT NULL COMMENT 'Último precio conocido',
    last_update DATETIME DEFAULT NULL COMMENT 'Última actualización de precio',
    FOREIGN KEY (plan_id) REFERENCES holding_plan (id) ON DELETE SET NULL,
    INDEX idx_plan (plan_id),
    INDEX idx_ticker (ticker)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Activos en cartera (acciones, ETFs, criptos)';

-- ========================================================================
-- TABLA: holding_purchase (Compras de activos)
-- ========================================================================
CREATE TABLE IF NOT EXISTS holding_purchase (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    holding_id INTEGER NOT NULL,
    fecha DATE NOT NULL,
    cantidad DECIMAL(24, 8) NOT NULL COMMENT 'Cantidad comprada (alta precisión para criptos)',
    precio_unitario DECIMAL(24, 8) NOT NULL COMMENT 'Precio unitario de compra',
    comisiones DECIMAL(12, 2) DEFAULT NULL COMMENT 'Comisiones de la operación',
    nota VARCHAR(255) DEFAULT NULL,
    FOREIGN KEY (holding_id) REFERENCES holding (id) ON DELETE CASCADE,
    INDEX idx_holding (holding_id),
    INDEX idx_fecha (fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Historial de compras de activos';

-- ========================================================================
-- TABLA: price_snapshot (Cache de precios de activos)
-- ========================================================================
CREATE TABLE IF NOT EXISTS price_snapshot (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    ticker VARCHAR(50) NOT NULL UNIQUE,
    price DECIMAL(18, 6) DEFAULT NULL,
    updated_at DATETIME DEFAULT NULL,
    INDEX idx_ticker (ticker)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Cache de precios actuales de activos';

-- ========================================================================
-- TABLA: simulation_variables (Variables de simulación)
-- ========================================================================
CREATE TABLE IF NOT EXISTS simulation_variables (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    descripcion VARCHAR(255) NOT NULL,
    cuenta_id INTEGER NOT NULL,
    importe DECIMAL(15, 2) NOT NULL,
    frecuencia VARCHAR(50) NOT NULL COMMENT 'semanal, mensual, trimestral, semestral, anual',
    activo INTEGER DEFAULT 1 COMMENT '1=activa en simulaciones, 0=inactiva',
    FOREIGN KEY (cuenta_id) REFERENCES account (id) ON DELETE CASCADE,
    INDEX idx_cuenta (cuenta_id),
    INDEX idx_activo (activo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Variables hipotéticas para simulación de saldos';

-- ========================================================================
-- DATOS DE EJEMPLO (OPCIONAL - Comentar si no se desea)
-- ========================================================================

-- Insertar una cuenta de ejemplo
-- INSERT INTO account (nombre, saldo_inicial, visible) VALUES ('Cuenta Corriente', 1000.00, 1);

-- ========================================================================
-- VERIFICACIÓN FINAL
-- ========================================================================
SELECT 'Base de datos creada exitosamente' AS resultado;
SELECT COUNT(*) AS total_tablas FROM information_schema.tables 
WHERE table_schema = 'MMFDatabase' AND table_type = 'BASE TABLE';
