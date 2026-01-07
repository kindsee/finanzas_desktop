# Guía de Instalación - Funcionalidad de Simulación

## Pasos para activar la funcionalidad

### 1. Ejecutar la migración de base de datos

Antes de usar la funcionalidad de simulación por primera vez, debes crear la tabla `simulation_variables`:

```bash
# Desde el directorio raíz del proyecto
python migrations/add_simulation_table.py
```

Cuando se te pregunte, responde **'s'** para confirmar la migración.

**Salida esperada:**
```
============================================================
  MIGRACIÓN: Crear tabla simulation_variables
============================================================

🔍 Buscando archivo: migrations\add_simulation_variables_table.sql

⚠️  Esta migración creará la tabla 'simulation_variables' con:
   - id (PRIMARY KEY)
   - descripcion (VARCHAR)
   - cuenta_id (FOREIGN KEY a accounts)
   - importe (DECIMAL)
   - frecuencia (VARCHAR)
   - activo (INTEGER, default 1)

¿Continuar con la migración? (s/n): s

🚀 Ejecutando migración...

  Ejecutando statement 1...
    ✓ {'resultado': 'Tabla simulation_variables creada correctamente'}

✅ Migración completada exitosamente

============================================================
  ✅ MIGRACIÓN COMPLETADA
============================================================

💡 Ahora puedes usar la funcionalidad de simulación
```

### 2. Verificar la instalación (opcional)

Puedes probar la funcionalidad con el script de prueba:

```bash
python test_simulacion.py
```

Este script mostrará:
- Las cuentas disponibles
- Las variables de simulación activas
- Una simulación de 6 meses

### 3. Usar la funcionalidad en la aplicación

1. **Ejecutar la aplicación**:
   ```bash
   python main.py
   ```

2. **Abrir Simulación**:
   - Clic en el botón **"🎯 Simulación"** (último botón de la barra superior)

3. **Gestionar Variables** (primera vez):
   - Clic en **"Gestionar Variables"**
   - Clic en **"Nueva Variable"**
   - Completar formulario:
     - **Descripción**: Nombre descriptivo (ej: "Ahorro mensual planificado")
     - **Cuenta**: Seleccionar cuenta afectada
     - **Importe**: Cantidad (positiva para ingresos, negativa para gastos)
     - **Frecuencia**: semanal, mensual, trimestral, semestral o anual
     - **Activo**: Marcar para incluir en simulaciones
   - Guardar

4. **Ejecutar Simulación**:
   - Establecer **Fecha Inicio** y **Fecha Fin**
   - Establecer **Intervalo** en días (ej: 7 = semanal, 30 = mensual)
   - Seleccionar **cuentas** a incluir (checkboxes)
   - Clic en **"Ejecutar Simulación"**
   - Ver resultados en la tabla

## Ejemplos de Variables

### Variable de Ahorro Mensual
- **Descripción**: Ahorro planificado
- **Cuenta**: Cuenta Ahorro
- **Importe**: 500.00
- **Frecuencia**: mensual
- **Activo**: ✓

### Variable de Gasto Hipoteca
- **Descripción**: Cuota hipoteca
- **Cuenta**: Cuenta Corriente
- **Importe**: -800.00
- **Frecuencia**: mensual
- **Activo**: ✓

### Variable de Bonus Anual
- **Descripción**: Bonus de empresa
- **Cuenta**: Cuenta Corriente
- **Importe**: 3000.00
- **Frecuencia**: anual
- **Activo**: ✓

## Interpretación de Resultados

La tabla de simulación muestra:

```
Fecha       | Cuenta1   | Cuenta2   | TOTAL
01/01/2026  | 1,000.00  | 500.00    | 1,500.00
01/02/2026  | 700.00    | 1,000.00  | 1,700.00
01/03/2026  | 400.00    | 1,500.00  | 1,900.00
```

- **Fecha**: Momento del cálculo según el intervalo
- **CuentaX**: Saldo proyectado incluyendo variables
- **TOTAL**: Suma de todas las cuentas seleccionadas

Los saldos mostrados son:
```
Saldo Proyectado = Saldo Real (de movimientos reales) + Efectos de Variables Activas
```

## Características Avanzadas

### Desactivar Variables Temporalmente
- Editar variable y desmarcar "Variable activa"
- La variable se conserva pero no afecta las simulaciones

### Simular Diferentes Escenarios
1. Crear variables para cada escenario
2. Activar solo las del escenario a simular
3. Ejecutar simulación
4. Cambiar variables activas y repetir

### Intervalos Recomendados
- **Semanal**: 7 días
- **Quincenal**: 15 días
- **Mensual**: 30 días
- **Trimestral**: 90 días

## Solución de Problemas

### Error: "No se encuentra el archivo de migración"
**Solución**: Verifica que estás ejecutando el comando desde el directorio raíz del proyecto.

### Error: "No se pudo conectar a la base de datos"
**Solución**: Verifica que el archivo `.env` contiene `DATABASE_URL` correctamente configurado.

### La tabla no muestra resultados
**Solución**: 
1. Verifica que al menos una cuenta está seleccionada
2. Verifica que la fecha de inicio es anterior a la fecha de fin
3. Verifica que el intervalo es válido (1-365 días)

### Las variables no afectan la simulación
**Solución**: Verifica que las variables están marcadas como "Activo" en el diálogo de gestión de variables.

## Notas Importantes

- ⚠️ Las variables de simulación **NO afectan** los datos reales de la aplicación
- 🔒 Solo se usan para proyecciones y escenarios hipotéticos
- 💾 Las variables se guardan en la base de datos y persisten entre sesiones
- 📊 Los saldos base siempre vienen de los movimientos reales (transactions, fixed_expenses, adjustments)

## Soporte

Para más detalles técnicos, consulta [SIMULACION_README.md](SIMULACION_README.md).
