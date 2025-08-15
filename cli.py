#!/usr/bin/env python3
import os, sys, time, hmac, hashlib, requests, datetime as dt
from dotenv import load_dotenv
from prettytable import PrettyTable

load_dotenv()
API_KEY    = os.getenv("MEXC_API_KEY")
API_SECRET = os.getenv("MEXC_API_SECRET")
BASE_URL   = "https://api.mexc.com"

def need_keys():
    if not API_KEY or not API_SECRET:
        print("⚠️ Нет API ключей. Добавь в .env:\nMEXC_API_KEY=...\nMEXC_API_SECRET=...\n")
        sys.exit(1)

def sign_request(params: dict) -> dict:
    qs = "&".join([f"{k}={v}" for k, v in params.items()])
    sig = hmac.new(API_SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()
    params["signature"] = sig
    return params

def my_trades(symbol: str, limit: int = 200):
    params = {"symbol": symbol, "limit": limit, "timestamp": int(time.time()*1000), "recvWindow": 60000}
    params = sign_request(params)
    headers = {"X-MEXC-APIKEY": API_KEY}
    r = requests.get(BASE_URL + "/api/v3/myTrades", params=params, headers=headers, timeout=12)
    if r.status_code != 200:
        print(f"⚠️ Ошибка {r.status_code}: {r.text}")
        sys.exit(1)
    return r.json()

def get_last_price(symbol: str) -> float:
    r = requests.get(BASE_URL + "/api/v3/ticker/price", params={"symbol": symbol}, timeout=8)
    r.raise_for_status()
    return float(r.json()["price"])

def normalize_symbol(sym: str) -> str:
    s = sym.upper()
    return s if s.endswith("USDT") else s + "USDT"

def show_trades(symbol, trades, tp_pct: float = 20.0, sl_pct: float = 10.0):
    trades = sorted(trades, key=lambda t: t["time"])
    total_qty = 0.0
    total_cost = 0.0
    realized_pnl = 0.0
    invested = 0.0
    returned = 0.0

    for t in trades:
        price = float(t["price"])
        qty   = float(t["qty"])
        quote = float(t.get("quoteQty", price*qty))
        is_buy = bool(t["isBuyer"])
        if is_buy:
            total_qty  += qty
            total_cost += price * qty
            invested += quote
        else:
            if total_qty > 0:
                avg = total_cost / total_qty
                pnl = (price - avg) * qty
                realized_pnl += pnl
                total_qty  -= qty
                total_cost -= avg * qty
                returned += quote

    mkt = None
    if total_qty > 0:
        avg = total_cost / total_qty
        mkt = get_last_price(symbol)
        roi_pos = (mkt/avg - 1.0) * 100.0
        unreal_pnl = (mkt - avg) * total_qty
        total_pnl = realized_pnl + unreal_pnl
        roi_total = (realized_pnl + unreal_pnl) / invested * 100.0 if invested else 0.0
        print(f"Монета: {symbol}")
        print(f"Текущая цена: {mkt:.6f}")
        print(f"Средняя цена позиции: {avg:.6f} USDT")
        print(f"Остаток монет: {total_qty:.8f}")
        print("\n### Доходность")
        print(f"- ROI позиции: {roi_pos:.2f}% (от средней цены позиции на текущей цене)")
        print(f"- ROI общий (с учетом продаж): {roi_total:.2f}% (реализованный + нереализованный к сумме вложений)")
        print(f"- PnL реализованный: {realized_pnl:.2f} USDT")
        print(f"- PnL нереализованный: {unreal_pnl:.2f} USDT (по текущей цене на остатке)")
        print(f"- PnL общий: {total_pnl:.2f} USDT (realized + unrealized)")
    else:
        roi_total = (realized_pnl / invested * 100.0) if invested else 0.0
        print(f"Монета: {symbol} — позиция закрыта")
        print(f"### Доходность (позиция закрыта)")
        print(f"- ROI общий: {roi_total:.2f}% (только по реализованному)")
        print(f"- PnL реализованный: {realized_pnl:.2f} USDT")
        print(f"- Invested: {invested:.2f} USDT | Returned: {returned:.2f} USDT | Net Cash: {(returned - invested):.2f} USDT")
        print()

    table = PrettyTable()
    table.field_names = ["Time","Side","Price","Qty","Quote","ROI %","PnL","Left Qty","Avg Price"]
    left_qty, left_cost = 0.0, 0.0
    for t in trades:
        ts    = dt.datetime.fromtimestamp(t["time"]/1000).strftime("%Y-%m-%d %H:%M:%S")
        price = float(t["price"])
        qty   = float(t["qty"])
        quote = float(t.get("quoteQty", price*qty))
        is_buy = bool(t["isBuyer"])
        if is_buy:
            side = "BUY"
            left_qty  += qty
            left_cost += quote
            roi_str, pnl_str = "", ""
        else:
            side = "SELL"
            if left_qty > 0:
                avg_line = left_cost / left_qty
                roi  = (price/avg_line - 1.0) * 100.0
                pnl  = (price - avg_line) * qty
                roi_str = f"{roi:.2f}%"
                pnl_str = f"{pnl:.2f}"
                left_qty  -= qty
                left_cost -= avg_line * qty
            else:
                roi_str, pnl_str = "—", ""
        avg_after = (left_cost/left_qty) if left_qty > 0 else 0.0
        table.add_row([ts, side, f"{price:.6f}", f"{qty:.8f}", f"{quote:.2f}",
                       roi_str, pnl_str, f"{left_qty:.8f}",
                       (f"{avg_after:.6f}" if left_qty>0 else "—")])
    print(table)

def main():
    need_keys()
    symbol = normalize_symbol(sys.argv[1]) if len(sys.argv) >= 2 else "BTCUSDT"
    trades = my_trades(symbol, limit=1000)
    if not trades:
        print("Сделок не найдено.")
        return
    show_trades(symbol, trades)

if __name__ == "__main__":
    main()