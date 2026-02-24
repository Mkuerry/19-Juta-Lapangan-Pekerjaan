import os
import json
import httpx
import time
from supabase import create_client, Client

# Konfigurasi Environment Variables (Aman di GitHub Secrets)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"

def terjemahkan_dengan_ai(teks_lowongan):
    prompt = f"""
    Kamu HR & Data Translator. Rangkum loker ini ke bahasa Indonesia dan ubah ke format JSON murni.
    Output HANYA objek JSON valid tanpa markdown (tanpa ```json ```).
    Jika gaji tidak disebutkan, tulis "Sesuai standar perusahaan".
    
    Format JSON:
    {{
        "judul_pekerjaan": "...",
        "perusahaan": "...",
        "lokasi": "...", 
        "estimasi_gaji": "...",
        "tech_stack": ["React", "Python", "Cloud"], 
        "tipe_pekerjaan": "..." 
    }}

    Data Mentah:
    {teks_lowongan}
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1}}
    
    try:
        response = httpx.post(GEMINI_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=60.0)
        response.raise_for_status() 
        data = response.json()
        hasil_teks = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(hasil_teks.replace('```json', '').replace('```', '').strip())
    except Exception as e:
        print(f"Error AI: {e}")
        return None

def main():
    print("Mencari lowongan Google Jobs via JSearch (RapidAPI)...")
    
    url = "https://jsearch.p.rapidapi.com/search"
    
    # Menggunakan parameter yang Anda temukan, dioptimasi untuk target DaaS kita
    querystring = {
        "query": "remote developer IT jobs in Indonesia",
        "page": "1",
        "num_pages": "1",
        "date_posted": "today" # Hanya ambil loker yang di-posting hari ini
    }
    
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "jsearch.p.rapidapi.com"
    }
    
    try:
        res = httpx.get(url, headers=headers, params=querystring, timeout=30.0)
        res.raise_for_status()
        jobs_data = res.json().get("data", [])
        print(f"✅ Berhasil mendapatkan {len(jobs_data)} lowongan dari Google Jobs.")
    except Exception as e:
        print(f"❌ Gagal mengakses JSearch API: {e}")
        return

    pekerjaan_baru = 0
    
    for job in jobs_data:
        judul = job.get("job_title", "")
        perusahaan = job.get("employer_name", "")
        link = job.get("job_apply_link", "")
        deskripsi = job.get("job_description", "")[:1500] 
        
        if not link:
            continue
            
        # Cek duplikasi di database
        cek_db = supabase.table("indo_tech_jobs").select("id").eq("url_sumber", link).execute()
        if len(cek_db.data) > 0:
            print(f"Lewati (Duplikat): {judul[:30]}...")
            continue
            
        print(f"🤖 AI Memproses: {judul[:30]}... dari {perusahaan}")
        
        data_json = terjemahkan_dengan_ai(f"Judul: {judul}\nPerusahaan: {perusahaan}\nDeskripsi: {deskripsi}")
        
        if data_json:
            data_json["url_sumber"] = link
            try:
                supabase.table("indo_tech_jobs").insert(data_json).execute()
                print(f"✅ TERSIMPAN: {data_json['judul_pekerjaan']}")
                pekerjaan_baru += 1
            except Exception as e:
                print(f"❌ DATABASE ERROR: {e}")
        
        time.sleep(3)
                
    print(f"\nSelesai! {pekerjaan_baru} loker Google Jobs berhasil ditambahkan.")

if __name__ == "__main__":
    main()
