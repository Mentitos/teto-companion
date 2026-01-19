import sys
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QTextEdit, 
                             QPushButton, QVBoxLayout, QHBoxLayout, QLineEdit)
from PyQt5.QtCore import Qt, QPoint, QTimer, QPropertyAnimation, QRect
from PyQt5.QtGui import QPixmap, QFont
from ai_service import TetoAI
from tts_service import TetoTTS

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
        self.label.setMaximumWidth(300)
        self.label.setMinimumWidth(100)
        self.hide()
        
    def show_message(self, text):
        """Muestra un mensaje en el globito"""
        self.label.setText(text)
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
        
        # IA
        self.teto_ai = TetoAI(use_gemini=False)  # Cambiar a True y agregar key para Gemini
        
        # TTS
        self.tts = TetoTTS(voice="es-AR-ElenaNeural")  # Voz argentina femenina
        
        # Globito de diálogo
        self.speech_bubble = SpeechBubble()
        
        # Panel de chat
        self.chat_panel = ChatPanel()
        self.chat_panel.input_field.returnPressed.connect(self.send_message)
        self.chat_panel.send_button.clicked.connect(self.send_message)
        self.chat_panel.close_button.clicked.connect(self.toggle_chat)
        
        self.init_ui()
        
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
            pixmap = QPixmap(sprite_path)
            self.sprite_label.setPixmap(pixmap)
            self.setGeometry(100, 100, pixmap.width(), pixmap.height())
            self.sprite_label.setGeometry(0, 0, pixmap.width(), pixmap.height())
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
        
    def mouseDoubleClickEvent(self, event):
        """Doble click para abrir/cerrar chat"""
        if event.button() == Qt.LeftButton:
            self.toggle_chat()
            
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = event.pos()
        elif event.button() == Qt.RightButton:
            # Por ahora solo cierra, después podés agregar menú contextual
            print("Cerrando...")
            self.close()
            
    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(event.globalPos() - self.offset)
            self.update_bubble_position()
            self.update_chat_position()
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
    
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
                self.speech_bubble.show_message("¡Hola! ¿Qué querés?\nEscribí /help para ver comandos")
                self.update_bubble_position()
    
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
        """Envía mensaje a Teto"""
        message = self.chat_panel.input_field.text().strip()
        if not message:
            return
        
        self.chat_panel.input_field.clear()
        
        # Comandos especiales
        if message == '/help':
            help_text = self.teto_ai.get_help()
            self.speech_bubble.show_message(help_text)
            self.update_bubble_position()
            return
        
        if message == '/memoria':
            memory_text = self.teto_ai.get_memory_summary()
            self.speech_bubble.show_message(memory_text)
            self.update_bubble_position()
            return
        
        if message == '/olvidar':
            result = self.teto_ai.clear_all_memory()
            self.conversation_history = []
            self.speech_bubble.show_message(result)
            self.update_bubble_position()
            return
        
        # Deshabilitar botón mientras piensa
        self.chat_panel.send_button.setEnabled(False)
        self.chat_panel.send_button.setText("...")
        
        # Mostrar que está pensando
        self.speech_bubble.show_message("🤔")
        self.update_bubble_position()
        
        # Procesar con la IA (de forma síncrona por ahora)
        QApplication.processEvents()  # Para que se actualice la UI
        
        try:
            # Agregar mensaje al historial
            self.conversation_history.append({
                "role": "user",
                "content": message
            })
            
            # Obtener respuesta
            response = self.teto_ai.chat(message, conversation_history=self.conversation_history)
            
            # Agregar respuesta al historial
            self.conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            # Mostrar respuesta
            self.speech_bubble.show_message(response)
            self.update_bubble_position()
            
            # Hacer que hable (no bloqueante)
            self.tts.speak(response, blocking=False)
            
        except Exception as e:
            self.speech_bubble.show_message(f"Error: {str(e)}")
            self.update_bubble_position()
        
        # Reactivar botón
        self.chat_panel.send_button.setEnabled(True)
        self.chat_panel.send_button.setText("Enviar")
        self.chat_panel.input_field.setFocus()
    
    def closeEvent(self, event):
        """Al cerrar la ventana principal"""
        self.speech_bubble.close()
        self.chat_panel.close()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    companion = TetoCompanion()
    companion.show()
    sys.exit(app.exec_())