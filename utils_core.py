import requests, json, datetime, time
import streamlit as st
import pandas as pd
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import os
import logging
# ==========================================================
# LOAD BIẾN MÔI TRƯỜNG & CẤU HÌNH API[cite: 1]
# ==========================================================
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    st.error("⚠️ Không tìm thấy GEMINI_API_KEY trong file .env")

# ==========================================================
# CÁC HÀM TIỆN ÍCH DÙNG CHUNG[cite: 2]
# ==========================================================
def parse_money_input(val_str):
    if not val_str: return 0
    try: return int(str(val_str).replace(',', '').replace('.', '').strip())
    except: return 0

def doc_anh_cay_xang(image_file):
    try:
        img = Image.open(image_file)
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = """
        Đây là ảnh chụp màn hình LED của trụ bơm xăng dầu.
        Hãy đọc chính xác các con số và trả về ĐÚNG định dạng JSON sau, không kèm bất kỳ văn bản nào khác:
        {
            "tong_tien": <tổng số tiền - dạng số nguyên>,
            "so_lit": <số lít - dạng số thập phân>,
            "don_gia": <đơn giá - dạng số nguyên>
        }
        """
        response = model.generate_content([prompt, img])
        text_result = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text_result)
        return data
    except Exception as e:
        st.error(f"Lỗi khi AI đọc ảnh: {e}")
        return None

def gui_file_excel_len_telegram(excel_buffer, file_name, caption):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    
    if not bot_token or not chat_id:
        return False, "Thiếu cấu hình Telegram Token hoặc Chat ID."

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    files = {
        'document': (file_name, excel_buffer.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    }
    data = {
        'chat_id': chat_id,
        'caption': caption
    }
    
    try:
        response = requests.post(url, data=data, files=files)
        return response.status_code == 200, response.json()
    except Exception as e:
        return False, str(e)

def kiem_tra_va_gui_bao_cao_telegram(df_danger, loai_bao_cao, buffer_excel):
    if df_danger.empty:
        return False, "Không có dữ liệu tới hạn, không thực hiện gửi."
    
    caption = f"🔔 [CẢNH BÁO PHÁP LÝ {loai_bao_cao}] - {datetime.date.today().strftime('%d/%m/%Y')}\nSố lượng cảnh báo: {len(df_danger)}"
    file_name = f"Canh_Bao_{loai_bao_cao}_{datetime.date.today().strftime('%d%m%Y')}.xlsx"
    
    return gui_file_excel_len_telegram(buffer_excel, file_name, caption)

# ==========================================================
# MODULE ZALO API MỚI (THAY THẾ SEND_ZALO_MESSAGE CŨ)
# ==========================================================
def send_zalo_personal_message(zalo_user_id, message_text):
    """
    Gửi tin nhắn cá nhân cho tài xế bằng Zalo OA thông qua CS API.
    Dựa trên cấu trúc an toàn của hàm send_zalo_gmf_message[cite: 1].
    """
    access_token = os.getenv("ZALO_OA_ACCESS_TOKEN")
    
    if not access_token:
        import logging
        logging.error("Thiếu ZALO_OA_ACCESS_TOKEN trong file .env")
        return False, "Chưa cấu hình Token OA"

    # API CS của Zalo dành cho tin nhắn văn bản tự do cá nhân
    api_url = "https://openapi.zalo.me/v3.0/oa/message/cs"
    
    headers = {
        "Content-Type": "application/json",
        "access_token": access_token
    }
    
    payload = {
        "recipient": {
            "user_id": zalo_user_id
        },
        "message": {
            "text": message_text
        }
    }
    
    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("error") == 0:
                return True, "Thành công"
            else:
                return False, f"Lỗi Zalo: {result.get('message', 'Không xác định')}"
        else:
            return False, f"Lỗi HTTP: {response.status_code}"
            
    except Exception as e:
        return False, f"Lỗi hệ thống: {str(e)}"
###########################################################
def send_zalo_gmf_message(group_id, message_text):
    """
    Gửi tin nhắn vào nhóm Zalo bằng Official Account (GMF API).
    """
    access_token = os.getenv("ZALO_OA_ACCESS_TOKEN")
    
    if not access_token:
        logging.error("Thiếu ZALO_OA_ACCESS_TOKEN trong file .env")
        return False, "Chưa cấu hình Token"

    # URL API chuẩn của Zalo GMF
    api_url = "https://openapi.zalo.me/v3.0/oa/group/message"
    
    headers = {
        "Content-Type": "application/json",
        "access_token": access_token
    }
    
    payload = {
        "group_id": group_id,
        "message": {
            "text": message_text
        }
    }
    
    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            # Theo tài liệu Zalo, error = 0 là thành công
            if result.get("error") == 0:
                return True, "Thành công"
            else:
                return False, f"Lỗi Zalo: {result.get('message', 'Không xác định')}"
        else:
            return False, f"Lỗi HTTP: {response.status_code}"
            
    except Exception as e:
        return False, f"Lỗi hệ thống: {str(e)}"
#######################
def tao_tieu_de_kem_nut_refresh(tieu_de, key_duy_nhat):
    """
    Hàm tạo tiêu đề Tab kèm nút Refresh đồng bộ.
    - tieu_de: Tên của Tab (vd: "Quản lý Chuyến đi")
    - key_duy_nhat: Mã định danh để Streamlit không bị lỗi trùng nút (vd: "ref_tab1")
    """
    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.markdown(f"#### {tieu_de}")
    with col_btn:
        # Bắt buộc phải có tham số key để phân biệt nút ở các tab khác nhau
        if st.button("🔄 Làm mới dữ liệu", key=key_duy_nhat, use_container_width=True):
            st.rerun()
    st.divider()
