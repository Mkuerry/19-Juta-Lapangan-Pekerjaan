import os
import json
import httpx
from bs4 import BeautifulSoup
from supabase import create_client, Client

# 1. Konfigurasi Environment Variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"

def ekstrak_data_dengan_ai(teks_lowongan):
    prompt = f"""
    Kamu adalah HR dan Data Engineer spesialis pasar teknologi di Indonesia.
    Tugasmu menganalisis deskripsi pekerjaan mentah dari portal loker Indonesia dan mengekstraknya ke format JSON.
    
    Aturan wajib:
    1. Output HANYA objek JSON valid tanpa markdown (tanpa ```json ```) atau teks lain.
    2. Jika tidak ada informasi eksplisit, tulis "Tidak disebutkan".
    
    Format JSON:
    {{
        "judul_pekerjaan": "...",
        "perusahaan": "...",
        "lokasi": "...", (Contoh: Jakarta, Bandung, Remote, dll)
        "estimasi_gaji": "...",
        "tech_stack": ["React", "PHP", "Laravel"], (Array string, maksimal 5 skill utama)
        "tipe_pekerjaan": "..." (Full-time, Magang, Part-time)
    }}

    Deskripsi Mentah:
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
        print(f"Error AI Processing: {e}")
        return None

def main():
    print("Memulai proses scraping loker lokal (Indonesia)...")
    
    # Target URL: Loker.id kategori Information Technology
    target_url = "https://www.loker.id/kategori/information-technology"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    
    try:
        response = httpx.get(target_url, headers=headers, timeout=15.0)
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"Gagal mengakses website sumber: {e}")
        return

    # Loker.id biasanya menyimpan judul kerja di tag <h3>
    pekerjaan_baru = 0
    job_cards = soup.find_all("h3", limit=10) # Ambil 10 teratas
    
    for card in job_cards:
        link_tag = card.find("a")
        if not link_tag:
            continue
            
        link = link_tag.get("href")
        judul_mentah = link_tag.get_text(strip=True)
        
        # Cek Database agar tidak duplikat
        cek_db = supabase.table("indo_tech_jobs").select("id").eq("url_sumber", link).execute()
        if len(cek_db.data) > 0:
            print(f"Lewati: {judul_mentah[:30]}... (Sudah ada di database)")
            continue
            
        print(f"Memproses: {judul_mentah}")
        
        # Masuk ke halaman detail untuk mengambil deskripsi lengkap
        try:
            detail_res = httpx.get(link, headers=headers, timeout=15.0)
            detail_soup = BeautifulSoup(detail_res.text, "html.parser")
            # Mengambil seluruh teks di halaman, dipotong agar tidak terlalu panjang untuk AI
            deskripsi_bersih = detail_soup.get_text(separator="\n", strip=True)[:3000] 
        except:
            deskripsi_bersih = judul_mentah # Jika gagal masuk, gunakan judulnya saja

        # Eksekusi AI
        teks_gabungan = f"Judul: {judul_mentah}\n\nDeskripsi:\n{deskripsi_bersih}"
        data_json = ekstrak_data_dengan_ai(teks_gabungan)
        
        if data_json:
            data_json["url_sumber"] = link
            try:
                supabase.table("indo_tech_jobs").insert(data_json).execute()
                print(f"✅ Sukses disimpan: {data_json['judul_pekerjaan']} di {data_json.get('lokasi', 'Indonesia')}")
                pekerjaan_baru += 1
            except Exception as e:
                print(f"❌ Gagal simpan ke DB: {e}")
                
    print(f"Selesai! {pekerjaan_baru} loker lokal baru berhasil ditambahkan.")

if __name__ == "__main__":
    main()
