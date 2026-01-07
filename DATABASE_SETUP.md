# Instalación de Base de Datos desde Cero

## Requisitos Previos
- MySQL o MariaDB instalado
- phpMyAdmin o cliente MySQL
- Permisos de creación de base de datos

## Opción 1: Ejecutar desde phpMyAdmin (Recomendado)

### Pasos:

1. **Acceder a phpMyAdmin**
   - Abre tu navegador y ve a phpMyAdmin (normalmente `http://localhost/phpmyadmin`)

2. **Importar el script SQL**
   - Clic en la pestaña **"SQL"** en la parte superior
   - O clic en **"Importar"** en el menú principal

3. **Ejecutar el script**

   **Método A - Pegar directamente:**
   - Abre el archivo `database_init.sql` con un editor de texto
   - Copia todo el contenido
   - Pégalo en la pestaña SQL de phpMyAdmin
   - Clic en **"Continuar"** o **"Ejecutar"**

   **Método B - Importar archivo:**
   - En la pestaña "Importar"
   - Clic en **"Seleccionar archivo"**
   - Selecciona `database_init.sql`
   - Clic en **"Continuar"**

4. **Verificar la creación**
   - Verás un mensaje: "Base de datos creada exitosamente"
   - En el panel izquierdo aparecerá `MMFDatabase`
   - Deberías ver 10 tablas creadas

## Opción 2: Ejecutar desde línea de comandos

### Desde terminal/cmd:

```bash
# Windows
mysql -u root -p < database_init.sql

# Linux/Mac
mysql -u root -p < database_init.sql
```

Cuando te pida la contraseña, introduce la de tu usuario MySQL root.

## Estructura de Tablas Creadas

| Tabla | Descripción |
|-------|-------------|
| `account` | Cuentas bancarias (con campo visible) |
| `transaction` | Transacciones únicas (con es_transferencia) |
| `adjustment` | Ajustes de reconciliación |
| `fixed_expense` | Gastos/ingresos recurrentes (con es_transferencia) |
| `mortgage` | Hipotecas y préstamos |
| `mortgage_interest` | Períodos de interés de hipotecas |
| `holding_plan` | Planes de inversión (carteras) |
| `holding` | Activos en cartera (acciones, ETFs, criptos) |
| `holding_purchase` | Historial de compras de activos |
| `simulation_variables` | Variables para simulación de saldos |

## Configurar la Aplicación

Después de crear la base de datos, configura el archivo `.env`:

```env
DATABASE_URL=mysql+pymysql://root:tu_contraseña@localhost/MMFDatabase
DATE_FORMAT=dd/MM/yyyy
```

**Importante:** Reemplaza `tu_contraseña` con tu contraseña real de MySQL.

## Datos de Ejemplo (Opcional)

El script incluye una línea comentada para insertar una cuenta de ejemplo. 

Para usarla, descomenta esta línea en `database_init.sql`:

```sql
-- INSERT INTO account (nombre, saldo_inicial, visible) VALUES ('Cuenta Corriente', 1000.00, 1);
```

Y vuelve a ejecutar solo esa línea en phpMyAdmin.

## Verificación

Para verificar que todo se creó correctamente, ejecuta en phpMyAdmin:

```sql
USE MMFDatabase;
SHOW TABLES;
```

Deberías ver 10 tablas listadas.

## Solución de Problemas

### Error: "Access denied"
**Solución:** Verifica usuario y contraseña de MySQL.

### Error: "Database already exists"
**Solución:** Si quieres recrear la base de datos desde cero:
```sql
DROP DATABASE MMFDatabase;
```
Luego ejecuta `database_init.sql` nuevamente.

### Error: "Unknown column type"
**Solución:** Asegúrate de usar MySQL 5.7+ o MariaDB 10.2+.

### Caracteres especiales no se ven bien
**Solución:** El script ya usa `utf8mb4`, asegúrate de que tu conexión también use UTF-8.

## Siguientes Pasos

1. ✅ Base de datos creada
2. Configurar archivo `.env` con la URL de conexión
3. Ejecutar `python main.py` para iniciar la aplicación
4. La primera vez, usa el botón "Config" para verificar la conexión
5. Ir a "Admin" para crear tus primeras cuentas

## Migraciones Adicionales (Ya incluidas en database_init.sql)

El script `database_init.sql` ya incluye todas las migraciones:
- ✅ Campo `visible` en tabla `account`
- ✅ Campo `es_transferencia` en `transaction` y `fixed_expense`
- ✅ Tabla `simulation_variables`

No es necesario ejecutar los scripts de migración individuales si usas `database_init.sql`.

## Respaldo

Para hacer un respaldo de tu base de datos:

```bash
mysqldump -u root -p MMFDatabase > backup_finanzas.sql
```

Para restaurar:

```bash
mysql -u root -p MMFDatabase < backup_finanzas.sql
```

## Soporte

Si encuentras problemas, verifica:
1. Versión de MySQL/MariaDB (mínimo 5.7/10.2)
2. Permisos del usuario de base de datos
3. Que el servicio MySQL esté ejecutándose
4. Logs de error de MySQL en caso de fallos
