import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl
from typing import List, Optional
from email.mime.base import MIMEBase
from email import encoders
import base64
import os
import certifi

SMTP_HOST = "smtp.office365.com"       # Exchange Online
SMTP_PORT = 587  # Alternatif: 25, 465 (SSL)

sender = "dijitalyayinlar@demirorenmedya.com"  # Gerçek Exchange Online email adresinizi yazın
password = "TGG351tg@@**"  # Uygulama parolası kullanın (16 karakterlik kod)
receiver = "ntopcugil@hurriyet.com.tr"  # Gerçek alıcı email adresini yazın

def encode_image_to_base64(image_path):
    """Resmi Base64 formatına çevirir"""
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return encoded_string
    except FileNotFoundError:
        print(f"Resim bulunamadı: {image_path}")
        return None

# Logoları Base64 formatına çevir (macOS yolları)
n_sosyal_logo = encode_image_to_base64("/Users/emirefeusenmez/code/heygen/sosyal/nsosyal.png")
instagram_logo = encode_image_to_base64("/Users/emirefeusenmez/code/heygen/sosyal/insta.png")
x_logo = encode_image_to_base64("/Users/emirefeusenmez/code/heygen/sosyal/x.png")

# Debug: Logo durumunu kontrol et
print(f"N Sosyal logo durumu: {'Başarılı' if n_sosyal_logo else 'Başarısız'}")
print(f"Instagram logo durumu: {'Başarılı' if instagram_logo else 'Başarısız'}")
print(f"X logo durumu: {'Başarılı' if x_logo else 'Başarısız'}")
if n_sosyal_logo:
    print(f"N Sosyal logo boyutu: {len(n_sosyal_logo)} karakter")
if instagram_logo:
    print(f"Instagram logo boyutu: {len(instagram_logo)} karakter")
if x_logo:
    print(f"X logo boyutu: {len(x_logo)} karakter")


def send_email_smtp(sender_email: str, sender_password: str, recipient_emails: List[str], 
                   subject: str, body: str, is_html: bool = True,
                   video_path: Optional[str] = None,
                   video_content_id: str = "video1") -> bool:
    """SMTP ile email gönderir"""
    try:
        # Email mesajını oluştur (alternatifli: HTML + ekler)
        msg = MIMEMultipart('related')
        msg["From"] = sender_email
        msg["To"] = ", ".join(recipient_emails)
        msg["Subject"] = subject
        
        # Body tipini belirle
        body_type = "html" if is_html else "plain"
        alternative = MIMEMultipart('alternative')
        alternative.attach(MIMEText(body, body_type))
        msg.attach(alternative)

        # Video dosyasını ekle (ek/attachment olarak)
        if video_path:
            try:
                with open(video_path, 'rb') as vf:
                    video_part = MIMEBase('video', 'mp4')
                    video_part.set_payload(vf.read())
                encoders.encode_base64(video_part)
                # Ek dosya adı: dosya adındaki kişi ismi (webcam_<isim>_... -> <isim>.mp4)
                base_name = os.path.basename(video_path)
                name_root, ext = os.path.splitext(base_name)
                parts = name_root.split('_')
                person_name = parts[1] if len(parts) >= 2 else name_root
                attach_name = f"{person_name}{ext or '.mp4'}"
                video_part.add_header('Content-Disposition', 'attachment', filename=attach_name)
                msg.attach(video_part)
            except FileNotFoundError:
                print(f"Video bulunamadı: {video_path}")
        
        # SSL context oluştur (certifi ile güvenilir kökler)
        context = ssl.create_default_context()
        try:
            context.load_verify_locations(cafile=certifi.where())
        except Exception:
            pass
        
        # SMTP bağlantısı kur
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()  # Sunucuya kendimizi tanıt
            server.starttls(context=context)  # TLS şifreleme başlat
            server.ehlo()  # TLS sonrası tekrar tanıt
            server.login(sender_email, sender_password)  # Giriş yap
            
            # Email gönder
            text = msg.as_string()
            server.sendmail(sender_email, recipient_emails, text)
            
        print(f"Email başarıyla gönderildi: {', '.join(recipient_emails)}")
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

# Logo HTML'lerini oluştur - Emoji alternatifi
if n_sosyal_logo:
    n_sosyal_img = f'<img src="data:image/png;base64,{n_sosyal_logo}" alt="N Sosyal" style="width: 24px; height: 24px; margin-right: 10px;">'
else:
    n_sosyal_img = '<span style="font-size: 24px; margin-right: 10px;">📱</span>'  # Emoji alternatif

if instagram_logo:
    instagram_img = f'<img src="data:image/png;base64,{instagram_logo}" alt="Instagram" style="width: 24px; height: 24px; margin-right: 10px;">'
else:
    instagram_img = '<span style="font-size: 24px; margin-right: 10px;">📷</span>'  # Emoji alternatif

if x_logo:
    x_img = f'<img src="data:image/png;base64,{x_logo}" alt="X" style="width: 24px; height: 24px; margin-right: 10px;">'
else:
    x_img = '<span style="font-size: 24px; margin-right: 10px;">🐦</span>'  # Emoji alternatif

# Email gönder
success = send_email_smtp(
    sender_email=sender,
    sender_password=password,
    recipient_emails=[receiver],
    subject="🎉 Teknofest 2025'teki Videonuz Hazır!",
    body=f"""
    <div style=\"margin:0; padding:0; background-color:#ffffff;\"> 
      <div style=\"max-width:560px; margin:0 auto; padding:16px; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; color:#111;\"> 
        <p style=\"font-size:16px; line-height:1.5; margin:0 0 12px;\">Merhaba,</p>
        <p style=\"font-size:16px; line-height:1.5; margin:0 0 12px;\">Teknofest 2025 (17-21 Eylül) etkinliğinde Demirören Medya dijital standında çekilen videonuz ektedir.</p>
        

        <div style=\"display:flex; align-items:center; gap:8px; margin:16px 0 8px;\"> 
          {n_sosyal_img} 
          <span style=\"font-weight:700; font-size:16px;\">N Sosyal</span> 
        </div> 
        <div style=\"font-size:14px; line-height:1.5; color:#111;\"> 
          <a href=\"https://sosyal.teknofest.app/@hurriyet\" style=\"color:#111;\">Hürriyet</a> | 
          <a href=\"https://sosyal.teknofest.app/@milliyet\" style=\"color:#111;\">Milliyet</a> | 
          <a href=\"https://sosyal.teknofest.app/@cnnturkcom\" style=\"color:#111;\">CNN Türk</a> | 
          <a href=\"https://sosyal.teknofest.app/@fanatikcomtr\" style=\"color:#111;\">Fanatik</a> | 
          <a href=\"https://sosyal.teknofest.app/@postacomtr\" style=\"color:#111;\">Posta</a> | 
          <a href=\"https://sosyal.teknofest.app/@gazetevatan\" style=\"color:#111;\">Vatan</a> | 
          <a href=\"https://sosyal.teknofest.app/@kanald\" style=\"color:#111;\">Kanal D</a> | 
          <a href=\"https://sosyal.teknofest.app/@teve2\" style=\"color:#111;\">Teve2</a> 
        </div>

        <div style=\"display:flex; align-items:center; gap:8px; margin:16px 0 8px;\"> 
          {instagram_img} 
          <span style=\"font-weight:700; font-size:16px;\">Instagram</span> 
        </div> 
        <div style=\"font-size:14px; line-height:1.5; color:#111;\"> 
          <a href=\"https://www.instagram.com/hurriyetcomtr/\" style=\"color:#111;\">Hürriyet</a> | 
          <a href=\"https://www.instagram.com/milliyetcomtr/\" style=\"color:#111;\">Milliyet</a> | 
          <a href=\"https://www.instagram.com/cnnturk/\" style=\"color:#111;\">CNN Türk</a> | 
          <a href=\"https://www.instagram.com/fanatikcomtr/\" style=\"color:#111;\">Fanatik</a> | 
          <a href=\"https://www.instagram.com/posta.com.tr/\" style=\"color:#111;\">Posta</a> | 
          <a href=\"https://www.instagram.com/gazetevatancom/\" style=\"color:#111;\">Vatan</a> | 
          <a href=\"https://www.instagram.com/kanald/\" style=\"color:#111;\">Kanal D</a> | 
          <a href=\"https://www.instagram.com/teve2/\" style=\"color:#111;\">Teve2</a> 
        </div>

        <div style=\"display:flex; align-items:center; gap:8px; margin:16px 0 8px;\"> 
          {x_img} 
          <span style=\"font-weight:700; font-size:16px;\">X</span> 
        </div> 
        <div style=\"font-size:14px; line-height:1.5; color:#111;\"> 
          <a href=\"https://x.com/Hurriyet\" style=\"color:#111;\">Hürriyet</a> | 
          <a href=\"https://x.com/milliyet\" style=\"color:#111;\">Milliyet</a> | 
          <a href=\"https://x.com/cnnturk\" style=\"color:#111;\">CNN Türk</a> | 
          <a href=\"https://x.com/fanatikcomtr\" style=\"color:#111;\">Fanatik</a> | 
          <a href=\"https://x.com/postacomtr\" style=\"color:#111;\">Posta</a> | 
          <a href=\"https://x.com/Vatan\" style=\"color:#111;\">Vatan</a> | 
          <a href=\"https://x.com/kanald\" style=\"color:#111;\">Kanal D</a> | 
          <a href=\"https://x.com/teve2Official\" style=\"color:#111;\">Teve2</a> 
        </div>

        <p style=\"font-size:14px; line-height:1.5; margin:16px 0; color:#333;\">Sevgiler,<br/>Demirören Medya Dijital Yayınlar</p> 
      </div> 
    </div> 
    """,
    is_html=True,
    video_path="/Users/emirefeusenmez/code/heygen/outputs/webcam_efeemirüşenmez_Dutch_20250911_171332.mp4"
)

if success:
    print("İşlem başarıyla tamamlandı!")
else:
    print("Email gönderilemedi!")
