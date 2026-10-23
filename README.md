# Signal Engine - ระบบส่งสัญญาณเทรด

Signal Engine สำหรับเทรด XAUUSD และ EURUSD บน MT5 iOS โดยไม่มีค่าใช้จ่ายรายเดือน

---

## คุณสมบัติ

| Feature | รายละเอียด |
|---------|-----------|
| **Data Source** | Yahoo Finance API (ฟรี) |
| **Interactive Bot** | ควบคุมผ่าน Telegram พร้อมปุ่มกด |
| **Risk Management** | Risk 1-1.5% ต่อเทรด, Circuit Breaker |
| **News Filter** | บล็อกสัญญาณ ±30 นาทีรอบข่าวสำคัญ |
| **ATR Filter** | กรองสภาวะตลาดผันผวน |
| **Multi-Language** | ไทย / ไทย-ศัพท์เฉพาะ / English |

---

## วิธีติดตั้ง

### 1. ติดตั้ง Dependencies

```bash
pip install -r requirements.txt
```

### 2. ตั้งค่า Telegram Bot

1. เปิด Telegram → ค้นหา `@BotFather`
2. ส่ง `/newbot`
3. ตั้งชื่อและ username
4. คัดลอก **Token** ที่ได้

### 3. หา Chat ID

1. สร้าง chat กับ bot
2. ส่งข้อความ `/start`
3. เปิด browser:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
4. หา `"chat":{"id":XXXXXXX}` → นี่คือ Chat ID

### 4. ตั้งค่าใน `config/settings.yaml`

```yaml
telegram:
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
```

---

## วิธีใช้งาน

### เริ่มระบบ

```bash
python run_bot.py
```

### คำสั่ง Telegram

| Command | คำอธิบาย |
|---------|----------|
| `/start` | เริ่มต้น + แสดงปุ่มควบคุม |
| `/help` | วิธีใช้งาน |
| `/status` | สถานะ Engine |
| `/backtest` | รัน Backtest |
| `/settings` | ดูการตั้งค่า |
| `/pause` | หยุดส่งสัญญาณ |
| `/resume` | เปิดส่งสัญญาณ |
| `/force` | บังคับตรวจสอบ |
| `/lang` | เปลี่ยนภาษา |

### ปุ่มควบคุม

| ปุ่ม | คำอธิบาย |
|------|----------|
| 📊 สถานะ | ดูสถานะ Engine |
| 🔄 Backtest | รัน Backtest |
| ⏸️ หยุด | หยุดส่งสัญญาณชั่วคราว |
| ▶️ เปิด | เปิดส่งสัญญาณต่อ |
| ⚙️ ตั้งค่า | ดูการตั้งค่าปัจจุบัน |
| 🇹🇭 ไทย | เปลี่ยนเป็นภาษาไทย |
| 🇬🇧 English | เปลี่ยนเป็นภาษาอังกฤษ |

---

## การตั้งค่า

### Risk Management

| Parameter | Default | คำอธิบาย |
|-----------|---------|----------|
| `capital_usc` | 5500 | เงินทุน (USC - Cent Account) |
| `risk_per_trade_pct` | 1.0 | Risk ต่อเทรด (%) |
| `max_daily_losses` | 2 | ขาดสูงสุดต่อวัน |
| `max_daily_drawdown_pct` | 3.0 | Drawdown สูงสุดต่อวัน (%) |

### Signal Settings

| Parameter | Default | คำอธิบาย |
|-----------|---------|----------|
| `ttl_minutes` | 60 | เวลาหมดอายุของสัญญาณ (นาที) |
| `cooldown_minutes` | 15 | เวลาระหว่างสัญญาณ (นาที) |

---

## โครงสร้างโปรเจค

```
SIG/
├── config/
│   └── settings.yaml        # การตั้งค่าทั้งหมด
├── src/
│   ├── main.py              # Entry point
│   ├── engine.py            # Signal Engine หลัก
│   ├── config.py            # Config manager
│   ├── data_feed/           # ดึงข้อมูลราคา
│   │   └── api_feed.py      # Yahoo Finance API
│   ├── strategy/            # Strategy สร้างสัญญาณ
│   │   └── trend_momentum.py # EMA + RSI + Structure
│   ├── risk/                # Risk Management
│   │   ├── position_sizer.py # คำนวณ Lot Size
│   │   └── circuit_breaker.py # ล็อคเมื่อขาดเยอะ
│   ├── filters/             # ตัวกรอง
│   │   ├── news_guard.py    # กรองข่าว
│   │   └── atr_filter.py    # กรองความผันผวน
│   ├── bot/                 # Telegram Bot
│   │   └── telegram_bot.py  # Interactive bot
│   └── backtest/            # Backtest
│       └── sanity_check.py  # ทดสอบ Strategy
├── logs/                    # Log files
├── run_bot.py               # สคริปต์รันหลัก
└── requirements.txt         # Dependencies
```

---

## ตัวอย่างสัญญาณ

```
🟢 BUY XAUUSD

📊 LIMIT ORDER

📍 Entry: 2650.50
🛑 SL: 2645.00
🎯 TP: 2660.00

📏 Lot: 0.02
💰 Risk: 55.0 USC (1.0%)
📈 R:R: 1.50

⏰ หมดอายุ: 15:30
⚠️ ยกเลิกถ้าถึง: 2647.75000

Strategy: TrendMomentum | TF: M15
```

---

## คำศัพท์เฉพาะ

| Term | ความหมาย |
|------|----------|
| **Entry** | ราคาเข้าเทรด |
| **SL (Stop Loss)** | จุดตัดขาดทุน |
| **TP (Take Profit)** | จุดตัดกำไร |
| **Lot** | ขนาด Position |
| **USC** | US Cent (สกุลเงิน Cent Account) |
| **R:R** | Risk:Reward Ratio |
| **TTL** | Time-To-Live (เวลาหมดอายุ) |
| **Circuit Breaker** | ระบบล็อคเมื่อขาดเกินขีดจำกัด |
| **ATR** | Average True Range (วัดความผันผวน) |
| **Backtest** | ทดสอบ strategy ย้อนหลัง |
| **Expectancy** | กำไรเฉลี่ยต่อเทรด (หน่วย R) |

---

## ข้อควรระวัง

- ระบบนี้ใช้ข้อมูลจาก Yahoo Finance ซึ่งอาจมีความแตกต่างจากราคา broker
- มี Spread Buffer 5 pips เพื่อชดเชยความแตกต่าง
- ทดสอบ Backtest ก่อนใช้งานจริง
- เทรดมีความเสี่ยง ใช้เงินที่พร้อมเสียได้

---

## License

MIT License - ใช้งานได้อย่างอิสระ

---

## ผู้พัฒนา

สร้างด้วย Claude Code

