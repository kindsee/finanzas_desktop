# ui/dashboard_widget.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QFrame, QMessageBox
)
from PySide6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates

from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy import func
import os

from database import db
from models.transaction import Transaction
from models.holding import Holding, HoldingPurchase

import numpy as np
from dateutil.relativedelta import relativedelta
from models.adjustment import Adjustment
from models.fixed_expense import FixedExpense
from utils.reconciler import obtener_gastos_top, calcular_detalle_cuenta

# Función helper para obtener formato matplotlib desde configuración
def get_matplotlib_date_format():
    """Convierte el formato de fecha configurado a formato matplotlib strftime"""
    formato = os.environ.get("DATE_FORMAT", "dd/MM/yyyy").strip()
    if not formato:
        formato = "dd/MM/yyyy"
    # Convertir formato Qt/Python a formato strftime para matplotlib
    formato_py = formato.replace('dd', '%d').replace('MM', '%m').replace('yyyy', '%Y').replace('yy', '%y')
    return formato_py

# Hipoteca models (opcional)
try:
    from models.mortgage import Mortgage, MortgagePeriod
except Exception:
    Mortgage = None
    MortgagePeriod = None
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel
)
from PySide6.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt


from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel
from PySide6.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import numpy as np

from models.account import Account
from utils.reconciler import calcular_detalle_acumulado
from models.mortgage import Mortgage
from models.mortgage_period import MortgagePeriod
import pandas as pd
from sqlalchemy import select, or_, func

class DashboardWidget(QWidget):
    
    def __init__(self, parent=None):
            super().__init__(parent)

            # Fecha actual
            hoy = date.today()

            # Primer y último día del mes actual
            primer_dia_mes = hoy.replace(day=1)
            
            # Primer día del mes anterior
            if primer_dia_mes.month == 1:
                self._primer_dia_prev = primer_dia_mes.replace(year=primer_dia_mes.year - 1, month=12)
            else:
                self._primer_dia_prev = primer_dia_mes.replace(month=primer_dia_mes.month - 1)

            # Último día del mes anterior
            self._ultimo_dia_prev = primer_dia_mes - timedelta(days=1)

            # Construir la UI (solo widgets y canvases)
            self._build_ui()

            # Refrescar datos (hace consultas y dibuja)
            self.refresh()

    def _build_ui(self):
        # Layout principal con QStackedLayout para superponer widgets
        from PySide6.QtWidgets import QStackedLayout, QGridLayout
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Contenedor para el grid de gráficos
        grid_container = QWidget()
        grid = QGridLayout(grid_container)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setSpacing(10)
        
        # --- Crear figuras y canvases (tamaños iguales) ---
        self.fig_bars = Figure(figsize=(6, 4))
        self.canvas_bars = FigureCanvas(self.fig_bars)
        self.canvas_bars.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.fig_loans = Figure(figsize=(6, 4))
        self.canvas_loans = FigureCanvas(self.fig_loans)
        self.canvas_loans.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.fig_top_gastos = Figure(figsize=(6, 4))
        self.canvas_top_gastos = FigureCanvas(self.fig_top_gastos)
        self.canvas_top_gastos.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.fig_invest = Figure(figsize=(6, 4))
        self.canvas_invest = FigureCanvas(self.fig_invest)
        self.canvas_invest.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Layout 2x2: todas las celdas con tamaño igual
        # Fila 0: Ingresos/Gastos | Préstamos
        # Fila 1: Top Gastos (tarta) | Inversiones
        grid.addWidget(self.canvas_bars, 0, 0)
        grid.addWidget(self.canvas_loans, 0, 1)
        grid.addWidget(self.canvas_top_gastos, 1, 0)
        grid.addWidget(self.canvas_invest, 1, 1)
        
        # Igualar proporciones
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        
        main_layout.addWidget(grid_container)
        
        # Score superpuesto en el centro con semi-transparencia
        self.score_container = QWidget(self)
        self.score_container.setAutoFillBackground(False)
        # Aplicar semi-transparencia al contenedor
        self.score_container.setWindowOpacity(0.85)
        
        score_layout = QVBoxLayout(self.score_container)
        score_layout.setContentsMargins(0, 0, 0, 0)
        
        self.score_big = QLabel("--")
        self.score_big.setAlignment(Qt.AlignCenter)
        self.score_big.setStyleSheet("""
            QLabel {
                background-color: rgba(46, 134, 193, 200);
                color: white;
                border-radius: 100px;
                font-size: 72px;
                font-weight: bold;
                min-width: 200px;
                min-height: 200px;
                max-width: 200px;
                max-height: 200px;
                border: 8px solid #1a5a8a;
            }
        """)
        
        self.score_label = QLabel("Score Financiero")
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setStyleSheet("""
            font-size: 16px; 
            font-weight: bold; 
            color: white;
            background-color: #2E86C1;
            padding: 5px 15px;
            border-radius: 10px;
        """)
        
        score_layout.addStretch()
        score_layout.addWidget(self.score_big, alignment=Qt.AlignCenter)
        score_layout.addSpacing(10)
        score_layout.addWidget(self.score_label, alignment=Qt.AlignCenter)
        score_layout.addStretch()
        
        # Hacer que el score se muestre sobre todo
        self.score_container.raise_()
        
        # Guardar referencia al grid
        self.grid = grid
    
    def showEvent(self, event):
        """Posiciona el score cuando se muestra el widget"""
        super().showEvent(event)
        self._position_score()
    
    def _position_score(self):
        """Posiciona el score en el centro de la ventana"""
        if hasattr(self, 'score_container'):
            # Obtener el tamaño del widget principal
            parent_rect = self.rect()
            score_width = 220
            score_height = 280
            
            # Centrar
            x = (parent_rect.width() - score_width) // 2
            y = (parent_rect.height() - score_height) // 2
            
            self.score_container.setGeometry(x, y, score_width, score_height)
    
    def resizeEvent(self, event):
        """Reposicionar el score cuando se redimensiona la ventana"""
        super().resizeEvent(event)
        self._position_score()

    # -------------------------
    # REFRESH
    # -------------------------
    def refresh(self):
        session = db.session()
        try:
            self._draw_barras_mes_anterior(session)  # ahora recibe session
            self._fill_top_gastos(session)         # dibuja tarta (usa ejemplo si no hay datos)
            rows = getattr(self, "_loans_rows_cached", None)
            self._draw_loans_barras(rows=rows)     # préstamos
            self._draw_investments(session)        # inversiones
            self._update_score(session)            # actualiza score
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error dashboard", f"Error refrescando dashboard: {e}")
            print("DEBUG dashboard refresh error:", e)
        finally:
            session.close()

    # -------------------------
    # INGRESOS vs GASTOS (barras)
    # -------------------------
    def _draw_barras_mes_anterior(self, session=None):
        """
        Dibuja barras de ingresos vs gastos del mes anterior.
        Si session es None, usa datos de ejemplo.
        """
        datos = None
        
        # Si tenemos session, calcular datos reales
        if session is not None:
            try:
                from models.account import Account
                from datetime import date, timedelta
                
                # Calcular fecha inicio y fin del mes anterior
                hoy = date.today()
                primer_dia_mes_actual = hoy.replace(day=1)
                ultimo_dia_mes_anterior = primer_dia_mes_actual - timedelta(days=1)
                primer_dia_mes_anterior = ultimo_dia_mes_anterior.replace(day=1)
                
                # Obtener todas las cuentas
                cuentas = session.query(Account).all()
                datos = []
                
                for cuenta in cuentas:
                    # Calcular ingresos y gastos usando la función helper
                    ing, gas, _ = _sum_ingresos_gastos_directo(
                        session, 
                        cuenta.id, 
                        primer_dia_mes_anterior, 
                        ultimo_dia_mes_anterior
                    )
                    
                    # Solo añadir si hay movimiento
                    if ing > 0 or gas > 0:
                        datos.append({
                            "id": cuenta.id,
                            "nombre": cuenta.nombre,
                            "ingresos": ing,
                            "gastos": gas
                        })
            except Exception as e:
                print(f"⚠️ Error calculando datos reales para barras: {e}")
                datos = None
        
        # Si no hay datos reales, usar ejemplo
        if datos is None:
            datos = [
                {"id": 1, "nombre": "Caja Sur 5701", "ingresos": 3690.62, "gastos": 3207.08},
                {"id": 2, "nombre": "DB 5330", "ingresos": 40.14, "gastos": 508.52},
                {"id": 3, "nombre": "ING Nomina 7338", "ingresos": 243.93, "gastos": 423.31},
                {"id": 4, "nombre": "ING Compartidos 8712", "ingresos": 0.0, "gastos": 3.0},
                {"id": 5, "nombre": "ING Naranja 4533", "ingresos": 0.0, "gastos": 7924.33},
                {"id": 6, "nombre": "Caja Rural 4324", "ingresos": 5482.07, "gastos": 2238.32},
            ]

        # Filtrar cuentas con ambos valores en 0
        datos = [d for d in datos if float(d.get("ingresos", 0.0) or 0.0) > 0 or float(d.get("gastos", 0.0) or 0.0) > 0]
        
        nombres = [d["nombre"] for d in datos]
        ingresos = [float(d.get("ingresos", 0.0) or 0.0) for d in datos]
        gastos = [float(d.get("gastos", 0.0) or 0.0) for d in datos]

        fig = self.fig_bars
        fig.clear()
        ax = fig.add_subplot(111)

        x = np.arange(len(nombres))
        width = 0.35

        bars_ing = ax.bar(x - width/2, ingresos, width, label="Ingresos")
        bars_gas = ax.bar(x + width/2, gastos, width, label="Gastos")

        ax.set_ylabel("Euros")
        ax.set_title("Ingresos y Gastos — mes anterior")
        ax.set_xticks(x)
        ax.set_xticklabels(nombres, rotation=25, ha="right")
        ax.legend()
        ax.grid(axis="y", linestyle="--", alpha=0.4)

        # anotar valores encima de las barras
        for rects in (bars_ing, bars_gas):
            for rect in rects:
                h = rect.get_height()
                if h:
                    ax.annotate(f'{h:.2f}', xy=(rect.get_x() + rect.get_width() / 2, h),
                                xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)

        fig.tight_layout()
        try:
            self.canvas_bars.draw_idle()
        except Exception as e:
            print("⚠️ Error dibujando canvas_bars:", e)

    # -------------------------
    # TOP GASTOS: pie (sin tabla)
    # -------------------------
    def _fill_top_gastos(self, session=None, data=None):
        """
        Dibuja la tarta de top gastos. Si data es None y session está disponible,
        usa obtener_gastos_top para datos reales (que excluye transferencias).
        """
        try:
            if data is None and session is not None:
                try:
                    from models.account import Account
                    
                    # Obtener todas las cuentas y calcular top gastos
                    cuentas = session.query(Account).all()
                    gastos_agregados = {}
                    
                    for cuenta in cuentas:
                        # obtener_gastos_top ya excluye transferencias
                        top = obtener_gastos_top(session, cuenta.id, meses=1, limite=10)
                        for descripcion, total in top:
                            if descripcion in gastos_agregados:
                                gastos_agregados[descripcion] += abs(float(total))
                            else:
                                gastos_agregados[descripcion] = abs(float(total))
                    
                    # Ordenar por mayor gasto
                    if gastos_agregados:
                        gastos_ordenados = sorted(gastos_agregados.items(), key=lambda x: x[1], reverse=True)
                        
                        # Tomar top 5 + agrupar resto como "Otros"
                        if len(gastos_ordenados) > 5:
                            top_5 = gastos_ordenados[:5]
                            otros = sum(val for _, val in gastos_ordenados[5:])
                            data = {desc: val for desc, val in top_5}
                            if otros > 0:
                                data["Otros"] = otros
                        else:
                            data = {desc: val for desc, val in gastos_ordenados}
                except Exception as e:
                    print(f"⚠️ Error calculando top gastos reales: {e}")
                    data = None
            
            if data is None:
                # ejemplo porcentajes
                data = {
                    "Hipotecas/Préstamos": 35.0,
                    "Supermercado": 15.0,
                    "Suministros": 10.0,
                    "Impuestos": 8.0,
                    "Colegio": 7.0,
                    "Otros": 25.0
                }

            labels = list(data.keys())
            sizes = [float(data[k]) for k in labels]
            total = sum(sizes)
            if total == 0:
                labels = ["Sin datos"]
                sizes = [1.0]

            # limpiar figura y dibujar tarta ocupando todo el canvas
            self.fig_top_gastos.clear()
            ax = self.fig_top_gastos.add_subplot(111)

            # dibujar pie completo (no rosquilla)
            wedges, texts, autotexts = ax.pie(
                sizes,
                labels=labels,
                autopct=lambda pct: f"{pct:.0f}%",
                startangle=90,
                textprops={'fontsize': 9, 'weight': 'bold'}
            )

            # mejor contraste: autotexts en blanco cuando es necesario
            for at in autotexts:
                at.set_color('white')
                at.set_fontsize(8)

            ax.set_aspect('equal')
            ax.axis('off')  # quitamos ejes para que ocupe todo el espacio

            self.fig_top_gastos.tight_layout()
            try:
                self.canvas_top_gastos.draw_idle()
            except Exception as e:
                print("⚠️ Error dibujando canvas_top_gastos:", e)

        except Exception as e:
            print("❌ Error en _fill_top_gastos:", e)

    # -------------------------
    # PRÉSTAMOS: barras horizontales
    # -------------------------
    def _draw_loans_barras(self, rows=None):
        """
        Dibuja préstamos en self.fig_loans / self.canvas_loans.
        rows: lista de tuplas (nombre, amortizado, pendiente). Si None, usa ejemplo.
        Muestra barras proporcionales (% amortizado vs pendiente) con valores dentro.
        """
        if rows is None or len(rows) == 0:
            rows = [
                ("Préstamo 0", 38950.0, 108000.0 - 38950.0),
                ("Préstamo 1", 35260.0, 278900.0 - 35260.0),
                ("Préstamo 2", 825.0, 253900.0 - 825.0),
                ("Préstamo 3", 49.9, 2994.0 - 49.9),
            ]

        # Preparar datos
        nombres = [r[0] for r in rows]
        amortizado = [float(r[1] or 0.0) for r in rows]
        pendiente = [float(r[2] or 0.0) for r in rows]

        # Usar la figura/canvas creados en _build_ui
        if not hasattr(self, "fig_loans") or not hasattr(self, "canvas_loans"):
            print("⚠️ fig_loans/canvas_loans no existen — crea en _build_ui")
            return

        self.fig_loans.set_size_inches(10, 6)  # ancho=10, alto=6 pulgadas
        self.fig_loans.clear()
        ax = self.fig_loans.add_subplot(111)

        import numpy as np
        y = np.arange(len(nombres))
        height = 0.6

        # Calcular porcentajes para visualización proporcional
        totales = [am + pend for am, pend in zip(amortizado, pendiente)]
        porcentajes_amortizado = [(am / total * 100) if total > 0 else 0 for am, total in zip(amortizado, totales)]
        porcentajes_pendiente = [(pend / total * 100) if total > 0 else 0 for pend, total in zip(pendiente, totales)]

        # Dibujar barras proporcionales (de 0 a 100%)
        ax.barh(y, porcentajes_amortizado, height=height, color="#27AE60", label="Amortizado", edgecolor='white', linewidth=1)
        ax.barh(y, porcentajes_pendiente, height=height, left=porcentajes_amortizado, color="#C0392B", label="Pendiente", edgecolor='white', linewidth=1)

        # Anotaciones: valores absolutos dentro de las barras
        for i, (am, pend, p_am, p_pend, total) in enumerate(zip(amortizado, pendiente, porcentajes_amortizado, porcentajes_pendiente, totales)):
            # Valor de amortizado dentro de su barra (verde) - solo si es visible (>5%)
            if p_am > 5:
                ax.annotate(f"{am:,.0f}€\n({p_am:.1f}%)", xy=(p_am/2, i), xytext=(0, 0),
                            textcoords="offset points", ha="center", va="center", 
                            color="white", fontsize=8, weight="bold")
            elif am > 0:
                # Si es muy pequeño, ponerlo fuera a la izquierda
                ax.annotate(f"{am:,.0f}€", xy=(0, i), xytext=(-5, 0),
                            textcoords="offset points", ha="right", va="center", 
                            color="#27AE60", fontsize=7, weight="bold")
            
            # Valor de pendiente dentro de su barra (roja) - solo si es visible (>5%)
            if p_pend > 5:
                ax.annotate(f"{pend:,.0f}€\n({p_pend:.1f}%)", xy=(p_am + p_pend/2, i), xytext=(0, 0),
                            textcoords="offset points", ha="center", va="center", 
                            color="white", fontsize=8, weight="bold")
            elif pend > 0:
                # Si es muy pequeño, ponerlo fuera a la derecha
                ax.annotate(f"{pend:,.0f}€", xy=(100, i), xytext=(5, 0),
                            textcoords="offset points", ha="left", va="center", 
                            color="#C0392B", fontsize=7, weight="bold")
            
            # Total al final de cada barra (fuera)
            ax.annotate(f"Total: {total:,.0f}€", xy=(100, i), xytext=(8, 0),
                       textcoords="offset points", ha="left", va="center", 
                       color="black", fontsize=8,
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.8, edgecolor='gray'))

        ax.set_yticks(y)
        ax.set_yticklabels(nombres, fontsize=9)
        ax.invert_yaxis()
        ax.set_xlabel("Porcentaje de amortización (%)", fontsize=10)
        ax.set_xlim(0, 115)  # Dar espacio para las etiquetas del total
        ax.set_title("Préstamos — Proporción Amortizado vs Pendiente", fontsize=11, weight='bold')
        ax.legend(loc="lower right")
        ax.grid(axis="x", linestyle="--", alpha=0.4)

        self.fig_loans.tight_layout()
        try:
            self.canvas_loans.draw_idle()
        except Exception as e:
            print("⚠️ Error dibujando canvas_loans:", e)

    # -------------------------
    # INVERSIONES: gráfico de líneas
    # -------------------------
    def _draw_investments(self, session):
        """Dibuja el gráfico de evolución de inversiones"""
        try:
            import matplotlib.dates as mdates
            
            # Obtener todas las compras y sus holdings
            purchases = (
                session.query(HoldingPurchase)
                .join(Holding)
                .order_by(HoldingPurchase.fecha)
                .all()
            )

            if not purchases:
                # Mostrar mensaje si no hay datos
                self.fig_invest.clear()
                ax = self.fig_invest.add_subplot(111)
                ax.text(0.5, 0.5, 'Sin datos de inversiones', 
                       ha='center', va='center', fontsize=14, color='gray')
                ax.axis('off')
                self.canvas_invest.draw_idle()
                return

            # Preparar listas
            fechas = []
            coste_total = []
            valor_actual_total = []

            acumulado_coste = 0
            acumulado_valor = 0

            for p in purchases:
                h = p.holding
                if not h or h.last_price is None:
                    continue

                coste = float(p.cantidad) * float(p.precio_unitario)
                valor_actual = float(p.cantidad) * float(h.last_price)

                acumulado_coste += coste
                acumulado_valor += valor_actual

                fechas.append(p.fecha)
                coste_total.append(acumulado_coste)
                valor_actual_total.append(acumulado_valor)

            if not fechas:
                # Mostrar mensaje si no hay datos válidos
                self.fig_invest.clear()
                ax = self.fig_invest.add_subplot(111)
                ax.text(0.5, 0.5, 'Sin datos válidos', 
                       ha='center', va='center', fontsize=14, color='gray')
                ax.axis('off')
                self.canvas_invest.draw_idle()
                return

            # Convertir a DataFrame
            df = pd.DataFrame({
                "fecha": fechas,
                "coste": coste_total,
                "valor_actual": valor_actual_total
            }).sort_values("fecha")

            # Limpiar y crear figura
            self.fig_invest.clear()
            ax = self.fig_invest.add_subplot(111)
            
            ax.plot(df["fecha"], df["coste"], label="Coste Acumulado", 
                   linewidth=2, color="tab:blue", marker="o")
            ax.plot(df["fecha"], df["valor_actual"], label="Valor Actual", 
                   linewidth=2, color="tab:green", marker="o")

            # Etiquetas con los valores
            # Coste acumulado: debajo del punto
            for x, y in zip(df["fecha"], df["coste"]):
                ax.annotate(f"{y:.0f}€", xy=(x, y), xytext=(0, -12),
                           textcoords="offset points", ha="center", fontsize=8, 
                           color="tab:blue", weight="bold")

            # Valor actual: ARRIBA del punto para evitar superposición
            for x, y in zip(df["fecha"], df["valor_actual"]):
                ax.annotate(f"{y:.0f}€", xy=(x, y), xytext=(0, 10),
                           textcoords="offset points", ha="center", fontsize=8, 
                           color="tab:green", weight="bold")

            # Formato de fecha usando configuración
            ax.xaxis.set_major_formatter(mdates.DateFormatter(get_matplotlib_date_format()))
            self.fig_invest.autofmt_xdate(rotation=30)

            ax.set_title("Evolución de Inversiones")
            ax.set_xlabel("Fecha")
            ax.set_ylabel("Valor (€)")
            ax.legend()
            ax.grid(True, linestyle="--", alpha=0.5)

            self.fig_invest.tight_layout()
            self.canvas_invest.draw_idle()
            
        except Exception as e:
            print(f"⚠️ Error en _draw_investments: {e}")
            import traceback
            traceback.print_exc()

    # -------------------------
    # SCORE FINANCIERO
    # -------------------------
    def _update_score(self, session):
        """Calcula y actualiza el score financiero"""
        try:
            hoy = date.today()

            # 1️⃣ Calcular saldo total real sumando todas las cuentas
            total_cuentas = 0.0
            from sqlalchemy import select
            cuentas = session.scalars(select(Account.id)).all()
            for cuenta_id in cuentas:
                try:
                    _, saldo_final = calcular_detalle_cuenta(session, cuenta_id, hoy)
                    total_cuentas += saldo_final
                except Exception as e_saldo:
                    print(f"⚠️ Error calculando saldo cuenta {cuenta_id}: {e_saldo}")

            # 2️⃣ Total inversiones (valor actual)
            total_inversiones = float(
                session.query(func.coalesce(func.sum(Holding.cantidad * Holding.last_price), 0)).scalar() or 0.0
            )

            # 3️⃣ Total préstamos pendientes
            total_prestamos = 0.0
            prestamos = session.scalars(select(Mortgage)).all()
            for m in prestamos:
                periodo_actual = (
                    session.query(MortgagePeriod)
                    .filter(
                        MortgagePeriod.mortgage_id == m.id,
                        MortgagePeriod.fecha_inicio <= hoy,
                        MortgagePeriod.fecha_fin >= hoy
                    )
                    .first()
                )
                if periodo_actual:
                    pendiente = periodo_actual.capital_fin
                else:
                    pendiente = getattr(m, "capital_inicial", 0.0)
                total_prestamos += float(pendiente)

            # Total valor propiedades
            total_valor_propiedades = float(
                session.query(func.coalesce(func.sum(Mortgage.valor_actual_propiedad), 0)).scalar() or 0.0
            )

            # 4️⃣ Gastos medios últimos 3 meses
            fecha_inicio = hoy - relativedelta(months=3)
            total_gastos = Decimal(0)
            for cuenta_id in cuentas:
                detalle = calcular_detalle_acumulado(session, cuenta_id, fecha_inicio, hoy)
                total_gastos += abs(Decimal(str(detalle.get("gastos", 0))))
            gasto_mensual = float(total_gastos / 3) if total_gastos > 0 else 1.0

            # 5️⃣ Patrimonio neto
            patrimonio = total_cuentas + total_inversiones + total_valor_propiedades - total_prestamos

            # Normalización y sub-scores
            def normalizar(valor, ideal):
                if ideal == 0:
                    return 0.0
                return max(0.0, min(100.0, (valor / ideal) * 100.0))

            # Liquidez
            liquidez = (total_cuentas / (gasto_mensual * 6)) if gasto_mensual > 0 else 1.0
            liquidez_score = normalizar(liquidez, 1.0)

            # Deuda
            deuda_ratio = (total_prestamos / patrimonio) if patrimonio > 0 else 1.0
            deuda_score = 100.0 - normalizar(deuda_ratio, 0.3)
            deuda_score = max(0.0, min(100.0, deuda_score))

            # Inversión
            inversion_ratio = (total_inversiones / patrimonio) if patrimonio > 0 else 0.0
            inversion_score = normalizar(inversion_ratio, 0.2)

            # Gasto
            gasto_ratio = (gasto_mensual / (patrimonio / 12.0)) if patrimonio > 0 else 1.0
            gasto_score = 100.0 - normalizar(gasto_ratio, 0.8)
            gasto_score = max(0.0, min(100.0, gasto_score))

            # Tendencia (placeholder)
            tendencia_score = 60.0

            # Pesos
            pesos = {
                "liquidez": 0.30,
                "deuda": 0.25,
                "inversion": 0.20,
                "gasto": 0.15,
                "tendencia": 0.10
            }

            score = (
                liquidez_score * pesos["liquidez"] +
                deuda_score * pesos["deuda"] +
                inversion_score * pesos["inversion"] +
                gasto_score * pesos["gasto"] +
                tendencia_score * pesos["tendencia"]
            )

            # Actualizar el widget del score
            if hasattr(self, "score_big"):
                self.score_big.setText(f"{score:.0f}")
                
        except Exception as e:
            print(f"⚠️ Error calculando score financiero: {e}")
            if hasattr(self, "score_big"):
                self.score_big.setText("--")

    # -------------------------
    # SCORE / DEUDA
    # -------------------------
    def _compute_debt_score(self, session):
        total_debt = Decimal("0")
        if Mortgage is not None and MortgagePeriod is not None:
            loans = session.query(Mortgage).all()
            for m in loans:
                inicial = Decimal(str(getattr(m, "capital_inicial", 0) or 0))
                paid = Decimal(str(
                    session.query(func.coalesce(func.sum(MortgagePeriod.amortizacion_total), 0))
                    .filter(MortgagePeriod.mortgage_id == m.id).scalar() or 0
                ))
                pending = max(Decimal("0"), inicial - paid)
                total_debt += pending

        # monthly avg income: últimos 6 meses
        today = date.today()
        start = (today.replace(day=1) - timedelta(days=180)).replace(day=1)
        total_ing = session.query(func.coalesce(func.sum(Transaction.monto), 0)).filter(
            Transaction.fecha >= start,
            Transaction.monto > 0,
            Transaction.es_transferencia == 0  # Excluir transferencias
        ).scalar() or 0

        months = 6
        monthly_avg_income = Decimal(str(total_ing)) / Decimal(str(months)) if months > 0 else Decimal("0.01")

        if monthly_avg_income > 0:
            debt_ratio = (total_debt / (monthly_avg_income * Decimal("12")))
        else:
            debt_ratio = Decimal("0")

        score = float(min(max(debt_ratio * Decimal("100"), Decimal("0")), Decimal("100")))

        # Interpretación textual para label pequeño (derecha arriba)
        if debt_ratio < Decimal("0.2"):
            text_small = f"Bueno ({score:.0f})"
            color = "green"
        elif debt_ratio < Decimal("0.5"):
            text_small = f"Moderado ({score:.0f})"
            color = "orange"
        else:
            text_small = f"Alto ({score:.0f})"
            color = "red"

        # actualiza widgets
        if hasattr(self, "score_top_label"):
            self.score_top_label.setText(text_small)
            self.score_top_label.setStyleSheet(f"font-size:18px; color:{color};")

        if hasattr(self, "score_big"):
            self.score_big.setText(f"{int(score)} / 100")
            self.score_big.setStyleSheet(
                f"background-color: #1E90FF; color: white; font-size:36px; font-weight:bold;"
                f"border-radius: 110px; border: 6px solid #0b61b0; color:{'white'};"
            )


# -------------------------
# Función util (fuera de la clase)
# -------------------------
def _sum_ingresos_gastos_directo(session, cuenta_id, fecha_inicio, fecha_fin):
    ingresos = 0.0
    gastos = 0.0
    n_eventos = 0

    # Transacciones puntuales (excluyendo transferencias)
    try:
        from sqlalchemy import select
        trans = session.execute(
            select(Transaction.monto)
            .where(Transaction.cuenta_id == cuenta_id)
            .where(Transaction.fecha >= fecha_inicio)
            .where(Transaction.fecha <= fecha_fin)
            .where(Transaction.es_transferencia == 0)  # Excluir transferencias
        ).scalars().all()
        for t in trans:
            m = float(t or 0.0)
            if m > 0:
                ingresos += m
            else:
                gastos += abs(m)
            n_eventos += 1
    except Exception as e:
        print("DEBUG trans error:", e)

    # Ajustes
    try:
        from sqlalchemy import select
        adjs = session.execute(
            select(Adjustment.monto_ajuste)
            .where(Adjustment.cuenta_id == cuenta_id)
            .where(Adjustment.fecha >= fecha_inicio)
            .where(Adjustment.fecha <= fecha_fin)
        ).scalars().all()
        for a in adjs:
            m = float(a or 0.0)
            if m > 0:
                ingresos += m
            else:
                gastos += abs(m)
            n_eventos += 1
    except Exception as e:
        print("DEBUG ajustes error:", e)

    # Gastos/ingresos fijos: generar ocurrencias en rango
    try:
        from sqlalchemy import select
        fijos = session.execute(
            select(FixedExpense)
            .where(FixedExpense.cuenta_id == cuenta_id)
            .where(FixedExpense.fecha_inicio <= fecha_fin)
            .where((FixedExpense.fecha_fin == None) | (FixedExpense.fecha_fin >= fecha_inicio))
        ).scalars().all()

        for f in fijos:
            ocurrencia = max(f.fecha_inicio, fecha_inicio)
            fin_fijo = f.fecha_fin if f.fecha_fin and f.fecha_fin < fecha_fin else fecha_fin
            while ocurrencia <= fin_fijo:
                if fecha_inicio <= ocurrencia <= fecha_fin:
                    m = float(f.monto or 0.0)
                    if m > 0:
                        ingresos += m
                    else:
                        gastos += abs(m)
                    n_eventos += 1
                if f.frecuencia == "semanal":
                    ocurrencia += timedelta(weeks=1)
                elif f.frecuencia == "mensual":
                    ocurrencia += relativedelta(months=1)
                elif f.frecuencia == "trimestral":
                    ocurrencia += relativedelta(months=3)
                elif f.frecuencia == "semestral":
                    ocurrencia += relativedelta(months=6)
                elif f.frecuencia == "anual":
                    ocurrencia += relativedelta(years=1)
                else:
                    break
    except Exception as e:
        print("DEBUG fijos error:", e)

    return round(ingresos, 2), round(gastos, 2), n_eventos

def normalizar(valor, ideal, maximo):
    # Escala de 0–100, sin superar 100
    return max(0, min(100, (valor / ideal) * 100)) if valor < ideal else 100