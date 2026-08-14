#!/usr/bin/env python3
import serial
import serial.tools.list_ports
import customtkinter as ctk
import threading
import time
import sys
import os
from datetime import datetime
from PIL import Image, ImageTk
import subprocess
import math

# Configurar tema
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ControlMotor:
    def __init__(self, root):
        self.root = root
        self.root.title("🎯 Inspección")
        self.root.geometry("800x480")
        self.root.resizable(False, False)
        self.root.attributes('-topmost', True)
        
        # Variables de conexión
        self.ser = None
        self.conectado = False
        self.lectura_activa = False
        
        # Variables de estado
        self.motor_habilitado = False
        self.moviendo = False
        self.pasos_restantes = 0
        self.pasos_totales = 0
        self.progreso = 0
        self.movimiento_completado = False
        self.en_home = False
        self.done_recibido = False
        self.home_exitoso = False
        self.home_timeout = False
        self.esperando_home = False
        self.buscando_home = False
        
        # Variables de cámara
        self.camara_disponible = False
        self.ultima_foto_path = None
        self.ultima_foto_img = None
        
        # Variables de inspección
        self.fotos_tomadas = 0
        self.total_fotos = 0
        self.pasos_por_bloque = []
        self.pasos_totales_movimiento = 0
        self.inspeccion_activa = False
        self.detener_inspeccion = False
        self.bloque_actual = 0
        
        # Directorio de fotos
        self.carpeta_fotos = os.path.expanduser("~/Documentos/detector/fotos")
        os.makedirs(self.carpeta_fotos, exist_ok=True)
        
        # Variables de sentido de giro
        self.sentido_home = 1
        self.sentido_giro_actual = 0
        
        # Variables para teclado numérico
        self.teclado_visible = False
        self.teclado_window = None
        self.campo_teclado_actual = None
        
        # Variables de luces
        self.luces_encendidas = False
        
        # Crear interfaz
        self.crear_interfaz()
        
        # Conectar automáticamente al puerto ttyUSB0
        self.conectar_automatico()
        
        # Verificar cámara
        self.verificar_camara()
    
    def conectar_automatico(self):
        """Conecta automáticamente al puerto ttyUSB0"""
        try:
            puerto = "/dev/ttyUSB0"
            self.ser = serial.Serial(puerto, 115200, timeout=1)
            time.sleep(2)
            self.conectado = True
            self.lectura_activa = True
            
            self.lbl_estado.configure(text="✅ Conectado", text_color="#2ecc71")
            
            self.hilo_lectura = threading.Thread(target=self.leer_serial, daemon=True)
            self.hilo_lectura.start()
            
            self.log(f"✅ Conectado automáticamente a {puerto}", "OK")
            self.consultar_estado()
            
            self.enviar_comando("SET_HOME_DIR=1")
            self.log("✅ Sentido HOME configurado a BAJAR (sensor inferior)", "OK")
            
        except Exception as e:
            self.log(f"⚠️ No se pudo conectar a /dev/ttyUSB0: {e}", "WARNING")
    
    def verificar_camara(self):
        """Verifica que rpicam-still esté disponible"""
        try:
            subprocess.run(['rpicam-still', '--version'], capture_output=True, check=True)
            self.camara_disponible = True
            self.lbl_estado_camara.configure(text="📷 Cámara lista", text_color="#2ecc71")
            self.log("✅ Cámara disponible (rpicam-still)", "OK")
        except:
            self.camara_disponible = False
            self.lbl_estado_camara.configure(text="❌ Cámara no disponible", text_color="#e74c3c")
            self.log("❌ rpicam-still no instalado", "ERROR")
    
    # ==================== TECLADO NUMÉRICO MEJORADO ====================
    def abrir_teclado(self, event=None, campo="soldadura"):
        """Abre un teclado numérico emergente para el campo especificado"""
        if self.teclado_visible:
            return
        
        self.teclado_visible = True
        self.campo_teclado_actual = campo
        
        # Obtener el texto actual del campo
        if campo == "soldadura":
            texto_actual = self.entry_soldadura.get()
            titulo = "📏 Soldadura (cm) [4-16]"
            es_numerico = True
        else:  # carpeta
            texto_actual = self.entry_carpeta.get()
            titulo = "📁 Nombre Carpeta"
            es_numerico = False
        
        # Crear ventana emergente
        self.teclado_window = ctk.CTkToplevel(self.root)
        self.teclado_window.title(titulo)
        self.teclado_window.geometry("450x400")
        self.teclado_window.resizable(False, False)
        self.teclado_window.attributes('-topmost', True)
        
        # Frame principal
        frame = ctk.CTkFrame(self.teclado_window)
        frame.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)
        
        # Label de título
        ctk.CTkLabel(frame, text=titulo, font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(0, 5))
        
        # Display del texto
        self.display_teclado = ctk.CTkEntry(
            frame,
            font=ctk.CTkFont(size=20, weight="bold"),
            justify="center",
            height=50
        )
        self.display_teclado.pack(fill=ctk.X, padx=5, pady=5)
        self.display_teclado.insert(0, texto_actual)
        self.display_teclado.focus_set()
        
        # Frame para botones
        btn_frame = ctk.CTkFrame(frame)
        btn_frame.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)
        
        if es_numerico:
            # ===== TECLADO NUMÉRICO (para soldadura) =====
            numeros = [
                ['7', '8', '9'],
                ['4', '5', '6'],
                ['1', '2', '3'],
                ['0', '⌫']
            ]
            
            for i, fila in enumerate(numeros):
                for j, valor in enumerate(fila):
                    if valor == '⌫':
                        btn = ctk.CTkButton(
                            btn_frame,
                            text=valor,
                            font=ctk.CTkFont(size=20, weight="bold"),
                            command=self.borrar_teclado,
                            fg_color="#e67e22",
                            hover_color="#d35400"
                        )
                    else:
                        btn = ctk.CTkButton(
                            btn_frame,
                            text=valor,
                            font=ctk.CTkFont(size=20, weight="bold"),
                            command=lambda v=valor: self.agregar_teclado(v)
                        )
                    
                    btn.grid(row=i, column=j, padx=3, pady=3, sticky="nsew")
                    btn_frame.grid_rowconfigure(i, weight=1)
                    btn_frame.grid_columnconfigure(j, weight=1)
            
            # Label de rango
            ctk.CTkLabel(
                frame, 
                text="📌 Rango permitido: 4 a 16 cm", 
                font=ctk.CTkFont(size=10), 
                text_color="gray"
            ).pack(pady=(0, 5))
            
            # Fila de botones de acción (OK y Cancelar)
            frame_acciones = ctk.CTkFrame(frame)
            frame_acciones.pack(fill=ctk.X, padx=5, pady=5)
            
            btn_ok = ctk.CTkButton(
                frame_acciones,
                text="✅ OK",
                font=ctk.CTkFont(size=16, weight="bold"),
                command=self.confirmar_teclado,
                fg_color="#2ecc71",
                hover_color="#27ae60",
                height=40
            )
            btn_ok.pack(side=ctk.LEFT, padx=3, fill=ctk.X, expand=True)
            
            btn_cancel = ctk.CTkButton(
                frame_acciones,
                text="✕ Cancelar",
                font=ctk.CTkFont(size=16, weight="bold"),
                command=self.cerrar_teclado,
                fg_color="#e74c3c",
                hover_color="#c0392b",
                height=40
            )
            btn_cancel.pack(side=ctk.LEFT, padx=3, fill=ctk.X, expand=True)
            
        else:
            # ===== TECLADO ALFANUMÉRICO (para carpeta) =====
            filas = [
                ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
                ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
                ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', 'Ñ'],
                ['Z', 'X', 'C', 'V', 'B', 'N', 'M', '_', '-', '⌫']
            ]
            
            for i, fila in enumerate(filas):
                for j, valor in enumerate(fila):
                    if valor == '⌫':
                        btn = ctk.CTkButton(
                            btn_frame,
                            text=valor,
                            font=ctk.CTkFont(size=18, weight="bold"),
                            command=self.borrar_teclado,
                            fg_color="#e67e22",
                            hover_color="#d35400",
                            height=35
                        )
                    else:
                        btn = ctk.CTkButton(
                            btn_frame,
                            text=valor,
                            font=ctk.CTkFont(size=16, weight="bold"),
                            command=lambda v=valor: self.agregar_teclado(v),
                            height=35
                        )
                    
                    btn.grid(row=i, column=j, padx=2, pady=2, sticky="nsew")
                    btn_frame.grid_rowconfigure(i, weight=1)
                    btn_frame.grid_columnconfigure(j, weight=1)
            
            # Fila de botones de acción (OK y Cancelar)
            frame_acciones = ctk.CTkFrame(frame)
            frame_acciones.pack(fill=ctk.X, padx=5, pady=5)
            
            btn_ok = ctk.CTkButton(
                frame_acciones,
                text="✅ OK",
                font=ctk.CTkFont(size=16, weight="bold"),
                command=self.confirmar_teclado,
                fg_color="#2ecc71",
                hover_color="#27ae60",
                height=35
            )
            btn_ok.pack(side=ctk.LEFT, padx=3, fill=ctk.X, expand=True)
            
            btn_cancel = ctk.CTkButton(
                frame_acciones,
                text="✕ Cancelar",
                font=ctk.CTkFont(size=16, weight="bold"),
                command=self.cerrar_teclado,
                fg_color="#e74c3c",
                hover_color="#c0392b",
                height=35
            )
            btn_cancel.pack(side=ctk.LEFT, padx=3, fill=ctk.X, expand=True)
        
        # Configurar cierre de ventana
        self.teclado_window.protocol("WM_DELETE_WINDOW", self.cerrar_teclado)
    
    def agregar_teclado(self, valor):
        """Agrega un carácter al display del teclado"""
        actual = self.display_teclado.get()
        if len(actual) < 50:
            self.display_teclado.delete(0, ctk.END)
            self.display_teclado.insert(0, actual + valor)
    
    def borrar_teclado(self):
        """Borra el último carácter"""
        actual = self.display_teclado.get()
        if len(actual) > 0:
            self.display_teclado.delete(0, ctk.END)
            self.display_teclado.insert(0, actual[:-1])
    
    def confirmar_teclado(self):
        """Confirma el texto y lo pasa al campo correspondiente con validación"""
        valor = self.display_teclado.get().strip()
        
        if self.campo_teclado_actual == "soldadura":
            # Validar que sea un número
            if not valor or not valor.replace('.', '').isdigit():
                self.log("⚠️ Valor inválido para soldadura", "WARNING")
                self.mostrar_error_teclado("❌ Ingrese un número válido")
                return
            
            # Convertir a float para validar rango
            try:
                valor_float = float(valor)
            except:
                self.log("⚠️ Valor inválido para soldadura", "WARNING")
                self.mostrar_error_teclado("❌ Ingrese un número válido")
                return
            
            # Validar rango 4-16
            if valor_float < 4:
                self.log(f"⚠️ Valor {valor_float} es menor a 4, ajustando a 4", "WARNING")
                self.display_teclado.delete(0, ctk.END)
                self.display_teclado.insert(0, "4")
                self.mostrar_error_teclado("📌 Mínimo: 4 cm")
                return
            elif valor_float > 16:
                self.log(f"⚠️ Valor {valor_float} es mayor a 16, ajustando a 16", "WARNING")
                self.display_teclado.delete(0, ctk.END)
                self.display_teclado.insert(0, "16")
                self.mostrar_error_teclado("📌 Máximo: 16 cm")
                return
            
            # Valor válido - guardar con formato limpio
            # Si es entero, guardar sin decimales
            if valor_float == int(valor_float):
                valor_guardar = str(int(valor_float))
            else:
                valor_guardar = str(valor_float)
            
            self.entry_soldadura.delete(0, ctk.END)
            self.entry_soldadura.insert(0, valor_guardar)
            self.log(f"✅ Soldadura: {valor_guardar} cm", "OK")
            
        else:  # carpeta
            # Limpiar caracteres no permitidos
            if valor:
                valor_limpio = ''.join(c for c in valor if c.isalnum() or c in '_-')
                if valor_limpio:
                    self.entry_carpeta.delete(0, ctk.END)
                    self.entry_carpeta.insert(0, valor_limpio)
                    self.log(f"✅ Carpeta: {valor_limpio}", "OK")
                else:
                    self.log("⚠️ Nombre de carpeta inválido", "WARNING")
                    self.mostrar_error_teclado("❌ Nombre inválido")
                    return
            else:
                self.entry_carpeta.delete(0, ctk.END)
                self.entry_carpeta.insert(0, "inspeccion")
                self.log("✅ Carpeta: inspeccion (valor por defecto)", "OK")
        
        self.cerrar_teclado()
    
    def mostrar_error_teclado(self, mensaje):
        """Muestra un mensaje de error en el teclado"""
        # Crear un label de error temporal
        frame = self.teclado_window
        error_label = ctk.CTkLabel(
            frame,
            text=mensaje,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e74c3c"
        )
        error_label.pack(pady=(0, 5))
        
        # Programar eliminación después de 2 segundos
        def eliminar_error():
            try:
                error_label.destroy()
            except:
                pass
        
        self.root.after(2000, eliminar_error)
    
    def cerrar_teclado(self):
        """Cierra el teclado sin guardar cambios"""
        self.teclado_visible = False
        self.campo_teclado_actual = None
        if self.teclado_window:
            self.teclado_window.destroy()
            self.teclado_window = None

    def crear_interfaz(self):
        # Frame principal
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill=ctk.BOTH, expand=True, padx=3, pady=3)
        
        # ==================== PANEL SUPERIOR ====================
        frame_superior = ctk.CTkFrame(self.main_frame, height=25)
        frame_superior.pack(fill=ctk.X, pady=(0, 2))
        frame_superior.pack_propagate(False)
        
        ctk.CTkLabel(frame_superior, text="🎯 Inspección", font=ctk.CTkFont(size=12, weight="bold")).pack(side=ctk.LEFT, padx=3)
        self.lbl_estado = ctk.CTkLabel(frame_superior, text="⚪ Desconectado", font=ctk.CTkFont(size=9))
        self.lbl_estado.pack(side=ctk.LEFT, padx=5)
        self.lbl_estado_camara = ctk.CTkLabel(frame_superior, text="📷 Verificando...", font=ctk.CTkFont(size=9))
        self.lbl_estado_camara.pack(side=ctk.RIGHT, padx=3)
        
        # ==================== PANEL PRINCIPAL (3 COLUMNAS) ====================
        panel_principal = ctk.CTkFrame(self.main_frame)
        panel_principal.pack(fill=ctk.BOTH, expand=True)
        
        # ----- COLUMNA IZQUIERDA (Configuración + Controles Motor) -----
        frame_izquierdo = ctk.CTkFrame(panel_principal, width=250)
        frame_izquierdo.pack(side=ctk.LEFT, fill=ctk.Y, padx=(0, 2))
        frame_izquierdo.pack_propagate(False)
        
        # --- Configuración ---
        frame_config = ctk.CTkFrame(frame_izquierdo)
        frame_config.pack(fill=ctk.X, pady=1)
        
        ctk.CTkLabel(frame_config, text="📏 Configuración", font=ctk.CTkFont(size=10, weight="bold")).pack(anchor=ctk.W, padx=3)
        
        # Soldadura (cm) - Con teclado numérico
        frame_sold = ctk.CTkFrame(frame_config)
        frame_sold.pack(fill=ctk.X, padx=3, pady=1)
        ctk.CTkLabel(frame_sold, text="Soldadura (cm):", font=ctk.CTkFont(size=9)).pack(side=ctk.LEFT, padx=2)
        self.entry_soldadura = ctk.CTkEntry(frame_sold, width=70, font=ctk.CTkFont(size=10), justify="center")
        self.entry_soldadura.pack(side=ctk.LEFT, padx=2)
        self.entry_soldadura.insert(0, "10")
        self.entry_soldadura.bind("<Button-1>", lambda e: self.abrir_teclado(e, "soldadura"))
        
        # Label de rango
        ctk.CTkLabel(
            frame_sold, 
            text="(4-16 cm)", 
            font=ctk.CTkFont(size=8), 
            text_color="gray"
        ).pack(side=ctk.LEFT, padx=2)
        
        # Carpeta - Con teclado alfanumérico
        frame_carpeta = ctk.CTkFrame(frame_config)
        frame_carpeta.pack(fill=ctk.X, padx=3, pady=1)
        ctk.CTkLabel(frame_carpeta, text="Carpeta:", font=ctk.CTkFont(size=9)).pack(side=ctk.LEFT, padx=2)
        self.entry_carpeta = ctk.CTkEntry(frame_carpeta, width=100, font=ctk.CTkFont(size=9))
        self.entry_carpeta.pack(side=ctk.LEFT, padx=2)
        self.entry_carpeta.insert(0, "inspeccion")
        self.entry_carpeta.bind("<Button-1>", lambda e: self.abrir_teclado(e, "carpeta"))
        
        # Checkbox volver
        self.check_volver = ctk.CTkCheckBox(
            frame_config,
            text="Volver al inicio",
            font=ctk.CTkFont(size=9)
        )
        self.check_volver.pack(anchor=ctk.W, padx=3, pady=1)
        self.check_volver.select()
        
        # Info pasos
       # ctk.CTkLabel(frame_config, text="⚙️ 1000 pasos = 1cm", 
        #            font=ctk.CTkFont(size=8), text_color="gray").pack(pady=1)
        
        # --- Controles Motor ---
        frame_controles = ctk.CTkFrame(frame_izquierdo)
        frame_controles.pack(fill=ctk.X, pady=1)
        
        ctk.CTkLabel(frame_controles, text="🔧 Control Motor", font=ctk.CTkFont(size=10, weight="bold")).pack(anchor=ctk.W, padx=3)
        
        # Fila 1: ENABLE + DISABLE + LUZ 
        frame_botones1 = ctk.CTkFrame(frame_controles)
        frame_botones1.pack(fill=ctk.X, pady=1, padx=3)
        
        self.btn_enable = ctk.CTkButton(
            frame_botones1, text="🔓 ENABLE", command=self.habilitar,
            width=80, height=34, fg_color="#2ecc71", font=ctk.CTkFont(size=12)
        )
        self.btn_enable.pack(side=ctk.LEFT, padx=1)
        
        self.btn_disable = ctk.CTkButton(
            frame_botones1, text="🔒 DISABLE", command=self.deshabilitar,
            width=80, height=34, fg_color="#95a5a6", font=ctk.CTkFont(size=12)
        )
        self.btn_disable.pack(side=ctk.LEFT, padx=1)
        
        self.btn_luz = ctk.CTkButton(
            frame_botones1, text="💡 LUZ", command=self.toggle_luz,
            width=80, height=34, fg_color="#f39c12", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_luz.pack(side=ctk.LEFT, padx=1)
        
        # Fila 2: INSPECCIONAR
        frame_botones2 = ctk.CTkFrame(frame_controles)
        frame_botones2.pack(fill=ctk.X, pady=3, padx=3)
        
        self.btn_inspeccion = ctk.CTkButton(
            frame_botones2, text="📷 INSPECCIONAR", command=self.iniciar_inspeccion,
            height=38, fg_color="#9b59b6", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.btn_inspeccion.pack(fill=ctk.X, padx=1)
        
        # --- Estado ---
        frame_estado = ctk.CTkFrame(frame_izquierdo)
        frame_estado.pack(fill=ctk.X, pady=1)
        
        ctk.CTkLabel(frame_estado, text="📊 Estado", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor=ctk.W, padx=3)
        
        grid_estado = ctk.CTkFrame(frame_estado)
        grid_estado.pack(fill=ctk.X, padx=3, pady=1)
        
        self.lbl_estado_motor = ctk.CTkLabel(grid_estado, text="Motor: ⚪", font=ctk.CTkFont(size=12))
        self.lbl_estado_motor.grid(row=0, column=0, padx=2, sticky=ctk.W)
        
        self.lbl_moviendo = ctk.CTkLabel(grid_estado, text="Mov: ⚪", font=ctk.CTkFont(size=12))
        self.lbl_moviendo.grid(row=0, column=1, padx=2, sticky=ctk.W)
        
        self.lbl_home = ctk.CTkLabel(grid_estado, text="Home: ⚪", font=ctk.CTkFont(size=12))
        self.lbl_home.grid(row=1, column=0, padx=2, sticky=ctk.W)
        
        self.lbl_pasos = ctk.CTkLabel(grid_estado, text="Pasos: 0", font=ctk.CTkFont(size=12))
        self.lbl_pasos.grid(row=1, column=1, padx=2, sticky=ctk.W)
        
        # --- Progreso ---
        frame_progreso = ctk.CTkFrame(frame_izquierdo)
        frame_progreso.pack(fill=ctk.X, pady=1)
        
        ctk.CTkLabel(frame_progreso, text="📈 Progreso", font=ctk.CTkFont(size=10, weight="bold")).pack(anchor=ctk.W, padx=3)
        
        self.progressbar = ctk.CTkProgressBar(frame_progreso, height=10)
        self.progressbar.pack(fill=ctk.X, padx=3, pady=1)
        self.progressbar.set(0)
        
        frame_info_prog = ctk.CTkFrame(frame_progreso)
        frame_info_prog.pack(fill=ctk.X, padx=3)
        
        self.lbl_progreso = ctk.CTkLabel(frame_info_prog, text="0%", font=ctk.CTkFont(size=8))
        self.lbl_progreso.pack(side=ctk.LEFT)
        
        self.lbl_fotos = ctk.CTkLabel(frame_info_prog, text="📸 0/0", font=ctk.CTkFont(size=8))
        self.lbl_fotos.pack(side=ctk.RIGHT)
        
        self.lbl_estado_actual = ctk.CTkLabel(frame_progreso, text="Esperando...", font=ctk.CTkFont(size=8), text_color="#3498db")
        self.lbl_estado_actual.pack(anchor=ctk.W, padx=3, pady=1)
        
        # ----- COLUMNA CENTRAL (Sentido giro + HOME + LOG) -----
        frame_central = ctk.CTkFrame(panel_principal, width=110)
        frame_central.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=True, padx=(0, 2))
        frame_central.pack_propagate(False)
        
        # --- Sentido Giro ---
        frame_sentido = ctk.CTkFrame(frame_central)
        frame_sentido.pack(fill=ctk.X, pady=1)
        
        ctk.CTkLabel(frame_sentido, text="🔄 Sentido", font=ctk.CTkFont(size=10, weight="bold")).pack(anchor=ctk.W, padx=3)
        
        # Sentido HOME
        frame_home_dir = ctk.CTkFrame(frame_sentido)
        frame_home_dir.pack(fill=ctk.X, padx=3, pady=1)
        ctk.CTkLabel(frame_home_dir, text="HOME:", font=ctk.CTkFont(size=8)).pack(side=ctk.LEFT, padx=2)
        
        self.combo_sentido_home = ctk.CTkComboBox(
            frame_home_dir,
            values=["SUBIR", "BAJAR"],
            width=150,
            font=ctk.CTkFont(size=8),
            command=self.cambiar_sentido_home
        )
        self.combo_sentido_home.pack(side=ctk.LEFT, padx=2)
        self.combo_sentido_home.set("BAJAR")
        
        # Sentido Giro
        frame_giro = ctk.CTkFrame(frame_sentido)
        frame_giro.pack(fill=ctk.X, padx=3, pady=1)
        ctk.CTkLabel(frame_giro, text="GIRO:   ", font=ctk.CTkFont(size=8)).pack(side=ctk.LEFT, padx=2)
        
        self.combo_sentido_giro = ctk.CTkComboBox(
            frame_giro,
            values=["ADELANTE", "ATRÁS"],
            width=150,
            font=ctk.CTkFont(size=8),
            command=self.cambiar_sentido_giro
        )
        self.combo_sentido_giro.pack(side=ctk.LEFT, padx=2)
        self.combo_sentido_giro.set("ADELANTE")
        
        # --- HOME + STOP ---
        frame_home_stop = ctk.CTkFrame(frame_central)
        frame_home_stop.pack(fill=ctk.X, pady=1)
        
        frame_botones_hs = ctk.CTkFrame(frame_home_stop)
        frame_botones_hs.pack(fill=ctk.X, padx=3, pady=2)
        
        self.btn_home = ctk.CTkButton(
            frame_botones_hs, text="🏠 HOME", command=self.ir_a_home,
            height=30, fg_color="#f39c12", font=ctk.CTkFont(size=10, weight="bold")
        )
        self.btn_home.pack(side=ctk.LEFT, padx=2, fill=ctk.X, expand=True)
        
        self.btn_stop = ctk.CTkButton(
            frame_botones_hs, text="⏹ STOP", command=self.detener,
            height=30, fg_color="#e74c3c", font=ctk.CTkFont(size=10, weight="bold")
        )
        self.btn_stop.pack(side=ctk.LEFT, padx=2, fill=ctk.X, expand=True)
        
        self.lbl_status_home = ctk.CTkLabel(frame_home_stop, text="⚪ No posicionado", font=ctk.CTkFont(size=8))
        self.lbl_status_home.pack(anchor=ctk.W, padx=3)
        
        # --- LOG ---
        frame_log = ctk.CTkFrame(frame_central)
        frame_log.pack(fill=ctk.BOTH, expand=True, pady=1)
        
        ctk.CTkLabel(frame_log, text="📋 Log", font=ctk.CTkFont(size=10, weight="bold")).pack(anchor=ctk.W, padx=3)
        
        self.txt_log = ctk.CTkTextbox(frame_log, font=ctk.CTkFont(size=8), wrap="word")
        self.txt_log.pack(fill=ctk.BOTH, expand=True, padx=3, pady=2)
        
        self.txt_log.tag_config("OK", foreground="#2ecc71")
        self.txt_log.tag_config("ERROR", foreground="#e74c3c")
        self.txt_log.tag_config("INFO", foreground="#3498db")
        self.txt_log.tag_config("COMANDO", foreground="#9b59b6")
        self.txt_log.tag_config("WARNING", foreground="#f39c12")
        self.txt_log.tag_config("FOTO", foreground="#e67e22")
        self.txt_log.tag_config("HOME", foreground="#2ecc71")
        self.txt_log.tag_config("PROGRESO", foreground="#1abc9c")
        
        # ----- COLUMNA DERECHA (Captura de Imagen) -----
        frame_derecho = ctk.CTkFrame(panel_principal)
        frame_derecho.pack(side=ctk.RIGHT, fill=ctk.BOTH, expand=True)
        
        # Título
        frame_titulo_foto = ctk.CTkFrame(frame_derecho)
        frame_titulo_foto.pack(fill=ctk.X, pady=1)
        
        ctk.CTkLabel(frame_titulo_foto, text="📸 Imagen", font=ctk.CTkFont(size=10, weight="bold")).pack(side=ctk.LEFT, padx=3)
        
        # Label para la foto
        self.foto_label = ctk.CTkLabel(
            frame_derecho,
            text="📷 Esperando...",
            font=ctk.CTkFont(size=12)
        )
        self.foto_label.pack(fill=ctk.BOTH, expand=True, padx=3, pady=2)
        
        # Info de la foto
        self.lbl_ultima_foto = ctk.CTkLabel(
            frame_derecho,
            text="Última: ---",
            font=ctk.CTkFont(size=8),
            text_color="gray"
        )
        self.lbl_ultima_foto.pack(pady=(0, 2))
    
    # ==================== FUNCIONES DE SENTIDO ====================
    def cambiar_sentido_home(self, valor):
        if "SUBIR" in valor:
            self.sentido_home = 0
            self.enviar_comando("SET_HOME_DIR=0")
            self.log("🔄 HOME: SUBIR", "INFO")
        else:
            self.sentido_home = 1
            self.enviar_comando("SET_HOME_DIR=1")
            self.log("🔄 HOME: BAJAR", "INFO")
    
    def cambiar_sentido_giro(self, valor):
        if "ADELANTE" in valor:
            self.sentido_giro_actual = 0
            self.enviar_comando("DIRECCION=0")
            self.log("🔄 GIRO: ADELANTE", "INFO")
        else:
            self.sentido_giro_actual = 1
            self.enviar_comando("DIRECCION=1")
            self.log("🔄 GIRO: ATRÁS", "INFO")
    
    # ==================== FUNCIONES DE LUZ ====================
    def toggle_luz(self):
        if not self.conectado:
            self.log("❌ No conectado", "ERROR")
            return
        
        if self.luces_encendidas:
            self.enviar_comando("LUZ_OFF")
            self.luces_encendidas = False
            self.btn_luz.configure(text="💡 LUZ", fg_color="#f39c12")
            self.log("💡 Luces APAGADAS", "INFO")
        else:
            self.enviar_comando("LUZ_ON")
            self.luces_encendidas = True
            self.btn_luz.configure(text="💡 LUZ ON", fg_color="#e67e22")
            self.log("💡 Luces ENCENDIDAS", "INFO")
    
    # ==================== FUNCIONES DE CÁMARA ====================
    def capturar_foto_alta_resolucion(self, ruta):
        try:
            subprocess.run([
                'rpicam-still',
                '-o', ruta,
                '--width', '4056',
                '--height', '3040',
                '--quality', '100',
                '--nopreview',
                '--timeout', '1000'
            ], check=True, capture_output=True, timeout=5)
            return True
        except:
            return False
    
    def mostrar_foto_en_interfaz(self, ruta_foto):
        try:
            img = Image.open(ruta_foto)
            ancho = self.foto_label.winfo_width()
            alto = self.foto_label.winfo_height()
            if ancho < 50:
                ancho = 250
            if alto < 50:
                alto = 200
            
            ratio = min(ancho / img.width, alto / img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img_resized = img.resize(new_size, Image.Resampling.LANCZOS)
            imgtk = ImageTk.PhotoImage(img_resized)
            self.foto_label.configure(image=imgtk, text="")
            self.foto_label.image = imgtk
            self.ultima_foto_path = ruta_foto
            return True
        except:
            return False
    
    # ==================== FUNCIÓN HOME ====================
    def ir_a_home(self):
        if not self.conectado:
            self.log("❌ No conectado", "ERROR")
            return
        if not self.motor_habilitado:
            self.log("⚠️ Motor deshabilitado", "WARNING")
            return
        if self.moviendo:
            self.log("⚠️ Movimiento en curso", "WARNING")
            return
        
        if self.en_home:
            self.log("✅ Ya está en HOME", "HOME")
            self.actualizar_estado_visual("✅ En HOME")
            return
        
        self.log(f"🏠 Buscando HOME... (Sentido: {'BAJAR' if self.sentido_home == 1 else 'SUBIR'})", "HOME")
        self.btn_home.configure(state="disabled", text="⏳ BUSCANDO...")
        self.actualizar_estado_visual("🏠 Buscando HOME...")
        self.lbl_status_home.configure(text="⏳ Buscando...", text_color="#f39c12")
        
        self.esperando_home = True
        self.home_exitoso = False
        self.home_timeout = False
        self.en_home = False
        self.buscando_home = True
        
        self.enviar_comando("HOME")
        
        def esperar_home():
            timeout = 30
            inicio = time.time()
            
            while time.time() - inicio < timeout:
                if self.en_home and self.home_exitoso:
                    self.log("✅ HOME alcanzado correctamente", "HOME")
                    break
                
                if self.home_timeout:
                    self.log("❌ HOME falló - Verificar sentido", "ERROR")
                    break
                
                time.sleep(1)
                self.consultar_estado()
            
            self.esperando_home = False
            self.buscando_home = False
            
            self.root.after(0, lambda: self.btn_home.configure(state="normal", text="🏠 HOME"))
            
            if not self.home_exitoso:
                self.root.after(0, lambda: self.lbl_status_home.configure(
                    text="❌ Falló - Verificar sentido", 
                    text_color="#e74c3c"
                ))
                self.root.after(0, lambda: self.lbl_home.configure(
                    text="Home: ❌", 
                    text_color="#e74c3c"
                ))
                self.root.after(0, lambda: self.actualizar_estado_visual("❌ HOME falló"))
            else:
                self.root.after(0, lambda: self.lbl_status_home.configure(
                    text="✅ Posicionado", 
                    text_color="#2ecc71"
                ))
                self.root.after(0, lambda: self.lbl_home.configure(
                    text="Home: 🏠", 
                    text_color="#2ecc71"
                ))
                self.root.after(0, lambda: self.actualizar_estado_visual("✅ En HOME"))
        
        threading.Thread(target=esperar_home, daemon=True).start()
    
    # ==================== FUNCIÓN DE INSPECCIÓN ====================
    def iniciar_inspeccion(self):
        if not self.conectado:
            self.log("❌ No conectado", "ERROR")
            return
        if not self.motor_habilitado:
            self.log("⚠️ Motor deshabilitado", "WARNING")
            return
        if self.moviendo:
            self.log("⚠️ Movimiento en curso", "WARNING")
            return
        if not self.camara_disponible:
            self.log("❌ Cámara no disponible", "ERROR")
            return
        if self.inspeccion_activa:
            self.log("⚠️ Inspección en curso", "WARNING")
            return
        
        try:
            tamano_soldadura = float(self.entry_soldadura.get())
            
            if tamano_soldadura <= 0:
                raise ValueError("El tamaño debe ser positivo")
            
            # Validar rango 4-16
            if tamano_soldadura < 4:
                self.log(f"⚠️ Soldadura {tamano_soldadura}cm es menor a 4cm, ajustando a 4cm", "WARNING")
                self.entry_soldadura.delete(0, ctk.END)
                self.entry_soldadura.insert(0, "4")
                tamano_soldadura = 4
            elif tamano_soldadura > 16:
                self.log(f"⚠️ Soldadura {tamano_soldadura}cm es mayor a 16cm, ajustando a 16cm", "WARNING")
                self.entry_soldadura.delete(0, ctk.END)
                self.entry_soldadura.insert(0, "16")
                tamano_soldadura = 16
            
            self.pasos_por_bloque = []
            self.pasos_por_bloque.append(2000)
            
            distancia_restante = tamano_soldadura - 4
            
            if distancia_restante > 0:
                fotos_adicionales = math.ceil(distancia_restante / 4)
                for _ in range(fotos_adicionales):
                    self.pasos_por_bloque.append(4000)
            
            self.total_fotos = len(self.pasos_por_bloque)
            self.fotos_tomadas = 0
            self.detener_inspeccion = False
            self.pasos_totales_movimiento = sum(self.pasos_por_bloque)
            self.bloque_actual = 0
            
            self.log("=" * 40, "INFO")
            self.log(f"📊 Soldadura: {tamano_soldadura}cm", "INFO")
            self.log(f"📸 {self.total_fotos} fotos", "FOTO")
            
            pos_actual = 0
            for i, pasos in enumerate(self.pasos_por_bloque):
                pos_actual += pasos / 1000
                self.log(f"   Foto {i+1}: {pasos} pasos → {pos_actual:.1f}cm", "FOTO")
            
            self.log(f"📏 Total: {self.pasos_totales_movimiento} pasos", "INFO")
            self.log("=" * 40, "INFO")
            
            self.progressbar.set(0)
            self.lbl_progreso.configure(text="0%")
            self.lbl_fotos.configure(text=f"📸 0/{self.total_fotos}")
            self.actualizar_estado_visual("🔄 Iniciando...")
            
            self.btn_inspeccion.configure(state="disabled", text="⏳ Inspeccionando...")
            self.btn_home.configure(state="disabled")
            self.btn_enable.configure(state="disabled")
            self.btn_disable.configure(state="disabled")
            self.btn_stop.configure(state="disabled")
            self.inspeccion_activa = True
            
            self.enviar_comando("INSPECCION_START")
            time.sleep(0.2)
            
            threading.Thread(target=self.proceso_inspeccion, daemon=True).start()
            
        except Exception as e:
            self.log(f"❌ Error: {e}", "ERROR")

    def proceso_inspeccion(self):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_carpeta = self.entry_carpeta.get().strip() or "inspeccion"
            carpeta_completa = os.path.join(self.carpeta_fotos, f"{nombre_carpeta}_{timestamp}")
            os.makedirs(carpeta_completa, exist_ok=True)
            
            self.log(f"📁 Carpeta: {nombre_carpeta}_{timestamp}", "INFO")
            
            direccion = self.sentido_giro_actual
            self.enviar_comando(f"DIRECCION={direccion}")
            time.sleep(0.2)
            
            pasos_acumulados = 0
            
            for i, pasos_bloque in enumerate(self.pasos_por_bloque):
                if self.detener_inspeccion:
                    self.log("⏹ Inspección detenida", "WARNING")
                    break
                
                self.bloque_actual = i + 1
                
                self.log(f"📷 Moviendo a foto {i+1}/{self.total_fotos}... ({pasos_bloque} pasos)", "PROGRESO")
                self.actualizar_estado_visual(f"📸 Moviendo a foto {i+1}...")
                
                self.enviar_comando(f"MOVER={pasos_bloque}")
                
                if not self.esperar_fin_movimiento(timeout=30, mostrar_log=False):
                    self.log(f"⚠️ Timeout en bloque {i+1}", "WARNING")
                    break
                
                pasos_acumulados += pasos_bloque
                progreso_actual = (pasos_acumulados / self.pasos_totales_movimiento) * 100
                
                self.root.after(0, lambda p=progreso_actual: self.progressbar.set(p/100))
                self.root.after(0, lambda p=progreso_actual: self.lbl_progreso.configure(text=f"{p:.0f}%"))
                
                nombre = f"foto_{i+1:02d}.jpg"
                ruta_completa = os.path.join(carpeta_completa, nombre)
                
                self.log(f"📸 Tomando foto {i+1}/{self.total_fotos}", "FOTO")
                self.actualizar_estado_visual(f"📸 Tomando foto {i+1}...")
                
                if self.capturar_foto_alta_resolucion(ruta_completa):
                    self.fotos_tomadas = i + 1
                    self.log(f"✅ Foto {i+1} guardada", "FOTO")
                    self.root.after(0, self.mostrar_foto_en_interfaz, ruta_completa)
                    self.root.after(0, lambda n=nombre: self.lbl_ultima_foto.configure(text=f"Última: {n}"))
                else:
                    self.log(f"❌ Error capturando foto {i+1}", "ERROR")
                
                self.root.after(0, lambda f=i+1: self.lbl_fotos.configure(text=f"📸 {f}/{self.total_fotos}"))
                
                if i < self.total_fotos - 1:
                    time.sleep(0.2)
            
            if not self.detener_inspeccion:
                self.root.after(0, lambda: self.progressbar.set(1.0))
                self.root.after(0, lambda: self.lbl_progreso.configure(text="100%"))
                
                if self.check_volver.get() == 1:
                    self.log(f"🔄 Volviendo al inicio...", "INFO")
                    self.actualizar_estado_visual("🔄 Regresando...")
                    self.root.after(0, lambda: self.progressbar.set(0))
                    self.root.after(0, lambda: self.lbl_progreso.configure(text="Regresando..."))
                    
                    direccion_contraria = 1 - self.sentido_giro_actual
                    self.enviar_comando(f"DIRECCION={direccion_contraria}")
                    time.sleep(0.3)
                    
                    self.enviar_comando(f"MOVER={self.pasos_totales_movimiento}")
                    
                    if self.esperar_fin_movimiento(timeout=60, mostrar_log=False):
                        self.log("✅ Regreso completado", "OK")
                        self.root.after(0, lambda: self.progressbar.set(1.0))
                        self.root.after(0, lambda: self.lbl_progreso.configure(text="Regreso OK"))
                        self.actualizar_estado_visual("✅ Regreso OK")
                    else:
                        self.log("⚠️ Timeout en regreso", "WARNING")
                        self.actualizar_estado_visual("⚠️ Timeout regreso")
                
                self.log(f"🎉 Inspección completada: {self.total_fotos} fotos", "OK")
                self.actualizar_estado_visual("🎉 Completada")
            else:
                self.log("⏹ Inspección detenida", "WARNING")
                self.actualizar_estado_visual("⏹ Detenida")
            
        except Exception as e:
            self.log(f"❌ Error: {e}", "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
            self.actualizar_estado_visual("❌ Error")
        
        finally:
            self.enviar_comando("INSPECCION_END")
            time.sleep(0.2)
            
            self.inspeccion_activa = False
            self.root.after(0, lambda: self.btn_inspeccion.configure(state="normal", text="📷 INSPECCIONAR"))
            self.root.after(0, lambda: self.btn_home.configure(state="normal"))
            self.root.after(0, lambda: self.btn_enable.configure(state="normal"))
            self.root.after(0, lambda: self.btn_disable.configure(state="normal"))
            self.root.after(0, lambda: self.btn_stop.configure(state="normal"))
            self.consultar_estado()
    
    def actualizar_estado_visual(self, mensaje):
        self.root.after(0, lambda: self.lbl_estado_actual.configure(text=f"{mensaje}"))
    
    def esperar_fin_movimiento(self, timeout=30, mostrar_log=True):
        self.done_recibido = False
        inicio = time.time()
        ultimo_estado_time = 0
        
        while time.time() - inicio < timeout:
            if self.detener_inspeccion:
                self.log("⏹ Deteniendo...", "WARNING")
                self.enviar_comando("STOP")
                return False
            
            if self.done_recibido:
                self.done_recibido = False
                return True
            
            ahora = time.time()
            if ahora - ultimo_estado_time >= 1.0:
                if self.conectado and self.ser and self.ser.is_open:
                    try:
                        self.ser.write(b"ESTADO\n")
                    except:
                        pass
                ultimo_estado_time = ahora
            
            time.sleep(0.05)
        
        return False
    
    # ==================== FUNCIONES DE COMUNICACIÓN ====================
    def leer_serial(self):
        while self.lectura_activa and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    linea = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if linea:
                        self.procesar_respuesta(linea)
            except:
                break
            time.sleep(0.01)
    
    def procesar_respuesta(self, linea):
        if linea.startswith("HOME_OK:"):
            mensaje = linea[8:]
            self.log("✅ " + mensaje, "HOME")
            self.en_home = True
            self.moviendo = False
            self.pasos_restantes = 0
            self.done_recibido = False
            self.home_exitoso = True
            self.home_timeout = False
            self.buscando_home = False
            self.esperando_home = False
            
            self.enviar_comando("STOP")
            
            self.actualizar_estado_visual("✅ En HOME (Sensor Inferior)")
            self.lbl_status_home.configure(text="✅ Posicionado", text_color="#2ecc71")
            self.lbl_home.configure(text="Home: 🏠", text_color="#2ecc71")
            return
        
        if linea.startswith("HOME_ERROR:"):
            mensaje = linea[11:]
            self.log("❌ HOME falló: " + mensaje, "ERROR")
            
            self.moviendo = False
            self.pasos_restantes = 0
            self.done_recibido = False
            self.home_timeout = True
            self.home_exitoso = False
            self.en_home = False
            self.buscando_home = False
            self.esperando_home = False
            
            self.enviar_comando("STOP")
            
            self.actualizar_estado_visual("❌ HOME falló")
            self.lbl_status_home.configure(text="❌ Falló - Verificar sentido", text_color="#e74c3c")
            self.lbl_home.configure(text="Home: ❌", text_color="#e74c3c")
            
            self.root.after(0, lambda: self.btn_home.configure(state="normal", text="🏠 HOME"))
            
            sentido_actual = "BAJAR" if self.sentido_home == 1 else "SUBIR"
            sugerencia = "SUBIR" if self.sentido_home == 1 else "BAJAR"
            self.log(f"💡 Sugerencia: Cambiar HOME a {sugerencia}", "WARNING")
            return
        
        if "Sensor inferior detectado" in linea or "LIMIT_HOME" in linea:
            self.log("🏠 HOME detectado (Sensor Inferior)", "HOME")
            self.en_home = True
            self.moviendo = False
            self.pasos_restantes = 0
            self.done_recibido = False
            self.buscando_home = False
            self.home_exitoso = True
            self.actualizar_estado_visual("🏠 HOME detectado")
            self.lbl_status_home.configure(text="✅ Posicionado", text_color="#2ecc71")
            self.lbl_home.configure(text="Home: 🏠", text_color="#2ecc71")
            return
        
        if "Sensor superior detectado" in linea or "LIMIT_SUPERIOR" in linea:
            self.log("⚠️ Límite superior detectado", "WARNING")
            self.moviendo = False
            self.pasos_restantes = 0
            self.done_recibido = False
            self.actualizar_estado_visual("⚠️ Límite superior")
            return
        
        if linea.startswith("OK:"):
            mensaje = linea[3:]
            if not mensaje.startswith("Dirección") and not mensaje.startswith("Sentido"):
                self.log("✓ " + mensaje, "OK")
        elif linea.startswith("ERROR:"):
            self.log("✗ " + linea[6:], "ERROR")
        elif linea.startswith("DONE"):
            self.moviendo = False
            self.pasos_restantes = 0
            self.movimiento_completado = True
            self.done_recibido = True
            if not self.inspeccion_activa:
                self.log("✅ Movimiento completado", "OK")
        elif linea.startswith("STOPPED:"):
            self.log("⏹ " + linea[8:], "WARNING")
            self.moviendo = False
            self.pasos_restantes = 0
            self.done_recibido = False
        elif linea.startswith("ESTADO:"):
            self.actualizar_estado(linea[7:])
        elif linea.startswith("LUCES:"):
            pass
        elif linea.startswith("HOME_TIMEOUT:"):
            self.log("⏱️ " + linea[13:], "WARNING")
            self.home_timeout = True
            self.buscando_home = False
            self.moviendo = False
        else:
            if linea and not linea.startswith(">>>"):
                pass
    
    def actualizar_estado(self, datos):
        try:
            partes = datos.split(',')
            estado = {}
            for p in partes:
                if '=' in p:
                    clave, valor = p.split('=', 1)
                    estado[clave] = valor
            
            if 'Motor' in estado:
                if estado['Motor'] == "HABILITADO":
                    self.lbl_estado_motor.configure(text="Motor: 🟢", text_color="#2ecc71")
                    self.motor_habilitado = True
                else:
                    self.lbl_estado_motor.configure(text="Motor: 🔴", text_color="#e74c3c")
                    self.motor_habilitado = False
            
            if 'Moviendo' in estado:
                if estado['Moviendo'] == "SI":
                    self.lbl_moviendo.configure(text="Mov: 🟢", text_color="#2ecc71")
                    self.moviendo = True
                else:
                    self.lbl_moviendo.configure(text="Mov: ⚪", text_color="gray")
                    self.moviendo = False
            
            if 'SensorInferior' in estado:
                if estado['SensorInferior'] == "ACTIVO":
                    self.en_home = True
                    self.lbl_home.configure(text="Home: 🏠", text_color="#2ecc71")
                    self.lbl_status_home.configure(text="✅ Posicionado", text_color="#2ecc71")
                else:
                    self.en_home = False
                    self.lbl_home.configure(text="Home: ⚪", text_color="gray")
                    if not self.inspeccion_activa and not self.moviendo and not self.esperando_home:
                        self.lbl_status_home.configure(text="⚪ No posicionado", text_color="gray")
            
            if 'SensorSuperior' in estado:
                if estado['SensorSuperior'] == "ACTIVO":
                    self.lbl_home.configure(text="Home: ⬆️ Límite", text_color="#f39c12")
            
            if 'PasosRestantes' in estado:
                self.pasos_restantes = int(estado['PasosRestantes'])
                if self.pasos_restantes < 900000:
                    self.lbl_pasos.configure(text=f"Pasos: {self.pasos_restantes}")
                else:
                    self.lbl_pasos.configure(text=f"Pasos: buscando...")
        except:
            pass
    
    def enviar_comando(self, comando):
        if not self.conectado or not self.ser or not self.ser.is_open:
            return False
        
        try:
            self.ser.write((comando + "\n").encode())
            if comando != "ESTADO":
                self.log(f">>> {comando}", "COMANDO")
            return True
        except:
            return False
    
    def detener(self):
        self.detener_inspeccion = True
        self.moviendo = False
        self.pasos_restantes = 0
        self.buscando_home = False
        self.esperando_home = False
        self.home_timeout = True
        
        self.enviar_comando("STOP")
        time.sleep(0.2)
        self.consultar_estado()
        self.actualizar_estado_visual("⏹ Detenido")
        
        self.root.after(0, lambda: self.btn_home.configure(state="normal", text="🏠 HOME"))
        self.root.after(0, lambda: self.btn_inspeccion.configure(state="normal", text="📷 INSPECCIONAR"))
        self.root.after(0, lambda: self.btn_enable.configure(state="normal"))
        self.root.after(0, lambda: self.btn_disable.configure(state="normal"))
        self.root.after(0, lambda: self.btn_stop.configure(state="normal"))
    
    def habilitar(self):
        self.enviar_comando("ENABLE")
        time.sleep(0.2)
        self.consultar_estado()
    
    def deshabilitar(self):
        self.enviar_comando("DISABLE")
        time.sleep(0.2)
        self.consultar_estado()
    
    def consultar_estado(self):
        if self.conectado and self.ser and self.ser.is_open:
            try:
                self.ser.write(b"ESTADO\n")
            except:
                pass
    
    def log(self, mensaje, tipo="INFO"):
        timestamp = time.strftime("%H:%M:%S")
        self.txt_log.insert("end", f"[{timestamp}] ", "INFO")
        self.txt_log.insert("end", mensaje + "\n", tipo)
        self.txt_log.see("end")
        
        if int(self.txt_log.index('end-1c').split('.')[0]) > 100:
            self.txt_log.delete("1.0", "30.0")

# ==================== MAIN ====================
if __name__ == "__main__":
    root = ctk.CTk()
    app = ControlMotor(root)
    root.mainloop()