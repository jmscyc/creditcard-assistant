# 💳 信用卡付款小幫手 (Credit Card Payment Assistant)

專門爬取 **符碼記憶 (fuma.me)** 與 **這就是人生 (beurlife.com)** 最新卡片權益的智能推薦系統。  
出門結帳、網購刷卡前，只要輸入通路或金額，立刻告訴你刷哪張卡回饋最高、回饋幾 %、有沒有上限，並**嚴格排除看得到吃不到的新戶加碼**！

---

## 🌐 線上免安裝直接使用 (GitHub Pages)

出門在手機點開即可使用，完全免開電腦、免安裝任何 App：
* 📱 **信用卡付款小幫手（主對話頁）**：  
  👉 **[https://jmscyc.github.io/creditcard-assistant/](https://jmscyc.github.io/creditcard-assistant/)**
* ⚙️ **我的卡片與特別權益設定（含 Google Sheet 雲端同步）**：  
  👉 **[https://jmscyc.github.io/creditcard-assistant/cards-settings.html](https://jmscyc.github.io/creditcard-assistant/cards-settings.html)**

---

## ☁️ 【重點教學】Google Sheet 跨裝置雲端同步設定

想要在**電腦選好卡片，出門拿出手機不用重選直接同步**？  
點擊網頁上的 **「設定教學與代碼」** 或依照以下 3 步即可完成：

### 第 1 步：建立 Google 試算表
點擊下方專用捷徑直接開啟一份全新空白試算表：
👉 **[sheets.new](https://sheets.new)**

### 第 2 步：貼上同步代碼 (Google Apps Script)
1. 在試算表頂部選單點選：**【擴充功能】 ➔ 【Apps Script】**。
2. 清空原本的程式碼。
3. 在設定網頁點選 **「📋 一鍵複製完整同步腳本」**（或複製專案中的 [`google-apps-script.js`](./google-apps-script.js)）並貼上儲存。

### 第 3 步：關鍵權限設定（防呆標註）
1. 在 Apps Script 畫面右上角點選 **【部署】 ➔ 【新部署】**。
2. 齒輪圖示選擇 **「網頁應用程式 (Web App)」**：
   * **說明**：信用卡小幫手同步
   * **執行身分**：選 **「我」**
   * **誰可以存取**：**務必選 👉「任何人 (Anyone)」**  
     *(⚠️ 防呆提醒：若未選任何人，手機未登入狀態將無法雙向讀寫試算表！)*
3. 點擊【部署】，複製產生的 **Web App 網址**（結尾是 `/exec`）。
4. 貼回設定頁的輸入框並點選 **「備份上雲端」** 即可！

---

## 📱 使用技巧與特色功能

1. **輸入通路或店家**：例如輸入 `LINE Pay`、`日本實體`、`全聯`、`加油`。
2. **輸入金額直接試算**：例如輸入 `蝦皮 3000` 或 `機票 25000`，小幫手會幫你算出：**「預估可賺 300 元/點」**！
3. **陷阱條款自動示警**：若在超商或繳費時使用會被排除回饋的卡片，會跳出 ⚠️ 警示提醒。
4. **一鍵複製卡片推薦**：卡片右上角設有 📋 複製按鈕，秒複製給家人朋友。
5. **預設推薦 5 張最優卡片**：點擊 **「查看更多卡片」** 可一鍵展開後續所有備用卡。

---

## 🤖 【給 AI / 開發者改版指南】（單檔極簡架構）

整套核心邏輯（爬蟲、時效過濾、排除新戶演算法、推薦大腦、FastAPI 服務、Telegram Bot）收納於單檔：
👉 **`app.py`** 👈

未來如需交給 AI 升級或調整，只需下載/提供：
1. **`app.py`**（核心大腦）
2. **`data/cards.json`**（卡片資料庫）
3. **`index.html`** / **`cards-settings.html`**（前端介面）

---

## 📁 檔案結構說明

```
creditcard-assistant/
├── index.html            ⭐【主對話頁】GitHub Pages 靜態前端 (支援試算、前5張卡、查看更多)
├── cards-settings.html   ⭐【設定頁】勾選皮夾卡片、會員方案、登錄活動、Google Sheet 同步彈窗
├── google-apps-script.js ⭐【同步代碼】Google Sheet 專用 Web App 腳本
├── app.py                ⭐【後端與本地服務】爬蟲、FastAPI、Telegram Bot
├── data/
│   └── cards.json        ⭐【卡片資料庫】各銀行卡片、權益與登錄活動資料
├── scripts/
│   └── start.sh          ⭐【一鍵啟動腳本】本地自動化建環境開機
├── requirements.txt      依賴套件清單
└── README.md             專案說明、啟動指引與雲端同步教學
```

---

## 🚀 【秒級零輸入】專屬同步網址與 QR Code 分享

為避免在每台新手機、平板都要手動複製長網址，系統支援 **「一鍵直連 / 掃碼同步」**：

1. **第一台裝置綁定後**：
   * 在設定頁點擊 **「🔗 複製我的專屬同步網址」** 或 **「📷 顯示同步 QR Code」**。
2. **換設備或分享給旅伴家人**：
   * **傳送專屬網址**：用 LINE 傳給自己，點開網址的瞬間，新設備便**自動綁定雲端並抓取所有卡片設定**！
   * **現場掃碼**：平板或新手機直接打開相機掃描 QR Code，打開即秒同步！
