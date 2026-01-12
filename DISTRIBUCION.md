# Distribución de Finanzas Desktop

## 📦 Ejecutable Compilado

El ejecutable compilado se encuentra en:
```
dist/finanzas_desktop/
```

## 📋 Contenido de la Distribución

La carpeta de distribución contiene:
- **finanzas_desktop.exe** - Ejecutable principal de la aplicación
- **.env** - Archivo de configuración de base de datos
- **_internal/** - Carpeta con librerías y dependencias necesarias

## 🚀 Instalación y Uso

### Primera vez:

1. **Copiar la carpeta completa** `dist/finanzas_desktop/` a la ubicación deseada

2. **Configurar la conexión a la base de datos:**
   - Editar el archivo `.env` con los datos de tu base de datos MySQL/MariaDB:
     ```
     DATABASE_URL=mysql+pymysql://usuario:contraseña@localhost:3306/nombre_base_datos
     DATE_FORMAT=dd/MM/yyyy
     ```
   - O ejecutar la aplicación directamente y usar el diálogo de configuración

3. **Ejecutar** `finanzas_desktop.exe`

### Actualizaciones:

Para actualizar a una nueva versión:
1. **Reemplazar** los archivos `finanzas_desktop.exe` y la carpeta `_internal/`
2. **Mantener** tu archivo `.env` con la configuración de base de datos
3. **Ejecutar migraciones** si es necesario (ver sección de migraciones)

## 🔄 Migraciones de Base de Datos

### Nueva migración incluida en esta versión:

Esta versión incluye una nueva funcionalidad de **variables de simulación con fecha de inicio**. 

**Migración necesaria:**
```
migrations/add_fecha_inicio_migration.py
```

**Cómo ejecutar la migración:**

Opción 1: Desde el entorno de desarrollo:
```bash
python migrations/add_fecha_inicio_migration.py
```

Opción 2: Ejecutar el SQL manualmente:
```sql
ALTER TABLE simulation_variables 
ADD COLUMN fecha_inicio DATE NULL COMMENT 'Fecha de inicio de aplicación de la variable';

CREATE INDEX idx_simulation_variables_fecha_inicio 
ON simulation_variables(fecha_inicio);
```

## 📝 Nuevas Funcionalidades en esta Versión

### 1. Botón "💳 Simular cuenta"
Nueva opción en el menú principal que permite simular una cuenta individual con vista detallada de movimientos:
- Selección de cuenta específica
- Rango de fechas configurable
- Vista de todos los movimientos (fijos, puntuales, ajustes, variables)
- Saldo acumulado después de cada movimiento
- Exportación a CSV
- Identificación de transferencias entre cuentas

### 2. Variables de Simulación con Fecha de Inicio
Las variables de simulación ahora incluyen:
- **Fecha de inicio:** Define desde cuándo se aplica la variable
- **Gestión de variables** accesible desde ambas ventanas de simulación
- Las variables se aplican desde su fecha de inicio según la frecuencia configurada

### 3. Mejoras en la Simulación Estándar
- Las variables respetan la fecha de inicio configurada
- Si no se especifica fecha, se aplican desde el inicio del rango de simulación

## 🔧 Requisitos del Sistema

- **Sistema Operativo:** Windows 10 o superior (64 bits)
- **Base de Datos:** MySQL 5.7+ o MariaDB 10.3+
- **Conexión a Internet:** Opcional (necesaria para actualizar cotizaciones de holdings)

## 📊 Estructura de la Base de Datos

La aplicación requiere las siguientes tablas:
- `account` - Cuentas
- `transaction` - Transacciones puntuales
- `fixed_expense` - Gastos/ingresos fijos recurrentes
- `adjustment` - Ajustes de reconciliación
- `mortgage` - Hipotecas
- `mortgage_period` - Períodos de amortización
- `holding` - Holdings de inversión
- `simulation_variables` - Variables de simulación (ahora con campo `fecha_inicio`)

## 🐛 Resolución de Problemas

### La aplicación no inicia:
- Verificar que todas las carpetas y archivos estén presentes
- Verificar permisos de ejecución
- Revisar el archivo `.env`

### Error de conexión a base de datos:
- Verificar credenciales en `.env`
- Comprobar que el servidor MySQL/MariaDB está corriendo
- Verificar permisos de usuario en la base de datos

### Error "platform plugin not found":
- Asegurarse de que la carpeta `_internal/` está completa
- No ejecutar el .exe desde otra ubicación sin copiar todo el contenido

## 📞 Soporte

Para reportar problemas o sugerencias, contactar al equipo de desarrollo.

## 📜 Historial de Versiones

### Versión Actual (Enero 2026)
- ✅ Nueva ventana "Simular cuenta" con vista detallada de movimientos
- ✅ Variables de simulación con fecha de inicio configurable
- ✅ Mejoras en la gestión de variables
- ✅ Identificación de transferencias en simulaciones
- ✅ Exportación a CSV mejorada

---

**Fecha de compilación:** 11 de Enero de 2026
**Entorno:** Python 3.11.6 + PySide6 + PyInstaller 6.16.0
