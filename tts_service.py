import asyncio
import edge_tts
import pygame
import os
import tempfile
from threading import Thread

class TetoTTS:
    def __init__(self, voice="es-AR-ElenaNeural"):
        """
        Voces recomendadas en español:
        - es-AR-ElenaNeural (Argentina, femenina) ← RECOMENDADA para Teto
        - es-AR-TomasNeural (Argentina, masculina)
        - es-ES-ElviraNeural (España, femenina)
        - es-MX-DaliaNeural (México, femenina)
        """
        self.voice = voice
        pygame.mixer.init()
        self.temp_dir = tempfile.gettempdir()
        print(f"✓ TTS configurado con voz: {voice}")
    
    async def _generate_speech_async(self, text, output_file):
        """Genera el audio usando Edge TTS"""
        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(output_file)
    
    def generate_speech(self, text):
        """Genera el archivo de audio de forma síncrona"""
        output_file = os.path.join(self.temp_dir, "teto_speech.mp3")
        
        # Ejecutar la función async
        asyncio.run(self._generate_speech_async(text, output_file))
        
        return output_file
    
    def speak(self, text, blocking=False):
        """
        Hace que Teto hable
        
        Args:
            text: El texto a decir
            blocking: Si True, espera a que termine de hablar
        """
        def _speak_thread():
            try:
                # Generar audio
                audio_file = self.generate_speech(text)
                
                # Reproducir
                pygame.mixer.music.load(audio_file)
                pygame.mixer.music.play()
                
                # Esperar a que termine
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                
                # Limpiar
                pygame.mixer.music.unload()
                
            except Exception as e:
                print(f"✗ Error en TTS: {e}")
        
        if blocking:
            _speak_thread()
        else:
            # Ejecutar en thread separado para no bloquear la UI
            thread = Thread(target=_speak_thread)
            thread.daemon = True
            thread.start()
    
    def stop(self):
        """Detiene la reproducción actual"""
        pygame.mixer.music.stop()
    
    def is_speaking(self):
        """Retorna True si está hablando actualmente"""
        return pygame.mixer.music.get_busy()
    
    def list_available_voices(self):
        """Lista todas las voces disponibles en español"""
        async def _list_voices():
            voices = await edge_tts.list_voices()
            spanish_voices = [v for v in voices if v['Locale'].startswith('es-')]
            return spanish_voices
        
        return asyncio.run(_list_voices())


# Test
if __name__ == "__main__":
    print("=== Test de TTS ===\n")
    
    tts = TetoTTS()
    
    print("Probando voz...")
    tts.speak("¡Hola! Soy Kasane Teto. ¿Qué tal estás?", blocking=True)
    
    print("\n✓ Test completado")
    
    # Mostrar voces disponibles
    print("\nVoces en español disponibles:")
    voices = tts.list_available_voices()
    for v in voices[:10]:  # Mostrar las primeras 10
        print(f"  - {v['ShortName']}: {v['FriendlyName']}")