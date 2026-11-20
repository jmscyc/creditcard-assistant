# 💳 信用卡付款小幫手 (Credit Card Payment Assistant)

專門爬取 **符碼記憶 (fuma.me)** 與 **這就是人生 (beurlife.com)** 最新卡片權益的智能推薦系統。  
出門結帳、網購刷卡前，只要輸入通路或金額，立刻告訴你刷哪張卡回饋最高、回饋幾 %、有沒有上限，並**嚴格排除看得到吃不到的新戶加碼**！

---

## 🚀 【新手入門】怎麼開始使用？從哪裡開啟？

不管是在電腦本機、遠端主機還是手機，請依照以下步驟直接開啟：

### 步驟 1：下載專案到電腦
打開你的終端機 (Terminal / PowerShell)，執行：
```bash
git clone https://github.com/jmscyc/creditcard-assistant.git
cd creditcard-assistant
```

---

### 步驟 2：開啟程式（兩種方式，任選一種）

#### 🟢 方式 A：【最推薦】一鍵自動開機（免手動設定）
專案內建自動化腳本，會**自動建環境、自動裝套件並直接開啟**：
```bash
./scripts/start.sh
```

#### 🟡 方式 B：手動指令啟動
```bash
# 建立並啟用 Python 虛擬環境
python3 -m venv .venv
source .venv/bin/activate       # Windows 請用: .venv\Scripts\activate

# 安裝所需套件
pip install -r requirements.txt

# 啟動服務
python app.py
```

---

### 步驟 3：從哪裡開啟對話視窗？

當終端機顯示 `🚀 啟動信用卡付款小幫手 Web 服務: http://0.0.0.0:8000` 後：

👉 **請打開任何瀏覽器（Chrome / Safari / Edge / 手機瀏覽器）訪問：**
```
http://localhost:8000
```
*(如果是在遠端伺服器或雲端環境執行，請將 localhost 換成您的伺服器 IP 或網址)*

---

## 📱 使用技巧與特色功能

進入網頁對話介面後，您可以：
1. **輸入通路或店家**：例如輸入 `LINE Pay`、`日本實體`、`全聯`、`加油`。
2. **輸入金額直接試算**：例如輸入 `蝦皮 3000` 或 `機票 25000`，小幫手會幫你算出：**「預估可賺 300 元/點」**！
3. **陷阱條款自動示警**：若在超商或繳費時使用會被排除回饋的卡片，會跳出 ⚠️ 警示提醒。
4. **一鍵複製卡片推薦**：卡片右上角設有 📋 複製按鈕，秒複製給家人朋友。
5. **右上角功能按鈕**：
   - 🔄 **更新權益**：即時重新抓取兩大信用卡達人部落格最新文章。
   - 🗑️ **清空紀錄**：隨時一鍵清空畫面。

---

## 🤖 【給 AI / 開發者改版指南】（單檔極簡架構）

> 💡 **核心架構精簡化聲明**：
> 為了方便您未來**單檔下載、提供給 AI 改版、或是迅速閱讀微調**，本專案將整套系統的核心（爬蟲、時效過濾、排除新戶演算法、推薦大腦、FastAPI 服務、HTML 前端、Telegram Bot）**全部收納在同一隻核心檔案：**
> 
> 👉 **`app.py`** 👈
>
> 🎯 **未來如需交給 AI（ChatGPT、Claude、Gemini）修改或升級，您只需要下載/提供：**
> 1. **`app.py`**（所有 Python 邏輯、爬蟲、推薦大腦、UI 介面都在裡面，AI 一眼就能看完修改）
> 2. **`data/cards.json`**（結構化卡片與回饋點數資料庫，選用）
>
> 若只想讓 AI 單純更新推薦邏輯或 UI 介面，甚至只需下載 **`app.py`** 一個檔案即可完成改版！

---

## 📁 檔案結構說明

```
creditcard-assistant/
├── app.py                ⭐【核心主程式】包含爬蟲、過濾器、推薦大腦、Web UI、Telegram Bot
├── data/
│   └── cards.json        ⭐【卡片資料庫】各銀行卡片、通路與回饋上限資料
├── scripts/
│   └── start.sh          ⭐【一鍵啟動腳本】免手動設定，自動建環境開機
├── requirements.txt      依賴套件清單 (fastapi, uvicorn, beautifulsoup4 等)
├── .env.example          環境變數範例 (TELEGRAM_BOT_TOKEN)
└── README.md             專案說明、啟動指引與 AI 改版指南
```

---

## 📲 Telegram 機器人模式 (選用)

如果您想在手機 Telegram 直接隨時發問：
1. `cp .env.example .env` 並填入向 `@BotFather` 申請的 Token。
2. 執行 `python app.py --bot` 即可啟動！

---

## 📜 授權聲明

本專案爬取之文章來源版權屬原作者所有：
- [符碼記憶 (fuma.me)](https://www.fuma.me/)
- [這就是人生 (beurlife.com)](https://www.beurlife.com/)
