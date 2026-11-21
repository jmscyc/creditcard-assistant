/**
 * ============================================================================
 * 💳 信用卡付款小幫手 - Google Sheet 同步後端 (Google Apps Script)
 * ============================================================================
 * 部署說明：
 * 1. 打開 Google Drive 建立一個新的 Google Sheet，隨意命名（如：信用卡設定資料庫）。
 * 2. 點選頂部選單【擴充功能】->【Apps Script】。
 * 3. 清空原本的程式碼，將本檔案內容全部複製貼上。
 * 4. 點選右上角【部署】->【新部署】。
 * 5. 類型選擇【網頁應用程式 (Web App)】：
 *    - 說明：信用卡小幫手同步 API
 *    - 執行身分：我 (你的帳號)
 *    - 誰可以存取：任何人 (Anyone)  <-- 重要！這樣 GitHub Pages 才能免帳密跨裝置連線
 * 6. 點擊【部署】，複製產生的【網頁應用程式網址】(結尾是 /exec)。
 * 7. 將該網址貼到小幫手的設定頁面中，即可完成跨裝置雲端同步！
 * ============================================================================
 */

function doGet(e) {
  var sheet = getOrCreateSheet();
  var rows = sheet.getDataRange().getValues();
  
  if (rows.length <= 1) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      data: null,
      message: "Sheet is empty"
    })).setMimeType(ContentService.MimeType.JSON);
  }

  // 取得最新一筆設定記錄
  var lastRow = rows[rows.length - 1];
  var settingsJson = lastRow[2]; // 第3欄存放 JSON 字串
  var updatedAt = lastRow[0];

  return ContentService.createTextOutput(JSON.stringify({
    status: "success",
    data: JSON.parse(settingsJson),
    updatedAt: updatedAt
  })).setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  try {
    var sheet = getOrCreateSheet();
    var postData = JSON.parse(e.postData.contents);
    var settings = postData.settings;
    var userDevice = postData.device || "Browser";
    var now = new Date();

    // 寫入一行：時間戳記、裝置/來源、JSON 設定資料
    sheet.appendRow([now, userDevice, JSON.stringify(settings)]);

    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      message: "雲端 Google Sheet 同步儲存成功！",
      timestamp: now
    })).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

function getOrCreateSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("CardSettings");
  if (!sheet) {
    sheet = ss.insertSheet("CardSettings");
    sheet.appendRow(["更新時間", "裝置來源", "卡片與權益設定 (JSON)"]);
    sheet.setFrozenRows(1);
  }
  return sheet;
}
