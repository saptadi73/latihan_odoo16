```markdown
// filepath: c:\latihanodoo\dynamic_accounts_report\docs\CONSOLIDATION_GUIDE.md
# Panduan Konsolidasi Multi-Company Balance Sheet

Dokumen ini menjelaskan cara menggunakan fitur konsolidasi multi-company dengan eliminasi intercompany di modul Dynamic Accounts Report.

---

## Fitur Utama

- ✅ Konsolidasi balance sheet dari multiple companies
- ✅ Grouping per account.group dengan summary opening/period/ending
- ✅ Eliminasi otomatis transaksi intercompany
- ✅ Support filter periode dan analytic accounts
- ✅ Simpan hasil konsolidasi ke record

---

## Langkah-Langkah Konsolidasi

### 1. Akses Menu Consolidation

**Path:** `Accounting → Configuration → Account Consolidation`

![Menu Location](screenshot_menu.png)

---

### 2. Buat Record Konsolidasi Baru

Klik **Create** untuk membuat record baru:

| Field                          | Deskripsi                                      | Contoh                      |
|--------------------------------|------------------------------------------------|-----------------------------|
| **Consolidation Name**         | Nama identifikasi konsolidasi                  | `Q4 2024 Group Consolidation` |
| **Date From**                  | Tanggal awal periode                           | `2024-10-01`                |
| **Date To**                    | Tanggal akhir periode                          | `2024-12-31`                |
| **Companies to Consolidate**   | Pilih multiple companies untuk dikonsolidasi   | `Company A`, `Company B`, `Company C` |
| **Intercompany Elimination Accounts** | Akun yang mewakili transaksi antar-perusahaan | `Intercompany AR`, `Intercompany AP` |

---

### 3. Konfigurasi Elimination Accounts

**Penting:** Elimination accounts adalah akun-akun yang digunakan untuk transaksi antar-perusahaan dalam satu group, misalnya:

- **Intercompany Receivables** (Piutang antar-perusahaan)
- **Intercompany Payables** (Hutang antar-perusahaan)
- **Intercompany Revenue/Expense** (Pendapatan/Biaya antar-perusahaan)

**Cara setting:**
1. Klik field **Intercompany Elimination Accounts**
2. Pilih akun-akun yang relevan dari daftar
3. Domain filter otomatis menampilkan akun dari companies yang dipilih

**Contoh skenario eliminasi:**
```
Company A → Piutang ke Company B: Rp 100,000
Company B → Hutang ke Company A: Rp 100,000

Setelah eliminasi: Net balance = 0 (transaksi internal dihapus)
```

---

### 4. Proses Konsolidasi

Setelah semua field terisi:

1. Klik tombol **Process Consolidation** (button hijau di header)
2. System akan:
   - Mengambil data balance sheet dari semua companies
   - Mengelompokkan per account.group
   - Menghitung opening/period/ending balance
   - Mengeliminasi saldo pada elimination accounts
   - Menyimpan hasil ke field `result_json`
3. Status berubah dari **Draft** → **Consolidated**
4. Notifikasi sukses muncul: `"Successfully consolidated X companies"`

---

### 5. Hasil Konsolidasi

Hasil konsolidasi tersimpan dalam format JSON di field `result_json` dengan struktur:

```json
{
  "status": "success",
  "consolidation_info": {
    "date_from": "2024-10-01",
    "date_to": "2024-12-31",
    "companies": [
      {"id": 1, "name": "Company A"},
      {"id": 2, "name": "Company B"}
    ],
    "elimination_accounts_count": 3
  },
  "assets": {
    "groups": [
      {
        "group_id": 10,
        "group_name": "Current Assets",
        "opening_balance": 500000,
        "period_balance": 100000,
        "ending_balance": 600000,
        "accounts": [
          {
            "account_code": "1101",
            "account_name": "Cash",
            "opening_balance": 200000,
            "period_balance": 50000,
            "ending_balance": 250000
          }
        ]
      }
    ],
    "summary": {
      "opening_balance": 500000,
      "period_balance": 100000,
      "ending_balance": 600000
    }
  },
  "liabilities": { /* struktur sama seperti assets */ },
  "equity": { /* struktur sama seperti assets */ },
  "summary": {
    "assets_ending": 600000,
    "liabilities_ending": 300000,
    "equity_ending": 300000,
    "balanced": true,
    "difference": 0.0
  }
}
```

---

### 6. Edit atau Reset Konsolidasi

**Reset ke Draft:**
- Klik tombol **Reset to Draft** jika perlu edit parameter
- Status kembali ke **Draft**
- Bisa edit companies/elimination accounts
- Proses ulang dengan **Process Consolidation**

---

## API Endpoints (untuk Frontend/Integration)

### A. Get Consolidation by ID
```http
POST /api/consolidation/by_id
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "consolidation_id": 5
  },
  "id": 1
}
```

**Response:** Hasil konsolidasi lengkap dalam format JSON

---

### B. Process Consolidation via API
```http
POST /api/consolidation/process
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "consolidation_id": 5
  },
  "id": 1
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Consolidation processed successfully"
}
```

---

### C. Get Grouped Balance Sheet Consolidation
```http
POST /api/consolidation/balance_sheet_grouped
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "date_from": "2024-01-01",
    "date_to": "2024-12-31",
    "company_ids": [1, 2, 3],
    "elimination_account_ids": [100, 101],
    "analytic_account_ids": [5, 7]
  },
  "id": 1
}
```

---

## Troubleshooting

### Error: "Please select at least one company to consolidate"
**Solusi:** Pastikan field **Companies to Consolidate** sudah diisi minimal 1 company.

---

### Hasil konsolidasi tidak seimbang (balanced = false)
**Kemungkinan penyebab:**
1. Ada transaksi yang belum posted di salah satu company
2. Elimination accounts kurang lengkap
3. Ada transaksi manual yang tidak tercatat

**Solusi:**
- Cek field `summary.difference` untuk melihat selisih
- Review per-company data di `per_company` section
- Pastikan semua journal entry sudah posted

---

### Elimination tidak bekerja dengan benar
**Checklist:**
1. ✅ Akun elimination sudah ditandai di field **Intercompany Elimination Accounts**?
2. ✅ Akun tersebut benar-benar dipakai di transaksi kedua companies?
3. ✅ Periode date_from/date_to sudah cover transaksi intercompany?

**Cara debug:**
- Lihat section `eliminations_summary` di hasil JSON
- Cek `by_account` untuk detail eliminasi per akun
- Bandingkan dengan `per_company` data sebelum eliminasi

---

## Best Practices

### 1. Setup Chart of Accounts yang Konsisten
- Gunakan account.group yang sama di semua companies
- Code prefix akun sebaiknya seragam (misal: 1xxx untuk assets)

### 2. Tandai Akun Intercompany dengan Jelas
- Buat akun khusus untuk transaksi intercompany
- Gunakan naming convention: `Intercompany - [Type]`
- Contoh: `Intercompany Receivables`, `Intercompany Payables`

### 3. Rekonsiliasi Berkala
- Proses konsolidasi setiap end-of-month/quarter
- Simpan record konsolidasi untuk audit trail
- Export hasil ke Excel/PDF untuk management reporting

### 4. Validasi Eliminasi
- Periksa `eliminations.total_eliminated` vs manual calculation
- Review `eliminations.by_account` untuk detail per akun
- Pastikan `summary.balanced = true`

---

## Contoh Use Case

### Skenario: Group ABC dengan 3 Perusahaan

**Companies:**
- Company A (Holding/Parent)
- Company B (Subsidiary 1)
- Company C (Subsidiary 2)

**Intercompany Transactions:**
```
Company A → Company B: Piutang Rp 50,000,000
Company B → Company A: Hutang Rp 50,000,000

Company A → Company C: Piutang Rp 30,000,000
Company C → Company A: Hutang Rp 30,000,000
```

**Setup Consolidation:**
1. Name: `ABC Group - Q4 2024`
2. Date: `2024-10-01` to `2024-12-31`
3. Companies: `Company A`, `Company B`, `Company C`
4. Elimination Accounts:
   - `Intercompany Receivables` (Company A)
   - `Intercompany Payables` (Company B, C)

**Expected Result:**
- Total elimination: Rp 80,000,000 (50M + 30M)
- Consolidated balance: Hanya transaksi eksternal (di luar group)
- `balanced = true`

---

## Support & Troubleshooting

**Log Location:** Check Odoo server log untuk detail error:
```bash
tail -f /var/log/odoo/odoo-server.log | grep CONSOLIDATION
```

**Debug Mode:**
- Aktifkan developer mode di Odoo
- Inspect field `result_json` untuk melihat raw data
- Check per-company balance sebelum eliminasi di section `per_company`

---

## Changelog

### Version 1.0 (2024-11-29)
- ✅ Initial release
- ✅ Multi-company consolidation
- ✅ Intercompany elimination
- ✅ Grouping by account.group
- ✅ API endpoints untuk integration

---

## Contact

Untuk pertanyaan atau issue, hubungi tim development atau buat ticket di sistem support.
```