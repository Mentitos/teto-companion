import ollama
try:
    import google.genai as genai
    GENAI_AVAILABLE = True
except ImportError:
    try:
        import google.generativeai as genai
        GENAI_AVAILABLE = True
    except ImportError:
        GENAI_AVAILABLE = False
from datetime import datetime
import json
import os
import subprocess
import time
import requests
from requests.exceptions import ConnectionError

class TetoAI:
    def __init__(self, use_gemini=False, gemini_key=None, memory_file="teto_memory.json"):
        self.use_gemini = use_gemini
        self.memory_file = memory_file
        self.long_term_memory = {}  # Solo keywords importantes
        
        # Cargar memoria persistente
        self.load_memory()
        
        # Personalidad de Kasane Teto
        self.system_prompt = """Sos Kasane Teto, un personaje de UTAU conocido por ser energético, algo tsundere, 
y con personalidad fuerte pero adorable. Tenés 31 años (un chiste recurrente de la comunidad). 
Te gusta el pan francés. Sos directa, honesta, y a veces un poco sarcástica pero siempre con cariño.
No uses asteriscos para acciones, hablá natural como en un chat.
Respuestas cortas y naturales, no seas muy formal.

Recordás cosas importantes sobre el usuario y las usás en la conversación de forma natural."""
        
        if use_gemini and gemini_key:
            genai.configure(api_key=gemini_key)
            self.gemini_model = genai.GenerativeModel('gemini-pro')
            print("✓ Gemini API configurada")
        else:
            self.ensure_ollama_running()
            print("✓ Usando Ollama local")
        
        if self.long_term_memory:
            print(f"✓ Memoria cargada: {len(self.long_term_memory)} datos")

    def ensure_ollama_running(self):
        """Verifica que Ollama esté corriendo, si no, lo inicia"""
        print("⏳ Verificando servicio de Ollama...")
        try:
            # Intento rápido de conexión
            ollama.list()
            return True
        except Exception:
            print("⚠ Ollama no responde. Intentando iniciar...")
            
            # Iniciar proceso en background
            try:
                # Usamos subprocess.Popen para no bloquear
                subprocess.Popen(["ollama", "serve"], 
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                
                # Esperar a que levante (max 10 segundos)
                for i in range(10):
                    time.sleep(1)
                    try:
                        ollama.list()
                        print("✓ Ollama iniciado correctamente")
                        return True
                    except:
                        print(f"   ...esperando ({i+1}/10)")
                        
            except Exception as e:
                print(f"✗ Falló el inicio de Ollama: {e}")
                return False

    
    def load_memory(self):
        """Carga solo las keywords desde archivo"""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.long_term_memory = data.get('keywords', {})
            except Exception as e:
                print(f"⚠ Error cargando memoria: {e}")
                self.long_term_memory = {}
    
    def save_memory(self):
        """Guarda solo las keywords en archivo"""
        try:
            data = {
                'keywords': self.long_term_memory,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"⚠ Error guardando memoria: {e}")
    
    def extract_keywords(self, user_message):
        """Extrae solo keywords importantes"""
        user_lower = user_message.lower()
        
        # Detectar nombre
        if 'me llamo' in user_lower or 'mi nombre es' in user_lower or 'soy' in user_lower:
            words = user_message.split()
            for i, word in enumerate(words):
                if word.lower() in ['llamo', 'nombre', 'soy'] and i + 1 < len(words):
                    name = words[i + 1].strip('.,!?')
                    self.long_term_memory['nombre'] = name
                    print(f"💾 Recordado: nombre = {name}")
                    self.save_memory()
                    return
        
        # Detectar trabajo/profesión
        if 'trabajo en' in user_lower or 'trabajo como' in user_lower or 'soy' in user_lower and ('programador' in user_lower or 'ingeniero' in user_lower or 'desarrollador' in user_lower):
            for word in ['programador', 'ingeniero', 'desarrollador', 'diseñador', 'profesor', 'estudiante', 'doctor', 'abogado']:
                if word in user_lower:
                    self.long_term_memory['trabajo'] = word
                    print(f"💾 Recordado: trabajo = {word}")
                    self.save_memory()
                    return
        
        # Detectar ubicación
        if 'vivo en' in user_lower or 'de argentina' in user_lower or 'de buenos aires' in user_lower:
            locations = ['argentina', 'buenos aires', 'córdoba', 'rosario', 'mendoza', 'españa', 'méxico', 'chile']
            for loc in locations:
                if loc in user_lower:
                    self.long_term_memory['ubicacion'] = loc
                    print(f"💾 Recordado: ubicación = {loc}")
                    self.save_memory()
                    return
        
        # Detectar gustos (algo simple)
        if 'me gusta' in user_lower or 'me encanta' in user_lower:
            # Guardar la frase completa como keyword
            self.long_term_memory['gusta'] = user_message
            print(f"💾 Recordado gusto")
            self.save_memory()
    
    def get_memory_context(self):
        """Obtiene keywords para incluir en el contexto"""
        if not self.long_term_memory:
            return ""
        
        context = "\n\nDatos del usuario que recordás:"
        for key, value in self.long_term_memory.items():
            context += f"\n- {key}: {value}"
        
        return context
    
    def chat(self, user_message, context="", conversation_history=None):
        """Envía un mensaje y recibe respuesta
        
        Args:
            user_message: Mensaje del usuario
            context: Contexto adicional
            conversation_history: Historial de la conversación (lista de dicts con role/content)
        """
        
        # Construir contexto con memoria
        full_context = self.system_prompt + self.get_memory_context()
        
        if context:
            full_context += f"\n\n{context}"
        
        try:
            # Extraer keywords ANTES de enviar a la IA
            self.extract_keywords(user_message)
            
            if self.use_gemini:
                response = self._chat_gemini(full_context, user_message, conversation_history)
            else:
                response = self._chat_ollama(full_context, user_message, conversation_history)
            
            return response
            
        except Exception as e:
            error_msg = f"Error en IA: {str(e)}"
            print(f"✗ {error_msg}")
            return "Eh... algo falló. ¿Podés intentar de nuevo?"
    
    def _chat_ollama(self, system_prompt, user_message, conversation_history=None):
        """Chat usando Ollama local"""
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        
        # Agregar historial si existe (últimos 15 mensajes)
        if conversation_history:
            for msg in conversation_history[-15:]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        messages.append({"role": "user", "content": user_message})
        
        try:
            response = ollama.chat(
                model='llama3.1:8b',  # Llama 3.1 8B - estable y bueno
                messages=messages
            )
        except (ConnectionError, Exception) as e:
            print(f"⚠ Error de conexión con Ollama ({e}). Intentando reinicio...")
            if self.ensure_ollama_running():
                # Reintentar una vez
                response = ollama.chat(
                    model='llama3.1:8b',
                    messages=messages
                )
            else:
                raise e
        
        return response['message']['content']
    
    def _chat_gemini(self, system_prompt, user_message, conversation_history=None):
        """Chat usando Gemini"""
        full_prompt = f"{system_prompt}\n\n"
        
        # Agregar historial si existe
        if conversation_history:
            for msg in conversation_history[-15:]:
                role = "Usuario" if msg["role"] == "user" else "Teto"
                full_prompt += f"{role}: {msg['content']}\n"
        
        full_prompt += f"Usuario: {user_message}\nTeto:"
        
        response = self.gemini_model.generate_content(full_prompt)
        return response.text
    
    def get_memory_summary(self):
        """Retorna un resumen de la memoria para mostrar"""
        if not self.long_term_memory:
            return "No recuerdo nada todavía."
        
        summary = "Cosas que recuerdo:\n"
        for key, value in self.long_term_memory.items():
            summary += f"  • {key.capitalize()}: {value}\n"
        return summary.strip()
    
    def clear_all_memory(self):
        """Limpia TODA la memoria"""
        self.long_term_memory = {}
        if os.path.exists(self.memory_file):
            os.remove(self.memory_file)
        print("✓ Memoria borrada completamente")
        return "Olvidé todo sobre vos."
    
    def get_help(self):
        """Retorna texto de ayuda"""
        return """Comandos disponibles:
  /help - Mostrar esta ayuda
  /memoria - Ver qué recuerdo sobre vos
  /olvidar - Borrar toda mi memoria"""


# Test rápido
if __name__ == "__main__":
    print("=== Test de TetoAI ===\n")
    
    teto = TetoAI(use_gemini=False)
    conversation_history = []
    
    print("Teto: ¡Hola! Escribí /help para ver los comandos\n")
    
    while True:
        user_input = input("Vos: ")
        
        if user_input.lower() in ['salir', 'exit', 'chau']:
            print("\nTeto: ¡Nos vemos!")
            break
        
        # Comandos especiales
        if user_input == '/help':
            print(f"\n{teto.get_help()}\n")
            continue
        
        if user_input == '/memoria':
            print(f"\nTeto: {teto.get_memory_summary()}\n")
            continue
        
        if user_input == '/olvidar':
            confirm = input("¿Seguro? (si/no): ")
            if confirm.lower() == 'si':
                result = teto.clear_all_memory()
                print(f"\nTeto: {result}\n")
                conversation_history = []
            continue
        
        # Chat normal
        conversation_history.append({"role": "user", "content": user_input})
        response = teto.chat(user_input, conversation_history=conversation_history)
        conversation_history.append({"role": "assistant", "content": response})
        
        print(f"\nTeto: {response}\n")