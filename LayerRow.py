# LayerRow.py
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QLineEdit, 
                             QPushButton, QLabel, QComboBox)
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtCore import Qt, QLocale 

class LayerRow(QWidget):
    """A custom widget representing a single layer row (Number, Material, Thickness, Delete)."""
    
    def __init__(self, index, materials_list, initial_mat, initial_thick, delete_callback):
        super().__init__()
        self.index = index
        self.delete_callback = delete_callback
        
        layout = QHBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(5)
        
        # This is the visible label for the index, which we will update
        self.num_label = QLabel(f"{index}:"); self.num_label.setFixedWidth(20); layout.addWidget(self.num_label)
        
        self.mat_combo = QComboBox(); self.mat_combo.addItems(materials_list); self.mat_combo.setCurrentText(initial_mat); layout.addWidget(self.mat_combo, stretch=2)

        self.thick_edit = QLineEdit(str(initial_thick))
        # Create the validator with bounds, setting 'self' (the LayerRow) as the parent
        validator = QDoubleValidator(0.0, 10000.0, 2, self)
        # Explicitly set the English locale to ensure the decimal separator is '.'
        validator.setLocale(QLocale(QLocale.Language.English))
        self.thick_edit.setValidator(validator)
        self.thick_edit.setAlignment(Qt.AlignmentFlag.AlignRight); self.thick_edit.setFixedWidth(80)
        layout.addWidget(self.thick_edit, stretch=1); layout.addWidget(QLabel("nm"))

        self.delete_btn = QPushButton("X"); self.delete_btn.setStyleSheet("color: red;"); self.delete_btn.setFixedWidth(30)
        self.delete_btn.clicked.connect(self._on_delete_clicked); layout.addWidget(self.delete_btn)
        
        # 1. The label for the layer index needs to be an attribute
        # NOTE: self.num_label is already being used as the visible layer index label.
        # We will keep self.num_label and just update its text format in the method below.
        # The following line is removed as it was not added to the layout:
        # self.index_label = QLabel(f"Layer {index}")
        
        # 2. The update method is now correctly implemented as a class method below
        
    def _on_delete_clicked(self):
        self.delete_callback(self.index)
        
    # Correct implementation of the required update method (replaces the old update_index)
    def update_layer_number(self, new_index):
        """Updates the layer's internal index and the visible layer number label."""
        self.index = new_index
        # Update the text of the visible layer label (self.num_label)
        # using the desired format: "Layer N:"
        self.num_label.setText(f"{new_index}:")

    def get_data(self):
        try:
            thickness = float(self.thick_edit.text())
        except ValueError:
            thickness = 0.0
        return (self.mat_combo.currentText(), thickness)