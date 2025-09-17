from flask import Flask, render_template, request, jsonify, send_from_directory, Response
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import ssl
import certifi
import msal  # type: ignore
import threading
import datetime
import os
import time
import cv2
import shutil
import subprocess
import sounddevice as sd
import soundfile as sf
import requests
import json
import uuid
import random
import base64
import numpy as np
import signal
import sys
from gif_overlay import load_gif_frames, overlay_gif_on_frame
try:
    import speech_recognition as sr  # type: ignore
except Exception:
    sr = None  # type: ignore
 
# Ortam değişkeni yoksa kullanılacak HEYGEN API anahtarı (kullanıcının verdiği)
HEYGEN_API_KEY_FALLBACK = 'N2Q5OWZiNGM2OWE1NDNlZTkwNzQyMGQ3OWY2Yzc2ZWItMTc1NzQwNDc5Nw=='
#api key:  N2Q5OWZiNGM2OWE1NDNlZTkwNzQyMGQ3OWY2Yzc2ZWItMTc1NzQwNDc5Nw==

TRANSLATED_OUTPUT_DIR = r'/Users/emirefeusenmez/Library/CloudStorage/OneDrive-DemirörenTeknoloji-Hürriyet/Masaüstü/videos'

# Ham videoların kaydedileceği klasör (OneDrive)
RAW_OUTPUT_DIR = r'/Users/emirefeusenmez/Library/CloudStorage/OneDrive-DemirörenTeknoloji-Hürriyet/Masaüstü/tr'

# GIF overlay ayarları
GIF_PATH = '/Users/emirefeusenmez/code/heygen/gif.gif'
GIF_SIZE = (100, 100)  # 200x200 piksel
GIF_POSITION = (0, 0)  # (0,0) = sağ üst köşe
GIF_ALPHA = 1.0  # Şeffaflık (1.0 = tam opak)
GIF_DURATION = 20.0  # GIF'in bir turu kaç saniyede tamamlanacak
GIF_ENABLED = True  # GIF overlay'i test amaçlı devre dışı bırakmak için bayrak

# Fligram overlay ayarları (DEVRE DIŞI)
FLIGRAM_PATH = '/Users/emirefeusenmez/code/heygen/fligram.png'
FLIGRAM_SIZE = None  # Video boyutuna göre dinamik olarak hesaplanacak
FLIGRAM_POSITION = (2, 2)  # (2,2) = merkez
FLIGRAM_ALPHA = 0.3  # Şeffaflık (0.3 = %30 opak - watermark için)
FLIGRAM_ENABLED = False  # Fligram overlay'i aktif

# Alt metin overlay ayarları
BOTTOM_TEXT_ENABLED = True  # Alt metin overlay'i aktif/pasif
BOTTOM_TEXT = "Havacılık, Uzay ve Teknoloji alanında dünyanın en büyük festivali TEKNOFEST'ten herkese merhaba. Burada milli teknoloji hamlemizin gurur verici projelerini yakından inceleme fırsatı buldum. Tüm katılımcılara sevgiler."
BOTTOM_TEXT_POSITION = (100, 1000)  # (x, y) - tam ekran için alt kısımda
BOTTOM_TEXT_FONT = cv2.FONT_HERSHEY_SIMPLEX
BOTTOM_TEXT_FONT_SCALE = 0.8  # Web arayüzü için uygun boyut
BOTTOM_TEXT_COLOR = (255, 255, 255)  # Beyaz
BOTTOM_TEXT_THICKNESS = 2  # Web arayüzü için uygun kalınlık
BOTTOM_TEXT_LINE_SPACING = 25  # Web arayüzü için uygun satır aralığı


app = Flask(__name__)

RECORD_JOBS: dict[str, dict] = {}
TRANSLATION_JOBS: dict[str, dict] = {}  # Çeviri işleri
PREVIEW_CAMERA = None  # Web stream için
FULLSCREEN_CAMERA = None  # Tam ekran pencere için
PREVIEW_THREAD = None
FULLSCREEN_THREAD = None
_fullscreen_thread = None  # Thread referansı için
PREVIEW_STOP_EVENT = threading.Event()
FULLSCREEN_STOP_EVENT = threading.Event()
RECORDING_DURATION = 20  # Video kayıt süresi (saniye)


def ensure_output_dir(path: str) -> None:
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def _send_email_smtp(recipient_email: str, subject: str, html_body: str, attachment_path: str | None = None) -> bool:
    """Basit SMTP e-posta gönderimi (O365 varsayılan). Kimlik bilgileri ortam değişkenlerinden okunur.

    Gerekli env:
      SMTP_HOST (varsayılan smtp.office365.com)
      SMTP_PORT (varsayılan 587)
      SMTP_USER (gönderici e-posta)
      SMTP_PASSWORD
    """
    smtp_host = os.getenv('SMTP_HOST', 'smtp.office365.com')
    try:
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
    except Exception:
        smtp_port = 587
    smtp_user = os.getenv('SMTP_USER') or os.getenv('SMTP_USERNAME') or "dijitalyayinlar@demirorenmedya.com"
    smtp_pass = os.getenv('SMTP_PASSWORD') or os.getenv('SMTP_PASS') or "TGG351tg@@**"

    if not smtp_user or not smtp_pass:
        print('SMTP kimlik bilgileri bulunamadı (SMTP_USER/SMTP_PASSWORD). E-posta atlanıyor.')
        return False

    try:
        # Email mesajını oluştur (mail_otomasyon.py'den alınan format)
        msg = MIMEMultipart('related')
        msg['From'] = smtp_user
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Body tipini belirle
        alternative = MIMEMultipart('alternative')
        alternative.attach(MIMEText(html_body, 'html'))
        msg.attach(alternative)

        # Video dosyasını ekle (ek/attachment olarak)
        if attachment_path and os.path.exists(attachment_path):
            try:
                with open(attachment_path, 'rb') as vf:
                    video_part = MIMEBase('video', 'mp4')
                    video_part.set_payload(vf.read())
                encoders.encode_base64(video_part)
                # Ek dosya adı: dosya adındaki kişi ismi (webcam_<isim>_... -> <isim>.mp4)
                base_name = os.path.basename(attachment_path)
                name_root, ext = os.path.splitext(base_name)
                parts = name_root.split('_')
                person_name = parts[1] if len(parts) >= 2 else name_root
                attach_name = f"{person_name}{ext or '.mp4'}"
                video_part.add_header('Content-Disposition', 'attachment', filename=attach_name)
                msg.attach(video_part)
            except FileNotFoundError:
                print(f"Video bulunamadı: {attachment_path}")
        
        # SSL context oluştur (certifi ile güvenilir kökler)
        context = ssl.create_default_context()
        try:
            context.load_verify_locations(cafile=certifi.where())
        except Exception:
            pass
        
        # SMTP bağlantısı kur
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()  # Sunucuya kendimizi tanıt
            server.starttls(context=context)  # TLS şifreleme başlat
            server.ehlo()  # TLS sonrası tekrar tanıt
            server.login(smtp_user, smtp_pass)  # Giriş yap
            
            # Email gönder
            text = msg.as_string()
            server.sendmail(smtp_user, [recipient_email], text)
            
        print(f"Email başarıyla gönderildi: {recipient_email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"SMTP kimlik doğrulama hatası: {str(e)}")
        print("Lütfen email adresinizi ve şifrenizi kontrol edin.")
        print("Exchange Online için uygulama parolası kullanmanız gerekebilir.")
        return False
        
    except smtplib.SMTPRecipientsRefused as e:
        print(f"Alıcı reddedildi: {str(e)}")
        return False
        
    except smtplib.SMTPServerDisconnected as e:
        print(f"SMTP sunucu bağlantısı kesildi: {str(e)}")
        return False
        
    except Exception as e:
        print(f"Beklenmeyen hata: {str(e)}")
        return False


def _send_email_graph(recipient_email: str, subject: str, html_body: str, attachment_path: str | None = None) -> bool:
    """Microsoft Graph API ile e-posta gönder.

    Gerekli env:
      GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET
      GRAPH_SENDER (gönderen mailbox, genelde kullanıcı veya shared mailbox UPN)
    """
    tenant_id = os.getenv('GRAPH_TENANT_ID')
    client_id = os.getenv('GRAPH_CLIENT_ID')
    client_secret = os.getenv('GRAPH_CLIENT_SECRET')
    sender_upn = os.getenv('GRAPH_SENDER')
    if not (tenant_id and client_id and client_secret and sender_upn):
        return False

    try:
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        app_conf = msal.ConfidentialClientApplication(
            client_id, authority=authority, client_credential=client_secret
        )
        scopes = ["https://graph.microsoft.com/.default"]
        token = app_conf.acquire_token_silent(scopes, account=None) or app_conf.acquire_token_for_client(scopes=scopes)
        access_token = token.get('access_token')
        if not access_token:
            print(f"Graph token alınamadı: {token}")
            return False

        # Mesaj gövdesi
        message = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": html_body},
                "toRecipients": [{"emailAddress": {"address": recipient_email}}]
            },
            "saveToSentItems": True
        }

        # Basit: eki link olarak göndermeyi tercih edin; ek eklemek gerekirse /attachments ile yüklenmeli
        import requests as _rq
        resp = _rq.post(
            f"https://graph.microsoft.com/v1.0/users/{sender_upn}/sendMail",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            data=json.dumps(message)
        )
        if resp.status_code in (202, 200):
            print("Graph: e-posta gönderildi")
            return True
        print(f"Graph sendMail hata: {resp.status_code} {resp.text[:200]}")
        return False
    except Exception as e:
        print(f"Graph gönderim hatası: {e}")
        return False



# ------- Mail HTML yardımcıları (logo ve gövde oluşturma) -------
def _encode_image_to_base64(image_path: str) -> str | None:
    try:
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception:
        return None


def _build_branded_email_body(default_body: str) -> str:
    base_dir = os.getcwd()
    n_sosyal_path = os.path.join(base_dir, 'sosyal', 'nsosyal.png')
    insta_path = os.path.join(base_dir, 'sosyal', 'insta.png')
    x_path = os.path.join(base_dir, 'sosyal', 'x.png')

    n_sosyal_logo = _encode_image_to_base64(n_sosyal_path)
    insta_logo = _encode_image_to_base64(insta_path)
    x_logo = _encode_image_to_base64(x_path)

    # Logo HTML'lerini oluştur - mail_otomasyon.py ile aynı format
    if n_sosyal_logo:
        n_sosyal_img = f'<img src="data:image/png;base64,{n_sosyal_logo}" alt="N Sosyal" style="width: 24px; height: 24px; margin-right: 10px;">'
    else:
        n_sosyal_img = '<span style="font-size: 24px; margin-right: 10px;">📱</span>'  # Emoji alternatif

    if insta_logo:
        instagram_img = f'<img src="data:image/png;base64,{insta_logo}" alt="Instagram" style="width: 24px; height: 24px; margin-right: 10px;">'
    else:
        instagram_img = '<span style="font-size: 24px; margin-right: 10px;">📷</span>'  # Emoji alternatif

    if x_logo:
        x_img = f'<img src="data:image/png;base64,{x_logo}" alt="X" style="width: 24px; height: 24px; margin-right: 10px;">'
    else:
        x_img = '<span style="font-size: 24px; margin-right: 10px;">🐦</span>'  # Emoji alternatif

    # mail_otomasyon.py ile aynı format
    return f"""
    <div style="margin:0; padding:0; background-color:#ffffff;"> 
      <div style="max-width:560px; margin:0 auto; padding:16px; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; color:#111;"> 
        {default_body}
        

        <div style="display:flex; align-items:center; gap:8px; margin:16px 0 8px;"> 
          {n_sosyal_img} 
          <span style="font-weight:700; font-size:16px;">N Sosyal</span> 
        </div> 
        <div style="font-size:14px; line-height:1.5; color:#111;"> 
          <a href="https://sosyal.teknofest.app/@hurriyet" style="color:#111;">Hürriyet</a> | 
          <a href="https://sosyal.teknofest.app/@milliyet" style="color:#111;">Milliyet</a> | 
          <a href="https://sosyal.teknofest.app/@cnnturkcom" style="color:#111;">CNN Türk</a> | 
          <a href="https://sosyal.teknofest.app/@fanatikcomtr" style="color:#111;">Fanatik</a> | 
          <a href="https://sosyal.teknofest.app/@postacomtr" style="color:#111;">Posta</a> | 
          <a href="https://sosyal.teknofest.app/@gazetevatan" style="color:#111;">Vatan</a> | 
          <a href="https://sosyal.teknofest.app/@kanald" style="color:#111;">Kanal D</a> | 
          <a href="https://sosyal.teknofest.app/@teve2" style="color:#111;">Teve2</a> 
        </div>

        <div style="display:flex; align-items:center; gap:8px; margin:16px 0 8px;"> 
          {instagram_img} 
          <span style="font-weight:700; font-size:16px;">Instagram</span> 
        </div> 
        <div style="font-size:14px; line-height:1.5; color:#111;"> 
          <a href="https://www.instagram.com/hurriyetcomtr/" style="color:#111;">Hürriyet</a> | 
          <a href="https://www.instagram.com/milliyetcomtr/" style="color:#111;">Milliyet</a> | 
          <a href="https://www.instagram.com/cnnturk/" style="color:#111;">CNN Türk</a> | 
          <a href="https://www.instagram.com/fanatikcomtr/" style="color:#111;">Fanatik</a> | 
          <a href="https://www.instagram.com/posta.com.tr/" style="color:#111;">Posta</a> | 
          <a href="https://www.instagram.com/gazetevatancom/" style="color:#111;">Vatan</a> | 
          <a href="https://www.instagram.com/kanald/" style="color:#111;">Kanal D</a> | 
          <a href="https://www.instagram.com/teve2/" style="color:#111;">Teve2</a> 
        </div>

        <div style="display:flex; align-items:center; gap:8px; margin:16px 0 8px;"> 
          {x_img} 
          <span style="font-weight:700; font-size:16px;">X</span> 
        </div> 
        <div style="font-size:14px; line-height:1.5; color:#111;"> 
          <a href="https://x.com/Hurriyet" style="color:#111;">Hürriyet</a> | 
          <a href="https://x.com/milliyet" style="color:#111;">Milliyet</a> | 
          <a href="https://x.com/cnnturk" style="color:#111;">CNN Türk</a> | 
          <a href="https://x.com/fanatikcomtr" style="color:#111;">Fanatik</a> | 
          <a href="https://x.com/postacomtr" style="color:#111;">Posta</a> | 
          <a href="https://x.com/Vatan" style="color:#111;">Vatan</a> | 
          <a href="https://x.com/kanald" style="color:#111;">Kanal D</a> | 
          <a href="https://x.com/teve2Official" style="color:#111;">Teve2</a> 
        </div>

        <p style="font-size:14px; line-height:1.5; margin:16px 0; color:#333;">Sevgiler,<br/>Demirören Medya Dijital Yayınlar</p> 
      </div> 
    </div> 
    """


def _derive_attachment_name(video_path: str) -> str:
    base_name = os.path.basename(video_path)
    name_root, ext = os.path.splitext(base_name)
    parts = name_root.split('_')
    person_name = parts[1] if len(parts) >= 2 else name_root
    return f"{person_name}{ext or '.mp4'}"


def check_camera_permissions():
    """macOS'ta kamera izinlerini kontrol et"""
    import platform
    if platform.system() != "Darwin":
        return True
    
    try:
        # Basit bir kamera testi
        cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            return ret and frame is not None
        return False
    except Exception:
        return False


def select_camera(device_index: int = 0):
    import platform
    import os
    system = platform.system()
    
    # macOS için kamera izinlerini ayarla
    if system == "Darwin":  # macOS
        # AVFoundation yetkilendirme isteğini devre dışı bırak
        os.environ['OPENCV_AVFOUNDATION_SKIP_AUTH'] = '1'
        # macOS için uygun backend'leri dene (QTKIT artık desteklenmiyor)
        backends = [cv2.CAP_AVFOUNDATION, cv2.CAP_ANY]
    elif system == "Windows":
        backends = [cv2.CAP_DSHOW]
    else:  # Linux
        backends = [cv2.CAP_V4L2, cv2.CAP_ANY]
    
    last_error = None
    for backend in backends:
        try:
            cap = cv2.VideoCapture(device_index, backend)
            
            if cap.isOpened():
                # Test frame oku
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"Kamera başarıyla açıldı (backend: {backend})")
                    return cap
                else:
                    cap.release()
        except Exception as e:
            last_error = e
            print(f"Backend {backend} hatası: {e}")
            continue
    
    error_msg = "Kamera açılamadı. "
    if system == "Darwin":
        error_msg += "macOS'ta kamera izinlerini kontrol edin: Sistem Tercihleri > Güvenlik ve Gizlilik > Gizlilik > Kamera"
    else:
        error_msg += "Başka bir uygulama kullanıyor olabilir veya cihaz yok."
    
    if last_error:
        error_msg += f" Son hata: {last_error}"
    
    raise RuntimeError(error_msg)


def set_resolution(cap, width: int = 1280, height: int = 720):
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)


def estimate_fps(cap, probe_seconds: float = 1.0) -> float:
    try:
        reported = cap.get(cv2.CAP_PROP_FPS) or 0.0
        if reported and reported >= 5.0:
            return float(reported)
    except Exception:
        pass
    
    # Daha güvenli FPS ölçümü
    start = time.perf_counter()
    frames = 0
    max_frames = 30  # Maksimum frame sayısı
    
    while time.perf_counter() - start < probe_seconds and frames < max_frames:
        try:
            ok, _ = cap.read()
            if ok:
                frames += 1
            time.sleep(0.01)  # Küçük gecikme
        except Exception:
            break
    
    dur = max(time.perf_counter() - start, 1e-3)
    measured = frames / dur
    if measured < 5:
        measured = 15.0  # macOS için daha düşük FPS
    elif measured > 30:
        measured = 30.0  # macOS için maksimum FPS
    return float(measured)


def create_writer(path: str, fps: float, frame_size):
    ensure_output_dir(path)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(path, fourcc, fps, frame_size)
    if not writer.isOpened():
        alt_path = os.path.splitext(path)[0] + '.avi'
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        writer = cv2.VideoWriter(alt_path, fourcc, fps, frame_size)
        if not writer.isOpened():
            raise RuntimeError('VideoWriter açılamadı (mp4/avi). Kodek desteğini kontrol edin.')
        return writer, alt_path
    return writer, path


def overlay_text(frame, text: str):
    return cv2.putText(frame.copy(), text, (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (0, 255, 0), 3, cv2.LINE_AA)

# GIF overlay için global değişkenler
GIF_FRAMES = None
GIF_LOADED = False

# Fligram overlay için global değişkenler
FLIGRAM_IMAGE = None
FLIGRAM_LOADED = False

def load_gif_overlay():
    """GIF overlay'i yükle"""
    global GIF_FRAMES, GIF_LOADED
    
    if GIF_LOADED:
        return GIF_FRAMES
    
    try:
        if os.path.exists(GIF_PATH):
            GIF_FRAMES = load_gif_frames(GIF_PATH, GIF_SIZE)
            if GIF_FRAMES:
                GIF_LOADED = True
                print(f"✅ GIF overlay yüklendi: {len(GIF_FRAMES)} frame")
                return GIF_FRAMES
            else:
                print("❌ GIF overlay yüklenemedi")
                return None
        else:
            print(f"⚠️ GIF dosyası bulunamadı: {GIF_PATH}")
            return None
    except Exception as e:
        print(f"❌ GIF overlay yükleme hatası: {e}")
        return None

def load_fligram_overlay(frame_width: int = 1280, frame_height: int = 720):
    """Fligram overlay'i yükle - video yüksekliğine göre 1:1 oranında boyut"""
    global FLIGRAM_IMAGE, FLIGRAM_LOADED
    
    # Video yüksekliğine göre 1:1 oranında boyut hesapla
    # Video yüksekliği kadar genişlik ve yükseklik (1:1 oran)
    fligram_size = (frame_height, frame_height)  # 1:1 oran (video yüksekliği kadar)
    
    if FLIGRAM_LOADED and FLIGRAM_IMAGE is not None:
        # Mevcut boyut kontrolü
        current_h, current_w = FLIGRAM_IMAGE.shape[:2]
        if current_w == frame_height and current_h == frame_height:
            return FLIGRAM_IMAGE
    
    try:
        if os.path.exists(FLIGRAM_PATH):
            # PNG dosyasını yükle
            from PIL import Image
            pil_image = Image.open(FLIGRAM_PATH)
            
            # Alpha channel'ı koru
            if pil_image.mode != 'RGBA':
                pil_image = pil_image.convert('RGBA')
            
            # 1:1 oranında resize et (genişlik = yükseklik = video genişliği)
            pil_image = pil_image.resize(fligram_size, Image.Resampling.LANCZOS)
            
            # PIL'den OpenCV formatına çevir (RGBA -> BGRA)
            FLIGRAM_IMAGE = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGBA2BGRA)
            FLIGRAM_LOADED = True
            print(f"✅ Fligram overlay yüklendi: {fligram_size} (1:1 oran, video yüksekliği)")
            return FLIGRAM_IMAGE
        else:
            print(f"⚠️ Fligram dosyası bulunamadı: {FLIGRAM_PATH}")
            return None
    except Exception as e:
        print(f"❌ Fligram overlay yükleme hatası: {e}")
        return None

def add_fligram_to_frame(frame):
    """Frame'e Fligram overlay ekle - 1:1 oranında ve tam merkezde"""
    global FLIGRAM_IMAGE
    
    # Fligram devre dışıysa frame'i olduğu gibi döndür
    if not FLIGRAM_ENABLED:
        return frame
    
    # Frame boyutlarını al
    frame_height, frame_width = frame.shape[:2]
    
    if FLIGRAM_IMAGE is None:
        FLIGRAM_IMAGE = load_fligram_overlay(frame_width, frame_height)
    
    if FLIGRAM_IMAGE is not None:
        return overlay_gif_on_frame(frame, [FLIGRAM_IMAGE], 0, FLIGRAM_POSITION, FLIGRAM_ALPHA)
    else:
        return frame

def add_bottom_text_to_frame(frame):
    """Frame'e alt metin ekle - çok satırlı metin desteği ile (web arayüzü için optimize edilmiş)"""
    global BOTTOM_TEXT_ENABLED, BOTTOM_TEXT, BOTTOM_TEXT_FONT, BOTTOM_TEXT_FONT_SCALE, BOTTOM_TEXT_COLOR, BOTTOM_TEXT_THICKNESS, BOTTOM_TEXT_LINE_SPACING
    
    # Alt metin devre dışıysa frame'i olduğu gibi döndür
    if not BOTTOM_TEXT_ENABLED:
        return frame
    
    # Frame boyutlarını al
    frame_height, frame_width = frame.shape[:2]
    
    # Web arayüzü için dinamik pozisyonlama (640x480 kamera görüntüsü)
    # Alt kısımda, ortalanmış pozisyon
    x = 10  # Sol kenardan 10 piksel
    y = frame_height - 20  # Alt kenardan 20 piksel yukarı
    
    # Metni satırlara böl (uzun metinleri otomatik kır)
    words = BOTTOM_TEXT.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        # Metin genişliğini tahmin et
        (text_width, _), _ = cv2.getTextSize(test_line, BOTTOM_TEXT_FONT, BOTTOM_TEXT_FONT_SCALE, BOTTOM_TEXT_THICKNESS)
        
        # Frame genişliğinin %95'ini aşarsa yeni satıra geç (web arayüzü için)
        if text_width > frame_width * 0.95:
            if current_line:
                lines.append(current_line)
                current_line = word
            else:
                lines.append(word)
        else:
            current_line = test_line
    
    if current_line:
        lines.append(current_line)
    
    # Metni frame'e yaz (alt kısımdan yukarı doğru)
    for i, line in enumerate(lines):
        line_y = y - (i * BOTTOM_TEXT_LINE_SPACING)
        
        # Metin gölgesi ekle (daha iyi okunabilirlik için)
        shadow_offset = 1
        cv2.putText(frame, line, (x + shadow_offset, line_y + shadow_offset), 
                   BOTTOM_TEXT_FONT, BOTTOM_TEXT_FONT_SCALE, (0, 0, 0), BOTTOM_TEXT_THICKNESS + 1)
        
        # Ana metni yaz
        cv2.putText(frame, line, (x, line_y), 
                   BOTTOM_TEXT_FONT, BOTTOM_TEXT_FONT_SCALE, BOTTOM_TEXT_COLOR, BOTTOM_TEXT_THICKNESS)
    
    return frame

def add_gif_to_frame(frame, frame_index: int, fps: float = 30.0):
    """Frame'e GIF overlay ekle - hız kontrolü ile"""
    global GIF_FRAMES
    
    # GIF overlay'i devre dışı bırakma seçeneği
    if not GIF_ENABLED:
        return frame

    if GIF_FRAMES is None:
        GIF_FRAMES = load_gif_overlay()
    
    if GIF_FRAMES:
        # GIF hızını kontrol et
        # GIF'in bir turu GIF_DURATION saniyede tamamlanacak
        gif_frame_count = len(GIF_FRAMES)
        frames_per_cycle = int(GIF_DURATION * fps)  # 20 saniyede kaç frame
        gif_frame_index = int((frame_index % frames_per_cycle) * gif_frame_count / frames_per_cycle)
        
        return overlay_gif_on_frame(frame, GIF_FRAMES, gif_frame_index, GIF_POSITION, GIF_ALPHA)
    else:
        return frame


def countdown(cap, window_name: str = 'Kayıt'):
    for num in [3, 2, 1]:
        start = time.perf_counter()
        while time.perf_counter() - start < 1.0:
            ok, frame = cap.read()
            if not ok:
                continue
            display = overlay_text(frame, f'{num}')
            cv2.imshow(window_name, display)
            try:
                cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
            except Exception:
                pass
            if cv2.waitKey(1) & 0xFF == ord('q'):
                raise KeyboardInterrupt


def get_ffmpeg_path() -> str | None:
    path = shutil.which('ffmpeg') or shutil.which('ffmpeg.exe')
    if path:
        print(f"FFmpeg bulundu: {path}")
        return path
    try:
        import imageio_ffmpeg  # type: ignore
        p = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"FFmpeg (imageio) bulundu: {p}")
        return p
    except Exception:
        print("FFmpeg bulunamadı.")
        return None


def get_available_audio_devices() -> list[int]:
    """Mevcut ses cihazlarını tespit et"""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        return []
    
    try:
        # FFmpeg ile cihaz listesini al
        result = subprocess.run([
            ffmpeg, '-f', 'avfoundation', '-list_devices', 'true', '-i', ''
        ], capture_output=True, text=True, timeout=10)
        
        audio_devices = []
        lines = result.stderr.split('\n')
        in_audio_section = False
        
        for line in lines:
            if 'AVFoundation audio devices:' in line:
                in_audio_section = True
                continue
            elif 'AVFoundation video devices:' in line:
                in_audio_section = False
                continue
            elif in_audio_section and '[' in line and ']' in line:
                # [AVFoundation indev @ 0x125616c50] [0] Microsoft Teams Audio formatındaki satırları parse et
                try:
                    # İkinci köşeli parantezi bul (cihaz numarası)
                    brackets = []
                    for i, char in enumerate(line):
                        if char == '[':
                            brackets.append(i)
                        elif char == ']':
                            brackets.append(i)
                    
                    # En az 4 karakter olmalı (2 açma, 2 kapama)
                    if len(brackets) >= 4:
                        # İkinci köşeli parantez çiftini al
                        start_bracket = brackets[2]
                        end_bracket = brackets[3]
                        device_index = int(line[start_bracket+1:end_bracket])
                        audio_devices.append(device_index)
                except (ValueError, IndexError):
                    continue
        
        print(f"Tespit edilen ses cihazları: {audio_devices}")
        return audio_devices
        
    except Exception as e:
        print(f"Ses cihazı tespit hatası: {e}")
        return [0, 1, 2]  # Varsayılan cihazları dene


def find_rode_device() -> tuple[int, str] | None:
    """Rode Wireless GO 2 cihazını tespit et, yoksa en iyi mikrofonu bul"""
    try:
        # sounddevice ile cihazları listele
        devices = sd.query_devices()
        
        # Önce Rode cihazlarını ara
        for i, device in enumerate(devices):
            device_name = device['name'].lower()
            if any(keyword in device_name for keyword in ['rode', 'wireless', 'go']):
                print(f"🎤 Rode cihazı bulundu: {device['name']} (ID: {i})")
                return i, device['name']
        
        # Rode bulunamazsa en iyi mikrofonu bul
        print("❌ Rode cihazı bulunamadı, en iyi mikrofon aranıyor...")
        
        # Mikrofonları öncelik sırasına göre ara
        preferred_names = ['efemiir', 'macbook', 'teams', 'mikrofon', 'microphone']
        
        for preferred in preferred_names:
            for i, device in enumerate(devices):
                device_name = device['name'].lower()
                if preferred in device_name and device['max_input_channels'] > 0:
                    print(f"🎤 En iyi mikrofon bulundu: {device['name']} (ID: {i})")
                    return i, device['name']
        
        # Son çare: ilk mikrofonu kullan
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                print(f"🎤 Varsayılan mikrofon: {device['name']} (ID: {i})")
                return i, device['name']
        
        print("❌ Hiçbir mikrofon bulunamadı")
        return None
        
    except Exception as e:
        print(f"Mikrofon tespit hatası: {e}")
        return None


def get_rode_audio_device_index() -> int | None:
    """En iyi mikrofon için FFmpeg cihaz indeksini bul"""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        print("⚠️ FFmpeg bulunamadı, varsayılan cihaz kullanılacak")
        return 0  # Varsayılan cihaz
    
    try:
        # FFmpeg ile cihaz listesini al
        result = subprocess.run([
            ffmpeg, '-f', 'avfoundation', '-list_devices', 'true', '-i', ''
        ], capture_output=True, text=True, timeout=10)
        
        lines = result.stderr.split('\n')
        in_audio_section = False
        audio_devices = []
        
        for line in lines:
            if 'AVFoundation audio devices:' in line:
                in_audio_section = True
                continue
            elif 'AVFoundation video devices:' in line:
                in_audio_section = False
                continue
            elif in_audio_section and '[' in line and ']' in line:
                try:
                    # Cihaz numarasını çıkar
                    brackets = []
                    for i, char in enumerate(line):
                        if char == '[':
                            brackets.append(i)
                        elif char == ']':
                            brackets.append(i)
                    
                    if len(brackets) >= 4:
                        start_bracket = brackets[2]
                        end_bracket = brackets[3]
                        device_index = int(line[start_bracket+1:end_bracket])
                        audio_devices.append((device_index, line))
                except (ValueError, IndexError):
                    continue
        
        # Önce Rode cihazını ara
        for device_index, line in audio_devices:
            if any(keyword in line.lower() for keyword in ['rode', 'wireless', 'go']):
                print(f"🎤 Rode FFmpeg cihaz indeksi: {device_index}")
                return device_index
        
        # Rode bulunamazsa en iyi mikrofonu bul
        print("❌ Rode bulunamadı, en iyi mikrofon aranıyor...")
        preferred_names = ['efemiir', 'macbook', 'teams', 'mikrofon', 'microphone']
        
        for preferred in preferred_names:
            for device_index, line in audio_devices:
                if preferred in line.lower():
                    print(f"🎤 En iyi mikrofon FFmpeg indeksi: {device_index}")
                    return device_index
        
        # Son çare: ilk cihazı kullan
        if audio_devices:
            device_index = audio_devices[0][0]
            print(f"🎤 Varsayılan FFmpeg cihaz indeksi: {device_index}")
            return device_index
        
        print("❌ Hiçbir ses cihazı bulunamadı")
        return None
        
    except Exception as e:
        print(f"FFmpeg cihaz tespit hatası: {e}")
        return 0  # Varsayılan cihaz


def start_camera_preview():
    """Web stream için kamera başlat"""
    global PREVIEW_CAMERA, PREVIEW_STOP_EVENT
    
    # Önce mevcut kamerayı temizle
    if PREVIEW_CAMERA is not None:
        stop_camera_preview()
        time.sleep(0.5)  # Kısa bekleme
    
    try:
        PREVIEW_STOP_EVENT.clear()
        
        # Web stream için kamera instance'ı oluştur
        PREVIEW_CAMERA = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
        
        if not PREVIEW_CAMERA.isOpened():
            print("Web stream kamera açılamadı")
            PREVIEW_CAMERA = None
            return False
        
        # Web stream için orta çözünürlük
        PREVIEW_CAMERA.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        PREVIEW_CAMERA.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        PREVIEW_CAMERA.set(cv2.CAP_PROP_FPS, 30)
        
        # Birkaç frame oku ve at (cache temizleme)
        for _ in range(5):
            ret, frame = PREVIEW_CAMERA.read()
            if not ret:
                break
        
        print("Web stream kamera başlatıldı")
        return True
        
    except Exception as e:
        print(f"Web stream kamera başlatma hatası: {e}")
        PREVIEW_CAMERA = None
        return False


def start_fullscreen_camera():
    """Tam ekran kamera penceresini başlat"""
    global FULLSCREEN_CAMERA, FULLSCREEN_THREAD, FULLSCREEN_STOP_EVENT
    
    # Önce mevcut tam ekran kamerayı temizle
    if FULLSCREEN_CAMERA is not None:
        stop_fullscreen_camera()
        time.sleep(0.5)
    
    try:
        FULLSCREEN_STOP_EVENT.clear()
        
        # Tam ekran için ayrı kamera instance'ı
        FULLSCREEN_CAMERA = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
        
        if not FULLSCREEN_CAMERA.isOpened():
            print("Tam ekran kamera açılamadı")
            FULLSCREEN_CAMERA = None
            return False
        
        # Tam ekran için yüksek çözünürlük
        FULLSCREEN_CAMERA.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        FULLSCREEN_CAMERA.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        FULLSCREEN_CAMERA.set(cv2.CAP_PROP_FPS, 30)
        
        # Birkaç frame oku ve at (cache temizleme)
        for _ in range(5):
            ret, frame = FULLSCREEN_CAMERA.read()
            if not ret:
                break
        
        # Tam ekran kamera penceresi başlat
        FULLSCREEN_THREAD = threading.Thread(target=show_fullscreen_camera, daemon=True)
        FULLSCREEN_THREAD.start()
        # Thread'i global olarak sakla ki temizlenebilsin
        global _fullscreen_thread
        _fullscreen_thread = FULLSCREEN_THREAD
        
        print("Tam ekran kamera penceresi başlatıldı")
        return True
        
    except Exception as e:
        print(f"Tam ekran kamera başlatma hatası: {e}")
        FULLSCREEN_CAMERA = None
        return False


def show_fullscreen_camera():
    """Tam ekran kamera penceresi göster"""
    global FULLSCREEN_CAMERA, FULLSCREEN_STOP_EVENT
    
    window_name = "Kamera - Kayıt Devam Ediyor"
    
    try:
        # Tam ekran pencere oluştur
        cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        
        # Pencereyi en üste getir
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
        
        start_time = time.time()
        
        while not FULLSCREEN_STOP_EVENT.is_set():
            if FULLSCREEN_CAMERA is None:
                break
            
            # Kayıt süresi dolduysa otomatik olarak çık
            elapsed = time.time() - start_time
            if elapsed >= RECORDING_DURATION:
                print(f"📹 Tam ekran kamera {RECORDING_DURATION}s süre doldu, kapatılıyor...")
                break
                
            ret, frame = FULLSCREEN_CAMERA.read()
            if not ret:
                break
            
            # Frame'i tam ekrana uygun boyuta getir
            height, width = frame.shape[:2]
            screen_height, screen_width = 1080, 1920  # Varsayılan ekran boyutu
            
            # Aspect ratio'yu koruyarak resize et
            scale = min(screen_width / width, screen_height / height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            resized_frame = cv2.resize(frame, (new_width, new_height))
            
            # Siyah arka plan oluştur ve frame'i ortala
            black_frame = np.zeros((screen_height, screen_width, 3), dtype=np.uint8)
            y_offset = (screen_height - new_height) // 2
            x_offset = (screen_width - new_width) // 2
            black_frame[y_offset:y_offset+new_height, x_offset:x_offset+new_width] = resized_frame
            
            # Süre bilgisini ekle
            elapsed = int(time.time() - start_time)
            remaining = max(0, RECORDING_DURATION - elapsed)  # Gerçek kayıt süresi
            
            # Metin ekle
            cv2.putText(black_frame, f"Kayit: {elapsed:02d}s / {RECORDING_DURATION}s", 
                       (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 4)
            cv2.putText(black_frame, f"Kalan: {remaining:02d}s", 
                       (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 4)
            cv2.putText(black_frame, "Kayit devam ediyor...", 
                       (50, screen_height - 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
            
            # Alt metin ekle (sadece tam ekran kamera penceresinde)
            black_frame = add_bottom_text_to_frame(black_frame)
            
            cv2.imshow(window_name, black_frame)
            
            # 'q' tuşu ile çıkış
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except Exception as e:
        print(f"Tam ekran kamera hatası: {e}")
    finally:
        # Pencereyi zorla kapat
        try:
            cv2.destroyWindow(window_name)
            cv2.destroyAllWindows()
            print("📹 Tam ekran pencere zorla kapatıldı")
        except Exception as e:
            print(f"Pencere kapatma hatası: {e}")
        
        # Kısa bekleme
        time.sleep(0.1)


def stop_camera_preview():
    """Web stream kamerayı durdur"""
    global PREVIEW_CAMERA, PREVIEW_STOP_EVENT
    
    # Eğer zaten durdurulmuşsa tekrar durdurma
    if PREVIEW_CAMERA is None:
        return
    
    PREVIEW_STOP_EVENT.set()
    
    if PREVIEW_CAMERA is not None:
        try:
            PREVIEW_CAMERA.release()
        except Exception as e:
            print(f"Web stream kamera release hatası: {e}")
        finally:
            PREVIEW_CAMERA = None
    
    # Kısa bekleme - kamera tamamen serbest bırakılsın
    time.sleep(0.2)
    
    print("Web stream kamera durduruldu")


def stop_fullscreen_camera():
    """Tam ekran kamera penceresini durdur"""
    global FULLSCREEN_CAMERA, FULLSCREEN_THREAD, FULLSCREEN_STOP_EVENT, _fullscreen_thread
    
    # Eğer zaten durdurulmuşsa tekrar durdurma
    if FULLSCREEN_CAMERA is None and FULLSCREEN_THREAD is None and _fullscreen_thread is None:
        return
    
    print("📹 Tam ekran kamera penceresi kapatılıyor...")
    
    # Stop event'i set et
    FULLSCREEN_STOP_EVENT.set()
    
    # Kamera'yı kapat
    if FULLSCREEN_CAMERA is not None:
        try:
            FULLSCREEN_CAMERA.release()
            print("📹 Kamera release edildi")
        except Exception as e:
            print(f"Tam ekran kamera release hatası: {e}")
        finally:
            FULLSCREEN_CAMERA = None
    
    # Tüm OpenCV pencerelerini hemen kapat
    try:
        cv2.destroyAllWindows()
        print("📹 OpenCV pencereleri kapatıldı")
    except Exception as e:
        print(f"OpenCV pencere kapatma hatası: {e}")
    
    # Thread'leri temizle
    threads_to_clean = [FULLSCREEN_THREAD, _fullscreen_thread]
    for thread in threads_to_clean:
        if thread is not None and thread.is_alive():
            try:
                print(f"📹 Thread bekleniyor: {thread.name}")
                thread.join(timeout=1)  # 1 saniye bekle
                if thread.is_alive():
                    print(f"⚠️ Thread hala çalışıyor, zorla sonlandırılıyor")
            except Exception as e:
                print(f"Thread join hatası: {e}")
    
    # Thread referanslarını temizle
    FULLSCREEN_THREAD = None
    _fullscreen_thread = None
    
    # Kısa bekleme - kamera tamamen serbest bırakılsın
    time.sleep(0.2)
    
    print("✅ Tam ekran kamera penceresi tamamen durduruldu")


def generate_frames():
    """Kamera frame'lerini generate et"""
    global PREVIEW_CAMERA, PREVIEW_STOP_EVENT
    
    # İlk birkaç frame'i at (cache temizleme)
    for _ in range(3):
        if PREVIEW_CAMERA is not None:
            ret, frame = PREVIEW_CAMERA.read()
            if not ret:
                break
    
    while not PREVIEW_STOP_EVENT.is_set():
        if PREVIEW_CAMERA is None:
            break
            
        try:
            ret, frame = PREVIEW_CAMERA.read()
            if not ret:
                break
            
            
            # Frame'i JPEG'e çevir
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ret:
                continue
            
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            time.sleep(0.033)  # ~30 FPS
            
        except Exception as e:
            print(f"Frame okuma hatası: {e}")
            break


def mux_with_ffmpeg(video_path: str, audio_path: str, output_path: str, audio_tempo: float | None = None) -> bool:
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        return False
    
    # Cızırtı önleyici ayarlar: büyük thread queue, pan + yumuşak resample
    # Dinamik ses zamanlama düzeltmesi (atempo) için filtre zinciri oluştur
    afilters = [
        'highpass=80',
        'lowpass=15000',
        'aresample=async=1000:min_hard_comp=0.100:first_pts=0'
    ]
    if audio_tempo and 0.5 <= audio_tempo <= 2.0 and abs(audio_tempo - 1.0) > 0.01:
        afilters.append(f'atempo={audio_tempo:.4f}')

    cmd = [
        ffmpeg, '-y',
        '-thread_queue_size', '4096', '-i', video_path,
        '-thread_queue_size', '4096', '-i', audio_path,
        '-map', '0:v:0', '-map', '1:a:0',
        # Videoyu CFR 30fps yeniden kodla ve süreyi sabitle
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
        '-fps_mode', 'cfr', '-r', '30',
        # Sesi kodla ve filtreleri uygula
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '1',
        '-af', ','.join(afilters),
        # Çıkış süresini sabitle
        '-t', '20',
        '-movflags', '+faststart',
        output_path
    ]
    
    print("FFmpeg komutu:", ' '.join(cmd))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        print("FFmpeg hata kodu:", proc.returncode)
        try:
            print("FFmpeg stderr:\n", proc.stderr.decode('utf-8', errors='ignore'))
        except Exception:
            pass
        return False
    return True


def transcribe_audio_to_text(wav_path: str, language: str = 'tr-TR') -> str:
    """WAV dosyasını metne çevirir; speech_recognition yoksa kısa uyarı döner."""
    if not os.path.exists(wav_path):
        return ""
    if sr is None:
        print("speech_recognition modülü yok, altyazı metni oluşturulamadı")
        return ""
    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.2)
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio, language=language)
        print(f"📝 STT metni: {text[:120]}{'...' if len(text) > 120 else ''}")
        return text
    except Exception as e:
        print(f"STT hata: {e}")
        return ""


def burn_scrolling_text_band(input_mp4: str, output_mp4: str, text: str,
                             band_height: int = 80, opacity: float = 0.6,
                             font_size: int = 36, scroll_speed_px_s: int = 250,
                             font_path: str | None = None, duration_s: int = 20) -> bool:
    """Altta yarı saydam bant üzerinde sağdan sola kayan metni videoya basar."""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        return False
    if not text:
        # Metin yoksa sadece kopyala
        cmd = [ffmpeg, '-y', '-i', input_mp4, '-c', 'copy', output_mp4]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.returncode == 0

    # Geçici metin dosyası (ASCII yol kullan; /tmp)
    try:
        tmp_txt = os.path.join('/tmp', f"scroll_text_{uuid.uuid4().hex}.txt")
        with open(tmp_txt, 'w', encoding='utf-8') as f:
            f.write(text.replace('\n', ' '))
    except Exception as e:
        print(f"Metin dosyası yazılamadı: {e}")
        return False

    # Opaklık: drawbox alpha 0..1; bant konumu: alt kısım
    # Scroll ifadesi: x = w - mod(t*speed\, text_w + w)
    # text_w için tahmini genişlik yerine drawtext'in internal ölçümü kullanmak için uzun döngü gerektirir; pratikte büyük bir döngü ile mod yapılır.
    # Font: macOS yaygın yolları sırayla dene; path'i drawtext için kaçır
    def _escape_for_drawtext_path(p: str) -> str:
        # ffmpeg drawtext için basit kaçışlar
        return p.replace('\\', r'\\').replace(':', r'\:').replace("'", r"\'").replace(',', r'\,').replace('=', r'\=').replace(' ', r'\ ')

    fontopt = []
    candidate_paths = []
    if font_path:
        candidate_paths.append(font_path)
    # macOS common
    candidate_paths += [
        '/System/Library/Fonts/Supplemental/Arial.ttf',
        '/Library/Fonts/Arial.ttf',
        '/System/Library/Fonts/Supplemental/Helvetica.ttf',
        '/Library/Fonts/Helvetica.ttf',
        '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
    ]
    chosen_font = None
    for p in candidate_paths:
        if p and os.path.exists(p):
            chosen_font = p
            break
    if chosen_font:
        fontopt = [':fontfile=' + _escape_for_drawtext_path(chosen_font)]
        print(f"drawtext fontfile kullanılıyor: {chosen_font}")
    else:
        print("drawtext için özel font bulunamadı; sistem varsayılanını deneyecek (fontconfig gerekebilir)")

    # Alttan kayan metin (siyah band ile) - yazılar bandın içinden kayıyor
    vf = (
        f"drawbox=x=0:y=640:w=1280:h={band_height}:color=black@{opacity}:t=fill,"
        f"drawtext=textfile='{tmp_txt}':fontcolor=white:fontsize={font_size}"
        + (''.join(fontopt)) +
        f":x=1280-t*{scroll_speed_px_s}:y=670"
    )

    cmd = [
        ffmpeg, '-y',
        '-i', input_mp4,
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
        '-fps_mode', 'cfr', '-r', '30',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '1',
        '-movflags', '+faststart',
        output_mp4
    ]
    print('FFmpeg (scroll band) komutu:', ' '.join(cmd))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        try:
            print(proc.stderr.decode('utf-8', errors='ignore')[:2000])
        except Exception:
            pass
        try:
            if os.path.exists(tmp_txt):
                os.remove(tmp_txt)
        except Exception:
            pass
        return False
    try:
        if os.path.exists(tmp_txt):
            os.remove(tmp_txt)
    except Exception:
        pass
    return True

def ses_kaydet(sure, dosya_adi, device_index=None):
    """Rode mikrofon ile kaliteli ses kaydı yapar - cızırtı önleyici ayarlar"""
    try:
        # SoundDevice ayarlarını optimize et (cızırtı önleyici)
        sd.default.latency = ('low', 'low')  # Düşük gecikme
        sd.default.blocksize = 1024  # Sabit blok boyutu
        
        # Rode mikrofon için optimize edilmiş ayarlar
        sample_rate = 48000  # Rode için 48kHz (doğal)
        channels = 1  # Mono kayıt (Rode tek kapsül için daha temiz)
        
        print(f"🎤 Rode mikrofon ile ses kaydı başlıyor... ({channels} kanal, {sample_rate}Hz)")
        
        # Rode cihazını kullan, yoksa varsayılan cihazı kullan
        if device_index is None:
            rode_device = find_rode_device()
            if rode_device:
                device_index = rode_device[0]
                print(f"🎤 Rode cihazı kullanılıyor: {rode_device[1]}")
            else:
                print("⚠️ Rode cihazı bulunamadı, varsayılan cihaz kullanılıyor")
        
        # Kaliteli ses kaydı (clipping önleyici)
        try:
            audio_data = sd.rec(int(sure * sample_rate), 
                               samplerate=sample_rate, 
                               channels=channels, 
                               dtype='float32',  # Yüksek kalite
                               device=device_index)
            
            # Kayıt bitene kadar bekle
            sd.wait()
        except Exception as e:
            print(f"❌ Rode ses kaydı hatası: {e}")
            print("🔄 Varsayılan ayarlarla tekrar deneniyor...")
            try:
                # Varsayılan cihaz ile tekrar dene
                audio_data = sd.rec(int(sure * sample_rate), 
                                   samplerate=sample_rate, 
                                   channels=channels, 
                                   dtype='float32')
                sd.wait()
            except Exception as e2:
                print(f"❌ Varsayılan ses kaydı da başarısız: {e2}")
                return None
        
        # Ses seviyesini kontrol et ve artır
        max_amplitude = np.max(np.abs(audio_data))
        print(f"🎤 Maksimum ses genliği: {max_amplitude:.6f}")
        
        if max_amplitude < 0.1:  # Düşük seviye
            gain = 0.1 / max_amplitude if max_amplitude > 0 else 1000
            gain = min(gain, 1000)  # Maksimum 1000x yükselt
            print(f"🔊 Ses seviyesi düşük, {gain:.1f}x yükseltiliyor...")
            audio_data = audio_data * gain
            # Clipping kontrolü
            audio_data = np.clip(audio_data, -1.0, 1.0)
        
        # WAV dosyası olarak kaydet (24-bit kalite)
        wav_dosya = dosya_adi.replace('.mp4', '.wav')
        sf.write(wav_dosya, audio_data, sample_rate, subtype='PCM_24')
        
        print(f"✅ Rode ses kaydı tamamlandı: {wav_dosya}")
        return wav_dosya
        
    except Exception as e:
        print(f"❌ Rode ses kaydı hatası: {e}")
        # Hata durumunda varsayılan ayarlarla dene
        try:
            print("🔄 Varsayılan ayarlarla tekrar deneniyor...")
            sample_rate = 44100
            channels = 1
            
            audio_data = sd.rec(int(sure * sample_rate), 
                               samplerate=sample_rate, 
                               channels=channels, 
                               dtype='float32',
                               device=None)
            
            sd.wait()
            
            # Ses seviyesini kontrol et ve artır
            max_amplitude = np.max(np.abs(audio_data))
            print(f"🎤 Maksimum ses genliği: {max_amplitude:.6f}")
            
            if max_amplitude < 0.1:  # Düşük seviye
                gain = 0.1 / max_amplitude if max_amplitude > 0 else 1000
                gain = min(gain, 1000)  # Maksimum 1000x yükselt
                print(f"🔊 Ses seviyesi düşük, {gain:.1f}x yükseltiliyor...")
                audio_data = audio_data * gain
                # Clipping kontrolü
                audio_data = np.clip(audio_data, -1.0, 1.0)
            
            wav_dosya = dosya_adi.replace('.mp4', '.wav')
            sf.write(wav_dosya, audio_data, sample_rate)
            
            print(f"✅ Varsayılan ses kaydı tamamlandı: {wav_dosya}")
            return wav_dosya
            
        except Exception as e2:
            print(f"❌ Varsayılan ses kaydı da başarısız: {e2}")
            return None


def video_ses_birlestir(video_dosya, ses_dosya, cikti_dosya):
    """Video ve ses dosyalarını birleştirir - cızırtı önleyici ayarlar"""
    try:
        # FFmpeg yolunu bul
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        
        # FFmpeg ile birleştirme (cızırtı önleyici ayarlar)
        cmd = [
            ffmpeg_path, '-y',
            '-thread_queue_size', '4096', '-i', video_dosya,
            '-thread_queue_size', '4096', '-i', ses_dosya,
            '-map', '0:v:0', '-map', '1:a:0',
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-ar', '48000', '-ac', '1',
            '-af', 'aresample=async=1000:min_hard_comp=0.100:first_pts=0,highpass=80,lowpass=15000',
            '-shortest',  # Kısa olanı al (senkronizasyon için)
            '-movflags', '+faststart',
            cikti_dosya
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"Video ve ses birleştirildi: {cikti_dosya}")
            return True
        else:
            print(f"Birleştirme hatası: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"Birleştirme hatası: {e}")
        return False

#video kayıt saniye - YENİ YAKLAŞIM (macos_10s_video.py tabanlı)
def record_with_opencv_sounddevice_new(output_path: str, device_index: int = 0, duration_sec: int = 20, with_audio: bool = True):
    """OpenCV + SoundDevice ile kayıt (macos_10s_video.py yaklaşımı)"""
    import threading
    import time
    
    print(f"🎥 OpenCV + SoundDevice ile kayıt başlıyor...")
    print(f"📁 Çıktı: {output_path}")
    print(f"⏱️  Süre: {duration_sec} saniye")
    print(f"🎤 Ses: {'Evet' if with_audio else 'Hayır'}")
    
    # Çıktı klasörünü oluştur
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Geçici dosya adları
    video_file = output_path.replace('.mp4', '_temp_video.mp4')
    audio_file = output_path.replace('.mp4', '_temp_audio.wav')
    
    try:
        # 1. Kamera aç
        print("📹 Kamera açılıyor...")
        cap = cv2.VideoCapture(device_index, cv2.CAP_AVFOUNDATION)
        
        if not cap.isOpened():
            print("❌ Hata: Kamera açılamadı!")
            return False
        
        # Kamera ayarları
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        print("✅ Kamera başarıyla açıldı")
        
        # 2. Video yazıcı oluştur
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(video_file, fourcc, 30, (1280, 720))
        
        if not out.isOpened():
            print("❌ Video yazıcı açılamadı!")
            cap.release()
            return False
        
        # 3. Geri sayım (kayıt süresine dahil değil)
        print("Geri sayım başlıyor...")
        for i in range(3, 0, -1):
            print(f"{i}...")
            time.sleep(1)
        print("🎬 Kayıt başladı!")
        
        # 4. Ses ve videoyu AYNI ANDA başlat
        audio_thread = None
        if with_audio:
            print("🎤 Ses kaydı başlatılıyor...")
            rode_device = find_rode_device()
            device_index = rode_device[0] if rode_device else None
            audio_thread = threading.Thread(target=ses_kaydet, args=(duration_sec, audio_file, device_index), daemon=True)
            audio_thread.start()
        
        # 6. Video kayıt döngüsü (geri sayım + 2 saniye sonrası başlar)
        print("🎬 Video kaydı başlıyor...")
        start_time = time.time()
        frame_count = 0
        target_frames = duration_sec * 30  # 20 saniye = 600 frame (30 FPS)
        
        while frame_count < target_frames:
                
            # Frame oku
            ret, frame = cap.read()
            
            if not ret:
                print("❌ Hata: Frame okunamadı!")
                break
            
            # Frame'i yeniden boyutlandır
            frame = cv2.resize(frame, (1280, 720))
            
            # GIF overlay ekle
            frame = add_gif_to_frame(frame, frame_count, 30.0)
            
            # Fligram overlay ekle
            frame = add_fligram_to_frame(frame)
            
            # Frame'i videoya yaz
            out.write(frame)
            
            frame_count += 1
            elapsed = time.time() - start_time
            remaining = duration_sec - elapsed
            
            # İlerleme göster (her saniye)
            if frame_count % 30 == 0:
                print(f"📹 Kayıt: {elapsed:.1f}s / {duration_sec}s (Kalan: {remaining:.1f}s)")
            
            # Frame sayısına ulaştıysa döngüden çık
            if frame_count >= target_frames:
                print(f"✅ Hedef frame sayısına ulaşıldı: {frame_count}/{target_frames}")
                break
        
        # 5. Video kaydını bitir - hemen kapat
        try:
            out.release()
            print("✅ Video kaydı tamamlandı")
        except Exception as e:
            print(f"Video writer kapatma hatası: {e}")
        
        # Kamera hemen kapat
        try:
            cap.release()
            cv2.destroyAllWindows()
            print("📹 Kamera hemen kapatıldı")
        except Exception as e:
            print(f"Kamera kapatma hatası: {e}")
        
        # Tam ekran kamera penceresini de hemen kapat
        try:
            stop_fullscreen_camera()
            print("📹 Tam ekran kamera penceresi hemen kapatıldı")
        except Exception as e:
            print(f"Tam ekran kamera kapatma hatası: {e}")
        
        # 6. Ses kaydının bitmesini bekle
        if with_audio and audio_thread:
            print("🎤 Ses kaydı bekleniyor...")
            audio_thread.join(timeout=10)
        
        # 7. Video ve sesi birleştir
        if with_audio and os.path.exists(audio_file):
            print("🔗 Video ve ses birleştiriliyor...")
            # Gerçek kayıt süresini ölç ve ses temposunu videoya uydur
            actual_duration = max(0.1, time.time() - start_time)
            tempo_factor = actual_duration / float(duration_sec)
            if 0.5 <= tempo_factor <= 2.0 and abs(tempo_factor - 1.0) > 0.01:
                print(f"⏱️  Gerçek süre: {actual_duration:.2f}s, Hedef: {duration_sec}s, atempo={tempo_factor:.4f}")
            else:
                print(f"⏱️  Gerçek süre: {actual_duration:.2f}s, Hedef: {duration_sec}s, atempo uygulanmayacak")
            
            # 7a. Önce mux -> muxed_path
            muxed_path = output_path
            if mux_with_ffmpeg(video_file, audio_file, muxed_path, tempo_factor):
                # 7b. STT: WAV silmeden önce metni çıkar
                try:
                    stt_text = ""
                    if os.path.exists(audio_file):
                        stt_text = transcribe_audio_to_text(audio_file)
                    elif os.path.exists(muxed_path.replace('.mp4', '.wav')):
                        stt_text = transcribe_audio_to_text(muxed_path.replace('.mp4', '.wav'))
                except Exception:
                    stt_text = ""

                # Geçici dosyaları sil (video_file her durumda silinir, audio_file STT sonrası silinir)
                try:
                    if os.path.exists(video_file):
                        os.remove(video_file)
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
                    print("🧹 Geçici dosyalar temizlendi")
                except Exception as e:
                    print(f"⚠️ Geçici dosya temizleme hatası: {e}")

                # Kayan bant sadece metin varsa basılır
                if stt_text:
                    banded_path = os.path.splitext(muxed_path)[0] + '.band.mp4'
                    font_candidate = '/Library/Fonts/Arial.ttf'
                    ok_band = burn_scrolling_text_band(
                        muxed_path, banded_path, stt_text,
                        band_height=80, opacity=0.6, font_size=36,
                        scroll_speed_px_s=250, font_path=font_candidate if os.path.exists(font_candidate) else None,
                        duration_s=duration_sec
                    )
                    if ok_band:
                        try:
                            os.replace(banded_path, muxed_path)
                        except Exception as rep_err:
                            print(f"Bantlı videoyu yerine koyma hatası: {rep_err}")
                    else:
                        print("Kayan bant eklenemedi, orijinal mux dosyası kullanılacak.")

                print(f"✅ Kayıt tamamlandı: {muxed_path}")
                return True
            else:
                print("❌ Video-ses birleştirme başarısız")
                # Video dosyasını final konuma taşı
                try:
                    os.rename(video_file, output_path)
                    print(f"📹 Video kaydı (ses yok): {output_path}")
                    return True
                except Exception as e:
                    print(f"❌ Video dosyası taşıma hatası: {e}")
                    return False
        else:
            # Sadece video
            try:
                os.rename(video_file, output_path)
                print(f"📹 Video kaydı (ses yok): {output_path}")
                return True
            except Exception as e:
                print(f"❌ Video dosyası taşıma hatası: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Kayıt hatası: {e}")
        return False
    finally:
        # Kaynakları temizle
        try:
            if 'cap' in locals() and cap is not None:
                cap.release()
            if 'out' in locals() and out is not None:
                out.release()
            cv2.destroyAllWindows()
        except Exception as cleanup_error:
            print(f"Cleanup error: {cleanup_error}")

#video kayıt saniye - ESKİ YAKLAŞIM (FFmpeg)
def record_with_opencv_sounddevice(output_path: str, device_index: int = 0, duration_sec: int = 20, with_audio: bool = True):
    """FFmpeg ile direkt kayıt (macOS için daha güvenli) - kamera önizlemesi ile"""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg bulunamadı")
    
    ensure_output_dir(output_path)
    
    # Tam ekran kamera penceresi zaten açık, sadece kayıt yap
    
    # Geri sayım göster (kayıt süresine dahil değil)
    print("Geri sayım başlıyor...")
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    print("🎬 Kayıt başladı!")
    
    # Kayıt başladı sinyali gönder (job status güncelle)
    # Bu sinyal frontend'e kayıt başladığını bildirir
    
    # macOS için FFmpeg komutu - Cızırtı önleyici ayarlar
    import platform
    if platform.system() == "Darwin":
        # Temel giriş ayarları (cızırtı önleyici)
        base_in = [
            ffmpeg, '-y',
            '-thread_queue_size', '8192',  # Çok büyük giriş kuyruğu
            '-use_wallclock_as_timestamps', '1',  # Gerçek saat timestamp
            '-f', 'avfoundation',
            '-video_size', '1280x720',
            '-framerate', '30',
        ]
        
        if with_audio:
            # Önce Rode cihazını ara
            rode_audio_device = get_rode_audio_device_index()
            
            if rode_audio_device is not None:
                print(f"🎤 Rode mikrofon FFmpeg ile kullanılıyor (cihaz: {rode_audio_device})")
                av_in = base_in + ['-i', f'{device_index}:{rode_audio_device}']
            else:
                # Rode bulunamazsa mevcut ses cihazlarını tespit et
                audio_devices = get_available_audio_devices()
                
                if not audio_devices:
                    print("⚠️ Ses cihazı bulunamadı, sadece video kaydı yapılıyor...")
                    av_in = base_in + ['-i', str(device_index)]
                    with_audio = False  # Ses kaydını devre dışı bırak
                else:
                    # Mevcut ses cihazlarını dene (öncelik sırası: 2, 1, 0)
                    audio_device = None
                    for preferred_device in [2, 1, 0]:
                        if preferred_device in audio_devices:
                            audio_device = preferred_device
                            break
                    
                    if audio_device is None:
                        audio_device = audio_devices[0]  # İlk mevcut cihazı kullan
                    
                    print(f"⚠️ Rode bulunamadı, varsayılan ses cihazı {audio_device} kullanılıyor...")
                    av_in = base_in + ['-i', f'{device_index}:{audio_device}']
        else:
            av_in = base_in + ['-i', str(device_index)]
        
        # Video kodlama ayarları
        cmd = av_in + [
            '-t', str(duration_sec),
            # **Yazılım** H.264 (donanım kodlama sorun yaratıyor)
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-pix_fmt', 'yuv420p',
        ]
        
        # Ses ayarları (cızırtı önleyici) - Donanım kodlama + yumuşak resample
        if with_audio:
            cmd += [
                '-c:a', 'aac',
                '-b:a', '192k',
                '-ar', '48000',
                '-ac', '1',  # Mono kayıt
                # ÖNEMLİ: Yumuşak aresample (pan filtresi kaldırıldı)
                '-af', 'aresample=async=1000:min_hard_comp=0.100:first_pts=0,highpass=f=80,lowpass=f=15000'
            ]
        
        cmd += [output_path]
    else:
        # Linux için
        video_device = f"/dev/video{device_index}"
        if with_audio:
            cmd = [ffmpeg, '-y', '-f', 'v4l2', '-i', video_device, '-f', 'alsa', '-i', 'default', '-t', str(duration_sec), output_path]
        else:
            cmd = [ffmpeg, '-y', '-f', 'v4l2', '-i', video_device, '-t', str(duration_sec), output_path]
    
    print(f"FFmpeg kayıt komutu: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration_sec + 30)
        
        # Tam ekran kamera penceresi devam ediyor
        
        if result.returncode == 0:
            print(f"FFmpeg kayıt tamamlandı: {output_path}")
            return True
        else:
            print(f"FFmpeg hatası: {result.stderr}")
            
            # Ses ile kayıt başarısız olduysa, sadece video ile dene
            if with_audio and platform.system() == "Darwin":
                print("Ses ile kayıt başarısız, sadece video ile tekrar deneniyor...")
                video_only_cmd = [
                    ffmpeg, '-y', 
                    '-f', 'avfoundation', 
                    '-video_size', '1280x720',
                    '-framerate', '30',
                    '-i', str(device_index), 
                    '-t', str(duration_sec),
                    '-c:v', 'libx264',
                    '-preset', 'fast',
                    output_path
                ]
                
                print(f"Video-only FFmpeg komutu: {' '.join(video_only_cmd)}")
                video_result = subprocess.run(video_only_cmd, capture_output=True, text=True, timeout=duration_sec + 30)
                
                if video_result.returncode == 0:
                    print(f"Video-only kayıt tamamlandı: {output_path}")
                    return True
                else:
                    print(f"Video-only FFmpeg hatası: {video_result.stderr}")
                    return False
            else:
                return False
                
    except subprocess.TimeoutExpired:
        print("FFmpeg zaman aşımı")
        return False
    except Exception as e:
        print(f"FFmpeg kayıt hatası: {e}")
        return False


def record_with_opencv_and_audio(output_path: str, device_index: int = 0, duration_sec: int = 20):
    """OpenCV ile video + sounddevice ile ses kaydı"""
    print('OpenCV + sounddevice ile kayıt yapılıyor...')
    
    # Kamera aç
    cap = select_camera(device_index)
    
    try:
        # Video ayarları
        width = 1280
        height = 720
        fps = 30
        
        # Çözünürlük ayarla
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        
        # Dosya adları
        video_file = output_path.replace('.mp4', '_video.mp4')
        final_file = output_path
        
        # Video yazıcı oluştur
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(video_file, fourcc, fps, (width, height))
        
        print(f"Kayıt başlıyor: {final_file}")
        print(f"{duration_sec} saniye boyunca video ve ses kaydı yapılacak...")
        
        # Geri sayım (kayıt süresine dahil değil)
        print("Geri sayım başlıyor...")
        for i in range(3, 0, -1):
            print(f"{i}...")
            time.sleep(1)
        print("🎬 Kayıt başladı!")
        
        # Rode mikrofon ile ses kaydını başlat (ayrı thread'de)
        rode_device = find_rode_device()
        device_index = rode_device[0] if rode_device else None
        ses_thread = threading.Thread(target=ses_kaydet, args=(duration_sec, video_file, device_index), daemon=True)
        ses_thread.start()
        
        # Video kayıt döngüsü (geri sayım sonrası başlar)
        baslangic_zamani = time.time()
        
        frame_count = 0
        while True:
            # Frame oku
            ret, frame = cap.read()
            
            if not ret:
                print("Hata: Frame okunamadı!")
                break
            
            # GIF overlay ekle
            frame = add_gif_to_frame(frame, frame_count, 30.0)
            
            # Fligram overlay ekle
            frame = add_fligram_to_frame(frame)
            
            # Frame'i videoya yaz
            out.write(frame)
            
            # Frame sayacını artır
            frame_count += 1
            
            # Ekranda göster
            cv2.imshow('Kamera Kayıt', frame)
            
            # Geçen süreyi hesapla
            gecen_sure = time.time() - baslangic_zamani
            kalan_sure = duration_sec - gecen_sure
            
            # Süre bilgisini ekrana yaz
            cv2.putText(frame, f"Kayit: {gecen_sure:.1f}s / {duration_sec}s", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, f"Kalan: {kalan_sure:.1f}s", 
                       (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Süre doldu mu kontrol et
            if gecen_sure >= duration_sec:
                break
            
            # 'q' tuşu ile çıkış
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        # Temizlik
        cap.release()
        out.release()
        cv2.destroyAllWindows()
        
        print("Video kaydı tamamlandı, ses kaydı bekleniyor...")
        
        # Ses kaydının bitmesini bekle
        ses_thread.join()
        
        # Ses dosyasını kontrol et
        ses_dosya = video_file.replace('.mp4', '.wav')
        
        if os.path.exists(ses_dosya):
            print("Video ve ses birleştiriliyor...")
            
            # Video ve sesi birleştir
            if video_ses_birlestir(video_file, ses_dosya, final_file):
                # Geçici dosyaları sil
                try:
                    os.remove(video_file)
                    os.remove(ses_dosya)
                    print("Geçici dosyalar temizlendi.")
                except:
                    pass
                
                print(f'Kayıt tamamlandı: {final_file}')
                return True
            else:
                print(f"Video kaydı (ses yok): {video_file}")
                return False
        else:
            print(f"Video kaydı (ses yok): {video_file}")
            return False
            
    except Exception as e:
        print(f"Kayıt hatası: {e}")
        return False
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception as e:
                print(f"Kamera kapatma hatası: {e}")
        try:
            cv2.destroyAllWindows()
        except Exception as e:
            print(f"Pencere kapatma hatası: {e}")


def record_20_seconds(output_path: str, device_index: int = 0, duration_sec: int = 20, with_audio: bool = True):
    import platform
    
    # macOS'ta yeni yaklaşım kullan (OpenCV + SoundDevice)
    if platform.system() == "Darwin":
        print('macOS tespit edildi, OpenCV + SoundDevice ile kayıt yapılıyor...')
        success = record_with_opencv_sounddevice_new(output_path, device_index, duration_sec, with_audio)
        if success:
            print(f'Kayıt tamamlandı: {output_path}')
            return
        else:
            raise RuntimeError("OpenCV + SoundDevice kayıt başarısız")
    
    print('OpenCV ile kayıt yapılıyor...')
    cap = None
    try:
        cap = select_camera(device_index)
        
        # Kamera ayarlarını güvenli şekilde yap
        try:
            set_resolution(cap, 1280, 720)
        except Exception as e:
            print(f"Çözünürlük ayarlanamadı: {e}")
        
        # Test frame'i güvenli şekilde oku
        max_retries = 5
        test_frame = None
        for attempt in range(max_retries):
            try:
                ok, test_frame = cap.read()
                if ok and test_frame is not None:
                    break
                time.sleep(0.1)
            except Exception as e:
                print(f"Frame okuma denemesi {attempt + 1} başarısız: {e}")
                if attempt == max_retries - 1:
                    raise RuntimeError('Kameradan görüntü alınamadı.')
                time.sleep(0.2)
        
        if test_frame is None:
            raise RuntimeError('Kameradan görüntü alınamadı.')
            
        height, width = test_frame.shape[:2]
        fps = estimate_fps(cap, probe_seconds=1.0)  # Daha kısa süre
        print(f'Kameradan ölçülen FPS: {fps:.2f}')

        # Yazıcıyı oluştur
        if with_audio:
            temp_video = os.path.splitext(output_path)[0] + '_video.mp4'
            writer, temp_video = create_writer(temp_video, fps, (width, height))
        else:
            writer, _ = create_writer(output_path, fps, (width, height))

        print('Geri sayım başlıyor: 3, 2, 1...')
        countdown(cap)

        print(f'Kayıt başladı. {duration_sec} saniye... (erken bitirmek için pencerede q)')
        window = 'Kayıt'
        frames_to_write = int(round(fps * duration_sec))
        start = time.perf_counter()

        # Rode mikrofon ile ses kaydını başlat (cızırtı önleyici ayarlar)
        if with_audio:
            # SoundDevice ayarlarını optimize et
            sd.default.latency = ('low', 'low')
            sd.default.blocksize = 1024
            
            # Rode cihazını tespit et
            rode_device = find_rode_device()
            device_index = rode_device[0] if rode_device else None
            
            if rode_device:
                sample_rate = 48000  # Rode için 48kHz (doğal)
                channels = 1  # Mono kayıt (daha temiz, faz sorunları yok)
                print(f"🎤 Rode mikrofon ile ses kaydı aktif: {channels} kanal, {sample_rate}Hz, {duration_sec}s")
            else:
                sample_rate = 44100  # Varsayılan
                channels = 1  # Mono
                print(f"⚠️ Rode bulunamadı, varsayılan ses kaydı: {channels} kanal, {sample_rate}Hz, {duration_sec}s")
            
            num_audio_samples = int(duration_sec * sample_rate)
            audio_frames = sd.rec(num_audio_samples, 
                                samplerate=sample_rate, 
                                channels=channels, 
                                dtype='float32',  # Yüksek kalite
                                device=device_index)
        else:
            print("Ses kaydı pasif.")

        for i in range(frames_to_write):
            try:
                target_t = start + i / fps
                while True:
                    now = time.perf_counter()
                    remaining = target_t - now
                    if remaining <= 0:
                        break
                    time.sleep(min(remaining, 0.01))  # Daha uzun gecikme

                # Frame'i güvenli şekilde oku
                frame = test_frame  # Varsayılan frame
                try:
                    ok, new_frame = cap.read()
                    if ok and new_frame is not None:
                        frame = new_frame
                except Exception as e:
                    print(f"Frame okuma hatası: {e}")
                    # Test frame'i kullan
                
                # GIF overlay ekle
                frame = add_gif_to_frame(frame, i, fps)
                
                # Fligram overlay ekle
                frame = add_fligram_to_frame(frame)
                
                # Frame yazma
                try:
                    writer.write(frame)
                except Exception as e:
                    print(f"Frame yazma hatası: {e}")
                    # Devam et

                # Görüntü gösterme (opsiyonel)
                elapsed = int(now - start) if 'now' in locals() else int(time.perf_counter() - start)
                if i % 5 == 0:  # Her 5 frame'de bir göster
                    try:
                        display = overlay_text(frame, f'Recording {min(elapsed, duration_sec):02d}/{duration_sec}s')
                        cv2.imshow(window, display)
                        try:
                            cv2.setWindowProperty(window, cv2.WND_PROP_TOPMOST, 1)
                        except Exception:
                            pass
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break
                    except Exception as e:
                        # Görüntü gösterme hatası önemli değil
                        pass
                        
            except Exception as e:
                print(f"Kayıt döngüsü hatası: {e}")
                # Devam et

        writer.release()
        if with_audio:
            sd.wait()
            wav_path = os.path.splitext(output_path)[0] + '.wav'
            
            # Rode cihazı kullanıldıysa yüksek kalite kaydet (cızırtı önleyici)
            rode_device = find_rode_device()
            if rode_device:
                sf.write(wav_path, audio_frames, 48000, subtype='PCM_24')  # 24-bit kalite
                print('🎤 Rode ses dosyası kaydedildi (24-bit, 48kHz, mono)')
            else:
                sf.write(wav_path, audio_frames, 44100)  # Varsayılan kalite
                print('⚠️ Varsayılan ses dosyası kaydedildi (44.1kHz, mono)')
            
            print('Ses ve videoyu birleştiriliyor...')
            ok_mux = mux_with_ffmpeg(temp_video, wav_path, output_path)
            if not ok_mux:
                print('⚠️ ffmpeg bulunamadı veya birleştirme başarısız. Sadece görüntü dosyası hazırlandı.')
                print(f'Video: {temp_video}\nSes (WAV): {wav_path}')
            else:
                print(f'✅ Kayıt tamamlandı: {output_path}')
                try:
                    os.remove(temp_video)
                    os.remove(wav_path)
                except Exception:
                    pass
        else:
            print(f'Kayıt tamamlandı: {output_path}')
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception as e:
                print(f"Kamera kapatma hatası: {e}")
        try:
            cv2.destroyAllWindows()
        except Exception as e:
            print(f"Pencere kapatma hatası: {e}")


def _upload_to_fileio(file_path: str) -> str:
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, 'video/mp4')}
        resp = requests.post('https://file.io', files=files, data={'expires': '1w'})
    data = resp.json()
    if not data.get('success'):
        raise RuntimeError(f'file.io yükleme başarısız: {json.dumps(data)[:200]}')
    link = data.get('link') or data.get('url')
    if not link:
        raise RuntimeError('file.io link döndürmedi')
    return link


def _upload_to_catbox(file_path: str, timeout: float | None = 30.0) -> str:
    with open(file_path, 'rb') as f:
        files = {'fileToUpload': (os.path.basename(file_path), f, 'video/mp4')}
        data = {'reqtype': 'fileupload'}
        resp = requests.post('https://catbox.moe/user/api.php', files=files, data=data, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f'catbox.moe yükleme başarısız: {resp.status_code} {resp.text[:200]}')
    text = resp.text.strip()
    if text.lower().startswith('error'):
        raise RuntimeError(f'catbox.moe hata: {text}')
    return text


def _upload_to_catbox_with_retry(file_path: str, attempts: int = 5, base_backoff: float = 2.0) -> str:
    last_err: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            timeout = 30.0 if i <= 2 else 60.0
            print(f"catbox.moe yükleme denemesi {i}/{attempts} (timeout={timeout}s)...")
            url = _upload_to_catbox(file_path, timeout=timeout)
            return url
        except Exception as e:
            last_err = e
            if i == attempts:
                break
            sleep_s = base_backoff * (2 ** (i - 1))
            sleep_s *= (1.0 + random.random() * 0.3)
            print(f"catbox hata: {e}. {sleep_s:.1f}s sonra tekrar denenecek...")
            time.sleep(sleep_s)
    raise RuntimeError(f"catbox.moe yükleme başarısız (tüm denemeler tükendi): {last_err}")


def _download_file(url: str, out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(out_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)


def _create_translation(video_url: str, title: str, output_language: str, api_key: str, with_captions: bool = True) -> str:
    url = 'https://api.heygen.com/v2/video_translate'
    headers = {'accept': 'application/json', 'content-type': 'application/json', 'x-api-key': api_key}
    
    # Altyazı ile çeviri payload'ı
    payload = {
        'video_url': video_url, 
        'title': title, 
        'output_language': output_language,
        'captions': with_captions  # Altyazı ekleme
    }
    
    resp = requests.post(url, headers=headers, data=json.dumps(payload))
    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(f'create_translation hata: {resp.status_code} {resp.text[:200]}')
    data = resp.json()
    vt_id = data.get('data', {}).get('video_translate_id') or data.get('video_translate_id')
    if not vt_id:
        raise RuntimeError(f'video_translate_id bulunamadı: {json.dumps(data)[:200]}')
    return vt_id


def _get_status(video_translate_id: str, api_key: str) -> dict:
    headers = {'accept': 'application/json', 'x-api-key': api_key}
    candidates = [
        f'https://api.heygen.com/v2/video_translate/{video_translate_id}/status',
        f'https://api.heygen.com/v2/video_translate/{video_translate_id}',
    ]
    for url in candidates:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            try:
                return resp.json().get('data') or resp.json()
            except Exception:
                pass
    return {'status': 'unknown'}


def _get_caption_url(video_translate_id: str, api_key: str) -> str | None:
    """Altyazı dosyasının URL'sini al (VTT formatında)"""
    headers = {'accept': 'application/json', 'x-api-key': api_key}
    url = f'https://api.heygen.com/v2/video_translate/caption?video_translate_id={video_translate_id}&caption_type=vtt'
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            caption_url = data.get('caption_url') or data.get('url')
            if caption_url:
                print(f'📝 Altyazı URL bulundu: {caption_url}')
                return caption_url
        else:
            print(f'⚠️ Altyazı URL alınamadı: {resp.status_code} {resp.text[:200]}')
    except Exception as e:
        print(f'⚠️ Altyazı URL alma hatası: {e}')
    
    return None


def translate_with_heygen(video_path: str, safe_name: str, safe_lang: str, translation_id: str = None, recipient_email: str | None = None) -> None:
    # Dil kodlarını Heygen API formatına çevir
    language_map = {
        'tr': 'Turkish',
        'en': 'English', 
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ru': 'Russian',
        'ja': 'Japanese',
        'ko': 'Korean',
        'zh': 'Chinese',
        'ar': 'Arabic'
    }
    
    # Geçersiz/boş/Unknown ise English'e düş
    invalid_langs = {"unknown", "auto", "random", ""}
    if not safe_lang or safe_lang.lower() in invalid_langs:
        safe_lang = 'English'
    output_language = language_map.get(safe_lang.lower(), safe_lang)
    api_key = os.getenv('HEYGEN_API_KEY') or HEYGEN_API_KEY_FALLBACK
    if not api_key:
        print('HEYGEN_API_KEY bulunamadı. Çeviri atlandı.')
        if translation_id:
            TRANSLATION_JOBS[translation_id] = {"status": "error", "message": "API key bulunamadı"}
        return
    
    # Çeviri durumunu güncelle
    if translation_id:
        TRANSLATION_JOBS[translation_id] = {"status": "uploading", "message": "Video yükleniyor..."}
    
    # Yalnızca catbox.moe ile yükle (yeniden denemeli)
    print('Video yükleniyor (catbox.moe)...')
    try:
        public_url = _upload_to_catbox_with_retry(video_path)
        print(f'catbox.moe: {public_url}')
    except Exception as e1:
        print(f'catbox hata: {e1}')
        if translation_id:
            TRANSLATION_JOBS[translation_id] = {"status": "error", "message": f"Video yükleme hatası: {e1}"}
        return

    title = f'{safe_name}.mp4'
    print(f'Heygen çeviri talebi oluşturuluyor... (Dil: {output_language})')
    
    if translation_id:
        TRANSLATION_JOBS[translation_id] = {"status": "translating", "message": "Çeviri başlatılıyor..."}
    
    vt_id = _create_translation(public_url, title, output_language, api_key, with_captions=True)
    print(f'video_translate_id: {vt_id}')
    print(f'📝 Altyazı ile çeviri başlatıldı (Dil: {output_language})')

    start_t = time.time()
    deadline = 60 * 30
    last_status = None
    info = {}
    while True:
        try:
            info = _get_status(vt_id, api_key)
            status = (info.get('status') or '').lower()
            if status and status != last_status:
                print(f'Status: {status}')
                last_status = status
                if translation_id:
                    TRANSLATION_JOBS[translation_id] = {"status": "translating", "message": f"Çeviri durumu: {status}"}
            
            if status in ('completed', 'succeeded', 'success', 'done'):
                break
            if status in ('failed', 'error'):
                print(f'İşlem başarısız: {json.dumps(info)[:200]}')
                if translation_id:
                    TRANSLATION_JOBS[translation_id] = {"status": "error", "message": f"Çeviri başarısız: {status}"}
                return
            if time.time() - start_t > deadline:
                print('Zaman aşımı')
                if translation_id:
                    TRANSLATION_JOBS[translation_id] = {"status": "error", "message": "Çeviri zaman aşımı"}
                return
            time.sleep(5)
            
        except requests.exceptions.ConnectionError as e:
            print(f"⚠️ API bağlantı hatası: {e}")
            if translation_id:
                TRANSLATION_JOBS[translation_id] = {"status": "error", "message": f"API bağlantı hatası: {e}"}
            return
        except Exception as e:
            print(f"⚠️ Durum kontrolü hatası: {e}")
            if translation_id:
                TRANSLATION_JOBS[translation_id] = {"status": "error", "message": f"Durum kontrolü hatası: {e}"}
            return

    download_url = (
        info.get('download_url') or info.get('url') or info.get('video_url') or info.get('output_url')
    )
    if not download_url:
        print('İndirme linki bulunamadı.')
        if translation_id:
            TRANSLATION_JOBS[translation_id] = {"status": "error", "message": "İndirme linki bulunamadı"}
        return
    
    if translation_id:
        TRANSLATION_JOBS[translation_id] = {"status": "downloading", "message": "Çeviri indiriliyor..."}
    
    # OneDrive klasörünü oluştur
    os.makedirs(TRANSLATED_OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(TRANSLATED_OUTPUT_DIR, f'{safe_name}_{safe_lang}.mp4')
    print('Çeviri indiriliyor...')
    _download_file(download_url, out_path)
    print(f'Çeviri tamamlandı: {out_path}')
    
    # Altyazı dosyasını da indir (VTT formatında)
    try:
        caption_url = _get_caption_url(vt_id, api_key)
        if caption_url:
            caption_path = os.path.join(TRANSLATED_OUTPUT_DIR, f'{safe_name}_{safe_lang}.vtt')
            print('📝 Altyazı dosyası indiriliyor...')
            _download_file(caption_url, caption_path)
            print(f'📝 Altyazı dosyası indirildi: {caption_path}')
    except Exception as e:
        pass  # Altyazı hatası sessizce geç
    
    # Alt yazı ekleme işlemi (çeviri tamamlandıktan sonra)
    try:
        print("🎬 Çevrilen videoya alt yazı ekleniyor...")
        if translation_id:
            TRANSLATION_JOBS[translation_id] = {"status": "adding_subtitles", "message": "Alt yazı ekleniyor..."}
        
        # Alt yazı eklenmiş video dosyası
        subtitled_path = os.path.splitext(out_path)[0] + '_subtitled.mp4'
        
        # VTT dosyasından metni oku
        vtt_path = os.path.splitext(out_path)[0] + '.vtt'
        subtitle_text = ""
        
        if os.path.exists(vtt_path):
            try:
                with open(vtt_path, 'r', encoding='utf-8') as f:
                    vtt_content = f.read()
                    # VTT dosyasından metin çıkar (basit parsing)
                    lines = vtt_content.split('\n')
                    subtitle_lines = []
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('WEBVTT') and not line.startswith('NOTE') and not '-->' in line and not line.isdigit():
                            subtitle_lines.append(line)
                    subtitle_text = ' '.join(subtitle_lines)
                    print(f"📝 VTT'den çıkarılan metin: {subtitle_text[:100]}...")
            except Exception as e:
                pass  # VTT okuma hatası sessizce geç
        
        # Alt yazı ekleme işlemi
        if subtitle_text:
            font_candidate = '/Library/Fonts/Arial.ttf'
            ok_subtitle = burn_scrolling_text_band(
                out_path, subtitled_path, subtitle_text,
                band_height=80, opacity=0.6, font_size=36,
                scroll_speed_px_s=180, font_path=font_candidate if os.path.exists(font_candidate) else None,
                duration_s=20  # Varsayılan süre
            )
            
            if ok_subtitle:
                # Orijinal dosyayı yedekle ve alt yazılı versiyonu kullan
                try:
                    backup_path = os.path.splitext(out_path)[0] + '_original.mp4'
                    os.rename(out_path, backup_path)
                    os.rename(subtitled_path, out_path)
                    print(f"✅ Alt yazı başarıyla eklendi: {out_path}")
                    print(f"📁 Orijinal video yedeklendi: {backup_path}")
                except Exception as e:
                    print(f"⚠️ Dosya değiştirme hatası: {e}")
            else:
                pass  # Alt yazı eklenemedi, sessizce geç
                try:
                    if os.path.exists(subtitled_path):
                        os.remove(subtitled_path)
                except Exception:
                    pass
        else:
            pass  # Alt yazı metni bulunamadı, sessizce geç
    
    except Exception as e:
        pass  # Alt yazı ekleme hatası sessizce geç
    
    if translation_id:
        TRANSLATION_JOBS[translation_id] = {"status": "completed", "message": "Çeviri ve alt yazı tamamlandı", "output_path": out_path}

    # Çıktıyı e-posta ile gönder (opsiyonel)
    try:
        if recipient_email and '@' in recipient_email:
            subject = f"🎉 Teknofest 2025'teki Videonuz Hazır!"
            base_body = (
                f"<p style=\"font-size:16px; line-height:1.5; margin:0 0 12px;\">Merhaba,</p>"
                f"<p style=\"font-size:16px; line-height:1.5; margin:0 0 12px;\">Teknofest 2025 (17-21 Eylül) etkinliğinde Demirören Medya dijital standında çekilen videonuz ektedir.</p>"
                f"<p style=\"font-size:14px; color:#555; margin:0 0 16px;\">Dosya adı: <b>{os.path.basename(out_path)}</b></p>"
            )
            html_body = _build_branded_email_body(base_body)
            # Önce Graph ile linkli gönder, sonra ek olarak düş
            sent = _send_email_graph(recipient_email, subject, html_body, attachment_path=None)
            try:
                file_size = os.path.getsize(out_path)
            except Exception:
                file_size = 0
            if not sent and file_size and file_size <= 20 * 1024 * 1024:
                sent = _send_email_smtp(recipient_email, subject, html_body, attachment_path=out_path)
            elif not sent:
                try:
                    url = _upload_to_catbox_with_retry(out_path)
                    html_body_link = _build_branded_email_body(base_body + f"<p>Video linki: <a href='{url}' target='_blank'>İndir</a></p>")
                    sent = _send_email_graph(recipient_email, subject, html_body_link, attachment_path=None) or _send_email_smtp(recipient_email, subject, html_body_link, attachment_path=None)
                except Exception as link_err:
                    print(f"Video link yükleme/gönderim hatası: {link_err}")
                    sent = False
            print(f"E-posta gönderim durumu: {sent}")
    except Exception as mail_err:
        print(f"E-posta gönderim istisnası: {mail_err}")


@app.route('/outputs/<path:filename>')
def serve_outputs(filename: str):
    base_dir = os.path.join(os.getcwd(), 'outputs')
    return send_from_directory(base_dir, filename, as_attachment=False)


@app.route('/brand/<path:filename>')
def serve_brand(filename: str):
    base_dir = os.path.join(os.getcwd(), 'brands')
    return send_from_directory(base_dir, filename, as_attachment=False)


@app.route('/logo.png')
def serve_logo():
    return send_from_directory(os.getcwd(), 'logo.png', as_attachment=False)


# Harici API: video_path ve email alıp mail gönderir
@app.route('/api/send-email', methods=['POST'])
def api_send_email():
    data = request.get_json(silent=True) or {}
    video_path = (data.get('video_path') or '').strip()
    email = (data.get('email') or '').strip()
    subject = (data.get('subject') or '🎉 Videonuz Hazır').strip()
    custom_html_body = data.get('html_body')

    if not (video_path and os.path.exists(video_path)):
        return jsonify({'ok': False, 'error': 'video_path bulunamadı'}), 400
    if not (email and '@' in email):
        return jsonify({'ok': False, 'error': 'geçersiz email'}), 400

    try:
        base_body = (
            f"<p style=\"font-size:16px; line-height:1.5; margin:0 0 12px;\">Merhaba,</p>"
            f"<p style=\"font-size:16px; line-height:1.5; margin:0 0 12px;\">Teknofest 2025 (17-21 Eylül) etkinliğinde Demirören Medya dijital standında çekilen videonuz ektedir.</p>"
            f"<p style=\"font-size:14px; color:#555; margin:0 0 16px;\">Dosya adı: <b>{os.path.basename(video_path)}</b></p>"
        )
        html_body = custom_html_body or _build_branded_email_body(base_body)

        sent = _send_email_graph(email, subject, html_body, attachment_path=None)
        try:
            file_size = os.path.getsize(video_path)
        except Exception:
            file_size = 0
        if not sent and file_size and file_size <= 20 * 1024 * 1024:
            sent = _send_email_smtp(email, subject, html_body, attachment_path=video_path)
        elif not sent:
            try:
                url = _upload_to_catbox_with_retry(video_path)
                html_body_link = _build_branded_email_body(base_body + f"<p>Video linki: <a href='{url}' target='_blank'>İndir</a></p>")
                sent = _send_email_graph(email, subject, html_body_link, attachment_path=None) or _send_email_smtp(email, subject, html_body_link, attachment_path=None)
            except Exception as link_err:
                print(f"Video link yükleme/gönderim hatası: {link_err}")
                sent = False
        return jsonify({'ok': bool(sent)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


def _maybe_build_public_url(local_path: str) -> str | None:
    base = os.getenv('PUBLIC_BASE_URL')
    if not base:
        return None
    fname = os.path.basename(local_path)
    return base.rstrip('/') + '/outputs/' + fname

@app.route("/")
def index():
    return render_template("index.html")

# Dil verileri ve ağırlıkları
languageData = [
    # Ana Diller (Daha Sık)
    {'lang': 'English', 'flag': 'fi-us', 'name': 'İngilizce', 'weight': 16.0},
    {'lang': 'Spanish', 'flag': 'fi-es', 'name': 'İspanyolca', 'weight': 10.0},
    {'lang': 'Chinese', 'flag': 'fi-cn', 'name': 'Çince', 'weight': 8.0},
    {'lang': 'Hindi', 'flag': 'fi-in', 'name': 'Hindi', 'weight': 6.0},
    {'lang': 'Arabic', 'flag': 'fi-sa', 'name': 'Arapça', 'weight': 6.0},
    {'lang': 'Portuguese', 'flag': 'fi-pt', 'name': 'Portekizce', 'weight': 6.0},
    {'lang': 'Russian', 'flag': 'fi-ru', 'name': 'Rusça', 'weight': 6.0},
    {'lang': 'Japanese', 'flag': 'fi-jp', 'name': 'Japonca', 'weight': 6.0},
    {'lang': 'Turkish', 'flag': 'fi-tr', 'name': 'Türkçe', 'weight': 6.0},
    
    # Özel Diller (Daha Sık)
    {'lang': 'French', 'flag': 'fi-fr', 'name': 'Fransızca', 'weight': 10.0},
    {'lang': 'German', 'flag': 'fi-de', 'name': 'Almanca', 'weight': 10.0},
    {'lang': 'Italian', 'flag': 'fi-it', 'name': 'İtalyanca', 'weight': 10.0},
    {'lang': 'Dutch', 'flag': 'fi-nl', 'name': 'Felemenkçe', 'weight': 10.0},
    {'lang': 'Korean', 'flag': 'fi-kr', 'name': 'Korece', 'weight': 8.0},
    
    # Kalan Diller (Nadiren)
    {'lang': 'Romanian', 'flag': 'fi-ro', 'name': 'Rumence', 'weight': 2.0},
    {'lang': 'Filipino', 'flag': 'fi-ph', 'name': 'Filipince', 'weight': 2.0},
    {'lang': 'Swedish', 'flag': 'fi-se', 'name': 'İsveççe', 'weight': 2.0},
    {'lang': 'Indonesian', 'flag': 'fi-id', 'name': 'Endonezce', 'weight': 2.0},
    {'lang': 'Ukrainian', 'flag': 'fi-ua', 'name': 'Ukraynaca', 'weight': 2.0},
    {'lang': 'Greek', 'flag': 'fi-gr', 'name': 'Yunanca', 'weight': 2.0},
    {'lang': 'Czech', 'flag': 'fi-cz', 'name': 'Çekçe', 'weight': 2.0},
    {'lang': 'Bulgarian', 'flag': 'fi-bg', 'name': 'Bulgarca', 'weight': 2.0},
    {'lang': 'Slovak', 'flag': 'fi-sk', 'name': 'Slovakça', 'weight': 2.0},
    {'lang': 'Croatian', 'flag': 'fi-hr', 'name': 'Hırvatça', 'weight': 2.0},
    {'lang': 'Finnish', 'flag': 'fi-fi', 'name': 'Fince', 'weight': 2.0}
]

def weightedPick():
    """Ağırlıklı rastgele seçim yapar"""
    total_weight = sum(lang['weight'] for lang in languageData)
    random_num = random.uniform(0, total_weight)
    
    current_weight = 0
    for lang in languageData:
        current_weight += lang['weight']
        if random_num <= current_weight:
            return lang
    
    # Fallback - son dil
    return languageData[-1]

@app.route('/api/languages')
def get_languages():
    """Tüm dil verilerini döndürür"""
    return jsonify(languageData)

@app.route('/api/spin')
def spin():
    """Slot makinesi için animasyon adımlarını döndürür"""
    steps = []
    final_language = weightedPick()
    
    # Tüm dilleri karıştır ve her birini kesin olarak bir kez göster
    all_languages = languageData.copy()
    random.shuffle(all_languages)
    
    # İlk 25 adım: Tüm dilleri kesin olarak bir kez göster
    for i in range(len(all_languages)):
        lang = all_languages[i]
        steps.append({
            'language': lang,
            'delay': 70  # Çok hızlı geçiş
        })
    
    # Kalan süre: Rastgele diller (çok hızlı)
    # 10 saniye = 10000ms, 25 dil * 100ms = 2500ms
    # Kalan 7500ms / 100ms = 75 adım daha
    for i in range(10):
        # Rastgele dil seçimi
        lang = random.choice(languageData)
        steps.append({
            'language': lang,
            'delay': 200  # Çok hızlı geçiş
        })
    
    # Son adım kesinlikle hedef
    steps.append({
        'language': final_language,
        'delay': 100
    })
    
    return jsonify({
        'steps': steps,
        'final': final_language
    })


@app.route("/check-camera", methods=["GET"])
def check_camera():
    """Kamera durumunu kontrol et"""
    try:
        has_permission = check_camera_permissions()
        return jsonify({
            "camera_available": has_permission,
            "message": "Kamera hazır" if has_permission else "Kamera izni gerekli"
        })
    except Exception as e:
        return jsonify({
            "camera_available": False,
            "message": f"Kamera hatası: {str(e)}"
        }), 500


@app.route("/camera-preview")
def camera_preview():
    """Kamera önizlemesi stream endpoint'i"""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route("/start-preview", methods=["POST"])
def start_preview():
    """Kamera önizlemesini başlat"""
    try:
        success = start_camera_preview()
        return jsonify({
            "success": success,
            "message": "Kamera önizlemesi başlatıldı" if success else "Kamera açılamadı"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Kamera önizlemesi hatası: {str(e)}"
        }), 500


@app.route("/stop-preview", methods=["POST"])
def stop_preview():
    """Kamera önizlemesini durdur"""
    try:
        # Sadece preview kamerayı durdur, uygulamayı kapatma
        global PREVIEW_CAMERA, PREVIEW_STOP_EVENT
        
        PREVIEW_STOP_EVENT.set()
        
        if PREVIEW_CAMERA is not None:
            try:
                PREVIEW_CAMERA.release()
            except Exception as e:
                print(f"Preview kamera release hatası: {e}")
            finally:
                PREVIEW_CAMERA = None
        
        # Kısa bekleme - kamera tamamen serbest bırakılsın
        time.sleep(0.2)
        
        print("Web stream kamera durduruldu")
        
        return jsonify({
            "success": True,
            "message": "Kamera önizlemesi durduruldu"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Kamera önizlemesi durdurma hatası: {str(e)}"
        }), 500


@app.route("/start-recording", methods=["POST"])
def start_recording():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "kullanici").strip() or "kullanici"
    email = (data.get("email") or "").strip()
    # Dil belirtilmemişse güvenli bir varsayılan seç (weightedPick veya English)
    try:
        default_lang = weightedPick().get('lang', 'English')
    except Exception:
        default_lang = 'English'
    language = (data.get("language") or default_lang).strip() or default_lang

    # Dosya adı güvenli hale getir
    safe_name = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_")).rstrip(" .") or "kullanici"
    safe_lang = "".join(ch for ch in language if ch.isalnum() or ch in ("-", "_")).rstrip(" .") or "Unknown"

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = RAW_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"webcam_{safe_name}_{safe_lang}_{timestamp}.mp4")

    job_id = uuid.uuid4().hex
    RECORD_JOBS[job_id] = {"status": "recording", "output": output_path, "email": email}

    def worker(job_key: str):
        try:
            # Önce tam ekran kamerayı başlat
            print('Tam ekran kamera penceresi başlatılıyor...')
            start_fullscreen_camera()
            
            # Kısa bekleme - kamera açılsın
            time.sleep(2)
            
            # Kayıt başlat
            record_20_seconds(output_path, with_audio=True)
            RECORD_JOBS[job_key] = {"status": "completed", "output": output_path}
            print('✅ Kayıt tamamlandı')
            
            # Çeviriyi ayrı thread'de başlat
            print('Çeviri arka planda başlatılıyor...')
            translation_id = uuid.uuid4().hex
            TRANSLATION_JOBS[translation_id] = {"status": "pending", "message": "Çeviri bekliyor...", "email": email}
            
            # Çeviri thread'ini başlat
            translation_thread = threading.Thread(
                target=translate_with_heygen, 
                args=(output_path, safe_name, safe_lang, translation_id, email if email else None),
                daemon=True
            )
            translation_thread.start()
            
            # Kayıt job'ına çeviri ID'sini ekle
            RECORD_JOBS[job_key]["translation_id"] = translation_id
            
        except Exception as exc:
            print("❌ Recording error:", exc)
            # Hata durumunda da kamerayı hemen kapat
            try:
                stop_fullscreen_camera()
                print('📹 Hata durumunda kamera kapatıldı')
            except Exception as cleanup_error:
                print(f"❌ Cleanup error: {cleanup_error}")
            RECORD_JOBS[job_key] = {"status": "error", "output": output_path, "error": str(exc)}
        finally:
            # Thread sonunda temizlik yap
            try:
                stop_fullscreen_camera()
            except Exception:
                pass

    ffmpeg_path = get_ffmpeg_path()
    threading.Thread(target=worker, args=(job_id,), daemon=True).start()
    return jsonify({"started": True, "output": output_path, "ffmpeg": ffmpeg_path, "audio": True, "job_id": job_id})


@app.route("/recording-status", methods=["GET"])
def recording_status():
    job_id = request.args.get("job_id", "").strip()
    if not job_id or job_id not in RECORD_JOBS:
        return jsonify({"error": "not_found"}), 404
    
    job_data = RECORD_JOBS[job_id].copy()
    
    # Çeviri durumunu da ekle
    if "translation_id" in job_data:
        translation_id = job_data["translation_id"]
        if translation_id in TRANSLATION_JOBS:
            job_data["translation"] = TRANSLATION_JOBS[translation_id]
    
    return jsonify({"job_id": job_id, **job_data})


@app.route("/translation-status", methods=["GET"])
def translation_status():
    translation_id = request.args.get("translation_id", "").strip()
    if not translation_id or translation_id not in TRANSLATION_JOBS:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"translation_id": translation_id, **TRANSLATION_JOBS[translation_id]})


@app.route("/caption-status", methods=["GET"])
def caption_status():
    """Altyazı durumunu kontrol et"""
    translation_id = request.args.get("translation_id", "").strip()
    if not translation_id or translation_id not in TRANSLATION_JOBS:
        return jsonify({"error": "not_found"}), 404
    
    job_data = TRANSLATION_JOBS[translation_id]
    
    # Çeviri tamamlandıysa altyazı dosyasını kontrol et
    if job_data.get("status") == "completed":
        output_path = job_data.get("output_path", "")
        if output_path:
            # VTT dosyasının varlığını kontrol et
            vtt_path = output_path.replace('.mp4', '.vtt')
            if os.path.exists(vtt_path):
                return jsonify({
                    "translation_id": translation_id,
                    "caption_available": True,
                    "caption_path": vtt_path,
                    "message": "Altyazı dosyası hazır"
                })
    
    return jsonify({
        "translation_id": translation_id,
        "caption_available": False,
        "message": "Altyazı henüz hazır değil"
    })

def cleanup_resources():
    """Uygulama kapatılırken kaynakları temizle"""
    try:
        stop_camera_preview()
        stop_fullscreen_camera()
        
        # Thread'leri temizle
        threads_to_clean = [PREVIEW_THREAD, FULLSCREEN_THREAD, _fullscreen_thread]
        for thread in threads_to_clean:
            if thread and thread.is_alive():
                try:
                    thread.join(timeout=2)  # Timeout artırıldı
                    if thread.is_alive():
                        print(f"⚠️ Thread hala çalışıyor: {thread.name}")
                except Exception as e:
                    print(f"Thread cleanup hatası: {e}")
        
        # OpenCV kaynaklarını temizle
        try:
            cv2.destroyAllWindows()
        except Exception as e:
            print(f"OpenCV cleanup hatası: {e}")
        
        # SoundDevice kaynaklarını temizle
        try:
            import sounddevice as sd
            sd.stop()  # Tüm aktif kayıtları durdur
        except Exception as e:
            print(f"SoundDevice cleanup hatası: {e}")
        
        # Multiprocessing kaynaklarını temizle
        try:
            import multiprocessing
            multiprocessing.active_children()  # Aktif child process'leri temizle
        except Exception as e:
            print(f"Multiprocessing cleanup hatası: {e}")
        
        # Kısa bekleme - kaynakların temizlenmesi için
        time.sleep(1.0)  # Bekleme süresi artırıldı
        
        print("Kaynaklar temizlendi")
    except Exception as e:
        print(f"Temizlik hatası: {e}")

def signal_handler(signum, frame):
    """Signal handler - uygulama kapatılırken temizlik yap"""
    print(f"\nSignal {signum} alındı, uygulama kapatılıyor...")
    cleanup_resources()
    sys.exit(0)

if __name__ == "__main__":
    # Signal handler'ları kaydet
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        app.run(host="0.0.0.0", port=8080, debug=True)
    except KeyboardInterrupt:
        print("\nUygulama kapatılıyor...")
    finally:
        cleanup_resources()



