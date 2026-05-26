from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from supabase import create_client, Client
from datetime import datetime
import os

# ==========================================
# 1. INISIALISASI APLIKASI WEB BACKEND
# ==========================================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 2. KONFIGURASI SUPABASE
# ==========================================
SUPABASE_URL = "https://tmyicpyizrsyxzqbcgnv.supabase.co"
SUPABASE_KEY = "sb_publishable_K5R45hpwY6oJHkyxi0D5JQ_hxfDLLFn"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ==========================================
# 3. STRUKTUR DATA (MODEL PYDANTIC)
# ==========================================
class LoginRequest(BaseModel):
    nik: str


class PengajuanBaru(BaseModel):
    nik_pemohon: str
    tgl_mulai: str
    tgl_selesai: str
    waktu_mulai: str
    waktu_selesai: str
    lokasi_awal: str
    tujuan: str
    keperluan: str


class ApprovalManager(BaseModel):
    id_pengajuan: int
    is_approved: bool
    keterangan: str = ""
    nama_manager: str = ""


class ApprovalGA(BaseModel):
    id_pengajuan: int
    is_approved: bool
    keterangan: str = ""
    nama_ga: str = ""
    no_polisi: str = ""
    merek_kendaraan: str = ""


class InspeksiKeluar(BaseModel):
    id_pengajuan: int
    odo_awal: int
    bbm_awal: int


class InspeksiMasuk(BaseModel):
    id_pengajuan: int
    odo_akhir: int
    bbm_akhir: int
    catatan_security: str = "-"


class KonfirmasiUser(BaseModel):
    id_pengajuan: int
    is_setuju: bool
    alasan_banding: str = ""
    timestamp_setuju: str = ""


# ==========================================
# FUNGSI PEMBANTU: CEK BENTROK JADWAL
# ==========================================
def cek_bentrok(tgl_m1, wkt_m1, tgl_s1, wkt_s1, tgl_m2, wkt_m2, tgl_s2, wkt_s2):
    try:
        format_waktu = "%Y-%m-%d %H:%M"
        mulai1 = datetime.strptime(f"{tgl_m1} {wkt_m1[:5]}", format_waktu)
        selesai1 = datetime.strptime(f"{tgl_s1} {wkt_s1[:5]}", format_waktu)
        mulai2 = datetime.strptime(f"{tgl_m2} {wkt_m2[:5]}", format_waktu)
        selesai2 = datetime.strptime(f"{tgl_s2} {wkt_s2[:5]}", format_waktu)

        return mulai1 < selesai2 and selesai1 > mulai2
    except Exception as e:
        return False


# ==========================================
# 4. ENDPOINT LOGIN
# ==========================================
@app.post("/api/login")
async def proses_login(req: LoginRequest):
    try:
        response = supabase.table("karyawan").select("*").eq("nik", req.nik).execute()

        if len(response.data) > 0:
            user_data = response.data[0]
            return {
                "status": "sukses",
                "nik": user_data["nik"],
                "nama": user_data["nama"],
                "role": user_data["role"],
                "divisi": user_data["divisi"],
            }
        else:
            raise HTTPException(
                status_code=404, detail="Maaf, NIK tidak terdaftar di sistem."
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Terjadi kesalahan sistem: {str(e)}"
        )


# ==========================================
# 5. ENDPOINT MENGAMBIL SEMUA PENGAJUAN
# ==========================================
@app.get("/api/pengajuan")
async def get_semua_pengajuan():
    try:
        res_pengajuan = (
            supabase.table("pengajuan").select("*").order("id", desc=True).execute()
        )
        res_karyawan = supabase.table("karyawan").select("nik, nama").execute()
        dict_karyawan = {k["nik"]: k["nama"] for k in res_karyawan.data}

        data_final = []
        for p in res_pengajuan.data:
            p["nama_pemohon"] = dict_karyawan.get(p["nik_pemohon"], "Tidak Diketahui")
            data_final.append(p)

        return {"status": "sukses", "data": data_final}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memuat data: {str(e)}")


# ==========================================
# 6. ENDPOINT MEMBUAT PENGAJUAN BARU (DIPERBARUI)
# ==========================================
@app.post("/api/pengajuan")
async def buat_pengajuan(req: PengajuanBaru):
    try:
        aktif_user = (
            supabase.table("pengajuan")
            .select("*")
            .eq("nik_pemohon", req.nik_pemohon)
            .neq("status_pengajuan", "selesai")
            .neq("status_pengajuan", "ditolak")
            .execute()
        )

        for p_lama in aktif_user.data:
            if cek_bentrok(
                req.tgl_mulai,
                req.waktu_mulai,
                req.tgl_selesai,
                req.waktu_selesai,
                p_lama["tgl_mulai"],
                p_lama["waktu_mulai"],
                p_lama["tgl_selesai"],
                p_lama["waktu_selesai"],
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Jadwal bentrok! Anda masih memiliki pengajuan yang aktif di jam dan tanggal tersebut.",
                )

        data_insert = {
            "nik_pemohon": req.nik_pemohon,
            "tgl_mulai": req.tgl_mulai,
            "tgl_selesai": req.tgl_selesai,
            "waktu_mulai": req.waktu_mulai,
            "waktu_selesai": req.waktu_selesai,
            "lokasi_awal": req.lokasi_awal,
            "tujuan": req.tujuan,
            "keperluan": req.keperluan,
            "status_pengajuan": "menunggu",
            "catatan": "-",
        }
        response = supabase.table("pengajuan").insert(data_insert).execute()
        return {
            "status": "sukses",
            "pesan": "Pengajuan berhasil dibuat!",
            "data_pengajuan": response.data[0],
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal menyimpan pengajuan: {str(e)}"
        )


# ==========================================
# 7. ENDPOINT APPROVAL MANAGER
# ==========================================
@app.put("/api/approval-manager")
async def proses_approval_manager(req: ApprovalManager):
    try:
        status_baru = "menunggu_ga" if req.is_approved else "ditolak"
        response = (
            supabase.table("pengajuan")
            .update(
                {
                    "status_pengajuan": status_baru,
                    "catatan": req.keterangan,
                    "nama_manager": req.nama_manager,
                }
            )
            .eq("id", req.id_pengajuan)
            .execute()
        )

        if len(response.data) > 0:
            return {
                "status": "sukses",
                "pesan": f"Status saat ini: {status_baru}",
                "data": response.data[0],
            }
        else:
            raise HTTPException(
                status_code=404, detail="Data pengajuan tidak ditemukan."
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Terjadi kesalahan sistem: {str(e)}"
        )


# ==========================================
# 8. ENDPOINT APPROVAL PIC GA (DIPERBARUI)
# ==========================================
@app.put("/api/approval-ga")
async def proses_approval_ga(req: ApprovalGA):
    try:
        if req.is_approved and req.no_polisi != "-":
            target = (
                supabase.table("pengajuan")
                .select("*")
                .eq("id", req.id_pengajuan)
                .execute()
                .data[0]
            )

            jadwal_mobil = (
                supabase.table("pengajuan")
                .select("*")
                .eq("no_polisi", req.no_polisi)
                .in_(
                    "status_pengajuan",
                    [
                        "disetujui",
                        "sedang_dipakai",
                        "menunggu_konfirmasi_user",
                        "banding",
                    ],
                )
                .execute()
            )

            for jm in jadwal_mobil.data:
                if jm["id"] != req.id_pengajuan:
                    if cek_bentrok(
                        target["tgl_mulai"],
                        target["waktu_mulai"],
                        target["tgl_selesai"],
                        target["waktu_selesai"],
                        jm["tgl_mulai"],
                        jm["waktu_mulai"],
                        jm["tgl_selesai"],
                        jm["waktu_selesai"],
                    ):
                        raise HTTPException(
                            status_code=400,
                            detail=f"Mobil {req.no_polisi} sudah di-booking pada rentang waktu tersebut (Terbentrok dengan ID #{jm['id']}). Silakan pilih mobil lain.",
                        )

        status_baru = "disetujui" if req.is_approved else "ditolak"

        response = (
            supabase.table("pengajuan")
            .update(
                {
                    "status_pengajuan": status_baru,
                    "catatan": req.keterangan,
                    "nama_ga": req.nama_ga,
                    "no_polisi": req.no_polisi,
                    "merek_kendaraan": req.merek_kendaraan,
                }
            )
            .eq("id", req.id_pengajuan)
            .execute()
        )

        if len(response.data) > 0:
            return {
                "status": "sukses",
                "pesan": f"Status kendaraan: {status_baru}",
                "data": response.data[0],
            }
        else:
            raise HTTPException(
                status_code=404, detail="Data pengajuan tidak ditemukan."
            )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Terjadi kesalahan sistem: {str(e)}"
        )


# ==========================================
# 9. ENDPOINT INSPEKSI SECURITY (KELUAR)
# ==========================================
@app.put("/api/inspeksi-keluar")
async def proses_inspeksi_keluar(req: InspeksiKeluar):
    try:
        response = (
            supabase.table("pengajuan")
            .update(
                {
                    "odo_awal": req.odo_awal,
                    "bbm_awal": req.bbm_awal,
                    "status_pengajuan": "sedang_dipakai",
                }
            )
            .eq("id", req.id_pengajuan)
            .execute()
        )

        if len(response.data) > 0:
            return {
                "status": "sukses",
                "pesan": "Kendaraan resmi keluar.",
                "data": response.data[0],
            }
        else:
            raise HTTPException(
                status_code=404, detail="Data pengajuan tidak ditemukan."
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Terjadi kesalahan sistem: {str(e)}"
        )


# ==========================================
# 10. ENDPOINT UPLOAD FOTO KENDARAAN
# ==========================================
@app.post("/api/upload-foto")
async def upload_foto_kendaraan(
    id_pengajuan: int = Form(...),
    tipe_inspeksi: str = Form(...),
    posisi_foto: str = Form(...),
    file: UploadFile = File(...),
):
    try:
        file_bytes = await file.read()
        ekstensi = file.filename.split(".")[-1]

        nama_file = f"pengajuan_{id_pengajuan}_{tipe_inspeksi}_{posisi_foto}.{ekstensi}"

        try:
            supabase.storage.from_("kendaraan-dokumen").upload(
                path=nama_file,
                file=file_bytes,
                file_options={"content-type": file.content_type},
            )
        except:
            supabase.storage.from_("kendaraan-dokumen").update(
                path=nama_file,
                file=file_bytes,
                file_options={"content-type": file.content_type},
            )

        url_publik = supabase.storage.from_("kendaraan-dokumen").get_public_url(
            nama_file
        )

        kolom_db = f"foto_{tipe_inspeksi}_{posisi_foto}"
        supabase.table("pengajuan").update({kolom_db: url_publik}).eq(
            "id", id_pengajuan
        ).execute()

        return {
            "status": "sukses",
            "pesan": f"Foto {posisi_foto} disimpan!",
            "url_foto": url_publik,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengunggah foto: {str(e)}")


# ==========================================
# 11. ENDPOINT INSPEKSI SECURITY (MASUK)
# ==========================================
@app.put("/api/inspeksi-masuk")
async def proses_inspeksi_masuk(req: InspeksiMasuk):
    try:
        response = (
            supabase.table("pengajuan")
            .update(
                {
                    "odo_akhir": req.odo_akhir,
                    "bbm_akhir": req.bbm_akhir,
                    "catatan_security": req.catatan_security,
                    "status_pengajuan": "menunggu_konfirmasi_user",
                }
            )
            .eq("id", req.id_pengajuan)
            .execute()
        )

        if len(response.data) > 0:
            return {
                "status": "sukses",
                "pesan": "Kendaraan kembali, menunggu konfirmasi user.",
                "data": response.data[0],
            }
        else:
            raise HTTPException(
                status_code=404, detail="Data pengajuan tidak ditemukan."
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Terjadi kesalahan sistem: {str(e)}"
        )


# ==========================================
# 12. ENDPOINT MENGAMBIL DATA KENDARAAN
# ==========================================
@app.get("/api/kendaraan")
async def get_semua_kendaraan():
    try:
        response = supabase.table("kendaraan").select("*").execute()
        return {"status": "sukses", "data": response.data}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal memuat data kendaraan: {str(e)}"
        )


# ==========================================
# 13. ENDPOINT MENGAMBIL KATALOG TTD KARYAWAN
# ==========================================
@app.get("/api/katalog-ttd")
async def get_katalog_ttd():
    try:
        response = supabase.table("karyawan").select("nama, ttd_url").execute()

        katalog = {
            item["nama"]: item["ttd_url"] for item in response.data if item["ttd_url"]
        }

        return {"status": "sukses", "data": katalog}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal memuat katalog TTD: {str(e)}"
        )


# ==========================================
# 14. ENDPOINT KONFIRMASI PEMOHON (E-SIGNATURE)
# ==========================================
@app.put("/api/konfirmasi-pemohon")
async def proses_konfirmasi_pemohon(req: KonfirmasiUser):
    try:
        if req.is_setuju:
            data_update = {
                "status_pengajuan": "selesai",
                "ttd_pemohon_timestamp": req.timestamp_setuju,
            }
        else:
            data_update = {
                "status_pengajuan": "banding",
                "alasan_banding": req.alasan_banding,
            }

        response = (
            supabase.table("pengajuan")
            .update(data_update)
            .eq("id", req.id_pengajuan)
            .execute()
        )

        if len(response.data) > 0:
            return {
                "status": "sukses",
                "pesan": "Konfirmasi berhasil diproses.",
                "data": response.data[0],
            }
        else:
            raise HTTPException(
                status_code=404, detail="Data pengajuan tidak ditemukan."
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Terjadi kesalahan sistem: {str(e)}"
        )


# ==========================================
# 15. SERVING FRONTEND (STATIC FILES)
# ==========================================
# CATATAN: Bagian ini WAJIB berada di paling akhir file, setelah semua rute API selesai didefinisikan.
try:
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(backend_dir)
    frontend_dir = os.path.join(project_root, "frontend")

    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")

except Exception:
    print(
        "\n[PERINGATAN] Direktori 'frontend' tidak dapat ditemukan. Penyajian file statis akan dinonaktifkan."
    )
    print(
        "Pastikan folder 'frontend' dan 'backend' berada di dalam direktori induk yang sama."
    )
    print(
        "Anda masih dapat menggunakan API, tetapi Anda perlu membuka 'frontend/index.html' secara manual di browser Anda.\n"
    )
