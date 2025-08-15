#!/usr/bin/env python3
# cli.py — отчёт по споту в новом формате вывода (без эмодзи)

import os
import sys
import time
import hmac
import hashlib
import requests
import datetime as dt
from dotenv import load_dotenv

load_dotenv()
API_KEY    = os.getenv("MEXC_API_KEY")
API_SECRET = os.getenv("MEXC_API_SECRET")
BASE_URL   = "https://api.mexc.com"

LEVELS_DEFAULT = [20, 40, 60]   # ROI уровни фиксации от средней, %
TRAILING_PCT   = 45             # трейлинг от текущей цены, %

def need_keys():
    if not API_KEY or not API_SECRET:
        print("Нет API ключей. Добавь в .env:\nMEXC_API_KEY=...\nMEXC_API_SECRET=...\n")
        sys.exit(1)

def sign_request(params: dict) -> dict:
    # Порядок параметров важен — как в исходном рабочем скрипте
    qs = "&".join([f"{k}={v}" for k, v in params.items()])
    sig = hmac.new(API_SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()
    params["signature"] = sig
    return params

def my_trades(symbol: str, limit: int = 1000):
    params = {"symbol": symbol, "limit": limit, "timestamp": int(time.time()*1000), "recvWindow": 60000}
    params = sign_request(params)
    headers = {"X-MEXC-APIKEY": API_KEY}
    r = requests.get(BASE_URL + "/api/v3/myTrades", params=params, headers=headers, timeout=12)
    if r.status_code != 200:
        print(f"Ошибка {r.status_code}: {r.text}")
        sys.exit(1)
    return r.json()

def get_last_price(symbol: str) -> float:
    r = requests.get(BASE_URL + "/api/v3/ticker/price", params={"symbol": symbol}, timeout=8)
    r.raise_for_status()
    return float(r.json()["price"])

def normalize_symbol(sym: str) -> str:
    s = sym.upper()
    return s if s.endswith("USDT") else s + "USDT"

def parse_levels_arg(arg: str):
    try:
        return [int(x.strip()) for x in arg.split(",") if x.strip() != ""]
    except Exception:
        return LEVELS_DEFAULT

# ===== Новый форматированный отчёт =====
def print_report_formatted(symbol: str, trades: list, levels=None, trailing_pct: int = TRAILING_PCT):
    if levels is None:
        levels = LEVELS_DEFAULT

    trades = sorted(trades, key=lambda t: t["time"])

    # Пересбор позиции (WAC) + подготовка строк для таблицы сделок
    left_qty = 0.0
    left_cost = 0.0
    realized_pnl = 0.0
    gross_buys = 0.0
    gross_sells = 0.0

    lines = []  # строки для таблицы покупок/продаж (промежуточные Left Qty и Avg Price после операции)

    for t in trades:
        ts    = dt.datetime.fromtimestamp(t["time"]/1000).strftime("%Y-%m-%d %H:%M:%S")
        price = float(t["price"])
        qty   = float(t["qty"])
        quote = float(t.get("quoteQty", price*qty))
        is_buy = bool(t["isBuyer"])

        side = "BUY" if is_buy else "SELL"

        if is_buy:
            # покупка
            left_qty  += qty
            left_cost += quote
            gross_buys += quote
            roi_str = ""
            pnl_str = ""
        else:
            # продажа
            if left_qty > 0:
                avg_line = left_cost / left_qty
                roi  = (price/avg_line - 1.0) * 100.0
                pnl  = (price - avg_line) * qty
                realized_pnl += pnl
                roi_str = f"{roi:.2f}%"
                pnl_str = f"{pnl:.2f}"
                # списываем по средней
                left_qty  -= qty
                left_cost -= avg_line * qty
            else:
                roi_str = "—"
                pnl_str = ""
            gross_sells += quote

        avg_after = (left_cost/left_qty) if left_qty > 0 else 0.0

        lines.append({
            "time": ts,
            "side": side,
            "price": price,
            "qty": qty,
            "quote": quote,
            "roi": roi_str if not is_buy else "",
            "pnl": pnl_str if not is_buy else "",
            "left_qty": left_qty if left_qty>0 else 0.0,
            "avg_price": avg_after if left_qty>0 else 0.0
        })

    # Если позиции нет — печатаем итоги и выходим
    if left_qty <= 0:
        print("Позиция отсутствует (остаток 0).")
        print(f"Реализованный PnL: {realized_pnl:.2f} USDT")
        return

    # Текущее состояние позиции
    avg = left_cost / left_qty
    try:
        mkt = get_last_price(symbol)
    except Exception:
        mkt = None

    if mkt is None:
        print("Не удалось получить текущую цену.")
        print(f"Средняя цена позиции: {avg:.6f} USDT")
        print(f"Остаток монет: {left_qty:.8f}")
        return

    roi_position   = (mkt/avg - 1.0) * 100.0
    unrealized_pnl = (mkt - avg) * left_qty
    roi_total      = ((realized_pnl + unrealized_pnl) / gross_buys * 100.0) if gross_buys > 0 else 0.0
    pnl_total      = realized_pnl + unrealized_pnl

    # ====== Блок «Доходность» ======
    print("### Доходность")
    print(f"- ROI позиции: {roi_position:.2f}% (от средней цены позиции на текущей цене)")
    print(f"- ROI общий (с учетом продаж): {roi_total:.2f}% (реализованный + нереализованный к сумме вложений)")
    print(f"- PnL реализованный: {realized_pnl:.2f} USDT")
    print(f"- PnL нереализованный: {unrealized_pnl:.2f} USDT (по текущей цене на остатке)")
    print(f"- PnL общий: {pnl_total:.2f} USDT (realized + unrealized)")
    print()

    # ====== Таблица «ROI уровни фиксации» ======
    # Уровни от средней; trailing от текущей
    print("### ROI уровни фиксации")
    print("| ROI уровень | Цена цели | Действие            |")
    print("|-------------|-----------|---------------------|")
    for p in levels:
        price_target = avg * (1.0 + p/100.0)
        print(f"| {p}%         | {price_target:.6f} | Частичная фиксация  |")
    trailing_price = mkt * (1.0 - trailing_pct/100.0)
    print(f"| Трейлинг -{trailing_pct}% от цены | {trailing_price:.6f} | Полная фиксация     |")
    print()

    # ====== Таблица «Покупки/продажи» ======
    print("Покупки/продажи:")
    print("|       Time         | Side |   Price   |     Qty     | Quote |   ROI %   |  PnL  | Left Qty    | Avg Price  |")
    print("|--------------------|------|-----------|-------------|-------|-----------|-------|-------------|------------|")
    for r in lines:
        roi_str = f"{r['roi']:<9}"
        pnl_str = f"{r['pnl']:<5}"
        avg_price_str = f"{r['avg_price']:.6f}" if r['avg_price'] else "0.000000"
        print(f"| {r['time']} | {r['side']:<4} | {r['price']:.6f} | {r['qty']:.8f} | {r['quote']:.2f} | {roi_str} | {pnl_str} | {r['left_qty']:.8f} | {avg_price_str} |")
    print()

    # ====== Сводка внизу ======
    print(f"Монета: {symbol}")
    print(f"Текущая цена: {mkt:.6f}")
    print(f"Средняя цена позиции: {avg:.6f} USDT")
    print(f"Остаток монет: {left_qty:.8f}")

def main():
    need_keys()
    if len(sys.argv) < 2:
        print("Использование:\n  python3 cli.py SYMBOL [levels_csv] [trailing_pct]\nПримеры:\n  python3 cli.py USELESS\n  python3 cli.py ETH 20,40,60 45")
        sys.exit(1)

    symbol = normalize_symbol(sys.argv[1])
    levels = parse_levels_arg(sys.argv[2]) if len(sys.argv) >= 3 else LEVELS_DEFAULT
    trailing_pct = int(sys.argv[3]) if len(sys.argv) >= 4 else TRAILING_PCT

    trades = my_trades(symbol, limit=1000)
    if not trades:
        print("Сделок не найдено.")
        return
    print_report_formatted(symbol, trades, levels=levels, trailing_pct=trailing_pct)

if __name__ == "__main__":
    main()
