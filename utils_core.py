import requests, json, datetime, time
import streamlit as st
import pandas as pd
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import os, re
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
    """Xóa dấu phẩy, chuyển chuỗi tiền tệ thành số float/int an toàn"""
    if val_str is None:
        return 0.0
    if isinstance(val_str, (int, float)):
        return float(val_str)
    
    val_clean = str(val_str).strip()
    if not val_clean or val_clean.lower() == 'nan':
        return 0.0
        
    # Loại bỏ dấu phẩy phân cách hàng nghìn
    val_clean = val_clean.replace(',', '')
    try:
        return float(val_clean)
    except ValueError:
        return 0.0
##########################
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
###############################################################

import traceback
import json
import pandas as pd
from audit_logger import ghi_log_he_thong

# hàm cho lần import data đầu tiên

def import_bang_gia_transaction(db_pool, df_rates, df_surcharges, current_user):
    """
    Import dữ liệu Biểu cước và Phụ phí từ DataFrame vào MySQL (Bổ sung cột GHI_CHU).
    Tích hợp tính năng TỰ ĐỘNG TÁCH DÒNG CƯỚC CHIỀU VỀ nếu có cột PHU_PHI_CHIEU_VE.
    Tuân thủ quy tắc Transaction, Rowcount và Audit Log[cite: 4].
    """
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False  # Bắt buộc Transaction[cite: 4]
        cursor = conn.cursor(dictionary=True)
        
        # 1. Lấy danh sách khách hàng để mapping Mã/Tên sang ID
        cursor.execute("SELECT id, ma_khach_hang, ten_khach_hang FROM khach_hang")
        kh_list = cursor.fetchall()
        kh_map_ma = {str(k['ma_khach_hang']).strip().upper(): k['id'] for k in kh_list if k['ma_khach_hang']}
        kh_map_ten = {str(k['ten_khach_hang']).strip().upper(): k['id'] for k in kh_list if k['ten_khach_hang']}

        def find_kh_id(tu_khoa):
            tu_khoa = str(tu_khoa).strip().upper()
            return kh_map_ma.get(tu_khoa) or kh_map_ten.get(tu_khoa)

        rates_inserted = 0
        surcharges_inserted = 0

        # 2. IMPORT BẢNG RATE CARDS (BIỂU CƯỚC) CÓ XỬ LÝ CHIỀU ĐI / CHIỀU VỀ
        if df_rates is not None and not df_rates.empty:
            sql_insert_rate = """
                INSERT INTO rate_cards (
                    khach_hang_id, ten_bang_gia, diem_di, diem_den, 
                    phan_loai_phuong_tien, loai_xe_quy_cach, gioi_han_kg, 
                    gioi_han_cbm, is_hang_tra_ve, don_gia_cuoc,gia_chuyen_tiep_noi, ghi_chu
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s)
            """
            for _, row in df_rates.iterrows():
                kh_input = row.get('KHACH_HANG')
                kh_id = find_kh_id(kh_input)
                
                if kh_id:
                    # Parse các thông tin cơ sở
                    ten_bang_gia = str(row.get('TEN_BANG_GIA', '')).strip()
                    diem_di = str(row.get('DIEM_DI', '')).strip().upper()
                    diem_den = str(row.get('DIEM_DEN', '')).strip().upper()
                    phan_loai = str(row.get('PHAN_LOAI_PHUONG_TIEN', '')).strip()
                    loai_xe = str(row.get('LOAI_XE_QUY_CACH', '')).strip()
                    gh_kg = clean_limit_number(row.get('GIOI_HAN_KG', 0))
                    gh_cbm = clean_limit_number(row.get('GIOI_HAN_CBM', 0))
                    
                    ghi_chu_val = str(row.get('GHI_CHU', '')).strip()
                    if ghi_chu_val.lower() == 'nan': ghi_chu_val = ''

                    # -----------------------------------------------------------------
                    # A. XỬ LÝ INSERT CƯỚC CHIỀU ĐI (is_hang_tra_ve = 0)
                    # -----------------------------------------------------------------
                    raw_don_gia = row.get('DON_GIA', 0)
                    don_gia_di = 0.0
                    
                    if pd.notna(raw_don_gia):
                        if isinstance(raw_don_gia, (int, float)):
                            don_gia_di = float(raw_don_gia) 
                        else:
                            dg_str = str(raw_don_gia).strip()
                            if dg_str.endswith('.0'):
                                dg_str = dg_str[:-2]
                            don_gia_di = parse_money_input(dg_str)
                            
                    # XỬ LÝ ĐỌC CỘT GIÁ CHUYẾN TIẾP NỐI (Và xử lý Logic <= 1)
                    raw_gia_tiep_noi = row.get('GIA_CHUYEN_TIEP_NOI', 0)
                    gia_tiep_noi_val = 0.0
                    
                    if pd.notna(raw_gia_tiep_noi):
                        if isinstance(raw_gia_tiep_noi, (int, float)):
                            gia_tiep_noi_val = float(raw_gia_tiep_noi)
                        else:
                            gtn_str = str(raw_gia_tiep_noi).strip()
                            if gtn_str.endswith('.0'):
                                gtn_str = gtn_str[:-2]
                            gia_tiep_noi_val = parse_money_input(gtn_str)
                            
                    # Nếu <= 1 thì gán bằng 0 (coi như chưa xây dựng giá)
                    if gia_tiep_noi_val <= 1:
                        gia_tiep_noi_val = 0.0
                    
                    if don_gia_di > 0:
                        # Truyền đúng 12 biến khớp với câu lệnh INSERT
                        val_di = (
                            kh_id, ten_bang_gia, diem_di, diem_den, 
                            phan_loai, loai_xe, gh_kg, gh_cbm, 
                            0, don_gia_di, gia_tiep_noi_val, ghi_chu_val if ghi_chu_val else None
                        )
                        cursor.execute(sql_insert_rate, val_di)
                        if cursor.rowcount > 0:
                            rates_inserted += 1
                            
                    # -----------------------------------------------------------------
                    # B. XỬ LÝ INSERT CƯỚC CHIỀU VỀ (is_hang_tra_ve = 1) - ĐÃ FIX LỖI 0.5
                    # -----------------------------------------------------------------
                    raw_phu_phi_ve = row.get('PHU_PHI_CHIEU_VE', '')
                    gia_chieu_ve = 0.0
                    
                    if pd.notna(raw_phu_phi_ve) and raw_phu_phi_ve != '' and raw_phu_phi_ve != 0:
                        
                        # TRƯỜNG HỢP 1: PANDAS ĐỌC LÀ SỐ FLOAT/INT (VD: Định dạng % trong Excel)
                        if isinstance(raw_phu_phi_ve, (int, float)):
                            if 0 < raw_phu_phi_ve <= 1.0:
                                # Nếu số nhỏ hơn 1 (VD: 0.5), tự hiểu là phần trăm -> NHÂN với đơn giá đi
                                gia_chieu_ve = don_gia_di * float(raw_phu_phi_ve)
                            else:
                                # Nếu là số tiền lớn (VD: 350000) -> Gán thẳng
                                gia_chieu_ve = float(raw_phu_phi_ve)
                                
                        # TRƯỜNG HỢP 2: PANDAS ĐỌC LÀ CHUỖI TEXT
                        else:
                            phu_phi_ve_str = str(raw_phu_phi_ve).strip().lower()
                            
                            # Có chứa ký hiệu '%' (VD: '30%', '50%')
                            if '%' in phu_phi_ve_str:
                                clean_percent = phu_phi_ve_str.replace('%', '').strip()
                                try:
                                    ty_le = float(clean_percent) / 100.0
                                    gia_chieu_ve = don_gia_di * ty_le
                                except ValueError:
                                    gia_chieu_ve = 0.0
                            else:
                                # Trực trừ các trường hợp còn lại (VD gõ nhầm text "0.5" hoặc text "350,000")
                                if phu_phi_ve_str.endswith('.0'):
                                    phu_phi_ve_str = phu_phi_ve_str[:-2]
                                
                                try:
                                    val_float = float(phu_phi_ve_str)
                                    if 0 < val_float <= 1.0:
                                        gia_chieu_ve = don_gia_di * val_float
                                    else:
                                        gia_chieu_ve = parse_money_input(phu_phi_ve_str)
                                except ValueError:
                                    gia_chieu_ve = parse_money_input(phu_phi_ve_str)
                            
                    if gia_chieu_ve > 0:
                        # Chiều về mặc định không có giá tiếp nối (Gán 0.0 vào cột gia_chuyen_tiep_noi)
                        val_ve = (
                            kh_id, ten_bang_gia, diem_den, diem_di, 
                            phan_loai, loai_xe, gh_kg, gh_cbm, 
                            1, gia_chieu_ve, 0.0, ghi_chu_val if ghi_chu_val else None
                        )
                        cursor.execute(sql_insert_rate, val_ve)
                        if cursor.rowcount > 0:
                            rates_inserted += 1

        # 3. IMPORT BẢNG PHỤ PHÍ KÈM GHI CHÚ
        if df_surcharges is not None and not df_surcharges.empty:
            sql_insert_sc = """
                INSERT INTO phu_phi_khach_hang (
                    khach_hang_id, ten_phu_phi, don_gia_phu_phi, 
                    dieu_kien_kich_hoat, loai_ap_dung, ghi_chu
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """
            for _, row in df_surcharges.iterrows():
                kh_input = row.get('KHACH_HANG')
                kh_id = find_kh_id(kh_input)
                
                if kh_id:
                    don_gia_pp = parse_money_input(str(row.get('DON_GIA', 0))) # Chuẩn hóa tiền tệ theo quy tắc[cite: 4]
                    ghi_chu_pp = str(row.get('GHI_CHU', '')).strip()
                    if ghi_chu_pp.lower() == 'nan': ghi_chu_pp = ''
                    
                    if don_gia_pp > 0:
                        val = (
                            kh_id,
                            str(row.get('TEN_PHU_PHI', '')).strip(),
                            don_gia_pp,
                            str(row.get('DIEU_KIEN_KICH_HOAT', '')).strip().upper(),
                            str(row.get('LOAI_AP_DUNG', '')).strip(),
                            ghi_chu_pp if ghi_chu_pp else None
                        )
                        cursor.execute(sql_insert_sc, val)
                        if cursor.rowcount > 0:
                            surcharges_inserted += 1

        # 4. GHI LOG HỆ THỐNG[cite: 4]
        chi_tiet_log = {
            "rate_cards_inserted": rates_inserted,
            "surcharges_inserted": surcharges_inserted,
            "luu_y": "Hệ thống tự động tách dòng đi/về nếu phát hiện phụ phí chiều về."
        }
        ghi_log_he_thong(
            cursor, 
            phan_he="QUAN_LY_BANG_GIA", 
            record_id=None, 
            nguoi_thuc_hien=current_user, 
            hanh_dong="IMPORT_EXCEL", 
            chi_tiet=json.dumps(chi_tiet_log, ensure_ascii=False)
        )

        conn.commit() # Lưu thay đổi an toàn[cite: 4]
        return True, f"✅ Import thành công: {rates_inserted} dòng Biểu cước (Đã tự động tính chiều về) và {surcharges_inserted} dòng Phụ phí."

    except Exception as e:
        if conn:
            conn.rollback() # Hoàn tác nếu có lỗi[cite: 4]
        traceback.print_exc()
        return False, f"Lỗi Import Database: {str(e)}"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
##########################
import re

def clean_limit_number(val):
    """
    Hàm làm sạch các chuỗi giới hạn như '<=6', '< 10 KGS', '<=25CBM' 
    để trích xuất ra số thực float an toàn.
    """
    if val is None:
        return 0.0
    val_str = str(val).strip()
    if not val_str or val_str.lower() == 'nan':
        return 0.0
    
    # Dùng Regular Expression tìm tất cả các số (bao gồm cả số thập phân)
    match = re.findall(r"[-+]?\d*\.\d+|\d+", val_str)
    if match:
        try:
            return float(match[0])
        except ValueError:
            return 0.0
    return 0.0
############################### hàm này dùng cho các lần import dữ liệu sau
def import_and_update_bang_gia_transaction(db_pool, df_rates, df_surcharges, current_user):
    """
    Import/Update Bảng giá và Phụ phí từ Excel (Gộp chung trong 1 Transaction).
    Có hiển thị thanh tiến trình UI (Progress Bar).
    Tích hợp thuật toán UPSERT chống trùng lặp.
    Đã FIX: Bắt buộc phải có Điểm Đi và Điểm Đến mới cho phép Insert/Update Bảng giá.
    """
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False # Tuân thủ nguyên tắc Transaction hệ thống
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id, ten_khach_hang, ma_khach_hang FROM khach_hang")
        kh_list = cursor.fetchall()
        kh_map = {str(k['ten_khach_hang']).strip().upper(): k['id'] for k in kh_list if k['ten_khach_hang']}
        kh_map_ma = {str(k['ma_khach_hang']).strip().upper(): k['id'] for k in kh_list if k['ma_khach_hang']}

        rates_inserted, rates_updated, rates_skipped = 0, 0, 0
        sc_inserted, sc_updated, sc_skipped = 0, 0, 0

        # --- KHỞI TẠO UI TIẾN TRÌNH CHẠY ---
        total_steps = (len(df_rates) if df_rates is not None else 0) + (len(df_surcharges) if df_surcharges is not None else 0)
        current_step = 0
        progress_bar = st.progress(0)
        status_text = st.empty()

        # ==========================================
        # 1. XỬ LÝ BẢNG GIÁ (RATE CARDS)
        # ==========================================
        if df_rates is not None and not df_rates.empty:
            for index, row in df_rates.iterrows():
                current_step += 1
                if total_steps > 0:
                    progress_bar.progress(current_step / total_steps)
                    status_text.markdown(f"**⏳ Đang xử lý Bảng Giá:** Dòng {index + 1}/{len(df_rates)}")

                bg_id = row.get('ID')
                if pd.isna(bg_id) or str(bg_id).strip() == '': bg_id = None
                else:
                    try: bg_id = int(float(bg_id))
                    except: bg_id = None

                kh_raw = row.get('KHACH_HANG') if pd.notna(row.get('KHACH_HANG')) else row.get('TEN_KHACH_HANG', '')
                kh_str = str(kh_raw).strip().upper()
                kh_id = kh_map.get(kh_str) or kh_map_ma.get(kh_str)
                
                if not kh_id: 
                    rates_skipped += 1
                    continue 
                
                # SỬA LỖI Ở ĐÂY: Lấy điểm đi/đến và kiểm tra chặt chẽ
                diem_di = str(row.get('DIEM_DI') if pd.notna(row.get('DIEM_DI')) else row.get('DIA_CHI_KHO_DI', '')).strip().upper()
                diem_den = str(row.get('DIEM_DEN') if pd.notna(row.get('DIEM_DEN')) else row.get('DIA_CHI_KHO_DEN', '')).strip().upper()

                # CHỐT CHẶN BẢO MẬT: Bắt buộc phải có Lộ trình mới tính là Bảng giá hợp lệ
                if not diem_di or not diem_den or diem_di == 'NAN' or diem_den == 'NAN':
                    rates_skipped += 1
                    continue

                ten_bg = str(row.get('TEN_BANG_GIA', '')).strip()
                if ten_bg.lower() == 'nan': ten_bg = ''

                phan_loai = str(row.get('PHAN_LOAI_PHUONG_TIEN', 'Xe_Tai')).strip()
                quy_cach = str(row.get('LOAI_XE_QUY_CACH', '')).strip()
                if quy_cach.lower() == 'nan': quy_cach = ''
                
                gh_kg = clean_limit_number(row.get('GIOI_HAN_KG', 0))
                gh_cbm = clean_limit_number(row.get('GIOI_HAN_CBM', 0))
                is_tra_ve = 1 if str(row.get('IS_HANG_TRA_VE', '0')).strip() == '1' else 0
                ghi_chu = str(row.get('GHI_CHU', '')).strip()
                if ghi_chu.lower() == 'nan': ghi_chu = ''

                raw_don_gia = row.get('DON_GIA_CUOC') if pd.notna(row.get('DON_GIA_CUOC')) else row.get('DON_GIA', 0)
                don_gia_di = parse_money_input(str(raw_don_gia)) if not isinstance(raw_don_gia, (int, float)) else float(raw_don_gia)

                raw_gia_tiep_noi = row.get('GIA_CHUYEN_TIEP_NOI', 0)
                gia_tiep_noi_val = parse_money_input(str(raw_gia_tiep_noi)) if not isinstance(raw_gia_tiep_noi, (int, float)) else float(raw_gia_tiep_noi)
                if gia_tiep_noi_val <= 1: gia_tiep_noi_val = 0.0

                # THUẬT TOÁN CHỐNG TRÙNG LẶP (DEDUPLICATION)
                if not bg_id:
                    sql_check_dup = """
                        SELECT id FROM rate_cards 
                        WHERE khach_hang_id = %s AND diem_di = %s AND diem_den = %s 
                          AND phan_loai_phuong_tien = %s AND loai_xe_quy_cach = %s 
                          AND is_hang_tra_ve = %s AND ten_bang_gia = %s
                        LIMIT 1
                    """
                    cursor.execute(sql_check_dup, (kh_id, diem_di, diem_den, phan_loai, quy_cach, is_tra_ve, ten_bg))
                    dup_row = cursor.fetchone()
                    if dup_row:
                        bg_id = dup_row['id']  # Đã tồn tại -> Chuyển thành lệnh UPDATE

                if bg_id:
                    # UPDATE
                    sql_update = """
                        UPDATE rate_cards
                        SET khach_hang_id=%s, ten_bang_gia=%s, diem_di=%s, diem_den=%s,
                            phan_loai_phuong_tien=%s, loai_xe_quy_cach=%s, gioi_han_kg=%s, gioi_han_cbm=%s,
                            is_hang_tra_ve=%s, don_gia_cuoc=%s, gia_chuyen_tiep_noi=%s, ghi_chu=%s
                        WHERE id=%s
                    """
                    cursor.execute(sql_update, (kh_id, ten_bg, diem_di, diem_den, phan_loai, quy_cach, gh_kg, gh_cbm, is_tra_ve, don_gia_di, gia_tiep_noi_val, ghi_chu, bg_id))
                    if cursor.rowcount > 0: rates_updated += 1 
                else:
                    # INSERT
                    if don_gia_di > 0:
                        sql_insert = """
                            INSERT INTO rate_cards (khach_hang_id, ten_bang_gia, diem_di, diem_den, phan_loai_phuong_tien, loai_xe_quy_cach, gioi_han_kg, gioi_han_cbm, is_hang_tra_ve, don_gia_cuoc, gia_chuyen_tiep_noi, ghi_chu) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(sql_insert, (kh_id, ten_bg, diem_di, diem_den, phan_loai, quy_cach, gh_kg, gh_cbm, is_tra_ve, don_gia_di, gia_tiep_noi_val, ghi_chu))
                        if cursor.rowcount > 0: rates_inserted += 1
                            
                # TÁCH DÒNG CHIỀU VỀ
                raw_phu_phi_ve = row.get('PHU_PHI_CHIEU_VE', '')
                gia_chieu_ve = 0.0
                if pd.notna(raw_phu_phi_ve) and raw_phu_phi_ve != '' and raw_phu_phi_ve != 0:
                    phu_phi_ve_str = str(raw_phu_phi_ve).strip().lower()
                    if '%' in phu_phi_ve_str:
                        try: gia_chieu_ve = don_gia_di * (float(phu_phi_ve_str.replace('%', '').strip()) / 100.0)
                        except: pass
                    else:
                        try:
                            val_float = float(phu_phi_ve_str)
                            gia_chieu_ve = don_gia_di * val_float if 0 < val_float <= 1.0 else parse_money_input(phu_phi_ve_str)
                        except: gia_chieu_ve = parse_money_input(phu_phi_ve_str)    
                                
                if gia_chieu_ve > 0:
                    # Chống trùng lặp cho chiều về
                    sql_check_ve = """
                        SELECT id FROM rate_cards 
                        WHERE khach_hang_id = %s AND diem_di = %s AND diem_den = %s 
                          AND phan_loai_phuong_tien = %s AND loai_xe_quy_cach = %s 
                          AND is_hang_tra_ve = 1 AND ten_bang_gia = %s
                        LIMIT 1
                    """
                    cursor.execute(sql_check_ve, (kh_id, diem_den, diem_di, phan_loai, quy_cach, ten_bg))
                    dup_ve = cursor.fetchone()
                    
                    if dup_ve:
                        sql_up_ve = "UPDATE rate_cards SET don_gia_cuoc=%s, gia_chuyen_tiep_noi=0.0, ghi_chu=%s WHERE id=%s"
                        cursor.execute(sql_up_ve, (gia_chieu_ve, ghi_chu, dup_ve['id']))
                        if cursor.rowcount > 0: rates_updated += 1
                    else:
                        sql_ins_ve = """
                            INSERT INTO rate_cards (khach_hang_id, ten_bang_gia, diem_di, diem_den, phan_loai_phuong_tien, loai_xe_quy_cach, gioi_han_kg, gioi_han_cbm, is_hang_tra_ve, don_gia_cuoc, gia_chuyen_tiep_noi, ghi_chu) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(sql_ins_ve, (kh_id, ten_bg, diem_den, diem_di, phan_loai, quy_cach, gh_kg, gh_cbm, 1, gia_chieu_ve, 0.0, ghi_chu))
                        if cursor.rowcount > 0: rates_inserted += 1

        # ==========================================
        # 2. XỬ LÝ PHỤ PHÍ (SURCHARGES)
        # ==========================================
        if df_surcharges is not None and not df_surcharges.empty:
            for index, row in df_surcharges.iterrows():
                current_step += 1
                if total_steps > 0:
                    progress_bar.progress(current_step / total_steps)
                    status_text.markdown(f"**⏳ Đang xử lý Phụ Phí:** Dòng {index + 1}/{len(df_surcharges)}")

                pp_id = row.get('ID')
                if pd.isna(pp_id) or str(pp_id).strip() == '': pp_id = None
                else:
                    try: pp_id = int(float(pp_id))
                    except: pp_id = None

                kh_raw = row.get('KHACH_HANG') if pd.notna(row.get('KHACH_HANG')) else row.get('TEN_KHACH_HANG', '')
                kh_str = str(kh_raw).strip().upper()
                kh_id = kh_map.get(kh_str) or kh_map_ma.get(kh_str)
                if not kh_id:
                    sc_skipped += 1
                    continue

                ten_phu_phi = str(row.get('TEN_PHU_PHI', '')).strip()
                if not ten_phu_phi or ten_phu_phi.lower() == 'nan': continue
                
                # THUẬT TOÁN CHỐNG TRÙNG LẶP CHO PHỤ PHÍ
                if not pp_id:
                    cursor.execute("SELECT id FROM phu_phi_khach_hang WHERE khach_hang_id = %s AND ten_phu_phi = %s LIMIT 1", (kh_id, ten_phu_phi))
                    dup_pp = cursor.fetchone()
                    if dup_pp:
                        pp_id = dup_pp['id']

                raw_dg_pp = row.get('DON_GIA_PHU_PHI') if pd.notna(row.get('DON_GIA_PHU_PHI')) else row.get('DON_GIA', 0)
                if pd.isna(raw_dg_pp) or str(raw_dg_pp).strip() == '': raw_dg_pp = 0
                
                loai_ap_dung_raw = str(row.get('LOAI_AP_DUNG', 'Tu_Dong')).strip()
                if loai_ap_dung_raw.lower() == 'nan' or not loai_ap_dung_raw: loai_ap_dung_raw = 'Tu_Dong'

                don_gia_pp = 0.0
                loai_ap_dung = loai_ap_dung_raw
                is_percent = False
                
                if '%' in loai_ap_dung_raw or '%' in str(raw_dg_pp) or loai_ap_dung_raw.lower() == 'phan_tram':
                    is_percent = True
                    
                if is_percent:
                    text_to_parse = f"{loai_ap_dung_raw} {raw_dg_pp}"
                    import re
                    match = re.search(r'(\d+(\.\d+)?)', text_to_parse)
                    if match:
                        val = float(match.group(1))
                        if 0 < val <= 1 and '%' not in text_to_parse:
                            val = val * 100
                        don_gia_pp = val
                    loai_ap_dung = '%'
                else:
                    don_gia_pp = parse_money_input(str(raw_dg_pp))

                dk_kich_hoat = str(row.get('DIEU_KIEN_KICH_HOAT', '')).strip().upper()
                if dk_kich_hoat.lower() == 'nan': dk_kich_hoat = ''
                
                ghi_chu = str(row.get('GHI_CHU', '')).strip()
                if ghi_chu.lower() == 'nan': ghi_chu = ''

                if pp_id:
                    # UPDATE
                    sql_update = "UPDATE phu_phi_khach_hang SET khach_hang_id=%s, ten_phu_phi=%s, don_gia_phu_phi=%s, dieu_kien_kich_hoat=%s, loai_ap_dung=%s, ghi_chu=%s WHERE id=%s"
                    cursor.execute(sql_update, (kh_id, ten_phu_phi, don_gia_pp, dk_kich_hoat, loai_ap_dung, ghi_chu, pp_id))
                    if cursor.rowcount > 0: sc_updated += 1
                else:
                    # INSERT
                    sql_insert = "INSERT INTO phu_phi_khach_hang (khach_hang_id, ten_phu_phi, don_gia_phu_phi, dieu_kien_kich_hoat, loai_ap_dung, ghi_chu) VALUES (%s, %s, %s, %s, %s, %s)"
                    cursor.execute(sql_insert, (kh_id, ten_phu_phi, don_gia_pp, dk_kich_hoat, loai_ap_dung, ghi_chu))
                    if cursor.rowcount > 0: sc_inserted += 1

        # Hoàn tất tiến trình
        progress_bar.progress(1.0)
        status_text.success("✅ Đã ghi nhận toàn bộ dữ liệu vào hệ thống!")
        time.sleep(0.5)
        progress_bar.empty()

        # Ghi log chuẩn
        log_detail = json.dumps({
            "rate_cards": {"new": rates_inserted, "update": rates_updated, "skipped": rates_skipped},
            "surcharges": {"new": sc_inserted, "update": sc_updated, "skipped": sc_skipped}
        })
        from audit_logger import ghi_log_he_thong
        ghi_log_he_thong(cursor, "QUAN_LY_BANG_GIA", None, current_user, "IMPORT_EXCEL_CAP_NHAT", log_detail)

        conn.commit()
        
        msg = f"""
        📊 **BẢNG GIÁ:** Đã cập nhật **{rates_updated}**, Thêm mới **{rates_inserted}**. (Bỏ qua {rates_skipped} dòng không hợp lệ)
        🏷️ **PHỤ PHÍ:** Đã cập nhật **{sc_updated}**, Thêm mới **{sc_inserted}**. (Bỏ qua {sc_skipped} dòng không hợp lệ)
        """
        return True, msg

    except Exception as e:
        if conn: conn.rollback()
        import traceback
        traceback.print_exc()
        return False, f"Lỗi hệ thống khi Import: {str(e)}"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
################################################

def import_and_update_phu_phi_transaction(db_pool, df_surcharges, current_user):
    """
    Import/Update Phụ phí khách hàng từ Excel. Sửa lỗi tương tự bảng giá.
    """
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id, ten_khach_hang, ma_khach_hang FROM khach_hang")
        kh_list = cursor.fetchall()
        kh_map_ten = {str(k['ten_khach_hang']).strip().upper(): k['id'] for k in kh_list if k['ten_khach_hang']}
        kh_map_ma = {str(k['ma_khach_hang']).strip().upper(): k['id'] for k in kh_list if k['ma_khach_hang']}

        row_inserted = 0
        row_updated = 0
        row_skipped = 0

        for index, row in df_surcharges.iterrows():
            pp_id = row.get('ID')
            if pd.isna(pp_id) or str(pp_id).strip() == '': pp_id = None
            else:
                try: pp_id = int(float(pp_id))
                except: pp_id = None

            # --- SỬA LỖI BỎ QUA DÒNG PHỤ PHÍ ---
            kh_raw = row.get('KHACH_HANG')
            if pd.isna(kh_raw) or str(kh_raw).strip() == '':
                kh_raw = row.get('TEN_KHACH_HANG', '')

            kh_str = str(kh_raw).strip().upper()
            kh_id = kh_map_ten.get(kh_str) or kh_map_ma.get(kh_str)
            if not kh_id:
                row_skipped += 1
                continue

            ten_phu_phi = str(row.get('TEN_PHU_PHI', '')).strip()
            if not ten_phu_phi or ten_phu_phi.lower() == 'nan': continue

            # Nhận diện Đơn giá
            raw_dg_pp = row.get('DON_GIA_PHU_PHI')
            if pd.isna(raw_dg_pp) or str(raw_dg_pp).strip() == '':
                raw_dg_pp = row.get('DON_GIA', 0)
            don_gia_pp = parse_money_input(str(raw_dg_pp))
            
            dk_kich_hoat = str(row.get('DIEU_KIEN_KICH_HOAT', '')).strip().upper()
            if dk_kich_hoat.lower() == 'nan': dk_kich_hoat = ''
            
            loai_ap_dung = str(row.get('LOAI_AP_DUNG', 'Tu_Dong')).strip()
            if loai_ap_dung.lower() == 'nan' or not loai_ap_dung: loai_ap_dung = 'Tu_Dong'

            ghi_chu = str(row.get('GHI_CHU', '')).strip()
            if ghi_chu.lower() == 'nan': ghi_chu = ''

            if pp_id:
                sql_update = """
                    UPDATE phu_phi_khach_hang
                    SET khach_hang_id=%s, ten_phu_phi=%s, don_gia_phu_phi=%s, dieu_kien_kich_hoat=%s, loai_ap_dung=%s, ghi_chu=%s
                    WHERE id=%s
                """
                cursor.execute(sql_update, (kh_id, ten_phu_phi, don_gia_pp, dk_kich_hoat, loai_ap_dung, ghi_chu, pp_id))
                row_updated += 1
            else:
                sql_insert = """
                    INSERT INTO phu_phi_khach_hang (khach_hang_id, ten_phu_phi, don_gia_phu_phi, dieu_kien_kich_hoat, loai_ap_dung, ghi_chu) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql_insert, (kh_id, ten_phu_phi, don_gia_pp, dk_kich_hoat, loai_ap_dung, ghi_chu))
                if cursor.rowcount > 0: row_inserted += 1

        log_detail = json.dumps({"phu_phi_moi": row_inserted, "phu_phi_cap_nhat": row_updated, "phu_phi_bo_qua": row_skipped}, ensure_ascii=False)
        ghi_log_he_thong(cursor, "QUAN_LY_PHU_PHI", None, current_user, "IMPORT_EXCEL_PHU_PHI", log_detail)

        conn.commit()
        
        msg = f"Đã cập nhật {row_updated} phụ phí | Thêm mới {row_inserted}."
        if row_skipped > 0:
            msg += f" (⚠️ Đã bỏ qua {row_skipped} dòng do sai tên Khách hàng)."
        return True, msg

    except Exception as e:
        if conn: conn.rollback()
        import traceback
        traceback.print_exc()
        return False, f"Lỗi hệ thống khi Import Phụ phí: {str(e)}"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
################################################

##############################
# ==========================================
# 1. QUẢN LÝ BẢNG GIÁ (RATE CARDS) - SỬA/XÓA TRỰC TIẾP
# ==========================================
def update_single_rate_card_transaction(db_pool, rate_id, data_dict, current_user):
    """Cập nhật một dòng bảng giá cụ thể theo ID"""
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False  # Bắt buộc Transaction[cite: 4]
        cursor = conn.cursor()

        sql = """
            UPDATE rate_cards 
            SET ten_bang_gia = %s, diem_di = %s, diem_den = %s, 
                phan_loai_phuong_tien = %s, loai_xe_quy_cach = %s, 
                gioi_han_kg = %s, gioi_han_cbm = %s, is_hang_tra_ve = %s, 
                don_gia_cuoc = %s, gia_chuyen_tiep_noi = %s, ghi_chu = %s
            WHERE id = %s
        """
        # Làm sạch tiền tệ qua parse_money_input theo quy tắc[cite: 4]
        don_gia = parse_money_input(str(data_dict.get('don_gia_cuoc', 0)))
        gia_tiep_noi = parse_money_input(str(data_dict.get('gia_chuyen_tiep_noi', 0)))
        
        values = (
            data_dict.get('ten_bang_gia', ''),
            data_dict.get('diem_di', ''),
            data_dict.get('diem_den', ''),
            data_dict.get('phan_loai_phuong_tien', 'Xe_Tai'),
            data_dict.get('loai_xe_quy_cach', ''),
            float(data_dict.get('gioi_han_kg', 0) or 0),
            float(data_dict.get('gioi_han_cbm', 0) or 0),
            int(data_dict.get('is_hang_tra_ve', 0)),
            don_gia,
            gia_tiep_noi,
            data_dict.get('ghi_chu', ''),
            rate_id
        )
        
        cursor.execute(sql, values)
        
        # Kiểm tra rowcount bắt buộc sau lệnh UPDATE[cite: 4]
        if cursor.rowcount == 0:
            raise Exception("Không tìm thấy mức giá để cập nhật hoặc dữ liệu không thay đổi.")
            
        # Ghi log hệ thống[cite: 4]
        ghi_log_he_thong(cursor, "QUAN_LY_BANG_GIA", rate_id, current_user, "CAP_NHAT_DON", json.dumps(data_dict, ensure_ascii=False))
        
        conn.commit()
        return True, "✅ Cập nhật mức giá thành công!"
    except Exception as e:
        if conn: conn.rollback()
        traceback.print_exc()
        return False, f"Lỗi hệ thống: {str(e)}"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def delete_single_rate_card_transaction(db_pool, rate_id, current_user):
    """Xóa một dòng bảng giá cụ thể theo ID"""
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False  # Bắt buộc Transaction[cite: 4]
        cursor = conn.cursor()

        cursor.execute("DELETE FROM rate_cards WHERE id = %s", (rate_id,))
        
        # Kiểm tra rowcount bắt buộc sau lệnh DELETE[cite: 4]
        if cursor.rowcount == 0:
            raise Exception("Không tìm thấy mức giá cần xóa hoặc đã bị xóa trước đó.")
            
        ghi_log_he_thong(cursor, "QUAN_LY_BANG_GIA", rate_id, current_user, "XOA_DON", json.dumps({"id": rate_id}))
        
        conn.commit()
        return True, "✅ Xóa mức giá thành công!"
    except Exception as e:
        if conn: conn.rollback()
        traceback.print_exc()
        return False, f"Lỗi hệ thống: {str(e)}"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==========================================
# 2. QUẢN LÝ PHỤ PHÍ (SURCHARGES) - SỬA/XÓA TRỰC TIẾP
# ==========================================
def update_single_phu_phi_transaction(db_pool, pp_id, data_dict, current_user):
    """Cập nhật một dòng phụ phí cụ thể theo ID"""
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False  # Bắt buộc Transaction[cite: 4]
        cursor = conn.cursor()

        sql = """
            UPDATE phu_phi_khach_hang 
            SET ten_phu_phi = %s, don_gia_phu_phi = %s, 
                dieu_kien_kich_hoat = %s, loai_ap_dung = %s, ghi_chu = %s
            WHERE id = %s
        """
        don_gia_pp = parse_money_input(str(data_dict.get('don_gia_phu_phi', 0)))
        
        values = (
            data_dict.get('ten_phu_phi', ''),
            don_gia_pp,
            data_dict.get('dieu_kien_kich_hoat', ''),
            data_dict.get('loai_ap_dung', 'Tu_Dong'),
            data_dict.get('ghi_chu', ''),
            pp_id
        )
        
        cursor.execute(sql, values)
        
        if cursor.rowcount == 0:
            raise Exception("Không tìm thấy phụ phí để cập nhật hoặc dữ liệu không thay đổi.")
            
        ghi_log_he_thong(cursor, "QUAN_LY_PHU_PHI", pp_id, current_user, "CAP_NHAT_DON", json.dumps(data_dict, ensure_ascii=False))
        
        conn.commit()
        return True, "✅ Cập nhật phụ phí thành công!"
    except Exception as e:
        if conn: conn.rollback()
        traceback.print_exc()
        return False, f"Lỗi hệ thống: {str(e)}"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def delete_single_phu_phi_transaction(db_pool, pp_id, current_user):
    """Xóa một dòng phụ phí cụ thể theo ID"""
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False  # Bắt buộc Transaction[cite: 4]
        cursor = conn.cursor()

        cursor.execute("DELETE FROM phu_phi_khach_hang WHERE id = %s", (pp_id,))
        
        if cursor.rowcount == 0:
            raise Exception("Không tìm thấy phụ phí cần xóa hoặc đã bị xóa trước đó.")
            
        ghi_log_he_thong(cursor, "QUAN_LY_PHU_PHI", pp_id, current_user, "XOA_DON", json.dumps({"id": pp_id}))
        
        conn.commit()
        return True, "✅ Xóa phụ phí thành công!"
    except Exception as e:
        if conn: conn.rollback()
        traceback.print_exc()
        return False, f"Lỗi hệ thống: {str(e)}"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
########################
def create_single_rate_card_transaction(db_pool, data_dict, current_user):
    """Thêm mới một dòng bảng giá từ giao diện UI"""
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False  # Bắt buộc Transaction
        cursor = conn.cursor()

        sql = """
            INSERT INTO rate_cards (
                khach_hang_id, ten_bang_gia, diem_di, diem_den, 
                phan_loai_phuong_tien, loai_xe_quy_cach, 
                gioi_han_kg, gioi_han_cbm, is_hang_tra_ve, 
                don_gia_cuoc, gia_chuyen_tiep_noi, ghi_chu
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        # Parse tiền tệ chuẩn xác
        don_gia = parse_money_input(str(data_dict.get('don_gia_cuoc', 0)))
        gia_tiep_noi = parse_money_input(str(data_dict.get('gia_chuyen_tiep_noi', 0)))
        
        values = (
            int(data_dict['khach_hang_id']),
            data_dict.get('ten_bang_gia', ''),
            data_dict.get('diem_di', ''),
            data_dict.get('diem_den', ''),
            data_dict.get('phan_loai_phuong_tien', 'Xe_Tai'),
            data_dict.get('loai_xe_quy_cach', ''),
            float(data_dict.get('gioi_han_kg', 0) or 0),
            float(data_dict.get('gioi_han_cbm', 0) or 0),
            int(data_dict.get('is_hang_tra_ve', 0)),
            don_gia,
            gia_tiep_noi,
            data_dict.get('ghi_chu', '')
        )
        
        cursor.execute(sql, values)
        
        # Kiểm tra rowcount bắt buộc sau lệnh INSERT
        if cursor.rowcount == 0:
            raise Exception("Lỗi Database: Không thể lưu dữ liệu.")
            
        new_id = cursor.lastrowid
        
        # Ghi log hệ thống
        from audit_logger import ghi_log_he_thong
        import json
        ghi_log_he_thong(cursor, "QUAN_LY_BANG_GIA", new_id, current_user, "THEM_MOI_DON", json.dumps(data_dict, ensure_ascii=False))
        
        conn.commit()
        return True, "✅ Thêm mới tuyến đường báo giá thành công!"
    except Exception as e:
        if conn: conn.rollback()
        import traceback
        traceback.print_exc()
        return False, f"Lỗi hệ thống: {str(e)}"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
####################################3
import json

def create_single_phu_phi_transaction(db_pool, data_add_pp, current_user):
    """
    Hàm thêm mới 1 dòng Phụ phí vào cơ sở dữ liệu.
    Tuân thủ nguyên tắc Transaction và Audit Log của Bảo Tín Logistics.
    """
    conn = None
    cursor = None
    try:
        # 1. Khởi tạo kết nối và Transaction
        conn = db_pool.get_connection()
        conn.autocommit = False
        cursor = conn.cursor()

        # 2. Thực thi lệnh INSERT
        sql_insert = """
            INSERT INTO phu_phi_khach_hang 
            (khach_hang_id, ten_phu_phi, don_gia_phu_phi, dieu_kien_kich_hoat, loai_ap_dung, ghi_chu)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        values = (
            data_add_pp.get('khach_hang_id'),
            data_add_pp.get('ten_phu_phi'),
            data_add_pp.get('don_gia_phu_phi', 0.0),
            data_add_pp.get('dieu_kien_kich_hoat'),
            data_add_pp.get('loai_ap_dung'),
            data_add_pp.get('ghi_chu')
        )
        
        cursor.execute(sql_insert, values)
        
        # Kiểm tra kết quả tác động dữ liệu
        if cursor.rowcount <= 0:
            conn.rollback()
            return False, "❌ Thêm mới phụ phí thất bại, không có dòng nào được tác động."
            
        new_id = cursor.lastrowid
        
        # 3. Ghi vết Audit Log
        from audit_logger import ghi_log_he_thong
        chi_tiet_log = json.dumps(data_add_pp, ensure_ascii=False)
        ghi_log_he_thong(
            cursor, 
            phan_he="QUAN_LY_PHU_PHI", 
            record_id=new_id, 
            nguoi_thuc_hien=current_user, 
            hanh_dong="TAO_MOI", 
            chi_tiet=chi_tiet_log
        )
        
        # 4. Xác nhận Transaction
        conn.commit()
        return True, "✅ Đã thêm mới phụ phí thành công!"
        
    except Exception as e:
        if conn:
            conn.rollback()
        return False, f"❌ Lỗi Database khi thêm phụ phí: {str(e)}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
####################
def tinh_tong_phu_cap_tu_dong(db_pool, xe_id, danh_sach_tieu_chi_id):
    """
    Hệ thống tự động dò ma trận để tính phụ cấp dựa trên Tải trọng xe và Tiêu chí phát sinh.
    Trả về: (tong_tien_phu_cap, chuoi_dien_giai_de_ghi_chu)
    """
    if not danh_sach_tieu_chi_id:
        return 0.0, ""

    conn = db_pool.get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        
        # 1. Lấy tải trọng thiết kế của xe
        cursor.execute("SELECT tai_trong_thiet_ke FROM xe WHERE id = %s", (xe_id,))
        xe_info = cursor.fetchone()
        if not xe_info or not xe_info['tai_trong_thiet_ke']:
            return 0.0, ""
            
        tai_trong_xe = float(xe_info['tai_trong_thiet_ke'])

        # 2. Tìm Khung tải trọng (tai_trong_id) tương ứng trong danh mục
        sql_tim_khung = """
            SELECT id FROM dm_tai_trong_phu_cap 
            WHERE tai_trong_min <= %s AND tai_trong_max >= %s
            ORDER BY tai_trong_min DESC LIMIT 1
        """
        cursor.execute(sql_tim_khung, (tai_trong_xe, tai_trong_xe))
        khung_tt = cursor.fetchone()
        
        if not khung_tt:
            return 0.0, "" # Không có khung phù hợp
            
        tai_trong_id = khung_tt['id']

        # 3. Tính tổng tiền từ Ma trận và lấy tên tiêu chí
        format_strings = ','.join(['%s'] * len(danh_sach_tieu_chi_id))
        sql_tinh_tien = f"""
            SELECT mt.so_tien, tc.ten_tieu_chi 
            FROM ma_tran_phu_cap mt
            JOIN dm_tieu_chi_phu_cap tc ON mt.tieu_chi_id = tc.id
            WHERE mt.tai_trong_id = %s AND mt.tieu_chi_id IN ({format_strings})
        """
        
        params = [tai_trong_id] + danh_sach_tieu_chi_id
        cursor.execute(sql_tinh_tien, tuple(params))
        ket_qua = cursor.fetchall()
        
        tong_tien = 0.0
        chi_tiet_phu_cap = []
        
        for row in ket_qua:
            tong_tien += float(row['so_tien'])
            chi_tiet_phu_cap.append(f"{row['ten_tieu_chi']} (+{float(row['so_tien']):,.0f}đ)")

        chuoi_dien_giai = " | ".join(chi_tiet_phu_cap)
        return tong_tien, chuoi_dien_giai

    except Exception as e:
        print(f"Lỗi tính phụ cấp tự động: {e}")
        return 0.0, ""
    finally:
        cursor.close()
        conn.close()
############################
import json
import pandas as pd
import re

def parse_tai_trong_excel(text):
    """Hàm AI bóc tách Tải Trọng Min/Max từ Text Excel (Ví dụ: 1<=2T, 3.5T, >15T)"""
    text = str(text).upper().replace('T', '').replace(' ', '')
    if '<=' in text:
        parts = text.split('<=')
        if len(parts) == 2:
            min_val = float(parts[0]) if parts[0] else 0.0
            max_val = float(parts[1]) if parts[1] else 99.0
            return min_val, max_val
    if '-' in text:
        parts = text.split('-')
        return float(parts[0]), float(parts[1])
    
    nums = re.findall(r'\d+\.?\d*', text)
    if nums:
        val = float(nums[0])
        return val, val # Nếu chỉ ghi "3.5T" thì min = max = 3.5
    return 0.0, 99.0
#################################################################
def import_excel_phu_cap_transaction(db_pool, df, current_user):
    """Hàm Import Excel tuân thủ Transaction & Ghi Log[cite: 5]"""
    conn = db_pool.get_connection()
    try:
        conn.autocommit = False
        cursor = conn.cursor(dictionary=True)
        
        # --- 1. XỬ LÝ TRỤC Y: BẢNG TẢI TRỌNG ---
        tt_map = {}
        cursor.execute("SELECT id, ten_hien_thi FROM dm_tai_trong_phu_cap")
        for row in cursor.fetchall(): tt_map[row['ten_hien_thi']] = row['id']
            
        tt_col = df.columns[0] # Cột đầu tiên luôn là Tải trọng
        for tt_name in df[tt_col].dropna().unique():
            if tt_name not in tt_map:
                min_val, max_val = parse_tai_trong_excel(tt_name)
                cursor.execute(
                    "INSERT INTO dm_tai_trong_phu_cap (ten_hien_thi, tai_trong_min, tai_trong_max) VALUES (%s, %s, %s)",
                    (str(tt_name).strip(), min_val, max_val)
                )
                tt_map[tt_name] = cursor.lastrowid
                
        # --- 2. XỬ LÝ TRỤC X: BẢNG TIÊU CHÍ ---
        tc_map = {}
        cursor.execute("SELECT id, ten_tieu_chi FROM dm_tieu_chi_phu_cap")
        for row in cursor.fetchall(): tc_map[row['ten_tieu_chi']] = row['id']
            
        tieu_chi_cols = df.columns[1:]
        for tc_name in tieu_chi_cols:
            tc_clean = str(tc_name).strip()
            if tc_clean not in tc_map:
                cursor.execute("INSERT INTO dm_tieu_chi_phu_cap (ten_tieu_chi) VALUES (%s)", (tc_clean,))
                tc_map[tc_clean] = cursor.lastrowid
                
        # --- 3. XỬ LÝ MA TRẬN & UPSERT DỮ LIỆU ---
        so_luong_update = 0
        for index, row in df.iterrows():
            tt_name = row[tt_col]
            if pd.isna(tt_name): continue
            tt_id = tt_map.get(tt_name)
            
            for tc_name in tieu_chi_cols:
                tc_clean = str(tc_name).strip()
                tc_id = tc_map.get(tc_clean)
                
                val = row[tc_name]
                so_tien = 0.0
                if pd.notna(val) and str(val).strip() != "":
                    try: so_tien = float(str(val).replace(",", "").replace(" ", ""))
                    except: pass
                    
                # Kiểm tra tồn tại để Insert hoặc Update
                cursor.execute("SELECT so_tien FROM ma_tran_phu_cap WHERE tai_trong_id=%s AND tieu_chi_id=%s", (tt_id, tc_id))
                if cursor.fetchone():
                    cursor.execute("UPDATE ma_tran_phu_cap SET so_tien=%s WHERE tai_trong_id=%s AND tieu_chi_id=%s", (so_tien, tt_id, tc_id))
                else:
                    cursor.execute("INSERT INTO ma_tran_phu_cap (tai_trong_id, tieu_chi_id, so_tien) VALUES (%s, %s, %s)", (tt_id, tc_id, so_tien))
                so_luong_update += 1
                
        # --- 4. GHI AUDIT LOG ---
        chi_tiet = json.dumps({"so_o_cap_nhat": so_luong_update, "nguon": "Import_Excel_2"}, ensure_ascii=False)
        cursor.execute("""
            INSERT INTO audit_logs (phan_he, nguoi_thuc_hien, hanh_dong, chi_tiet)
            VALUES (%s, %s, %s, %s)
        """, ('QUAN_LY_PHU_CAP', current_user, 'IMPORT_EXCEL_MA_TRAN', chi_tiet))
        
        conn.commit()
        return True, f"✅ Đã Import thành công toàn bộ {so_luong_update} ô dữ liệu vào Ma trận Phụ cấp!"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()