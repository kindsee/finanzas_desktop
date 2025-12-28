# ui/mortgage_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QDateEdit,
    QDoubleSpinBox, QSpinBox, QDialogButtonBox
)
from PySide6.QtCore import QDate


class MortgageDialog(QDialog):
    """Diálogo para crear/editar un préstamo (PySide6)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo Préstamo")
        self.resize(420, 260)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.input_nombre = QLineEdit()
        self.input_tipo = QComboBox()
        self.input_tipo.addItems(["fijo", "variable"])
        self.input_fecha_inicio = QDateEdit()
        self.input_fecha_inicio.setCalendarPopup(True)
        self.input_fecha_inicio.setDate(QDate.currentDate())

        self.input_capital = QDoubleSpinBox()
        self.input_capital.setRange(0, 1_000_000_000)
        self.input_capital.setDecimals(2)
        self.input_capital.setSingleStep(1000)

        self.input_cuotas = QSpinBox()
        self.input_cuotas.setRange(1, 600*12)  # hasta muchos meses si quieres
        self.input_cuotas.setValue(240)  # ejemplo 20 años



        form.addRow("Nombre:", self.input_nombre)
        form.addRow("Tipo:", self.input_tipo)
        form.addRow("Fecha inicio:", self.input_fecha_inicio)
        form.addRow("Capital inicial:", self.input_capital)
        form.addRow("Cuotas (meses):", self.input_cuotas)

        layout.addLayout(form)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def get_values(self):
        """Devuelve los valores en el mismo formato esperado por admin_ui."""
        return {
            "nombre": self.input_nombre.text().strip(),
            "tipo": self.input_tipo.currentText(),
            "fecha_inicio": self.input_fecha_inicio.date().toPython(),
            "capital_inicial": float(self.input_capital.value()),
            "cuotas_totales": int(self.input_cuotas.value()),

        }
