from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
                               QFormLayout, QLineEdit, QComboBox, QDoubleSpinBox, QCheckBox,
                               QDialogButtonBox, QDateEdit)
from PySide6.QtCore import Qt, QDate
from models.simulation_variable import SimulationVariable
from models.account import Account
from datetime import date


class VariableEditDialog(QDialog):
    """Diálogo para crear/editar una variable de simulación"""
    def __init__(self, session, variable=None, parent=None):
        super().__init__(parent)
        self.session = session
        self.variable = variable
        self.setWindowTitle("Editar Variable" if variable else "Nueva Variable")
        self.setModal(True)
        self.resize(400, 250)
        
        self.setup_ui()
        if variable:
            self.load_data()
    
    def setup_ui(self):
        layout = QFormLayout(self)
        
        # Descripción
        self.descripcion_input = QLineEdit()
        layout.addRow("Descripción:", self.descripcion_input)
        
        # Cuenta
        self.cuenta_combo = QComboBox()
        cuentas = self.session.query(Account).order_by(Account.nombre).all()
        for cuenta in cuentas:
            self.cuenta_combo.addItem(cuenta.nombre, cuenta.id)
        layout.addRow("Cuenta:", self.cuenta_combo)
        
        # Importe
        self.importe_input = QDoubleSpinBox()
        self.importe_input.setRange(-999999999.99, 999999999.99)
        self.importe_input.setDecimals(2)
        self.importe_input.setValue(0.0)
        layout.addRow("Importe:", self.importe_input)
        
        # Frecuencia
        self.frecuencia_combo = QComboBox()
        self.frecuencia_combo.addItems(['semanal', 'mensual', 'trimestral', 'semestral', 'anual'])
        layout.addRow("Frecuencia:", self.frecuencia_combo)
        
        # Fecha de inicio
        self.fecha_inicio_input = QDateEdit()
        self.fecha_inicio_input.setCalendarPopup(True)
        self.fecha_inicio_input.setDate(QDate.currentDate())
        layout.addRow("Fecha Inicio:", self.fecha_inicio_input)
        
        # Activo
        self.activo_check = QCheckBox("Variable activa")
        self.activo_check.setChecked(True)
        layout.addRow("", self.activo_check)
        
        # Botones
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def load_data(self):
        """Cargar datos de la variable existente"""
        self.descripcion_input.setText(self.variable.descripcion)
        
        # Seleccionar cuenta
        for i in range(self.cuenta_combo.count()):
            if self.cuenta_combo.itemData(i) == self.variable.cuenta_id:
                self.cuenta_combo.setCurrentIndex(i)
                break
        
        self.importe_input.setValue(float(self.variable.importe))
        
        # Seleccionar frecuencia
        index = self.frecuencia_combo.findText(self.variable.frecuencia)
        if index >= 0:
            self.frecuencia_combo.setCurrentIndex(index)
        
        # Cargar fecha de inicio
        if self.variable.fecha_inicio:
            self.fecha_inicio_input.setDate(QDate(self.variable.fecha_inicio.year, 
                                                   self.variable.fecha_inicio.month, 
                                                   self.variable.fecha_inicio.day))
        
        self.activo_check.setChecked(bool(self.variable.activo))
    
    def get_data(self):
        """Obtener datos del formulario"""
        return {
            'descripcion': self.descripcion_input.text().strip(),
            'cuenta_id': self.cuenta_combo.currentData(),
            'importe': self.importe_input.value(),
            'frecuencia': self.frecuencia_combo.currentText(),
            'fecha_inicio': self.fecha_inicio_input.date().toPython(),
            'activo': 1 if self.activo_check.isChecked() else 0
        }


class VariablesDialog(QDialog):
    """Diálogo para gestionar variables de simulación"""
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Variables de Simulación")
        self.setModal(True)
        self.resize(800, 500)
        
        self.setup_ui()
        self.refresh()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Tabla de variables
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(['ID', 'Descripción', 'Cuenta', 'Importe', 'Frecuencia', 'Fecha Inicio', 'Activo'])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)
        
        # Botones de acción
        button_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("Nueva Variable")
        self.add_btn.clicked.connect(self.add_variable)
        button_layout.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("Editar")
        self.edit_btn.clicked.connect(self.edit_variable)
        button_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("Eliminar")
        self.delete_btn.clicked.connect(self.delete_variable)
        button_layout.addWidget(self.delete_btn)
        
        button_layout.addStretch()
        
        self.close_btn = QPushButton("Cerrar")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def refresh(self):
        """Recargar la tabla de variables"""
        try:
            variables = self.session.query(SimulationVariable).order_by(SimulationVariable.id).all()
            
            self.table.setRowCount(len(variables))
            for row, var in enumerate(variables):
                self.table.setItem(row, 0, QTableWidgetItem(str(var.id)))
                self.table.setItem(row, 1, QTableWidgetItem(var.descripcion))
                self.table.setItem(row, 2, QTableWidgetItem(var.cuenta.nombre if var.cuenta else ''))
                self.table.setItem(row, 3, QTableWidgetItem(f"{float(var.importe):.2f}"))
                self.table.setItem(row, 4, QTableWidgetItem(var.frecuencia))
                fecha_str = var.fecha_inicio.strftime('%d/%m/%Y') if var.fecha_inicio else 'No definida'
                self.table.setItem(row, 5, QTableWidgetItem(fecha_str))
                self.table.setItem(row, 6, QTableWidgetItem('Sí' if var.activo else 'No'))
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al cargar variables: {e}")
    
    def add_variable(self):
        """Añadir una nueva variable"""
        dialog = VariableEditDialog(self.session, parent=self)
        if dialog.exec() == QDialog.Accepted:
            try:
                data = dialog.get_data()
                if not data['descripcion']:
                    QMessageBox.warning(self, "Error", "La descripción es obligatoria")
                    return
                
                variable = SimulationVariable(**data)
                self.session.add(variable)
                self.session.commit()
                self.refresh()
                QMessageBox.information(self, "Éxito", "Variable creada correctamente")
            except Exception as e:
                self.session.rollback()
                QMessageBox.warning(self, "Error", f"Error al crear variable: {e}")
    
    def edit_variable(self):
        """Editar la variable seleccionada"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Aviso", "Selecciona una variable para editar")
            return
        
        try:
            variable_id = int(self.table.item(current_row, 0).text())
            variable = self.session.query(SimulationVariable).filter_by(id=variable_id).first()
            
            if not variable:
                QMessageBox.warning(self, "Error", "Variable no encontrada")
                return
            
            dialog = VariableEditDialog(self.session, variable, parent=self)
            if dialog.exec() == QDialog.Accepted:
                data = dialog.get_data()
                if not data['descripcion']:
                    QMessageBox.warning(self, "Error", "La descripción es obligatoria")
                    return
                
                for key, value in data.items():
                    setattr(variable, key, value)
                
                self.session.commit()
                self.refresh()
                QMessageBox.information(self, "Éxito", "Variable actualizada correctamente")
        except Exception as e:
            self.session.rollback()
            QMessageBox.warning(self, "Error", f"Error al editar variable: {e}")
    
    def delete_variable(self):
        """Eliminar la variable seleccionada"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Aviso", "Selecciona una variable para eliminar")
            return
        
        reply = QMessageBox.question(self, "Confirmar", 
                                     "¿Estás seguro de eliminar esta variable?",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                variable_id = int(self.table.item(current_row, 0).text())
                variable = self.session.query(SimulationVariable).filter_by(id=variable_id).first()
                
                if variable:
                    self.session.delete(variable)
                    self.session.commit()
                    self.refresh()
                    QMessageBox.information(self, "Éxito", "Variable eliminada correctamente")
            except Exception as e:
                self.session.rollback()
                QMessageBox.warning(self, "Error", f"Error al eliminar variable: {e}")
