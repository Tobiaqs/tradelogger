import os, websocket
from json import loads
from datetime import datetime
import psycopg2

try:
    conn = psycopg2.connect(f'dbname=app user=app host=postgres password={os.environ["POSTGRES_PASSWORD"]}')
except:
    print('Cannot connect to postgres')
    exit(1)

cur = conn.cursor()
cur.execute(f'create table if not exists trades (id serial PRIMARY KEY, symbol TEXT, price TEXT, volume TEXT, codes TEXT, time TIMESTAMP)')
conn.commit()

# parameters
FINNHUB_TOKEN = os.environ['FINNHUB_TOKEN']

def on_ws_message(ws, message):
    # parse the trades object
    trades = loads(message)

    for trade in trades['data']:
        if trade['v'] != 0:
            cur.execute(f'insert into trades(symbol, price, volume, codes, time) VALUES(%s,%s,%s,%s,%s)', (trade['s'], str(trade['p']), str(trade['v']), ','.join(map(lambda x: str(x), trade['c'])), datetime.fromtimestamp(trade['t']/1000.0)))
    conn.commit()

def on_ws_error(ws, error):
    print(error)

def on_ws_close(ws):
    print('disconnected')
    conn.close()

def on_ws_open(ws):
    ws.send(f'{{"type":"subscribe","symbol":"GME"}}')
    ws.send(f'{{"type":"subscribe","symbol":"AMC"}}')
    ws.send(f'{{"type":"subscribe","symbol":"AAPL"}}')
    ws.send(f'{{"type":"subscribe","symbol":"GOOG"}}')

    print('connected to Finnhub WS')

ws = websocket.WebSocketApp(f'wss://ws.finnhub.io?token={FINNHUB_TOKEN}',
                              on_message = on_ws_message,
                              on_error = on_ws_error,
                              on_close = on_ws_close)

ws.on_open = on_ws_open

ws.run_forever()
