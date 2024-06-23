from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import math
import os

app = Flask(__name__)

# Line API credentials
line_bot_api = LineBotApi('L1v3/MpC608IdWNP7eu4ZHsOeYdWzP6EADrI8/TvHz8JUCoCFq4F2XQFftUS/MVBz5KEHe6AKhAbIC6NmkFNKvZieC7t2SsOdopQHlfJnq4JSFMO2Fg5wBhIlJlnfB1k/x4UvwVN/e46iVf2saNcggdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('6ee9665923b90570948a7d3e9828899a')

def calculate_lora(sf, bw, cr, payload_length, preamble_length, tx_power, tx_gain, rx_gain, frequency, noise_figure, ple):
    symbol_duration = (2 ** sf) / (bw * 1000)
    total_symbols = preamble_length + 4.25 + 8 + max(
        math.ceil(
            (8 * payload_length - 4 * sf + 28 + 16 - 20 * (1 if cr == 1 else 0)) / (4 * (sf - 2))
        ) * (cr + 4),
        0
    )
    total_symbol_duration = total_symbols * symbol_duration
    effective_data_rate = payload_length * 8 / total_symbol_duration
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
    link_budget = tx_power + tx_gain + rx_gain - receiver_sensitivity
    max_distance = 10 ** ((link_budget - 32.45 - 20 * math.log10(frequency)) / (10 * ple))
    return {
        'effective_data_rate': effective_data_rate,
        'time_on_air': total_symbol_duration * 1000,
        'max_distance': max_distance,
        'receiver_sensitivity': receiver_sensitivity
    }

@app.route("/callback", methods=['POST'])
def callback():
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
    text = event.message.text
    if text.lower().startswith('calculate'):
        try:
            params = text.split()[1:]
            if len(params) != 11:
                raise ValueError("Invalid number of parameters.")
            sf, bw, cr, payload_length, preamble_length, tx_power, tx_gain, rx_gain, frequency, noise_figure, ple = map(float, params)
            result = calculate_lora(sf, bw, cr, payload_length, preamble_length, tx_power, tx_gain, rx_gain, frequency, noise_figure, ple)
            response = (
                f"有效數據速率: {result['effective_data_rate']:.3f} kbps\n"
                f"空中時間: {result['time_on_air']:.3f} ms\n"
                f"最大傳輸距離: {result['max_distance']:.3f} km\n"
                f"接收靈敏度: {result['receiver_sensitivity']:.2f} dBm"
            )
        except Exception as e:
            response = f"Error: {str(e)}"
    else:
        response = "請輸入正確的參數格式：calculate SF BW CR PAYLOAD_LENGTH PREAMBLE_LENGTH TX_POWER TX_GAIN RX_GAIN FREQUENCY NOISE_FIGURE PLE"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response)
    )

if __name__ == "__main__":
    app.run()
