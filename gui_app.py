# gui_app.py
import sys
import numpy as np
from scipy.interpolate import interp1d
# --- PyQt Imports ---
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QLineEdit, QPushButton,
                             QLabel, QComboBox, QScrollArea, QGroupBox, QMessageBox, QCheckBox,
                             QProgressBar, QFileDialog) # QFileDialog added for saving
from PyQt6.QtCore import Qt, QLocale, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QDoubleValidator, QAction # QAction added for menu items
# --- Matplotlib Imports ---
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib import ticker
# --- Local Imports: Connect to the Physics Engine ---
from LayerRow import LayerRow
from physics_engine.reflectance import calculate_reflectance
from physics_engine.colorimetry import calculate_colorimetry

# ==============================================================================
# 1. WORKER CLASS: Runs the heavy computation in a separate thread
# ... (ColorChartWorker remains unchanged) ...
# ==============================================================================

class ColorChartWorker(QObject):
    """Worker object to perform the intensive 2D color chart calculation."""
    calculation_finished = pyqtSignal(object) # Signal to send result back
    calculation_error = pyqtSignal(str) # Signal for errors
    progress_update = pyqtSignal(int) # Signal to update progress

    def __init__(self, base_layers, lambda_full_vis, sweep_params, parent=None):
        super().__init__(parent)
        self.base_layers = base_layers
        self.lambda_full_vis = lambda_full_vis
        self.sweep_params = sweep_params

    def run_2d_sweep(self):
        """Performs the 2D sweep (Thickness vs. Angle) calculation."""
        try:
            # Unpack parameters
            thick_layer_index = self.sweep_params['thick_layer_index'] # 0-based index
            thick_values = self.sweep_params['thick_values']
            angle_values = self.sweep_params['angle_values']
            
            R_sRGB_chart_2d = []
            
            total_angles = len(angle_values)
            
            # Angle sweep is Y-axis (Outer Loop)
            for i, angle in enumerate(angle_values):
                # Calculate and emit progress based on angle sweep completion
                progress = int((i + 1) * 100 / total_angles)
                self.progress_update.emit(progress) # EMIT PROGRESS

                row_colors = []
                # IMPORTANT: Need to copy the layers for each outer loop iteration
                current_layers_angle = [list(layer) for layer in self.base_layers]

                # Thickness sweep is X-axis (Inner Loop)
                for thick in thick_values:
                    # Apply the swept thickness. Need another copy to avoid modifying the 'angle' base layer setup
                    current_layers_thick_angle = [list(layer) for layer in current_layers_angle]
                    # Uses the corrected 0-based index: thick_layer_index
                    current_layers_thick_angle[thick_layer_index][1] = thick

                    # Calculate R for this Angle and this Thickness
                    Rs, Rp = calculate_reflectance(current_layers_thick_angle, 'Si', self.lambda_full_vis, angle)

                    # Colorimetry Calculation (Mixed polarization for chart)
                    R_spectrum = (Rs + Rp) / 2.0
                    R_sRGB, _, _ = calculate_colorimetry(R_spectrum, self.lambda_full_vis)
                    row_colors.append(R_sRGB)

                R_sRGB_chart_2d.append(row_colors)
            
            color_data_array = np.array(R_sRGB_chart_2d)
            
            # Send the result back to the main thread
            result = {
                'color_data': color_data_array,
                'params': self.sweep_params
            }
            self.calculation_finished.emit(result)

        except Exception as e:
            self.calculation_error.emit(f"2D Sweep Error: {e}")


# ==============================================================================
# 2. MAIN APPLICATION CLASS
# ==============================================================================

class ReflectanceApp(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Thin-Film Reflectance Calculator")

        self.setGeometry(100, 100, 960, 640)
        self.center()

        # --- Default Values ---
        self.DEFAULT_LAMBDA_START = 380
        self.DEFAULT_LAMBDA_END = 780
        self.DEFAULT_ANGLE_DEG = 0
        self.DEFAULT_SUBSTRATE = 'Si'

        self.materials_list = ['a-Ge','Al','Al2O3','AlN','a-Si','GaAs','Ge','HfN','HfO2','MgF2','MgO','poly-Si','RuO2','Si3N4','Si65Ge35','Si77Ge23','Si88Ge12','Si94Ge6','Si','SiC','SiO','SiO2','SnO2','Ta2O5','TiN','TiO2','W','Y2O3','ZnO','ZrO2']
        self.polarization_options = ['s (TE)', 'p (TM)', 'Mixed (s+p)/2']

        self.layer_widgets = []
        self.worker_thread = None # Thread reference

        self._init_ui()
        self._load_initial_layers()

    # ... (center method remains unchanged) ...
    def center(self):
        """Centers the main window on the primary screen's available geometry."""
        screen_geo = self.screen().availableGeometry()
        window_geo = self.frameGeometry()
        center_point = screen_geo.center()
        window_geo.moveCenter(center_point)
        self.move(window_geo.topLeft())
    
    def _init_ui(self):
        """Sets up the main layout and all controls."""
        
        # --- ADDED: Create Menu Bar ---
        self._create_menu_bar() 
        
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

    # --- UPDATED: Menu Bar Creation and Callbacks ---
    def _create_menu_bar(self):
        """Creates the File and Help menus for the main window."""
        menu_bar = self.menuBar()

        # --- File Menu ---
        file_menu = menu_bar.addMenu("&File")

        # Save Spectral Reflectance Plot Action
        save_action = QAction("&Save Spectral Plot...", self)
        save_action.setShortcut("Ctrl+S") # ADDED SHORTCUT
        save_action.setStatusTip("Save the current spectral reflectance plot as an image file.")
        save_action.triggered.connect(self._save_plot_callback)
        file_menu.addAction(save_action)

        # Exit Action
        exit_action = QAction("&Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit the application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # --- Help Menu ---
        help_menu = menu_bar.addMenu("&Help")

        # About Action
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._about_callback)
        help_menu.addAction(about_action)

        # NEW: License Action
        license_action = QAction("&License", self)
        license_action.triggered.connect(self._license_callback)
        help_menu.addAction(license_action)
        
    # --- NEW: License Callback ---
    def _license_callback(self):
        """Displays the MIT License information in a QMessageBox."""
        license_text = """
MIT License

Copyright (c) 2025 ajschmidt-ucb

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF 
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY 
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
        QMessageBox.about(
            self, 
            "Software License (MIT)",
            license_text.strip()
        )

    # --- NEW: Menu Bar for Chart Windows ---
    def _create_chart_menu_bar(self, chart_window, figure):
        """Creates a simplified File menu for the color chart window."""
        menu_bar = chart_window.menuBar()
        file_menu = menu_bar.addMenu("&File")

        # Save Color Chart Action
        save_chart_action = QAction("&Save Color Chart...", chart_window)
        save_chart_action.setShortcut("Ctrl+S") # ADDED SHORTCUT
        save_chart_action.setStatusTip("Save the color chart as an image file.")
        # We need to pass the figure and the chart window to the saving function
        save_chart_action.triggered.connect(lambda: self._save_chart_callback(figure, chart_window)) 
        file_menu.addAction(save_chart_action)
        
        # Quit Chart Window Action
        quit_chart_action = QAction("&Close Window", chart_window)
        quit_chart_action.setShortcut("Ctrl+Q") # ADDED SHORTCUT
        quit_chart_action.setStatusTip("Close the color chart window")
        # Connect to the chart window's close method
        quit_chart_action.triggered.connect(chart_window.close) 
        file_menu.addAction(quit_chart_action)
        
    def _save_plot_callback(self):
        """Opens a file dialog to save the current Matplotlib plot (main window)."""
        if not self.figure.axes: # Check if the plot has been initialized or cleared
            QMessageBox.warning(self, "Save Error", "No spectral plot has been generated yet.")
            return

        # QFileDialog.getSaveFileName returns a tuple: (filename, filter)
        # We allow common image formats
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Spectral Reflectance Plot",
            "spectral_plot.png", # Default filename
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;All Files (*)"
        )

        if file_path:
            try:
                # Save the figure to the chosen path
                self.figure.savefig(file_path, bbox_inches='tight', dpi=300)
                QMessageBox.information(self, "Success", f"Plot successfully saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Could not save plot:\n{e}")

    # --- NEW: Save Chart Callback for Chart Windows ---
    def _save_chart_callback(self, figure, chart_window):
        """Opens a file dialog to save the Matplotlib chart figure (chart windows)."""
        
        # QFileDialog.getSaveFileName returns a tuple: (filename, filter)
        file_path, _ = QFileDialog.getSaveFileName(
            chart_window, # Parent is the chart window
            "Save Color Chart",
            "color_chart.png", # Default filename
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;All Files (*)"
        )

        if file_path:
            try:
                # Save the figure to the chosen path
                figure.savefig(file_path, bbox_inches='tight', dpi=300)
                QMessageBox.information(chart_window, "Success", f"Color chart successfully saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(chart_window, "Save Error", f"Could not save color chart:\n{e}")

    def _about_callback(self):
        """Displays the 'About' information in a QMessageBox."""
        QMessageBox.about(
            self, 
            "About Thin-Film Reflectance Calculator",
            "<h2>Thin-Film Reflectance Calculator</h2>"
            "<p>Version 1.2.0</p>"
            "<p>Developed by: Alexander J. Schmidt, PhD Electrical Engineering and Computer Sciences University of California, Berkeley Prof. Salahuddin Laboratory and Marvell Nanofabrication Laboratory</p>"
            "<p>A Python-based desktop application for calculating the spectral reflectance and colorimetric properties of multi-layer thin-film stacks. It implements Parratt Recursion and the Fresnel Equations for precise optical simulation.</p>"
            "<p>Built using PyQt6 and Matplotlib.</p>"
            "<p>Source code can be found on GitHub here: <a href='https://github.com/ajschmidt-ucb/ThinFilmCalculator'>https://github.com/ajschmidt-ucb/ThinFilmCalculator</a></p>"
        )

    # ... (The rest of the class methods remain unchanged, including _create_calc_param_group, 
    # _create_stack_panel_group, _create_color_output_group, _create_color_chart_group, 
    # _init_plot, layer management methods, and all calculation callbacks) ...

    # --- GUI Creation Methods (unchanged) ---
    def _create_calc_param_group(self):
        group = QGroupBox("Calculation Parameters"); layout = QGridLayout(); group.setLayout(layout)
        self.h_lambda_start = QLineEdit(str(self.DEFAULT_LAMBDA_START)); self.h_lambda_end = QLineEdit(str(self.DEFAULT_LAMBDA_END)); self.h_angle = QLineEdit(str(self.DEFAULT_ANGLE_DEG)); self.h_pol = QComboBox(); self.h_pol.addItems(self.polarization_options)
        layout.addWidget(QLabel("Wavelength (nm):"), 0, 0); layout.addWidget(self.h_lambda_start, 0, 1); layout.addWidget(QLabel("-"), 0, 2, alignment=Qt.AlignmentFlag.AlignCenter); layout.addWidget(self.h_lambda_end, 0, 3)
        layout.addWidget(QLabel("Angle (deg):"), 1, 0); layout.addWidget(self.h_angle, 1, 1, 1, 3); layout.addWidget(QLabel("Polarization:"), 2, 0); layout.addWidget(self.h_pol, 2, 1, 1, 3)
        plot_btn = QPushButton("Calculate & Plot Reflectance"); plot_btn.clicked.connect(self._plot_button_callback)
        layout.addWidget(plot_btn, 4, 0, 1, 4)
        return group

    def _create_stack_panel_group(self):
        group = QGroupBox("Layer Stack"); main_layout = QVBoxLayout(); group.setLayout(main_layout)
        air_label = QLabel("<b>Incident Medium, Air (Top)</b>"); air_label.setAlignment(Qt.AlignmentFlag.AlignCenter); main_layout.addWidget(air_label)
        self.layer_scroll_widget = QWidget(); self.layer_vbox = QVBoxLayout(self.layer_scroll_widget); self.layer_vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True); scroll_area.setWidget(self.layer_scroll_widget); main_layout.addWidget(scroll_area)
        substrate_label = QLabel("<b>Substrate, Si (Bottom)</b>"); substrate_label.setAlignment(Qt.AlignmentFlag.AlignCenter); main_layout.addWidget(substrate_label)
        add_btn = QPushButton("Add Layer"); add_btn.clicked.connect(lambda: self._add_layer_callback('SiO2', 100.0)); main_layout.addWidget(add_btn)
        return group

    def _create_color_output_group(self):
        group = QGroupBox("Calculated Color"); layout = QGridLayout(); group.setLayout(layout)
        self.h_color_patch = QLabel(); self.h_color_patch.setStyleSheet("background-color: rgb(0, 0, 0); border: 1px solid black;"); self.h_color_patch.setFixedSize(100, 50)
        self.h_rgb_text = QLabel("[R, G, B]"); self.h_xy_text = QLabel("x, y")
        layout.addWidget(self.h_color_patch, 0, 0, 2, 1); layout.addWidget(QLabel("sRGB (0-255):"), 0, 1); layout.addWidget(self.h_rgb_text, 0, 2)
        layout.addWidget(QLabel("CIE xy:"), 1, 1); layout.addWidget(self.h_xy_text, 1, 2)
        return group

    def _create_color_chart_group(self):
        group = QGroupBox("Color Chart Sweep"); layout = QGridLayout(); group.setLayout(layout)
        thick_validator = QDoubleValidator(0.0, 10000.0, 2, self); angle_validator = QDoubleValidator(0.0, 90.0, 2, self)
        for validator in [thick_validator, angle_validator]: validator.setLocale(QLocale(QLocale.Language.English, QLocale.Country.AnyCountry))

        self.h_sweep_chk = QCheckBox("Thickness"); self.h_sweep_chk.setChecked(True)
        self.h_sweep_layer = QLineEdit("1")
        self.h_sweep_start = QLineEdit("0.0"); self.h_sweep_end = QLineEdit("500.0"); self.h_sweep_step = QLineEdit("1.0")
        self.h_sweep_start.setValidator(thick_validator); self.h_sweep_end.setValidator(thick_validator); self.h_sweep_step.setValidator(thick_validator)

        layout.addWidget(self.h_sweep_chk, 0, 0); layout.addWidget(QLabel("Layer Index:"), 0, 1); layout.addWidget(self.h_sweep_layer, 0, 2, 1, 4)
        layout.addWidget(QLabel("T Range (nm):"), 1, 0, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.h_sweep_start, 1, 1); layout.addWidget(QLabel("-"), 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.h_sweep_end, 1, 3); layout.addWidget(QLabel("step"), 1, 4, alignment=Qt.AlignmentFlag.AlignRight); layout.addWidget(self.h_sweep_step, 1, 5)

        self.h_sweep_angle_chk = QCheckBox("Angle"); self.h_sweep_angle_chk.setChecked(False)
        self.h_sweep_angle_start = QLineEdit("0.0"); self.h_sweep_angle_end = QLineEdit("90.0"); self.h_sweep_angle_step = QLineEdit("1.0")
        self.h_sweep_angle_start.setValidator(angle_validator); self.h_sweep_angle_end.setValidator(angle_validator); self.h_sweep_angle_step.setValidator(angle_validator)

        layout.addWidget(self.h_sweep_angle_chk, 2, 0, 1, 6)
        layout.addWidget(QLabel("θ Range (deg):"), 3, 0, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.h_sweep_angle_start, 3, 1); layout.addWidget(QLabel("-"), 3, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.h_sweep_angle_end, 3, 3); layout.addWidget(QLabel("step"), 3, 4, alignment=Qt.AlignmentFlag.AlignRight); layout.addWidget(self.h_sweep_angle_step, 3, 5)

        chart_btn = QPushButton("Generate Color Chart")
        chart_btn.clicked.connect(self._generate_color_chart_callback)
        self.h_chart_btn = chart_btn # Keep a reference to disable during calculation
        layout.addWidget(chart_btn, 4, 0, 1, 6)
        
        # --- PROGRESS BAR AND STATUS LABEL ---
        self.h_chart_status_label = QLabel("")
        self.h_progress_bar = QProgressBar()
        self.h_progress_bar.setRange(0, 100)
        self.h_progress_bar.setTextVisible(True)
        self.h_progress_bar.setValue(0)
        self.h_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid grey;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #38a169; /* Green color */
                width: 20px;
            }
        """)
        self.h_progress_bar.setVisible(False) # Start hidden

        layout.addWidget(self.h_chart_status_label, 5, 0, 1, 6)
        layout.addWidget(self.h_progress_bar, 6, 0, 1, 6)
        # ----------------------------------------
        
        return group
    
    # --- Other UI methods ---
    def _init_plot(self):
        self.ax.set_title('Spectral Reflectance'); self.ax.set_xlabel('Wavelength (nm)'); self.ax.set_ylabel('Reflectance (R)')
        self.ax.set_xlim(self.DEFAULT_LAMBDA_START, self.DEFAULT_LAMBDA_END); self.ax.set_ylim(0, 1.0); self.ax.grid(True); self.canvas.draw()
    def _load_initial_layers(self): self._add_layer_callback('SiO2', 100.0)
    def _add_layer_callback(self, init_mat, init_thick):
        new_layer_widget = LayerRow(index=0, materials_list=self.materials_list, initial_mat=init_mat, initial_thick=init_thick, delete_callback=self._delete_layer_callback)
        self.layer_vbox.insertWidget(0, new_layer_widget)
        self.layer_widgets.insert(0, new_layer_widget)
        self._reindex_layers()
    def _reindex_layers(self):
        total_layers = len(self.layer_widgets)
        for i, layer_widget in enumerate(self.layer_widgets): layer_widget.update_layer_number(total_layers - i)
    def _delete_layer_callback(self, index_to_delete):
        widget_to_delete = None
        for i, widget in enumerate(self.layer_widgets):
            if widget.index == index_to_delete:
                widget_to_delete = widget; del self.layer_widgets[i]; break
        if widget_to_delete: widget_to_delete.setParent(None); widget_to_delete.deleteLater(); self._reindex_layers()
    def _get_current_layer_stack(self):
        layers = [];
        for widget in self.layer_widgets:
            material, thickness = widget.get_data();
            if thickness > 0: layers.append([material, thickness])
        return layers
    
    # --- Calculation Callbacks (unchanged) ---

    def _plot_button_callback(self):
        """1D Reflectance Plot (Quick, stays on main thread)."""
        try:
            lambda_start = int(self.h_lambda_start.text())
            lambda_end = int(self.h_lambda_end.text())
            theta_inc_deg = float(self.h_angle.text())
            polarization_text = self.h_pol.currentText()
            layers = self._get_current_layer_stack()

            if lambda_start >= lambda_end: raise ValueError("Plot Start Wavelength must be less than Plot End Wavelength.")
            if not layers: raise ValueError("Layer stack is empty. Please add at least one layer.")

            # --- 1. Wavelength Array for Calculation and Plotting (User's Range) ---
            # lambda_calc_plot now defines the primary calculation range.
            lambda_calc_plot = np.arange(float(lambda_start), float(lambda_end) + 1.0, 1.0) 
            
            # --- 2. Calculate Reflectance over User's Range ---
            Rs_plot, Rp_plot = calculate_reflectance(layers, self.DEFAULT_SUBSTRATE, lambda_calc_plot, theta_inc_deg)
            R_spectrum_plot = (Rs_plot + Rp_plot) / 2.0 if 'Mixed' in polarization_text else (Rs_plot if 's' in polarization_text else Rp_plot)
            
            # --- 3. Prepare Data for Colorimetry (Fixed Visible Range: 380-780 nm) ---
            lambda_calc_full_vis = np.arange(380.0, 781.0, 1.0)
            
            # Interpolate the calculated spectrum onto the fixed visible range
            # Check if the user's range covers the visible spectrum for accurate interpolation
            if lambda_start <= 380 and lambda_end >= 780:
                
                # Use interpolation function (requires 'interp1d' from scipy.interpolate)
                # interpf will be a function that takes a new lambda and returns the R value
                interpf = interp1d(lambda_calc_plot, R_spectrum_plot, kind='linear')
                R_spectrum_full_vis = interpf(lambda_calc_full_vis)
                
                # --- 4. Colorimetry Calculation (Always uses the interpolated 380-780 nm spectrum) ---
                R_sRGB, x, y = calculate_colorimetry(R_spectrum_full_vis, lambda_calc_full_vis)
                
                r, g, b = R_sRGB
                self.h_rgb_text.setText(f"[{r}, {g}, {b}]")
                self.h_xy_text.setText(f"x={x:.4f}, y={y:.4f}")
                self.h_color_patch.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;")

            else:
                # Cannot calculate accurate colorimetry if the range is incomplete
                self.h_rgb_text.setText("[N/A]")
                self.h_xy_text.setText("N/A")
                self.h_color_patch.setStyleSheet("background-color: rgb(100, 100, 100); border: 1px solid black;")
                QMessageBox.warning(self, "Colorimetry Warning", 
                                    "Color calculation requires the wavelength range to cover 380 nm to 780 nm.")

            # --- 5. Plotting (Uses the R_spectrum_plot calculated over the user's range) ---
            self.ax.clear()
            self.ax.plot(lambda_calc_plot, R_spectrum_plot, color='purple', linewidth=2)
            
            self.ax.set_title(f'Spectral Reflectance for {polarization_text}'); 
            self.ax.set_xlabel('Wavelength (nm)'); self.ax.set_ylabel('Reflectance (R)')
            self.ax.set_xlim(lambda_start, lambda_end); # Set x-limits to user's input
            self.ax.set_ylim(0, 1.0); self.ax.grid(True); self.canvas.draw()
            
        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Error:\n{e}")

    # ... (Rest of the worker-related and 2D sweep methods remain unchanged) ...

    def _generate_color_chart_callback(self):
        """Determines sweep type and initiates calculation."""
        try:
            is_thickness_sweep = self.h_sweep_chk.isChecked()
            is_angle_sweep = self.h_sweep_angle_chk.isChecked()

            if is_thickness_sweep and is_angle_sweep:
                self._prepare_and_start_2d_sweep()
            elif is_thickness_sweep ^ is_angle_sweep:
                self._generate_1d_color_chart_callback(is_thickness_sweep)
            else:
                QMessageBox.warning(self, "Calculation Warning", "Please select at least one sweep type.")
        except Exception as e:
            QMessageBox.critical(self, "Color Chart Error", f"Error:\n{e}")

    def _prepare_and_start_2d_sweep(self):
        """Gathers parameters and launches the 2D sweep in a new thread."""
        base_layers = self._get_current_layer_stack()
        if not base_layers:
            raise ValueError("Layer stack is empty. Cannot generate color chart.")

        # --- Get Thickness Sweep Parameters ---
        total_layers = len(base_layers)
        
        # READ: The user's visual layer number (1 to N)
        user_layer_number = int(self.h_sweep_layer.text()) 
        
        # CORRECTION APPLIED: Map reversed user-numbering (1=bottom, N=top) 
        # to the 0-based list index (0=top, N-1=bottom).
        thick_layer_index = total_layers - user_layer_number

        thick_start = float(self.h_sweep_start.text())
        thick_end = float(self.h_sweep_end.text())
        thick_step = float(self.h_sweep_step.text())
        thick_values = np.arange(thick_start, thick_end + thick_step / 2, thick_step)

        # VALIDATION: Check the user's visual number
        if user_layer_number < 1 or user_layer_number > total_layers:
            raise ValueError(f"Thickness Sweep Layer Index must be between 1 (Bottom Layer) and {total_layers} (Top Layer).")
        if thick_start < 0 or thick_step <= 0 or thick_start >= thick_end:
            raise ValueError("Thickness sweep parameters are invalid.")

        swept_material = base_layers[thick_layer_index][0]
        thick_layer_text = str(user_layer_number) # Use the user's visual number for plot title

        # --- Get Angle Sweep Parameters ---
        angle_start = float(self.h_sweep_angle_start.text())
        angle_end = float(self.h_sweep_angle_end.text())
        angle_step = float(self.h_sweep_angle_step.text())
        angle_values = np.arange(angle_start, angle_end + angle_step / 2, angle_step)

        if angle_start < 0 or angle_end > 90 or angle_step <= 0 or angle_start >= angle_end:
            raise ValueError("Angle sweep values must be between 0 and 90 degrees, and step must be positive.")

        # Consolidate sweep parameters
        sweep_params = {
            'thick_layer_index': thick_layer_index, # 0-based index for the worker
            'thick_values': thick_values,
            'thick_step': thick_step,
            'thick_start': thick_start,
            'thick_end': thick_end,
            'angle_values': angle_values,
            'angle_step': angle_step,
            'angle_start': angle_start,
            'angle_end': angle_end,
            'swept_material': swept_material,
            'thick_layer_text': thick_layer_text # 1-based number for plot title
        }

        # Disable button, show status and progress bar
        self.h_chart_btn.setEnabled(False)
        self.h_chart_status_label.setText("Calculating Color Chart...")
        self.h_progress_bar.setValue(0)
        self.h_progress_bar.setVisible(True) # SHOW PROGRESS BAR

        # Create and start the worker thread
        self.worker_thread = QThread()
        lambda_full_vis = np.arange(380.0, 781.0, 1.0)
        self.worker = ColorChartWorker(base_layers, lambda_full_vis, sweep_params)
        self.worker.moveToThread(self.worker_thread)
        
        # Connect signals
        self.worker_thread.started.connect(self.worker.run_2d_sweep)
        self.worker.calculation_finished.connect(self._handle_2d_sweep_result)
        self.worker.calculation_error.connect(self._handle_worker_error)
        self.worker.progress_update.connect(self._update_progress_bar) # CONNECT PROGRESS SIGNAL
        self.worker.calculation_finished.connect(self.worker_thread.quit) # Stop thread on success
        self.worker.calculation_error.connect(self.worker_thread.quit) # Stop thread on error
        self.worker_thread.finished.connect(self._thread_cleanup)
        
        self.worker_thread.start()

    def _update_progress_bar(self, progress_value):
        """Updates the progress bar with the value emitted by the worker."""
        self.h_progress_bar.setValue(progress_value)

    def _handle_2d_sweep_result(self, result):
        """Called when the worker thread finishes successfully."""
        
        color_data_array = result['color_data']
        params = result['params']
        
        # Plotting remains on the main thread
        self._plot_2d_color_chart(
            color_data_array,
            params['thick_values'], params['thick_step'], params['thick_start'], params['thick_end'],
            params['angle_values'], params['angle_step'], params['angle_start'], params['angle_end'],
            params['swept_material'], params['thick_layer_text']
        )

    def _handle_worker_error(self, error_message):
        """Called if an error occurs in the worker thread."""
        QMessageBox.critical(self, "Background Error", error_message)
        
    def _thread_cleanup(self):
        """Cleans up the worker and thread after they quit."""
        self.worker_thread.deleteLater()
        self.worker.deleteLater()
        self.worker_thread = None
        self.worker = None
        
        self.h_chart_btn.setText("Generate Color Chart")
        self.h_chart_btn.setEnabled(True)
        self.h_progress_bar.setVisible(False) # HIDE PROGRESS BAR
        self.h_chart_status_label.setText("") # CLEAR STATUS LABEL


    def _generate_1d_color_chart_callback(self, is_thickness_sweep):
        """Generates a 1D color chart by sweeping either thickness or incident angle (Stays on main thread as it's typically fast)."""
        # ... (1D sweep logic) ...
        
        base_layers = self._get_current_layer_stack()
        lambda_full_vis = np.arange(380.0, 781.0, 1.0)
        if not base_layers: raise ValueError("Layer stack is empty. Cannot generate color chart.")
            
        if is_thickness_sweep:
            sweep_type = 'Thickness'
            total_layers = len(base_layers) # Get total layers
            
            # READ: The user's visual layer number (1 to N)
            user_layer_number = int(self.h_sweep_layer.text())
            
            # CORRECTION APPLIED: Map reversed user-numbering (1=bottom, N=top) 
            # to the 0-based list index (0=top, N-1=bottom).
            sweep_layer_index = total_layers - user_layer_number
            
            sweep_start = float(self.h_sweep_start.text())
            sweep_end = float(self.h_sweep_end.text())
            sweep_step = float(self.h_sweep_step.text())
            theta_inc_deg = float(self.h_angle.text())
            
            # Validation using the user's visual layer number
            if user_layer_number < 1 or user_layer_number > total_layers: 
                raise ValueError(f"Thickness Sweep Layer Index must be between 1 (Bottom Layer) and {total_layers} (Top Layer).");
                
            if sweep_start < 0 or sweep_step <= 0 or sweep_start >= sweep_end: 
                raise ValueError("Thickness sweep parameters are invalid.")
                
            swept_values = np.arange(sweep_start, sweep_end + sweep_step / 2, sweep_step)
            swept_material = base_layers[sweep_layer_index][0]
            fixed_value = theta_inc_deg
            layer_number = user_layer_number # Use visual number for plotting/titles
            
        else:
            sweep_type = 'Angle'
            sweep_start = float(self.h_sweep_angle_start.text())
            sweep_end = float(self.h_sweep_angle_end.text())
            sweep_step = float(self.h_sweep_angle_step.text())
            # For angle sweep, we use the first layer's thickness for context in the title
            sweep_layer_index = 0 
            fixed_value = base_layers[sweep_layer_index][1] # Get thickness of Layer 1 for context
            
            if sweep_start < 0 or sweep_end > 90 or sweep_step <= 0 or sweep_start >= sweep_end: 
                raise ValueError("Angle sweep values must be between 0 and 90 degrees, and step must be positive.")
                
            swept_values = np.arange(sweep_start, sweep_end + sweep_step / 2, sweep_step)
            swept_material = "Incident Angle"
            layer_number = sweep_layer_index + 1 # 1-based layer index for title context

        R_sRGB_chart = []
        for value in swept_values:
            if sweep_type == 'Thickness':
                # Use the corrected 0-based index for modification
                current_layers = [list(layer) for layer in base_layers]
                current_layers[sweep_layer_index][1] = value 
                Rs, Rp = calculate_reflectance(current_layers, self.DEFAULT_SUBSTRATE, lambda_full_vis, theta_inc_deg)
            elif sweep_type == 'Angle':
                Rs, Rp = calculate_reflectance(base_layers, self.DEFAULT_SUBSTRATE, lambda_full_vis, value)
                
            R_spectrum = (Rs + Rp) / 2.0
            R_sRGB, _, _ = calculate_colorimetry(R_spectrum, lambda_full_vis)
            R_sRGB_chart.append(R_sRGB)

        self._plot_1d_color_chart(np.array(R_sRGB_chart), swept_values, sweep_step, swept_material, sweep_type, fixed_value, layer_number)
        
    def _plot_1d_color_chart(self, sRGB_chart, swept_values, sweep_step, swept_material, sweep_type, fixed_value, layer_number):
        """Plots the thickness or angle sweep color chart (1D: single row of color) in a new Matplotlib figure."""
        if sweep_type == 'Thickness':
            window_title = f"Color Chart Sweep: {swept_material} (Layer {layer_number}) at {fixed_value:.0f}°"
            x_label = f"Thickness (nm) of Layer {layer_number}"
        else:
            window_title = f"Color Chart Sweep: Angle (Thickness of Layer {layer_number} fixed at {fixed_value:.1f} nm)"
            x_label = "Incident Angle (deg)"
        
        chart_window = QMainWindow(self); 
        chart_window.setWindowTitle(window_title)
        
        # Create Menu Bar for the chart window
        fig = Figure(); 
        self._create_chart_menu_bar(chart_window, fig) # PASS THE FIGURE AND WINDOW
        
        canvas = FigureCanvas(fig); 
        chart_window.setCentralWidget(canvas); 
        chart_window.resize(800, 300)
        
        chart_ax = fig.add_subplot(111); 
        color_matrix_for_display = sRGB_chart[np.newaxis, :, :] / 255.0
        sweep_end_boundary = swept_values[-1] + sweep_step
        chart_ax.imshow(color_matrix_for_display, aspect='auto', extent=[swept_values[0], sweep_end_boundary, 0, 1])
        chart_ax.set_yticks([]); chart_ax.set_ylim(0, 1)
        chart_ax.set_xlim(swept_values[0], sweep_end_boundary)
        chart_ax.set_title(window_title); chart_ax.set_xlabel(x_label); fig.subplots_adjust(bottom=0.20)
        canvas.draw(); 
        chart_window.show()

    def _plot_2d_color_chart(self, sRGB_chart_2d, thick_values, thick_step, thick_start, thick_end, angle_values, angle_step, angle_start, angle_end, swept_material, layer_number):
        """Plots the 2D color chart (thickness vs angle map) in a new Matplotlib figure."""
        
        window_title = f"2D Color Chart: {swept_material} (Layer {layer_number}) vs Incident Angle"
        
        chart_window = QMainWindow(self); 
        chart_window.setWindowTitle(window_title)
        
        # ADDED: Create Menu Bar for the chart window
        fig = Figure(); 
        self._create_chart_menu_bar(chart_window, fig) # PASS THE FIGURE AND WINDOW
        
        canvas = FigureCanvas(fig); 
        chart_window.setCentralWidget(canvas); 
        chart_window.resize(800, 300)
        
        chart_ax = fig.add_subplot(111); 
        color_matrix_for_display = sRGB_chart_2d / 255.0
        thick_end_boundary = thick_values[-1] + thick_step; angle_end_boundary = angle_values[-1] + angle_step
        
        # 1. Plot the color map
        chart_ax.imshow(
            color_matrix_for_display,
            aspect='auto',
            origin='lower',
            extent=[thick_start, thick_end_boundary, angle_start, angle_end_boundary]
        )
        
        # 2. Set Limits
        chart_ax.set_xlim(thick_start, thick_end_boundary); 
        chart_ax.set_ylim(angle_start, angle_end_boundary)
        
        # --- 3. Refined Automatic Ticks for the Angle Axis (Y-axis) ---
        
        # Check for the common, full 0 to 90 degree sweep
        if np.isclose(angle_start, 0.0) and np.isclose(angle_end, 90.0):
            # Explicitly set ticks to 0, 30, 60, 90 for the cleanest full axis
            final_ticks = [0.0, 30.0, 60.0, 90.0]
        else:
            # Use MaxNLocator for partial/unusual ranges (as in the previous step)
            locator = ticker.MaxNLocator(nbins=6, steps=[1, 2, 3, 4, 5, 10], prune='both')
            angle_ticks = locator.tick_values(angle_start, angle_end)

            final_ticks = set()
            final_ticks.add(angle_start)
            final_ticks.add(angle_end)
            for tick in angle_ticks:
                # Check for small floating point errors when adding ticks near boundaries
                if angle_start - 1e-6 <= tick <= angle_end + 1e-6:
                    final_ticks.add(tick)
            
            final_ticks = sorted(list(final_ticks))
            
        chart_ax.set_yticks(final_ticks) # DYNAMICALLY CALCULATED Ticks

        # 4. Set Labels and Draw
        chart_ax.set_title(window_title); 
        chart_ax.set_xlabel(f"Thickness (nm) of Layer {layer_number} ({swept_material})"); 
        chart_ax.set_ylabel("Incident Angle (°)")
        fig.subplots_adjust(left=0.15, right=0.95, top=0.9, bottom=0.15)
        canvas.draw(); 
        chart_window.show()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_app = ReflectanceApp()
    main_app.show()
    sys.exit(app.exec())
