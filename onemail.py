import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl
import certifi
from typing import List, Optional
 
SMTP_HOST = "smtp.office365.com"       # Exchange Online
SMTP_PORT = 587  # Alternatif: 25, 465 (SSL)
 
sender = "emir.usenmez@hurriyet.com.tr"  # Gerçek Exchange Online email adresinizi yazın
password = "Dmm.112255"  # Uygulama parolası kullanın (16 karakterlik kod)
receiver = "orcun.eren@hurriyet.com.tr"  # Gerçek alıcı email adresini yazın
 
def send_email_smtp(sender_email: str, sender_password: str, recipient_emails: List[str],
                   subject: str, body: str, is_html: bool = True) -> bool:
    """SMTP ile email gönderir"""
    try:
        # Email mesajını oluştur
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = ", ".join(recipient_emails)
        msg["Subject"] = subject
       
        # Body tipini belirle
        body_type = "html" if is_html else "plain"
        msg.attach(MIMEText(body, body_type))
       
        # SSL context oluştur
        context = ssl.create_default_context(cafile=certifi.where())
       
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
 
# Email gönder
success = send_email_smtp(
    sender_email=sender,
    sender_password=password,
    recipient_emails=[receiver],
    subject="SMTP Test - Exchange Online",
    body="<h3>Merhaba SMTP!</h3><p>Bu Microsoft Exchange Online üzerinden SMTP ile gönderilen bir test emailidir.</p>",
    is_html=True
)
 
if success:
    print("İşlem başarıyla tamamlandı!")
else:
    print("Email gönderilemedi!")