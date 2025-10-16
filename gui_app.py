# gui_app.py
import sys
import numpy as np
from scipy.interpolate import interp1d
# --- PyQt Imports ---
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QLineEdit, QPushButton, 
                             QLabel, QComboBox, QScrollArea, QGroupBox, QMessageBox)
from PyQt6.QtCore import Qt, QLocale
from PyQt6.QtGui import QDoubleValidator
# --- Matplotlib Imports ---
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
# --- Local Imports: Connect to the Physics Engine ---
from LayerRow import LayerRow 
from physics_engine.reflectance import calculate_reflectance
from physics_engine.colorimetry import calculate_colorimetry


class ReflectanceApp(QMainWindow):
    """Main application window, translating main_program.m."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Thin-Film Reflectance Calculator")
        
        # Set the desired default size (width, height). The position (100, 100) is temporary/ignored.
        self.setGeometry(100, 100, 960, 640) 
        
        # Call the centering logic here
        self.center()
        
        # --- Default Values ---
        self.DEFAULT_LAMBDA_START = 380
        self.DEFAULT_LAMBDA_END = 780
        self.DEFAULT_ANGLE_DEG = 0.0
        self.DEFAULT_SUBSTRATE = 'Si'
        
        # NOTE: This list must match the materials defined in nk_data_loader.py's file_map
        self.materials_list = ['a-Ge','Al','Al2O3','a-Si','GaAs','Ge','HfN','HfO2','MgO','poly-Si','RuO2','Si3N4','Si65Ge35','Si77Ge23','Si88Ge12','Si94Ge6','Si','SiO','SiO2','SnO2','TiO2','W','ZnO','ZrO2']
        self.polarization_options = ['s (TE)', 'p (TM)', 'Mixed (s+p)/2']
        
        self.layer_widgets = []
        
        self._init_ui()
        self._load_initial_layers()
        
    def center(self):
        """Centers the main window on the primary screen's available geometry."""
        
        # 1. Get the geometry of the entire screen (excluding taskbar/docks)
        # self.screen() gets the QScreen object for the current display
        screen_geo = self.screen().availableGeometry()
        
        # 2. Get the current geometry (size) of the application window
        window_geo = self.frameGeometry()
        
        # 3. Find the center point of the screen
        center_point = screen_geo.center()
        
        # 4. Move the window's center point to the screen's center point.
        # This automatically calculates the new top-left corner (x, y).
        window_geo.moveCenter(center_point)
        
        # 5. Apply the new position to the window
        self.move(window_geo.topLeft())        
        
    def _init_ui(self):
        """Sets up the main layout and all controls."""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # --- Left Panel: Controls ---
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        control_panel.setFixedWidth(350)
        
        control_layout.addWidget(self._create_calc_param_group())
        control_layout.addWidget(self._create_stack_panel_group())
        control_layout.addWidget(self._create_color_output_group())
        control_layout.addWidget(self._create_color_chart_group())
        control_layout.addStretch(1)
        
        main_layout.addWidget(control_panel)
        
        # --- Right Panel: Plotting ---
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        main_layout.addWidget(self.canvas, stretch=1)
        
        self._init_plot()
        
    # --- Helper methods for creating GUI groups (omitted for brevity) ---
    def _create_calc_param_group(self):
        # UI setup logic...
        group = QGroupBox("Calculation Parameters"); layout = QGridLayout(); group.setLayout(layout)
        self.h_lambda_start = QLineEdit(str(self.DEFAULT_LAMBDA_START)); self.h_lambda_end = QLineEdit(str(self.DEFAULT_LAMBDA_END)); self.h_angle = QLineEdit(str(self.DEFAULT_ANGLE_DEG)); self.h_pol = QComboBox(); self.h_pol.addItems(self.polarization_options)
        layout.addWidget(QLabel("Wavelength (nm):"), 0, 0); layout.addWidget(self.h_lambda_start, 0, 1); layout.addWidget(QLabel("-"), 0, 2, alignment=Qt.AlignmentFlag.AlignCenter); layout.addWidget(self.h_lambda_end, 0, 3)
        layout.addWidget(QLabel("Angle (deg):"), 1, 0); layout.addWidget(self.h_angle, 1, 1, 1, 3); layout.addWidget(QLabel("Polarization:"), 2, 0); layout.addWidget(self.h_pol, 2, 1, 1, 3)
        # layout.addWidget(QLabel("Substrate:"), 3, 0); layout.addWidget(QLabel(self.DEFAULT_SUBSTRATE), 3, 1, 1, 3)
        plot_btn = QPushButton("Calculate & Plot Reflectance"); plot_btn.clicked.connect(self._plot_button_callback)
        layout.addWidget(plot_btn, 4, 0, 1, 4)
        return group
        
    def _create_stack_panel_group(self):
        # UI setup logic...
        group = QGroupBox("Layer Stack"); main_layout = QVBoxLayout(); group.setLayout(main_layout)
        
        # 1. Air (Top) Label
        air_label = QLabel("<b>Incident Medium, Air (Top)</b>")
        air_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(air_label)

        # 2. Layer Scroll Area
        self.layer_scroll_widget = QWidget()
        self.layer_vbox = QVBoxLayout(self.layer_scroll_widget)
        self.layer_vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.layer_scroll_widget)
        main_layout.addWidget(scroll_area)
        
        # 3. Substrate (Bottom) Label
        substrate_label = QLabel("<b>Substrate, Si (Bottom)</b>")
        substrate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(substrate_label)

        # 4. Add Layer Button
        add_btn = QPushButton("Add Layer")
        add_btn.clicked.connect(lambda: self._add_layer_callback('SiO2', 100.0))
        main_layout.addWidget(add_btn)
        
        return group        

    def _create_color_output_group(self):
        # UI setup logic...
        group = QGroupBox("Calculated Color"); layout = QGridLayout(); group.setLayout(layout)
        self.h_color_patch = QLabel(); self.h_color_patch.setStyleSheet("background-color: rgb(0, 0, 0); border: 1px solid black;"); self.h_color_patch.setFixedSize(100, 50)
        self.h_rgb_text = QLabel("[R, G, B]"); self.h_xy_text = QLabel("x, y")
        layout.addWidget(self.h_color_patch, 0, 0, 2, 1); layout.addWidget(QLabel("sRGB (0-255):"), 0, 1); layout.addWidget(self.h_rgb_text, 0, 2)
        layout.addWidget(QLabel("CIE xy:"), 1, 1); layout.addWidget(self.h_xy_text, 1, 2)
        return group

    def _create_color_chart_group(self):
        # UI setup logic...
        group = QGroupBox("Thickness Color Sweep"); layout = QGridLayout(); group.setLayout(layout)
        self.h_sweep_layer = QLineEdit("1"); self.h_sweep_start = QLineEdit("0"); self.h_sweep_end = QLineEdit("500"); self.h_sweep_step = QLineEdit("1")
        layout.addWidget(QLabel("Layer Index:"), 0, 0); layout.addWidget(self.h_sweep_layer, 0, 1); layout.addWidget(QLabel("T Start (nm):"), 1, 0); layout.addWidget(self.h_sweep_start, 1, 1)
        layout.addWidget(QLabel("T End (nm):"), 2, 0); layout.addWidget(self.h_sweep_end, 2, 1); layout.addWidget(QLabel("T Step (nm):"), 3, 0); layout.addWidget(self.h_sweep_step, 3, 1)
        chart_btn = QPushButton("Generate Color Chart"); chart_btn.clicked.connect(self._generate_color_chart_callback); layout.addWidget(chart_btn, 4, 0, 1, 2)
        return group
    
    def _init_plot(self):
        self.ax.set_title('Spectral Reflectance'); self.ax.set_xlabel('Wavelength (nm)'); self.ax.set_ylabel('Reflectance (R)')
        self.ax.set_xlim(self.DEFAULT_LAMBDA_START, self.DEFAULT_LAMBDA_END); self.ax.set_ylim(0, 1.0); self.ax.grid(True); self.canvas.draw()
        
    def _load_initial_layers(self):
        self._add_layer_callback('SiO2', 100.0) 
        
    # def _add_layer_callback(self, init_mat, init_thick):
        # new_index = len(self.layer_widgets) + 1
        # new_layer_widget = LayerRow(
            # index=new_index, materials_list=self.materials_list, 
            # initial_mat=init_mat, initial_thick=init_thick, 
            # delete_callback=self._delete_layer_callback
        # )
        # self.layer_vbox.insertWidget(0, new_layer_widget)
        # self.layer_widgets.insert(0, new_layer_widget)

    def _add_layer_callback(self, init_mat, init_thick):
        # Note: The 'index' argument in LayerRow creation will be a placeholder,
        # as the correct index is determined *after* the insertion/re-indexing.
        new_layer_widget = LayerRow(
            index=0,  # Placeholder index
            materials_list=self.materials_list, 
            initial_mat=init_mat, initial_thick=init_thick, 
            delete_callback=self._delete_layer_callback
        )
        
        # Insert the widget at index 0 of the layout (closest to Air).
        self.layer_vbox.insertWidget(0, new_layer_widget)
        
        # Insert the widget at index 0 of the tracking list (Air-side).
        self.layer_widgets.insert(0, new_layer_widget)
        
        # Call the new method to renumber all layers.
        self._reindex_layers()
     
    def _reindex_layers(self):
        total_layers = len(self.layer_widgets)
        
        # self.layer_widgets is ordered Air-side (index 0) to Substrate-side (index N-1)
        for i, layer_widget in enumerate(self.layer_widgets):
            # Calculate the layer number:
            # - When i=0 (Air-side layer), new_index = N - 0 = N
            # - When i=N-1 (Substrate-side layer), new_index = N - (N-1) = 1
            new_index = total_layers - i
            
            # ASSUMPTION: LayerRow has an update method.
            layer_widget.update_layer_number(new_index)
            
            # OPTIONAL: Also update an internal index property if your other logic needs it
            # layer_widget.index = new_index
     
    def _delete_layer_callback(self, index_to_delete):
        widget_to_delete = None
        for i, widget in enumerate(self.layer_widgets):
            if widget.index == index_to_delete:
                widget_to_delete = widget
                del self.layer_widgets[i] 
                break
        if widget_to_delete:
            widget_to_delete.setParent(None); widget_to_delete.deleteLater()
            for i, widget in enumerate(self.layer_widgets):
                widget.update_layer_number(i + 1)
                
    def _get_current_layer_stack(self):
        layers = []
        for widget in self.layer_widgets:
            material, thickness = widget.get_data()
            if thickness > 0:
                layers.append([material, thickness])
        return layers

    def _plot_button_callback(self):
        """Translates plot_button_callback.m - calls the imported physics functions."""
        try:
            lambda_start = int(self.h_lambda_start.text()); lambda_end = int(self.h_lambda_end.text())
            theta_inc_deg = float(self.h_angle.text()); polarization_text = self.h_pol.currentText()
            layers = self._get_current_layer_stack()
            
            if lambda_start >= lambda_end: raise ValueError("Plot Start Wavelength must be less than Plot End Wavelength.")
            if not layers: raise ValueError("Layer stack is empty. Please add at least one layer.")

            lambda_calc = np.arange(380.0, 781.0, 1.0) # Full visible range for colorimetry
            
            # CALL PHYSICS ENGINE
            Rs, Rp = calculate_reflectance(layers, self.DEFAULT_SUBSTRATE, lambda_calc, theta_inc_deg)

            R_spectrum = (Rs + Rp) / 2.0 if 'Mixed' in polarization_text else (Rs if 's' in polarization_text else Rp)
            
            # CALL COLORIMETRY ENGINE
            R_sRGB, x, y = calculate_colorimetry(R_spectrum, lambda_calc)

            self.ax.clear(); idx_start = np.searchsorted(lambda_calc, lambda_start); idx_end = np.searchsorted(lambda_calc, lambda_end)
            self.ax.plot(lambda_calc[idx_start:idx_end], R_spectrum[idx_start:idx_end], color='purple', linewidth=2)
            self.ax.set_title(f'Spectral Reflectance for {polarization_text}'); self.ax.set_xlabel('Wavelength (nm)'); self.ax.set_ylabel('Reflectance (R)')
            self.ax.set_xlim(lambda_start, lambda_end); self.ax.set_ylim(0, 1.0); self.ax.grid(True); self.canvas.draw()
            
            r, g, b = R_sRGB
            self.h_rgb_text.setText(f"[{r}, {g}, {b}]"); self.h_xy_text.setText(f"x={x:.4f}, y={y:.4f}")
            self.h_color_patch.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;")

        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Error:\n{e}")
            
    def _generate_color_chart_callback(self):
        """Translates generate_color_chart_callback.m - performs the thickness sweep."""
        try:
            sweep_index = int(self.h_sweep_layer.text()); t_start = float(self.h_sweep_start.text()); t_end = float(self.h_sweep_end.text())
            t_step = float(self.h_sweep_step.text()); theta_inc_deg = float(self.h_angle.text()); polarization_text = self.h_pol.currentText()
            base_layers = self._get_current_layer_stack()
            
            if not base_layers: raise ValueError("Layer stack is empty. Cannot generate color chart.")
            if sweep_index < 1 or sweep_index > len(base_layers): raise ValueError(f"Sweep Layer Index must be between 1 and {len(base_layers)}.")
            
            t_values = np.arange(t_start, t_end + t_step/2, t_step); R_sRGB_chart = []; lambda_full_vis = np.arange(380.0, 781.0, 1.0)
            swept_material = base_layers[sweep_index - 1][0]
            
            for t_val in t_values:
                current_layers = [list(layer) for layer in base_layers]
                current_layers[sweep_index - 1][1] = t_val 
                
                Rs, Rp = calculate_reflectance(current_layers, self.DEFAULT_SUBSTRATE, lambda_full_vis, theta_inc_deg)
                R_spectrum = (Rs + Rp) / 2.0 if 'Mixed' in polarization_text else (Rs if 's' in polarization_text else Rp)
                
                R_sRGB, _, _ = calculate_colorimetry(R_spectrum, lambda_full_vis)
                R_sRGB_chart.append(R_sRGB)

            self._plot_color_chart(np.array(R_sRGB_chart), t_values, t_start, t_step, swept_material)
            
        except Exception as e:
            QMessageBox.critical(self, "Color Chart Error", f"Error:\n{e}")

    def _plot_color_chart(self, sRGB_chart, t_values, t_start, t_step, swept_material):
        """Plots the thickness sweep color chart in a new Matplotlib figure."""
        chart_window = QMainWindow(self); chart_window.setWindowTitle(f"Color Chart Sweep: {swept_material} (Layer {self.h_sweep_layer.text()})")
        fig = Figure(); canvas = FigureCanvas(fig); chart_window.setCentralWidget(canvas); chart_window.resize(800, 300)
        chart_ax = fig.add_subplot(111)
        color_matrix_for_display = sRGB_chart[np.newaxis, :, :] / 255.0
        t_end_boundary = t_values[-1] + t_step
        chart_ax.imshow(color_matrix_for_display, aspect='auto', extent=[t_start, t_end_boundary, 0, 1])
        chart_ax.set_yticks([]); chart_ax.set_ylim(0, 1)
        chart_ax.set_xlim(t_start, t_end_boundary)
        chart_ax.set_title(f"Color Sweep: {swept_material} Thickness")
        chart_ax.set_xlabel(f"Thickness (nm) of Layer {self.h_sweep_layer.text()}")
        fig.subplots_adjust(bottom=0.20)
        canvas.draw(); chart_window.show()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_app = ReflectanceApp()
    main_app.show()

    sys.exit(app.exec())
