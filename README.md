# 💳 信用卡付款小幫手 (Credit Card Payment Assistant)

專門爬取 **符碼記憶 (fuma.me)** 與 **這就是人生 (beurlife.com)** 最新卡片權益的智能推薦系統。

---

## 📌 【給使用者與 AI 開發者改版指南】（必讀）

> 💡 **核心架構精簡化聲明**：
> 為了方便您未來**單檔下載、提供給 AI 改版、或是迅速閱讀微調**，本專案將整套系統的核心（爬蟲、時效過濾、排除新戶演算法、推薦大腦、FastAPI 服務、HTML 前端、Telegram Bot）**全部收納在同一隻核心檔案：**
> 
> 👉 **`app.py`** 👈
>
> 🎯 **未來如需交給 AI 修改或升級，您只需要下載/提供以下 2 個檔案即可：**
> 1. **`app.py`**（所有 Python 邏輯、爬蟲、推薦大腦、UI 介面都在裡面，AI 一眼就能看完修改）
> 2. **`data/cards.json`**（結構化卡片與回饋點數資料庫）
>
> 若只想讓 AI 單純更新推薦邏輯或 UI 介面，甚至只需下載 **`app.py`** 一個檔案即可完成改版！

---

## ✨ 核心特點

1. **嚴格排除新戶加碼 (No New Customer Traps)**：
   - 拒絕虛高宣傳！自動過濾「新戶首刷禮」、「核卡 N 天內加碼」等限制，只推薦**既有卡友/常態人人可拿**的真實回饋率。
2. **時效過濾與上下半年區隔 (Validity & Period Filtering)**：
   - 信用卡權益通常每半年（上半年 1~6 月、下半年 7~12 月）或每季調整。
   - 系統依據文章發布時間與年份標籤，自動過濾已過期或太久以前的舊資訊。
3. **雙通道對話互動**：
   - **現代化 Web 介面**：手機/電腦自適應暗黑模式，內建常用通路快捷鍵（LINE Pay、日本日幣、蝦皮、超商繳費、加油、外送）。
   - **Telegram Bot**：結帳付款時打開手機 Telegram 輸入通路名稱秒查。
4. **即時爬蟲與資料更新**：
   - 點擊網頁右上角「更新權益」或執行命令列，即時掃描兩大部落格最新攻略文章。

---

## 🚀 快速開始

### 1. 安裝環境與套件

```bash
cd creditcard-assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 一鍵啟動 Web 對話視窗

```bash
python app.py
```
打開瀏覽器訪問 `http://localhost:8000` 即可隨時對話詢問！

### 3. 啟動 Telegram Bot (選用)

```bash
# 複製設定檔並填入向 @BotFather 申請的 Token
cp .env.example .env

# 啟動 Telegram 機器人
python app.py --bot
```

### 4. 執行手動爬蟲更新

```bash
python app.py --crawl
```

---

## 📁 檔案結構說明

```
creditcard-assistant/
├── app.py                ⭐【核心主程式】包含爬蟲、過濾器、推薦大腦、Web UI、Telegram Bot
├── data/
│   └── cards.json        ⭐【卡片資料庫】各銀行卡片、通路與回饋上限資料
├── requirements.txt      依賴套件清單 (fastapi, uvicorn, beautifulsoup4, python-telegram-bot 等)
├── .env.example          環境變數範例 (TELEGRAM_BOT_TOKEN)
├── scripts/
│   └── start.sh          一鍵啟動腳本
└── README.md             專案說明與改版指南
```

## 📜 授權聲明

本專案爬取之文章來源版權屬原作者所有：
- [符碼記憶 (fuma.me)](https://www.fuma.me/)
- [這就是人生 (beurlife.com)](https://www.beurlife.com/)
