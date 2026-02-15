import yfinance as yf
import pandas as pd
import numpy as np
from transformers import pipeline
import logging

logging.getLogger("transformers").setLevel(logging.ERROR)
sentiment_pipe = pipeline("text-classification", model="ProsusAI/finbert")

def get_comprehensive_analysis(symbol):
    ticker = yf.Ticker(f"{symbol}.NS")
    hist = ticker.history(period="1y", interval="1d")
    
    # 🟡 2️⃣ CRASH PREVENTION: Insufficient history
    if hist.empty or len(hist) < 60: return None

    curr_price = hist['Close'].iloc[-1]
    ema20 = hist['Close'].ewm(span=20).mean()
    ema50 = hist['Close'].ewm(span=50).mean()
    
    # RSI Setup
    delta = hist['Close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=13, adjust=False).mean()
    ema_down = down.ewm(com=13, adjust=False).mean()
    
    # 🟡 2️⃣ CRASH PREVENTION: RSI Divide-by-Zero
    rs = ema_up / ema_down.replace(0, 1e-10)
    curr_rsi = (100 - (100 / (1 + rs))).iloc[-1]
    
    # ATR Setup
    high_low = hist['High'] - hist['Low']
    high_close = np.abs(hist['High'] - hist['Close'].shift())
    low_close = np.abs(hist['Low'] - hist['Close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    # 🟡 2️⃣ CRASH PREVENTION: ATR NaN backfill
    atr = tr.rolling(14).mean().bfill().iloc[-1]
    
    # --- 1️⃣ NORMALIZED TREND SCORE ---
    dist_20 = ((curr_price - ema20.iloc[-1]) / ema20.iloc[-1]) * 100
    # 🟡 4️⃣ Normalized Slope (Percentage based) x Heavy Weight (5x)
    pct_slope = ((ema20.iloc[-1] - ema20.iloc[-5]) / ema20.iloc[-5]) * 100
    
    trend_val = 50 - (dist_20 * 2) if dist_20 > 15 else 50 + (dist_20 * 3)
    trend_score = min(100, max(0, trend_val + (pct_slope * 5)))
    
    # --- 2️⃣ STABILITY SCORE ---
    last_10 = hist.iloc[-10:]
    higher_lows = sum(1 for i in range(1, len(last_10)) if last_10['Low'].iloc[i] >= last_10['Low'].iloc[i-1])
    stability_score = (higher_lows / 9) * 100
    if curr_rsi > 80 or dist_20 > 15: stability_score = max(0, stability_score - 20)

    # --- 3️⃣ ADVANCED RISK SCORE ---
    risk = 0
    if curr_price < ema20.iloc[-1]: risk += 40
    if curr_rsi < 45: risk += 20
    
    # 🟡 3️⃣ Breakout vs Blowoff Detection
    is_red_candle = hist['Close'].iloc[-1] < hist['Open'].iloc[-1]
    if is_red_candle and hist['Volume'].iloc[-1] > hist['Volume'].mean() * 1.5: 
        risk += 20 
        
    if atr > (curr_price * 0.05): risk += 20 
    risk_score = min(100, risk)

    # --- 4️⃣ NEWS MODIFIER ---
    news = ticker.news[:5]
    news_mod, news_type = 0, "Type B (Neutral)"
    if news:
        try:
            results = sentiment_pipe([n['title'] for n in news])
            pos = sum(1 for r in results if r['label'] == 'positive')
            neg = sum(1 for r in results if r['label'] == 'negative')
            if neg >= 2: news_type, news_mod = "🔴 TYPE C (Negative)", -10
            elif pos >= 2: news_type, news_mod = "🟢 TYPE A (Positive)", 5
        except Exception: pass

    final_score = ((trend_score + stability_score) / 2) - risk_score + news_mod
    
    return {
        "final_score": round(max(0, min(100, final_score)), 2),
        "trend": round(trend_score),
        "stability": round(stability_score),
        "risk": round(risk_score),
        "news_type": news_type,
        "news_mod": news_mod,
        "price": round(curr_price, 2),
        "strategy": "LONG" if final_score > 75 else "SWING"
    }