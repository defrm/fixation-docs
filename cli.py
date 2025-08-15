import sys
from utils import get_trade_data, get_fixation_levels  # пример, заменить на твои импорты

def print_report(symbol, trades, avg_price, current_price, roi_position, roi_total, pnl_realized, pnl_unrealized, pnl_total, fixation_levels):
    # 1. Доходность
    print("### Доходность")
    print(f"- ROI позиции: {roi_position:.2f}%")
    print(f"- ROI общий (с учетом продаж): {roi_total:.2f}%")
    print(f"- PnL реализованный: {pnl_realized:.2f} USDT")
    print(f"- PnL нереализованный: {pnl_unrealized:.2f} USDT")
    print(f"- PnL общий: {pnl_total:.2f} USDT\n")

    # 2. ROI уровни фиксации
    print("### ROI уровни фиксации")
    print("| ROI уровень | Цена цели | Действие            |")
    print("|-------------|-----------|---------------------|")
    for level in fixation_levels:
        print(f"| {level['roi']}% | {level['price']:.6f} | {level['action']} |")
    print()

    # 3. Сделки
    print("Покупки/продажи:")
    print("|       Time         | Side |   Price   |     Qty     | Quote |   ROI %   |  PnL  | Left Qty    | Avg Price  |")
    print("|--------------------|------|-----------|-------------|-------|-----------|-------|-------------|------------|")
    for t in trades:
        roi_str = f"{t['roi']:.2f}%" if 'roi' in t and t['roi'] is not None else ""
        pnl_str = f"{t['pnl']:.2f}" if 'pnl' in t and t['pnl'] is not None else ""
        print(f"| {t['time']}| {t['side']:<4} | {t['price']:.6f} | {t['qty']:.8f} | {t['quote']:.2f} | {roi_str:<9} | {pnl_str:<5} | {t['left_qty']:.8f} | {t['avg_price']:.6f} |")
    print()

    # 4. Инфо по монете
    print(f"Монета: {symbol}")
    print(f"Текущая цена: {current_price:.6f}")
    print(f"Средняя цена позиции: {avg_price:.6f} USDT")
    print(f"Остаток монет: {trades[-1]['left_qty']:.8f}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("⚠️ Укажите символ монеты, например: python3 cli.py USELESS")
        sys.exit(1)

    symbol = sys.argv[1]

    # Получаем данные (здесь подставить свои функции)
    trades, avg_price, current_price, roi_position, roi_total, pnl_realized, pnl_unrealized, pnl_total = get_trade_data(symbol)
    fixation_levels = get_fixation_levels(avg_price)

    # Выводим
    print_report(symbol, trades, avg_price, current_price, roi_position, roi_total, pnl_realized, pnl_unrealized, pnl_total, fixation_levels)
