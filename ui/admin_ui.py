# admin_ui.py
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView,
    QFormLayout, QLineEdit, QDateEdit, QDialogButtonBox, QSpinBox, QDoubleSpinBox,QAbstractSpinBox,
    QLineEdit, QTextEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QHBoxLayout, QFrame, QCheckBox
)
from PySide6.QtCore import Qt, QDate
from datetime import date
import os

from database import db
from models.account import Account
from models.transaction import Transaction
from models.adjustment import Adjustment
from models.fixed_expense import FixedExpense
# modelos de préstamo (añade estas líneas junto a los imports de modelos)
from models.mortgage import Mortgage
from models.mortgage_period import MortgagePeriod   # o MortgageInterest si lo nombraste así
from models.holding import HoldingPlan,update_prices_for_all_holdings, Holding,get_value_of_holding,update_price_for_holding

from decimal import Decimal, getcontext, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
# Si en un futuro tienes Loan/LoanModel, puedes importarlo aquí:
# from models.loan import Loan
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from models.holding import Holding
from models.holding import HoldingPlan, HoldingPurchase

# Función helper para configurar formato de fecha en QDateEdit
def setup_date_edit(date_edit):
    """Configura un QDateEdit con el formato de fecha desde .env"""
    formato = os.environ.get("DATE_FORMAT", "dd/MM/yyyy").strip()
    if not formato:
        formato = "dd/MM/yyyy"
    date_edit.setDisplayFormat(formato)
    return date_edit

def format_date_str(fecha_obj):
    """Convierte un objeto date/datetime a string usando formato configurado"""
    if fecha_obj is None:
        return ""
    
    formato = os.environ.get("DATE_FORMAT", "dd/MM/yyyy").strip()
    if not formato:
        formato = "dd/MM/yyyy"
    
    # Convertir formato Qt a formato strftime
    formato_py = formato.replace('dd', '%d').replace('MM', '%m').replace('yyyy', '%Y').replace('yy', '%y')
    
    if hasattr(fecha_obj, 'date'):
        fecha_obj = fecha_obj.date()
    
    try:
        return fecha_obj.strftime(formato_py)
    except:
        return str(fecha_obj)

class AdminWindow(QDialog):
    """Ventana de administración: crear/editar/eliminar entidades."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Administración")
        self.resize(1000, 600)

        main = QVBoxLayout(self)
        top = QHBoxLayout()
        main.addLayout(top)

        # Columna izquierda con botones de acción rápida
        left_col = QVBoxLayout()
        left_col.setSpacing(12)
        btn_new_account = QPushButton("Nueva Cuenta")
        btn_new_loan = QPushButton("Nuevo Préstamo")
        btn_new_tx = QPushButton("Nuevo Gasto/Ingreso")
        btn_new_transfer = QPushButton("Nueva Transferencia")
        #btn_new_income = QPushButton("Nuevo Ingreso")
        btn_new_fixed = QPushButton("Nuevo Gasto/Ingr Recurrente")
        #btn_new_fixed_inc = QPushButton("Nuevo Ingreso Recurrente")
        # después de btn_new_fixed
        btn_new_plan = QPushButton("Nuevo Plan Acciones")
        btn_new_holding = QPushButton("Añadir Holding a Plan")
        btn_new_purchase = QPushButton("Añadir Compra (Holding)")
        for b in (btn_new_account, btn_new_loan, btn_new_tx, btn_new_transfer, btn_new_fixed,btn_new_plan,btn_new_holding,btn_new_purchase):
            b.setFixedWidth(160)
            left_col.addWidget(b)
        left_col.addStretch()
        top.addLayout(left_col)

        # Panel central: selector y tabla
        center = QVBoxLayout()
        top.addLayout(center, stretch=1)

        # Selector de tipo
        row_sel = QHBoxLayout()
        row_sel.addStretch()
        row_sel.addWidget(QLabel("Mostrar:"))
        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems(["Cuentas", "Transacciones", "Préstamos", "Gastos Recurrentes", "Ajustes","Cuadros de Amortización","Planes de Acciones", "Holdings", "Compras"])
        row_sel.addWidget(self.combo_tipo)
        row_sel.addStretch()
        center.addLayout(row_sel)

        # Tabla principal
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Col1", "Col2", "Col3", "Col4", "Col5", "Editar", "Eliminar"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        center.addWidget(self.table)

        # Conexiones
        self.combo_tipo.currentIndexChanged.connect(self.refresh_table)
        btn_new_account.clicked.connect(self.on_new_account)
        btn_new_tx.clicked.connect(lambda: self.on_new_transaction(is_income=False))
        btn_new_transfer.clicked.connect(self.on_new_transfer)
        btn_new_fixed.clicked.connect(lambda: self.on_new_fixed(is_income=False))
        btn_new_loan.clicked.connect(self.on_new_loan)
        btn_new_plan.clicked.connect(lambda: self.on_new_plan())
        btn_new_holding.clicked.connect(lambda: self.on_new_holding())
        btn_new_purchase.clicked.connect(lambda: self.on_new_purchase())
        # cargar datos
        self.refresh_table()

    # -------------------------
    # REFRESH / CARGA DE TABLA
    # -------------------------
    def refresh_table(self):
        tipo = self.combo_tipo.currentText()
        # print(f"DEBUG tipo actual: '{self.combo_tipo.currentText()}'", flush=True)
        session = db.session()
        try:
            if tipo == "Cuentas":
                rows = session.query(Account).order_by(Account.id).all()
                self._fill_accounts(rows)
            elif tipo == "Transacciones":
                rows = session.query(Transaction).order_by(Transaction.fecha.desc(), Transaction.id).limit(500).all()
                self._fill_transactions(rows)
            elif tipo == "Préstamos":
                rows = session.query(Mortgage).order_by(Mortgage.id).limit(500).all()
                # print(f"DEBUG: registros obtenidos = {len(rows)}", flush=True)
                self._fill_mortgages(rows)
            elif tipo == "Gastos Recurrentes":
                rows = session.query(FixedExpense).order_by(FixedExpense.id).all()
                self._fill_fixed(rows)
            elif tipo == "Planes de Acciones":
                try:
                    # actualizar precios para todos los holdings antes de calcular valores
                    update_prices_for_all_holdings(session)

                    holdings = session.query(Holding).order_by(Holding.id).all()

                    # Construimos lista de tuplas:
                    # (id, plan_nombre, ticker, exchange, moneda, cantidad_total, last_price, valor, last_update)
                    rows_with_totals = []
                    for h in holdings:
                        plan_nombre = getattr(h.plan, "nombre", "") if getattr(h, "plan", None) else ""
                        # sumar compras (cantidad total)
                        total_qty = session.query(func.coalesce(func.sum(HoldingPurchase.cantidad), 0)) \
                                        .filter(HoldingPurchase.holding_id == h.id).scalar() or 0
                        last_price = getattr(h, "last_price", None)
                        valor = (float(total_qty) * float(last_price)) if (last_price is not None) else None
                        last_update = getattr(h, "last_update", None)
                        rows_with_totals.append((h.id, plan_nombre, h.ticker or "", h.exchange or "", h.moneda or "",
                                                float(total_qty), last_price, valor, last_update))

                    # Llamar a _fill_holdings UNA SOLA VEZ con la lista completa
                    self._fill_holdings(rows_with_totals)

                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self, "Error", f"No se pudo leer holdings: {e}")
            elif tipo == "Holdings":
                session = db.session()
                try:
                    holdings = (
                        session.query(Holding)
                        .options(joinedload(Holding.purchases), joinedload(Holding.plan))
                        .all()
                    )

                    rows = []
                    for h in holdings:
                        # Nombre del plan (si tiene)
                        plan_nombre = h.plan.nombre if h.plan else ""

                        # Sumar todas las compras asociadas
                        total_qty = sum(p.cantidad for p in (h.purchases or []))

                        # Precio actual (si ya está actualizado)
                        last_price = h.last_price or 0.00

                        # Valor total
                        valor_total = float(total_qty) * float(last_price) if last_price else 0.00

                        rows.append((
                            h.id,
                            plan_nombre,
                            h.ticker or "",
                            h.exchange or "",
                            h.moneda or "",
                            total_qty,
                            last_price,
                            valor_total,
                            h.last_update
                        ))

                    # Rellenar tabla
                    self._fill_holdings(rows)

                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self, "Error", f"No se pudieron cargar los holdings: {e}")
                finally:
                    session.close()
            elif tipo == "Compras":
                # cargamos purchases + holding eager para evitar detached
                purchases = session.query(HoldingPurchase).options(joinedload(HoldingPurchase.holding)).order_by(HoldingPurchase.fecha.desc(), HoldingPurchase.id).all()
                self._fill_purchases(purchases)
            elif tipo == "Ajustes":
                rows = session.query(Adjustment).order_by(Adjustment.fecha.desc()).limit(500).all()
                self._fill_adjustments(rows)
            elif tipo == "Cuadros de Amortización":
                rows = session.query(MortgagePeriod).order_by(MortgagePeriod.mortgage_id,MortgagePeriod.fecha_inicio).limit(500).all()
                # print(f"DEBUG: registros obtenidos = {len(rows)}", flush=True)
                self._fill_mortgage_periods(rows)
            else:
                self.table.setRowCount(0)
        finally:
            session.close()

    def _set_action_buttons(self, row, edit_cb, del_cb):
        # Botón editar
        btn_e = QPushButton("✎")
        btn_e.clicked.connect(lambda _, r=row: edit_cb(r))
        self.table.setCellWidget(row, 8, btn_e)
        # Botón eliminar
        btn_d = QPushButton("🗑")
        btn_d.clicked.connect(lambda _, r=row: del_cb(r))
        self.table.setCellWidget(row, 9, btn_d)

    def _fill_accounts(self, rows):
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre", "Saldo inicial", "—", "—", "—","—","—", "Editar", "Eliminar"])
        self.table.setRowCount(len(rows))
        for i, a in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(a.id)))
            self.table.setItem(i, 1, QTableWidgetItem(a.nombre))
            self.table.setItem(i, 2, QTableWidgetItem(f"{float(a.saldo_inicial):.2f}"))
            self.table.setItem(i, 3, QTableWidgetItem(""))
            self.table.setItem(i, 4, QTableWidgetItem(""))
            self.table.setItem(i, 5, QTableWidgetItem(""))
            self.table.setItem(i, 6, QTableWidgetItem(""))
            self.table.setItem(i, 7, QTableWidgetItem(""))
            self._set_action_buttons(i,
                                     edit_cb=lambda r, aid=a.id: self.on_edit_account(aid),
                                     del_cb=lambda r, aid=a.id: self.on_delete_account(aid))

    def _fill_transactions(self, rows):
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(["ID", "Fecha", "Cuenta", "Concepto", "Importe", "Transf.", "-", "-", "Editar", "Eliminar"])
        self.table.setRowCount(len(rows))
        
        # Ajustar anchos de columna para mejor visualización
        self.table.setColumnWidth(0, 40)   # ID más estrecho
        self.table.setColumnWidth(1, 90)   # Fecha
        self.table.setColumnWidth(2, 100)  # Cuenta
        self.table.setColumnWidth(3, 250)  # Concepto más ancho
        self.table.setColumnWidth(4, 80)   # Importe
        self.table.setColumnWidth(5, 60)   # Transf
        self.table.setColumnWidth(6, 5)    # columna vacía mínima
        self.table.setColumnWidth(7, 5)    # columna vacía mínima
        
        for i, t in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(t.id)))
            self.table.setItem(i, 1, QTableWidgetItem(format_date_str(t.fecha)))
            # intentar obtener nombre de cuenta (si relación existe)
            account_name = getattr(t, "cuenta", None).nombre if getattr(t, "cuenta", None) else str(t.cuenta_id)
            self.table.setItem(i, 2, QTableWidgetItem(account_name))
            self.table.setItem(i, 3, QTableWidgetItem(t.descripcion or ""))
            self.table.setItem(i, 4, QTableWidgetItem(f"{float(t.monto):.2f}€"))
            es_transf = "Sí" if getattr(t, "es_transferencia", 0) else "No"
            self.table.setItem(i, 5, QTableWidgetItem(es_transf))
            self.table.setItem(i, 6, QTableWidgetItem(""))
            self.table.setItem(i, 7, QTableWidgetItem(""))
            self._set_action_buttons(i,
                                     edit_cb=lambda r, tid=t.id: self.on_edit_transaction(tid),
                                     del_cb=lambda r, tid=t.id: self.on_delete_transaction(tid))

    def _fill_fixed(self, rows):
        # print("DEBUG: Entro gastos fijos")
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(["ID", "Cuenta", "Descripción", "Monto", "Frecuencia", "Inicio", "Fin", "Transf.", "Editar", "Eliminar"])
        self.table.setRowCount(len(rows))
        
        # Ajustar anchos de columna
        self.table.setColumnWidth(0, 40)   # ID
        self.table.setColumnWidth(1, 100)  # Cuenta
        self.table.setColumnWidth(2, 200)  # Descripción más ancho
        self.table.setColumnWidth(3, 70)   # Monto
        self.table.setColumnWidth(4, 80)   # Frecuencia
        self.table.setColumnWidth(5, 70)   # Inicio
        self.table.setColumnWidth(6, 70)   # Fin
        self.table.setColumnWidth(7, 60)   # Transf
        
        for i, f in enumerate(rows):
            account_name = getattr(f, "cuenta", None).nombre if getattr(f, "cuenta", None) else str(f.cuenta_id)
            self.table.setItem(i, 0, QTableWidgetItem(str(f.id)))
            self.table.setItem(i, 1, QTableWidgetItem(account_name))
            self.table.setItem(i, 2, QTableWidgetItem(f.descripcion))
            self.table.setItem(i, 3, QTableWidgetItem(f"{float(f.monto):.2f}"))
            self.table.setItem(i, 4, QTableWidgetItem(f.frecuencia or ""))
            # Fechas
            fecha_inicio_str = format_date_str(f.fecha_inicio) if f.fecha_inicio else "-"
            fecha_fin_str = format_date_str(f.fecha_fin) if f.fecha_fin else "∞"
            self.table.setItem(i, 5, QTableWidgetItem(fecha_inicio_str))
            self.table.setItem(i, 6, QTableWidgetItem(fecha_fin_str))
            # Transferencia
            es_transf = "Sí" if getattr(f, "es_transferencia", 0) else "No"
            self.table.setItem(i, 7, QTableWidgetItem(es_transf))
            self._set_action_buttons(i,
                                     edit_cb=lambda checked=False, fid=f.id: self.on_edit_fixed(fid),
                                     del_cb=lambda checked=False, fid=f.id: self.on_delete_fixed(fid))
    def _fill_adjustments(self, rows):
        # print("DEBUG: Entro en Adjuntment")
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(["ID", "Fecha", "Cuenta", "Importe", "-" , "-" , "-" , "-" ,  "Editar", "Eliminar"])
        self.table.setRowCount(len(rows))
        for i, a in enumerate(rows):
            account_name = getattr(a, "cuenta", None).nombre if getattr(a, "cuenta", None) else str(a.cuenta_id)
            self.table.setItem(i, 0, QTableWidgetItem(str(a.id)))
            self.table.setItem(i, 1, QTableWidgetItem(format_date_str(a.fecha)))
            self.table.setItem(i, 2, QTableWidgetItem(account_name))
            self.table.setItem(i, 3, QTableWidgetItem(f"{float(a.monto_ajuste):.2f}"))
            self.table.setItem(i, 4, QTableWidgetItem(""))
            self.table.setItem(i, 5, QTableWidgetItem(""))
            self.table.setItem(i, 6, QTableWidgetItem(""))
            self.table.setItem(i, 7, QTableWidgetItem(""))
            self._set_action_buttons(i,
                                     edit_cb=lambda r, aid=a.id: self.on_edit_adjustment(aid),
                                     del_cb=lambda r, aid=a.id: self.on_delete_adjustment(aid))
    def _fill_mortgages(self, rows):
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre", "Tipo", "Capital Inicial", "Fecha Inicio", "Cuotas" , "Mensualidad A." , "Valor Actual" ,  "Editar", "Eliminar"])
        self.table.setRowCount(len(rows))
        for i, m in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(m.id)))
            self.table.setItem(i, 1, QTableWidgetItem(m.nombre or ""))
            self.table.setItem(i, 2, QTableWidgetItem(m.tipo or ""))
            self.table.setItem(i, 3, QTableWidgetItem(f"{float(m.capital_inicial):.2f}"))
            self.table.setItem(i, 4, QTableWidgetItem(format_date_str(m.fecha_inicio)))
            self.table.setItem(i, 5, QTableWidgetItem(str(m.cuotas_totales)))
                # Buscar el periodo que incluye hoy (usar date.today() correctamente)
            try:
                hoy = date.today()
                session = db.session()
                period = session.query(MortgagePeriod).filter(
                    MortgagePeriod.mortgage_id == m.id,
                    MortgagePeriod.fecha_inicio <= hoy,
                    MortgagePeriod.fecha_fin >= hoy
                ).first()
            except Exception as e:
                print("ERROR query periodo para cuota actual:", e)
                period = None

            cuota_actual_text = "AQUI 1"   # debug inicial
            if period:
                # debug: mostrar lo encontrado
                print("DEBUG periodo encontrado:", period.id, period.fecha_inicio, period.fecha_fin,
                    getattr(period, "capital_inicio", None), getattr(period, "interes_total", None),
                    getattr(period, "amortizacion_total", None))

                meses_en_periodo = (period.fecha_fin.year - period.fecha_inicio.year) * 12 + \
                                (period.fecha_fin.month - period.fecha_inicio.month) + 1
                try:
                    interes_tot = Decimal(str(getattr(period, "interes_total", 0)))
                    amort_tot = Decimal(str(getattr(period, "amortizacion_total", 0)))
                    if meses_en_periodo > 0:
                        cuota_mensual = (interes_tot + amort_tot) / Decimal(str(meses_en_periodo-1))
                        cuota_actual_text = f"{float(cuota_mensual):.2f}"
                    else:
                        cuota_actual_text = "AQUI 2"
                except Exception as e:
                    print("ERROR calculando cuota mensual:", e)
                    # fallback
                    try:
                        interes_tot = float(getattr(period, "interes_total", 0.0))
                        amort_tot = float(getattr(period, "amortizacion_total", 0.0))
                        if meses_en_periodo > 0:
                            cuota_actual_text = f"{(interes_tot + amort_tot) / (meses_en_periodo-1):.2f}"
                    except Exception:
                        cuota_actual_text = ""
            else:
                cuota_actual_text = ""  # ningún periodo para hoy

            self.table.setItem(i, 6, QTableWidgetItem(cuota_actual_text))
            # columnas vacías
            self.table.setItem(i, 7, QTableWidgetItem(f"{float(m.valor_actual_propiedad):.2f}"))
            self._set_action_buttons(i,
                                    edit_cb=lambda checked=False, mid=m.id: self.on_edit_mortgage(mid),
                                    del_cb=lambda checked=False, mid=m.id: self.on_delete_mortgage(mid))
    def _fill_mortgage_periods(self, rows):
            self.table.setColumnCount(10)
            self.table.setHorizontalHeaderLabels(["ID", "Préstamo ID", "Inicio", "Fin", "CapitalFinal","Cuota", "C. Intereses", "C. Amortizacion", "Editar", "Eliminar"])
            self.table.setRowCount(len(rows))
            for i, p in enumerate(rows):
                self.table.setItem(i, 0, QTableWidgetItem(str(p.id)))
                self.table.setItem(i, 1, QTableWidgetItem(str(p.mortgage_id)))
                self.table.setItem(i, 2, QTableWidgetItem(format_date_str(p.fecha_inicio)))
                self.table.setItem(i, 3, QTableWidgetItem(format_date_str(p.fecha_fin)))
                self.table.setItem(i, 4, QTableWidgetItem(f"{float(p.capital_fin):.2f}"))
                self.table.setItem(i, 5, QTableWidgetItem(f"{float((p.amortizacion_total + p.interes_total)/12):.2f}"))
                self.table.setItem(i, 6, QTableWidgetItem(f"{float(p.interes_total):.2f}"))
                self.table.setItem(i, 7, QTableWidgetItem(f"{float(p.amortizacion_total):.2f}"))
                self._set_action_buttons(i,
                                        edit_cb=lambda checked=False, mip=p.id: self.on_edit_mortgage_period(mip),
                                        del_cb=lambda checked=False, mip=p.id: self.on_delete_mortgage_period(mip))
    def _fill_plans(self, rows):
        # columnas: ID, Nombre, Descripción, Nº holdings, Valor actual (opcional), -, -, Editar, Eliminar
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre", "Descripción", "Holdings", "Valor actual", "", "","", "Editar", "Eliminar"])
        self.table.setRowCount(len(rows))
        for i, p in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(p.id)))
            self.table.setItem(i, 1, QTableWidgetItem(p.nombre or ""))
            self.table.setItem(i, 2, QTableWidgetItem(p.descripcion or ""))
            n_holdings = str(len(getattr(p, "holdings", [])))
            self.table.setItem(i, 3, QTableWidgetItem(n_holdings))
            # valor actual lo dejamos vacío aquí (puedes usar compute_plan_value si quieres)
            self.table.setItem(i, 4, QTableWidgetItem(""))
            self.table.setItem(i, 5, QTableWidgetItem(""))
            self.table.setItem(i, 6, QTableWidgetItem(""))
            self.table.setItem(i, 7, QTableWidgetItem(""))
            self._set_action_buttons(i,
                                    edit_cb=lambda checked=False, pid=p.id: self.on_edit_plan(pid),
                                    del_cb=lambda checked=False, pid=p.id: self.on_delete_plan(pid))

    def _fill_holdings(self, rows):
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "ID", "Plan", "Ticker", "Exchange", "Moneda",
            "Acciones", "Precio", "Total", "Editar", "Eliminar"
        ])
        self.table.setRowCount(len(rows))

        for i, (hid, plan, ticker, exch, mon, qty, price, total, last_update) in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(hid)))
            self.table.setItem(i, 1, QTableWidgetItem(plan))
            self.table.setItem(i, 2, QTableWidgetItem(ticker))
            self.table.setItem(i, 3, QTableWidgetItem(exch))
            self.table.setItem(i, 4, QTableWidgetItem(mon))
            self.table.setItem(i, 5, QTableWidgetItem(f"{qty:.6f}"))
            self.table.setItem(i, 6, QTableWidgetItem(f"{price:.2f}" if price else ""))
            self.table.setItem(i, 7, QTableWidgetItem(f"{total:.2f}" if total else ""))
            self.table.setItem(i, 8, QTableWidgetItem(str(last_update or "")))

            # botón editar
            self._set_action_buttons(i,
                                    edit_cb=lambda checked=False, id=hid: self.on_edit_holding(id),
                                    del_cb=lambda checked=False, id=hid: self.on_delete_holding(id))
    
    def _fill_purchases(self, rows):
        # rows son HoldingPurchase
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(["ID", "Holding", "Fecha", "Cantidad", "Precio unit.", "Valor", "", "",  "Editar", "Eliminar"])
        self.table.setRowCount(len(rows))
        for i, pu in enumerate(rows):
            #holding_ticker = getattr(pu, "holding").ticker if getattr(pu, "holding", None) else str(getattr(pu, "holding_id", ""))
            holding_ticker = ""
            if getattr(pu, "holding", None):
                holding_ticker = getattr(pu.holding, "ticker", "")
            else:
                holding_ticker = str(getattr(pu, "holding_id", ""))
            self.table.setItem(i, 0, QTableWidgetItem(str(pu.id)))
            self.table.setItem(i, 1, QTableWidgetItem(holding_ticker))
            self.table.setItem(i, 2, QTableWidgetItem(format_date_str(pu.fecha)))
            self.table.setItem(i, 3, QTableWidgetItem(f"{float(pu.cantidad):.6f}"))
            self.table.setItem(i, 4, QTableWidgetItem(f"{float(pu.precio_unitario):.6f}"))
            valor = float(pu.cantidad) * float(pu.precio_unitario)
            self.table.setItem(i, 5, QTableWidgetItem(f"{valor:.6f}"))
            self.table.setItem(i, 6, QTableWidgetItem(""))
            self.table.setItem(i, 7, QTableWidgetItem(""))
            self._set_action_buttons(i,
                                    edit_cb=lambda checked=False, pid=pu.id: self.on_edit_purchase(pid),
                                    del_cb=lambda checked=False, pid=pu.id: self.on_delete_purchase(pid))
    # -------------------------
    # CRUD: CUENTAS
    # -------------------------

    def on_new_account(self):
        dlg = AccountDialog(self)
        if dlg.exec() == QDialog.Accepted:
            nombre, saldo, visible = dlg.get_values()
            session = db.session()
            try:
                nueva = Account(nombre=nombre, saldo_inicial=saldo, visible=visible)
                session.add(nueva)
                session.commit()
                QMessageBox.information(self, "OK", "Cuenta creada")
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", f"No se pudo crear la cuenta: {e}")
            finally:
                session.close()
            self.refresh_table()
   

    def on_edit_account(self, account_id):
        session = db.session()
        try:
            acc = session.get(Account, account_id)
            if not acc:
                QMessageBox.warning(self, "No encontrado", "Cuenta no encontrada")
                return
            visible_actual = getattr(acc, 'visible', 1)
            dlg = AccountDialog(self, acc.nombre, float(acc.saldo_inicial), visible_actual)
            if dlg.exec() == QDialog.Accepted:
                nombre, saldo, visible = dlg.get_values()
                acc.nombre = nombre
                acc.saldo_inicial = saldo
                acc.visible = visible
                session.commit()
                QMessageBox.information(self, "OK", "Cuenta actualizada")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo editar la cuenta: {e}")
        finally:
            session.close()
        self.refresh_table()

    def on_delete_account(self, account_id):
        if QMessageBox.question(self, "Eliminar", "¿Eliminar esta cuenta?") != QMessageBox.Yes:
            return
        session = db.session()
        try:
            acc = session.get(Account, account_id)
            if acc:
                session.delete(acc)
                session.commit()
                QMessageBox.information(self, "OK", "Cuenta eliminada")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo eliminar la cuenta: {e}")
        finally:
            session.close()
        self.refresh_table()

    # -------------------------
    # CRUD: GASTOS PUNTUALES
    # -------------------------

    def on_edit_transaction(self, transaction_id):
        session = db.session()
        try:
            t = session.get(Transaction, transaction_id)
            if not t:
                QMessageBox.warning(self, "No encontrado", "Transacción no encontrada")
                return

            # obtener lista de cuentas para el combo
            cuentas = [(a.id, a.nombre) for a in session.query(Account).order_by(Account.id).all()]
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"Error al cargar datos: {e}")
            return
        finally:
            session.close()

        # Abrimos diálogo pasándole cuentas y el objeto transaction
        dlg = TransactionDialog(self, cuentas=cuentas, transaction=t, is_income=False)
        if dlg.exec() != QDialog.Accepted:
            return

        try:
            vals = dlg.get_values()
        except ValueError as e:
            QMessageBox.warning(self, "Valor inválido", str(e))
            return

        # Validaciones mínimas
        if vals.get("cuenta_id") is None:
            QMessageBox.warning(self, "Falta cuenta", "Selecciona una cuenta.")
            return

        session = db.session()
        try:
            tdb = session.get(Transaction, transaction_id)
            if not tdb:
                QMessageBox.warning(self, "No encontrado", "Transacción no encontrada (ya eliminada?)")
                return

            tdb.cuenta_id = int(vals["cuenta_id"])
            tdb.fecha = vals["fecha"]
            tdb.descripcion = vals["descripcion"]

            # Aceptar Decimal o str/float; almacenamos Decimal
            monto_val = vals["monto"]
            if not isinstance(monto_val, Decimal):
                monto_val = Decimal(str(monto_val))
            tdb.monto = monto_val
            tdb.es_transferencia = vals.get("es_transferencia", 0)

            session.add(tdb)
            session.commit()
            QMessageBox.information(self, "OK", "Transacción actualizada")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo actualizar la transacción: {e}")
            print("DEBUG on_edit_transaction error:", e)
        finally:
            session.close()

        self.refresh_table()


    def on_delete_transaction(self, transaction_id):
        resp = QMessageBox.question(
            self,
            "Eliminar",
            "¿Eliminar esta transacción?",
            QMessageBox.Yes | QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            return

        session = db.session()
        try:
            t = session.get(Transaction, transaction_id)
            if not t:
                QMessageBox.warning(self, "No encontrado", "Transacción no encontrada")
                return
            session.delete(t)
            session.commit()
            QMessageBox.information(self, "OK", "Transacción eliminada")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo eliminar la transacción: {e}")
        finally:
            session.close()

        self.refresh_table()
        
    # -------------------------
    # CRUD: GASTOS PUNTUALES
    # -------------------------
    def on_new_transaction(self, is_income=False):
        # obtener cuentas para llenar el combo del diálogo
        session = db.session()
        try:
            cuentas = [(a.id, a.nombre) for a in session.query(Account).order_by(Account.id).all()]
        finally:
            session.close()

        dlg = TransactionDialog(self, cuentas=cuentas, transaction=None, is_income=is_income)
        if dlg.exec() != QDialog.Accepted:
            return

        try:
            data = dlg.get_values()  # debe devolver cuenta_id, fecha, descripcion, monto (Decimal)
        except ValueError as e:
            QMessageBox.warning(self, "Valor inválido", str(e))
            return

        if data.get("cuenta_id") is None:
            QMessageBox.warning(self, "Falta cuenta", "Selecciona una cuenta.")
            return

        session = db.session()
        try:
            t = Transaction(
                cuenta_id=int(data["cuenta_id"]),
                fecha=data["fecha"],
                descripcion=data["descripcion"],
                monto=Decimal(data["monto"]) if not isinstance(data["monto"], Decimal) else data["monto"],
                es_transferencia=data.get("es_transferencia", 0)
            )
            session.add(t)
            session.commit()
            QMessageBox.information(self, "OK", "Transacción añadida")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo añadir transacción: {e}")
            print("DEBUG on_new_transaction error:", e)
        finally:
            session.close()

        self.refresh_table()
    
    # -------------------------
    # NUEVA TRANSFERENCIA
    # -------------------------
    def on_new_transfer(self):
        """Crea una transferencia entre dos cuentas (dos transacciones vinculadas)"""
        session = db.session()
        try:
            cuentas = [(a.id, a.nombre) for a in session.query(Account).order_by(Account.id).all()]
        finally:
            session.close()

        if len(cuentas) < 2:
            QMessageBox.warning(self, "Cuentas insuficientes", "Necesitas al menos 2 cuentas para hacer una transferencia.")
            return

        dlg = TransferenciaDialog(self, cuentas=cuentas)
        if dlg.exec() != QDialog.Accepted:
            return

        try:
            data = dlg.get_values()
        except ValueError as e:
            QMessageBox.warning(self, "Valor inválido", str(e))
            return

        # Validaciones
        if data.get("cuenta_origen_id") is None or data.get("cuenta_destino_id") is None:
            QMessageBox.warning(self, "Faltan cuentas", "Debes seleccionar cuenta origen y destino.")
            return
        
        if data["cuenta_origen_id"] == data["cuenta_destino_id"]:
            QMessageBox.warning(self, "Cuentas iguales", "La cuenta origen y destino deben ser diferentes.")
            return
        
        if data.get("monto", 0) <= 0:
            QMessageBox.warning(self, "Importe inválido", "El importe debe ser mayor que 0.")
            return

        session = db.session()
        try:
            # Crear transacción negativa en cuenta origen
            t_origen = Transaction(
                cuenta_id=int(data["cuenta_origen_id"]),
                fecha=data["fecha"],
                descripcion=data["descripcion"],
                monto=Decimal(str(-abs(float(data["monto"])))),  # negativo
                es_transferencia=1
            )
            
            # Crear transacción positiva en cuenta destino
            t_destino = Transaction(
                cuenta_id=int(data["cuenta_destino_id"]),
                fecha=data["fecha"],
                descripcion=data["descripcion"],
                monto=Decimal(str(abs(float(data["monto"])))),  # positivo
                es_transferencia=1
            )
            
            session.add(t_origen)
            session.add(t_destino)
            session.commit()
            QMessageBox.information(self, "OK", "Transferencia realizada correctamente")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo realizar la transferencia: {e}")
            print("DEBUG on_new_transfer error:", e)
        finally:
            session.close()

        self.refresh_table()
    
    # -------------------------
    # CRUD: GASTOS FIJOS
    # -------------------------
    def on_new_fixed(self, is_income=False):
        dlg = FixedExpenseDialog(self, is_income=is_income)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_values()
            session = db.session()
            try:
                fe = FixedExpense(
                    cuenta_id=data['cuenta_id'],
                    descripcion=data['descripcion'],
                    monto=data['monto'],
                    frecuencia=data['frecuencia'],
                    fecha_inicio=data['fecha_inicio'],
                    fecha_fin=data['fecha_fin'],
                    es_transferencia=data.get('es_transferencia', 0)
                )
                session.add(fe)
                session.commit()
                QMessageBox.information(self, "OK", "Gasto fijo añadido")
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", f"No se pudo añadir gasto fijo: {e}")
            finally:
                session.close()
            self.refresh_table()

    def on_edit_fixed(self, fixed_id):
        session = db.session()
        try:
            f = session.get(FixedExpense, fixed_id)
            if not f:
                QMessageBox.warning(self, "No encontrado", "Gasto fijo no encontrado")
                return

            # abrimos diálogo usando fixed_values
            dlg = FixedExpenseDialog(self, fixed_values={
                "id": f.id,
                "cuenta_id": f.cuenta_id,
                "descripcion": f.descripcion,
                "monto": float(f.monto) if f.monto is not None else 0.0,
                "frecuencia": f.frecuencia,
                "fecha_inicio": f.fecha_inicio,
                "fecha_fin": f.fecha_fin,
                "es_transferencia": getattr(f, "es_transferencia", 0)
            }, fixed_expense_obj=f, session=session)

            from PySide6.QtWidgets import QDialog
            result = dlg.exec()
            
            if result == QDialog.Accepted:
                data = dlg.get_values()

                from decimal import Decimal
                monto_decimal = Decimal(str(data['monto'])) if data['monto'] is not None else Decimal('0.00')

                f.cuenta_id = data['cuenta_id']
                f.descripcion = data['descripcion']
                f.monto = monto_decimal
                f.frecuencia = data['frecuencia']
                f.fecha_inicio = data['fecha_inicio']
                f.fecha_fin = data['fecha_fin']
                f.es_transferencia = data.get('es_transferencia', 0)

                session.add(f)
                session.flush()
                session.commit()
                try:
                    session.refresh(f)
                except Exception:
                    pass

                # comprobación opcional en nueva sesión (útil para depurar)
                new_s = db.session()
                try:
                    fresh = new_s.get(FixedExpense, f.id)
                    print("DEBUG fresh from new session:", fresh.id, "monto:", getattr(fresh, "monto", None))
                finally:
                    new_s.close()

                QMessageBox.information(self, "OK", "Gasto fijo actualizado")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo editar gasto fijo: {e}")
            print("DEBUG exception in on_edit_fixed:", e)
        finally:
            session.close()

        self.refresh_table()

    def on_delete_fixed(self, fixed_id):
        if QMessageBox.question(self, "Eliminar", "¿Eliminar este gasto fijo?") != QMessageBox.Yes:
            return
        session = db.session()
        try:
            f = session.get(FixedExpense, fixed_id)
            if f:
                session.delete(f)
                session.commit()
                QMessageBox.information(self, "OK", "Gasto fijo eliminado")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo eliminar gasto fijo: {e}")
        finally:
            session.close()
        self.refresh_table()

    # -------------------------
    # CRUD: ADJUSTMENTS
    # -------------------------
    def on_edit_adjustment(self, adj_id):
        session = db.session()
        try:
            a = session.get(Adjustment, adj_id)
            if not a:
                QMessageBox.warning(self, "No encontrado", "Ajuste no encontrado")
                return

            # obtener cuentas para combo
            cuentas = [(acc.id, acc.nombre) for acc in session.query(Account).order_by(Account.id).all()]
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"Error cargando datos: {e}")
            print("DEBUG on_edit_adjustment load error:", e)
            return
        finally:
            session.close()

        # abrir diálogo con cuentas y el ajuste a editar
        dlg = AdjustmentDialog(self, cuentas=cuentas, adj=a)
        if dlg.exec() != QDialog.Accepted:
            return

        try:
            data = dlg.get_values()
        except ValueError as e:
            QMessageBox.warning(self, "Valor inválido", str(e))
            return

        # validaciones mínimas
        if data.get("cuenta_id") is None:
            QMessageBox.warning(self, "Falta cuenta", "Selecciona una cuenta.")
            return

        session = db.session()
        try:
            adj_db = session.get(Adjustment, adj_id)
            if not adj_db:
                QMessageBox.warning(self, "No encontrado", "Ajuste no encontrado (ya eliminado?)")
                return

            adj_db.cuenta_id = int(data["cuenta_id"])
            adj_db.fecha = data["fecha"]
            monto_val = data["monto"]
            if not isinstance(monto_val, Decimal):
                monto_val = Decimal(str(monto_val))
            adj_db.monto_ajuste = monto_val
            adj_db.descripcion = data.get("descripcion") or ""

            session.add(adj_db)
            session.commit()
            QMessageBox.information(self, "OK", "Ajuste actualizado")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo editar ajuste: {e}")
            print("DEBUG on_edit_adjustment save error:", e)
        finally:
            session.close()

        self.refresh_table()

    def on_delete_adjustment(self, adj_id):
        resp = QMessageBox.question(
            self,
            "Eliminar",
            "¿Eliminar este ajuste?",
            QMessageBox.Yes | QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            return

        session = db.session()
        try:
            a = session.get(Adjustment, adj_id)
            if not a:
                QMessageBox.warning(self, "No encontrado", "Ajuste no encontrado")
                return
            session.delete(a)
            session.commit()
            QMessageBox.information(self, "OK", "Ajuste eliminado")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo eliminar ajuste: {e}")
            print("DEBUG on_delete_adjustment error:", e)
        finally:
            session.close()

        self.refresh_table()
    
    # -------------------------
    # CRUD: PRÉSTAMOS
    # -------------------------
    def on_edit_mortgage(self, mortgage_id):
        session = db.session()
        try:
            m = session.get(Mortgage, mortgage_id)
            if not m:
                QMessageBox.warning(self, "No encontrado", "Préstamo no encontrado")
                return
            dlg = MortgageDialog(self, mortgage=m)
            if dlg.exec() == QDialog.Accepted:
                data = dlg.get_values()
                m.nombre = data["nombre"]
                m.tipo = data["tipo"]
                m.fecha_inicio = data["fecha_inicio"]
                m.capital_inicial = Decimal(str(data["capital_inicial"]))
                m.cuotas_totales = int(data["cuotas_totales"])
                m.valor_actual_propiedad = Decimal(str(data["valor_actual_propiedad"]))
                session.commit()
                QMessageBox.information(self, "OK", "Préstamo actualizado")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo editar el préstamo: {e}")
        finally:
            session.close()
        self.refresh_table()

    def on_delete_mortgage(self, mortgage_id):
        if QMessageBox.question(self, "Eliminar", "¿Eliminar este préstamo y sus periodos?") != QMessageBox.Yes:
            return
        session = db.session()
        try:
            m = session.get(Mortgage, mortgage_id)
            if m:
                # borrar periodos asociados
                session.query(MortgagePeriod).filter_by(mortgage_id=m.id).delete()
                session.delete(m)
                session.commit()
                QMessageBox.information(self, "OK", "Préstamo eliminado")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo eliminar préstamo: {e}")
        finally:
            session.close()
        self.refresh_table()
    
    def on_edit_mortgage_period(self, period_id):
        session = db.session()
        try:
            p = session.get(MortgagePeriod, period_id)
            if not p:
                QMessageBox.warning(self, "No encontrado", "Periodo no encontrado")
                return

            dlg = MortgagePeriodDialog(self, period=p)
            if dlg.exec() == QDialog.Accepted:
                data = dlg.get_values()
                p.capital_fin = Decimal(str(data["capital_fin"]))
                p.interes = Decimal(str(data["interes"]))

                # ✅ Recalcular cuadro desde este periodo
                self.recalc_from_period(session, p)

                session.commit()
                QMessageBox.information(self, "OK", "Periodo actualizado y cuadro recalculado")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo editar el cuadro: {e}")
        finally:
            session.close()
        self.refresh_table()

    def on_delete_mortgage_period(self, period_id):
        if QMessageBox.question(self, "Eliminar", "¿Eliminar este periodo del cuadro de amortización?") != QMessageBox.Yes:
            return
        session = db.session()
        try:
            p = session.get(MortgagePeriod, period_id)
            if p:
                session.delete(p)
                session.commit()
                QMessageBox.information(self, "OK", "Periodo eliminado")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo eliminar periodo: {e}")
        finally:
            session.close()
        self.refresh_table()

    # -------------------------
    # Placeholder préstamos
    # -------------------------
    def on_new_loan(self):
        dlg = MortgageDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return

        data = dlg.get_values()
        session = db.session()
        try:
            # Crear el préstamo
            m = Mortgage(
                nombre=data["nombre"],
                tipo=data["tipo"],
                fecha_inicio=data["fecha_inicio"],
                capital_inicial=Decimal(str(data["capital_inicial"])),
                cuotas_totales=int(data["cuotas_totales"]),
                valor_actual_propiedad=Decimal(str(data["valor_actual_propiedad"]))
            )
            session.add(m)
            session.flush()  # obtener m.id

            # Usamos el interés indicado en el diálogo para generar los periodos
            interes_anual = Decimal(str(data.get("interes_anual", "0")))

            # Generar periodos y calcular interes/amortizacion por periodo
            generar_periodos_amortizacion(session, m, interes_anual_inicial=interes_anual)

            QMessageBox.information(self, "OK", "Préstamo creado y tabla de periodos generada.")
            self.refresh_table()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo crear el préstamo: {e}")
            print("DEBUG on_new_loan error:", e)
        finally:
            session.close()
    def recalc_from_period(self, session, period):
        """
        Recalcula el préstamo a partir del periodo indicado y refresca la tabla.
        """
        # print("DEBUG: recalc_from_period...")
        # llama a tu función que borra periodos posteriores y genera los nuevos
        recalcular_desde_periodo(session, period.mortgage, period)

        # obtener los rows actualizados para ese mortgage
        rows = session.query(MortgagePeriod).filter_by(mortgage_id=period.mortgage_id).order_by(MortgagePeriod.fecha_inicio).all()

        # actualizar cualquier cache local que uses
        self.mortgage_periods = rows

        # rellenar la tabla con los rows (método existente que espera `rows`)
        self._fill_mortgage_periods(rows)
       
    def _recalculate_from(self, item: QTableWidgetItem):
        if item.column() != 2:
            return

        try:
            new_interes = Decimal(str(item.text()))
        except Exception:
            print(f"Valor de interés inválido: {item.text()}")
            return

        session = db.session()
        try:
            period = self.mortgage_periods[item.row()]
            period.interes = float(new_interes)
            session.add(period)
            session.commit()

            # usa el método de recálculo que ahora refresca y llama a _fill_mortgage_periods(rows)
            self.recalc_from_period(session, period)
        except Exception as e:
            session.rollback()
            print("ERROR al recalcular desde periodo:", e)
        finally:
            session.close()
    # --- Planes ---
    def on_new_plan(self):
        dlg = PlanDialog(self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_values()
            session = db.session()
            try:
                from models.holding import HoldingPlan
                p = HoldingPlan(nombre=data['nombre'], descripcion=data.get('descripcion'))
                session.add(p)
                session.commit()
                QMessageBox.information(self, "OK", "Plan creado")
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", f"No se pudo crear plan: {e}")
            finally:
                session.close()
            self.refresh_table()

    def on_edit_plan(self, plan_id):
        session = db.session()
        try:
            from models.holding import HoldingPlan
            p = session.get(HoldingPlan, plan_id)
            if not p:
                QMessageBox.warning(self, "No encontrado", "Plan no encontrado")
                return
            dlg = PlanDialog(self, plan=p)
            if dlg.exec() == QDialog.Accepted:
                data = dlg.get_values()
                p.nombre = data['nombre']
                p.descripcion = data.get('descripcion')
                session.add(p)
                session.commit()
                QMessageBox.information(self, "OK", "Plan actualizado")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo editar plan: {e}")
        finally:
            session.close()
        self.refresh_table()

    def on_delete_plan(self, plan_id):
        if QMessageBox.question(self, "Eliminar", "¿Eliminar este plan?") != QMessageBox.Yes:
            return
        session = db.session()
        try:
            from models.holding import HoldingPlan
            p = session.get(HoldingPlan, plan_id)
            if p:
                session.delete(p)
                session.commit()
                QMessageBox.information(self, "OK", "Plan eliminado")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo eliminar plan: {e}")
        finally:
            session.close()
        self.refresh_table()

    # --- Holdings ---
    def on_new_holding(self):
        # abrir diálogo que permite elegir plan (opcional) y ticker
        session = db.session()
        try:
            from models.holding import HoldingPlan
            plans = session.query(HoldingPlan).order_by(HoldingPlan.id).all()
        finally:
            session.close()

        dlg = HoldingDialog(self, plans=plans)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_values()
            session = db.session()
            try:
                from models.holding import Holding
                h = Holding(plan_id=data.get('plan_id'), ticker=data['ticker'].upper(), exchange=data.get('exchange'), moneda=data.get('moneda', 'USD'))
                session.add(h)
                session.commit()
                QMessageBox.information(self, "OK", "Holding creado")
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", f"No se pudo crear holding: {e}")
            finally:
                session.close()
            self.refresh_table()

    def on_edit_holding(self, holding_id):
        session = db.session()
        try:
            from models.holding import Holding, HoldingPlan
            h = session.get(Holding, holding_id)
            plans = session.query(HoldingPlan).order_by(HoldingPlan.id).all()
            if not h:
                QMessageBox.warning(self, "No encontrado", "Holding no encontrado")
                return
            dlg = HoldingDialog(self, holding=h, plans=plans)
            if dlg.exec() == QDialog.Accepted:
                data = dlg.get_values()
                h.plan_id = data.get('plan_id')
                h.ticker = data['ticker'].upper()
                h.exchange = data.get('exchange')
                h.moneda = data.get('moneda', 'USD')
                session.add(h)
                session.commit()
                QMessageBox.information(self, "OK", "Holding actualizado")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo editar holding: {e}")
        finally:
            session.close()
        self.refresh_table()

    def on_delete_holding(self, holding_id):
        if QMessageBox.question(self, "Eliminar", "¿Eliminar este holding?") != QMessageBox.Yes:
            return
        session = db.session()
        try:
            from models.holding import Holding
            h = session.get(Holding, holding_id)
            if h:
                session.delete(h)
                session.commit()
                QMessageBox.information(self, "OK", "Holding eliminado")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo eliminar holding: {e}")
        finally:
            session.close()
        self.refresh_table()

    # --- Purchases ---
    # ---
    def on_new_purchase(self):
        session = db.session()
        try:
            holdings_q = session.query(Holding).order_by(Holding.id).all()
            holdings_choices = []
            for h in holdings_q:
                plan_nombre = getattr(getattr(h, "plan", None), "nombre", "") or ""
                holdings_choices.append((h.id, h.ticker or "", plan_nombre))
        finally:
            session.close()

        dlg = HoldingPurchaseDialog(self, holdings=holdings_choices)
        if dlg.exec() == QDialog.Accepted:
            vals = dlg.get_values()
            session2 = db.session()
            try:
                if vals.get("holding_id") is None:
                    raise ValueError("Selecciona un holding válido.")
                p = HoldingPurchase(
                    holding_id = int(vals["holding_id"]),
                    fecha = vals["fecha"],
                    cantidad = vals["cantidad"],
                    precio_unitario = vals["precio_unitario"],
                    nota = vals.get("nota") or None
                )
                session2.add(p)
                session2.commit()
                # ------ NUEVO: recalcular cantidad del holding y actualizar precio ------
                try:
                    # recalcular cantidad (actualiza holding.cantidad y hace commit)
                    from models.holding import recalc_holding_cantidad, update_price_for_holding
                    recalc_holding_cantidad(session2, int(vals["holding_id"]))
                    # obtener holding en la misma sesión y actualizar precio actual
                    h = session2.get(Holding, int(vals["holding_id"]))
                    update_price_for_holding(session2, h)
                    session2.commit()
                except Exception as e:
                    # no queremos que falle todo si falla la actualización del precio; registramos
                    session2.rollback()
                    print("Aviso: no se pudo actualizar cantidad/precio tras nueva compra:", e)
                QMessageBox.information(self, "OK", "Compra registrada")
            except Exception as e:
                session2.rollback()
                QMessageBox.critical(self, "Error", f"No se pudo registrar compra: {e}")
            finally:
                session2.close()

        self.refresh_table()


    def on_edit_purchase(self, purchase_id):
        from decimal import Decimal
        try:
            from models.holding import Holding, HoldingPurchase
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudieron importar modelos de holdings: {e}")
            return

        session = db.session()
        try:
            pu = session.get(HoldingPurchase, purchase_id)
            if not pu:
                QMessageBox.warning(self, "No encontrado", "Compra no encontrada")
                return

            # Construir dict simple con los datos de la compra (para evitar DetachedInstanceError)
            purchase_data = {
                "id": pu.id,
                "holding_id": int(pu.holding_id),
                "fecha": pu.fecha,
                "cantidad": float(pu.cantidad),
                "precio_unitario": float(pu.precio_unitario),
                "nota": pu.nota
            }

            holdings_q = session.query(Holding).order_by(Holding.id).all()
            holdings_choices = []
            for h in holdings_q:
                plan_nombre = getattr(getattr(h, "plan", None), "nombre", "") or ""
                holdings_choices.append((h.id, h.ticker or "", plan_nombre))
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"Error leyendo datos: {e}")
            return
        finally:
            session.close()

        dlg = HoldingPurchaseDialog(self, purchase=purchase_data, holdings=holdings_choices)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_values()
            session2 = db.session()
            try:
                pu2 = session2.get(HoldingPurchase, purchase_id)
                if not pu2:
                    raise ValueError("Compra no encontrada en sesión nueva.")
                pu2.holding_id = int(data['holding_id'])
                pu2.fecha = data['fecha']
                pu2.cantidad = data['cantidad']
                pu2.precio_unitario = data['precio_unitario']
                pu2.nota = data.get('nota') or None
                session2.add(pu2)
                session2.commit()
                QMessageBox.information(self, "OK", "Compra actualizada")
            except Exception as e:
                session2.rollback()
                QMessageBox.critical(self, "Error", f"No se pudo editar compra: {e}")
            finally:
                session2.close()
                 # actualizar cantidad y precio del holding afectado (puede haber cambiado holding_id)
                try:
                    from models.holding import recalc_holding_cantidad, update_price_for_holding
                    recalc_holding_cantidad(session2, int(data['holding_id']))
                    h2 = session2.get(Holding, int(data['holding_id']))
                    update_price_for_holding(session2, h2)
                    session2.commit()
                except Exception as e:
                    session2.rollback()
                    print("Aviso: no se pudo actualizar cantidad/precio tras editar compra:", e)
                QMessageBox.information(self, "OK", "Compra actualizada")
        self.refresh_table()


    def on_delete_purchase(self, purchase_id):
        try:
            from models.holding import HoldingPurchase
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudieron importar modelos de holdings: {e}")
            return

        resp = QMessageBox.question(self, "Eliminar", "¿Eliminar esta compra?", QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            return

        session = db.session()
        try:
            pu = session.get(HoldingPurchase, purchase_id)
            if pu:
                session.delete(pu)
                session.commit()
                QMessageBox.information(self, "OK", "Compra eliminada")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo eliminar compra: {e}")
        finally:
            session.close()
            if pu:
                holding_id = pu.holding_id
                session.delete(pu)
                session.commit()
                # recalcular cantidad y actualizar precio en la misma sesión
                try:
                    from models.holding import recalc_holding_cantidad, update_price_for_holding
                    recalc_holding_cantidad(session, holding_id)
                    h = session.get(Holding, holding_id)
                    update_price_for_holding(session, h)
                    session.commit()
                except Exception as e:
                    session.rollback()
                    print("Aviso: no se pudo actualizar cantidad/precio tras eliminar compra:", e)

                QMessageBox.information(self, "OK", "Compra eliminada")

        self.refresh_table()
    
    

class AccountDialog(QDialog):
    def __init__(self, parent=None, nombre="", saldo=0.0, visible=1):
        super().__init__(parent)
        self.setWindowTitle("Cuenta")
        self.setModal(True)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.input_nombre = QLineEdit(nombre)
        self.input_saldo = QDoubleSpinBox()
        self.input_saldo.setMaximum(1_000_000_000)
        self.input_saldo.setValue(float(saldo))
        self.input_saldo.setDecimals(2)
        form.addRow("Nombre:", self.input_nombre)
        form.addRow("Saldo inicial:", self.input_saldo)
        
        # Checkbox para cuenta activa/visible
        self.check_visible = QCheckBox("Cuenta activa (visible en UI)")
        self.check_visible.setChecked(bool(visible))
        form.addRow("", self.check_visible)
        
        layout.addLayout(form)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def get_values(self):
        return (self.input_nombre.text().strip(), 
                float(self.input_saldo.value()),
                1 if self.check_visible.isChecked() else 0)


class TransactionDialog(QDialog):
    def __init__(self, parent=None, transaction=None, cuentas=None, is_income=False):
        """
        transaction: objeto Transaction (ORM) para editar, o None para nuevo
        cuentas: lista de tuples (id, nombre) para poblar combo de cuentas (opcional)
        is_income: si True puedes pre-marcar o influir en el signo/valor
        """
        super().__init__(parent)
        self.setWindowTitle("Transacción" if transaction else "Nueva transacción")
        self.resize(480, 160)

        self.transaction = transaction

        layout = QVBoxLayout(self)

        form = QFormLayout()
        # Cuenta (combo)
        self.combo_cuenta = QComboBox()
        # si te pasan cuentas, poblar; si no, dejar vacío (puedes cargar en caller)
        if cuentas:
            for cid, name in cuentas:
                self.combo_cuenta.addItem(name, cid)

        # Fecha
        self.input_fecha = QDateEdit(calendarPopup=True)
        setup_date_edit(self.input_fecha)
        self.input_fecha.setDate(QDate.currentDate())

        # Descripción
        self.input_desc = QLineEdit()

        # Importe -> QDoubleSpinBox que permite negativos
        self.input_monto = QDoubleSpinBox()
        self.input_monto.setRange(-10_000_000_000, 10_000_000_000)
        self.input_monto.setDecimals(2)
        self.input_monto.setSingleStep(0.01)
        # opcional: quitar botones (estética)
        # from PySide6.QtWidgets import QAbstractSpinBox
        # self.input_monto.setButtonSymbols(QAbstractSpinBox.NoButtons)

        form.addRow(QLabel("Cuenta:"), self.combo_cuenta)
        form.addRow(QLabel("Fecha:"), self.input_fecha)
        form.addRow(QLabel("Concepto:"), self.input_desc)
        form.addRow(QLabel("Importe (€):"), self.input_monto)
        
        # Checkbox para marcar como transferencia
        self.check_transferencia = QCheckBox("Es transferencia entre cuentas")
        self.check_transferencia.setToolTip("Marca esto si es una transferencia entre tus cuentas (no se contará como gasto/ingreso real)")
        form.addRow("", self.check_transferencia)

        layout.addLayout(form)

        # Botones OK/Cancelar
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Si vienen datos para editar, rellenar
        if transaction is not None:
            # Asumiendo atributos: cuenta_id, fecha (date), descripcion, monto (Numeric)
            # seleccionar cuenta si corresponde
            if hasattr(transaction, "cuenta_id"):
                idx = None
                for i in range(self.combo_cuenta.count()):
                    if self.combo_cuenta.itemData(i) == transaction.cuenta_id:
                        idx = i
                        break
                if idx is not None:
                    self.combo_cuenta.setCurrentIndex(idx)
            if hasattr(transaction, "fecha") and transaction.fecha:
                try:
                    self.input_fecha.setDate(QDate(transaction.fecha.year, transaction.fecha.month, transaction.fecha.day))
                except Exception:
                    pass
            if hasattr(transaction, "descripcion"):
                self.input_desc.setText(str(transaction.descripcion or ""))
            if hasattr(transaction, "monto"):
                try:
                    self.input_monto.setValue(float(transaction.monto))
                except Exception:
                    self.input_monto.setValue(0.0)
            if hasattr(transaction, "es_transferencia"):
                self.check_transferencia.setChecked(bool(transaction.es_transferencia))
        else:
            # nuevo: si is_income quieres 0 positivo por defecto
            self.input_monto.setValue(0.0 if is_income else 0.0)

    def get_values(self) -> dict:
        """Devuelve un dict listo para guardar: cuenta_id, fecha (date), descripcion, monto (Decimal)"""
        cuenta_id = None
        if self.combo_cuenta.count() > 0:
            cuenta_id = self.combo_cuenta.currentData()
            # si no usas itemData, toma index -> text o manejar en caller

        fecha_qdate = self.input_fecha.date()
        fecha_py = date(fecha_qdate.year(), fecha_qdate.month(), fecha_qdate.day())

        # usar Decimal para precisión monetaria
        monto_val = Decimal(f"{self.input_monto.value():.2f}")

        return {
            "cuenta_id": cuenta_id,
            "fecha": fecha_py,
            "descripcion": self.input_desc.text().strip(),
            "monto": monto_val,
            "es_transferencia": 1 if self.check_transferencia.isChecked() else 0
        }


class FixedExpenseDialog(QDialog):
    def __init__(self, parent=None, fixed: FixedExpense=None, fixed_values: dict=None, is_income=False, fixed_expense_obj=None, session=None):
        super().__init__(parent)
        self.setWindowTitle("Gasto Fijo" if not is_income else "Ingreso Fijo")
        self.setModal(True)
        self.fixed_expense_obj = fixed_expense_obj
        self.session = session
        self.fixed_id = fixed_values.get("id") if fixed_values else None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Cargar cuentas
        session = db.session()
        cuentas = session.query(Account).order_by(Account.nombre).all()
        session.close()
        self.combo_cuenta = QComboBox()
        for c in cuentas:
            self.combo_cuenta.addItem(f"{c.nombre} ({c.id})", c.id)

        # Widgets
        self.input_desc = QLineEdit()
       # --- creación y configuración del spinbox (reemplaza tu bloque actual) ---
        self.input_monto = QDoubleSpinBox()
        # permitir valores negativos y positivos (rango amplio)
        self.input_monto.setRange(-1_000_000_000, 1_000_000_000)
        # permitir decimales y paso fino
        self.input_monto.setDecimals(2)
        self.input_monto.setSingleStep(0.01)
        # quitar botones de incremento para que quede como campo editable puro
        self.input_monto.setButtonSymbols(QAbstractSpinBox.NoButtons)
        # opcional: permitir edición por teclado sin validar hasta aceptar
        self.input_monto.setKeyboardTracking(True)

        self.combo_freq = QComboBox()
        self.combo_freq.addItems(["semanal", "mensual", "trimestral", "semestral", "anual"])

        self.input_fecha_inicio = QDateEdit()
        setup_date_edit(self.input_fecha_inicio)
        self.input_fecha_inicio.setCalendarPopup(True)
        self.input_fecha_fin = QDateEdit()
        setup_date_edit(self.input_fecha_fin)
        self.input_fecha_fin.setCalendarPopup(True)
        
        # Checkbox para marcar como transferencia (crear ANTES de cargar valores)
        self.check_transferencia = QCheckBox("Es transferencia entre cuentas")
        self.check_transferencia.setToolTip("Marca esto si es una transferencia recurrente entre tus cuentas")

        # Fuente de datos: prioridad fixed_values (dict) > fixed (obj) > None
        source = None
        if fixed_values:
            source = fixed_values
            # debug temporal
            # print("DEBUG FixedExpenseDialog: using fixed_values dict:", source)
        elif fixed:
            # construir dict desde el objeto ORM (más seguro)
            try:
                monto_conv = float(getattr(fixed, "monto")) if getattr(fixed, "monto", None) is not None else 0.0
            except Exception:
                from decimal import Decimal
                monto_conv = float(Decimal(str(getattr(fixed, "monto", 0))))
            source = {
                "id": getattr(fixed, "id", None),
                "cuenta_id": getattr(fixed, "cuenta_id", None),
                "descripcion": getattr(fixed, "descripcion", "") or "",
                "monto": monto_conv,
                "frecuencia": getattr(fixed, "frecuencia", None),
                "fecha_inicio": getattr(fixed, "fecha_inicio", None),
                "fecha_fin": getattr(fixed, "fecha_fin", None)
            }
            #  print("DEBUG FixedExpenseDialog: built source from fixed obj:", source)

        # Aplicar valores si existen
        if source:
            # cuenta
            if source.get("cuenta_id") is not None:
                idx = self.combo_cuenta.findData(source["cuenta_id"])
                if idx >= 0:
                    self.combo_cuenta.setCurrentIndex(idx)

            # descripción
            self.input_desc.setText(source.get("descripcion", ""))

            # monto (seguro)
            if source and "monto" in source:
                try:
                    self.input_monto.setValue(float(source.get("monto", 0.0)))
                except Exception:
                    from decimal import Decimal
                    self.input_monto.setValue(float(Decimal(str(source.get("monto", 0)))))
            else:
                self.input_monto.setValue(0.0)

            # frecuencia
            if source.get("frecuencia"):
                fq_idx = self.combo_freq.findText(source["frecuencia"])
                if fq_idx >= 0:
                    self.combo_freq.setCurrentIndex(fq_idx)

            # fechas (defensivo)
            if source.get("fecha_inicio"):
                d = source["fecha_inicio"]
                self.input_fecha_inicio.setDate(QDate(d.year, d.month, d.day))
            if source.get("fecha_fin"):
                d2 = source["fecha_fin"]
                self.input_fecha_fin.setDate(QDate(d2.year, d2.month, d2.day))
            
            # es_transferencia
            if "es_transferencia" in source:
                self.check_transferencia.setChecked(bool(source["es_transferencia"]))
        else:
            # valores por defecto para nuevo
            self.input_monto.setValue(0.0)
            self.input_fecha_inicio.setDate(QDate.currentDate())
            self.input_fecha_fin.setDate(QDate.currentDate())

        # Montar formulario
        form.addRow("Cuenta:", self.combo_cuenta)
        form.addRow("Descripción:", self.input_desc)
        form.addRow("Monto:", self.input_monto)
        form.addRow("Frecuencia:", self.combo_freq)
        form.addRow("Fecha inicio:", self.input_fecha_inicio)
        form.addRow("Fecha fin (opcional):", self.input_fecha_fin)
        form.addRow("", self.check_transferencia)

        layout.addLayout(form)

        # Botones de fijación (solo en modo edición)
        if self.fixed_id and self.fixed_expense_obj:
            hoy = date.today()
            fecha_fin = self.fixed_expense_obj.fecha_fin
            
            # Crear frame para botones de fijación
            fix_frame = QFrame()
            fix_frame.setFrameStyle(QFrame.Box | QFrame.Raised)
            fix_layout = QVBoxLayout(fix_frame)
            
            lbl_fix = QLabel("<b>Opciones de Fijación:</b>")
            fix_layout.addWidget(lbl_fix)
            
            # Botón 1: Si el gasto ha finalizado
            if fecha_fin and fecha_fin < hoy:
                btn_fix_all = QPushButton("🔒 Fijar todos los periodos (gasto finalizado)")
                btn_fix_all.setToolTip("Convierte todas las ocurrencias en transacciones individuales y elimina el gasto recurrente")
                btn_fix_all.clicked.connect(self.on_fix_all_periods)
                fix_layout.addWidget(btn_fix_all)
            
            # Botón 2: Si el gasto está activo
            elif not fecha_fin or fecha_fin >= hoy:
                btn_fix_past = QPushButton("🔒 Fijar periodos pasados y modificar importe futuro")
                btn_fix_past.setToolTip("Convierte las ocurrencias pasadas en transacciones y permite cambiar el importe para el futuro")
                btn_fix_past.clicked.connect(self.on_fix_past_periods)
                fix_layout.addWidget(btn_fix_past)
            
            layout.addWidget(fix_frame)

        # Botones OK/Cancel
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def get_values(self):
        # fecha_fin: si no se editó se devolverá la fecha del widget (puedes adaptar para None si quieres)
        fecha_fin = self.input_fecha_fin.date().toPython() if self.input_fecha_fin.date() else None
        return {
            "cuenta_id": int(self.combo_cuenta.currentData()),
            "descripcion": self.input_desc.text().strip(),
            "monto": float(self.input_monto.value()),
            "frecuencia": self.combo_freq.currentText(),
            "fecha_inicio": self.input_fecha_inicio.date().toPython(),
            "fecha_fin": fecha_fin,
            "es_transferencia": 1 if self.check_transferencia.isChecked() else 0
        }
    
    def on_fix_all_periods(self):
        """Fijar todos los periodos de un gasto recurrente finalizado"""
        if not self.fixed_expense_obj or not self.session:
            QMessageBox.warning(self, "Error", "No hay datos suficientes para fijar periodos")
            return
        
        reply = QMessageBox.question(self, "Confirmar", 
                                     f"¿Convertir todas las ocurrencias de '{self.fixed_expense_obj.descripcion}' en transacciones individuales?\n\n"
                                     "El gasto recurrente se eliminará tras crear las transacciones.",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        
        try:
            # Generar todas las ocurrencias
            ocurrencias = self._generar_ocurrencias(
                self.fixed_expense_obj.fecha_inicio,
                self.fixed_expense_obj.fecha_fin or date.today(),
                self.fixed_expense_obj.frecuencia
            )
            
            # Crear transacciones
            count = 0
            for fecha_ocurrencia in ocurrencias:
                tx = Transaction(
                    cuenta_id=self.fixed_expense_obj.cuenta_id,
                    fecha=fecha_ocurrencia,
                    descripcion=f"{self.fixed_expense_obj.descripcion} (fijado)",
                    monto=float(self.fixed_expense_obj.monto)
                )
                self.session.add(tx)
                count += 1
            
            # Eliminar el gasto recurrente
            self.session.delete(self.fixed_expense_obj)
            self.session.commit()
            
            QMessageBox.information(self, "Éxito", 
                                   f"Se crearon {count} transacciones y se eliminó el gasto recurrente.")
            self.reject()  # Cerrar diálogo
            
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudieron fijar los periodos: {e}")
    
    def on_fix_past_periods(self):
        """Fijar periodos pasados y permitir modificar el importe futuro"""
        if not self.fixed_expense_obj or not self.session:
            QMessageBox.warning(self, "Error", "No hay datos suficientes para fijar periodos")
            return
        
        hoy = date.today()
        
        # Solicitar nuevo importe para el futuro
        from PySide6.QtWidgets import QInputDialog
        nuevo_monto, ok = QInputDialog.getDouble(
            self, 
            "Nuevo importe",
            f"Importe actual: {float(self.fixed_expense_obj.monto):.2f}€\n\nIntroduce el nuevo importe para periodos futuros:",
            value=float(self.fixed_expense_obj.monto),
            decimals=2
        )
        
        if not ok:
            return
        
        reply = QMessageBox.question(self, "Confirmar", 
                                     f"¿Fijar periodos pasados de '{self.fixed_expense_obj.descripcion}' como transacciones?\n\n"
                                     f"Importe actual: {float(self.fixed_expense_obj.monto):.2f}€\n"
                                     f"Nuevo importe futuro: {nuevo_monto:.2f}€\n\n"
                                     "Los periodos futuros usarán el nuevo importe.",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        
        try:
            # Generar todas las ocurrencias desde el inicio hasta hoy
            todas_ocurrencias = self._generar_ocurrencias(
                self.fixed_expense_obj.fecha_inicio,
                hoy,
                self.fixed_expense_obj.frecuencia
            )
            
            # Filtrar solo las que son pasadas (< hoy)
            ocurrencias_pasadas = [f for f in todas_ocurrencias if f < hoy]
            
            # Crear transacciones para periodos pasados
            count = 0
            for fecha_ocurrencia in ocurrencias_pasadas:
                tx = Transaction(
                    cuenta_id=self.fixed_expense_obj.cuenta_id,
                    fecha=fecha_ocurrencia,
                    descripcion=f"{self.fixed_expense_obj.descripcion} (fijado)",
                    monto=float(self.fixed_expense_obj.monto)
                )
                self.session.add(tx)
                count += 1
            
            # Calcular la siguiente fecha futura según el patrón de frecuencia
            # Buscar la primera ocurrencia >= hoy
            siguiente_fecha = None
            for f in todas_ocurrencias:
                if f >= hoy:
                    siguiente_fecha = f
                    break
            
            # Si no hay ninguna ocurrencia futura en la lista, calcular la siguiente
            if siguiente_fecha is None:
                # Partir de la última ocurrencia pasada y calcular la siguiente
                if ocurrencias_pasadas:
                    ultima_pasada = ocurrencias_pasadas[-1]
                else:
                    ultima_pasada = self.fixed_expense_obj.fecha_inicio
                
                siguiente_fecha = self._calcular_siguiente_ocurrencia(ultima_pasada, self.fixed_expense_obj.frecuencia)
            
            # Actualizar el gasto recurrente
            self.fixed_expense_obj.fecha_inicio = siguiente_fecha
            self.fixed_expense_obj.monto = Decimal(str(nuevo_monto))
            self.session.add(self.fixed_expense_obj)
            
            self.session.commit()
            
            QMessageBox.information(self, "Éxito", 
                                   f"Se crearon {count} transacciones para periodos pasados.\n"
                                   f"El gasto recurrente continuará desde {format_date_str(siguiente_fecha)} con el nuevo importe.")
            
            # Actualizar valores en el diálogo
            self.input_fecha_inicio.setDate(QDate(siguiente_fecha.year, siguiente_fecha.month, siguiente_fecha.day))
            self.input_monto.setValue(nuevo_monto)
            
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudieron fijar los periodos: {e}")
    
    def _generar_ocurrencias(self, fecha_inicio, fecha_fin, frecuencia):
        """Genera lista de fechas según la frecuencia"""
        ocurrencias = []
        fecha_actual = fecha_inicio
        
        while fecha_actual <= fecha_fin:
            ocurrencias.append(fecha_actual)
            
            # Calcular siguiente ocurrencia
            if frecuencia == 'semanal':
                fecha_actual += timedelta(weeks=1)
            elif frecuencia == 'mensual':
                fecha_actual += relativedelta(months=1)
            elif frecuencia == 'trimestral':
                fecha_actual += relativedelta(months=3)
            elif frecuencia == 'semestral':
                fecha_actual += relativedelta(months=6)
            elif frecuencia == 'anual':
                fecha_actual += relativedelta(years=1)
            else:
                break
        
        return ocurrencias
    
    def _calcular_siguiente_ocurrencia(self, desde_fecha, frecuencia):
        """Calcula la siguiente ocurrencia después de una fecha dada"""
        if frecuencia == 'semanal':
            return desde_fecha + timedelta(weeks=1)
        elif frecuencia == 'mensual':
            return desde_fecha + relativedelta(months=1)
        elif frecuencia == 'trimestral':
            return desde_fecha + relativedelta(months=3)
        elif frecuencia == 'semestral':
            return desde_fecha + relativedelta(months=6)
        elif frecuencia == 'anual':
            return desde_fecha + relativedelta(years=1)
        else:
            return desde_fecha + timedelta(days=1)

        

class AdjustmentDialog(QDialog):
    def __init__(self, parent=None, cuentas=None, adj=None):
        super().__init__(parent)
        self.setWindowTitle("Ajuste")
        self.setModal(True)

        # Guardamos las cuentas recibidas (lista de tuplas (id, nombre))
        self.cuentas = cuentas or []

        # --- Widgets ---
        layout = QFormLayout(self)

        # Combo de cuentas
        self.combo_cuenta = QComboBox()
        for cid, nombre in self.cuentas:
            self.combo_cuenta.addItem(nombre, cid)
        layout.addRow("Cuenta:", self.combo_cuenta)

        # Fecha
        self.input_fecha = QDateEdit()
        setup_date_edit(self.input_fecha)
        self.input_fecha.setCalendarPopup(True)
        self.input_fecha.setDate(QDate.currentDate())
        layout.addRow("Fecha:", self.input_fecha)

        # Monto
        self.input_monto = QLineEdit()
        self.input_monto.setPlaceholderText("Ej: -100.50")
        layout.addRow("Monto:", self.input_monto)

        # Descripción
        self.input_desc = QLineEdit()
        layout.addRow("Descripción:", self.input_desc)

        # Botones
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addRow(btns)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        # Si estamos editando un ajuste existente, cargamos sus valores
        if adj:
            self.load_from_adj(adj)

    def load_from_adj(self, adj):
        """Carga los valores del ajuste en el diálogo."""
        idx = self.combo_cuenta.findData(adj.cuenta_id)
        if idx >= 0:
            self.combo_cuenta.setCurrentIndex(idx)
        if adj.fecha:
            self.input_fecha.setDate(adj.fecha)
        self.input_monto.setText(str(adj.monto_ajuste))
        self.input_desc.setText(adj.descripcion or "")

    def get_values(self):
        """Devuelve los valores introducidos en formato dict."""
        from decimal import Decimal

        cuenta_id = self.combo_cuenta.currentData()
        if cuenta_id is None:
            raise ValueError("Debe seleccionarse una cuenta")

        monto_text = self.input_monto.text().strip()
        if not monto_text:
            raise ValueError("El monto no puede estar vacío")

        try:
            monto = Decimal(monto_text)
        except Exception:
            raise ValueError("Monto inválido (usa números, puede ser negativo)")

        fecha = self.input_fecha.date().toPython()
        descripcion = self.input_desc.text().strip()

        return {
            "cuenta_id": cuenta_id,
            "fecha": fecha,
            "monto": monto,
            "descripcion": descripcion
        }
    
class MortgageDialog(QDialog):
    def __init__(self, parent=None, mortgage=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo Préstamo" if mortgage is None else "Editar Préstamo")
        self.resize(420, 260)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.input_nombre = QLineEdit()
        self.input_tipo = QComboBox()
        self.input_tipo.addItems(["fijo", "variable"])
        self.input_fecha_inicio = QDateEdit()
        setup_date_edit(self.input_fecha_inicio)
        self.input_fecha_inicio.setCalendarPopup(True)
        self.input_fecha_inicio.setDate(QDate.currentDate())

        self.input_capital = QDoubleSpinBox()
        self.input_capital.setRange(0, 1_000_000_000)
        self.input_capital.setDecimals(2)
        self.input_capital.setSingleStep(1000)

        self.input_cuotas = QSpinBox()
        self.input_cuotas.setRange(1, 600 * 12)
        self.input_cuotas.setValue(240)
        self.input_interes = QDoubleSpinBox()
        self.input_interes.setRange(0, 100)  # 0% a 100%
        self.input_interes.setDecimals(2)
        self.valor_actual_input = QLineEdit()
       
        

        form.addRow("Nombre:", self.input_nombre)
        form.addRow("Tipo:", self.input_tipo)
        form.addRow("Fecha inicio:", self.input_fecha_inicio)
        form.addRow("Capital inicial:", self.input_capital)
        form.addRow("Interés anual (%):", self.input_interes)
        form.addRow("Cuotas (meses):", self.input_cuotas)
        form.addRow("Valor actual de la propiedad :", self.valor_actual_input)

        layout.addLayout(form)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

        # --- si se pasa un préstamo, se cargan los datos ---
        if mortgage:
            self.input_nombre.setText(mortgage.nombre or "")
            idx = self.input_tipo.findText(mortgage.tipo or "fijo")
            self.input_tipo.setCurrentIndex(idx if idx >= 0 else 0)
            self.input_fecha_inicio.setDate(mortgage.fecha_inicio)
            self.input_capital.setValue(float(mortgage.capital_inicial))
            self.input_cuotas.setValue(int(mortgage.cuotas_totales))
            self.input_capital.setValue(float(mortgage.valor_actual_propiedad))
    def get_values(self):
        """Devuelve los valores en el mismo formato esperado por admin_ui."""
        return {
            "nombre": self.input_nombre.text().strip(),
            "tipo": self.input_tipo.currentText(),
            "fecha_inicio": self.input_fecha_inicio.date().toPython(),
            "capital_inicial": float(self.input_capital.value()),
            "cuotas_totales": int(self.input_cuotas.value()),
             "interes_anual": float(self.input_interes.value()),
             "valor_actual_propiedad": float(self.valor_actual_input.value()),

        }
class MortgagePeriodDialog(QDialog):
    def __init__(self, parent=None, period=None):
        super().__init__(parent)
        self.period = period
        self.setWindowTitle("Editar periodo de amortización")
        self.resize(400, 220)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.input_inicio = QDateEdit()
        setup_date_edit(self.input_inicio)
        self.input_inicio.setCalendarPopup(True)
        self.input_inicio.setEnabled(False)

        self.input_fin = QDateEdit()
        setup_date_edit(self.input_fin)
        self.input_fin.setCalendarPopup(True)
        self.input_fin.setEnabled(False)

        self.input_capital_inicial = QDoubleSpinBox()
        self.input_capital_inicial.setRange(0, 1_000_000_000)
        self.input_capital_inicial.setDecimals(2)
        self.input_capital_inicial.setEnabled(False)

        self.input_capital_final = QDoubleSpinBox()
        self.input_capital_final.setRange(0, 1_000_000_000)
        self.input_capital_final.setDecimals(2)

        self.input_interes = QDoubleSpinBox()
        self.input_interes.setRange(0, 100)
        self.input_interes.setDecimals(3)
        self.input_interes.setSuffix(" %")

        form.addRow("Inicio:", self.input_inicio)
        form.addRow("Fin:", self.input_fin)
        form.addRow("Capital inicial:", self.input_capital_inicial)
        form.addRow("Capital final:", self.input_capital_final)
        form.addRow("Interés (%):", self.input_interes)
        layout.addLayout(form)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

        if period:
            self._load_values(period)

    def _load_values(self, p):
        self.input_inicio.setDate(QDate(p.fecha_inicio.year, p.fecha_inicio.month, p.fecha_inicio.day))
        self.input_fin.setDate(QDate(p.fecha_fin.year, p.fecha_fin.month, p.fecha_fin.day))
        self.input_capital_inicial.setValue(float(p.capital_inicio))
        self.input_capital_final.setValue(float(p.capital_fin))
        self.input_interes.setValue(float(p.interes))

    def get_values(self):
        return {
            "capital_fin": float(self.input_capital_final.value()),
            "interes": float(self.input_interes.value()),
        }
class PlanDialog(QDialog):
    def __init__(self, parent=None, plan=None):
        super().__init__(parent)
        self.setWindowTitle("Plan Acciones" if plan is None else "Editar Plan Acciones")
        self.resize(420, 160)
        layout = QFormLayout(self)

        self.input_nombre = QLineEdit()
        self.input_desc = QTextEdit()
        self.input_desc.setFixedHeight(60)

        if plan:
            self.input_nombre.setText(plan.nombre or "")
            self.input_desc.setPlainText(plan.descripcion or "")

        layout.addRow("Nombre:", self.input_nombre)
        layout.addRow("Descripción:", self.input_desc)

        from PySide6.QtWidgets import QDialogButtonBox
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addRow(bb)

    def get_values(self):
        return {
            "nombre": self.input_nombre.text().strip(),
            "descripcion": self.input_desc.toPlainText().strip()
        }

class HoldingDialog(QDialog):
    def __init__(self, parent=None, holding=None, plans=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo Holding" if holding is None else "Editar Holding")
        self.resize(420, 180)
        layout = QFormLayout(self)

        self.combo_plan = QComboBox()
        self.combo_plan.addItem("— ninguno —", None)
        if plans:
            for p in plans:
                self.combo_plan.addItem(f"{p.id} - {p.nombre}", p.id)
        self.input_ticker = QLineEdit()
        self.input_exchange = QLineEdit()
        self.input_moneda = QLineEdit()
        self.input_moneda.setText("USD")

        if holding:
            # seleccionar plan si lo tiene
            if holding.plan_id:
                idx = self.combo_plan.findData(holding.plan_id)
                if idx >= 0:
                    self.combo_plan.setCurrentIndex(idx)
            self.input_ticker.setText(holding.ticker or "")
            self.input_exchange.setText(holding.exchange or "")
            self.input_moneda.setText(holding.moneda or "USD")

        layout.addRow("Plan:", self.combo_plan)
        layout.addRow("Ticker:", self.input_ticker)
        layout.addRow("Exchange:", self.input_exchange)
        layout.addRow("Moneda:", self.input_moneda)

        from PySide6.QtWidgets import QDialogButtonBox
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addRow(bb)

    def get_values(self):
        return {
            "plan_id": self.combo_plan.currentData(),
            "ticker": self.input_ticker.text().strip(),
            "exchange": self.input_exchange.text().strip(),
            "moneda": self.input_moneda.text().strip() or "USD"
        }
    
class HoldingPurchaseDialog(QDialog):
    def __init__(self, parent=None, purchase=None, holdings=None):
        super().__init__(parent)
        self.setWindowTitle("Nueva Compra" if purchase is None else "Editar Compra")
        self.resize(520, 220)
        layout = QFormLayout(self)

        # Combo: recibimos lista de tuplas (id, ticker, plan_nombre) o instancias (pero mejor tuplas)
        self.combo_holding = QComboBox()
        if holdings:
            for h in holdings:
                if isinstance(h, (tuple, list)):
                    try:
                        id_, ticker, plan_nombre = h
                    except Exception:
                        id_ = h[0]
                        ticker = h[1] if len(h) > 1 else ""
                        plan_nombre = h[2] if len(h) > 2 else ""
                else:
                    id_ = getattr(h, "id", None)
                    ticker = getattr(h, "ticker", "")
                    plan_nombre = getattr(getattr(h, "plan", None), "nombre", "") or ""

                label = f"{id_} - {ticker} ({plan_nombre})"
                self.combo_holding.addItem(label, id_)

        self.input_fecha = QDateEdit()
        setup_date_edit(self.input_fecha)
        self.input_fecha.setCalendarPopup(True)
        self.input_fecha.setDate(QDate.currentDate())

        self.input_cantidad = QDoubleSpinBox()
        self.input_cantidad.setDecimals(6)
        self.input_cantidad.setRange(0, 10_000_000)

        self.input_precio = QDoubleSpinBox()
        self.input_precio.setDecimals(6)
        self.input_precio.setRange(0, 1_000_000_000)

        self.input_nota = QLineEdit()

        # Si estamos editando, rellenamos campos con los valores pasados (purchase puede ser dict simple)
        if purchase:
            # purchase puede ser dict {holding_id, fecha, cantidad, precio_unitario, nota}
            holding_id = purchase.get("holding_id") if isinstance(purchase, dict) else getattr(purchase, "holding_id", None)
            if holding_id is not None:
                idx = self.combo_holding.findData(int(holding_id))
                if idx >= 0:
                    self.combo_holding.setCurrentIndex(idx)

            pf = purchase.get("fecha") if isinstance(purchase, dict) else getattr(purchase, "fecha", None)
            if pf:
                self.input_fecha.setDate(QDate(pf.year, pf.month, pf.day))

            cantidad = purchase.get("cantidad") if isinstance(purchase, dict) else getattr(purchase, "cantidad", None)
            if cantidad is not None:
                self.input_cantidad.setValue(float(cantidad))

            precio = purchase.get("precio_unitario") if isinstance(purchase, dict) else getattr(purchase, "precio_unitario", None)
            if precio is not None:
                self.input_precio.setValue(float(precio))

            nota = purchase.get("nota") if isinstance(purchase, dict) else getattr(purchase, "nota", None)
            self.input_nota.setText(nota or "")

        layout.addRow("Holding:", self.combo_holding)
        layout.addRow("Fecha:", self.input_fecha)
        layout.addRow("Cantidad:", self.input_cantidad)
        layout.addRow("Precio unit.:", self.input_precio)
        layout.addRow("Nota:", self.input_nota)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addRow(bb)

    def get_values(self):
        holding_id = self.combo_holding.currentData()
        qdate = self.input_fecha.date()
        fecha_py = date(qdate.year(), qdate.month(), qdate.day())
        return {
            "holding_id": int(holding_id) if holding_id is not None else None,
            "fecha": fecha_py,
            "cantidad": Decimal(str(self.input_cantidad.value())),
            "precio_unitario": Decimal(str(self.input_precio.value())),
            "nota": self.input_nota.text().strip()
        }

def generar_periodos_amortizacion(session, mortgage, interes_anual_inicial: Decimal = None):
        """
        Genera (o regenera) los MortgagePeriod para `mortgage` rellenando:
        - capital_inicio
        - capital_fin
        - interes_total (suma de intereses de los meses del periodo)
        - amortizacion_total (suma de amortizaciones de los meses del periodo)
        - interes (campo anual guardado en cada periodo)
        Esta función asume que los periodos se agrupan por años (o intervalos que ya tengas definidos
        en la tabla mortgage_period). Si no hay periodos creados, crea periodos anuales desde fecha_inicio
        hasta que se consuman todas las cuotas. Si ya existen, los sobreescribe.
        """
        # print("DEBUG: generar_periodos_amortizacion...")
        # parámetros del préstamo
        total_months = int(mortgage.cuotas_totales)
        capital = Decimal(str(mortgage.capital_inicial))

        # si el usuario indica un interés inicial distinto al del mortgage (opcional)
        if interes_anual_inicial is None:
            # si mortgage no guarda interés global, tomamos el proporcionado por el diálogo
            # pero por defecto usamos 0
            interes_anual_inicial = Decimal("0")

        # calculamos número de años (ceil)
        años = (total_months + 11) // 12

        # eliminamos periodos existentes desde el seleccionado en adelante
        #session.query(MortgagePeriod).filter(MortgagePeriod.mortgage_id == mortgage.id).delete()
        #session.flush()

        meses_restantes = total_months
        fecha_inicio = mortgage.fecha_inicio

        for año in range(años):
            meses_en_este_año = min(12, max(0, meses_restantes))

            fecha_ini_periodo = fecha_inicio + relativedelta(months=año * 12)
            fecha_fin_periodo = fecha_ini_periodo + relativedelta(months=meses_en_este_año) - timedelta(days=1)

            capital_inicio_periodo = capital

            # interés anual a usar para este periodo: tomamos parametro o mortgage/interes por defecto
            interes_anual = Decimal(str(interes_anual_inicial)) if interes_anual_inicial is not None else Decimal("0")

            # mensualización
            i_mensual = (interes_anual / Decimal("100")) / Decimal("12")

            # Calcular cuota mensual francesa usando **meses_restantes** (no solo meses_en_este_año)
            if meses_restantes <= 0:
                cuota_mensual = Decimal("0.00")
            else:
                if i_mensual == Decimal("0"):
                    cuota_mensual = (capital / Decimal(str(meses_restantes))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                else:
                    uno = Decimal("1")
                    pow_term = (uno + i_mensual) ** (Decimal(str(-meses_restantes)))
                    denom = (uno - pow_term)
                    if denom == Decimal("0"):
                        cuota_mensual = (capital / Decimal(str(meses_restantes))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    else:
                        cuota_mensual = ((capital * i_mensual) / denom).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            intereses_tot = Decimal("0.00")
            amortizacion_tot = Decimal("0.00")

            # Simular mes a mes dentro del periodo
            for _ in range(meses_en_este_año):
                if meses_restantes <= 0:
                    break

                interes_mes = (capital * i_mensual).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                amortizacion_mes = (cuota_mensual - interes_mes).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if amortizacion_mes < Decimal("0.00"):
                    amortizacion_mes = Decimal("0.00")

                intereses_tot += interes_mes
                amortizacion_tot += amortizacion_mes

                capital = (capital - amortizacion_mes).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if capital < Decimal("0.00"):
                    capital = Decimal("0.00")

                meses_restantes -= 1

            capital_fin_periodo = capital

            # crear periodo (usa MortgagePeriod tal como lo definiste; asegúrate de tener campos interes_total y amortizacion_total)
            period = MortgagePeriod(
                mortgage_id=mortgage.id,
                fecha_inicio=fecha_ini_periodo,
                fecha_fin=fecha_fin_periodo,
                capital_inicio=round(float(capital_inicio_periodo), 2),
                capital_fin=round(float(capital_fin_periodo), 2),
                interes=float(round(interes_anual, 6)),  # guardamos interés anual en el periodo
            )

            # asignar totales (si tu modelo define Decimal/Float ajusta tipos)
            # convertimos a Decimal->float para compatibilidad con Column(Float) o Decimal según modelo
            try:
                period.interes_total = float(intereses_tot)
                period.amortizacion_total = float(amortizacion_tot)
            except Exception:
                # si los campos son DECIMAL en SQLAlchemy, asigna Decimal directamente
                period.interes_total = intereses_tot
                period.amortizacion_total = amortizacion_tot

            session.add(period)

        # confirmamos
        session.commit()
def recalcular_desde_periodo(session, mortgage, period_edited):
        """
        Ajusta el flujo: tomamos capital_fin del periodo_editado como capital inicial
        y regeneramos los periodos posteriores usando el interés del periodo_editado
        (o el interés que tú decidas).
        """
        # print("DEBUG: recalcular_desde_periodo...")
        # Tomamos interés anual del periodo editado
        interes = Decimal(str(period_edited.interes))

        # Para conservar periodos anteriores usamos lógica similar a generar_periodos but starting from period_edited
        # Simplificación: borramos periodos siguientes y regeneramos a partir de period_edited.capital_fin
        # (puedes adaptar para preservar algunos datos)
        # borrar posteriores
        
        #session.query(MortgagePeriod).filter(
        #    MortgagePeriod.mortgage_id == mortgage.id,
        #    MortgagePeriod.fecha_inicio > period_edited.fecha_inicio
        #).delete()
        #session.flush()

        borrar_periodos_desde(session, mortgage.id, period_edited.fecha_inicio)
        # crear un "pseudo mortgage" con capital inicial = period_edited.capital_fin y cuotas restantes
        meses_transcurridos = (period_edited.fecha_inicio.year - mortgage.fecha_inicio.year) * 12 + \
                            (period_edited.fecha_inicio.month - mortgage.fecha_inicio.month) + \
                            ( (period_edited.fecha_fin.year - period_edited.fecha_inicio.year) * 12 + (period_edited.fecha_fin.month - period_edited.fecha_inicio.month) + 1 )

        # calcular meses consumidos exactos hasta el fin del periodo editado => ajustar remaining
        meses_consumidos_hasta_fin = (period_edited.fecha_fin.year - mortgage.fecha_inicio.year) * 12 + (period_edited.fecha_fin.month - mortgage.fecha_inicio.month) + 1
        cuotas_totales = int(mortgage.cuotas_totales)
        meses_restantes = cuotas_totales - meses_consumidos_hasta_fin

        # construir temporal mortgage-like para generar los periodos restantes:
        temp_m = type('T', (), {})()
        temp_m.id = mortgage.id
        temp_m.capital_inicial = float(period_edited.capital_fin)  # valor inicial para la regeneración
        temp_m.cuotas_totales = meses_restantes
        temp_m.fecha_inicio = period_edited.fecha_fin + relativedelta(days=1)

        # llamar a la función generadora pero adaptada: generará periodos desde fecha_inicio de temp_m en bloques anuales
        generar_periodos_amortizacion(session, temp_m, interes_anual_inicial=interes)
# módulo amortizacion_utils.py o dentro del mismo archivo de AdminWindow

# borrar solo periodos desde cierto periodo
def borrar_periodos_desde(session, mortgage_id, fecha_inicio):
    print("borrar_periodos_desde...")
    session.query(MortgagePeriod).filter(
        MortgagePeriod.mortgage_id == mortgage_id,
        MortgagePeriod.fecha_inicio > fecha_inicio
    ).delete()
    session.flush()


# -------------------------
# DIÁLOGO DE TRANSFERENCIA
# -------------------------
class TransferenciaDialog(QDialog):
    """Diálogo para crear una transferencia entre dos cuentas"""
    def __init__(self, parent=None, cuentas=None):
        super().__init__(parent)
        self.setWindowTitle("Nueva Transferencia")
        self.cuentas = cuentas or []
        
        layout = QFormLayout(self)
        
        # Cuenta origen
        self.combo_origen = QComboBox()
        for cid, nombre in self.cuentas:
            self.combo_origen.addItem(nombre, cid)
        layout.addRow("Cuenta origen:", self.combo_origen)
        
        # Cuenta destino
        self.combo_destino = QComboBox()
        for cid, nombre in self.cuentas:
            self.combo_destino.addItem(nombre, cid)
        layout.addRow("Cuenta destino:", self.combo_destino)
        
        # Fecha (por defecto hoy)
        self.date_edit = QDateEdit()
        setup_date_edit(self.date_edit)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        layout.addRow("Fecha:", self.date_edit)
        
        # Importe
        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setRange(0.01, 999999999.99)
        self.spin_monto.setDecimals(2)
        self.spin_monto.setValue(0.0)
        self.spin_monto.setPrefix("€ ")
        layout.addRow("Importe:", self.spin_monto)
        
        # Descripción/Concepto
        self.edit_desc = QLineEdit()
        self.edit_desc.setPlaceholderText("Ej: Transferencia entre cuentas")
        layout.addRow("Concepto:", self.edit_desc)
        
        # Info label
        info_label = QLabel("Nota: Se crearán automáticamente dos transacciones marcadas como transferencia")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addRow("", info_label)
        
        # Botones
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)
    
    def get_values(self):
        """Devuelve dict con los valores del diálogo"""
        fecha = self.date_edit.date().toPython()
        descripcion = self.edit_desc.text().strip()
        if not descripcion:
            descripcion = "Transferencia entre cuentas"
        
        return {
            "cuenta_origen_id": self.combo_origen.currentData(),
            "cuenta_destino_id": self.combo_destino.currentData(),
            "fecha": fecha,
            "monto": self.spin_monto.value(),
            "descripcion": descripcion
        }
