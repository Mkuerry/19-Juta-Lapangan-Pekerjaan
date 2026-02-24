import os
import json
import httpx
import time
from bs4 import BeautifulSoup
from supabase import create_client, Client

# Konfigurasi Environment Variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"

def ekstrak_dan_terjemahkan_dengan_ai(teks_lowongan):
    prompt = f"""
    Kamu adalah HR dan Data Translator spesialis loker IT.
    Terjemahkan dan rangkum loker ini ke bahasa Indonesia, lalu ubah ke format JSON murni.
    
    Aturan wajib:
    1. Output HANYA objek JSON valid tanpa markdown (tanpa ```json ```).
    2. Jika lokasi mencakup "Worldwide/Global/Anywhere", tulis "Remote Global (Bisa dari Indonesia)".
    
    Format JSON:
    {{
        "judul_pekerjaan": "...",
        "perusahaan": "...",
        "lokasi": "...", 
        "estimasi_gaji": "...",
        "tech_stack": ["React", "Node", "AWS"], (Maksimal 5)
        "tipe_pekerjaan": "..." 
    }}

    Data Mentah:
    {teks_lowongan}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1}
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        response = httpx.post(GEMINI_URL, json=payload, headers=headers, timeout=30.0)
        response.raise_for_status() 
        data = response.json()
        hasil_teks = data["candidates"][0]["content"]["parts"][0]["text"]
        
        hasil_teks = hasil_teks.replace('```json', '').replace('```', '').strip()
        return json.loads(hasil_teks)
    except Exception as e:
        print(f"Error AI: {e}")
        return None

# --- FUNGSI PENGAMBIL DATA DARI BERBAGAI SUMBER ---

def ambil_dari_remotive():
    print("\n--- Menarik data dari Remotive API ---")
    url = "https://remotive.com/api/remote-jobs?category=software-dev&limit=5"
    pekerjaan = []
    try:
        res = httpx.get(url, timeout=15.0)
        for job in res.json().get("jobs", []):
            if "worldwide" in job.get("candidate_required_location", "").lower():
                pekerjaan.append({
                    "judul": job.get("title", ""),
                    "perusahaan": job.get("company_name", ""),
                    "link": job.get("url", ""),
                    "deskripsi_mentah": job.get("description", "")[:1500]
                })
    except Exception as e:
        print(f"Gagal Remotive: {e}")
    return pekerjaan

def ambil_dari_joinrise():
    print("\n--- Menarik data dari JoinRise API ---")
    # Kita ubah limit=5 saja agar tidak membebani API Gemini harian Anda
    url = "https://api.joinrise.io/api/v1/jobs/public?limit=5&sortedBy=createdAt&sort=des&page=1"
    pekerjaan = []
    try:
        res = httpx.get(url, timeout=15.0)
        data_json = res.json()
        
        # JoinRise biasanya menaruh list pekerjaannya di dalam key 'data' atau 'items'
        jobs_list = data_json.get("data", data_json.get("items", [])) if isinstance(data_json, dict) else []
        
        for job in jobs_list:
            # Menggunakan .get() bertingkat untuk berjaga-jaga jika struktur JSON mereka berubah
            judul = job.get("title", "Posisi Tidak Diketahui")
            perusahaan = job.get("companyName", job.get("company", {}).get("name", "Perusahaan Rahasia"))
            link = job.get("applyUrl", job.get("url", f"https://joinrise.io/jobs/{job.get('id', '')}"))
            
            # Membersihkan HTML jika deskripsinya mengandung tag HTML
            deskripsi_mentah = job.get("description", "")
            if "<" in deskripsi_mentah and ">" in deskripsi_mentah:
                soup = BeautifulSoup(deskripsi_mentah, "html.parser")
                deskripsi_mentah = soup.get_text(separator=" ", strip=True)
                
            pekerjaan.append({
                "judul": judul,
                "perusahaan": perusahaan,
                "link": link,
                "deskripsi_mentah": deskripsi_mentah[:1500]
            })
    except Exception as e:
        print(f"Gagal JoinRise: {e}")
    return pekerjaan

def main():
    print("Memulai Mesin Agregator Multi-Sumber...\n")
    
    # Kumpulkan semua data dari berbagai sumber ke dalam satu antrean (Queue)
    antrean_pekerjaan = []
    antrean_pekerjaan.extend(ambil_dari_remotive())
    antrean_pekerjaan.extend(ambil_dari_joinrise())  # <--- JoinRise dimasukkan ke antrean!
    
    print(f"\nTotal pekerjaan mentah terkumpul: {len(antrean_pekerjaan)}")
    pekerjaan_baru = 0
