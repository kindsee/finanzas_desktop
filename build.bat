@echo off
REM Script para compilar Finanzas Desktop
REM Ejecutar desde el directorio raíz del proyecto

echo ================================================
echo   Compilando Finanzas Desktop
echo ================================================
echo.

REM Verificar que existe el archivo .spec
if not exist "finanzas_desktop.spec" (
    echo ERROR: No se encuentra finanzas_desktop.spec
    pause
    exit /b 1
)

REM Compilar con PyInstaller
echo Ejecutando PyInstaller...
".venv\Scripts\pyinstaller.exe" finanzas_desktop.spec --clean

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: La compilacion fallo
    pause
    exit /b 1
)

REM Copiar archivo .env
echo.
echo Copiando archivo .env...
if exist ".env" (
    copy /Y ".env" "dist\finanzas_desktop\.env"
) else (
    echo ADVERTENCIA: No se encuentra .env - recuerda configurar la base de datos
)

echo.
echo ================================================
echo   COMPILACION COMPLETADA
echo ================================================
echo.
echo El ejecutable esta en: dist\finanzas_desktop\finanzas_desktop.exe
echo.
echo Para ejecutar:
echo   cd dist\finanzas_desktop
echo   finanzas_desktop.exe
echo.
pause
