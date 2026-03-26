import sys
import os
import csv
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QFileDialog, QProgressBar, QMessageBox,
                             QGroupBox)
from PyQt6.QtGui import QIcon, QAction, QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal

def calcular_digito_control(imei14: str) -> str:
    """Calcula el dígito de control para un IMEI de 14 dígitos usando algoritmo Luhn."""
    if len(imei14) != 14 or not imei14.isdigit():
        raise ValueError("El IMEI de entrada debe tener exactamente 14 números.")
    
    suma = 0
    flip = True
    
    # Siguiendo la lógica proporcionada iterando desde el final
    for i in range(13, -1, -1):
        digit = int(imei14[i])
        if flip:
            double = digit * 2
            if double > 9:
                double -= 9
            suma += double
            flip = False
        else:
            suma += digit
            flip = True
            
    cd = 10 - (suma % 10)
    return str(0 if cd == 10 else cd)

def verificar_imei(imei15: str) -> bool:
    """Verifica si un IMEI de 15 dígitos es válido."""
    if len(imei15) != 15 or not imei15.isdigit():
        return False
    return calcular_digito_control(imei15[:14]) == imei15[-1]

def procesar_archivo(ruta_entrada: str, ruta_salida: str, worker) -> dict:
    """Procesa un archivo por lotes, separado como función independiente."""
    imeis = []
    if ruta_entrada.lower().endswith('.csv'):
        with open(ruta_entrada, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                for item in row:
                    val = item.strip()
                    if val: imeis.append(val)
    else:
        with open(ruta_entrada, 'r', encoding='utf-8') as f:
            imeis = [line.strip() for line in f if line.strip()]

    total = len(imeis)
    if total == 0:
        raise ValueError("El archivo está vacío o no contiene líneas legibles.")

    validos, invalidos, completados = 0, 0, 0
    resultados = []

    for i, imei in enumerate(imeis):
        imei_clean = ''.join(filter(str.isdigit, imei))
        estado = "Inválido (Formato erróneo)"
        imei_salida = imei_clean

        if len(imei_clean) == 14:
            try:
                digito = calcular_digito_control(imei_clean)
                imei_salida = imei_clean + digito
                estado = "Completado y Válido"
                completados += 1
                validos += 1
            except Exception:
                estado = "Error al calcular"
                invalidos += 1
        elif len(imei_clean) == 15:
            if verificar_imei(imei_clean):
                estado = "Válido"
                validos += 1
            else:
                estado = "Inválido (Dígito de control incorrecto)"
                invalidos += 1
        else:
            invalidos += 1

        resultados.append(f"{imei_salida},{estado}\n")
        
        # Reportar progreso
        worker.reportar_progreso(int(((i + 1) / total) * 100))

    with open(ruta_salida, 'w', encoding='utf-8') as f:
        f.write("IMEI,ESTADO\n")
        f.writelines(resultados)

    return {
        "total": total, "validos": validos, "invalidos": invalidos, 
        "completados": completados, "ruta_salida": ruta_salida
    }


class ProcesadorArchivoWorker(QThread):
    progreso = pyqtSignal(int)
    terminado = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, ruta_entrada, ruta_salida):
        super().__init__()
        self.ruta_entrada = ruta_entrada
        self.ruta_salida = ruta_salida

    def reportar_progreso(self, val):
        self.progreso.emit(val)

    def run(self):
        try:
            stats = procesar_archivo(self.ruta_entrada, self.ruta_salida, self)
            self.terminado.emit(stats)
        except Exception as e:
            self.error.emit(str(e))


class ImeiCheckApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IMEI Check Tool")
        self.setMinimumSize(600, 550)
        
        icon_path = os.path.join(os.path.dirname(__file__), "imei_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.ruta_entrada = None
        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        # Menu Bar
        menubar = self.menuBar()
        archivo_menu = menubar.addMenu("Archivo")
        
        salir_action = QAction("Salir", self)
        salir_action.shortcut = "Ctrl+Q"
        salir_action.triggered.connect(self.close)
        archivo_menu.addAction(salir_action)

        ayuda_menu = menubar.addMenu("Ayuda")
        acerca_de_action = QAction("Acerca de", self)
        acerca_de_action.triggered.connect(self.show_about)
        ayuda_menu.addAction(acerca_de_action)

        # Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(20)

        # App Title
        title_lbl = QLabel("IMEI Check Tool")
        title_lbl.setObjectName("mainTitle")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        # 1. Single IMEI Verification
        group_single = QGroupBox("Verificación Individual")
        single_layout = QVBoxLayout(group_single)
        single_layout.setSpacing(15)

        input_layout = QHBoxLayout()
        self.txt_imei = QLineEdit()
        self.txt_imei.setPlaceholderText("Introduce 14 o 15 dígitos aquí...")
        self.txt_imei.setMaxLength(15)
        
        self.btn_calc = QPushButton("Calcular Dígito / Verificar IMEI")
        self.btn_calc.clicked.connect(self.verificar_individual)
        self.txt_imei.returnPressed.connect(self.verificar_individual)
        
        input_layout.addWidget(self.txt_imei)
        input_layout.addWidget(self.btn_calc)
        single_layout.addLayout(input_layout)

        self.lbl_resultado_individual = QLabel("")
        self.lbl_resultado_individual.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_resultado_individual.setWordWrap(True)
        self.lbl_resultado_individual.setMinimumHeight(40)
        single_layout.addWidget(self.lbl_resultado_individual)
        
        layout.addWidget(group_single)

        # 2. File Processing
        group_file = QGroupBox("Procesamiento de Archivos (.txt, .csv)")
        file_layout = QVBoxLayout(group_file)
        file_layout.setSpacing(15)

        btn_file_layout = QHBoxLayout()
        btn_file_layout.setSpacing(10)
        self.lbl_archivo = QLabel("Ningún archivo seleccionado")
        
        btn_cargar = QPushButton("Cargar archivo")
        btn_cargar.clicked.connect(self.cargar_archivo)
        
        btn_procesar = QPushButton("Procesar archivo")
        btn_procesar.clicked.connect(self.procesar_lote)
        
        btn_file_layout.addWidget(self.lbl_archivo, stretch=1)
        btn_file_layout.addWidget(btn_cargar)
        btn_file_layout.addWidget(btn_procesar)
        file_layout.addLayout(btn_file_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()
        file_layout.addWidget(self.progress_bar)

        layout.addWidget(group_file)

        # 3. Log Output
        log_label = QLabel("Registro de operaciones y resultados:")
        log_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        layout.addWidget(log_label)
        
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setPlaceholderText("> Las salidas del programa aparecerán aquí.")
        layout.addWidget(self.log_area, stretch=1)

    def apply_styles(self):
        style = """
        QMainWindow {
            background-color: #fcfcfc;
        }
        QLabel#mainTitle {
            font-size: 26px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 5px;
            letter-spacing: 1px;
        }
        QGroupBox {
            font-size: 14px;
            font-weight: bold;
            color: #34495e;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            margin-top: 20px;
            background-color: white;
            padding: 15px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 15px;
            padding: 0 5px;
            color: #3498db;
        }
        QLineEdit {
            padding: 12px;
            border: 1px solid #dcdde1;
            border-radius: 6px;
            font-size: 14px;
            background-color: #fefefe;
            color: #2c3e50;
        }
        QLineEdit:focus {
            border: 2px solid #3498db;
            background-color: #ffffff;
        }
        QPushButton {
            padding: 12px 18px;
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 13px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #2980b9;
        }
        QPushButton:pressed {
            background-color: #1c5980;
        }
        QTextEdit {
            border: 1px solid #dcdde1;
            border-radius: 6px;
            background-color: #f7f9fa;
            font-family: Consolas, "Courier New", monospace;
            font-size: 13px;
            color: #2c3e50;
            padding: 10px;
        }
        QProgressBar {
            border: 1px solid #dcdde1;
            border-radius: 6px;
            text-align: center;
            background-color: #f7f9fa;
            font-weight: bold;
            color: #2c3e50;
        }
        QProgressBar::chunk {
            background-color: #2ecc71;
            border-radius: 5px;
        }
        QMessageBox {
            background-color: #ffffff;
            color: #2c3e50;
        }
        """
        self.setStyleSheet(style)

    def log(self, msj: str):
        self.log_area.append(f"> {msj}")
        # Scroll al fondo
        sb = self.log_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def verificar_individual(self):
        imei = self.txt_imei.text().strip()
        
        if not imei.isdigit():
            self.lbl_resultado_individual.setStyleSheet("color: #e74c3c; font-size: 15px; font-weight: bold;")
            self.lbl_resultado_individual.setText("Error: Introduce únicamente dígitos sin espacios ni letras.")
            return

        if len(imei) == 14:
            self.log(f"Calculando dígito para: {imei}")
            try:
                digito = calcular_digito_control(imei)
                imei_completo = imei + digito
                self.lbl_resultado_individual.setStyleSheet("color: #27ae60; font-size: 16px; font-weight: bold;")
                self.lbl_resultado_individual.setText(f"✓ Dígito de control: {digito} (IMEI Completo: {imei_completo})")
                self.log(f"Completado exitosamente: {imei} -> {imei_completo}")
                self.txt_imei.setText(imei_completo)
            except Exception as e:
                self.lbl_resultado_individual.setText(f"Error: {e}")
        elif len(imei) == 15:
            self.log(f"Verificando validez del arreglo IMEI: {imei}")
            if verificar_imei(imei):
                self.lbl_resultado_individual.setStyleSheet("color: #27ae60; font-size: 16px; font-weight: bold;")
                self.lbl_resultado_individual.setText(f"✓ El IMEI {imei} es TOTALMENTE VÁLIDO.")
                self.log(f"Verificado: {imei} -> [Válido]")
            else:
                self.lbl_resultado_individual.setStyleSheet("color: #c0392b; font-size: 16px; font-weight: bold;")
                self.lbl_resultado_individual.setText(f"✗ El IMEI {imei} NO ES VÁLIDO (Falló algoritmo Luhn).")
                self.log(f"Verificado: {imei} -> [Inválido]")
        else:
            self.lbl_resultado_individual.setStyleSheet("color: #e67e22; font-size: 14px; font-weight: bold;")
            self.lbl_resultado_individual.setText(f"Aviso: Longitud incorrecta ({len(imei)} dígitos). Introduce numéricamente 14 o 15 dígitos.")

    def cargar_archivo(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo de IMEIs", "", "Archivos Soportados (*.txt *.csv);;Todos (*)")
        if ruta:
            self.ruta_entrada = ruta
            archivo_nombre = os.path.basename(ruta)
            self.lbl_archivo.setText(f".../{archivo_nombre}")
            self.log(f"Archivo de entrada cargado: {ruta}")

    def procesar_lote(self):
        if not self.ruta_entrada:
            QMessageBox.warning(self, "Acción requerida", "Primero debes cargar un archivo .txt o .csv con los IMEIs.")
            return

        ruta_salida, _ = QFileDialog.getSaveFileName(self, "Guardar resultados filtrados como", "resultados_imei.csv", "Archivo CSV (*.csv)")
        if not ruta_salida:
            return

        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.log(f"Desplegando procesamiento asíncrono sobre -> {os.path.basename(self.ruta_entrada)}...")

        self.worker = ProcesadorArchivoWorker(self.ruta_entrada, ruta_salida)
        self.worker.progreso.connect(self.progress_bar.setValue)
        self.worker.terminado.connect(self.procesamiento_completado)
        self.worker.error.connect(self.procesamiento_error)
        self.worker.start()

    def procesamiento_completado(self, stats):
        self.progress_bar.hide()
        msg = (
            f"El procesamiento ha concluido existosamente.\n\n"
            f"• Total IMEIs identificados procesados: {stats['total']}\n"
            f"• ✓ Completados y/o Válidos: {stats['validos']}\n"
            f"• ✗ Inválidos o con error de forma: {stats['invalidos']}\n\n"
            f"Datos depurados guardados íntegramente en:\n{stats['ruta_salida']}"
        )
        self.log("=== Procesamiento Lotes Finalizado ===")
        self.log(f"Total: {stats['total']} | Válidos: {stats['validos']} | Inválidos: {stats['invalidos']}")
        QMessageBox.information(self, "Procesamiento Completo", msg)

    def procesamiento_error(self, err_msg):
        self.progress_bar.hide()
        self.log(f"Error procesando archivo mediante thread: {err_msg}")
        QMessageBox.critical(self, "Error Fatal", f"Ocurrió un error inesperado al procesar el archivo por lotes:\n\n{err_msg}")

    def show_about(self):
        info_html = (
            "<div style='text-align: center; font-family: sans-serif;'>"
            "<h2 style='color: #2c3e50;'>IMEI Check Tool</h2>"
            "<p style='color: #7f8c8d;'><b>Versión:</b> 1.0</p>"
            "<br>"
            "<p><b>Creador:</b> Roberto Getino García</p>"
            "<p><b>Sitio Web:</b> <a href='https://www.pulchratech.com' style='color: #3498db; text-decoration: none;'>https://www.pulchratech.com</a></p>"
            "<p><b>GitHub:</b> <a href='https://www.github.com/noclastic/imei_check_tool' style='color: #3498db; text-decoration: none;'>https://www.github.com/noclastic/imei_check_tool</a></p>"
            "<hr style='border: 0; height: 1px; background: #ecf0f1; margin: 15px 0;'>"
            "<p style='color: #34495e; font-size: 13px; text-align: justify;'>"
            "Herramienta de software diseñada con estética minimalista y profesional para verificar y calcular dígitos de control de internacional de equipos móviles (IMEI), garantizando validaciones de checksum usando el algoritmo estandarizado Luhn."
            "</p>"
            "</div>"
        )
        QMessageBox.about(self, "Acerca de IMEI Check Tool", info_html)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Fuentes más modernas
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = ImeiCheckApp()
    window.show()
    sys.exit(app.exec())
