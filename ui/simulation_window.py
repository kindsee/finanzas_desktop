from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
                               QFormLayout, QDateEdit, QSpinBox, QGroupBox, QCheckBox,
                               QScrollArea, QWidget, QLabel, QFileDialog)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import csv
from models.account import Account
from models.simulation_variable import SimulationVariable
from utils.reconciler import calcular_balance_cuenta
from ui.variables_dialog import VariablesDialog


class SimulationWindow(QDialog):
    """Ventana principal de simulación de saldos"""
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Simulación de Saldos")
        self.resize(1200, 800)
        
        self.cuenta_checkboxes = {}
        self.resultados_cache = None  # Cache para exportar
        self.cuentas_cache = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # --- Panel de configuración ---
        config_group = QGroupBox("Configuración de Simulación")
        config_layout = QFormLayout()
        
        # Fecha inicio
        self.fecha_inicio = QDateEdit()
        self.fecha_inicio.setCalendarPopup(True)
        self.fecha_inicio.setDate(QDate.currentDate())
        config_layout.addRow("Fecha Inicio:", self.fecha_inicio)
        
        # Fecha fin
        self.fecha_fin = QDateEdit()
        self.fecha_fin.setCalendarPopup(True)
        self.fecha_fin.setDate(QDate.currentDate().addMonths(12))
        config_layout.addRow("Fecha Fin:", self.fecha_fin)
        
        # Intervalo de días
        self.intervalo_input = QSpinBox()
        self.intervalo_input.setRange(1, 365)
        self.intervalo_input.setValue(7)  # Por defecto semanal
        self.intervalo_input.setSuffix(" días")
        config_layout.addRow("Intervalo:", self.intervalo_input)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # --- Panel de cuentas ---
        cuentas_group = QGroupBox("Cuentas a Simular")
        cuentas_layout = QVBoxLayout()
        
        # Botón de seleccionar todas/ninguna
        select_buttons = QHBoxLayout()
        select_all_btn = QPushButton("Seleccionar Todas")
        select_all_btn.clicked.connect(self.select_all_accounts)
        select_buttons.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deseleccionar Todas")
        deselect_all_btn.clicked.connect(self.deselect_all_accounts)
        select_buttons.addWidget(deselect_all_btn)
        select_buttons.addStretch()
        
        cuentas_layout.addLayout(select_buttons)
        
        # Scroll area para checkboxes de cuentas
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(150)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        try:
            cuentas = self.session.query(Account).order_by(Account.nombre).all()
            for cuenta in cuentas:
                checkbox = QCheckBox(cuenta.nombre)
                checkbox.setChecked(True)  # Por defecto todas seleccionadas
                self.cuenta_checkboxes[cuenta.id] = checkbox
                scroll_layout.addWidget(checkbox)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al cargar cuentas: {e}")
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        cuentas_layout.addWidget(scroll)
        
        cuentas_group.setLayout(cuentas_layout)
        layout.addWidget(cuentas_group)
        
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
        
        # --- Tabla de resultados ---
        results_label = QLabel("Resultados:")
        layout.addWidget(results_label)
        
        self.results_table = QTableWidget()
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.results_table)
        
        # --- Botón cerrar ---
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        close_layout.addWidget(close_btn)
        
        layout.addLayout(close_layout)
    
    def select_all_accounts(self):
        """Seleccionar todas las cuentas"""
        for checkbox in self.cuenta_checkboxes.values():
            checkbox.setChecked(True)
    
    def deselect_all_accounts(self):
        """Deseleccionar todas las cuentas"""
        for checkbox in self.cuenta_checkboxes.values():
            checkbox.setChecked(False)
    
    def open_variables_dialog(self):
        """Abrir el diálogo de gestión de variables"""
        dialog = VariablesDialog(self.session, parent=self)
        dialog.exec()
    
    def export_to_csv(self):
        """Exportar los resultados de la simulación a un archivo CSV"""
        if not self.resultados_cache or not self.cuentas_cache:
            QMessageBox.warning(self, "Aviso", "No hay resultados para exportar. Ejecuta primero una simulación.")
            return
        
        # Diálogo para seleccionar ubicación del archivo
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar simulación como CSV",
            "simulacion_saldos.csv",
            "Archivos CSV (*.csv);;Todos los archivos (*.*)"
        )
        
        if not file_path:
            return  # Usuario canceló
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')
                
                # Escribir encabezados
                headers = ['Fecha']
                for cuenta in self.cuentas_cache:
                    headers.append(cuenta.nombre)
                headers.append('TOTAL')
                writer.writerow(headers)
                
                # Escribir datos
                for resultado in self.resultados_cache:
                    row = [resultado['fecha'].strftime('%d/%m/%Y')]
                    
                    total = 0.0
                    for cuenta in self.cuentas_cache:
                        saldo = resultado['saldos'].get(cuenta.id, 0.0)
                        total += saldo
                        row.append(f"{saldo:.2f}")
                    
                    row.append(f"{total:.2f}")
                    writer.writerow(row)
            
            QMessageBox.information(self, "Éxito", f"Simulación exportada correctamente a:\n{file_path}")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo exportar el archivo: {e}")
    
    def run_simulation(self):
        """Ejecutar la simulación y mostrar resultados"""
        try:
            # Validar fechas
            fecha_inicio = self.fecha_inicio.date().toPython()
            fecha_fin = self.fecha_fin.date().toPython()
            
            if fecha_inicio >= fecha_fin:
                QMessageBox.warning(self, "Error", "La fecha de inicio debe ser anterior a la fecha de fin")
                return
            
            # Obtener cuentas seleccionadas
            cuentas_seleccionadas = []
            for cuenta_id, checkbox in self.cuenta_checkboxes.items():
                if checkbox.isChecked():
                    cuenta = self.session.query(Account).filter_by(id=cuenta_id).first()
                    if cuenta:
                        cuentas_seleccionadas.append(cuenta)
            
            if not cuentas_seleccionadas:
                QMessageBox.warning(self, "Error", "Debes seleccionar al menos una cuenta")
                return
            
            intervalo = self.intervalo_input.value()
            
            # Obtener variables activas
            variables_activas = self.session.query(SimulationVariable).filter_by(activo=1).all()
            
            # Ejecutar simulación
            resultados = self.calculate_simulation(
                fecha_inicio, fecha_fin, intervalo,
                cuentas_seleccionadas, variables_activas
            )
            
            # Guardar en cache para exportar
            self.resultados_cache = resultados
            self.cuentas_cache = cuentas_seleccionadas
            
            # Mostrar resultados
            self.display_results(resultados, cuentas_seleccionadas)
            
            # Habilitar botón de exportar
            self.export_btn.setEnabled(True)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al ejecutar simulación: {e}")
    
    def calculate_simulation(self, fecha_inicio, fecha_fin, intervalo, cuentas, variables):
        """
        Calcular la simulación de saldos
        
        Args:
            fecha_inicio: datetime.date
            fecha_fin: datetime.date
            intervalo: int (días)
            cuentas: List[Account]
            variables: List[SimulationVariable]
        
        Returns:
            List[dict] con estructura: {'fecha': date, 'saldos': {cuenta_id: float}}
        """
        resultados = []
        fecha_actual = fecha_inicio
        
        # Diccionario para acumular efectos de variables por cuenta
        # {cuenta_id: {fecha: importe_acumulado}}
        efectos_variables = {cuenta.id: {} for cuenta in cuentas}
        
        # Pre-calcular efectos de variables para cada fecha
        for variable in variables:
            if variable.cuenta_id not in efectos_variables:
                continue
            
            # Si la variable tiene fecha de inicio, empezar desde esa fecha
            # Si no, empezar desde fecha_inicio de la simulación
            fecha_var = variable.fecha_inicio if variable.fecha_inicio else fecha_inicio
            
            # Si la fecha de inicio de la variable es posterior al rango, saltarla
            if fecha_var > fecha_fin:
                continue
            
            # Si la fecha de inicio es anterior al rango de simulación, empezar desde fecha_inicio
            fecha_var = max(fecha_var, fecha_inicio)
            
            while fecha_var <= fecha_fin:
                if fecha_var not in efectos_variables[variable.cuenta_id]:
                    efectos_variables[variable.cuenta_id][fecha_var] = Decimal('0')
                
                efectos_variables[variable.cuenta_id][fecha_var] += Decimal(str(variable.importe))
                
                # Calcular siguiente fecha según frecuencia
                if variable.frecuencia == 'semanal':
                    fecha_var += timedelta(days=7)
                elif variable.frecuencia == 'mensual':
                    fecha_var += relativedelta(months=1)
                elif variable.frecuencia == 'trimestral':
                    fecha_var += relativedelta(months=3)
                elif variable.frecuencia == 'semestral':
                    fecha_var += relativedelta(months=6)
                elif variable.frecuencia == 'anual':
                    fecha_var += relativedelta(years=1)
                else:
                    break  # Frecuencia desconocida
        
        # Calcular saldos en cada intervalo
        while fecha_actual <= fecha_fin:
            saldos = {}
            
            for cuenta in cuentas:
                # Obtener saldo base de la cuenta usando reconciler
                saldo_base = calcular_balance_cuenta(self.session, cuenta.id, fecha_actual)
                
                # Aplicar efectos acumulados de variables hasta esta fecha
                efecto_total = Decimal('0')
                for fecha_efecto, importe in efectos_variables[cuenta.id].items():
                    if fecha_efecto <= fecha_actual:
                        efecto_total += importe
                
                saldo_final = float(Decimal(str(saldo_base)) + efecto_total)
                saldos[cuenta.id] = saldo_final
            
            resultados.append({
                'fecha': fecha_actual,
                'saldos': saldos
            })
            
            fecha_actual += timedelta(days=intervalo)
        
        return resultados
    
    def display_results(self, resultados, cuentas):
        """
        Mostrar resultados de la simulación en la tabla
        
        Args:
            resultados: List[dict] con estructura {'fecha': date, 'saldos': {cuenta_id: float}}
            cuentas: List[Account]
        """
        if not resultados:
            self.results_table.setRowCount(0)
            return
        
        # Configurar columnas: Fecha + Cuentas + TOTAL
        num_columns = len(cuentas) + 2
        self.results_table.setColumnCount(num_columns)
        
        headers = ['Fecha']
        for cuenta in cuentas:
            headers.append(cuenta.nombre)
        headers.append('TOTAL')
        
        self.results_table.setHorizontalHeaderLabels(headers)
        
        # Llenar datos
        self.results_table.setRowCount(len(resultados))
        
        for row, resultado in enumerate(resultados):
            # Fecha
            fecha_str = resultado['fecha'].strftime('%d/%m/%Y')
            self.results_table.setItem(row, 0, QTableWidgetItem(fecha_str))
            
            # Saldos por cuenta
            total = 0.0
            for col, cuenta in enumerate(cuentas, start=1):
                saldo = resultado['saldos'].get(cuenta.id, 0.0)
                total += saldo
                
                item = QTableWidgetItem(f"{saldo:,.2f}")
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                # Colorear en rojo si es negativo
                if saldo < 0:
                    item.setBackground(QColor(255, 200, 200))  # Rojo claro
                
                self.results_table.setItem(row, col, item)
            
            # Total
            total_item = QTableWidgetItem(f"{total:,.2f}")
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # Resaltar columna total en negrita
            font = total_item.font()
            font.setBold(True)
            total_item.setFont(font)
            
            # Colorear en rojo si el total es negativo
            if total < 0:
                total_item.setBackground(QColor(255, 200, 200))  # Rojo claro
            
            self.results_table.setItem(row, num_columns - 1, total_item)
        
        # Ajustar tamaño de columnas
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for i in range(1, num_columns):
            self.results_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
