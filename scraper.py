import os
import json
import feedparser
from bs4 import BeautifulSoup
import google.generativeai as genai
from supabase import create_client, Client

# 1. Konfigurasi Environment Variables (Nanti diset di GitHub Secrets)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Inisiasi Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

# Menggunakan model Gemini 1.5 Flash (Sangat cepat dan gratis)
model = genai.GenerativeModel('gemini-1.5-flash')

def bersihkan_html(raw_html):
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ", strip=True)

def ekstrak_data_dengan_ai(teks_lowongan):
    """
    PROMPT ENGINEERING DETAIL:
    Ini adalah kunci dari sistem Data-as-a-Service Anda.
    AI dipaksa menjadi sistem ekstraksi data yang outputnya hanya JSON.
    """
    prompt = f"""
    Kamu adalah spesialis HR dan Data Engineer untuk pasar teknologi di Indonesia.
    Tugasmu adalah menganalisis deskripsi pekerjaan mentah berikut dan mengekstrak informasinya menjadi format JSON murni.
    
    Aturan wajib:
    1. Output HANYA boleh berupa objek JSON yang valid tanpa markdown (```json ... ```) atau teks pengantar apapun.
    2. Terjemahkan konsep atau tipe pekerjaan ke dalam bahasa Indonesia (misal: "Full-time" -> "Penuh Waktu").
    3. Jika tidak ada informasi eksplisit, tulis "Tidak disebutkan".
    
    Format JSON yang diharapkan:
    {{
        "judul_pekerjaan": "...",
        "perusahaan": "...",
        "lokasi": "...", (Contoh: Jakarta, Remote Indonesia, Bandung, dll)
        "estimasi_gaji": "...", (Jika ada mata uang asing, biarkan aslinya. Jika tidak ada, tulis "Sesuai standar perusahaan")
        "tech_stack": ["React", "Python", "AWS"], (Array string, maksimal 5 skill utama)
        "tipe_pekerjaan": "..."
    }}

    Deskripsi Pekerjaan Mentah:
    {teks_lowongan}
    """
    
    try:
        response = model.generate_content(prompt)
        # Membersihkan output jika AI bandel memberikan markdown
        hasil_teks = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(hasil_teks)
    except Exception as e:
        print(f"Error AI Processing: {e}")
        return None

def main():
    print("Memulai proses scraping data...")
    
    # Contoh Sumber: RSS Job Board Remote (Anda bisa menggantinya dengan RSS lokal jika ada)
    # Sistem ini akan memfilter/mengonversi yang relevan lewat AI
    rss_url = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
    feed = feedparser.parse(rss_url)
    
    pekerjaan_baru = 0
    
    # Ambil 10 data terbaru saja setiap jalan agar tidak kena limit gratisan
    for entry in feed.entries[:10]:
        link = entry.link
        
        # Cek apakah data sudah ada di database (Mencegah duplikasi)
        cek_db = supabase.table("indo_tech_jobs").select("id").eq("url_sumber", link).execute()
        if len(cek_db.data) > 0:
            print(f"Lewati: {link} (Sudah ada di database)")
            continue
            
        print(f"Memproses: {entry.title}")
        deskripsi_bersih = bersihkan_html(entry.description)
        
        # Proses ke AI
        data_json = ekstrak_data_dengan_ai(entry.title + " " + deskripsi_bersih)
        
        if data_json:
            # Tambahkan URL ke data sebelum dimasukkan ke database
            data_json["url_sumber"] = link
            
            # Insert ke Supabase
            try:
                supabase.table("indo_tech_jobs").insert(data_json).execute()
                print(f"Sukses disimpan: {data_json['judul_pekerjaan']}")
                pekerjaan_baru += 1
            except Exception as e:
                print(f"Gagal simpan ke DB: {e}")
                
    print(f"Selesai! {pekerjaan_baru} pekerjaan baru berhasil ditambahkan ke database.")

if __name__ == "__main__":
    main()
