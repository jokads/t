import pandas as pd

def generate_signal(data, short=5, long=20):
    data['EMA_short'] = data['close'].ewm(span=short, adjust=False).mean()
    data['EMA_long'] = data['close'].ewm(span=long, adjust=False).mean()

    if data['EMA_short'].iloc[-1] > data['EMA_long'].iloc[-1]:
        return "BUY"
    elif data['EMA_short'].iloc[-1] < data['EMA_long'].iloc[-1]:
        return "SELL"
    return "HOLD"
