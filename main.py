import sys
import os
import subprocess
import speech_recognition as sr
import threading
import pyaudio
from pynput import keyboard
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QTextEdit, 
                             QPushButton, QVBoxLayout, QHBoxLayout, QLineEdit)
from PyQt5.QtCore import Qt, QPoint, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QFont
from ai_service import TetoAI
from tts_service import TetoTTS

class SubtitleOverlay(QWidget):
    """Subtítulos flotantes para mostrar lo que escucha"""
    def __init__(self):
        super().__init__()
        # Importante: WindowTransparentForInput permite clickear a través, pero no si queremos moverlo.
        # Quitamos WindowTransparentForInput para que se vea claro, o lo dejamos si es solo overlay.
        # El usuario quiere VERLO, así que aseguramos que esté TopMost.
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        layout = QVBoxLayout()
        self.label = QLabel("")
        self.label.setStyleSheet("""
            QLabel {
                color: #ffff00; /* Amarillo para contraste */
                font-size: 20px;
                font-weight: bold;
                background-color: rgba(0, 0, 0, 180);
                padding: 15px;
                border-radius: 10px;
                border: 2px solid white;
            }
        """)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.setLayout(layout)
        
        # Posicionar
        self.update_position()
        
    def update_position(self):
        screen = QApplication.primaryScreen().geometry()
        # Ancho 80% de la pantalla, centrado abajo
        w = int(screen.width() * 0.8)
        h = 100
        x = (screen.width() - w) // 2
        y = screen.height() - h - 50 
        self.setGeometry(x, y, w, h)
        
    def set_text(self, text):
        self.label.setText(text)
        self.update_position()
        self.show()
        self.raise_() # Traer al frente
        
    def clear(self):
        self.hide()

class AIWorker(QThread):

    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, teto_ai, message, history):
        super().__init__()
        self.teto_ai = teto_ai
        self.message = message
        self.history = history
        
    def run(self):
        try:
            response = self.teto_ai.chat(self.message, conversation_history=self.history)
            self.finished.emit(response)
        except Exception as e:
            self.error.emit(str(e))

class VoiceWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, audio_data):
        super().__init__()
        self.audio_data = audio_data
    
    def run(self):
        r = sr.Recognizer()
        try:
            # Usar el audio raw capturado
            text = r.recognize_google(self.audio_data, language="es-AR")
            print(f"🎤 Reconocido: {text}")
            self.finished.emit(text)
        except sr.UnknownValueError:
            self.error.emit("No entendí...")
        except Exception as e:
            self.error.emit(f"Error voz: {e}")


class SpeechBubble(QWidget):
    """Globo de diálogo que aparece arriba de Teto"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.label = QLabel(self)
        self.label.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 240);
                border: 3px solid #ff69b4;
                border-radius: 15px;
                padding: 12px 15px;
                color: #2b2b2b;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        self.label.setWordWrap(True)
        self.hide()
        
    def show_message(self, text):
        """Muestra un mensaje en el globito con ajuste dinámico"""
        self.label.setText(text)
        
        # Calcular tamaño cuadrado ideal
        # Aproximación: sqrt(caracteres * factor)
        chars = len(text)
        ideal_width = int((chars * 10) ** 0.5 * 10)
        ideal_width = max(100, min(ideal_width, 300))
        
        self.label.setFixedWidth(ideal_width)
        self.label.adjustSize()
        
        self.resize(self.label.width() + 10, self.label.height() + 10)
        self.label.move(5, 5)
        self.show()
        
    def hide_message(self):
        """Oculta el globito"""
        self.hide()


class ChatPanel(QWidget):
    """Panel de chat que aparece debajo de Teto"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.init_ui()
        self.hide()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Container con fondo
        container = QWidget()
        container.setStyleSheet("""
            QWidget {
                background-color: rgba(43, 43, 43, 230);
                border: 3px solid #ff69b4;
                border-radius: 10px;
            }
        """)
        
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(10, 10, 10, 10)
        container_layout.setSpacing(8)
        
        # Input del usuario
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Escribile a Teto...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #3b3b3b;
                color: #ffffff;
                border: 2px solid #ff69b4;
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 2px solid #ff1493;
            }
        """)
        
        # Botones
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)
        
        self.mic_button = QPushButton("🎤")
        self.mic_button.setFixedSize(40, 35)
        self.mic_button.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: 2px solid #ff69b4;
                border-radius: 8px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #ff69b4;
            }
        """)

        self.send_button = QPushButton("Enviar")
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #ff69b4;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #ff1493;
            }
            QPushButton:pressed {
                background-color: #c71585;
            }
            QPushButton:disabled {
                background-color: #666666;
            }
        """)
        
        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(35, 35)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #666666;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #888888;
            }
        """)
        
        button_layout.addWidget(self.mic_button)
        button_layout.addWidget(self.send_button)
        button_layout.addWidget(self.close_button)
        
        container_layout.addWidget(self.input_field)
        container_layout.addLayout(button_layout)
        
        container.setLayout(container_layout)
        layout.addWidget(container)
        
        self.setLayout(layout)
        self.setFixedWidth(300)
        self.adjustSize()


class TetoCompanion(QWidget):
    def __init__(self):
        super().__init__()
        self.dragging = False
        self.offset = QPoint()
        self.chat_active = False
        self.conversation_history = []
        
        self.known_processes = set()
        # Timer para procesos
        self.process_timer = QTimer(self)
        self.process_timer.timeout.connect(self.check_processes)
        self.process_timer.start(5000) # Cada 5 segundos
        
        # Variables para física de agitado
        self.original_pixmap = None
        self.current_scale = 1.0
        self.shake_intensity = 0.0
        self.last_global_pos = None
        self.hold_timer = 0
        
        # Timer de física (30 FPS aprox)
        self.physics_timer = QTimer(self)
        self.physics_timer.timeout.connect(self.update_physics)
        self.physics_timer.start(33)
        
        # IA
        self.teto_ai = TetoAI(use_gemini=False)
        
        # TTS
        self.tts = TetoTTS(voice="es-AR-ElenaNeural")
        
        # Globito de diálogo
        self.speech_bubble = SpeechBubble()
        
        # Panel de chat
        self.chat_panel = ChatPanel()
        self.chat_panel.input_field.returnPressed.connect(self.send_message)
        self.chat_panel.send_button.clicked.connect(self.send_message)
        self.chat_panel.close_button.clicked.connect(self.toggle_chat)
        self.chat_panel.mic_button.clicked.connect(self.toggle_voice_input)
        
        # Subtítulos
        self.subtitles = SubtitleOverlay()
        
        # Audio PTT
        self.is_recording = False
        self.audio_frames = []
        self.pyaudio_instance = pyaudio.PyAudio()
        self.stream = None
        
        self.init_ui()

    def keyPressEvent(self, event):
        """PTT cuando se presiona O"""
        if event.key() == Qt.Key_O and not event.isAutoRepeat() and not self.is_recording:
            self.start_recording()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """PTT cuando se suelta O"""
        if event.key() == Qt.Key_O and not event.isAutoRepeat() and self.is_recording:
            self.stop_recording()
        super().keyReleaseEvent(event)

            
    def start_recording(self):
        print("🎤 Iniciando grabación PTT...")
        self.is_recording = True
        self.audio_frames = []
        
        # Feedback visual
        QTimer.singleShot(0, lambda: self.subtitles.set_text("🎤 Escuchando..."))
        
        # Abrir stream
        try:
            self.stream = self.pyaudio_instance.open(format=pyaudio.paInt16,
                                                   channels=1,
                                                   rate=44100,
                                                   input=True,
                                                   frames_per_buffer=1024)
            
            # Grabar en hilo aparte para no bloquear
            threading.Thread(target=self.record_loop).start()
            
        except Exception as e:
            print(f"Error abriendo mic: {e}")
            self.is_recording = False

    def record_loop(self):
        while self.is_recording and self.stream:
            try:
                data = self.stream.read(1024)
                self.audio_frames.append(data)
            except:
                break

    def stop_recording(self):
        print("🎤 Deteniendo grabación...")
        self.is_recording = False
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            
        # Convertir a AudioData de SpeechRecognition
        raw_data = b''.join(self.audio_frames)
        audio_data = sr.AudioData(raw_data, 44100, 2)
        
        # Procesar
        QTimer.singleShot(0, lambda: self.subtitles.set_text("⏳ Procesando..."))
        self.process_voice(audio_data)

    def process_voice(self, audio_data):
        self.voice_worker = VoiceWorker(audio_data)
        self.voice_worker.finished.connect(self.handle_voice_result)
        self.voice_worker.error.connect(self.handle_voice_error)
        self.voice_worker.start()

    def handle_voice_result(self, text):
        self.subtitles.set_text(f"🗣 \"{text}\"")
        QTimer.singleShot(3000, self.subtitles.clear)
        
        # Enviar al chat
        self.chat_panel.input_field.setText(text)
        self.send_message()

    def handle_voice_error(self, error):
        self.subtitles.set_text(f"❌ {error}")
        QTimer.singleShot(2000, self.subtitles.clear)
        
    def init_ui(self):
        # Ventana sin bordes, siempre arriba, fondo transparente
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Label para el sprite
        self.sprite_label = QLabel(self)
        
        # Cargar el sprite
        sprite_path = os.path.join('sprites', 'idle', 'Sprite-0001.png')
        
        if os.path.exists(sprite_path):
            self.original_pixmap = QPixmap(sprite_path)
            self.sprite_label.setPixmap(self.original_pixmap)
            self.setGeometry(100, 100, self.original_pixmap.width(), self.original_pixmap.height())
            self.sprite_label.setGeometry(0, 0, self.original_pixmap.width(), self.original_pixmap.height())
            print(f"✓ Sprite cargado")
        else:
            print(f"✗ No se encontró el sprite")
            self.setGeometry(100, 100, 200, 200)
            self.sprite_label.setGeometry(0, 0, 200, 200)
        
        print("\n=== Kasane Teto Companion ===")
        print("- Click izquierdo: Arrastrar")
        print("- Doble click: Abrir/cerrar chat")
        print("- Click derecho: Menú/Cerrar")
        print("=============================\n")
        
        # Saludo inicial
        QTimer.singleShot(500, self.show_startup_greeting)

    def show_startup_greeting(self):
        """Muestra el saludo inicial con la hora"""
        greeting = self.get_time_greeting()
        self.speech_bubble.show_message(f"¡Hola! {greeting}")
        self.update_bubble_position()
        QTimer.singleShot(30000, self.speech_bubble.hide_message)
            
    def mouseDoubleClickEvent(self, event):
        """Doble click para abrir/cerrar chat"""
        if event.button() == Qt.LeftButton:
            self.toggle_chat()
            
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = event.pos()
            self.last_global_pos = event.globalPos()
        elif event.button() == Qt.RightButton:
            # Por ahora solo cierra, después podés agregar menú contextual
            print("Cerrando...")
            self.close()
            
    def mouseMoveEvent(self, event):
        if self.dragging:
            curr_pos = event.globalPos()
            self.move(curr_pos - self.offset)
            
            # Detectar agitado
            if self.last_global_pos:
                dist = (curr_pos - self.last_global_pos).manhattanLength()
                # Aumentar intensidad si se mueve
                self.shake_intensity += dist
            
            self.last_global_pos = curr_pos
            
            self.update_bubble_position()
            self.update_chat_position()
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.last_global_pos = None

    def update_physics(self):
        """Actualiza el tamaño basado en el agitado"""
        
        # Si estamos en espera (teto gigante)
        if self.hold_timer > 0:
            self.hold_timer -= 33
            # Mantener intensidad al tope para que no se achique
            self.shake_intensity = 6000
            target_scale = 3.0
            
            if self.hold_timer <= 0:
                self.hold_timer = 0
                
        else:
            # Decaer intensidad (un poco más lento para que sea más fácil mantener)
            self.shake_intensity = max(0, self.shake_intensity * 0.95 - 10)
            
            # Calcular escala objetivo (1.0 a 3.0)
            # Ahora es más sensible para llegar a x3
            target_scale = 1.0 + min(self.shake_intensity / 3000.0, 2.0)
            
            # Si llegamos al máximo, activamos el timer de espera
            if target_scale >= 3.0:
                target_scale = 3.0
                self.hold_timer = 3000 # 3 segundos de espera
                # Feedback visual opcional
                self.speech_bubble.show_message("¡WAAAAH! 💢")
                self.update_bubble_position()
                QTimer.singleShot(2000, self.speech_bubble.hide_message)
        
        # Suavizar transición
        if abs(target_scale - self.current_scale) > 0.001:
            self.current_scale += (target_scale - self.current_scale) * 0.1
            self.apply_scale()
            
    def apply_scale(self):
        """Aplica la escala actual al sprite y ventana"""
        if not self.original_pixmap:
            return
            
        new_w = int(self.original_pixmap.width() * self.current_scale)
        new_h = int(self.original_pixmap.height() * self.current_scale)
        
        if new_w != self.width() or new_h != self.height():
            scaled_pixmap = self.original_pixmap.scaled(
                new_w, new_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.sprite_label.setPixmap(scaled_pixmap)
            self.sprite_label.resize(new_w, new_h)
            self.resize(new_w, new_h)
            
            # Actualizar posiciones de elementos adjuntos inmediatamente
            self.update_bubble_position()
            self.update_chat_position()
    
    def toggle_chat(self):
        """Abre/cierra el chat"""
        if self.chat_active:
            # Cerrar chat
            self.chat_active = False
            self.chat_panel.hide()
            self.speech_bubble.hide_message()
        else:
            # Abrir chat
            self.chat_active = True
            self.update_chat_position()
            self.chat_panel.show()
            self.chat_panel.input_field.setFocus()
            
            # Mensaje de bienvenida
            if not self.conversation_history:
                greeting = self.get_time_greeting()
                self.speech_bubble.show_message(f"{greeting} ¿Qué querés?\nEscribí /help para ver comandos")
                self.update_bubble_position()
    
    def get_time_greeting(self):
        """Devuelve un saludo basado en la hora del día"""
        hour = datetime.now().hour
        
        if 6 <= hour < 12:
            return "¡Buenos días!"
        elif 12 <= hour < 20:
            return "¡Buenas tardes!"
        else:
            return "¡Buenas noches!"
    
    def update_bubble_position(self):
        """Actualiza la posición del globito (arriba de Teto)"""
        if self.speech_bubble.isVisible():
            bubble_x = self.x() + (self.width() // 2) - (self.speech_bubble.width() // 2)
            bubble_y = self.y() - self.speech_bubble.height() - 15
            self.speech_bubble.move(bubble_x, bubble_y)
    
    def update_chat_position(self):
        """Actualiza la posición del panel de chat (debajo de Teto)"""
        if self.chat_panel.isVisible():
            chat_x = self.x() + (self.width() // 2) - (self.chat_panel.width() // 2)
            chat_y = self.y() + self.height() + 10
            self.chat_panel.move(chat_x, chat_y)
    
    
    def send_message(self):
        """Envía mensaje a Teto (Async)"""
        message = self.chat_panel.input_field.text().strip()
        if not message:
            return
        
        self.chat_panel.input_field.clear()
        
        # Comandos especiales (síncronos)
        if message.startswith('/'):
            self.handle_command(message)
            return

        # Deshabilitar UI
        self.chat_panel.send_button.setEnabled(False)
        self.chat_panel.input_field.setEnabled(False)
        self.chat_panel.mic_button.setEnabled(False)
        self.chat_panel.send_button.setText("...")
        
        # Mostrar que está pensando
        self.speech_bubble.show_message("🤔 Pensando...")
        self.update_bubble_position()
        
        # Agregar mensaje al historial
        self.conversation_history.append({"role": "user", "content": message})
        
        # Iniciar Worker
        self.ai_worker = AIWorker(self.teto_ai, message, self.conversation_history)
        self.ai_worker.finished.connect(self.handle_ai_response)
        self.ai_worker.error.connect(self.handle_ai_error)
        self.ai_worker.start()

    def handle_command(self, command):
        """Maneja comandos slash"""
        if command == '/help':
            text = self.teto_ai.get_help()
        elif command == '/memoria':
            text = self.teto_ai.get_memory_summary()
        elif command == '/olvidar':
            text = self.teto_ai.clear_all_memory()
            self.conversation_history = []
        else:
            text = "Comando desconocido"
            
        self.speech_bubble.show_message(text)
        self.update_bubble_position()

    def handle_ai_response(self, response):
        """Maneja respuesta exitosa de la IA"""
        # UI Release
        self.chat_panel.send_button.setEnabled(True)
        self.chat_panel.input_field.setEnabled(True)
        self.chat_panel.mic_button.setEnabled(True)
        self.chat_panel.send_button.setText("Enviar")
        self.chat_panel.input_field.setFocus()
        
        # Historial
        self.conversation_history.append({"role": "assistant", "content": response})
        
        # Mostrar y hablar
        self.speech_bubble.show_message(response)
        self.update_bubble_position()
        self.tts.speak(response, blocking=False)
        
    def handle_ai_error(self, error):
        """Maneja error de la IA"""
        self.chat_panel.send_button.setEnabled(True)
        self.chat_panel.input_field.setEnabled(True)
        self.chat_panel.mic_button.setEnabled(True)
        self.chat_panel.send_button.setText("Enviar")
        
        self.speech_bubble.show_message(f"Error: {error}")
        self.update_bubble_position()

    def toggle_voice_input(self):
        """Maneja la entrada de voz"""
        self.chat_panel.mic_button.setEnabled(False)
        self.chat_panel.input_field.setPlaceholderText("Escuchando...")
        self.chat_panel.mic_button.setStyleSheet("background-color: #ff0000; border-radius: 8px;")
        
        self.voice_worker = VoiceWorker()
        self.voice_worker.listening.connect(lambda: self.speech_bubble.show_message("👂 Te escucho..."))
        self.voice_worker.finished.connect(self.handle_voice_result)
        self.voice_worker.error.connect(self.handle_voice_error)
        self.voice_worker.start()
        
    def handle_voice_result(self, text):
        self.speech_bubble.hide_message()
        self.chat_panel.input_field.setPlaceholderText("Escribile a Teto...")
        self.chat_panel.mic_button.setEnabled(True)
        self.chat_panel.mic_button.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: 2px solid #ff69b4;
                border-radius: 8px;
                font-size: 16px;
            }
        """)
        
        # Escribir y enviar
        self.chat_panel.input_field.setText(text)
        self.send_message()

    def handle_voice_error(self, error):
        self.chat_panel.input_field.setPlaceholderText("Escribile a Teto...")
        self.chat_panel.mic_button.setEnabled(True)
        self.chat_panel.mic_button.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: 2px solid #ff69b4;
                border-radius: 8px;
                font-size: 16px;
            }
        """)
        self.speech_bubble.show_message(error)
        self.update_bubble_position()
    
    def closeEvent(self, event):
        """Al cerrar la ventana principal"""
        self.speech_bubble.close()
        self.chat_panel.close()
        
        # Cerrar Ollama si se usó (prioritario)
        if not self.teto_ai.use_gemini:
            print("Cerrando Ollama...")
            try:
                subprocess.run('taskkill /F /IM ollama.exe', shell=True, stderr=subprocess.DEVNULL)
                subprocess.run('taskkill /F /IM "ollama app.exe"', shell=True, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Error cerrando Ollama: {e}")
        
        event.accept()

    def check_processes(self):
        """Revisa procesos nuevos"""
        try:
            # Obtener lista de procesos usando tasklist
            output = subprocess.check_output('tasklist /FO CSV /NH', shell=True).decode('utf-8', errors='ignore')
            current_processes = set()
            
            for line in output.splitlines():
                if '"' in line:
                    # El formato es "Image Name","PID",...
                    proc_name = line.split('","')[0].replace('"', '').lower()
                    current_processes.add(proc_name)
            
            # Detectar nuevos procesos (si no es la primera vez)
            if self.known_processes:
                new_procs = current_processes - self.known_processes
                
                for proc in new_procs:
                    if proc in ['code.exe', 'chimera.exe', 'steam.exe', 'discord.exe']:
                         print(f"👀 Teto vió que abriste: {proc}")

                if 'code.exe' in new_procs:
                    self.speech_bubble.show_message("¡Oh! ¿Vas a programar?\n¡Espero que no rompas nada!")
                    self.update_bubble_position()
                    QTimer.singleShot(5000, self.speech_bubble.hide_message)
                
                # Ejemplo extra: navegador
                elif 'chrome.exe' in new_procs and 'chrome.exe' not in self.known_processes:
                    # Chrome abre muchos procesos, evitar spam
                    pass 
                    
            self.known_processes = current_processes
            
        except Exception as e:
            print(f"Error monitoreando procesos: {e}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    companion = TetoCompanion()
    companion.show()
    sys.exit(app.exec_())