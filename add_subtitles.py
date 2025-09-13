#!/usr/bin/env python3
"""
add_subtitles.py
----------------
Türkçe altyazı ekleme aracı.

Kullanım örnekleri:
1) Elindeki SRT dosyasını MP4'e SOFT (gömülü) ekle:
   python add_subtitles.py --file "/path/video.mp4" --srt "/path/subtitles.srt" --soft

2) Elindeki SRT'yi BURN (yanık) olarak videoya bas:
   python add_subtitles.py --file "/path/video.mp4" --srt "/path/subtitles.srt" --burn

3) Dubsmart API ile SRT üret, sonra SOFT olarak ekle:
   python add_subtitles.py --file "/path/video.mp4" --api-key "DUBSMART_API_KEY" --soft

4) Dubsmart API ile SRT üret, sonra BURN olarak ekle:
   python add_subtitles.py --file "/path/video.mp4" --api-key "DUBSMART_API_KEY" --burn

Notlar:
- SOFT ekleme MP4 kapsayıcısında `mov_text` ile yapılır (çoğu player destekler)
- BURN için ffmpeg'de libass/subtitles filtresi gerekir.
- Dubsmart uç noktaları yer tutucudur; kurumunuzun gerçek endpoint'lerini değiştirin.
"""

import os
import sys
import argparse
import subprocess
import time
import json
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

DEFAULT_BASE_URL = os.environ.get("DUBSMART_API_BASE", "https://api.dubsmart.ai/v1")

# TODO: Kurumunuzun gerçek Dubsmart yolları ile değiştirin
UPLOAD_ENDPOINT = "/media/upload"
CREATE_JOB_ENDPOINT = "/stt/jobs"
GET_JOB_ENDPOINT_TEMPLATE = "/stt/jobs/{job_id}"
GET_SRT_ENDPOINT_TEMPLATE = "/stt/jobs/{job_id}/subtitles.srt"


def eprint(*a, **k):
    print(*a, file=sys.stderr, **k)


def run_cmd(cmd: list):
    """Run a subprocess and raise on error."""
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError as e:
        eprint(f"Komut bulunamadı: {cmd[0]} (örn. ffmpeg kurulu mu?)")
        raise
    except subprocess.CalledProcessError as e:
        eprint(f"Komut hatası ({e.returncode}): {' '.join(cmd)}")
        raise


def soft_embed_subs(input_mp4: str, srt_path: str, output_mp4: str):
    """MP4 içine SOFT altyazı (mov_text) ekle (yanık değil)."""
    # Not: srt -> mov_text dönüşümü ffmpeg tarafından yapılır.
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_mp4,
        "-i", srt_path,
        "-c:v", "copy",
        "-c:a", "copy",
        "-c:s", "mov_text",
        "-metadata:s:s:0", "language=tur",
        output_mp4,
    ]
    run_cmd(cmd)


def burn_in_subs(input_mp4: str, srt_path: str, output_mp4: str):
    """Altyazıyı videoya yanık (burn) olarak bas."""
    # subtitles filtresi yol çözümlemesinde titiz olabilir; absolute path kullan.
    srt_abs = os.path.abspath(srt_path)
    # Windows/Unix-kaçışlarını olabildiğince basit tutalım:
    vf_expr = f"subtitles={srt_abs}"
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_mp4,
        "-vf", vf_expr,
        "-c:a", "copy",
        output_mp4,
    ]
    run_cmd(cmd)


def upload_media(file_path: str, api_key: str, base_url: str) -> str:
    if requests is None:
        raise RuntimeError("requests kütüphanesi gerekli: pip install requests")

    url = base_url.rstrip("/") + UPLOAD_ENDPOINT
    headers = {"Authorization": f"Bearer {api_key}"}
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f, "video/mp4")}
        print(f"[upload] -> {url}")
        r = requests.post(url, headers=headers, files=files, timeout=600)
    if r.status_code >= 300:
        raise RuntimeError(f"Upload hata: {r.status_code} {r.text}")
    data = r.json()
    media_id = data.get("media_id") or data.get("id") or data.get("url")
    if not media_id:
        raise RuntimeError(f"Upload dönen gövde beklenmedik: {data}")
    print(f"[upload] OK media_id={media_id}")
    return media_id


def create_stt_job(media_id: str, api_key: str, base_url: str, language: str = "tr") -> str:
    if requests is None:
        raise RuntimeError("requests kütüphanesi gerekli: pip install requests")

    url = base_url.rstrip("/") + CREATE_JOB_ENDPOINT
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "media_id": media_id,
        "task": "transcribe",
        "output_format": "srt",
        "source_language": language,
        "target_language": language,
    }
    print(f"[job] -> {url} {json.dumps(payload)}")
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    if r.status_code >= 300:
        raise RuntimeError(f"Job hata: {r.status_code} {r.text}")
    data = r.json()
    job_id = data.get("job_id") or data.get("id")
    if not job_id:
        raise RuntimeError(f"Job dönen gövde beklenmedik: {data}")
    print(f"[job] OK job_id={job_id}")
    return job_id


def wait_job(job_id: str, api_key: str, base_url: str, timeout_s: int = 3600, poll_s: int = 5) -> dict:
    if requests is None:
        raise RuntimeError("requests kütüphanesi gerekli: pip install requests")

    url = base_url.rstrip("/") + GET_JOB_ENDPOINT_TEMPLATE.format(job_id=job_id)
    headers = {"Authorization": f"Bearer {api_key}"}
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code >= 300:
            raise RuntimeError(f"Durum sorgu hata: {r.status_code} {r.text}")
        data = r.json()
        status = (data.get("status") or "").lower()
        print(f"[wait] status={status}")
        if status in {"succeeded", "completed", "done", "finished"}:
            return data
        if status in {"failed", "error"}:
            raise RuntimeError(f"İş başarısız: {data}")
        time.sleep(poll_s)
    raise TimeoutError("İş zaman aşımına uğradı")


def download_srt(job_id: str, api_key: str, base_url: str, out_srt: str):
    if requests is None:
        raise RuntimeError("requests kütüphanesi gerekli: pip install requests")

    url = base_url.rstrip("/") + GET_SRT_ENDPOINT_TEMPLATE.format(job_id=job_id)
    headers = {"Authorization": f"Bearer {api_key}"}
    print(f"[srt] indir -> {url}")
    r = requests.get(url, headers=headers, timeout=120)
    if r.status_code >= 300:
        raise RuntimeError(f"SRT indirme hata: {r.status_code} {r.text}")
    with open(out_srt, "wb") as f:
        f.write(r.content)
    print(f"[srt] kaydedildi: {out_srt}")


def main():
    ap = argparse.ArgumentParser(description="Video dosyasına Türkçe altyazı ekle (Dubsmart veya mevcut SRT ile)")
    ap.add_argument("--file", required=True, help="Girdi MP4 video yolu")
    ap.add_argument("--srt", help="Var olan SRT yolu (varsa Dubsmart kullanılmaz)")
    ap.add_argument("--api-key", help="Dubsmart API anahtarı (SRT yoksa gerekli)")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Dubsmart API base URL (varsayılan env DUBSMART_API_BASE)")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--soft", action="store_true", help="SRT'yi MP4 içine SOFT olarak ekle (mov_text)")
    group.add_argument("--burn", action="store_true", help="SRT'yi videoya yanık (burn) olarak bas")
    ap.add_argument("--language", default="tr", help="STT dili (varsayılan: tr)")
    args = ap.parse_args()

    input_mp4 = args.file
    if not os.path.exists(input_mp4):
        eprint(f"Girdi video bulunamadı: {input_mp4}")
        sys.exit(1)

    # 1) SRT hazır mı? değilse Dubsmart ile üret
    srt_path = args.srt
    if not srt_path:
        if not args.api_key:
            eprint("--srt vermediğiniz için --api-key gerekli (Dubsmart'tan SRT üretmek için).")
            sys.exit(2)
        # Dubsmart akışı
        media_id = upload_media(input_mp4, args.api_key, args.base_url)
        job_id = create_stt_job(media_id, args.api_key, args.base_url, language=args.language)
        _ = wait_job(job_id, args.api_key, args.base_url)
        srt_path = os.path.splitext(input_mp4)[0] + ".tr.srt"
        download_srt(job_id, args.api_key, args.base_url, srt_path)

    if not os.path.exists(srt_path):
        eprint(f"SRT bulunamadı/oluşturulamadı: {srt_path}")
        sys.exit(3)

    # 2) Çıktı adı
    suffix = ".soft" if args.soft else ".burned"
    output_mp4 = os.path.splitext(input_mp4)[0] + f".tr{suffix}.mp4"

    # 3) Gömme veya burn işlemi
    if args.soft:
        soft_embed_subs(input_mp4, srt_path, output_mp4)
    else:
        burn_in_subs(input_mp4, srt_path, output_mp4)

    print(f"Tamam! Çıktı: {output_mp4}")


if __name__ == "__main__":
    main()
