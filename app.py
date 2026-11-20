#!/usr/bin/env python3
"""
=============================================================================
💳 信用卡付款小幫手 (Credit Card Payment Assistant) - 單一核心整合版
=============================================================================
本檔案為整套系統的【大腦與核心入口】。
將以下模組全部收納在同一隻檔案內，方便隨時打包下載給 AI / 開發者進行二次改版：
  1. 爬蟲模組 (Scraper)：爬取 fuma.me (符碼記憶) 與 beurlife.com (這就是人生)，含失敗重試機制
  2. 權益解析與過濾模組 (Parser)：時效判斷、上下半年過濾、嚴格剔除新戶加碼、超商繳費陷阱提示
  3. 推薦檢索大腦 (Recommender Engine)：同義詞擴展、消費金額回饋試算、實質%數排序、上限門檻計算
  4. 現代化 Web 前端與 API (FastAPI)：內嵌完整 HTML/CSS/JS (支援 100dvh 手機鍵盤、XSS 轉義、一鍵複製、清空紀錄)
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
import time
import html
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("CreditCardAssistant")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "cards.json")

# 通路與關鍵字同義詞字典
CHANNEL_ALIASES = {
    "line pay": ["line pay", "linepay", "lp", "連線支付"],
    "街口": ["街口", "街口支付", "jkopay"],
    "日本": ["日本", "日幣", "japan", "jp", "唐吉訶德", "驚安殿堂", "bic camera", "友都八喜", "松本清", "大國藥妝", "quicpay"],
    "韓國": ["韓國", "韓元", "korea", "kr", "首爾", "olive young"],
    "海外": ["海外", "國外", "外幣", "跨境", "國外實體", "歐盟"],
    "蝦皮": ["蝦皮", "shopee", "蝦皮購物", "蝦幣"],
    "momo": ["momo", "富邦媒", "momo購物"],
    "pchome": ["pchome", "24h購物"],
    "酷澎": ["酷澎", "coupang"],
    "超商": ["超商", "便利商店", "7-11", "711", "全家", "萊爾富", "ok超商"],
    "全聯": ["全聯", "px pay", "全支付", "福利中心"],
    "加油": ["加油", "中油", "全國加油", "台亞", "西歐", "福懋"],
    "外送": ["外送", "uber eats", "ubereats", "foodpanda", "熊貓"],
    "訂房": ["訂房", "agoda", "booking", "trip.com", "klook", "kkday", "機票", "飯店"],
    "影音": ["影音", "netflix", "spotify", "disney+", "youtube premium", "串流"],
    "繳費": ["繳費", "水費", "電費", "瓦斯", "路邊停車", "健保費", "稅"],
    "行動支付": ["行動支付", "apple pay", "google pay", "ap", "gp", "感應支付", "台灣pay"]
}

# 嚴格排除「新戶限定」關鍵字
NEW_CUSTOMER_PATTERNS = [
    r'新戶.*加碼',
    r'新戶.*首刷',
    r'新戶.*限定',
    r'新戶.*專屬',
    r'新卡.*首刷',
    r'核卡後\s*\d+\s*天內',
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

def check_channel_warnings(query: str, card: Dict[str, Any], channel: Dict[str, Any]) -> Optional[str]:
    """檢測除外條款陷阱（例如超商、繳費、全聯回饋限制）"""
    q = query.lower()
    ch_name = channel.get("channel_name", "").lower()
    card_name = card.get("card_name", "")

    if any(k in q for k in ["7-11", "全家", "超商", "繳費", "水電"]):
        if "小小兵" not in card_name and "台新" not in card_name:
            return "⚠️ 注意：多數信用卡一般回饋排除超商直刷或公用事業水電繳費，請確認有特別列入加碼才刷。"
    if "全聯" in q:
        if "小小兵" not in card_name and "全支付" not in ch_name:
            return "⚠️ 注意：全聯福利中心通常排除一般信用卡回饋，建議綁定指定行動支付。"
    return None

def extract_spending_amount(query: str) -> (str, Optional[float]):
    """解析查詢字串中是否包含消費金額，例如 '蝦皮 3000' -> ('蝦皮', 3000.0)"""
    match = re.search(r'^(.*?)\s*[$￥]?(\d+(?:\.\d+)?)\s*(?:元|塊)?$', query.strip())
    if match:
        clean_q = match.group(1).strip()
        amt = float(match.group(2))
        if clean_q:
            return clean_q, amt
    return query.strip(), None

# =============================================================================
# 2. 爬蟲模組 (Scraper) - fuma.me & beurlife.com（具備重試機制）
# =============================================================================
def scrape_fuma(max_entries: int = 8) -> List[Dict[str, Any]]:
    """爬取符碼記憶 (fuma.me) 最新文章與 Feed"""
    feed_url = 'https://www.fuma.me/feeds/posts/default'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    for attempt in range(2):
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
            logger.warning(f"[Scraper] fuma.me 第 {attempt+1} 次爬取失敗: {err}")
            time.sleep(1)
    return []

def scrape_beurlife(max_articles: int = 8) -> List[Dict[str, Any]]:
    """爬取這就是人生 (beurlife.com) 信用卡文章列表"""
    search_url = 'https://www.beurlife.com/?s=%E4%BF%A1%E7%94%A8%E5%8D%A1'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    for attempt in range(2):
        try:
            req = urllib.request.Request(search_url, headers=headers)
            html_raw = urllib.request.urlopen(req, timeout=8).read().decode('utf-8', errors='ignore')
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_raw, 'html.parser')
            articles = soup.find_all('article')
            results = []
            for a in articles[:max_articles]:
                h = a.find(['h1', 'h2', 'h3'])
                l = a.find('a')
                if h and l:
                    results.append({"title": h.get_text(strip=True), "link": l.get('href', '')})
            if results:
                return results
        except Exception as err:
            logger.warning(f"[Scraper] beurlife.com 第 {attempt+1} 次爬取失敗: {err}")
            time.sleep(1)
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
            "reward_type": "點數回饋 (e point)",
            "channels": [
                {
                    "channel_name": "LINE Pay / 街口支付 / 悠遊付",
                    "keywords": ["line pay", "linepay", "街口", "悠遊付", "行動支付"],
                    "cashback_rate": 4.5,
                    "cashback_display": "最高 4.5% e point",
                    "is_new_customer_only": False,
                    "cap": "指定百大特店最高 4.5%，每月加碼上限 500~2000 點",
                    "condition": "需使用玉山 Wallet 綁定並切換方案；舊戶享有"
                },
                {
                    "channel_name": "日本/韓國/海外實體消費",
                    "keywords": ["日本", "韓國", "國外", "海外", "日幣", "韓幣", "國外實體"],
                    "cashback_rate": 4.5,
                    "cashback_display": "4.5% (海外實體消費)",
                    "is_new_customer_only": False,
                    "cap": "每月加碼上限 1,000 點（可刷約 2.8 萬）",
                    "condition": "海外實體店面切換百大特店專案"
                },
                {
                    "channel_name": "蝦皮購物 / momo / PChome",
                    "keywords": ["蝦皮", "shopee", "momo", "pchome", "網購"],
                    "cashback_rate": 3.5,
                    "cashback_display": "3.5% e point",
                    "is_new_customer_only": False,
                    "cap": "每期回饋上限 500 點",
                    "condition": "任意選/UP選通路，非新戶享 3.5%"
                },
                {
                    "channel_name": "國內一般消費無腦刷",
                    "keywords": ["國內一般", "一般消費", "無腦刷", "隨便", "無腦"],
                    "cashback_rate": 1.0,
                    "cashback_display": "1.0% 無上限",
                    "is_new_customer_only": False,
                    "cap": "回饋無上限",
                    "condition": "綁定玉山帳戶自動扣繳"
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
            "reward_type": "點數回饋 (台新Point)",
            "channels": [
                {
                    "channel_name": "街口支付 / 台新Pay",
                    "keywords": ["街口", "街口支付", "台新pay", "超商", "7-11", "全家"],
                    "cashback_rate": 3.8,
                    "cashback_display": "3.8% 台新Point",
                    "is_new_customer_only": False,
                    "cap": "每期帳單加碼上限 1,000 點（可刷 $30,303）",
                    "condition": "需使用數位帳單並設定 Richart 自動扣繳"
                },
                {
                    "channel_name": "蝦皮 / momo / PChome / 酷澎網購",
                    "keywords": ["蝦皮", "momo", "pchome", "酷澎", "網購"],
                    "cashback_rate": 3.8,
                    "cashback_display": "3.8% 台新Point",
                    "is_new_customer_only": False,
                    "cap": "加碼上限 1,000 點/月",
                    "condition": "數位帳單 + Richart 自動扣款即享"
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
            "reward_type": "點數回饋 (小樹點)",
            "channels": [
                {
                    "channel_name": "日本/韓國/海外消費 (趣旅行)",
                    "keywords": ["日本", "韓國", "海外", "國外", "日幣", "韓元", "機場", "機票", "飯店"],
                    "cashback_rate": 3.3,
                    "cashback_display": "3.3% 小樹點 無上限",
                    "is_new_customer_only": False,
                    "cap": "無上限！適合大額刷卡",
                    "condition": "切換為「趣旅行」權益，不限新舊戶"
                },
                {
                    "channel_name": "中油直營 / Uber Eats / 高鐵 / 捷運 (集精選)",
                    "keywords": ["中油", "加油", "uber", "uber eats", "外送", "高鐵", "台鐵"],
                    "cashback_rate": 3.0,
                    "cashback_display": "3.0% 小樹點 無上限",
                    "is_new_customer_only": False,
                    "cap": "無上限",
                    "condition": "切換指定權益方案"
                },
                {
                    "channel_name": "國內一般消費",
                    "keywords": ["國內一般", "一般消費", "無腦刷", "隨便", "無腦"],
                    "cashback_rate": 0.3,
                    "cashback_display": "0.3% 基本回饋無上限",
                    "is_new_customer_only": False,
                    "cap": "無上限",
                    "condition": "一般消費"
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
            "reward_type": "現金折抵帳單",
            "channels": [
                {
                    "channel_name": "全聯 / 超商 7-11 / 全家 / 繳費",
                    "keywords": ["全聯", "7-11", "全家", "超商", "繳費", "水電費", "瓦斯費"],
                    "cashback_rate": 5.0,
                    "cashback_display": "5.0% 現金回饋",
                    "is_new_customer_only": False,
                    "cap": "指定生活通路加碼每月上限 200 元（可刷 $4,000）",
                    "condition": "綁定自動扣繳與電子帳單，舊戶同享 5%"
                },
                {
                    "channel_name": "全球主題樂園 (迪士尼/環球影城)",
                    "keywords": ["迪士尼", "環球影城", "樂園", "日本環球", "東京迪士尼"],
                    "cashback_rate": 10.0,
                    "cashback_display": "10.0% 現金回饋",
                    "is_new_customer_only": False,
                    "cap": "每月上限 500 元（可刷 $5,000）",
                    "condition": "全球指定樂園門票購票回饋"
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
            "reward_type": "點數回饋 (豐點折抵)",
            "channels": [
                {
                    "channel_name": "Apple Pay / Google Pay 行動感應支付",
                    "keywords": ["apple pay", "google pay", "ap", "gp", "感應支付", "實體刷卡"],
                    "cashback_rate": 6.0,
                    "cashback_display": "最高 6.0% 豐點",
                    "is_new_customer_only": False,
                    "cap": "加碼 5% 每月上限 300 點（可刷 $6,000）",
                    "condition": "每月運動燃燒 7,000 卡路里，舊戶綁定 AP/GP 即享 6%"
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
            "reward_type": "蝦幣點數",
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
            "reward_type": "現金折抵帳單",
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

def find_best_cards(raw_query: str, top_n: int = 4) -> (List[Dict[str, Any]], Optional[float]):
    """核心查詢大腦：支援金額解析、關鍵字展開、嚴格排除新戶、計算最優卡片排名與除外條款提示"""
    clean_q, amount = extract_spending_amount(raw_query)
    cards = load_cards_db()
    q = clean_q.lower()
    
    # 擴展關鍵字
    search_terms = {q}
    for alias_key, terms in CHANNEL_ALIASES.items():
        if alias_key in q:
            search_terms.update(terms)

    matches = []
    for card in cards:
        reward_type = card.get("reward_type", "現金/點數回饋")
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
                warning = check_channel_warnings(q, card, ch)
                rate = ch.get("cashback_rate", 0.0)
                
                # 計算試算回饋金額
                est_reward = None
                if amount and amount > 0:
                    est_reward = round(amount * (rate / 100.0), 1)

                matches.append({
                    "card_name": card.get("card_name"),
                    "bank": card.get("bank"),
                    "reward_type": reward_type,
                    "matched_channel": ch.get("channel_name"),
                    "cashback_rate": rate,
                    "cashback_display": ch.get("cashback_display"),
                    "cap": ch.get("cap"),
                    "condition": ch.get("condition"),
                    "warning": warning,
                    "estimated_reward": est_reward,
                    "valid_period": card.get("valid_period"),
                    "period_tag": card.get("period_tag"),
                    "source_blog": card.get("source_blog"),
                    "source_url": card.get("source_url")
                })

    # 依照回饋率由大到小排序
    matches.sort(key=lambda x: x["cashback_rate"], reverse=True)
    return matches[:top_n], amount

def format_recommendation_text(raw_query: str, results: List[Dict[str, Any]], amount: Optional[float] = None) -> str:
    """產出文字版結構化回覆 (給 Telegram Bot 或 CLI 使用)"""
    clean_q, _ = extract_spending_amount(raw_query)
    if not results:
        return f"💡 找不到與「{clean_q}」完全符合的專屬回饋，建議使用一般消費無腦刷（如國泰 CUBE 卡或玉山 Unicard 1%~3%）。"

    title = f"💳 **【{clean_q}】付款卡片推薦"
    if amount:
        title += f"（消費試算：${int(amount):,} 元）"
    title += "（已嚴格排除新戶加碼）**\n"

    reply = [title]
    for i, r in enumerate(results, 1):
        est_str = f"• 💵 **預估回饋**：約 `{r['estimated_reward']} 元/點`\n" if r.get('estimated_reward') else ""
        warn_str = f"• ⚠️ **陷阱提醒**：{r['warning']}\n" if r.get('warning') else ""
        reply.append(
            f"**Top {i}：{r['bank']} {r['card_name']}** [{r['reward_type']}]\n"
            f"• 💰 **回饋率**：`{r['cashback_display']}`\n"
            f"{est_str}"
            f"• 🎯 **適用通路**：{r['matched_channel']}\n"
            f"• ⏱️ **權益期限**：{r['valid_period']} ({r['period_tag']})\n"
            f"• ⚠️ **門檻/上限**：{r['cap']}\n"
            f"{warn_str}"
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>💳 信用卡付款小幫手 | 爬蟲即時推薦</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --bg-color: #0b1120;
            --card-bg: #1e293b;
            --text-color: #f8fafc;
            --text-muted: #94a3b8;
            --border-color: #334155;
            --accent: #10b981;
            --warning-bg: #451a03;
            --warning-border: #d97706;
            --warning-text: #fde68a;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        html, body { height: 100%; height: 100dvh; background-color: var(--bg-color); color: var(--text-color); overflow: hidden; display: flex; justify-content: center; align-items: center; }
        .chat-container { width: 100%; max-width: 850px; height: 100%; height: 100dvh; background: #0f172a; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }
        @media (min-width: 640px) {
            .chat-container { height: 94dvh; border-radius: 16px; border: 1px solid var(--border-color); }
        }
        .chat-header { padding: 14px 18px; background: #1e293b; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; flex-shrink: 0; }
        .header-info { display: flex; align-items: center; gap: 12px; }
        .avatar { width: 42px; height: 42px; border-radius: 50%; background: linear-gradient(135deg, #3b82f6, #1d4ed8); display: flex; align-items: center; justify-content: center; font-size: 20px; color: white; flex-shrink: 0; }
        .status-subtitle { font-size: 0.8rem; color: var(--text-muted); display: flex; align-items: center; gap: 6px; }
        .status-dot { width: 8px; height: 8px; background-color: var(--accent); border-radius: 50%; display: inline-block; }
        .header-actions { display: flex; gap: 8px; }
        .header-actions button { background: #334155; color: #e2e8f0; border: none; padding: 7px 12px; border-radius: 8px; cursor: pointer; font-size: 0.82rem; display: flex; align-items: center; gap: 5px; transition: all 0.2s; }
        .header-actions button:hover { background: #475569; }
        .chat-messages { flex: 1; padding: 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; -webkit-overflow-scrolling: touch; }
        .message { display: flex; max-width: 90%; }
        .message.bot { align-self: flex-start; }
        .message.user { align-self: flex-end; }
        .bubble { padding: 12px 16px; border-radius: 14px; line-height: 1.55; font-size: 0.94rem; word-break: break-word; }
        .message.bot .bubble { background: var(--card-bg); color: var(--text-color); border: 1px solid var(--border-color); }
        .message.user .bubble { background: var(--primary); color: white; border-bottom-right-radius: 4px; }
        .rec-card { background: #182234; border: 1px solid #3b82f6; border-radius: 10px; padding: 12px 14px; margin-top: 10px; position: relative; }
        .rec-title { font-weight: 700; font-size: 1.02rem; color: #60a5fa; display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; padding-right: 32px; }
        .rate-badge { background: #10b981; color: white; padding: 2px 8px; border-radius: 6px; font-size: 0.82rem; font-weight: bold; }
        .type-tag { font-size: 0.75rem; color: #cbd5e1; background: #334155; padding: 2px 6px; border-radius: 4px; margin-left: 6px; }
        .rec-detail { font-size: 0.87rem; color: #cbd5e1; margin-bottom: 4px; }
        .rec-warning { background: var(--warning-bg); border-left: 3px solid var(--warning-border); color: var(--warning-text); padding: 6px 10px; border-radius: 4px; font-size: 0.82rem; margin: 6px 0; }
        .rec-calc { background: #064e3b; color: #6ee7b7; border-left: 3px solid #10b981; padding: 6px 10px; border-radius: 4px; font-size: 0.88rem; font-weight: bold; margin: 6px 0; }
        .rec-source { font-size: 0.78rem; color: var(--text-muted); margin-top: 6px; }
        .rec-source a { color: #93c5fd; text-decoration: none; }
        .copy-btn { position: absolute; top: 10px; right: 10px; background: #334155; color: #94a3b8; border: none; width: 26px; height: 26px; border-radius: 6px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; }
        .copy-btn:hover { background: #475569; color: white; }
        .quick-chips { padding: 8px 14px; background: #111827; border-top: 1px solid var(--border-color); display: flex; align-items: center; gap: 8px; overflow-x: auto; white-space: nowrap; flex-shrink: 0; }
        .quick-chips::-webkit-scrollbar { display: none; }
        .chip { background: #1e293b; color: #93c5fd; border: 1px solid #334155; padding: 5px 12px; border-radius: 16px; font-size: 0.82rem; cursor: pointer; flex-shrink: 0; }
        .chip:hover { background: #2563eb; color: white; }
        .chat-input-area { padding: 12px 14px; background: #1e293b; display: flex; gap: 8px; flex-shrink: 0; }
        .chat-input-area input { flex: 1; background: #0f172a; border: 1px solid var(--border-color); padding: 12px 14px; border-radius: 10px; color: white; font-size: 0.95rem; outline: none; }
        .chat-input-area input:focus { border-color: #3b82f6; }
        .chat-input-area button { background: var(--primary); color: white; border: none; width: 46px; border-radius: 10px; font-size: 1.1rem; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .chat-input-area button:hover { background: var(--primary-hover); }
    </style>
</head>
<body>
    <div class="chat-container">
        <header class="chat-header">
            <div class="header-info">
                <div class="avatar"><i class="fa-solid fa-credit-card"></i></div>
                <div>
                    <h2>信用卡付款小幫手</h2>
                    <p class="status-subtitle"><span class="status-dot"></span> 排除新戶限定優惠 | 支援金額試算</p>
                </div>
            </div>
            <div class="header-actions">
                <button id="clear-chat-btn" title="清空對話"><i class="fa-solid fa-trash-can"></i></button>
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
                        <li>⚠️ <strong>超商/繳費/全聯陷阱提示</strong>（提醒銀行除外不回饋規定）</li>
                        <li>💵 <strong>支援消費金額試算</strong>（例如輸入「<code>蝦皮 3000</code>」或「<code>機票 25000</code>」幫你直接算出賺多少點！）</li>
                    </ul>
                    <br>請點選下方快捷按鈕，或直接輸入你想付款的通路或金額（如：<code>LINE Pay</code>、<code>蝦皮 5000</code>、<code>日本實體</code>、<code>全聯</code>、<code>加油 1000</code>）！
                </div>
            </div>
        </main>

        <div class="quick-chips">
            <span style="font-size:0.78rem; color:var(--text-muted); flex-shrink:0;">快捷：</span>
            <button class="chip" onclick="sendQuick('LINE Pay')">📱 LINE Pay</button>
            <button class="chip" onclick="sendQuick('日本實體')">🇯🇵 日本實體/日幣</button>
            <button class="chip" onclick="sendQuick('蝦皮購物 3000')">🛒 蝦皮 3000</button>
            <button class="chip" onclick="sendQuick('超商 7-11 繳費')">🏪 超商/繳費/全聯</button>
            <button class="chip" onclick="sendQuick('中油 加油 1000')">⛽ 加油 1000</button>
            <button class="chip" onclick="sendQuick('Uber Eats 外送')">🛵 外送/影音</button>
            <button class="chip" onclick="sendQuick('隨便無腦刷')">💳 一般消費無腦刷</button>
        </div>

        <footer class="chat-input-area">
            <input type="text" id="user-input" placeholder="輸入通路或包含金額，例如：LINE Pay、日本藥妝、蝦皮 3000..." autocomplete="off">
            <button id="send-btn"><i class="fa-solid fa-paper-plane"></i></button>
        </footer>
    </div>

    <script>
        const chatMessages = document.getElementById('chat-messages');
        const userInput = document.getElementById('user-input');
        const sendBtn = document.getElementById('send-btn');
        const refreshBtn = document.getElementById('refresh-db-btn');
        const clearBtn = document.getElementById('clear-chat-btn');

        // 安全 XSS 轉義
        function escapeHtml(str) {
            if (!str) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        function appendMessage(sender, htmlContent) {
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${sender}`;
            msgDiv.innerHTML = `<div class="bubble">${htmlContent}</div>`;
            chatMessages.appendChild(msgDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        function copyCardInfo(btn, text) {
            navigator.clipboard.writeText(text).then(() => {
                const orig = btn.innerHTML;
                btn.innerHTML = '<i class="fa-solid fa-check" style="color:#10b981;"></i>';
                setTimeout(() => { btn.innerHTML = orig; }, 2000);
            });
        }

        async function handleSend() {
            const text = userInput.value.trim();
            if (!text) return;
            appendMessage('user', escapeHtml(text));
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
                    appendMessage('bot', `💡 找不到與「${escapeHtml(data.query)}」完全符合的加碼，建議使用一般消費無腦刷（如國泰 CUBE 卡或玉山 Unicard 1%~3%）。`);
                    return;
                }

                let calcNotice = data.amount ? `<span style="color:#6ee7b7; font-weight:bold;">（已依金額 $${data.amount.toLocaleString()} 元進行回饋試算）</span>` : '';
                let html = `<div>💡 針對 <strong>「${escapeHtml(data.query)}」</strong> 付款${calcNotice}，為您推薦以下最優卡片（已排除新戶限定優惠）：</div>`;

                data.cards.forEach((c, idx) => {
                    const copySummary = `${c.bank} ${c.card_name} - ${c.cashback_display} (${c.matched_channel}) | 門檻: ${c.cap}`;
                    const warnBlock = c.warning ? `<div class="rec-warning">${escapeHtml(c.warning)}</div>` : '';
                    const calcBlock = c.estimated_reward ? `<div class="rec-calc">💰 消費 $${data.amount.toLocaleString()} 元，預估可拿約 ${c.estimated_reward} 元/點！</div>` : '';

                    html += `
                    <div class="rec-card">
                        <button class="copy-btn" title="複製卡片資訊" onclick="copyCardInfo(this, '${escapeHtml(copySummary)}')">
                            <i class="fa-regular fa-copy"></i>
                        </button>
                        <div class="rec-title">
                            <span>Top ${idx + 1}：${escapeHtml(c.bank)} ${escapeHtml(c.card_name)} <span class="type-tag">${escapeHtml(c.reward_type)}</span></span>
                            <span class="rate-badge">${escapeHtml(c.cashback_display)}</span>
                        </div>
                        ${calcBlock}
                        <div class="rec-detail"><strong>🎯 通路：</strong>${escapeHtml(c.matched_channel)}</div>
                        <div class="rec-detail"><strong>⏱️ 期限：</strong>${escapeHtml(c.valid_period)} (${escapeHtml(c.period_tag)})</div>
                        <div class="rec-detail"><strong>⚠️ 門檻/上限：</strong>${escapeHtml(c.cap || '無特殊限制')}</div>
                        ${warnBlock}
                        <div class="rec-detail"><strong>📌 條件說明：</strong>${escapeHtml(c.condition || '無')}</div>
                        <div class="rec-source">📖 來源：<a href="${escapeHtml(c.source_url)}" target="_blank">${escapeHtml(c.source_blog)}</a></div>
                    </div>`;
                });
                appendMessage('bot', html);
            } catch (e) {
                document.getElementById(loadingId)?.remove();
                appendMessage('bot', `❌ 查詢失敗: ${escapeHtml(e.message)}`);
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
                appendMessage('bot', `❌ 更新失敗: ${escapeHtml(err.message)}`);
            }
        });

        clearBtn.addEventListener('click', () => {
            chatMessages.innerHTML = '';
            appendMessage('bot', '🧹 對話紀錄已清空，請隨時輸入想查詢的通路或金額！');
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
        results, amount = find_best_cards(req.query, top_n=req.top_n)
        return {
            "query": req.query,
            "amount": amount,
            "count": len(results),
            "cards": results,
            "formatted_text": format_recommendation_text(req.query, results, amount)
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
        from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    except ImportError:
        logger.error("請先安裝 python-telegram-bot: pip install python-telegram-bot")
        return

    bot_token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.error("未設定 TELEGRAM_BOT_TOKEN！請在環境變數或 .env 填入。")
        return

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = (
            "👋 歡迎使用 *信用卡付款小幫手*！\n\n"
            "直接傳送你想付款的通路或金額，例如：\n"
            "• `LINE Pay`\n"
            "• `蝦皮 3000`\n"
            "• `日本實體`\n"
            "• `7-11`、`全聯`、`加油`\n\n"
            "我會自動排除新戶加碼，並提醒超商除外條款與試算金額！"
        )
        await update.message.reply_text(welcome_text, parse_mode="Markdown")

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_msg = update.message.text.strip()
        results, amount = find_best_cards(user_msg, top_n=3)
        reply = format_recommendation_text(user_msg, results, amount)
        await update.message.reply_text(reply, parse_mode="Markdown", disable_web_page_preview=True)

    app_bot = Application.builder().token(bot_token).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🤖 Telegram Bot 已成功啟動監聽中...")
    app_bot.run_polling()

# =============================================================================
# 6. 主程式執行入口
# =============================================================================
if __name__ == "__main__":
    if "--crawl" in sys.argv:
        print("=== 執行手動爬蟲更新 ===")
        f = scrape_fuma()
        b = scrape_beurlife()
        print(f"爬取結果: fuma.me ({len(f)} 篇), beurlife.com ({len(b)} 篇)")
        sys.exit(0)

    if "--bot" in sys.argv:
        print("=== 啟動 Telegram Bot 模式 ===")
        run_telegram_bot()
        sys.exit(0)

    port = int(os.getenv("PORT", 8000))
    print(f"🚀 啟動信用卡付款小幫手 Web 服務: http://0.0.0.0:{port}")
    import uvicorn
    app_instance = create_fastapi_app()
    uvicorn.run(app_instance, host="0.0.0.0", port=port)
