# Funcionalidad de Simulación

## Descripción
La funcionalidad de simulación permite proyectar los saldos futuros de las cuentas en base a escenarios hipotéticos, utilizando variables que simulan ingresos o gastos recurrentes que aún no están registrados en el sistema.

## Componentes

### 1. Modelo: SimulationVariable
**Archivo**: `models/simulation_variable.py`

Define las variables de simulación con los siguientes campos:
- `id`: Identificador único
- `descripcion`: Descripción de la variable (ej: "Incremento salarial esperado")
- `cuenta_id`: Cuenta a la que afecta
- `importe`: Cantidad aplicada (positiva o negativa)
- `frecuencia`: Periodicidad (semanal, mensual, trimestral, semestral, anual)
- `activo`: Si está activa se incluye en la simulación (0=inactiva, 1=activa)

### 2. Diálogo de Variables
**Archivo**: `ui/variables_dialog.py`

Gestión CRUD de variables de simulación:
- **VariableEditDialog**: Formulario para crear/editar variables
- **VariablesDialog**: Tabla con listado y botones de acción (Nueva, Editar, Eliminar)

### 3. Ventana Principal de Simulación
**Archivo**: `ui/simulation_window.py`

Interfaz principal con:
- **Configuración**:
  - Fecha de inicio y fin
  - Intervalo de cálculo (en días)
- **Selección de cuentas**: Checkboxes para activar/desactivar cuentas
- **Botón Variables**: Abre el diálogo de gestión de variables
- **Botón Ejecutar Simulación**: Calcula y muestra resultados
- **Tabla de resultados**: 
  - Columnas: Fecha | Cuenta1 | Cuenta2 | ... | TOTAL
  - Cada fila representa un punto temporal según el intervalo

### 4. Lógica de Cálculo

La simulación sigue este proceso:

1. **Obtener saldos base**: Usa `calcular_balance_cuenta()` del reconciler para obtener el saldo real de cada cuenta en cada fecha
2. **Aplicar variables activas**: Pre-calcula las fechas donde cada variable activa aplica según su frecuencia
3. **Acumular efectos**: Suma los efectos de todas las variables hasta cada fecha de cálculo
4. **Saldo proyectado**: `saldo_final = saldo_base + efectos_variables_acumulados`

**Importante**: Las variables solo se usan para simulación, no afectan los datos reales ni el resto de la aplicación.

## Uso

### Crear Variables de Simulación
1. Clic en botón **"🎯 Simulación"** en la ventana principal
2. Clic en **"Gestionar Variables"**
3. Clic en **"Nueva Variable"**
4. Completar formulario:
   - Descripción: "Ahorro mensual planificado"
   - Cuenta: Seleccionar de desplegable
   - Importe: 500.00 (positivo = ingreso, negativo = gasto)
   - Frecuencia: mensual
   - Activo: ✓ (checked)
5. Guardar

### Ejecutar Simulación
1. En la ventana de simulación:
   - Establecer **Fecha Inicio** y **Fecha Fin**
   - Establecer **Intervalo** (ej: 7 días para semanal, 30 para mensual)
   - Seleccionar las **cuentas** a incluir (checkboxes)
2. Clic en **"Ejecutar Simulación"**
3. La tabla mostrará:
   - Saldos proyectados en cada fecha
   - Columna TOTAL con la suma de todas las cuentas

### Ejemplo de Escenario
```
Variables activas:
- "Ahorro mensual": +500€, cuenta Ahorro, mensual
- "Hipoteca": -800€, cuenta Corriente, mensual
- "Bonus anual": +2000€, cuenta Corriente, anual

Simulación: 01/01/2026 - 31/12/2026, intervalo 30 días

Resultado:
Fecha       | Corriente | Ahorro | TOTAL
01/01/2026  | 1000.00   | 500.00 | 1500.00
31/01/2026  | 700.00    | 1000.00| 1700.00
...
```

## Migración de Base de Datos

Para crear la tabla necesaria:

```bash
python migrations/add_simulation_table.py
```

Esto ejecutará `add_simulation_variables_table.sql` que crea la tabla `simulation_variables`.

## Archivos Relacionados

- `models/simulation_variable.py` - Modelo ORM
- `ui/simulation_window.py` - Ventana principal
- `ui/variables_dialog.py` - Gestión de variables
- `main.py` - Botón y método `on_simulation_clicked()`
- `migrations/add_simulation_variables_table.sql` - Schema SQL
- `migrations/add_simulation_table.py` - Script de migración

## Consideraciones Técnicas

- **Frecuencias**: Usa `dateutil.relativedelta` para cálculos de meses/años precisos
- **Precisión**: Utiliza `Decimal` para cálculos financieros, convierte a `float` solo para la UI
- **Performance**: Pre-calcula efectos de variables una vez, luego acumula por fecha
- **Sesiones**: Pasa la misma sesión a `calcular_balance_cuenta()` - no abrir nuevas sesiones
- **Aislamiento**: Las variables NO afectan tablas reales (Transaction, FixedExpense, etc.)
