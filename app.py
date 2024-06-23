from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import math

app = Flask(__name__)

# 設定你的Line Bot的Channel Access Token和Channel Secret
LINE_CHANNEL_ACCESS_TOKEN = '你的Channel Access Token'
LINE_CHANNEL_SECRET = '你的Channel Secret'

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.route("/callback", methods=['POST'])
def callback():
    # 確認請求來自Line
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    
    # 將用戶輸入解析成參數
    try:
        params = user_message.split(',')
        sf = int(params[0].strip())
        bw = float(params[1].strip())
        cr = float(params[2].strip())
        payload_length = float(params[3].strip())
        preamble_length = float(params[4].strip())
        tx_power = float(params[5].strip())
        tx_gain = float(params[6].strip())
        rx_gain = float(params[7].strip())
        frequency = float(params[8].strip())
        noise_figure = float(params[9].strip())
        ple_values = [float(ple) for ple in params[10:]]

        ple = sum(ple_values) / len(ple_values)
        
        # 計算結果
        result = calculate_lora(sf, bw, cr, payload_length, preamble_length, tx_power, tx_gain, rx_gain, frequency, noise_figure, ple)
        
        # 構建回覆訊息
        reply_message = f"有效數據速率: {result['effective_data_rate']} kbps\n空中時間: {result['time_on_air']} ms\n最大傳輸距離: {result['max_distance']} km\n接收靈敏度: {result['receiver_sensitivity']} dBm"
    except Exception as e:
        reply_message = f"錯誤: {str(e)}\n請依照格式輸入參數：SF, BW, CR, Payload Length, Preamble Length, Tx Power, Tx Gain, Rx Gain, Frequency, Noise Figure, PLEs (用逗號分隔)"

    # 回應用戶的訊息
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_message)
    )

def calculate_lora(sf, bw, cr, payload_length, preamble_length, tx_power, tx_gain, rx_gain, frequency, noise_figure, ple):
    # Calculate symbol duration (ms)
    symbol_duration = (2 ** sf) / (bw * 1000)
    
    # Calculate number of symbols
    total_symbols = preamble_length + 4.25 + 8 + max(
        math.ceil(
            (8 * payload_length - 4 * sf + 28 + 16 - 20 * (1 if cr == 1 else 0)) / (4 * (sf - 2))
        ) * (cr + 4),
        0
    )

    # Calculate total symbol duration (ms)
    total_symbol_duration = total_symbols * symbol_duration
    
    # Calculate effective data rate (kbps)
    effective_data_rate = payload_length * 8 / total_symbol_duration
    
    # Calculate receiver sensitivity (dBm)
    def calculate_receiver_sensitivity(sf, bw, nf):
        SNR = {
            6: -5,
            7: -7.5,
            8: -10,
            9: -12.5,
            10: -15,
            11: -17.5,
            12: -20
        }[sf]
        return -174 + 10 * math.log10(bw * 1000) + nf + SNR
    
    receiver_sensitivity = calculate_receiver_sensitivity(sf, bw, noise_figure)
    
    # Calculate maximum distance (km)
    link_budget = tx_power + tx_gain + rx_gain - receiver_sensitivity
    max_distance = 10 ** ((link_budget - 32.45 - 20 * math.log10(frequency)) / (10 * ple))
    
    return {
        'effective_data_rate': effective_data_rate,
        'time_on_air': total_symbol_duration * 1000,
        'max_distance': max_distance,
        'receiver_sensitivity': receiver_sensitivity
    }

if __name__ == "__main__":
    app.run(debug=True)
