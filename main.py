import os
import logging
import re
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters, 
    ContextTypes
)
from telegram.constants import ParseMode

# Internal Modules
import engines
import data_manager

# --- SETUP & LOGGING ---
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTH_ID = os.getenv("AUTHORIZED_CHAT_ID")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize JSON files if they don't exist
data_manager.init_files()

# --- HELPER FUNCTIONS ---
def is_authorized(update: Update):
    """🟡 Security Lock: Only respond to the ID in .env (if set)"""
    if not AUTH_ID: return True
    return str(update.effective_chat.id) == str(AUTH_ID)

def get_progress_bar(value):
    """Visual utility for scores"""
    filled = int(value // 10)
    return f"[{'█' * filled}{'░' * (10 - filled)}]"

# --- BACKGROUND JOBS ---
async def hourly_scan(context: ContextTypes.DEFAULT_TYPE):
    """🟡 5️⃣ TRUE JOB SCHEDULER: Scans portfolio for crashes every hour"""
    b = data_manager.get_budget()
    chat_id = b.get('chat_id')
    
    if not chat_id:
        return 

    holdings = data_manager.get_port()
    alerts_triggered = False

    for stock in holdings:
        res = engines.get_comprehensive_analysis(stock['symbol'])
        # Alert if score drops into the 'Danger Zone'
        if res and res['final_score'] < 35:
            alerts_triggered = True
            alert_text = (
                f"🚨 <b>PORTFOLIO CRITICAL ALERT</b>\n"
                f"Symbol: <b>{stock['symbol']}</b>\n"
                f"Score: <code>{res['final_score']}/100</code>\n"
                f"Action: Consider immediate exit."
            )
            await context.bot.send_message(
                chat_id=chat_id, 
                text=alert_text, 
                parse_mode=ParseMode.HTML
            )
    
    if not alerts_triggered:
        logger.info("Hourly scan completed: All systems nominal.")

# --- COMMAND HANDLERS ---
async def port_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    
    data_manager.update_chat_id(update.message.chat_id)
    holdings = data_manager.get_port()
    b = data_manager.get_budget()
    
    if not holdings:
        return await update.message.reply_text("Your portfolio is currently empty.")

    # 🔥 LEVEL 2.775: DYNAMIC RANKING MATRIX
    # Analyze all holdings in real-time to rank them
    ranked = []
    for s in holdings:
        res = engines.get_comprehensive_analysis(s['symbol'])
        score = res['final_score'] if res else 0
        ranked.append((s, score))
    
    # Sort by score descending
    ranked.sort(key=lambda x: x[1], reverse=True)
    
    msg = "💼 <b>AlgoTrade 7 Portfolio Matrix</b>\n"
    msg += "<i>Ranked by Real-time Quant Score</i>\n\n"
    
    keyboard = []
    for s, score in ranked:
        indicator = "🟢" if score > 55 else ("🟡" if score > 35 else "🔴")
        msg += f"{indicator} <b>{s['symbol']}</b> | {s['qty']} @ ₹{s['buy_price']}\n"
        msg += f"      Score: <code>{score}</code>\n"
        
        # Add sell buttons for each
        callback_data = f"pre|{s['symbol']}|{s['buy_price']}|{s['qty']}|{s['strategy']}"
        keyboard.append([InlineKeyboardButton(f"🗑️ Sell {s['symbol']}", callback_data=callback_data)])
    
    # Budget Summary
    msg += f"\n💳 <b>Budget Allocation</b>:\n"
    msg += f"Swing Used: ₹{b['swing_used']:,} / ₹{b['swing_limit']:,}\n"
    msg += f"Vault: ₹{b['profit_vault']:,}"
    
    await update.message.reply_text(
        msg, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode=ParseMode.HTML
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    
    # Lock the chat_id for background alerts
    data_manager.update_chat_id(update.message.chat_id)
    
    text = update.message.text.strip()
    
    # --- 1. TRADE LOGGING DETECTOR ---
    # Example: "bought 10 RELIANCE at 2500"
    buy_match = re.search(r"bought (\d+) ([\w.]+) at ([\d.]+)", text.lower())
    if buy_match:
        qty, sym, price = buy_match.groups()
        sym = sym.upper()
        
        holdings = data_manager.get_port()
        holdings.append({
            'symbol': sym, 
            'qty': int(qty), 
            'buy_price': float(price), 
            'strategy': 'SWING'
        })
        data_manager.save_port(holdings)
        
        b = data_manager.get_budget()
        b['swing_used'] += (int(qty) * float(price))
        data_manager.save_budget(b)
        
        return await update.message.reply_text(f"✅ Successfully logged {qty} shares of {sym}.")

    # --- 2. SINGLE SYMBOL ANALYSIS ---
    symbol = text.upper()
    if len(symbol) > 10: return # Ignore long prose

    status_msg = await update.message.reply_text(f"🔍 Analyzing {symbol} via NSE & FinBERT...")
    
    res = engines.get_comprehensive_analysis(symbol)
    if not res:
        return await status_msg.edit_text("❌ Error: Could not fetch data. Check ticker name.")

    # 🟡 6️⃣ INJECTION-SAFE HTML FORMATTING
    reliability = "⭐" * max(1, min(5, int(res['final_score'] / 20)))
    
    report = (
        f"📊 <b>ANALYSIS: {symbol}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>Verdict:</b> {'🟢 BUY' if res['final_score'] > 55 else '🔴 AVOID'}\n"
        f"<b>Strategy:</b> <code>{res['strategy']}</code>\n"
        f"<b>Score:</b> <code>{res['final_score']}/100</code> {reliability}\n\n"
        f"📈 Trend:  {get_progress_bar(res['trend'])} {res['trend']}\n"
        f"🛡️ Risk:   {get_progress_bar(res['risk'])} {res['risk']}\n"
        f"📰 News:   {res['news_type']} ({res['news_mod']})\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Current Price: <b>₹{res['price']}</b>"
    )
    
    await status_msg.edit_text(report, parse_mode=ParseMode.HTML)

# --- CALLBACK HANDLERS (SELLING) ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("|")
    action = parts[0]
    
    if action == "pre":
        sym, buy_p, qty, strat = parts[1], parts[2], parts[3], parts[4]
        # Ask for budget refill preference
        btns = [
            [InlineKeyboardButton("🔄 Refill Budget", callback_data=f"exit|refill|{sym}|{buy_p}|{qty}|{strat}")],
            [InlineKeyboardButton("⚪ Profits to Vault", callback_data=f"exit|vault|{sym}|{buy_p}|{qty}|{strat}")]
        ]
        await query.edit_message_text(
            text=f"Confirm Exit for {sym}?\nPrice at Log: ₹{buy_p}",
            reply_markup=InlineKeyboardMarkup(btns)
        )
        
    elif action == "exit":
        mode, sym, buy_p, qty, strat = parts[1], parts[2], parts[3], parts[4], parts[5]
        
        # Get current market price for final calculation
        res = engines.get_comprehensive_analysis(sym)
        sell_price = res['price'] if res else float(buy_p)
        
        refill = True if mode == "refill" else False
        data_manager.handle_exit_logic(sym, sell_price, int(qty), strat, refill)
        
        await query.edit_message_text(f"✅ Position Closed: {sym} at ₹{sell_price}. Ledger updated.")

# --- MAIN RUNNER ---
def main():
    if not TOKEN:
        print("❌ CRITICAL: No Token found in .env")
        return

    # Using v20+ Application architecture
    app = Application.builder().token(TOKEN).read_timeout(30).connect_timeout(30).build()
    
    # 🟡 5️⃣ JOB QUEUE: Repeating Hourly Task
    if app.job_queue:
        app.job_queue.run_repeating(hourly_scan, interval=3600, first=10)
        logger.info("JobQueue initialized: Hourly scans active.")
    
    # Handlers
    app.add_handler(CommandHandler("port", port_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    print("🚀 AlgoTrade 7 (v2.775) is now Polling...")
    app.run_polling()

if __name__ == "__main__":
    main()