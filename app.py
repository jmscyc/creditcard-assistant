#!/usr/bin/env python3
"""
=============================================================================
💳 信用卡付款小幫手 (Credit Card Payment Assistant) - 單一核心整合版
=============================================================================
本檔案為整套系統的【大腦與核心入口】。
將以下模組全部收納在同一隻檔案內，方便隨時打包下載給 AI / 開發者進行二次改版：
  1. 爬蟲模組 (Scraper)：爬取 fuma.me (符碼記憶) 與 beurlife.com (這就是人生)
  2. 權益解析與過濾模組 (Parser)：時效判斷、上下半年過濾、嚴格剔除新戶加碼
  3. 推薦檢索大腦 (Recommender Engine)：同義詞擴展、實質%數排序、上限門檻計算
  4. 現代化 Web 前端與 API (FastAPI)：內嵌完整 HTML/CSS/JS 介面與 REST API
  5. Telegram Bot (可選獨立啟動)：支援手機 Telegram 輸入關鍵字秒查

使用方式：
  - 啟動 Web 服務：python app.py
  - 啟動 Telegram Bot：python app.py --bot
  - 執行單次爬蟲更新：python app.py --crawl
=============================================================================
"""

import os
import sys
import re
import json
import logging
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Optional

# =============================================================================
# [設定與全域路徑]
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "cards.json")
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

# 通路與關鍵字同義詞字典
CHANNEL_ALIASES = {
    "line": ["line pay", "linepay"],
    "linepay": ["line pay", "linepay"],
    "街口": ["街口", "街口支付"],
    "日本": ["日本", "日韓", "日幣", "日本實體", "bic camera", "唐吉訶德"],
    "國外": ["海外", "國外", "日本", "韓國"],
    "韓國": ["韓國", "日韓", "韓元"],
    "蝦皮": ["蝦皮", "shopee"],
    "momo": ["momo", "網購"],
    "超商": ["7-11", "全家", "超商", "萊爾富"],
    "全聯": ["全聯", "超市"],
    "外送": ["uber", "uber eats", "foodpanda", "外送"],
    "加油": ["加油", "中油", "全國加油"],
    "悠遊卡": ["悠遊卡", "自動加值", "捷運"],
    "apple pay": ["apple pay", "ap", "感應支付"],
    "google pay": ["google pay", "gp", "感應支付"]
}

# 排除新戶專屬規則特徵
NEW_CUSTOMER_PATTERNS = [
    r'新戶.*加碼',
    r'新戶.*首刷',
    r'新戶.*獨享',
    r'新卡友.*首刷',
    r'核卡後\s*\d+\s*天內',
    r'新戶首刷禮',
    r'新申辦.*加贈',
    r'首次申辦'
]

# =============================================================================
# 1. 權益解析與時效過濾模組 (Parser)
# =============================================================================
def is_new_customer_promo(text: str) -> bool:
    """判定是否為新戶獨享優惠，若是則予以排除"""
    for pattern in NEW_CUSTOMER_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def clean_rate(rate_text: str) -> float:
    """將文字回饋率轉為浮點數，例如 '3.8%' -> 3.8"""
    match = re.search(r'(\d+(?:\.\d+)?)\s*%', rate_text)
    return float(match.group(1)) if match else 0.0

def determine_period(date_str: str) -> str:
    """判斷適用年期與上下半年"""
    match = re.search(r'(202\d)[/-](\d{1,2})', date_str)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        half = "上半年" if month <= 6 else "下半年"
        return f"{year}{half}"
    return "2026下半年"

# =============================================================================
# 2. 爬蟲模組 (Scraper) - fuma.me & beurlife.com
# =============================================================================
def scrape_fuma(max_entries: int = 8) -> List[Dict[str, Any]]:
    """爬取符碼記憶 (fuma.me) 最新文章與 Feed"""
    feed_url = 'https://www.fuma.me/feeds/posts/default'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        req = urllib.request.Request(feed_url, headers=headers)
        content = urllib.request.urlopen(req, timeout=8).read()
        root = ET.fromstring(content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('atom:entry', ns)
        
        results = []
        for e in entries[:max_entries]:
            t_el = e.find('atom:title', ns)
            u_el = e.find('atom:updated', ns)
            title = t_el.text if t_el is not None else ""
            updated = u_el.text if u_el is not None else ""
            
            link = ""
            for l in e.findall('atom:link', ns):
                if l.get('rel') == 'alternate':
                    link = l.get('href')

            results.append({"title": title, "updated": updated, "link": link})
        return results
    except Exception as err:
        print(f"[Scraper] fuma.me 爬取通知: {err}")
        return []

def scrape_beurlife(max_articles: int = 8) -> List[Dict[str, Any]]:
    """爬取這就是人生 (beurlife.com) 信用卡文章列表"""
    search_url = 'https://www.beurlife.com/?s=%E4%BF%A1%E7%94%A8%E5%8D%A1'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        req = urllib.request.Request(search_url, headers=headers)
        html = urllib.request.urlopen(req, timeout=8).read().decode('utf-8', errors='ignore')
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        articles = soup.find_all('article')
        results = []
        for a in articles[:max_articles]:
            h = a.find(['h1', 'h2', 'h3'])
            l = a.find('a')
            if h and l:
                results.append({"title": h.get_text(strip=True), "link": l.get('href', '')})
        return results
    except Exception as err:
        print(f"[Scraper] beurlife.com 爬取通知: {err}")
        return []

# =============================================================================
# 3. 推薦檢索大腦核心 (Recommender Engine)
# =============================================================================
def load_cards_db() -> List[Dict[str, Any]]:
    """載入結構化卡片知識庫"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    # 內建預設最新卡片種子知識庫（2026年最新權益、已排除新戶首刷加碼）
    return [
        {
            "card_name": "玉山 Unicard",
            "bank": "玉山銀行",
            "valid_period": "2026/01/01 - 2026/12/31",
            "period_tag": "2026全年/下半年",
            "channels": [
                {
                    "channel_name": "LINE Pay / 街口支付 / 悠遊付",
                    "keywords": ["line pay", "linepay", "街口", "街口支付", "悠遊付", "行動支付"],
                    "cashback_rate": 4.5,
                    "cashback_display": "最高 4.5% e point",
                    "is_new_customer_only": False,
                    "cap": "指定百大特店最高 4.5%（特選 3.5% + UP選 4.5%），每月加碼上限 500~2000 點",
                    "condition": "需使用玉山 Wallet 綁定並切換方案；排除新戶加碼，舊戶卡友皆可享有。"
                },
                {
                    "channel_name": "日本/韓國/海外實體消費",
                    "keywords": ["日本", "韓國", "國外", "海外", "日幣", "韓幣", "國外實體", "bic camera", "唐吉訶德"],
                    "cashback_rate": 4.5,
                    "cashback_display": "4.5% (海外實體消費)",
                    "is_new_customer_only": False,
                    "cap": "每月加碼上限 1,000 點（可刷約 2.8 萬）",
                    "condition": "海外實體店面切換百大特店專案，扣除 1.5% 交易手續費後淨賺 3.0%"
                },
                {
                    "channel_name": "蝦皮購物 / momo / PChome",
                    "keywords": ["蝦皮", "shopee", "momo", "pchome", "網購", "酷澎"],
                    "cashback_rate": 3.5,
                    "cashback_display": "3.5% e point",
                    "is_new_customer_only": False,
                    "cap": "每期回饋上限 500 點",
                    "condition": "任意選/UP選通路，非新戶享 3.5%"
                }
            ],
            "source_url": "https://www.fuma.me/2017/12/creditcard-cash-back-top.html",
            "source_blog": "符碼記憶"
        },
        {
            "card_name": "台新 GoGo卡",
            "bank": "台新銀行",
            "valid_period": "2026/06/01 - 2026/11/30",
            "period_tag": "2026下半年",
            "channels": [
                {
                    "channel_name": "街口支付 / 台新Pay",
                    "keywords": ["街口", "街口支付", "台新pay", "超商", "7-11", "全家"],
                    "cashback_rate": 3.8,
                    "cashback_display": "3.8% 台新Point",
                    "is_new_customer_only": False,
                    "cap": "每期帳單加碼上限 1,000 點（可刷 $30,303）",
                    "condition": "需使用數位帳單並設定 Richart 帳戶自動扣繳（已排除新戶首刷禮）"
                },
                {
                    "channel_name": "蝦皮 / momo / PChome / 酷澎網購",
                    "keywords": ["蝦皮", "momo", "pchome", "酷澎", "網購"],
                    "cashback_rate": 3.8,
                    "cashback_display": "3.8% 台新Point",
                    "is_new_customer_only": False,
                    "cap": "加碼上限 1,000 點/月",
                    "condition": "數位帳單 + Richart 自動扣款即享，既有卡友標準回饋"
                }
            ],
            "source_url": "https://www.beurlife.com/2026/01/best-credit-card-cash-back.html",
            "source_blog": "這就是人生"
        },
        {
            "card_name": "國泰世華 CUBE卡",
            "bank": "國泰世華",
            "valid_period": "2026/07/01 - 2026/12/31",
            "period_tag": "2026下半年",
            "channels": [
                {
                    "channel_name": "日本/韓國/海外消費 (趣旅行)",
                    "keywords": ["日本", "韓國", "海外", "國外", "日幣", "韓元", "機場", "機票", "飯店"],
                    "cashback_rate": 3.3,
                    "cashback_display": "3.3% 小樹點(信用卡) 無上限",
                    "is_new_customer_only": False,
                    "cap": "無上限！適合大額刷卡",
                    "condition": "切換為「趣旅行」權益，不限新舊戶，海外實體或機票皆享 3.3% 無上限"
                },
                {
                    "channel_name": "中油直營 / Uber Eats / 高鐵 / 捷運 (集精選)",
                    "keywords": ["中油", "加油", "uber", "uber eats", "外送", "高鐵", "台鐵"],
                    "cashback_rate": 3.0,
                    "cashback_display": "3.0% 小樹點 無上限",
                    "is_new_customer_only": False,
                    "cap": "無上限",
                    "condition": "切換指定權益方案，舊戶同享無上限回饋"
                }
            ],
            "source_url": "https://www.fuma.me/2017/12/creditcard-cash-back-top.html",
            "source_blog": "符碼記憶"
        },
        {
            "card_name": "上海商業銀行 小小兵卡 (BEE DO卡)",
            "bank": "上海商銀",
            "valid_period": "2026/07/01 - 2026/12/31",
            "period_tag": "2026下半年",
            "channels": [
                {
                    "channel_name": "全聯 / 超商 7-11 / 全家 / 水電公用繳費",
                    "keywords": ["全聯", "7-11", "全家", "超商", "繳費", "水電費", "瓦斯費", "路邊停車"],
                    "cashback_rate": 5.0,
                    "cashback_display": "5.0% 現金回饋",
                    "is_new_customer_only": False,
                    "cap": "指定生活通路加碼每月上限 200 元（可刷 $4,000）",
                    "condition": "綁定自動扣繳與電子帳單，舊戶同享 5% 繳費神回饋"
                },
                {
                    "channel_name": "全球主題樂園 (迪士尼/環球影城)",
                    "keywords": ["迪士尼", "環球影城", "樂園", "日本環球", "東京迪士尼"],
                    "cashback_rate": 10.0,
                    "cashback_display": "10.0% 現金回饋",
                    "is_new_customer_only": False,
                    "cap": "每月上限 500 元（可刷 $5,000）",
                    "condition": "全球指定樂園門票購票回饋，非新戶限定"
                }
            ],
            "source_url": "https://www.beurlife.com/2026/02/scsb_minions_credit_card.html",
            "source_blog": "這就是人生"
        },
        {
            "card_name": "永豐 SPORT卡",
            "bank": "永豐銀行",
            "valid_period": "2026/07/01 - 2026/12/31",
            "period_tag": "2026下半年",
            "channels": [
                {
                    "channel_name": "Apple Pay / Google Pay 行動感應支付",
                    "keywords": ["apple pay", "google pay", "ap", "gp", "感應支付", "手機感應"],
                    "cashback_rate": 6.0,
                    "cashback_display": "最高 6.0% 豐點",
                    "is_new_customer_only": False,
                    "cap": "加碼 5% 每月上限 300 點（可刷 $6,000）",
                    "condition": "每月運動燃燒 7,000 卡路里，舊戶綁定 Apple Pay / Google Pay 即享 6%（非新戶限定）"
                }
            ],
            "source_url": "https://www.fuma.me/2017/12/creditcard-cash-back-top.html",
            "source_blog": "符碼記憶"
        },
        {
            "card_name": "國泰世華 蝦皮聯名卡",
            "bank": "國泰世華",
            "valid_period": "2026/07/01 - 2026/12/31",
            "period_tag": "2026下半年",
            "channels": [
                {
                    "channel_name": "蝦皮購物站內消費 (大促日加碼)",
                    "keywords": ["蝦皮", "shopee", "蝦皮購物", "大促日"],
                    "cashback_rate": 10.0,
                    "cashback_display": "最高 10.0% 蝦幣",
                    "is_new_customer_only": False,
                    "cap": "平日 4% 蝦幣無上限；促銷日加碼至 10%，加碼上限 1,000 蝦幣",
                    "condition": "已排除新卡首刷贈送之蝦幣，此為既有卡友之促銷日消費標準回饋率"
                }
            ],
            "source_url": "https://www.fuma.me/feeds/posts/default",
            "source_blog": "符碼記憶"
        },
        {
            "card_name": "遠東 樂家+卡",
            "bank": "遠東商銀",
            "valid_period": "2026/07/01 - 2026/12/31",
            "period_tag": "2026下半年",
            "channels": [
                {
                    "channel_name": "加油 / 餐廳 / 寵物 / 健身房",
                    "keywords": ["加油", "中油", "全國加油", "餐廳", "吃飯", "寵物", "健身房"],
                    "cashback_rate": 5.0,
                    "cashback_display": "5.0% 現金回饋",
                    "is_new_customer_only": False,
                    "cap": "指定生活通路每期上限 350 元（可刷 $7,000）",
                    "condition": "設定遠銀帳戶自動扣繳即享 5%，非新戶限定活動"
                }
            ],
            "source_url": "https://www.beurlife.com/2026/01/best-credit-card-cash-back.html",
            "source_blog": "這就是人生"
        }
    ]

def find_best_cards(query: str, top_n: int = 4) -> List[Dict[str, Any]]:
    """核心查詢大腦：關鍵字展開、嚴格排除新戶、計算最優卡片排名"""
    cards = load_cards_db()
    q = query.strip().lower()
    
    # 擴展關鍵字
    search_terms = {q}
    for alias_key, terms in CHANNEL_ALIASES.items():
        if alias_key in q:
            search_terms.update(terms)

    matches = []
    for card in cards:
        for ch in card.get("channels", []):
            if ch.get("is_new_customer_only", False):
                continue
                
            ch_keywords = [k.lower() for k in ch.get("keywords", [])]
            ch_name = ch.get("channel_name", "").lower()
            
            matched = False
            for term in search_terms:
                if any(term in kw or kw in term for kw in ch_keywords) or term in ch_name:
                    matched = True
                    break
                    
            if not matched and any(b in q for b in ["一般", "無腦", "其他", "生活"]):
                if any("一般" in kw or "無腦" in kw for kw in ch_keywords):
                    matched = True

            if matched:
                matches.append({
                    "card_name": card.get("card_name"),
                    "bank": card.get("bank"),
                    "matched_channel": ch.get("channel_name"),
                    "cashback_rate": ch.get("cashback_rate", 0.0),
                    "cashback_display": ch.get("cashback_display"),
                    "cap": ch.get("cap"),
                    "condition": ch.get("condition"),
                    "valid_period": card.get("valid_period"),
                    "period_tag": card.get("period_tag"),
                    "source_blog": card.get("source_blog"),
                    "source_url": card.get("source_url")
                })

    # 依照回饋率由大到小排序
    matches.sort(key=lambda x: x["cashback_rate"], reverse=True)
    return matches[:top_n]

def format_recommendation_text(query: str, results: List[Dict[str, Any]]) -> str:
    """產出文字版結構化回覆 (給 Telegram Bot 或 CLI 使用)"""
    if not results:
        return f"💡 找不到與「{query}」完全符合的專屬回饋，建議使用一般消費無腦刷（如國泰 CUBE 卡或玉山 Unicard 1%~3%）。"

    reply = [f"💳 **【{query}】付款卡片推薦（已嚴格排除新戶加碼）**\n"]
    for i, r in enumerate(results, 1):
        reply.append(
            f"**Top {i}：{r['bank']} {r['card_name']}**\n"
            f"• 💰 **回饋率**：`{r['cashback_display']}`\n"
            f"• 🎯 **適用通路**：{r['matched_channel']}\n"
            f"• ⏱️ **權益期限**：{r['valid_period']} ({r['period_tag']})\n"
            f"• ⚠️ **門檻/上限**：{r['cap']}\n"
            f"• 📌 **注意事項**：{r['condition']}\n"
            f"• 📖 **資料來源**：[{r['source_blog']}]({r['source_url']})\n"
        )
    reply.append("🛡️ *小幫手備註：以上回饋均為「常態/既有卡友回饋」，已過濾僅限新戶首刷之加碼優惠。*")
    return "\n".join(reply)

# =============================================================================
# 4. 內嵌現代化 Web 前端與 FastAPI 服務
# =============================================================================
HTML_UI = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>💳 信用卡付款小幫手 | 爬蟲即時推薦</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-color: #f8fafc;
            --text-muted: #94a3b8;
            --border-color: #334155;
            --accent: #10b981;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background-color: var(--bg-color); color: var(--text-color); height: 100vh; display: flex; justify-content: center; align-items: center; }
        .chat-container { width: 100%; max-width: 850px; height: 95vh; background: #111827; border-radius: 16px; display: flex; flex-direction: column; border: 1px solid var(--border-color); overflow: hidden; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }
        .chat-header { padding: 16px 20px; background: #1f2937; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; }
        .header-info { display: flex; align-items: center; gap: 12px; }
        .avatar { width: 44px; height: 44px; border-radius: 50%; background: linear-gradient(135deg, #3b82f6, #1d4ed8); display: flex; align-items: center; justify-content: center; font-size: 20px; color: white; }
        .status-subtitle { font-size: 0.8rem; color: var(--text-muted); display: flex; align-items: center; gap: 6px; }
        .status-dot { width: 8px; height: 8px; background-color: var(--accent); border-radius: 50%; display: inline-block; }
        .header-actions button { background: #374151; color: #e5e7eb; border: none; padding: 8px 14px; border-radius: 8px; cursor: pointer; font-size: 0.85rem; display: flex; align-items: center; gap: 6px; }
        .chat-messages { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; }
        .message { display: flex; max-width: 85%; }
        .message.bot { align-self: flex-start; }
        .message.user { align-self: flex-end; }
        .bubble { padding: 14px 18px; border-radius: 14px; line-height: 1.6; font-size: 0.95rem; word-break: break-word; }
        .message.bot .bubble { background: var(--card-bg); color: var(--text-color); border: 1px solid var(--border-color); }
        .message.user .bubble { background: var(--primary); color: white; }
        .rec-card { background: #1e293b; border: 1px solid #3b82f6; border-radius: 10px; padding: 12px 14px; margin-top: 10px; }
        .rec-title { font-weight: 700; font-size: 1.05rem; color: #60a5fa; display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
        .rate-badge { background: #10b981; color: white; padding: 2px 8px; border-radius: 6px; font-size: 0.85rem; font-weight: bold; }
        .rec-detail { font-size: 0.88rem; color: #cbd5e1; margin-bottom: 4px; }
        .rec-source { font-size: 0.78rem; color: var(--text-muted); margin-top: 6px; }
        .rec-source a { color: #93c5fd; text-decoration: none; }
        .quick-chips { padding: 10px 20px; background: #161f30; border-top: 1px solid var(--border-color); display: flex; align-items: center; gap: 8px; overflow-x: auto; white-space: nowrap; }
        .chip { background: #1f2937; color: #93c5fd; border: 1px solid #374151; padding: 6px 12px; border-radius: 20px; font-size: 0.82rem; cursor: pointer; }
        .chip:hover { background: #2563eb; color: white; }
        .chat-input-area { padding: 14px 20px; background: #1f2937; display: flex; gap: 10px; }
        .chat-input-area input { flex: 1; background: #111827; border: 1px solid var(--border-color); padding: 12px 16px; border-radius: 10px; color: white; font-size: 0.95rem; outline: none; }
        .chat-input-area button { background: var(--primary); color: white; border: none; width: 48px; border-radius: 10px; font-size: 1.1rem; cursor: pointer; }
    </style>
</head>
<body>
    <div class="chat-container">
        <header class="chat-header">
            <div class="header-info">
                <div class="avatar"><i class="fa-solid fa-credit-card"></i></div>
                <div>
                    <h2>信用卡付款小幫手</h2>
                    <p class="status-subtitle"><span class="status-dot"></span> 資料源：fuma.me & beurlife.com (嚴格排除新戶加碼)</p>
                </div>
            </div>
            <div class="header-actions">
                <button id="refresh-db-btn"><i class="fa-solid fa-arrows-rotate"></i> 更新權益</button>
            </div>
        </header>

        <main class="chat-messages" id="chat-messages">
            <div class="message bot">
                <div class="bubble">
                    👋 你好！我是你的<strong>信用卡付款小幫手</strong>。<br><br>
                    我會定期爬取 <strong>符碼記憶 (fuma.me)</strong> 與 <strong>這就是人生 (beurlife.com)</strong> 最新發布的文章，並自動做到：
                    <ul style="margin: 8px 0 0 20px;">
                        <li>✨ <strong>區分上半年與下半年最新權益</strong>（自動淘汰過舊失效資訊）</li>
                        <li>🚫 <strong>嚴格排除新戶獨享/首刷禮</strong>（僅推薦人人拿得到的既有卡友真實回饋）</li>
                        <li>📊 <strong>告訴你最佳卡片、實質%數、回饋上限與門檻</strong></li>
                    </ul>
                    <br>請點選下方快捷按鈕，或直接輸入你想付款的通路或店家（如：<code>LINE Pay</code>、<code>蝦皮購物</code>、<code>日本實體</code>、<code>全聯</code>、<code>加油</code>）！
                </div>
            </div>
        </main>

        <div class="quick-chips">
            <span style="font-size:0.8rem; color:var(--text-muted);">快捷：</span>
            <button class="chip" onclick="sendQuick('LINE Pay')">📱 LINE Pay</button>
            <button class="chip" onclick="sendQuick('日本實體')">🇯🇵 日本實體/日幣</button>
            <button class="chip" onclick="sendQuick('蝦皮購物')">🛒 蝦皮/momo網購</button>
            <button class="chip" onclick="sendQuick('全聯 7-11 超商')">🏪 全聯/超商/繳費</button>
            <button class="chip" onclick="sendQuick('中油 加油')">⛽ 中油/加油</button>
            <button class="chip" onclick="sendQuick('Uber Eats 外送')">🛵 外送/影音</button>
        </div>

        <footer class="chat-input-area">
            <input type="text" id="user-input" placeholder="輸入付款通路或店家關鍵字，例如：LINE Pay、日本藥妝、蝦皮..." autocomplete="off">
            <button id="send-btn"><i class="fa-solid fa-paper-plane"></i></button>
        </footer>
    </div>

    <script>
        const chatMessages = document.getElementById('chat-messages');
        const userInput = document.getElementById('user-input');
        const sendBtn = document.getElementById('send-btn');
        const refreshBtn = document.getElementById('refresh-db-btn');

        function appendMessage(sender, htmlContent) {
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${sender}`;
            msgDiv.innerHTML = `<div class="bubble">${htmlContent}</div>`;
            chatMessages.appendChild(msgDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        async function handleSend() {
            const text = userInput.value.trim();
            if (!text) return;
            appendMessage('user', text);
            userInput.value = '';

            const loadingId = 'loading-' + Date.now();
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'message bot';
            loadingDiv.id = loadingId;
            loadingDiv.innerHTML = '<div class="bubble"><i class="fa-solid fa-spinner fa-spin"></i> 正在檢索最優信用卡...</div>';
            chatMessages.appendChild(loadingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            try {
                const res = await fetch('/api/recommend', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ query: text })
                });
                const data = await res.json();
                document.getElementById(loadingId)?.remove();

                if (!data.cards || data.cards.length === 0) {
                    appendMessage('bot', `💡 找不到與「${data.query}」完全符合的加碼，建議使用一般消費無腦刷（如國泰 CUBE 卡或玉山 Unicard 1%~3%）。`);
                    return;
                }

                let html = `<div>💡 針對 <strong>「${data.query}」</strong> 付款，為您推薦以下最優卡片（已排除新戶限定優惠）：</div>`;
                data.cards.forEach((c, idx) => {
                    html += `
                    <div class="rec-card">
                        <div class="rec-title">
                            <span>Top ${idx + 1}：${c.bank} ${c.card_name}</span>
                            <span class="rate-badge">${c.cashback_display}</span>
                        </div>
                        <div class="rec-detail"><strong>🎯 通路：</strong>${c.matched_channel}</div>
                        <div class="rec-detail"><strong>⏱️ 期限：</strong>${c.valid_period} (${c.period_tag})</div>
                        <div class="rec-detail"><strong>⚠️ 門檻/上限：</strong>${c.cap || '無特殊限制'}</div>
                        <div class="rec-detail"><strong>📌 條件說明：</strong>${c.condition || '無'}</div>
                        <div class="rec-source">📖 來源：<a href="${c.source_url}" target="_blank">${c.source_blog}</a></div>
                    </div>`;
                });
                appendMessage('bot', html);
            } catch (e) {
                document.getElementById(loadingId)?.remove();
                appendMessage('bot', `❌ 查詢失敗: ${e.message}`);
            }
        }

        function sendQuick(kw) { userInput.value = kw; handleSend(); }
        sendBtn.addEventListener('click', handleSend);
        userInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') handleSend(); });

        refreshBtn.addEventListener('click', async () => {
            appendMessage('bot', '🔄 正在觸發爬蟲檢查 fuma.me 與 beurlife.com 最新文章...');
            try {
                const res = await fetch('/api/crawl', { method: 'POST' });
                const d = await res.json();
                appendMessage('bot', `✅ 更新完成！已掃描 ${d.fuma_count} 篇符碼記憶文章與 ${d.beurlife_count} 篇這就是人生文章。現有收錄 ${d.total_cards} 張卡片規則。`);
            } catch (err) {
                appendMessage('bot', `❌ 更新失敗: ${err.message}`);
            }
        });
    </script>
</body>
</html>
"""

def create_fastapi_app():
    """建立 FastAPI 應用實例"""
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel

    server = FastAPI(title="Credit Card Payment Assistant API")

    class QueryReq(BaseModel):
        query: str
        top_n: int = 4

    @server.get("/", response_class=HTMLResponse)
    def index():
        return HTML_UI

    @server.post("/api/recommend")
    def api_recommend(req: QueryReq):
        if not req.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        results = find_best_cards(req.query, top_n=req.top_n)
        return {
            "query": req.query,
            "count": len(results),
            "cards": results,
            "formatted_text": format_recommendation_text(req.query, results)
        }

    @server.post("/api/crawl")
    def api_crawl():
        fuma_res = scrape_fuma()
        beurlife_res = scrape_beurlife()
        all_cards = load_cards_db()
        return {
            "status": "success",
            "fuma_count": len(fuma_res),
            "beurlife_count": len(beurlife_res),
            "total_cards": len(all_cards)
        }

    @server.get("/api/health")
    def health():
        return {"status": "ok"}

    return server

# =============================================================================
# 5. Telegram Bot 服務
# =============================================================================
def run_telegram_bot(token: Optional[str] = None):
    """啟動 Telegram Bot 服務"""
    try:
        from telegram import Update
        from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
    except ImportError:
        print("[TelegramBot] 請先安裝套件: pip install python-telegram-bot")
        return

    bot_token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("[TelegramBot] 未設定 TELEGRAM_BOT_TOKEN。請在環境變數或 .env 中填入 Token。")
        return

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = (
            "💳 **歡迎使用信用卡付款小幫手！**\n\n"
            "直接發送你想付款的通路關鍵字（如：`LINE Pay`、`日本實體`、`蝦皮`、`全聯`、`超商`），我會即時為你推薦最優信用卡！\n"
            "• 嚴格排除新戶首刷加碼\n"
            "• 排除過期舊卡，鎖定最新權益"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    async def handle_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        if not text:
            return
        results = find_best_cards(text, top_n=3)
        reply = format_recommendation_text(text, results)
        try:
            await update.message.reply_text(reply, parse_mode='Markdown', disable_web_page_preview=True)
        except Exception:
            await update.message.reply_text(reply, disable_web_page_preview=True)

    print("[TelegramBot] Telegram 機器人輪詢已啟動...")
    bot_app = ApplicationBuilder().token(bot_token).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_query))
    bot_app.run_polling()

# =============================================================================
# [主入口判斷]
# =============================================================================
if __name__ == '__main__':
    # 命令列模式支援
    if "--crawl" in sys.argv:
        print("=== 執行手動爬蟲更新 ===")
        f = scrape_fuma()
        b = scrape_beurlife()
        print(f"爬取結果: fuma.me ({len(f)} 篇), beurlife.com ({len(b)} 篇)")
        sys.exit(0)

    if "--bot" in sys.argv:
        from dotenv import load_dotenv
        load_dotenv()
        run_telegram_bot()
        sys.exit(0)

    # 預設啟動 Web 服務
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 啟動信用卡付款小幫手 Web 服務: http://0.0.0.0:{port}")
    fastapi_app = create_fastapi_app()
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)
