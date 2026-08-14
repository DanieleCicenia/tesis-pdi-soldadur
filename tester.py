#!/usr/bin/env python3
"""
SISTEMA DE CONTROL - Motor + Cámara 720p
Con video completo manteniendo relación de aspecto
"""

import serial
import customtkinter as ctk
import threading
import time
import os
from datetime import datetime
import cv2
import subprocess
import numpy as np
import shutil
from PIL import Image, ImageTk

# Configurar tema
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ControlMotor:
    def __init__(self, root):
        self.root = root
        self.root.title("Control Motor")
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
        self.progreso = 0
        self.luces_encendidas = False
        
        # Variables de cámara
        self.camara_activa = False
        self.frame = None
        self.fps = 0
        self.frame_count = 0
        self.last_time = time.time()
        self.process = None
        
        # Variables para teclado numérico
        self.teclado_visible = False
        self.teclado_window = None
        
        # Variables para tamaño de video
        self.video_display_width = 0
        self.video_display_height = 0
        
        # Crear interfaz
        self.crear_interfaz()
        
        # Conectar automáticamente a ttyUSB0
        self.conectar_auto()
        
        # Inicializar cámara
        self.inicializar_camara()
    
    def conectar_auto(self):
        """Conecta automáticamente a ttyUSB0"""
        try:
            puerto = "/dev/ttyUSB0"
            self.ser = serial.Serial(puerto, 115200, timeout=1)
            time.sleep(1)
            self.conectado = True
            self.lectura_activa = True
            
            self.lbl_estado.configure(text="✅")
            
            self.hilo_lectura = threading.Thread(target=self.leer_serial, daemon=True)
            self.hilo_lectura.start()
            
            self.log("Conectado", "OK")
            self.consultar_estado()
            
        except Exception as e:
            self.log("Error USB", "ERROR")
            self.lbl_estado.configure(text="❌")
    
    def inicializar_camara(self):
        """Inicializa la cámara con rpicam-vid a 720p"""
        try:
            comando = self.encontrar_comando()
            if comando is None:
                self.log("Camara no disp", "ERROR")
                return
            
            self.camara_activa = True
            
            self.hilo_video = threading.Thread(target=self.capturar_video_720p, daemon=True)
            self.hilo_video.start()
            
            self.log("Camara iniciada", "OK")
            
        except Exception as e:
            self.log("Error camara", "ERROR")
    
    def encontrar_comando(self):
        comandos = ['rpicam-vid', 'libcamera-vid']
        for cmd in comandos:
            if shutil.which(cmd) is not None:
                return cmd
        return None
    
    def capturar_video_720p(self):
        comando = self.encontrar_comando()
        if comando is None:
            self.camara_activa = False
            return
        
        # Resolución de la cámara
        cam_width = 1280
        cam_height = 720
        aspect_ratio = cam_width / cam_height  # 16:9 = 1.777...
        
        cmd = [
            comando,
            '-t', '0',
            '--width', str(cam_width),
            '--height', str(cam_height),
            '--framerate', '15',
            '--codec', 'yuv420',
            '--output', '-',
            '--nopreview'
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
                stdin=subprocess.DEVNULL
            )
            
            frame_size = cam_width * cam_height * 3 // 2
            buffer = bytearray()
            
            while self.camara_activa and self.process:
                try:
                    data = self.process.stdout.read(4096)
                    if not data:
                        break
                    
                    buffer.extend(data)
                    
                    while len(buffer) >= frame_size:
                        frame_data = buffer[:frame_size]
                        buffer = buffer[frame_size:]
                        
                        try:
                            yuv = np.frombuffer(frame_data, dtype=np.uint8)
                            yuv = yuv.reshape((cam_height * 3 // 2, cam_width))
                            frame_bgr = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)
                            
                            self.frame = frame_bgr.copy()
                            
                            # Obtener el tamaño del label de video
                            label_width = self.video_label.winfo_width()
                            label_height = self.video_label.winfo_height()
                            
                            # Si no se ha calculado aún o es muy pequeño, usar valores por defecto
                            if label_width < 50:
                                label_width = 400
                            if label_height < 50:
                                label_height = 300
                            
                            # Calcular el tamaño para mostrar el video COMPLETO manteniendo la relación de aspecto
                            # Mostrar el video COMPLETO, no recortado
                            display_width = label_width
                            display_height = int(display_width / aspect_ratio)
                            
                            if display_height > label_height:
                                display_height = label_height
                                display_width = int(display_height * aspect_ratio)
                            
                            # Guardar las dimensiones para referencia
                            self.video_display_width = display_width
                            self.video_display_height = display_height
                            
                            # Redimensionar manteniendo la relación de aspecto
                            frame_display = cv2.resize(
                                frame_bgr, 
                                (display_width, display_height),
                                interpolation=cv2.INTER_LINEAR
                            )
                            
                            img = Image.fromarray(cv2.cvtColor(frame_display, cv2.COLOR_BGR2RGB))
                            imgtk = ImageTk.PhotoImage(image=img)
                            
                            self.root.after(0, self.actualizar_video, imgtk)
                            
                            self.frame_count += 1
                            current_time = time.time()
                            if current_time - self.last_time >= 1.0:
                                self.fps = self.frame_count
                                self.frame_count = 0
                                self.last_time = current_time
                                self.root.after(0, self.actualizar_fps)
                            
                        except Exception as e:
                            pass
                            
                except:
                    if self.camara_activa:
                        self.log("Error captura", "WARNING")
                    break
            
            if self.process:
                self.process.terminate()
                self.process = None
                
        except:
            if self.camara_activa:
                self.log("Error camara", "ERROR")
                self.camara_activa = False
    
    def actualizar_video(self, imgtk):
        try:
            self.video_label.configure(image=imgtk)
            self.video_label.image = imgtk
        except:
            pass
    
    def actualizar_fps(self):
        self.lbl_fps.configure(text=f"{self.fps}")
    
    def toggle_camara(self):
        if self.camara_activa:
            self.camara_activa = False
            self.btn_camara.configure(text="▶", fg_color="#2ecc71")
            self.lbl_estado_cam.configure(text="🔴")
            self.video_label.configure(image=None)
            self.video_label.image = None
            self.log("Camara detenida", "INFO")
            
            if self.process:
                self.process.terminate()
                self.process = None
        else:
            self.camara_activa = True
            self.btn_camara.configure(text="⏹", fg_color="#e74c3c")
            self.lbl_estado_cam.configure(text="🟢")
            self.log("Iniciando camara", "INFO")
            self.inicializar_camara()
    
    def toggle_luz(self):
        if not self.conectado:
            self.log("No conectado", "ERROR")
            return
        self.enviar_comando("LUZ_TOGGLE")
        self.root.after(200, self.consultar_estado)
    
    # ==================== TECLADO NUMÉRICO ====================
    def abrir_teclado(self, event=None):
        """Abre un teclado numérico emergente"""
        if self.teclado_visible:
            return
        
        self.teclado_visible = True
        
        # Crear ventana emergente
        self.teclado_window = ctk.CTkToplevel(self.root)
        self.teclado_window.title("Teclado Numérico")
        self.teclado_window.geometry("300x350")
        self.teclado_window.resizable(False, False)
        self.teclado_window.attributes('-topmost', True)
        
        # Frame principal
        frame = ctk.CTkFrame(self.teclado_window)
        frame.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)
        
        # Display del número
        self.display_num = ctk.CTkEntry(
            frame,
            font=ctk.CTkFont(size=24, weight="bold"),
            justify="center",
            height=50
        )
        self.display_num.pack(fill=ctk.X, padx=5, pady=5)
        self.display_num.insert(0, self.entry_pasos.get())
        
        # Frame para botones
        btn_frame = ctk.CTkFrame(frame)
        btn_frame.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)
        
        # Botones numéricos
        numeros = [
            ['7', '8', '9'],
            ['4', '5', '6'],
            ['1', '2', '3'],
            ['0', '⌫', '✕']
        ]
        
        for i, fila in enumerate(numeros):
            for j, valor in enumerate(fila):
                if valor == '⌫':
                    btn = ctk.CTkButton(
                        btn_frame,
                        text=valor,
                        font=ctk.CTkFont(size=20, weight="bold"),
                        command=self.borrar_digito,
                        fg_color="#e67e22",
                        hover_color="#d35400"
                    )
                elif valor == '✕':
                    btn = ctk.CTkButton(
                        btn_frame,
                        text=valor,
                        font=ctk.CTkFont(size=20, weight="bold"),
                        command=self.cerrar_teclado,
                        fg_color="#e74c3c",
                        hover_color="#c0392b"
                    )
                else:
                    btn = ctk.CTkButton(
                        btn_frame,
                        text=valor,
                        font=ctk.CTkFont(size=20, weight="bold"),
                        command=lambda v=valor: self.agregar_digito(v)
                    )
                
                btn.grid(row=i, column=j, padx=3, pady=3, sticky="nsew")
                btn_frame.grid_rowconfigure(i, weight=1)
                btn_frame.grid_columnconfigure(j, weight=1)
        
        # Botón OK
        btn_ok = ctk.CTkButton(
            frame,
            text="OK",
            font=ctk.CTkFont(size=18, weight="bold"),
            command=self.confirmar_numero,
            fg_color="#2ecc71",
            hover_color="#27ae60",
            height=40
        )
        btn_ok.pack(fill=ctk.X, padx=5, pady=5)
        
        # Configurar cierre de ventana
        self.teclado_window.protocol("WM_DELETE_WINDOW", self.cerrar_teclado)
    
    def agregar_digito(self, digito):
        """Agrega un dígito al display"""
        actual = self.display_num.get()
        if len(actual) < 10:  # Limitar a 10 dígitos
            self.display_num.delete(0, ctk.END)
            self.display_num.insert(0, actual + digito)
    
    def borrar_digito(self):
        """Borra el último dígito"""
        actual = self.display_num.get()
        if len(actual) > 0:
            self.display_num.delete(0, ctk.END)
            self.display_num.insert(0, actual[:-1])
    
    def confirmar_numero(self):
        """Confirma el número y lo pasa al entry principal"""
        valor = self.display_num.get()
        if valor and valor.isdigit():
            self.entry_pasos.delete(0, ctk.END)
            self.entry_pasos.insert(0, valor)
        self.cerrar_teclado()
    
    def cerrar_teclado(self):
        """Cierra el teclado"""
        self.teclado_visible = False
        if self.teclado_window:
            self.teclado_window.destroy()
            self.teclado_window = None

    def crear_interfaz(self):
        # ========== VARIABLES DE TAMAÑO (AJUSTA AQUÍ) ==========
        # Tamaños de columnas
        self.col_control_width = 250   # Ancho columna controles
        self.col_log_width = 300       # Ancho columna log
        # El resto del espacio es para la cámara
        
        # Tamaños de fuentes
        self.font_title = 10           # Tamaño títulos
        self.font_normal = 10          # Tamaño texto normal
        self.font_small = 10           # Tamaño texto pequeño
        self.font_button = 10          # Tamaño botones
        
        # Alturas de frames
        self.row_height = 40          # Altura filas normales
        self.row_small = 40           # Altura filas pequeñas
        self.row_button = 44          # Altura fila botones
        self.row_status = 60          # Altura estado
        # =======================================================
        
        # Frame principal
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill=ctk.BOTH, expand=True, padx=2, pady=4)
        
        # ==================== COLUMNA 1: CONTROLES ====================
        frame_controles = ctk.CTkFrame(self.main_frame, width=self.col_control_width)
        frame_controles.pack(side=ctk.LEFT, fill=ctk.Y, padx=(0, 1))
        frame_controles.pack_propagate(False)
        
        # Título
        ctk.CTkLabel(
            frame_controles,
            text="CONTROL",
            font=ctk.CTkFont(size=self.font_title, weight="bold")
        ).pack(pady=(1, 2))
        
        # USB
        frame_usb = ctk.CTkFrame(frame_controles, height=self.row_height)
        frame_usb.pack(fill=ctk.X, pady=1)
        frame_usb.pack_propagate(False)
        
        ctk.CTkLabel(frame_usb, text="USB:", font=ctk.CTkFont(size=self.font_normal)).place(x=2, y=4)
        self.lbl_estado = ctk.CTkLabel(frame_usb, text="⚪", font=ctk.CTkFont(size=self.font_normal))
        self.lbl_estado.place(x=30, y=3)
        ctk.CTkLabel(frame_usb, text="ttyUSB0", font=ctk.CTkFont(size=self.font_small), text_color="gray").place(x=48, y=5)
        
        # Dirección
        frame_dir = ctk.CTkFrame(frame_controles, height=self.row_height)
        frame_dir.pack(fill=ctk.X, pady=4)
        frame_dir.pack_propagate(False)
        
        ctk.CTkLabel(frame_dir, text="Dir:", font=ctk.CTkFont(size=self.font_normal)).place(x=2, y=4)
        
        self.combo_direccion = ctk.CTkComboBox(
            frame_dir,
            values=["▶ adelante", "◀ atraz"],
            state="readonly",
            width=150,
            height=self.row_small-2,
            font=ctk.CTkFont(size=self.font_normal)
        )
        self.combo_direccion.place(x=38, y=1)
        self.combo_direccion.set("▶ adelante")
        
        # Pasos - Modificado para abrir teclado al hacer click
        frame_pasos = ctk.CTkFrame(frame_controles, height=self.row_height)
        frame_pasos.pack(fill=ctk.X, pady=4)
        frame_pasos.pack_propagate(False)
        
        ctk.CTkLabel(frame_pasos, text="Pasos:", font=ctk.CTkFont(size=self.font_normal)).place(x=2, y=4)
        
        self.entry_pasos = ctk.CTkEntry(
            frame_pasos,
            width=150,
            height=self.row_small-2,
            font=ctk.CTkFont(size=self.font_normal),
            justify="center"
        )
        self.entry_pasos.place(x=38, y=1)
        self.entry_pasos.insert(0, "500")
        # Vincular evento de click para abrir teclado
        self.entry_pasos.bind("<Button-1>", self.abrir_teclado)
        
        # Botones rápidos
        frame_rapidos = ctk.CTkFrame(frame_controles, height=self.row_small)
        frame_rapidos.pack(fill=ctk.X, pady=4)
        frame_rapidos.pack_propagate(False)
        
        for i, valor in enumerate([100, 500, 1000, 2000, 5000]):
            btn = ctk.CTkButton(
                frame_rapidos,
                text=str(valor),
                command=lambda v=valor: self.set_pasos(v),
                width=38,
                height=self.row_small-2,
                font=ctk.CTkFont(size=self.font_small)
            )
            btn.place(x=i*50, y=1)
        
        # Botones principales
        frame_botones = ctk.CTkFrame(frame_controles, height=self.row_button)
        frame_botones.pack(fill=ctk.X, pady=4)
        frame_botones.pack_propagate(False)
        
        self.btn_mover = ctk.CTkButton(
            frame_botones,
            text="▶ Mover",
            command=self.mover,
            width=55,
            height=self.row_button-4,
            fg_color="#3498db",
            font=ctk.CTkFont(size=self.font_button+2, weight="bold")
        )
        self.btn_mover.place(x=2, y=2)
        
        self.btn_stop = ctk.CTkButton(
            frame_botones,
            text="⏹Stop",
            command=self.detener,
            width=55,
            height=self.row_button-4,
            fg_color="#e74c3c",
            font=ctk.CTkFont(size=self.font_button+2, weight="bold")
        )
        self.btn_stop.place(x=65, y=2)
        
        self.btn_enable = ctk.CTkButton(
            frame_botones,
            text="🔓Enable",
            command=self.habilitar,
            width=55,
            height=self.row_button-4,
            fg_color="#2ecc71",
            font=ctk.CTkFont(size=self.font_button, weight="bold")
        )
        self.btn_enable.place(x=125, y=2)
        
        self.btn_disable = ctk.CTkButton(
            frame_botones,
            text="🔒Disable",
            command=self.deshabilitar,
            width=55,
            height=self.row_button-4,
            fg_color="#95a5a6",
            font=ctk.CTkFont(size=self.font_button, weight="bold")
        )
        self.btn_disable.place(x=185, y=2)
        
        # Luz
        frame_luz = ctk.CTkFrame(frame_controles, height=self.row_height)
        frame_luz.pack(fill=ctk.X, pady=4)
        frame_luz.pack_propagate(False)
        
        self.lbl_luces = ctk.CTkLabel(frame_luz, text="💡OFF", font=ctk.CTkFont(size=self.font_normal), text_color="gray")
        self.lbl_luces.place(x=2, y=4)
        
        self.btn_luz = ctk.CTkButton(
            frame_luz,
            text="LUZ",
            command=self.toggle_luz,
            width=60,
            height=self.row_small,
            fg_color="#f39c12",
            font=ctk.CTkFont(size=self.font_small+1, weight="bold")
        )
        self.btn_luz.place(x=65, y=1)
        
        # Estado
        frame_status = ctk.CTkFrame(frame_controles, height=self.row_status + 20)
        frame_status.pack(fill=ctk.X, pady=4)
        frame_status.pack_propagate(False)
        
        # Columna izquierda
        ctk.CTkLabel(frame_status, text="Motor:", font=ctk.CTkFont(size=self.font_small)).place(x=5, y=5)
        self.lbl_estado_motor = ctk.CTkLabel(frame_status, text="⚪", font=ctk.CTkFont(size=self.font_normal))
        self.lbl_estado_motor.place(x=45, y=4)
        
        ctk.CTkLabel(frame_status, text="Mov:", font=ctk.CTkFont(size=self.font_small)).place(x=5, y=22)
        self.lbl_moviendo = ctk.CTkLabel(frame_status, text="⚪", font=ctk.CTkFont(size=self.font_normal))
        self.lbl_moviendo.place(x=40, y=21)
        
        ctk.CTkLabel(frame_status, text="Pasos:", font=ctk.CTkFont(size=self.font_small)).place(x=5, y=39)
        self.lbl_pasos = ctk.CTkLabel(frame_status, text="0", font=ctk.CTkFont(size=self.font_normal))
        self.lbl_pasos.place(x=45, y=39)
        
        # Columna derecha
        ctk.CTkLabel(frame_status, text="Prog:", font=ctk.CTkFont(size=self.font_small)).place(x=100, y=2)
        self.lbl_progreso = ctk.CTkLabel(frame_status, text="0%", font=ctk.CTkFont(size=self.font_normal))
        self.lbl_progreso.place(x=130, y=2)
        
        self.progressbar = ctk.CTkProgressBar(frame_status, height=15, width=130)
        self.progressbar.place(x=100, y=25)
        self.progressbar.set(0)
        
        # ==================== COLUMNA 2: LOG ====================
        frame_log = ctk.CTkFrame(self.main_frame, width=self.col_log_width)
        frame_log.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=False, padx=(0, 1))
        frame_log.pack_propagate(False)
        
        ctk.CTkLabel(
            frame_log,
            text="LOG",
            font=ctk.CTkFont(size=self.font_title, weight="bold")
        ).pack(pady=(2, 2))
        
        self.txt_log = ctk.CTkTextbox(frame_log, font=ctk.CTkFont(size=self.font_normal), wrap="word")
        self.txt_log.pack(fill=ctk.BOTH, expand=True, padx=2, pady=4)
        
        self.txt_log.tag_config("OK", foreground="#2ecc71")
        self.txt_log.tag_config("ERROR", foreground="#e74c3c")
        self.txt_log.tag_config("INFO", foreground="#3498db")
        self.txt_log.tag_config("COMANDO", foreground="#9b59b6")
        self.txt_log.tag_config("WARNING", foreground="#f39c12")
        
        self.btn_limpiar = ctk.CTkButton(
            frame_log,
            text="🗑",
            command=self.limpiar_log,
            width=25,
            height=25,
            font=ctk.CTkFont(size=self.font_normal)
        )
        self.btn_limpiar.pack(anchor=ctk.E, padx=3, pady=4)

        # ==================== COLUMNA 3: CÁMARA ====================
        frame_camara = ctk.CTkFrame(self.main_frame)
        frame_camara.pack(side=ctk.RIGHT, fill=ctk.BOTH, expand=True)
        
        # Título cámara
        frame_titulo = ctk.CTkFrame(frame_camara, height=self.row_height+2)
        frame_titulo.pack(fill=ctk.X, pady=(0, 1))
        frame_titulo.pack_propagate(False)
        
        ctk.CTkLabel(
            frame_titulo,
            text="CAMARA 720p",
            font=ctk.CTkFont(size=self.font_title, weight="bold")
        ).place(x=3, y=4)
        
        self.lbl_estado_cam = ctk.CTkLabel(frame_titulo, text="🟢", font=ctk.CTkFont(size=self.font_normal+2))
        self.lbl_estado_cam.place(x=85, y=4)
        
        self.lbl_fps = ctk.CTkLabel(frame_titulo, text="0", font=ctk.CTkFont(size=self.font_normal), text_color="gray")
        self.lbl_fps.place(x=105, y=5)
        ctk.CTkLabel(frame_titulo, text="FPS", font=ctk.CTkFont(size=self.font_small), text_color="gray").place(x=125, y=6)
        
        self.btn_camara = ctk.CTkButton(
            frame_titulo,
            text="⏹",
            command=self.toggle_camara,
            width=28,
            height=28,
            fg_color="#e74c3c",
            font=ctk.CTkFont(size=self.font_normal)
        )
        self.btn_camara.place(x=160, y=2)
        
        # Info de resolución
        self.lbl_resolucion = ctk.CTkLabel(
            frame_titulo,
            text="1280x720",
            font=ctk.CTkFont(size=self.font_small),
            text_color="#f39c12"
        )
        self.lbl_resolucion.place(x=200, y=6)
        
        # Video - Ocupa todo el espacio restante
        self.video_label = ctk.CTkLabel(
            frame_camara,
            text="",
            fg_color="#0a0a0a"
        )
        self.video_label.pack(fill=ctk.BOTH, expand=True)
        
        # Log inicial
        self.log("Iniciado", "INFO")
        self.log("Conectando USB", "INFO")
        
        # Actualizar tamaño de video después de crear la interfaz
        self.root.after(100, self.actualizar_tamano_video)
    
    def actualizar_tamano_video(self):
        """Actualiza el tamaño del video según el espacio disponible"""
        try:
            # Obtener el tamaño actual del frame de cámara
            frame_camara = self.video_label.master
            width = frame_camara.winfo_width()
            height = frame_camara.winfo_height()
            
            if width > 10 and height > 10:
                # Restar espacio del título
                video_width = width - 10
                video_height = height - 35
                
                # Asegurar que no sea muy pequeño
                if video_width < 100:
                    video_width = 100
                if video_height < 100:
                    video_height = 100
                
                # La relación de aspecto se mantiene en el redimensionado
                # No necesitamos guardar las dimensiones aquí
        except:
            pass
    
    # ==================== FUNCIONES ====================
    def set_pasos(self, valor):
        self.entry_pasos.delete(0, ctk.END)
        self.entry_pasos.insert(0, str(valor))
    
    def actualizar_estado_luces(self, estado):
        if estado == "ON":
            self.luces_encendidas = True
            self.lbl_luces.configure(text="💡ON", text_color="#f39c12")
            self.btn_luz.configure(fg_color="#e67e22")
        else:
            self.luces_encendidas = False
            self.lbl_luces.configure(text="💡OFF", text_color="gray")
            self.btn_luz.configure(fg_color="#f39c12")
    
    # ==================== COMUNICACIÓN SERIAL ====================
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
        if linea.startswith("OK:"):
            self.log(linea[3:], "OK")
        elif linea.startswith("ERROR:"):
            self.log(linea[6:], "ERROR")
        elif linea.startswith("DONE"):
            self.log("Mov completado", "OK")
            self.moviendo = False
            self.root.after(0, lambda: self.progressbar.set(1.0))
            self.root.after(0, lambda: self.lbl_progreso.configure(text="100%"))
            self.consultar_estado()
        elif linea.startswith("STOPPED:"):
            self.log("Detenido", "WARNING")
            self.moviendo = False
            self.consultar_estado()
        elif linea.startswith("ESTADO:"):
            self.actualizar_estado(linea[7:])
        elif linea.startswith("ESP8266 LISTO"):
            self.log("ESP8266 listo", "OK")
        elif linea.startswith("LUCES:"):
            self.actualizar_estado_luces(linea[6:].strip())
        else:
            self.log(linea, "INFO")
    
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
                    self.lbl_estado_motor.configure(text="🟢")
                    self.motor_habilitado = True
                else:
                    self.lbl_estado_motor.configure(text="🔴")
                    self.motor_habilitado = False
            
            if 'Moviendo' in estado:
                if estado['Moviendo'] == "SI":
                    self.lbl_moviendo.configure(text="🟢")
                    self.moviendo = True
                else:
                    self.lbl_moviendo.configure(text="⚪")
                    self.moviendo = False
            
            if 'PasosRestantes' in estado:
                self.pasos_restantes = int(estado['PasosRestantes'])
                self.lbl_pasos.configure(text=str(self.pasos_restantes))
            
            if 'Progreso' in estado:
                progreso_str = estado['Progreso'].replace('%', '')
                try:
                    progreso = int(progreso_str)
                    self.progressbar.set(progreso / 100.0)
                    self.lbl_progreso.configure(text=f"{progreso}%")
                except:
                    pass
                
            if 'Luces' in estado:
                self.actualizar_estado_luces(estado['Luces'])
                
        except:
            pass
    
    def enviar_comando(self, comando):
        if not self.conectado or not self.ser or not self.ser.is_open:
            return False
        try:
            self.ser.write((comando + "\n").encode())
            self.log(f">>> {comando}", "COMANDO")
            return True
        except:
            return False
    
    def mover(self):
        if not self.conectado:
            self.log("No conectado", "ERROR")
            return
        if not self.motor_habilitado:
            self.log("Motor deshab", "WARNING")
            return
        if self.moviendo:
            self.log("En movimiento", "WARNING")
            return
        
        try:
            pasos = int(self.entry_pasos.get())
            if pasos <= 0:
                raise ValueError()
            
            self.progressbar.set(0)
            self.lbl_progreso.configure(text="0%")
            
            direccion = 0 if self.combo_direccion.get() == "▶ adelante" else 1
            self.enviar_comando(f"DIRECCION={direccion}")
            time.sleep(0.1)
            self.enviar_comando(f"MOVER={pasos}")
            self.root.after(100, self.consultar_estado)
            
        except:
            self.log("Pasos invalidos", "ERROR")
    
    def detener(self):
        self.enviar_comando("STOP")
        self.root.after(500, self.consultar_estado)
    
    def habilitar(self):
        self.enviar_comando("ENABLE")
        self.root.after(500, self.consultar_estado)
    
    def deshabilitar(self):
        self.enviar_comando("DISABLE")
        self.root.after(500, self.consultar_estado)
    
    def consultar_estado(self):
        self.enviar_comando("ESTADO")
    
    def log(self, mensaje, tipo="INFO"):
        timestamp = time.strftime("%H:%M:%S")
        self.txt_log.insert("end", f"[{timestamp}] ", "INFO")
        self.txt_log.insert("end", mensaje + "\n", tipo)
        self.txt_log.see("end")
        
        # Limitar líneas
        if int(self.txt_log.index('end-1c').split('.')[0]) > 100:
            self.txt_log.delete("1.0", "30.0")
    
    def limpiar_log(self):
        self.txt_log.delete("1.0", "end")
        self.log("Log limpiado", "INFO")
    
    def __del__(self):
        self.camara_activa = False
        self.lectura_activa = False
        if self.process:
            self.process.terminate()
            self.process = None
        if self.ser and self.ser.is_open:
            self.ser.close()

# ==================== MAIN ====================
if __name__ == "__main__":
    root = ctk.CTk()
    app = ControlMotor(root)
    root.mainloop()