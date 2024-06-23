from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
import os
import math

app = Flask(__name__)

# 設置Line Bot的Channel Access Token和Channel Secret
line_bot_api = LineBotApi('/CJFLhYsy8U8EIFUhjpJ0tVTxS5y1akXvOa7KZwcV06guiDwAIdn92xHhx/iErlxz5KEHe6AKhAbIC6NmkFNKvZieC7t2SsOdopQHlfJnq7XaPKcENJj43unpHMRh48H1yR/43eTaY12YFYmO+r2dQdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('03f5a604171a37cb9ffa82be800bd72e')

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

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    if user_message.lower() == 'calculate':
        # Send Flex Message for user to input parameters
        line_bot_api.reply_message(
            event.reply_token,
            FlexSendMessage(
                alt_text="Parameter Input",
                contents={
                    "type": "bubble",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": "Please enter the parameters:",
                                "weight": "bold",
                                "size": "md"
                            },
                            {
                                "type": "separator",
                                "margin": "md"
                            },
                            {
                                "type": "text",
                                "text": "SF, BW, CR, Payload Length, Preamble Length, Tx Power, Tx Gain, Rx Gain, Frequency, Noise Figure, PLEs",
                                "size": "sm",
                                "color": "#AAAAAA",
                                "wrap": True
                            }
                        ]
                    },
                    "footer": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "button",
                                "style": "primary",
                                "action": {
                                    "type": "message",
                                    "label": "Enter Parameters",
                                    "text": "Enter parameters in the format: SF, BW, CR, Payload Length, Preamble Length, Tx Power, Tx Gain, Rx Gain, Frequency, Noise Figure, PLEs"
                                }
                            }
                        ]
                    }
                }
            )
        )
    else:
        try:
            params = user_message.split(',')
            if len(params) != 11:
                raise ValueError("Invalid number of parameters")
            
            result = calculate_lora(
                int(params[0]), float(params[1]), float(params[2]), float(params[3]),
                float(params[4]), float(params[5]), float(params[6]), float(params[7]),
                float(params[8]), float(params[9]), sum(map(float, params[10].split('+')))
            )
            
            response_message = f"有效數據速率: {result['effective_data_rate']:.2f} kbps\n"
            response_message += f"空中時間: {result['time_on_air']:.2f} ms\n"
            response_message += f"最大傳輸距離: {result['max_distance']:.2f} km\n"
            response_message += f"接收靈敏度: {result['receiver_sensitivity']:.2f} dBm"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=response_message)
            )
        except Exception as e:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"錯誤: {str(e)}\n請依照格式輸入參數： SF, BW, CR, Payload Length, Preamble Length, Tx Power, Tx Gain, Rx Gain, Frequency, Noise Figure, PLEs (用逗號分隔)")
            )

if __name__ == "__main__":
    app.run()

