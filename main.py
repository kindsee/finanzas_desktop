# --- inicio: parche para ejecución desde dist en Windows (pyinstaller --onedir / --onefile) ---
import os, sys

# base_dir: carpeta donde está el exe cuando está congelado (frozen). 
# - con --onefile existe sys._MEIPASS
# - con --onedir y ejecución desde dist, sys.executable apunta al exe dentro de la carpeta dist
if getattr(sys, "frozen", False):
    # onefile -> sys._MEIPASS, onedir -> dirname(sys.executable)
    base_dir = getattr(sys, "_MEIPASS", None) or os.path.dirname(sys.executable)
else:
    # modo desarrollo: carpeta del archivo actual
    base_dir = os.path.dirname(os.path.abspath(__file__))

# Forzar working directory a la carpeta del exe (evita depender del "Start in")
try:
    os.chdir(base_dir)
except Exception:
    pass

# Hacer que .env se cargue desde la carpeta del exe (si usas python-dotenv)
from dotenv import load_dotenv
load_dotenv(os.path.join(base_dir, ".env"))

# Asegurar que Windows puede localizar las DLLs y plugins Qt incluidos por PyInstaller.
# Añadir base_dir y posibles subcarpetas a PATH (Windows)
if os.name == "nt":
    p = os.environ.get("PATH", "")
    candidates = [
        base_dir,
        os.path.join(base_dir, "PySide6"),
        os.path.join(base_dir, "PySide6", "plugins"),
        os.path.join(base_dir, "PySide6", "plugins", "platforms"),
        os.path.join(base_dir, "platforms"),
    ]
    for c in candidates:
        if c and os.path.isdir(c) and c not in p:
            p = c + os.pathsep + p
    os.environ["PATH"] = p

# Forzar a Qt a usar la carpeta platforms dentro de la distribución
qt_plugins = os.path.join(base_dir, "PySide6", "plugins", "platforms")
if not os.path.isdir(qt_plugins):
    # PyInstaller a veces coloca plugins en 'platforms' directamente
    alt = os.path.join(base_dir, "platforms")
    if os.path.isdir(alt):
        qt_plugins = alt

if os.path.isdir(qt_plugins):
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = qt_plugins

# Añadir base_dir al sys.path para imports relativos si es necesario
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)
# --- fin parche ---

# main.py
import sys
import csv
from datetime import date, timedelta, datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QCalendarWidget, QSizePolicy, QScrollArea, QFrame, QDialog, QTableWidget,
    QTableWidgetItem, QFileDialog, QMessageBox,QComboBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import math
import matplotlib.dates as mdates

from database import db
from models.account import Account
from models.adjustment import Adjustment
from models.transaction import Transaction
from models.fixed_expense import FixedExpense

from ui.admin_ui import AdminWindow
from ui.dashboard_widget import DashboardWidget

import os
from dotenv import load_dotenv, set_key, dotenv_values

# Importar la versión de reconciler adaptada al entorno de escritorio
# (la que definimos antes: calcular_balance_cuenta(session, cuenta_id, fecha_objetivo))
from utils.reconciler import calcular_balance_cuenta,calcular_detalle_cuenta

from decimal import InvalidOperation
import io
import traceback

# Función helper para obtener formato de fecha desde configuración
def get_date_format():
    """Retorna el formato de fecha configurado en .env o 'dd/MM/yyyy' por defecto"""
    formato = os.environ.get("DATE_FORMAT", "dd/MM/yyyy").strip()
    if not formato:
        formato = "dd/MM/yyyy"
    return formato

def date_to_string(fecha_obj, formato=None):
    """Convierte un objeto date a string usando el formato configurado"""
    if formato is None:
        formato = get_date_format()
    
    if not isinstance(fecha_obj, (date, datetime)):
        return str(fecha_obj)
    
    # Convertir formato Qt/Python a formato strftime
    # dd/MM/yyyy -> %d/%m/%Y
    # MM/dd/yyyy -> %m/%d/%Y
    # yyyy-MM-dd -> %Y-%m-%d
    formato_py = formato.replace('dd', '%d').replace('MM', '%m').replace('yyyy', '%Y').replace('yy', '%y')
    
    if hasattr(fecha_obj, 'date'):
        fecha_obj = fecha_obj.date()
    
    return fecha_obj.strftime(formato_py)

def get_matplotlib_date_format():
    """Convierte el formato de fecha configurado a formato matplotlib strftime"""
    formato = get_date_format()
    # Convertir formato Qt/Python a formato strftime para matplotlib
    # dd/MM/yyyy -> %d/%m/%Y
    # MM/dd/yyyy -> %m/%d/%Y
    # yyyy-MM-dd -> %Y-%m-%d
    formato_py = formato.replace('dd', '%d').replace('MM', '%m').replace('yyyy', '%Y').replace('yy', '%y')
    return formato_py

# Inicializa DB (usa DATABASE_URL en .env o el que hayas configurado)
db.init_app()

# --------------------------
# Helper: calcular serie de saldos (igual que tu dashboard web)
# --------------------------
def generar_fechas_rango(fecha_obj: date):
    fechas = []
    # 8 semanas antes
    for i in range(8, 0, -1):
        fechas.append(fecha_obj - timedelta(weeks=i))
    fechas.append(fecha_obj)
    # 4 semanas después
    for i in range(1, 5):
        fechas.append(fecha_obj + timedelta(weeks=i))
    return fechas

# Función para obtener la serie de saldos de una cuenta usando el reconciler
def obtener_serie_saldos(session, cuenta, fecha_obj: date):
    fechas = generar_fechas_rango(fecha_obj)
    saldos = []
     # saldo inicial a la primera fecha del rango
    saldo_inicial = Decimal(str(calcular_balance_cuenta(session, cuenta.id, fechas[0]) or 0))
    saldo_parcial = saldo_inicial

    # iteramos fechas
    for f in fechas:
        # sumar movimientos fijos/transacciones/ajustes del día exacto f
        movimientos, _ = calcular_detalle_cuenta(session, cuenta.id, f)  # devuelve todos hasta f
        # obtener el saldo para ese día
        saldo_f = Decimal(str(movimientos[-1]['saldo'])) if movimientos else saldo_parcial
        saldos.append(float(saldo_f))
    return fechas, saldos

# --------------------------
# Función de auditoría (detalle acumulado)
# Reproduce paso a paso saldo_inicial + ajustes + transacciones + fijos
# Devuelve lista de eventos ordenados (fecha, tipo, concepto, importe, saldo_parcial)
# --------------------------
def calcular_detalle_acumulado(session, cuenta_id: int, fecha_inicio: date, fecha_fin: date):
    """
    Devuelve lista de dicts: {'fecha', 'tipo', 'concepto', 'importe', 'saldo'}
    Calcula acumulado desde fecha_inicio hasta fecha_fin (inclusive).
    """
    # Obtener cuenta y saldo inicial
    cuenta = session.get(Account, cuenta_id)
    if not cuenta:
        raise ValueError(f"Cuenta {cuenta_id} no encontrada")

    saldo = Decimal(str(cuenta.saldo_inicial or 0))
    eventos = []

    # 1) Gastos fijos: generar eventos en el rango
    fijos = session.query(FixedExpense).filter(
        FixedExpense.cuenta_id == cuenta_id,
        FixedExpense.fecha_inicio <= fecha_fin,
        (FixedExpense.fecha_fin == None) | (FixedExpense.fecha_fin >= fecha_inicio)
    ).all()

    for f in fijos:
        ocurrencia = f.fecha_inicio  # start desde fecha original
        fin_fijo = f.fecha_fin if f.fecha_fin and f.fecha_fin < fecha_fin else fecha_fin
        
        while ocurrencia <= fin_fijo:
            if fecha_inicio <= ocurrencia <= fecha_fin:  # solo eventos dentro del rango
                eventos.append({
                    'fecha': ocurrencia,
                    'tipo': 'fijo',
                    'concepto': f.descripcion,
                    'importe': Decimal(str(f.monto)),
                    'es_transferencia': getattr(f, 'es_transferencia', 0)
                })
            
            # calcular siguiente ocurrencia según frecuencia
            if f.frecuencia == 'semanal':
                ocurrencia += timedelta(weeks=1)
            elif f.frecuencia == 'mensual':
                ocurrencia += relativedelta(months=1)
            elif f.frecuencia == 'trimestral':
                ocurrencia += relativedelta(months=3)
            elif f.frecuencia == 'semestral':
                ocurrencia += relativedelta(months=6)
            elif f.frecuencia == 'anual':
                ocurrencia += relativedelta(years=1)
            else:
                break

    # 2) Transacciones puntuales en rango
    trans = session.query(Transaction).filter(
        Transaction.cuenta_id == cuenta_id,
        Transaction.fecha >= fecha_inicio,
        Transaction.fecha <= fecha_fin
    ).order_by(Transaction.fecha, Transaction.id).all()
    for t in trans:
        eventos.append({
            'fecha': t.fecha,
            'tipo': 'puntual',
            'concepto': t.descripcion,
            'importe': Decimal(str(t.monto)),
            'es_transferencia': getattr(t, 'es_transferencia', 0)
        })

    # 3) Ajustes en rango
    ajustes = session.query(Adjustment).filter(
        Adjustment.cuenta_id == cuenta_id,
        Adjustment.fecha >= fecha_inicio,
        Adjustment.fecha <= fecha_fin
    ).order_by(Adjustment.fecha, Adjustment.id).all()
    for a in ajustes:
        eventos.append({
            'fecha': a.fecha,
            'tipo': 'ajuste',
            'concepto': a.descripcion or 'Ajuste',
            'importe': Decimal(str(a.monto_ajuste)),
            'es_transferencia': 0  # Los ajustes no son transferencias
        })

    # Ordenar eventos por fecha
    eventos.sort(key=lambda e: (e['fecha'], 0 if e['tipo']=='fijo' else 1))

    # Calcular saldo parcial por evento
    detalle = []
    # Saldo inicial: balance ANTES del primer día del rango (fecha_inicio - 1 día)
    fecha_anterior = fecha_inicio - timedelta(days=1)
    saldo_inicial = Decimal(str(calcular_balance_cuenta(session, cuenta_id, fecha_anterior) or 0))
    saldo_parcial = saldo_inicial

    for e in eventos:
        saldo_parcial += e['importe']
        detalle.append({
            'fecha': e['fecha'],
            'tipo': e['tipo'],
            'concepto': e['concepto'],
            'importe': float(e['importe']),
            'saldo': float(saldo_parcial),
            'es_transferencia': e.get('es_transferencia', 0)
        })

    return {
        'saldo_inicial': float(saldo_inicial),
        'detalle': detalle,
        'saldo_final': float(saldo_parcial)
    }
class ConfigDialog(QDialog):
    """
    Diálogo pequeño para editar DATABASE_URL, formato de fecha y probar conexión.
    Devuelve aceptado() si la nueva configuración se aplicó correctamente.
    """
    def __init__(self, parent=None, current_url: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Configuración")
        self.resize(800, 600)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.input_dburl = QLineEdit(current_url or os.environ.get("DATABASE_URL", ""))
        form.addRow("DATABASE_URL:", self.input_dburl)
        
        # Campo para formato de fecha
        self.combo_date_format = QComboBox()
        self.combo_date_format.addItem("dd/MM/yyyy", "dd/MM/yyyy")
        self.combo_date_format.addItem("MM/dd/yyyy", "MM/dd/yyyy")
        self.combo_date_format.addItem("yyyy-MM-dd", "yyyy-MM-dd")
        self.combo_date_format.addItem("dd-MM-yyyy", "dd-MM-yyyy")
        self.combo_date_format.addItem("MM-dd-yyyy", "MM-dd-yyyy")
        
        # Seleccionar formato actual
        current_format = os.environ.get("DATE_FORMAT", "dd/MM/yyyy")
        index = self.combo_date_format.findData(current_format)
        if index >= 0:
            self.combo_date_format.setCurrentIndex(index)
        
        form.addRow("Formato de fecha:", self.combo_date_format)
        
        # Label de ejemplo
        ejemplo_fecha = date.today()
        self.lbl_ejemplo = QLabel()
        self._update_ejemplo()
        form.addRow("Ejemplo:", self.lbl_ejemplo)
        self.combo_date_format.currentIndexChanged.connect(self._update_ejemplo)

        self.lbl_status = QLabel("")  # para mensajes de estado
        layout.addLayout(form)
        layout.addWidget(self.lbl_status)

        botones = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.on_save)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

        self._saved = False
    
    def _update_ejemplo(self):
        """Actualiza el label de ejemplo con el formato seleccionado"""
        formato = self.combo_date_format.currentData()
        ejemplo_fecha = date.today()
        try:
            ejemplo_str = date_to_string(ejemplo_fecha, formato)
            self.lbl_ejemplo.setText(f"Hoy: {ejemplo_str}")
        except:
            self.lbl_ejemplo.setText("(formato inválido)")

    def on_save(self):
        new_url = self.input_dburl.text().strip()
        
        # Verificar si solo se está cambiando el formato de fecha
        current_url = os.environ.get("DATABASE_URL", "")
        solo_formato = (not new_url or new_url == current_url)
        
        if not new_url and not current_url:
            self.lbl_status.setText("Introduce una DATABASE_URL válida.")
            return
        
        # Si hay nueva URL, probar conexión
        if new_url and new_url != current_url:
            # intentamos inicializar engine localmente para probar la conexión
            from database import db as _db
            try:
                _db.init_app(new_url)
                ok = _db.check_connection(timeout_seconds=5)
            except Exception as e:
                ok = False
                self.lbl_status.setText(f"Error probando conexión: {e}")

            if not ok:
                self.lbl_status.setText("No se pudo conectar con esa URL. Revisa credenciales/host.")
                return
        
        # si ok -> persistir en .env
        try:
            # escribir en .env (crea si no existe)
            env_path = os.path.join(os.getcwd(), ".env")
            load_dotenv(env_path)
            
            # Guardar DATABASE_URL solo si cambió
            if new_url and new_url != current_url:
                set_key(env_path, "DATABASE_URL", new_url)
                # opcional: desactivar echo
                set_key(env_path, "DB_ECHO", os.environ.get("DB_ECHO", "False"))
            
            # Siempre guardar formato de fecha
            date_format = self.combo_date_format.currentData()
            set_key(env_path, "DATE_FORMAT", date_format)
            os.environ["DATE_FORMAT"] = date_format  # actualizar en memoria también
            
        except Exception as e:
            # no crítico, avisamos pero aceptamos
            self.lbl_status.setText(f"Configuración guardada pero hubo un error al escribir .env: {e}")
            self._saved = True
            self.accept()
            return

        self._saved = True
        self.accept()

    def saved(self):
        return self._saved
# --------------------------
# UI: ventana principal
# --------------------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Finanzas Desktop")
        self.resize(1280, 1024)

        self.selected_account_id = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # Header spacer
        header = QWidget()
        header.setFixedHeight(6)
        main_layout.addWidget(header)

        # --- Zona central: calendario y panel derecho (botones verticales centrados) ---
        center_widget = QWidget()
        center_widget.setFixedHeight(260)
        center_layout = QHBoxLayout(center_widget)
        center_layout.setContentsMargins(8, 8, 8, 8)
        center_layout.setSpacing(12)

        # Calendario (centrado)
        self.calendar = QCalendarWidget()
        self.calendar.setSelectedDate(date.today())
        self.calendar.setGridVisible(True)
        self.calendar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        center_layout.addWidget(self.calendar, stretch=1)

        # Panel derecho con botones verticales, centrado verticalmente
        right_widget = QWidget()
        right_widget.setFixedWidth(210)
        right_v = QVBoxLayout(right_widget)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(8)
        right_v.setAlignment(Qt.AlignVCenter)

        # Botones (6) + Auditoría
        self.btn_config = QPushButton("⚙️ Config")
        self.btn_admin = QPushButton("✎ Admin")
        self.btn_cons = QPushButton("📊 Consolidación")
        self.btn_dash = QPushButton("🖥 Dashboard")
        self.btn_import = QPushButton("🔁 Importar")
        self.btn_audit = QPushButton("🔍 Auditoría")  # abre diálogo de auditoría

        for b in (self.btn_config, self.btn_admin, self.btn_cons, self.btn_dash, self.btn_import, self.btn_audit):
            b.setFixedWidth(190)
            b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            right_v.addWidget(b)

        center_layout.addWidget(right_widget, alignment=Qt.AlignVCenter)
        main_layout.addWidget(center_widget)

        # Conectar auditoría
        self.btn_audit.clicked.connect(self.on_audit_clicked)
        self.btn_admin.clicked.connect(self.open_admin)
        # Conectar con Dashboard
        self.btn_dash.clicked.connect(self.open_dashboard)
        #conectar consolidacion
        self.btn_cons.clicked.connect(self.on_consolidation_clicked)
        #conectar config
        self.btn_config.clicked.connect(self.on_config_clicked)
         #conectar importar
        self.btn_import.clicked.connect(self.on_import_clicked)
        # --- Línea de cuentas (centradas) ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.accounts_layout = QHBoxLayout(container)
        self.accounts_layout.setSpacing(12)
        self.accounts_layout.setContentsMargins(12, 8, 12, 8)
        self.accounts_layout.setAlignment(Qt.AlignHCenter)
        self.load_accounts_buttons(self.accounts_layout)
        scroll.setWidget(container)
        scroll.setFixedHeight(120)
        main_layout.addWidget(scroll)

        # --- Gráfico ---
        self.figure = Figure(figsize=(8, 4))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.canvas, stretch=1)

        # Botón recalc/refresh para recalcular series (útil si cambian datos)
        btn_refresh = QPushButton("Recalcular gráfico")
        btn_refresh.clicked.connect(self.recalcular_grafico)
        main_layout.addWidget(btn_refresh, alignment=Qt.AlignRight)

    def load_accounts_buttons(self, layout):
        # limpia layout
        while layout.count():
            it = layout.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

        from database import db as _db

        # Intentamos init sin forzar la conexión
        try:
            _db.init_app()
        except Exception:
            pass

        # Comprobamos si la BD responde
        try:
            connected = _db.check_connection()
        except Exception:
            connected = False

        # Si no hay conexión, mostramos placeholder (y guardamos referencia)
        if not connected:
            widget = QFrame()
            widget.setFrameShape(QFrame.StyledPanel)
            widget.setFixedSize(420, 80)
            vbox = QVBoxLayout(widget)
            vbox.setContentsMargins(6, 6, 6, 6)
            vbox.setSpacing(6)

            lbl = QLabel("Base de datos inaccesible o no configurada.\nPulsa 'Config' para establecer la conexión.")
            lbl.setWordWrap(True)
            lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            btn_conf = QPushButton("Abrir Configuración")
            btn_conf.clicked.connect(self.on_config_clicked if hasattr(self, "on_config_clicked") else lambda: None)

            vbox.addWidget(lbl)
            vbox.addWidget(btn_conf, alignment=Qt.AlignRight)
            layout.addWidget(widget)

            # Guarda la referencia para poder eliminarla si la conexión se establece posteriormente
            self.db_placeholder_widget = widget
            return

        # Si está conectada, eliminamos placeholder si existía
        try:
            if hasattr(self, "db_placeholder_widget") and self.db_placeholder_widget is not None:
                try:
                    layout.removeWidget(self.db_placeholder_widget)
                    self.db_placeholder_widget.deleteLater()
                except Exception:
                    pass
                self.db_placeholder_widget = None
        except Exception:
            pass

        # Abrimos UNA sesión y consultamos cuentas
        session = _db.session()
        try:
            cuentas = session.query(Account).order_by(Account.id).all()
        except Exception as e:
            print("Error cargando cuentas:", e)
            try:
                session.close()
            except Exception:
                pass
            widget = QFrame()
            widget.setFrameShape(QFrame.StyledPanel)
            widget.setFixedSize(420, 80)
            vbox = QVBoxLayout(widget)
            vbox.setContentsMargins(6, 6, 6, 6)
            lbl = QLabel(f"No se pudo obtener la lista de cuentas ({e}). Pulsa 'Config' para revisar conexión.")
            lbl.setWordWrap(True)
            btn_conf = QPushButton("Abrir Configuración")
            btn_conf.clicked.connect(self.on_config_clicked if hasattr(self, "on_config_clicked") else lambda: None)
            vbox.addWidget(lbl)
            vbox.addWidget(btn_conf, alignment=Qt.AlignRight)
            layout.addWidget(widget)
            return

        # Recorremos las cuentas y calculamos saldo usando la MISMA sesión.
        for c in cuentas:
            widget = QFrame()
            widget.setFrameShape(QFrame.StyledPanel)
            widget.setFixedSize(160, 80)
            vbox = QVBoxLayout(widget)
            vbox.setContentsMargins(6, 6, 6, 6)
            vbox.setSpacing(4)

            lbl_nombre = QLabel(f"{c.nombre}")
            lbl_nombre.setAlignment(Qt.AlignCenter)
            lbl_nombre.setStyleSheet("font-weight: bold;")

            fecha_hoy = date.today()
            try:
                result = calcular_detalle_cuenta(session, c.id, fecha_hoy)
                if isinstance(result, dict):
                    saldo_actual = result.get("saldo_final", result.get("saldo", getattr(c, "saldo_inicial", 0.0)))
                elif isinstance(result, tuple) and len(result) == 2:
                    movimientos, saldo_actual = result
                else:
                    try:
                        movimientos = list(result)
                        saldo_actual = getattr(c, "saldo_inicial", 0.0)
                    except Exception:
                        saldo_actual = getattr(c, "saldo_inicial", 0.0)
            except Exception as e:
                print(f"Error calculando saldo para cuenta {c.id}: {e}")
                saldo_actual = getattr(c, "saldo_inicial", 0.0)

            lbl_saldo = QLabel(f"{float(saldo_actual):.2f} €")
            lbl_saldo.setAlignment(Qt.AlignCenter)

            vbox.addWidget(lbl_nombre)
            vbox.addWidget(lbl_saldo)

            # captura cid correctamente para evitar cierre sobre la variable de bucle
            widget.mousePressEvent = lambda ev, _cid=c.id: self.on_account_click(_cid)
            layout.addWidget(widget)

        try:
            session.close()
        except Exception:
            pass
    def open_admin(self):
        self.admin_window = AdminWindow()
        self.admin_window.show()
    def open_dashboard(self):
        self.dashboard = DashboardWidget()
        self.dashboard.show()

    def on_account_click(self, cuenta_id):
        # Al hacer click en cuenta, actualizamos selección y dibujamos su gráfico
        self.selected_account_id = cuenta_id
        self.dibujar_grafico_cuenta(cuenta_id)

    def dibujar_grafico_cuenta(self, cuenta_id):
        session = db.session()
        try:
            cuenta = session.get(Account, cuenta_id)
            if not cuenta:
                return
            fecha_obj = self.calendar.selectedDate().toPython() if hasattr(self.calendar, "selectedDate") else date.today()
            fechas, saldos = obtener_serie_saldos(session, cuenta, fecha_obj)
        finally:
            session.close()

        # ploteamos
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        # preparar x (fechas) y y (saldos)
        x = [f for f in fechas]
        y = [s if s is not None else float('nan') for s in saldos]

        ax.plot(x, y, marker='o', linestyle='-')

        # Formato del eje X para fechas y rotación - usar formato configurado
        ax.xaxis.set_major_formatter(mdates.DateFormatter(get_matplotlib_date_format()))
        self.figure.autofmt_xdate(rotation=30)

        ax.set_title(f"Saldo - {cuenta.nombre} (semana)")
        ax.set_xlabel("Fecha")
        ax.set_ylabel("Saldo (€)")
        ax.grid(True)

        # --- Anotaciones: mostrar el valor encima de cada punto ---
        # Para evitar montones de texto en series muy largas, usar 'label_every' (1 = todos,
        # 2 = cada 2ª etiqueta, etc.). Ajusta según necesites.
        label_every = 1
        max_labels = 40  # si hay más puntos que este umbral, aumenta label_every automáticamente
        n_points = len(x)
        if n_points > max_labels:
            label_every = max(1, n_points // max_labels)

        for idx, (xx, yy) in enumerate(zip(x, y)):
            # saltar NaN y controlar frecuencia de etiquetas
            if idx % label_every != 0:
                continue
            try:
                if yy is None or (isinstance(yy, float) and math.isnan(yy)):
                    continue
            except Exception:
                pass

            # small offset above the point
            ax.annotate(f"{yy:.2f}", xy=(xx, yy), xytext=(0, 6),
                        textcoords="offset points", ha='center', fontsize=8)

        self.canvas.draw()

    def recalcular_grafico(self):
        # Si hay cuenta seleccionada, recalcular su serie; si no, recalcular primer cuenta
        session = db.session()
        try:
            if self.selected_account_id:
                target_id = self.selected_account_id
            else:
                first = session.query(Account).order_by(Account.id).first()
                target_id = first.id if first else None
        finally:
            session.close()

        if target_id:
            self.dibujar_grafico_cuenta(target_id)
        else:
            QMessageBox.information(self, "Info", "No hay cuentas para graficar.")

    # ---------------------------
    # Auditoría: abre diálogo con detalle acumulado y posibilidad de exportar CSV
    # ---------------------------
    def on_audit_clicked(self):
        if not self.selected_account_id:
            QMessageBox.information(self, "Auditoría", "Selecciona primero una cuenta (haz click en la casilla de la cuenta).")
            return

        # Rango: tomamos ±8 semanas por defecto (igual que en web)
        fecha_central = self.calendar.selectedDate().toPython()
        fecha_inicio = fecha_central - timedelta(weeks=8)
        fecha_fin = fecha_central + timedelta(weeks=4)

        session = db.session()
        try:
            # llamar a la función que tengas; puede llamarse calcular_detalle_acumulado o calcular_detalle_cuenta
            # adaptamos la recepción de la respuesta para varios formatos:
            result = None
            try:
                result = calcular_detalle_acumulado(session, self.selected_account_id, fecha_inicio, fecha_fin)
            except TypeError:
                # quizá tu función tiene firma (session, cuenta_id, fecha_objetivo) -> en ese caso llamamos con fecha_fin
                result = calcular_detalle_cuenta(session, self.selected_account_id, fecha_fin)

            # Normalizar resultado a un dict con claves: 'detalle', 'saldo_inicial', 'saldo_final'
            report = None
            if isinstance(result, dict):
                # ya es un dict — comprobamos claves mínimas
                report = result
            elif isinstance(result, tuple) and len(result) == 2:
                # (movimientos, saldo_final) o (movimientos, saldo)
                movimientos, saldo_final = result
                # construir report: calcular saldo_inicial a partir de movimientos si está
                saldo_inicial = None
                if movimientos and isinstance(movimientos, list):
                    first = movimientos[0]
                    saldo_inicial = first.get("saldo") if isinstance(first, dict) else None
                if saldo_inicial is None:
                    # fallback: usar saldo inicial de la cuenta
                    acc = session.get(Account, self.selected_account_id)
                    from decimal import Decimal
                    saldo_inicial = float(Decimal(str(getattr(acc, "saldo_inicial", 0))))
                report = {
                    "detalle": movimientos,
                    "saldo_inicial": float(saldo_inicial),
                    "saldo_final": float(saldo_final)
                }
            else:
                # formato inesperado: intentar convertir iterables
                try:
                    movimientos = list(result)
                    # si al menos hay una estructura intentamos usarla
                    report = {"detalle": movimientos, "saldo_inicial": 0.0, "saldo_final": 0.0}
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Respuesta inesperada del cálculo: {e}")
                    return

        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo calcular la auditoría: {e}")
            print("DEBUG on_audit error:", e)
            return
        finally:
            session.close()

        dlg = AuditDialog(self, report)
        dlg.exec()
    #Definición para la consolidación
    def on_consolidation_clicked(self):
        if not self.selected_account_id:
            QMessageBox.information(self, "Consolidación", "Selecciona primero una cuenta.")
            return

        # abrir diálogo
        fecha_def = self.calendar.selectedDate().toPython() if hasattr(self.calendar, "selectedDate") else date.today()
        dlg = ConsolidationDialog(self, fecha_default=fecha_def, saldo_default=0.0)
        if dlg.exec() != QDialog.Accepted:
            return

        vals = dlg.get_values()
        fecha = vals["fecha"]
        saldo_obj = vals["saldo_objetivo"]
        descripcion = vals["descripcion"]

        session = db.session()
        try:
            from utils.reconciler import reconciliar_cuenta
            ajuste = reconciliar_cuenta(session, self.selected_account_id, fecha, saldo_obj, descripcion)
            session.commit()
            QMessageBox.information(self, "Consolidación", f"Ajuste creado: {float(ajuste.monto_ajuste):.2f} € en {ajuste.fecha}")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo crear el ajuste de consolidación: {e}")
            print("DEBUG: error en reconciliar:", e)
        finally:
            session.close()

        # refrescar UI: botón saldo, gráfico y auditoría si quieres
        try:
            self.load_accounts_buttons(self.accounts_layout)  # recarga los botones con saldos actualizados
        except Exception:
            pass
        self.recalcular_grafico()
        # opcional: abrir el diálogo de auditoría en el rango centrado en la fecha de reconciliación
        # seleccionar cuenta y mostrar auditoría:
        self.selected_account_id = self.selected_account_id
        self.calendar.setSelectedDate(QDate(fecha.year, fecha.month, fecha.day))
        # llamar a auditoría para ver efecto
        self.on_audit_clicked()
    def on_config_clicked(self):
        # Abrir diálogo (tu ConfigDialog puede aceptar args si ya lo tienes así)
        try:
            dlg = ConfigDialog(self)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No pude abrir ConfigDialog: {e}")
            return

        # Si el usuario cancela, salimos
        if dlg.exec() != QDialog.Accepted:
            return

        # Primero intentamos guardar usando métodos habituales del diálogo (si existen)
        new_url = None
        try:
            # si el diálogo implementa save(), úsalo (guardará en .env o similar)
            if hasattr(dlg, "save") and callable(dlg.save):
                dlg.save()
            # si implementa saved() (boolean), comprobamos
            if hasattr(dlg, "saved") and callable(dlg.saved) and not dlg.saved():
                QMessageBox.warning(self, "Config", "No se guardó la configuración.")
                return
            # intenta obtener la URL (método recomendado)
            if hasattr(dlg, "get_database_url") and callable(dlg.get_database_url):
                new_url = dlg.get_database_url().strip()
        except Exception as e:
            QMessageBox.warning(self, "Config", f"Error guardando configuración: {e}")
            # intentar continuar intentando leer la URL manualmente abajo

        # fallback: si no obtuvimos new_url, intentar leer un atributo directo
        if not new_url:
            if hasattr(dlg, "database_url"):
                new_url = getattr(dlg, "database_url")
            if not new_url:
                # No hay nueva URL, pero puede que solo se haya cambiado el formato de fecha
                # Intentar usar la URL existente en .env
                new_url = os.environ.get("DATABASE_URL", "").strip()
                if not new_url:
                    QMessageBox.warning(self, "Config", "No se encontró DATABASE_URL. Configura la conexión a la base de datos.")
                    return
                # Si hay URL en .env, continuar sin mostrar error
        
        # Reinicializar base de datos con la URL
        try:
            from database import db as _db
            _db.init_app(new_url)
            ok, err = _db.check_connection()
        except Exception as e:
            ok = False
            err = str(e)
        
        if not ok:
            QMessageBox.critical(self, "No se pudo conectar", f"No se pudo conectar con la DB: {err}")
            return
        
        # Conexión OK -> limpiar sesiones antiguas y recargar cuentas en caliente
        try:
            if getattr(_db, "SessionLocal", None) is not None and hasattr(_db.SessionLocal, "remove"):
                try:
                    _db.SessionLocal.remove()
                except Exception:
                    pass
        except Exception:
            pass

        # Quitar placeholder si existe
        try:
            if hasattr(self, "db_placeholder_widget") and self.db_placeholder_widget is not None:
                try:
                    self.accounts_layout.removeWidget(self.db_placeholder_widget)
                except Exception:
                    pass
                try:
                    self.db_placeholder_widget.deleteLater()
                except Exception:
                    pass
                self.db_placeholder_widget = None
        except Exception:
            pass

        # Recargar botones/cuentas
        try:
            self.load_accounts_buttons(self.accounts_layout)
        except Exception as e:
            QMessageBox.warning(self, "Advertencia", f"Conexión establecida pero fallo al cargar cuentas: {e}")
            print("DEBUG load_accounts_buttons error:", e)

        QMessageBox.information(self, "Conectado", "Conexión OK. Configuración guardada correctamente.")
    
    def on_import_clicked(self):
        """
        Importa movimientos desde un fichero TSV/CSV con columnas:
        Fecha    Descripcion    Monto
        Detecta delimitador automáticamente y gestiona comillas/negativos.
        """
        from decimal import Decimal, InvalidOperation
        import csv, traceback
        from datetime import date

        # Aviso de formato antes de seleccionar cuenta
        example_text = (
                        "El fichero CSV/TSV debe tener las siguientes columnas:\n"
                        "Fecha\tDescripcion\tMonto\n"
                        "Ejemplo:\n"
                        "2025-08-15\tIngreso Bizum\t134.98\n"
                        "2025-09-05\tDevolucion Bizum\t134.98\n"
                        "2025-10-30\tTransferencia\t1225.24\n"
                        "2025-10-31\tTransferencia de vuelta\t-1225.24\n\n"
                        "Separador: Tabulador o coma. Las comillas son opcionales.\n"
                        "La primera fila puede ser cabecera con nombres de columna."
                    )
        QMessageBox.information(self, "Formato esperado del fichero", example_text)
        
        # 1) comprobar cuenta seleccionada (o pedir al usuario que la elija)
        cuenta_id = getattr(self, "selected_account_id", None)
        session = db.session()
        try:
            cuentas = session.query(Account).order_by(Account.id).all()
        except Exception as e:
            session.close()
            QMessageBox.critical(self, "Error", f"No se pudieron cargar cuentas: {e}")
            return
        finally:
            session.close()

        if not cuenta_id:
            dlg_sel = SelectAccountDialog(self, cuentas=[(c.id, c.nombre) for c in cuentas])
            if dlg_sel.exec() != QDialog.Accepted:
                
                return
            cuenta_id = dlg_sel.get_values()["cuenta_id"]
            if not cuenta_id:
                QMessageBox.warning(self, "Cuenta no seleccionada", "No se seleccionó ninguna cuenta.")
                return

        # 2) elegir fichero
        fname, _ = QFileDialog.getOpenFileName(self, "Seleccionar fichero (TSV/CSV)", "", "All files (*);;CSV files (*.csv *.txt *.tsv)")
        if not fname:
            return

        # 3) leer contenido y detectar delimitador con csv.Sniffer
        try:
            with open(fname, "r", encoding="utf-8") as fh:
                sample = fh.read(8192)
                fh.seek(0)
                # intentar detectar dialecto (limitamos delimiters probables)
                sniffer = csv.Sniffer()
                try:
                    dialect = sniffer.sniff(sample, delimiters=[",", "\t", ";"])
                    delimiter = dialect.delimiter
                except Exception:
                    # fallback heurístico: si hay tabs en sample preferimos tab
                    delimiter = "\t" if "\t" in sample else ","
                reader = csv.reader(fh, delimiter=delimiter)
                rows = list(reader)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo leer el fichero: {e}")
            return

        if not rows:
            QMessageBox.information(self, "Importar", "El fichero está vacío.")
            return

        # 4) decidir si hay cabecera (buscar palabras clave)
        header = [c.strip().lower() for c in rows[0]]
        has_header = False
        if any(h in header for h in ("fecha", "date")) and any(h in header for h in ("monto", "importe", "amount", "value")):
            has_header = True

        start_idx = 1 if has_header else 0

        # util para parsear fechas simples
        def _try_parse_date(s):
            if s is None:
                return None
            s = str(s).strip().strip('"').strip("'")
            if not s:
                return None
            from datetime import datetime
            fmts = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d")
            for f in fmts:
                try:
                    return datetime.strptime(s, f).date()
                except Exception:
                    pass
            # fallback: intentar split por /
            try:
                parts = [p for p in s.replace("-", "/").split("/") if p]
                if len(parts) == 3:
                    d, m, y = parts
                    if len(y) == 4:
                        # suponer formato día/mes/año o año/mes/día si el primero tiene 4 dígitos
                        if len(d) == 4:
                            return datetime(int(d), int(m), int(y)).date()
                        return datetime(int(y), int(m), int(d)).date()
            except Exception:
                pass
            return None

        inserted = 0
        skipped = 0
        errors = []
        session2 = db.session()
        try:
            for idx, row in enumerate(rows[start_idx:], start=start_idx + 1):
                # normalizar celdas: quitar comillas externas y espacios
                try:
                    cells = [c.strip().strip('"').strip("'") for c in row]
                    # coger primeras 3 columnas si hay más
                    if len(cells) == 0 or (len(cells) == 1 and cells[0] == ""):
                        skipped += 1
                        errors.append((idx, "fila vacía", row))
                        continue

                    # Intentar mapear: Fecha, Descripcion, Monto
                    if len(cells) >= 3:
                        raw_fecha, raw_desc, raw_monto = cells[0], cells[1], cells[2]
                    elif len(cells) == 2:
                        raw_fecha, raw_desc = cells[0], cells[1]
                        raw_monto = ""
                    else:
                        # Una sola columna -> intentar separar por espacios (poco fiable)
                        skipped += 1
                        errors.append((idx, "fila con menos de 2 columnas", row))
                        continue

                    fecha = _try_parse_date(raw_fecha)
                    if fecha is None:
                        # si fecha vacía usar hoy, si no reconocida marcar error
                        if raw_fecha == "":
                            from datetime import date as _d
                            fecha = _d.today()
                        else:
                            skipped += 1
                            errors.append((idx, f"fecha no reconocida: {raw_fecha}", row))
                            continue

                    descripcion = raw_desc or ""

                    # parseo importe: aceptar coma decimal, paréntesis para negativo, signos
                    monto_s = raw_monto.replace(",", ".").strip()
                    if monto_s.startswith("(") and monto_s.endswith(")"):
                        monto_s = "-" + monto_s[1:-1]

                    try:
                        monto_dec = Decimal(monto_s) if monto_s != "" else Decimal("0")
                    except (InvalidOperation, ValueError):
                        # intentar float fallback
                        try:
                            monto_dec = Decimal(str(float(monto_s)))
                        except Exception:
                            skipped += 1
                            errors.append((idx, f"importe no parseable: {raw_monto}", row))
                            continue

                    # insertar transacción
                    trx = Transaction(cuenta_id=int(cuenta_id), fecha=fecha, descripcion=descripcion, monto=monto_dec)
                    session2.add(trx)
                    inserted += 1

                except Exception as ex_row:
                    skipped += 1
                    errors.append((idx, f"excepción: {ex_row}", row))
                    print("DEBUG import fila error:", traceback.format_exc())

            # commit si se añadieron filas
            if inserted > 0:
                session2.commit()
            else:
                session2.rollback()

            # guardar fichero de errores si hay
            summary = f"Import finalizado.\nFilas leídas: {len(rows)-start_idx}\nInsertadas: {inserted}\nIgnoradas: {skipped}"
            if errors:
                err_fname = fname + ".errors.csv"
                try:
                    with open(err_fname, "w", newline='', encoding='utf-8') as ef:
                        w = csv.writer(ef)
                        w.writerow(["fila", "motivo", "contenido"])
                        for fila, motivo, contenido in errors:
                            w.writerow([fila, motivo, str(contenido)])
                    summary += f"\nDetalle errores en: {err_fname}"
                except Exception as e:
                    summary += f"\nNo se pudo guardar fichero errores: {e}"

            QMessageBox.information(self, "Importar movimientos", summary)

        except Exception as e:
            session2.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo importar: {e}\n\n{traceback.format_exc()}")
        finally:
            session2.close()

        # refrescar UI
        try:
            self.recalcular_grafico()
        except Exception:
            pass
        try:
            self.refresh_table()
        except Exception:
            pass
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDateEdit, QDoubleSpinBox,
    QLineEdit, QDialogButtonBox, QLabel
)
from PySide6.QtCore import QDate

class ConsolidationDialog(QDialog):
    """
    Diálogo para introducir fecha y saldo objetivo de la consolidación (reconciliación).
    Devuelve: dict {'fecha': date, 'saldo_objetivo': float, 'descripcion': str}
    """
    def __init__(self, parent=None, fecha_default=None, saldo_default=0.0, descripcion_default="Consolidación / Reconciliación"):
        super().__init__(parent)
        self.setWindowTitle("Consolidación / Reconciliación")
        self.resize(360, 160)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # fecha
        self.input_fecha = QDateEdit()
        self.input_fecha.setCalendarPopup(True)
        if fecha_default:
            self.input_fecha.setDate(QDate(fecha_default.year, fecha_default.month, fecha_default.day))
        else:
            self.input_fecha.setDate(QDate.currentDate())

        # saldo objetivo
        self.input_saldo = QDoubleSpinBox()
        self.input_saldo.setRange(-10_000_000_000, 10_000_000_000)
        self.input_saldo.setDecimals(2)
        self.input_saldo.setValue(float(saldo_default))

        # descripcion
        self.input_desc = QLineEdit(descripcion_default)

        form.addRow("Fecha reconciliación:", self.input_fecha)
        form.addRow("Saldo objetivo (€):", self.input_saldo)
        form.addRow("Descripción:", self.input_desc)

        layout.addLayout(form)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def get_values(self):
        return {
            "fecha": self.input_fecha.date().toPython(),
            "saldo_objetivo": float(self.input_saldo.value()),
            "descripcion": self.input_desc.text().strip() or "Consolidación / Reconciliación"
        }

class AuditDialog(QDialog):
            def __init__(self, parent, report):
                super().__init__(parent)
                self.setWindowTitle("Auditoría de cuenta")
                self.resize(1000, 800)
                self.report = report

                layout = QVBoxLayout(self)

                # Asegurar claves en report
                saldo_inicial = report.get("saldo_inicial", 0.0)
                saldo_final = report.get("saldo_final", 0.0)
                # si report['detalle'] no existe, intentar otras claves
                detalle = report.get("detalle") or report.get("movimientos") or report.get("rows") or []

                lbl = QLabel(f"Saldo inicial: {float(saldo_inicial):.2f} €    -    Saldo final: {float(saldo_final):.2f} €")
                layout.addWidget(lbl)

                # Normalizar cada fila del detalle para que tenga: fecha, tipo, concepto, importe, saldo
                norm_rows = []
                for r in detalle:
                    # r puede ser dict o un ORM object; intentamos extraer de forma defensiva
                    if isinstance(r, dict):
                        fecha = r.get("fecha") or r.get("date") or r.get("fecha_inicio") or ""
                        tipo = r.get("tipo") or r.get("kind") or ""
                        concepto = r.get("descripcion") or r.get("concepto") or r.get("desc") or ""
                        # importe puede estar en 'monto' o 'importe'
                        importe = r.get("monto") if r.get("monto") is not None else r.get("importe", 0.0)
                        saldo = r.get("saldo") if r.get("saldo") is not None else r.get("saldo_parcial", 0.0)
                    else:
                        # intento de extraer atributos de ORM
                        fecha = getattr(r, "fecha", "")
                        tipo = getattr(r, "tipo", "")
                        concepto = getattr(r, "descripcion", "") or getattr(r, "concepto", "")
                        importe = getattr(r, "monto", None)
                        if importe is None:
                            importe = getattr(r, "importe", 0.0)
                        saldo = getattr(r, "saldo", None)
                    # garantizar tipos numéricos
                    try:
                        importe_f = float(importe) if importe is not None else 0.0
                    except Exception:
                        importe_f = 0.0
                    try:
                        saldo_f = float(saldo) if saldo is not None else None
                    except Exception:
                        saldo_f = None

                    # Extraer es_transferencia
                    if isinstance(r, dict):
                        es_transf = r.get("es_transferencia", 0)
                    else:
                        es_transf = getattr(r, "es_transferencia", 0)
                    
                    norm_rows.append({
                        "fecha": fecha,
                        "tipo": tipo,
                        "concepto": str(concepto) if concepto is not None else "",
                        "importe": importe_f,
                        "saldo": saldo_f,
                        "es_transferencia": es_transf
                    })

                # Construir tabla
                table = QTableWidget(len(norm_rows), 5)
                table.setHorizontalHeaderLabels(["Fecha", "Tipo", "Concepto", "Importe", "Saldo parcial"])
                
                # Fecha de hoy para comparar
                hoy = date.today()
                
                for i, e in enumerate(norm_rows):
                    # fecha -> string usando formato configurado
                    fecha_obj = e["fecha"]
                    if isinstance(fecha_obj, str):
                        try:
                            fecha_obj = datetime.strptime(fecha_obj, "%Y-%m-%d").date()
                        except:
                            pass
                    
                    fecha_txt = date_to_string(fecha_obj)
                    
                    # Crear items
                    item_fecha = QTableWidgetItem(fecha_txt)
                    item_tipo = QTableWidgetItem(str(e["tipo"]))
                    item_concepto = QTableWidgetItem(str(e["concepto"]))
                    item_importe = QTableWidgetItem(f"{e['importe']:.2f}")
                    item_saldo = QTableWidgetItem(f"{e['saldo']:.2f}" if e['saldo'] is not None else "")
                    
                    # Diferenciar visualmente movimientos futuros vs pasados
                    es_futuro = False
                    try:
                        if hasattr(fecha_obj, "date"):
                            fecha_obj = fecha_obj.date()
                        if isinstance(fecha_obj, date) and fecha_obj > hoy:
                            es_futuro = True
                    except:
                        pass
                    
                    # Aplicar color de fondo: azul claro para futuros, blanco para pasados
                    if es_futuro:
                        color_fondo = QColor(220, 235, 255)  # azul muy claro
                        item_fecha.setBackground(color_fondo)
                        item_tipo.setBackground(color_fondo)
                        item_concepto.setBackground(color_fondo)
                        item_importe.setBackground(color_fondo)
                        item_saldo.setBackground(color_fondo)
                    
                    # Aplicar color rojo y negrita a transferencias
                    # El campo es_transferencia ya está en e directamente
                    es_transferencia = bool(e.get("es_transferencia", 0))
                    
                    if es_transferencia:
                        color_rojo = QColor(200, 0, 0)  # rojo
                        fuente_negrita = item_fecha.font()
                        fuente_negrita.setBold(True)
                        
                        # Aplicar color rojo y negrita a todos los campos
                        for item in [item_fecha, item_tipo, item_concepto, item_importe, item_saldo]:
                            item.setForeground(color_rojo)
                            item.setFont(fuente_negrita)
                    
                    table.setItem(i, 0, item_fecha)
                    table.setItem(i, 1, item_tipo)
                    table.setItem(i, 2, item_concepto)
                    table.setItem(i, 3, item_importe)
                    table.setItem(i, 4, item_saldo)
                
                table.resizeColumnsToContents()
                layout.addWidget(table)

                btns_layout = QHBoxLayout()
                btn_export = QPushButton("Exportar CSV")
                btn_close = QPushButton("Cerrar")
                btns_layout.addStretch()
                btns_layout.addWidget(btn_export)
                btns_layout.addWidget(btn_close)
                layout.addLayout(btns_layout)

                btn_export.clicked.connect(lambda: self.export_csv(norm_rows))
                btn_close.clicked.connect(self.close)

def export_csv(self, detalle):
                fname, _ = QFileDialog.getSaveFileName(self, "Guardar CSV", f"auditoria_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "CSV files (*.csv)")
                if not fname:
                    return
                try:
                    with open(fname, "w", newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(["fecha", "tipo", "concepto", "importe", "saldo"])
                        for e in detalle:
                            writer.writerow([
                                e['fecha'].isoformat() if hasattr(e['fecha'], "isoformat") else str(e['fecha']),
                                e['tipo'],
                                e['concepto'],
                                f"{e['importe']:.2f}",
                                f"{e['saldo']:.2f}" if e['saldo'] is not None else ""
                            ])
                    QMessageBox.information(self, "Exportado", f"CSV guardado en:\n{fname}")
                except Exception as exc:
                    QMessageBox.critical(self, "Error", f"No se pudo guardar CSV: {exc}")                

class SelectAccountDialog(QDialog):
    """
    Si no hay cuenta seleccionada, mostramos este diálogo para elegir una cuenta.
    Devuelve {'cuenta_id': id} en get_values()
    """
    def __init__(self, parent=None, cuentas=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar cuenta para importar")
        self.resize(420, 120)
        layout = QFormLayout(self)

        self.combo_cuenta = QComboBox()
        if cuentas:
            for c in cuentas:
                if isinstance(c, (tuple, list)):
                    cid = c[0]
                    name = c[1] if len(c) > 1 else str(cid)
                else:
                    cid = getattr(c, "id", None)
                    name = getattr(c, "nombre", str(cid))
                self.combo_cuenta.addItem(f"{name} ({cid})", cid)

        layout.addRow("Cuenta:", self.combo_cuenta)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addRow(bb)

    def get_values(self):
        return {"cuenta_id": self.combo_cuenta.currentData()}
    
def _try_parse_date(s: str):
    """Intentos habituales de parseo; devolver date o None."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    from datetime import datetime, date
    fmts = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d")
    for f in fmts:
        try:
            return datetime.strptime(s, f).date()
        except Exception:
            pass
    # último recurso: intentar parseo flexible (día,mes, año separados por espacios)
    try:
        parts = [p for p in s.replace("-", "/").replace(".", "/").split("/") if p]
        if len(parts) == 3:
            d, m, y = parts
            # heurística: si el primero tiene 4 dígitos, es año
            if len(d) == 4:
                return date(int(d), int(m), int(y))
            else:
                return date(int(y), int(m), int(d)) if len(y) == 4 else date(int(y), int(m), int(d))
    except Exception:
        pass
    return None



# --------------------------
# main
# --------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
