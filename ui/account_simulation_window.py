from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
                               QFormLayout, QDateEdit, QGroupBox, QComboBox, QLabel,
                               QFileDialog)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from datetime import timedelta
import csv
from models.account import Account
from models.transaction import Transaction
from models.adjustment import Adjustment
from models.fixed_expense import FixedExpense
from models.simulation_variable import SimulationVariable
from utils.reconciler import calcular_balance_cuenta
from sqlalchemy import select, or_
from ui.variables_dialog import VariablesDialog


class AccountSimulationWindow(QDialog):
    """Ventana de simulación de movimientos detallados de una cuenta"""
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Simulación de Cuenta - Movimientos Detallados")
        self.resize(1000, 700)
        
        self.resultados_cache = None  # Cache para exportar
        self.cuenta_actual = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # --- Panel de configuración ---
        config_group = QGroupBox("Configuración")
        config_layout = QFormLayout()
        
        # Selector de cuenta
        self.cuenta_combo = QComboBox()
        try:
            cuentas = self.session.query(Account).order_by(Account.nombre).all()
            for cuenta in cuentas:
                self.cuenta_combo.addItem(cuenta.nombre, cuenta.id)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al cargar cuentas: {e}")
        
        config_layout.addRow("Cuenta:", self.cuenta_combo)
        
        # Fecha inicio
        self.fecha_inicio = QDateEdit()
        self.fecha_inicio.setCalendarPopup(True)
        self.fecha_inicio.setDate(QDate.currentDate().addMonths(-1))
        config_layout.addRow("Fecha Inicio:", self.fecha_inicio)
        
        # Fecha fin
        self.fecha_fin = QDateEdit()
        self.fecha_fin.setCalendarPopup(True)
        self.fecha_fin.setDate(QDate.currentDate().addMonths(1))
        config_layout.addRow("Fecha Fin:", self.fecha_fin)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # --- Botones de acción ---
        action_layout = QHBoxLayout()
        
        self.variables_btn = QPushButton("Gestionar Variables")
        self.variables_btn.clicked.connect(self.open_variables_dialog)
        action_layout.addWidget(self.variables_btn)
        
        action_layout.addStretch()
        
        self.export_btn = QPushButton("📄 Exportar CSV")
        self.export_btn.clicked.connect(self.export_to_csv)
        self.export_btn.setEnabled(False)  # Deshabilitado hasta que haya resultados
        action_layout.addWidget(self.export_btn)
        
        self.simulate_btn = QPushButton("Ejecutar Simulación")
        self.simulate_btn.clicked.connect(self.run_simulation)
        action_layout.addWidget(self.simulate_btn)
        
        layout.addLayout(action_layout)
        
        # --- Resumen del saldo ---
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("font-weight: bold; padding: 8px; background-color: #e8f4f8; border-radius: 4px;")
        layout.addWidget(self.summary_label)
        
        # --- Tabla de resultados ---
        results_label = QLabel("Movimientos:")
        layout.addWidget(results_label)
        
        self.results_table = QTableWidget()
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        layout.addWidget(self.results_table)
        
        # --- Botón cerrar ---
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        close_layout.addWidget(close_btn)
        
        layout.addLayout(close_layout)
    
    def open_variables_dialog(self):
        """Abrir el diálogo de gestión de variables"""
        dialog = VariablesDialog(self.session, parent=self)
        dialog.exec()
    
    def export_to_csv(self):
        """Exportar los resultados de la simulación a un archivo CSV"""
        if not self.resultados_cache or not self.cuenta_actual:
            QMessageBox.warning(self, "Aviso", "No hay resultados para exportar. Ejecuta primero una simulación.")
            return
        
        # Diálogo para seleccionar ubicación del archivo
        cuenta_nombre = self.cuenta_actual.nombre.replace(' ', '_').replace('/', '-')
        default_filename = f"simulacion_{cuenta_nombre}.csv"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar simulación como CSV",
            default_filename,
            "Archivos CSV (*.csv);;Todos los archivos (*.*)"
        )
        
        if not file_path:
            return  # Usuario canceló
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')
                
                # Escribir información de la cuenta
                writer.writerow([f"Cuenta: {self.cuenta_actual.nombre}"])
                writer.writerow([f"Saldo Inicial: {self.resultados_cache['saldo_inicial']:.2f}"])
                writer.writerow([f"Saldo Final: {self.resultados_cache['saldo_final']:.2f}"])
                writer.writerow([])
                
                # Escribir encabezados
                writer.writerow(['Fecha', 'Tipo', 'Descripción', 'Importe', 'Saldo', 'Es Transferencia'])
                
                # Escribir movimientos
                for mov in self.resultados_cache['detalle']:
                    writer.writerow([
                        mov['fecha'].strftime('%d/%m/%Y'),
                        mov['tipo'].capitalize(),
                        mov['concepto'],
                        f"{float(mov['importe']):.2f}",
                        f"{float(mov['saldo']):.2f}",
                        'Sí' if mov.get('es_transferencia') else 'No'
                    ])
            
            QMessageBox.information(self, "Éxito", f"Simulación exportada correctamente a:\n{file_path}")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo exportar el archivo: {e}")
    
    def calcular_movimientos_con_saldo(self, cuenta_id, fecha_inicio_param, fecha_fin_param):
        """
        Calcula movimientos detallados con saldo acumulado entre dos fechas.
        Incluye variables de simulación activas.
        Devuelve diccionario con 'saldo_inicial', 'detalle', 'saldo_final'
        """
        cuenta = self.session.get(Account, cuenta_id)
        if not cuenta:
            raise ValueError(f"Cuenta {cuenta_id} no encontrada")
        
        # Calcular saldo inicial (un día antes de la fecha de inicio)
        dia_anterior = fecha_inicio_param - timedelta(days=1)
        saldo_inicial = Decimal(str(calcular_balance_cuenta(self.session, cuenta_id, dia_anterior)))
        
        movimientos = []
        
        # --- Ajustes en rango ---
        ajustes = self.session.scalars(
            select(Adjustment)
            .where(
                Adjustment.cuenta_id == cuenta_id,
                Adjustment.fecha >= fecha_inicio_param,
                Adjustment.fecha <= fecha_fin_param
            )
        ).all()
        for adj in ajustes:
            movimientos.append({
                "fecha": adj.fecha,
                "concepto": adj.descripcion or "Ajuste",
                "importe": Decimal(str(adj.monto_ajuste)),
                "tipo": "ajuste",
                "es_transferencia": 0
            })
        
        # --- Transacciones puntuales en rango ---
        transacciones = self.session.scalars(
            select(Transaction)
            .where(
                Transaction.cuenta_id == cuenta_id,
                Transaction.fecha >= fecha_inicio_param,
                Transaction.fecha <= fecha_fin_param
            )
        ).all()
        for t in transacciones:
            movimientos.append({
                "fecha": t.fecha,
                "concepto": t.descripcion or "Transacción",
                "importe": Decimal(str(t.monto)),
                "tipo": "puntual",
                "es_transferencia": getattr(t, 'es_transferencia', 0)
            })
        
        # --- Gastos/ingresos fijos: generar ocurrencias dentro del rango ---
        fijos = self.session.scalars(
            select(FixedExpense)
            .where(
                FixedExpense.cuenta_id == cuenta_id,
                FixedExpense.fecha_inicio <= fecha_fin_param,
                or_(
                    FixedExpense.fecha_fin == None,
                    FixedExpense.fecha_fin >= fecha_inicio_param
                )
            )
        ).all()
        
        for f in fijos:
            inicio = max(f.fecha_inicio, fecha_inicio_param)
            fin = f.fecha_fin if f.fecha_fin is not None else fecha_fin_param
            fin = min(fin, fecha_fin_param)
            
            ocurrencia = inicio
            while ocurrencia <= fin:
                movimientos.append({
                    "fecha": ocurrencia,
                    "concepto": f.descripcion or "Gasto/Ingreso Fijo",
                    "importe": Decimal(str(f.monto)),
                    "tipo": "fijo",
                    "es_transferencia": getattr(f, 'es_transferencia', 0)
                })
                
                # Avanzar según frecuencia
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
        
        # --- Variables de simulación activas para esta cuenta ---
        variables = self.session.query(SimulationVariable).filter_by(
            cuenta_id=cuenta_id,
            activo=1
        ).all()
        
        for variable in variables:
            # Si la variable tiene fecha de inicio, empezar desde esa fecha
            # Si no, empezar desde fecha_inicio_param
            fecha_var = variable.fecha_inicio if variable.fecha_inicio else fecha_inicio_param
            
            # Si la fecha de inicio de la variable es posterior al rango, saltarla
            if fecha_var > fecha_fin_param:
                continue
            
            # Si la fecha de inicio es anterior al rango de simulación, empezar desde fecha_inicio_param
            fecha_var = max(fecha_var, fecha_inicio_param)
            
            while fecha_var <= fecha_fin_param:
                movimientos.append({
                    "fecha": fecha_var,
                    "concepto": f"[Variable] {variable.descripcion}",
                    "importe": Decimal(str(variable.importe)),
                    "tipo": "variable",
                    "es_transferencia": 0
                })
                
                # Avanzar según frecuencia
                if variable.frecuencia == "semanal":
                    fecha_var += timedelta(weeks=1)
                elif variable.frecuencia == "mensual":
                    fecha_var += relativedelta(months=1)
                elif variable.frecuencia == "trimestral":
                    fecha_var += relativedelta(months=3)
                elif variable.frecuencia == "semestral":
                    fecha_var += relativedelta(months=6)
                elif variable.frecuencia == "anual":
                    fecha_var += relativedelta(years=1)
                else:
                    break
        
        # Ordenar movimientos por fecha y tipo
        tipo_orden = {"fijo": 1, "ajuste": 2, "puntual": 3, "variable": 4}
        movimientos.sort(key=lambda m: (m["fecha"], tipo_orden.get(m["tipo"], 99)))
        
        # Calcular saldo acumulado
        saldo_actual = saldo_inicial
        for mov in movimientos:
            saldo_actual += mov["importe"]
            mov["saldo"] = saldo_actual
        
        return {
            "saldo_inicial": saldo_inicial,
            "detalle": movimientos,
            "saldo_final": saldo_actual
        }
    
    def run_simulation(self):
        """Ejecutar la simulación y mostrar resultados"""
        try:
            # Validar cuenta seleccionada
            if self.cuenta_combo.count() == 0:
                QMessageBox.warning(self, "Error", "No hay cuentas disponibles")
                return
            
            cuenta_id = self.cuenta_combo.currentData()
            if not cuenta_id:
                QMessageBox.warning(self, "Error", "Selecciona una cuenta")
                return
            
            # Obtener cuenta
            cuenta = self.session.query(Account).filter_by(id=cuenta_id).first()
            if not cuenta:
                QMessageBox.warning(self, "Error", "Cuenta no encontrada")
                return
            
            # Validar fechas
            fecha_inicio = self.fecha_inicio.date().toPython()
            fecha_fin = self.fecha_fin.date().toPython()
            
            if fecha_inicio >= fecha_fin:
                QMessageBox.warning(self, "Error", "La fecha de inicio debe ser anterior a la fecha de fin")
                return
            
            # Ejecutar simulación
            resultados = self.calcular_movimientos_con_saldo(cuenta_id, fecha_inicio, fecha_fin)
            
            # Guardar en cache para exportar
            self.resultados_cache = resultados
            self.cuenta_actual = cuenta
            
            # Mostrar resultados
            self.display_results(resultados, cuenta)
            
            # Habilitar botón de exportar
            self.export_btn.setEnabled(True)
            
        except Exception as e:
            import traceback
            QMessageBox.warning(self, "Error", f"Error al ejecutar simulación: {e}\n\n{traceback.format_exc()}")
    
    def display_results(self, resultados, cuenta):
        """
        Mostrar resultados de la simulación en la tabla
        
        Args:
            resultados: dict con keys 'saldo_inicial', 'detalle', 'saldo_final'
            cuenta: Account object
        """
        if not resultados or not resultados.get('detalle'):
            self.results_table.setRowCount(0)
            self.summary_label.setText("No hay movimientos en el rango seleccionado")
            return
        
        # Mostrar resumen
        saldo_inicial = resultados['saldo_inicial']
        saldo_final = resultados['saldo_final']
        diferencia = saldo_final - saldo_inicial
        
        summary_text = (f"Cuenta: {cuenta.nombre} | "
                       f"Saldo Inicial: {float(saldo_inicial):,.2f} € | "
                       f"Saldo Final: {float(saldo_final):,.2f} € | "
                       f"Diferencia: {float(diferencia):+,.2f} €")
        self.summary_label.setText(summary_text)
        
        # Configurar columnas: Fecha, Tipo, Descripción, Importe, Saldo, Es Transferencia
        self.results_table.setColumnCount(6)
        headers = ['Fecha', 'Tipo', 'Descripción', 'Importe', 'Saldo', 'Transferencia']
        self.results_table.setHorizontalHeaderLabels(headers)
        
        # Llenar datos
        movimientos = resultados['detalle']
        self.results_table.setRowCount(len(movimientos))
        
        for row, mov in enumerate(movimientos):
            # Fecha
            fecha_str = mov['fecha'].strftime('%d/%m/%Y')
            fecha_item = QTableWidgetItem(fecha_str)
            self.results_table.setItem(row, 0, fecha_item)
            
            # Tipo
            tipo_str = mov['tipo'].capitalize()
            tipo_item = QTableWidgetItem(tipo_str)
            self.results_table.setItem(row, 1, tipo_item)
            
            # Descripción
            desc_item = QTableWidgetItem(mov['concepto'])
            self.results_table.setItem(row, 2, desc_item)
            
            # Importe
            importe = float(mov['importe'])
            importe_item = QTableWidgetItem(f"{importe:,.2f}")
            importe_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            # Colorear importe: verde si positivo, rojo si negativo
            if importe > 0:
                importe_item.setForeground(QColor(0, 128, 0))  # Verde
            elif importe < 0:
                importe_item.setForeground(QColor(200, 0, 0))  # Rojo
            
            self.results_table.setItem(row, 3, importe_item)
            
            # Saldo
            saldo = float(mov['saldo'])
            saldo_item = QTableWidgetItem(f"{saldo:,.2f}")
            saldo_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            # Colorear saldo en rojo si es negativo
            if saldo < 0:
                saldo_item.setBackground(QColor(255, 220, 220))  # Rojo claro
            
            self.results_table.setItem(row, 4, saldo_item)
            
            # Es Transferencia
            es_transferencia = mov.get('es_transferencia', 0)
            transfer_item = QTableWidgetItem('✓' if es_transferencia else '')
            transfer_item.setTextAlignment(Qt.AlignCenter)
            if es_transferencia:
                transfer_item.setBackground(QColor(230, 230, 250))  # Lavanda claro
            self.results_table.setItem(row, 5, transfer_item)
        
        # Ajustar tamaño de columnas
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Fecha
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Tipo
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)  # Descripción
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Importe
        self.results_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Saldo
        self.results_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Transferencia
