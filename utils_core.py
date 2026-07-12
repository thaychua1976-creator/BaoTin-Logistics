import requests

def parse_money_input(val_str):
    if not val_str: return 0
    try: return int(str(val_str).replace(',', '').replace('.', '').strip())
    except: return 0

def send_zalo_message(phone, khach_hang, lo_trinh):
    """Hàm gửi tin nhắn qua Zalo Official Account (Zalo ZNS)."""
    phone_str = str(phone).strip()
    if phone_str.startswith('0'):
        phone_str = '84' + phone_str[1:]
        
    url = "https://business.openapi.zalo.me/message/template"
    access_token = "YOUR_ZALO_ACCESS_TOKEN" 
    template_id = "YOUR_ZNS_TEMPLATE_ID" 
    
    headers = {
        "access_token": access_token,
        "Content-Type": "application/json"
    }
    
    payload = {
        "phone": phone_str,
        "template_id": template_id,
        "template_data": {
            "khach_hang": khach_hang,
            "lo_trinh": lo_trinh
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
    except Exception as e:
        return {"error": str(e)}