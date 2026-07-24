# Chess God Board

Windows desktop app (PySide6) — กระดานหมากรุกข้างจอ + **Stockfish** สำหรับฝึก/วิเคราะห์

> **ขอบเขต:** ใช้เพื่อ practice / analysis เท่านั้น  
> แอป**ไม่**ควบคุมเมาส์ ไม่วิ่งเดินอัตโนมัติในเกม และไม่เลี่ยง anti-cheat

## แนวคิด

| บนกระดาน | ความหมาย |
|----------|----------|
| **ด้านล่าง** | คุณเสมอ |
| **ด้านบน** | คู่แข่ง |

1. คุณ**ใส่การเดินของคู่แข่งเอง** (คลิกช่อง หรือพิมพ์ `e2e4`)
2. ตาคุณ → Stockfish วิเคราะห์ แสดงลูกศร Best Move
3. คุณเดินในเกมจริงตามลูกศร แล้วกด **เดินตาม Best Move**

## ความต้องการ

- Windows 10/11
- Python **3.12–3.13**
- [Stockfish](https://stockfishchess.org/download/) (แยกดาวน์โหลด — GPL, ไม่ฝังใน build)

## ติดตั้ง & รัน

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:PYTHONPATH = (Get-Location).Path
python -m app
```

วาง `engines\stockfish.exe` หรือเลือก path ในแอปด้วยปุ่ม **Stockfish…**  
รายละเอียด: [`engines/README.md`](engines/README.md) · [`scripts/download_stockfish_note.md`](scripts/download_stockfish_note.md)

## คุณสมบัติหลัก

- กระดานข้างจอ + Always on top
- วิเคราะห์แบบมีขอบเขตเวลา (ไม่ปั่น CPU ตลอด) + **ponder** (คิดล่วงหน้าตาคู่แข่ง)
- **Opening Book** (polyglot `.bin`) — เปิด/ปิดด้วยติ๊ก **ตำรา**
- **Syzygy tablebase** — จบเกม ≤5 หมาก (วางที่ `engines/syzygy/` หรือ `python tools/download_syzygy_345.py`)
- **Overlay** บนเกมจริง — ลูกศร Best Move / กระดานเงา / โหมดคลิกบันทึกการเดิน
- เลือกฝ่าย White (Light Cherry) / Black (Dark Cherry)

## ปุ่มหลัก

| ปุ่ม | หน้าที่ |
|------|---------|
| คลิกต้นทาง→ปลายทาง | บันทึกการเดิน |
| **เดินตาม Best Move** | บันทึกตาคุณตาม Stockfish |
| **วิเคราะห์ใหม่** | ให้ engine คิดใหม่ |
| **Undo** / **เกมใหม่** | ย้อน / เริ่มเกม |
| **ตั้งตำแหน่ง Overlay** | ลากมุม 1–4 ให้ตรงกระดานในเกม |

โหมดปกติ Overlay เป็น click-through — คลิกทะลุไปเกมได้  
เมื่อเปิด **คลิก Overlay** คลิกจะไม่ทะลุ (ใช้บันทึกการเดินบนเกม)

## ทดสอบ

```powershell
pytest -q
python tools\smoke_import.py
```

## สร้าง .exe (ทางเลือก)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

`stockfish.exe` **ไม่**ถูก bundle — ผู้ใช้ติดตั้งเอง

## โครงสร้างโปรเจกต์ (สรุป)

```
app/            entry point
gui/            God Board UI + widgets
chess_core/     FEN / validation / special moves
chess_engine/   Stockfish UCI, ponder, opening book
overlay/        transparent overlay + setup frame
profiles/       calibration profiles (persist)
storage/        config + PGN export
engines/        local Stockfish / book / syzygy (gitignored binaries)
tests/          unit tests (logic only)
```

ข้อมูลผู้ใช้เก็บที่ `%APPDATA%\ChessVisionAssistant\` (config, profiles, logs, exports)

## License

โค้ดใน repo นี้ใช้ตามที่ระบุใน repository  
**Stockfish** เป็นซอฟต์แวร์แยกภายใต้ **GPL** — ดาวน์โหลดและใช้งานตามเงื่อนไขของ upstream
