import os, websocket, time
from json import loads
from threading import Thread
from queue import Queue
from datetime import datetime
import psycopg2

try:
    conn = psycopg2.connect(f'dbname=app user=app host=postgres password={os.environ["POSTGRES_PASSWORD"]}')
except:
    print('Cannot connect to postgres')
    exit(1)

cur = conn.cursor()
cur.execute(f'create table if not exists trades (id serial PRIMARY KEY, symbol TEXT, price TEXT, volume TEXT, codes TEXT, time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)')
conn.commit()

SYMBOLS = os.environ['SYMBOLS'].split(',')

prices_queue = Queue()

class SumHolder:
    v = 0
    pv = 0
    codes = set()

agg_sums = {}
ws_sums = {}
for symbol in SYMBOLS:
    ws_sums[symbol] = SumHolder()
    agg_sums[symbol] = SumHolder()

def price_aggregator():
    while True:
        for sum in agg_sums.values():
            sum.v = 0
            sum.pv = 0
            sum.codes = set()

        # obtain all readings from the prices_queue
        while True:
            try:
                price = prices_queue.get(timeout=0.1)
                agg_sums[price['s']].v += price['v']
                agg_sums[price['s']].pv += price['p'] * price['v']
                for code in price['c']:
                    agg_sums[price['s']].codes.add(code)
            except:
                break
        
        for symbol, sum in agg_sums.items():
            if sum.v > 0:
                    cur.execute(f'insert into trades(symbol, price, volume, codes) VALUES(%s,%s,%s,%s)', (symbol, str(sum.pv / sum.v), str(sum.v), ','.join(map(lambda x: str(x), sorted(sum.codes)))))
        conn.commit()

        time.sleep(1)

Thread(target=price_aggregator, daemon=True).start()

# parameters
FINNHUB_TOKEN = os.environ['FINNHUB_TOKEN']

def on_ws_message(ws, message):
    # parse the trades object
    trades = loads(message)

    for sum in ws_sums.values():
        sum.v = 0
        sum.pv = 0
        sum.codes = set()

    # sum all volumes and price*volume products
    for trade in trades['data']:
        ws_sums[trade['s']].v += trade['v']
        ws_sums[trade['s']].pv += trade['p'] * trade['v']
        for code in trade['c']:
            ws_sums[trade['s']].codes.add(code)
    
    for symbol, sum in ws_sums.items():
        # ignore 0-volume trades
        if sum.v > 0:
            try:
                prices_queue.put({'v': sum.v, 'p': sum.pv / sum.v, 's': symbol, 'c': sum.codes}, timeout=0.1)
            except:
                print('WARNING: timeout for queue put expired. this should NEVER happen.')
                pass

def on_ws_error(ws, error):
    print(error)

def on_ws_close(ws):
    print('disconnected')
    conn.close()

def on_ws_open(ws):
    for symbol in SYMBOLS:
        ws.send(f'{{"type":"subscribe","symbol":"{symbol}"}}')

    print('connected to Finnhub WS')

ws = websocket.WebSocketApp(f'wss://ws.finnhub.io?token={FINNHUB_TOKEN}',
                              on_message = on_ws_message,
                              on_error = on_ws_error,
                              on_close = on_ws_close)

ws.on_open = on_ws_open

ws.run_forever()
