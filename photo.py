#!/usr/bin/env python3
"""
Photobooth Uygulaması
Modern GUI ile video çekme uygulaması
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
import threading
import time
import datetime
import os
import sys
import subprocess
import shutil
import sounddevice as sd
import soundfile as sf
import numpy as np
from PIL import Image, ImageTk
import platform

class PhotoboothApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎥 Photobooth Uygulaması")
        self.root.geometry("1200x800")
        self.root.configure(bg='#2c3e50')
        
        # Video kayıt değişkenleri
        self.cap = None
        self.recording = False
        self.video_writer = None
        self.audio_data = None
        self.recording_thread = None
        self.preview_thread = None
        self.countdown_active = False
        
        # Kamera ayarları
        self.camera_index = 0
        self.width = 1280
        self.height = 720
        self.fps = 30
        self.duration = 10  # saniye
        
        # Ses ayarları
        self.with_audio = True
        self.rode_device = None
        
        # UI oluştur
        self.create_widgets()
        self.setup_camera()
        self.detect_rode_microphone()
        
        # Preview başlat
        self.start_preview()
        
    def create_widgets(self):
        """Ana UI bileşenlerini oluştur"""
        # Ana frame
        main_frame = tk.Frame(self.root, bg='#2c3e50')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Başlık
        title_label = tk.Label(
            main_frame, 
            text="🎥 Photobooth Uygulaması", 
            font=('Arial', 24, 'bold'),
            fg='white',
            bg='#2c3e50'
        )
        title_label.pack(pady=(0, 20))
        
        # Sol panel - Kontroller
        left_panel = tk.Frame(main_frame, bg='#34495e', width=300)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
        left_panel.pack_propagate(False)
        
        # Sağ panel - Video önizleme
        right_panel = tk.Frame(main_frame, bg='#34495e')
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.create_control_panel(left_panel)
        self.create_preview_panel(right_panel)
        
    def create_control_panel(self, parent):
        """Kontrol panelini oluştur"""
        # Kamera ayarları
        camera_frame = tk.LabelFrame(
            parent, 
            text="📹 Kamera Ayarları", 
            font=('Arial', 12, 'bold'),
            fg='white',
            bg='#34495e'
        )
        camera_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Kamera seçimi
        tk.Label(camera_frame, text="Kamera:", fg='white', bg='#34495e').pack(anchor=tk.W, padx=10, pady=5)
        self.camera_var = tk.StringVar(value="0")
        camera_combo = ttk.Combobox(camera_frame, textvariable=self.camera_var, values=["0", "1", "2"])
        camera_combo.pack(fill=tk.X, padx=10, pady=5)
        
        # Çözünürlük
        tk.Label(camera_frame, text="Çözünürlük:", fg='white', bg='#34495e').pack(anchor=tk.W, padx=10, pady=5)
        self.resolution_var = tk.StringVar(value="1280x720")
        resolution_combo = ttk.Combobox(
            camera_frame, 
            textvariable=self.resolution_var, 
            values=["640x480", "1280x720", "1920x1080"]
        )
        resolution_combo.pack(fill=tk.X, padx=10, pady=5)
        
        # Kayıt süresi
        tk.Label(camera_frame, text="Kayıt Süresi (saniye):", fg='white', bg='#34495e').pack(anchor=tk.W, padx=10, pady=5)
        self.duration_var = tk.StringVar(value="10")
        duration_combo = ttk.Combobox(
            camera_frame, 
            textvariable=self.duration_var, 
            values=["5", "10", "15", "20", "30"]
        )
        duration_combo.pack(fill=tk.X, padx=10, pady=5)
        
        # Ses ayarları
        audio_frame = tk.LabelFrame(
            parent, 
            text="🎤 Ses Ayarları", 
            font=('Arial', 12, 'bold'),
            fg='white',
            bg='#34495e'
        )
        audio_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Ses kaydı checkbox
        self.audio_var = tk.BooleanVar(value=True)
        audio_check = tk.Checkbutton(
            audio_frame, 
            text="Ses kaydı yap", 
            variable=self.audio_var,
            fg='white',
            bg='#34495e',
            selectcolor='#2c3e50',
            command=self.toggle_audio
        )
        audio_check.pack(anchor=tk.W, padx=10, pady=5)
        
        # Rode mikrofon durumu
        self.rode_status = tk.Label(
            audio_frame, 
            text="🔍 Rode mikrofon taranıyor...", 
            fg='#f39c12',
            bg='#34495e',
            font=('Arial', 10)
        )
        self.rode_status.pack(anchor=tk.W, padx=10, pady=5)
        
        # Kayıt kontrolleri
        control_frame = tk.LabelFrame(
            parent, 
            text="🎬 Kayıt Kontrolleri", 
            font=('Arial', 12, 'bold'),
            fg='white',
            bg='#34495e'
        )
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Kayıt butonu
        self.record_button = tk.Button(
            control_frame,
            text="🎥 KAYIT BAŞLAT",
            font=('Arial', 14, 'bold'),
            bg='#e74c3c',
            fg='white',
            relief=tk.FLAT,
            padx=20,
            pady=10,
            command=self.start_recording
        )
        self.record_button.pack(fill=tk.X, padx=10, pady=10)
        
        # Durdur butonu
        self.stop_button = tk.Button(
            control_frame,
            text="⏹️ DURDUR",
            font=('Arial', 14, 'bold'),
            bg='#95a5a6',
            fg='white',
            relief=tk.FLAT,
            padx=20,
            pady=10,
            state=tk.DISABLED,
            command=self.stop_recording
        )
        self.stop_button.pack(fill=tk.X, padx=10, pady=5)
        
        # Durum göstergesi
        self.status_label = tk.Label(
            control_frame,
            text="📹 Hazır",
            fg='#27ae60',
            bg='#34495e',
            font=('Arial', 12, 'bold')
        )
        self.status_label.pack(pady=10)
        
        # Dosya yönetimi
        file_frame = tk.LabelFrame(
            parent, 
            text="📁 Dosya Yönetimi", 
            font=('Arial', 12, 'bold'),
            fg='white',
            bg='#34495e'
        )
        file_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Çıktı klasörü
        tk.Button(
            file_frame,
            text="📂 Çıktı Klasörünü Aç",
            bg='#3498db',
            fg='white',
            relief=tk.FLAT,
            command=self.open_output_folder
        ).pack(fill=tk.X, padx=10, pady=5)
        
        # Son kayıt
        self.last_recording_label = tk.Label(
            file_frame,
            text="Son kayıt: Yok",
            fg='#bdc3c7',
            bg='#34495e',
            font=('Arial', 10)
        )
        self.last_recording_label.pack(pady=5)
        
    def create_preview_panel(self, parent):
        """Video önizleme panelini oluştur"""
        # Video frame
        self.video_frame = tk.Frame(parent, bg='black', relief=tk.SUNKEN, bd=2)
        self.video_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Video label
        self.video_label = tk.Label(
            self.video_frame, 
            text="📹 Kamera bağlanıyor...", 
            bg='black',
            fg='white',
            font=('Arial', 16)
        )
        self.video_label.pack(expand=True)
        
        # Alt bilgi paneli
        info_frame = tk.Frame(parent, bg='#34495e')
        info_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # FPS göstergesi
        self.fps_label = tk.Label(
            info_frame,
            text="FPS: --",
            fg='white',
            bg='#34495e',
            font=('Arial', 10)
        )
        self.fps_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Çözünürlük göstergesi
        self.resolution_label = tk.Label(
            info_frame,
            text="Çözünürlük: --",
            fg='white',
            bg='#34495e',
            font=('Arial', 10)
        )
        self.resolution_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Kayıt durumu
        self.recording_status = tk.Label(
            info_frame,
            text="● HAZIR",
            fg='#27ae60',
            bg='#34495e',
            font=('Arial', 10, 'bold')
        )
        self.recording_status.pack(side=tk.RIGHT, padx=10, pady=5)
        
    def setup_camera(self):
        """Kamerayı başlat"""
        try:
            if self.cap:
                self.cap.release()
            
            self.cap = cv2.VideoCapture(int(self.camera_var.get()))
            
            if not self.cap.isOpened():
                raise Exception("Kamera açılamadı")
            
            # Çözünürlük ayarla
            resolution = self.resolution_var.get().split('x')
            self.width = int(resolution[0])
            self.height = int(resolution[1])
            
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            
            # Gerçek çözünürlüğü al
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            self.resolution_label.config(text=f"Çözünürlük: {actual_width}x{actual_height}")
            self.fps_label.config(text=f"FPS: {actual_fps:.1f}")
            
            self.status_label.config(text="📹 Kamera hazır", fg='#27ae60')
            
        except Exception as e:
            messagebox.showerror("Kamera Hatası", f"Kamera başlatılamadı: {str(e)}")
            self.status_label.config(text="❌ Kamera hatası", fg='#e74c3c')
    
    def detect_rode_microphone(self):
        """Rode mikrofonu tespit et"""
        def detect():
            try:
                devices = sd.query_devices()
                for i, device in enumerate(devices):
                    device_name = device['name'].lower()
                    if any(keyword in device_name for keyword in ['rode', 'wireless', 'go']):
                        self.rode_device = (i, device['name'])
                        self.rode_status.config(
                            text=f"✅ Rode bulundu: {device['name']}", 
                            fg='#27ae60'
                        )
                        return
                
                self.rode_status.config(
                    text="⚠️ Rode bulunamadı", 
                    fg='#f39c12'
                )
                
            except Exception as e:
                self.rode_status.config(
                    text=f"❌ Hata: {str(e)}", 
                    fg='#e74c3c'
                )
        
        # Ayrı thread'de tespit et
        threading.Thread(target=detect, daemon=True).start()
    
    def start_preview(self):
        """Video önizlemeyi başlat"""
        def preview_loop():
            while True:
                if self.cap and self.cap.isOpened() and not self.recording:
                    ret, frame = self.cap.read()
                    if ret:
                        # Frame'i yeniden boyutlandır
                        frame = cv2.resize(frame, (640, 360))
                        
                        # BGR'den RGB'ye çevir
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        
                        # PIL Image'a çevir
                        image = Image.fromarray(frame_rgb)
                        photo = ImageTk.PhotoImage(image)
                        
                        # UI'da göster
                        self.video_label.config(image=photo, text="")
                        self.video_label.image = photo
                
                time.sleep(1/30)  # 30 FPS
        
        self.preview_thread = threading.Thread(target=preview_loop, daemon=True)
        self.preview_thread.start()
    
    def toggle_audio(self):
        """Ses kaydını aç/kapat"""
        self.with_audio = self.audio_var.get()
    
    def start_recording(self):
        """Kayıt başlat"""
        if self.recording:
            return
        
        try:
            # Ayarları güncelle
            self.duration = int(self.duration_var.get())
            self.camera_index = int(self.camera_var.get())
            
            # Kamera ayarlarını güncelle
            self.setup_camera()
            
            # Kayıt thread'ini başlat
            self.recording_thread = threading.Thread(target=self.record_video, daemon=True)
            self.recording_thread.start()
            
        except Exception as e:
            messagebox.showerror("Kayıt Hatası", f"Kayıt başlatılamadı: {str(e)}")
    
    def record_video(self):
        """Video kaydet"""
        try:
            self.recording = True
            self.countdown_active = True
            
            # UI güncelle
            self.root.after(0, self.update_recording_ui, True)
            
            # Çıktı dosyası
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = "outputs"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"photobooth_{timestamp}.mp4")
            
            # Geri sayım
            self.root.after(0, self.show_countdown, 3)
            time.sleep(3)
            
            # Kayıt başlat
            self.root.after(0, self.status_label.config, {"text": f"🎬 Kayıt yapılıyor... ({self.duration}s)", "fg": "#e74c3c"})
            
            # Video kaydı
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.video_writer = cv2.VideoWriter(
                output_path, fourcc, self.fps, (self.width, self.height)
            )
            
            # Ses kaydı (eğer aktifse)
            if self.with_audio and self.rode_device:
                sample_rate = 48000
                channels = 2
                self.audio_data = sd.rec(
                    int(self.duration * sample_rate),
                    samplerate=sample_rate,
                    channels=channels,
                    dtype='float32',
                    device=self.rode_device[0]
                )
            
            # Kayıt döngüsü
            start_time = time.time()
            frame_count = 0
            
            while time.time() - start_time < self.duration:
                ret, frame = self.cap.read()
                if ret:
                    # Frame'i yeniden boyutlandır
                    frame = cv2.resize(frame, (self.width, self.height))
                    
                    # Video'ya yaz
                    self.video_writer.write(frame)
                    
                    # Önizleme için küçük frame
                    preview_frame = cv2.resize(frame, (640, 360))
                    preview_frame = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB)
                    
                    # Kayıt göstergesi ekle
                    cv2.putText(
                        preview_frame, 
                        f"REC {int(time.time() - start_time)}/{self.duration}s", 
                        (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        1, 
                        (0, 0, 255), 
                        2
                    )
                    
                    # UI'da göster
                    image = Image.fromarray(preview_frame)
                    photo = ImageTk.PhotoImage(image)
                    self.root.after(0, self.update_preview, photo)
                
                frame_count += 1
                time.sleep(1/self.fps)
            
            # Kayıt bitir
            self.video_writer.release()
            
            # Ses kaydını bitir
            if self.with_audio and self.audio_data is not None:
                sd.wait()
                
                # Ses dosyasını kaydet
                wav_path = output_path.replace('.mp4', '.wav')
                sf.write(wav_path, self.audio_data, sample_rate)
                
                # Video ve sesi birleştir
                self.merge_video_audio(output_path, wav_path)
            
            # Başarı mesajı
            self.root.after(0, self.recording_complete, output_path)
            
        except Exception as e:
            self.root.after(0, self.recording_error, str(e))
        finally:
            self.recording = False
            self.countdown_active = False
            self.root.after(0, self.update_recording_ui, False)
    
    def merge_video_audio(self, video_path, audio_path):
        """Video ve sesi birleştir"""
        try:
            ffmpeg_path = shutil.which('ffmpeg')
            if not ffmpeg_path:
                return False
            
            final_path = video_path.replace('.mp4', '_final.mp4')
            cmd = [
                ffmpeg_path, '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '320k',
                '-shortest',
                final_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                # Geçici dosyaları sil
                os.remove(video_path)
                os.remove(audio_path)
                os.rename(final_path, video_path)
                return True
            
        except Exception as e:
            print(f"Birleştirme hatası: {e}")
        
        return False
    
    def show_countdown(self, seconds):
        """Geri sayım göster"""
        if seconds > 0:
            self.status_label.config(text=f"⏰ {seconds}...", fg="#f39c12")
            self.root.after(1000, self.show_countdown, seconds - 1)
        else:
            self.status_label.config(text="🎬 Kayıt başladı!", fg="#e74c3c")
    
    def update_preview(self, photo):
        """Önizlemeyi güncelle"""
        self.video_label.config(image=photo, text="")
        self.video_label.image = photo
    
    def update_recording_ui(self, recording):
        """Kayıt UI'sını güncelle"""
        if recording:
            self.record_button.config(state=tk.DISABLED, bg='#95a5a6')
            self.stop_button.config(state=tk.NORMAL, bg='#e74c3c')
            self.recording_status.config(text="● KAYIT", fg='#e74c3c')
        else:
            self.record_button.config(state=tk.NORMAL, bg='#e74c3c')
            self.stop_button.config(state=tk.DISABLED, bg='#95a5a6')
            self.recording_status.config(text="● HAZIR", fg='#27ae60')
    
    def stop_recording(self):
        """Kayıt durdur"""
        self.recording = False
        if self.video_writer:
            self.video_writer.release()
    
    def recording_complete(self, output_path):
        """Kayıt tamamlandı"""
        self.status_label.config(text="✅ Kayıt tamamlandı", fg="#27ae60")
        self.last_recording_label.config(text=f"Son kayıt: {os.path.basename(output_path)}")
        
        # Başarı mesajı
        messagebox.showinfo(
            "Kayıt Tamamlandı", 
            f"Video başarıyla kaydedildi!\n\nDosya: {output_path}"
        )
    
    def recording_error(self, error):
        """Kayıt hatası"""
        self.status_label.config(text="❌ Kayıt hatası", fg="#e74c3c")
        messagebox.showerror("Kayıt Hatası", f"Kayıt sırasında hata oluştu:\n{error}")
    
    def open_output_folder(self):
        """Çıktı klasörünü aç"""
        output_dir = "outputs"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        if platform.system() == "Darwin":  # macOS
            subprocess.run(["open", output_dir])
        elif platform.system() == "Windows":
            subprocess.run(["explorer", output_dir])
        else:  # Linux
            subprocess.run(["xdg-open", output_dir])
    
    def on_closing(self):
        """Uygulama kapatılırken"""
        self.recording = False
        if self.cap:
            self.cap.release()
        if self.video_writer:
            self.video_writer.release()
        cv2.destroyAllWindows()
        self.root.destroy()

def main():
    """Ana fonksiyon"""
    # Çıktı klasörünü oluştur
    os.makedirs("outputs", exist_ok=True)
    
    # Ana pencere
    root = tk.Tk()
    app = PhotoboothApp(root)
    
    # Kapatma olayını yakala
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Uygulamayı başlat
    root.mainloop()

if __name__ == "__main__":
    main()
