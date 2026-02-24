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
                    "judul": job.get("title"),
                    "perusahaan": job.get("company_name"),
                    "link": job.get("url"),
                    "deskripsi_mentah": job.get("description", "")[:1500]
                })
    except Exception as e:
        print(f"Gagal Remotive: {e}")
    return pekerjaan

def ambil_dari_arbeitnow():
    print("\n--- Menarik data dari Arbeitnow API ---")
    url = "https://www.arbeitnow.com/api/job-board-api"
    pekerjaan = []
    try:
        res = httpx.get(url, timeout=15.0)
        # Ambil 5 data teratas saja per hari
        for job in res.json().get("data", [])[:5]:
            if job.get("remote"): # Hanya ambil yang remote
                # Membersihkan HTML bawaan Arbeitnow
                soup = BeautifulSoup(job.get("description", ""), "html.parser")
                deskripsi_bersih = soup.get_text(separator=" ", strip=True)[:1500]
                
                pekerjaan.append({
                    "judul": job.get("title"),
                    "perusahaan": job.get("company_name"),
                    "link": job.get("url"),
                    "deskripsi_mentah": deskripsi_bersih
                })
    except Exception as e:
        print(f"Gagal Arbeitnow: {e}")
    return pekerjaan

def main():
    print("Memulai Mesin Agregator Multi-Sumber...\n")
    
    # Kumpulkan semua data dari berbagai sumber ke dalam satu antrean (Queue)
    antrean_pekerjaan = []
    antrean_pekerjaan.extend(ambil_dari_remotive())
    antrean_pekerjaan.extend(ambil_dari_arbeitnow())
    
    print(f"\nTotal pekerjaan mentah terkumpul: {len(antrean_pekerjaan)}")
    pekerjaan_baru = 0
    
    # Proses antrean satu per satu
    for job in antrean_pekerjaan:
        link = job["link"]
        judul = job["judul"]
        
        # Cek Database agar tidak duplikat
        cek_db = supabase.table("indo_tech_jobs").select("id").eq("url_sumber", link).execute()
        if len(cek_db.data) > 0:
            print(f"Lewati: {judul} (Sudah ada di DB)")
            continue
            
        print(f"🤖 Memproses AI: {judul}")
        teks_gabungan = f"Judul: {judul}\nPerusahaan: {job['perusahaan']}\nDeskripsi: {job['deskripsi_mentah']}"
        
        data_json = ekstrak_dan_terjemahkan_dengan_ai(teks_gabungan)
        
        if data_json:
            data_json["url_sumber"] = link
            try:
                supabase.table("indo_tech_jobs").insert(data_json).execute()
                print(f"✅ Tersimpan: {data_json['judul_pekerjaan']}")
                pekerjaan_baru += 1
            except Exception as e:
                print(f"❌ Gagal simpan: {e}")
        
        # Jeda 3 detik agar Google Gemini API tidak memblokir kita karena terlalu banyak request (Rate Limiting)
        time.sleep(3)
                
    print(f"\nSelesai! {pekerjaan_baru} loker baru berhasil ditambahkan dari berbagai sumber.")

if __name__ == "__main__":
    main()
