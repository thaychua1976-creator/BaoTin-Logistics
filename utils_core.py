import os
import re
import json
import time
import datetime
import logging
import traceback
import unicodedata

import requests
import pandas as pd
import streamlit as st
from PIL import Image
from dotenv import load_dotenv
from google import genai
from audit_logger import ghi_log_he_thong

# ==========================================================
# LOAD BIẾN MÔI TRƯỜNG & CẤU HÌNH API
# ==========================================================
load_dotenv()


def _get_secret_or_env(key_name, section=None, sub_key=None):
    """Lấy cấu hình ưu tiên từ st.secrets (Cloud), dự phòng biến môi trường .env (Local)."""
    try:
        if section and sub_key and section in st.secrets and sub_key in st.secrets[section]:
            return st.secrets[section][sub_key]
        if key_name in st.secrets:
            return st.secrets[key_name]
    except Exception:
        pass
    return os.getenv(key_name)


class _GeminiModelAdapter:
    """Lớp bọc tương thích hàm .generate_content() cho SDK google-genai mới."""
    def __init__(self, client, model_name):
        self.client = client
        self.model_name = model_name

    def generate_content(self, contents):
        return self.client.models.generate_content(
            model=self.model_name,
            contents=contents
        )


def get_gemini_model(model_name='gemini-2.5-flash'):
    cache_key = f"gemini_model_utils_{model_name}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    api_key = _get_secret_or_env("GEMINI_API_KEY", section="api_keys", sub_key="gemini")
    if api_key:
        client = genai.Client(api_key=api_key)
        model = _GeminiModelAdapter(client, model_name)
        st.session_state[cache_key] = model
        return model
    return None


# ==========================================================
# CÁC HÀM TIỆN ÍCH DÙNG CHUNG
# ==========================================================
def parse_money_input(val_str):
    """Xóa dấu phẩy, đơn vị tiền tệ và chuyển chuỗi thành số float an toàn."""
    if val_str is None:
        return 0.0
    if isinstance(val_str, (int, float)):
        return float(val_str)

    val_clean = str(val_str).strip()
    if not val_clean or val_clean.lower() == 'nan':
        return 0.0

    val_clean = re.sub(r'(vnđ|vnd|đ|\s)', '', val_clean, flags=re.IGNORECASE)
    val_clean = val_clean.replace(',', '')
    try:
        return float(val_clean)
    except ValueError:
        return 0.0


def _parse_surcharge_value_and_type(raw_dg_pp, loai_ap_dung_raw):
    """Chuẩn hóa đơn giá và loại áp dụng phụ phí (hỗ trợ cả số tiền cố định và phần trăm %)."""
    if pd.isna(raw_dg_pp) or str(raw_dg_pp).strip() == '':
        raw_dg_pp = 0

    loai_clean = str(loai_ap_dung_raw).strip() if pd.notna(loai_ap_dung_raw) else ''
    if not loai_clean or loai_clean.lower() == 'nan':
        loai_clean = 'Tu_Dong'

    raw_dg_str = str(raw_dg_pp).strip()
    is_percent = (
        '%' in loai_clean
        or '%' in raw_dg_str
        or loai_clean.lower() in ('phan_tram', 'phan tram', '%')
    )

    if is_percent:
        # Ưu tiên lấy số từ cột đơn giá trước, nếu không có mới tìm trong cột loại áp dụng
        match = re.search(r'(\d+(\.\d+)?)', raw_dg_str.replace(',', '.'))
        if not match:
            match = re.search(r'(\d+(\.\d+)?)', loai_clean.replace(',', '.'))
        val = 0.0
        if match:
            val = float(match.group(1))
            if 0 < val <= 1 and '%' not in raw_dg_str and '%' not in loai_clean:
                val = val * 100.0
        return val, '%'

    return parse_money_input(raw_dg_pp), loai_clean


def doc_anh_cay_xang(image_file):
    try:
        img = Image.open(image_file)

        model = get_gemini_model('gemini-2.5-flash')
        if not model:
            st.error("Lỗi: Không tìm thấy GEMINI_API_KEY trong hệ thống!")
            return None

        prompt = """
        Đây là ảnh chụp màn hình LED của trụ bơm xăng dầu ở Việt Nam (gồm 3 dòng số từ trên xuống dưới).
        Hãy đọc thật kỹ từng chữ số và vị trí dấu chấm thập phân:
        - Dòng 1 (TỔNG TIỀN): Màn hình LED 6 số thường bị khuyết 1 số 0 ở cuối (ví dụ hiển thị "3.486.60" thực tế là 3486600 đồng). Hãy đọc đúng các chữ số hiển thị.
        - Dòng 2 (SỐ LÍT): Luôn có 2 chữ số thập phân ở cuối (ví dụ "130.00" là 130.0 lít, KHÔNG đọc nhầm thành 13.0).
        - Dòng 3 (ĐƠN GIÁ): Giá 1 lít xăng/dầu tính theo VNĐ (ví dụ "26820" hoặc "26.820" là 26820 đồng, thường nằm trong khoảng 15.000 - 35.000).

        Trả về ĐÚNG định dạng JSON sau, không kèm bất kỳ văn bản nào khác:
        {
            "tong_tien_hien_thi": <số nguyên đọc được ở dòng 1, bỏ dấu chấm ngăn cách>,
            "so_lit": <số lít dạng số thập phân ở dòng 2>,
            "don_gia": <đơn giá dạng số nguyên ở dòng 3>
        }
        """
        response = model.generate_content([prompt, img])
        raw_resp = (response.text or "").replace("```json", "").replace("```", "").strip()
        match = re.search(r'\{.*\}', raw_resp, re.DOTALL)
        if not match:
            st.error("AI không trả về dữ liệu JSON hợp lệ từ ảnh trụ bơm.")
            return None

        data = json.loads(match.group(0))

        # 1. Chuẩn hóa dữ liệu thô từ AI
        raw_tien_str = re.sub(r"[^\d]", "", str(data.get("tong_tien_hien_thi") or data.get("tong_tien") or "0"))
        tien_raw = float(raw_tien_str) if raw_tien_str else 0.0

        so_lit = float(str(data.get("so_lit") or 0).replace(",", "."))
        don_gia = float(re.sub(r"[^\d.]", "", str(data.get("don_gia") or 0)))

        # Chuẩn hóa đơn giá về VNĐ (tránh trường hợp AI đọc 26.82 hoặc thiếu số 0 cuối)
        if 0 < don_gia < 100:
            don_gia = round(don_gia * 1000)
        elif 100 <= don_gia < 5000:
            don_gia = round(don_gia * 10)
        else:
            don_gia = round(don_gia)

        # 2. Đối chiếu chéo giữa Dòng 1 (Tiền hiển thị), Dòng 2 (Số lít) và Dòng 3 (Đơn giá)
        if don_gia > 0 and so_lit > 0:
            if tien_raw > 0 and abs((tien_raw * 10) - (so_lit * don_gia)) <= max(1000, don_gia * 0.3):
                tien_raw = tien_raw * 10

            if so_lit < 40 and tien_raw > 0:
                if abs(tien_raw - (so_lit * 10 * don_gia)) <= max(1000, don_gia * 0.3):
                    so_lit = round(so_lit * 10, 2)
                elif abs((tien_raw * 10) - (so_lit * 10 * don_gia)) <= max(1000, don_gia * 0.3):
                    so_lit = round(so_lit * 10, 2)
                    tien_raw = tien_raw * 10

            tong_tien = int(round(so_lit * don_gia))
        else:
            tong_tien = int(round(tien_raw))

        return {
            "tong_tien": tong_tien,
            "so_lit": round(so_lit, 2),
            "don_gia": int(don_gia)
        }
    except Exception as e:
        st.error(f"Lỗi khi AI đọc ảnh: {e}")
        return None


def gui_file_excel_len_telegram(excel_buffer, file_name, caption):
    bot_token = _get_secret_or_env("TELEGRAM_BOT_TOKEN")
    chat_id = _get_secret_or_env("CHAT_ID")

    if not bot_token or not chat_id:
        return False, "Thiếu cấu hình Telegram Token hoặc Chat ID."

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    files = {
        'document': (
            file_name,
            excel_buffer.getvalue(),
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    }
    data = {
        'chat_id': chat_id,
        'caption': caption
    }

    try:
        response = requests.post(url, data=data, files=files, timeout=30)
        return response.status_code == 200, response.json()
    except Exception as e:
        return False, str(e)


def kiem_tra_va_gui_bao_cao_telegram(df_danger, loai_bao_cao, buffer_excel):
    if df_danger.empty:
        return False, "Không có dữ liệu tới hạn, không thực hiện gửi."

    caption = (
        f"🔔 [CẢNH BÁO PHÁP LÝ {loai_bao_cao}] - {datetime.date.today().strftime('%d/%m/%Y')}\n"
        f"Số lượng cảnh báo: {len(df_danger)}"
    )
    file_name = f"Canh_Bao_{loai_bao_cao}_{datetime.date.today().strftime('%d%m%Y')}.xlsx"

    return gui_file_excel_len_telegram(buffer_excel, file_name, caption)


# ==========================================================
# MODULE ZALO API MỚI (THAY THẾ SEND_ZALO_MESSAGE CŨ)
# ==========================================================
def send_zalo_personal_message(zalo_user_id, message_text):
    """Gửi tin nhắn cá nhân cho tài xế bằng Zalo OA thông qua CS API."""
    access_token = _get_secret_or_env("ZALO_OA_ACCESS_TOKEN")

    if not access_token:
        logging.error("Thiếu ZALO_OA_ACCESS_TOKEN trong cấu hình")
        return False, "Chưa cấu hình Token OA"

    api_url = "https://openapi.zalo.me/v3.0/oa/message/cs"
    headers = {
        "Content-Type": "application/json",
        "access_token": access_token
    }
    payload = {
        "recipient": {"user_id": zalo_user_id},
        "message": {"text": message_text}
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            result = response.json()
            if result.get("error") == 0:
                return True, "Thành công"
            return False, f"Lỗi Zalo: {result.get('message', 'Không xác định')}"
        return False, f"Lỗi HTTP: {response.status_code}"
    except Exception as e:
        return False, f"Lỗi hệ thống: {str(e)}"


def send_zalo_gmf_message(group_id, message_text):
    """Gửi tin nhắn vào nhóm Zalo bằng Official Account (GMF API)."""
    access_token = _get_secret_or_env("ZALO_OA_ACCESS_TOKEN")

    if not access_token:
        logging.error("Thiếu ZALO_OA_ACCESS_TOKEN trong cấu hình")
        return False, "Chưa cấu hình Token"

    api_url = "https://openapi.zalo.me/v3.0/oa/group/message"
    headers = {
        "Content-Type": "application/json",
        "access_token": access_token
    }
    payload = {
        "group_id": group_id,
        "message": {"text": message_text}
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            result = response.json()
            if result.get("error") == 0:
                return True, "Thành công"
            return False, f"Lỗi Zalo: {result.get('message', 'Không xác định')}"
        return False, f"Lỗi HTTP: {response.status_code}"
    except Exception as e:
        return False, f"Lỗi hệ thống: {str(e)}"


def tao_tieu_de_kem_nut_refresh(tieu_de, key_duy_nhat):
    """Hàm tạo tiêu đề Tab kèm nút Refresh đồng bộ."""
    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.markdown(f"#### {tieu_de}")
    with col_btn:
        if st.button("🔄 Làm mới dữ liệu", key=key_duy_nhat, use_container_width=True):
            st.cache_data.clear()

            keys_to_clear = [
                k for k in st.session_state.keys()
                if k.startswith("df_") or k.startswith("cache_")
            ]
            for k in keys_to_clear:
                del st.session_state[k]

            for counter in ["form_reset_counter", "reset_chuyen_form", "reset_sqt", "reset_file_upload"]:
                if counter in st.session_state:
                    st.session_state[counter] += 1

            st.rerun()
    st.divider()


# ==========================================================
# CÁC HÀM XỬ LÝ DỮ LIỆU & IMPORT BẢNG GIÁ / PHỤ PHÍ
# ==========================================================
def clean_limit_number(val):
    """Làm sạch các chuỗi giới hạn như '<=6', '< 10 KGS', '<=25CBM' thành số float an toàn."""
    if val is None:
        return 0.0
    val_str = str(val).strip()
    if not val_str or val_str.lower() == 'nan':
        return 0.0

    match = re.findall(r"[-+]?\d*\.\d+|\d+", val_str)
    if match:
        try:
            return float(match[0])
        except ValueError:
            return 0.0
    return 0.0


def normalize_text(text):
    """Chuẩn hóa chuỗi tiếng Việt (NFC) để so sánh chính xác, xóa khoảng trắng thừa."""
    if pd.isna(text) or text is None:
        return ""
    text = unicodedata.normalize('NFC', str(text))
    return re.sub(r'\s+', ' ', text).strip().upper()


def parse_float_safe(val):
    """Bóc tách số an toàn, kể cả khi dính chữ (VD: '150 km' -> 150.0)."""
    if pd.isna(val) or val is None or str(val).strip() == '':
        return 0.0
    try:
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(val).replace(',', ''))
        if nums:
            return float(nums[0])
        return 0.0
    except Exception:
        return 0.0


def import_bang_gia_transaction(db_pool, df_rates, df_surcharges, current_user):
    """
    Import dữ liệu Biểu cước và Phụ phí từ DataFrame vào MySQL (lần đầu).
    Tự động tách dòng cước chiều về nếu có cột PHU_PHI_CHIEU_VE.
    """
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id, ma_khach_hang, ten_khach_hang FROM khach_hang")
        kh_list = cursor.fetchall()
        kh_map_ma = {normalize_text(k['ma_khach_hang']): k['id'] for k in kh_list if k['ma_khach_hang']}
        kh_map_ten = {normalize_text(k['ten_khach_hang']): k['id'] for k in kh_list if k['ten_khach_hang']}

        def find_kh_id(tu_khoa):
            key = normalize_text(tu_khoa)
            return kh_map_ma.get(key) or kh_map_ten.get(key)

        rates_inserted = 0
        surcharges_inserted = 0

        if df_rates is not None and not df_rates.empty:
            sql_insert_rate = """
                INSERT INTO rate_cards (
                    khach_hang_id, ten_bang_gia, diem_di, diem_den,
                    phan_loai_phuong_tien, loai_xe_quy_cach, gioi_han_kg,
                    gioi_han_cbm, is_hang_tra_ve, don_gia_cuoc, gia_chuyen_tiep_noi, khoang_cach, ghi_chu
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            for _, row in df_rates.iterrows():
                kh_id = find_kh_id(row.get('KHACH_HANG'))
                if not kh_id:
                    continue

                ten_bang_gia = str(row.get('TEN_BANG_GIA', '')).strip()
                if ten_bang_gia.lower() == 'nan':
                    ten_bang_gia = ''
                diem_di = normalize_text(row.get('DIEM_DI', ''))
                diem_den = normalize_text(row.get('DIEM_DEN', ''))
                khoang_cach = clean_limit_number(row.get('KHOANG_CACH', 0))
                phan_loai = str(row.get('PHAN_LOAI_PHUONG_TIEN', '')).strip()
                loai_xe = str(row.get('LOAI_XE_QUY_CACH', '')).strip()
                gh_kg = clean_limit_number(row.get('GIOI_HAN_KG', 0))
                gh_cbm = clean_limit_number(row.get('GIOI_HAN_CBM', 0))

                ghi_chu_val = str(row.get('GHI_CHU', '')).strip()
                if ghi_chu_val.lower() == 'nan':
                    ghi_chu_val = ''

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

                if gia_tiep_noi_val <= 1:
                    gia_tiep_noi_val = 0.0

                if don_gia_di > 0:
                    val_di = (
                        kh_id, ten_bang_gia, diem_di, diem_den,
                        phan_loai, loai_xe, gh_kg, gh_cbm,
                        0, don_gia_di, gia_tiep_noi_val, khoang_cach,
                        ghi_chu_val if ghi_chu_val else None
                    )
                    cursor.execute(sql_insert_rate, val_di)
                    if cursor.rowcount > 0:
                        rates_inserted += 1

                raw_phu_phi_ve = row.get('PHU_PHI_CHIEU_VE', '')
                gia_chieu_ve = 0.0
                if pd.notna(raw_phu_phi_ve) and raw_phu_phi_ve != '' and raw_phu_phi_ve != 0:
                    if isinstance(raw_phu_phi_ve, (int, float)):
                        if 0 < raw_phu_phi_ve <= 1.0:
                            gia_chieu_ve = don_gia_di * float(raw_phu_phi_ve)
                        else:
                            gia_chieu_ve = float(raw_phu_phi_ve)
                    else:
                        phu_phi_ve_str = str(raw_phu_phi_ve).strip().lower()
                        if '%' in phu_phi_ve_str:
                            clean_percent = phu_phi_ve_str.replace('%', '').strip()
                            try:
                                ty_le = float(clean_percent) / 100.0
                                gia_chieu_ve = don_gia_di * ty_le
                            except ValueError:
                                gia_chieu_ve = 0.0
                        else:
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
                    val_ve = (
                        kh_id, ten_bang_gia, diem_den, diem_di,
                        phan_loai, loai_xe, gh_kg, gh_cbm,
                        1, gia_chieu_ve, 0.0, khoang_cach,
                        ghi_chu_val if ghi_chu_val else None
                    )
                    cursor.execute(sql_insert_rate, val_ve)
                    if cursor.rowcount > 0:
                        rates_inserted += 1

        if df_surcharges is not None and not df_surcharges.empty:
            sql_insert_sc = """
                INSERT INTO phu_phi_khach_hang (
                    khach_hang_id, ten_phu_phi, don_gia_phu_phi,
                    dieu_kien_kich_hoat, loai_ap_dung, ghi_chu
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """
            for _, row in df_surcharges.iterrows():
                kh_id = find_kh_id(row.get('KHACH_HANG'))
                if not kh_id:
                    continue

                don_gia_pp, loai_ap_dung = _parse_surcharge_value_and_type(
                    row.get('DON_GIA', 0),
                    row.get('LOAI_AP_DUNG', 'Tu_Dong')
                )
                ghi_chu_pp = str(row.get('GHI_CHU', '')).strip()
                if ghi_chu_pp.lower() == 'nan':
                    ghi_chu_pp = ''

                if don_gia_pp > 0:
                    val = (
                        kh_id,
                        str(row.get('TEN_PHU_PHI', '')).strip(),
                        don_gia_pp,
                        str(row.get('DIEU_KIEN_KICH_HOAT', '')).strip().upper(),
                        loai_ap_dung,
                        ghi_chu_pp if ghi_chu_pp else None
                    )
                    cursor.execute(sql_insert_sc, val)
                    if cursor.rowcount > 0:
                        surcharges_inserted += 1

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

        conn.commit()
        return True, f"✅ Import thành công: {rates_inserted} dòng Biểu cước (Đã tự động tính chiều về) và {surcharges_inserted} dòng Phụ phí."

    except Exception as e:
        if conn:
            conn.rollback()
        traceback.print_exc()
        return False, f"Lỗi Import Database: {str(e)}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def import_and_update_bang_gia_transaction(db_pool, df_rates, df_surcharges, current_user):
    """
    Import/Update Bảng giá từ Excel (xử lý chuẩn Unicode NFC, chống trùng và cập nhật tiến độ).
    """
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id, ten_khach_hang, ma_khach_hang FROM khach_hang")
        kh_list = cursor.fetchall()
        kh_map = {normalize_text(k['ten_khach_hang']): k['id'] for k in kh_list if k['ten_khach_hang']}
        kh_map_ma = {normalize_text(k['ma_khach_hang']): k['id'] for k in kh_list if k['ma_khach_hang']}

        rates_inserted, rates_updated, rates_skipped = 0, 0, 0
        sc_inserted, sc_updated, sc_skipped = 0, 0, 0

        total_steps = (len(df_rates) if df_rates is not None else 0) + (len(df_surcharges) if df_surcharges is not None else 0)
        current_step = 0

        if total_steps > 0:
            progress_bar = st.progress(0)
            status_text = st.empty()
        else:
            return False, "File Excel trống hoặc không có dữ liệu."

        # 1. XỬ LÝ BẢNG GIÁ (RATE CARDS)
        if df_rates is not None and not df_rates.empty:
            col_khoang_cach = None
            for c in df_rates.columns:
                c_clean = normalize_text(c).replace(' ', '').replace('_', '')
                if 'KHOANGCACH' in c_clean or 'SOKM' in c_clean or 'CỰLY' in c_clean:
                    col_khoang_cach = c
                    break

            for _, row in df_rates.iterrows():
                current_step += 1
                if current_step % 50 == 0 or current_step == total_steps:
                    progress_bar.progress(current_step / total_steps)
                    status_text.markdown(f"**⏳ Đang cập nhật Bảng Giá:** Dòng {current_step}/{total_steps}")

                bg_id = row.get('ID')
                if pd.isna(bg_id) or str(bg_id).strip() == '':
                    bg_id = None
                else:
                    try:
                        bg_id = int(float(bg_id))
                    except Exception:
                        bg_id = None

                kh_raw = row.get('KHACH_HANG') if pd.notna(row.get('KHACH_HANG')) else row.get('TEN_KHACH_HANG', '')
                kh_str = normalize_text(kh_raw)
                kh_id = kh_map.get(kh_str) or kh_map_ma.get(kh_str)

                if not kh_id:
                    rates_skipped += 1
                    continue

                diem_di = normalize_text(row.get('DIEM_DI') if pd.notna(row.get('DIEM_DI')) else row.get('DIA_CHI_KHO_DI', ''))
                diem_den = normalize_text(row.get('DIEM_DEN') if pd.notna(row.get('DIEM_DEN')) else row.get('DIA_CHI_KHO_DEN', ''))

                khoang_cach = parse_float_safe(row.get(col_khoang_cach, 0)) if col_khoang_cach else parse_float_safe(row.get('KHOANG_CACH', 0))

                if not diem_di or not diem_den or diem_di == 'NAN' or diem_den == 'NAN':
                    rates_skipped += 1
                    continue

                ten_bg = str(row.get('TEN_BANG_GIA', '')).strip()
                if ten_bg.lower() == 'nan':
                    ten_bg = ''

                phan_loai = str(row.get('PHAN_LOAI_PHUONG_TIEN', 'Xe_Tai')).strip()
                quy_cach = str(row.get('LOAI_XE_QUY_CACH', '')).strip()
                if quy_cach.lower() == 'nan':
                    quy_cach = ''

                gh_kg = parse_float_safe(row.get('GIOI_HAN_KG', 0))
                gh_cbm = parse_float_safe(row.get('GIOI_HAN_CBM', 0))

                is_tra_ve = 1 if str(row.get('IS_HANG_TRA_VE', '0')).strip() in ['1', '1.0', 'True', 'true'] else 0
                ghi_chu = str(row.get('GHI_CHU', '')).strip()
                if ghi_chu.lower() == 'nan':
                    ghi_chu = ''

                raw_don_gia = row.get('DON_GIA_CUOC') if pd.notna(row.get('DON_GIA_CUOC')) else row.get('DON_GIA', 0)
                don_gia_di = parse_money_input(raw_don_gia)

                raw_gia_tiep_noi = row.get('GIA_CHUYEN_TIEP_NOI', 0)
                gia_tiep_noi_val = parse_money_input(raw_gia_tiep_noi)
                if gia_tiep_noi_val <= 1:
                    gia_tiep_noi_val = 0.0

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
                        bg_id = dup_row['id']

                if bg_id:
                    sql_update = """
                        UPDATE rate_cards
                        SET khach_hang_id=%s, ten_bang_gia=%s, diem_di=%s, diem_den=%s,
                            phan_loai_phuong_tien=%s, loai_xe_quy_cach=%s, gioi_han_kg=%s, gioi_han_cbm=%s,
                            is_hang_tra_ve=%s, don_gia_cuoc=%s, gia_chuyen_tiep_noi=%s, khoang_cach=%s, ghi_chu=%s
                        WHERE id=%s
                    """
                    cursor.execute(sql_update, (
                        kh_id, ten_bg, diem_di, diem_den, phan_loai, quy_cach,
                        gh_kg, gh_cbm, is_tra_ve, don_gia_di, gia_tiep_noi_val,
                        khoang_cach, ghi_chu, bg_id
                    ))
                    rates_updated += 1
                else:
                    if don_gia_di > 0:
                        sql_insert = """
                            INSERT INTO rate_cards (
                                khach_hang_id, ten_bang_gia, diem_di, diem_den,
                                phan_loai_phuong_tien, loai_xe_quy_cach, gioi_han_kg, gioi_han_cbm,
                                is_hang_tra_ve, don_gia_cuoc, gia_chuyen_tiep_noi, khoang_cach, ghi_chu
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(sql_insert, (
                            kh_id, ten_bg, diem_di, diem_den, phan_loai, quy_cach,
                            gh_kg, gh_cbm, is_tra_ve, don_gia_di, gia_tiep_noi_val,
                            khoang_cach, ghi_chu
                        ))
                        rates_inserted += 1

                # XỬ LÝ CHIỀU VỀ
                raw_phu_phi_ve = row.get('PHU_PHI_CHIEU_VE', '')
                gia_chieu_ve = 0.0
                if pd.notna(raw_phu_phi_ve) and str(raw_phu_phi_ve).strip() not in ['', '0', '0.0', 'nan']:
                    phu_phi_ve_str = str(raw_phu_phi_ve).strip().lower()
                    if '%' in phu_phi_ve_str:
                        try:
                            gia_chieu_ve = don_gia_di * (float(phu_phi_ve_str.replace('%', '').strip()) / 100.0)
                        except Exception:
                            pass
                    else:
                        try:
                            val_float = float(phu_phi_ve_str)
                            gia_chieu_ve = don_gia_di * val_float if 0 < val_float <= 1.0 else parse_money_input(phu_phi_ve_str)
                        except Exception:
                            gia_chieu_ve = parse_money_input(phu_phi_ve_str)

                if gia_chieu_ve > 0:
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
                        sql_up_ve = "UPDATE rate_cards SET don_gia_cuoc=%s, gia_chuyen_tiep_noi=0.0, khoang_cach=%s, ghi_chu=%s WHERE id=%s"
                        cursor.execute(sql_up_ve, (gia_chieu_ve, khoang_cach, ghi_chu, dup_ve['id']))
                        rates_updated += 1
                    else:
                        sql_ins_ve = """
                            INSERT INTO rate_cards (
                                khach_hang_id, ten_bang_gia, diem_di, diem_den,
                                phan_loai_phuong_tien, loai_xe_quy_cach, gioi_han_kg, gioi_han_cbm,
                                is_hang_tra_ve, don_gia_cuoc, gia_chuyen_tiep_noi, khoang_cach, ghi_chu
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(sql_ins_ve, (
                            kh_id, ten_bg, diem_den, diem_di, phan_loai, quy_cach,
                            gh_kg, gh_cbm, 1, gia_chieu_ve, 0.0, khoang_cach, ghi_chu
                        ))
                        rates_inserted += 1

        # 2. XỬ LÝ PHỤ PHÍ
        if df_surcharges is not None and not df_surcharges.empty:
            for index, row in df_surcharges.iterrows():
                current_step += 1
                if current_step % 50 == 0 or current_step == total_steps:
                    progress_bar.progress(current_step / total_steps)
                    status_text.markdown(f"**⏳ Đang xử lý Phụ Phí:** Dòng {index + 1}/{len(df_surcharges)}")

                pp_id = row.get('ID')
                if pd.isna(pp_id) or str(pp_id).strip() == '':
                    pp_id = None
                else:
                    try:
                        pp_id = int(float(pp_id))
                    except Exception:
                        pp_id = None

                kh_raw = row.get('KHACH_HANG') if pd.notna(row.get('KHACH_HANG')) else row.get('TEN_KHACH_HANG', '')
                kh_str = normalize_text(kh_raw)
                kh_id = kh_map.get(kh_str) or kh_map_ma.get(kh_str)

                if not kh_id:
                    sc_skipped += 1
                    continue

                ten_phu_phi = str(row.get('TEN_PHU_PHI', '')).strip()
                if not ten_phu_phi or ten_phu_phi.lower() == 'nan':
                    continue

                if not pp_id:
                    cursor.execute(
                        "SELECT id FROM phu_phi_khach_hang WHERE khach_hang_id = %s AND ten_phu_phi = %s LIMIT 1",
                        (kh_id, ten_phu_phi)
                    )
                    dup_pp = cursor.fetchone()
                    if dup_pp:
                        pp_id = dup_pp['id']

                raw_dg_pp = row.get('DON_GIA_PHU_PHI') if pd.notna(row.get('DON_GIA_PHU_PHI')) else row.get('DON_GIA', 0)
                don_gia_pp, loai_ap_dung = _parse_surcharge_value_and_type(raw_dg_pp, row.get('LOAI_AP_DUNG', 'Tu_Dong'))

                dk_kich_hoat = str(row.get('DIEU_KIEN_KICH_HOAT', '')).strip().upper()
                if dk_kich_hoat.lower() == 'nan':
                    dk_kich_hoat = ''
                ghi_chu = str(row.get('GHI_CHU', '')).strip()
                if ghi_chu.lower() == 'nan':
                    ghi_chu = ''

                if pp_id:
                    sql_update = """
                        UPDATE phu_phi_khach_hang
                        SET khach_hang_id=%s, ten_phu_phi=%s, don_gia_phu_phi=%s,
                            dieu_kien_kich_hoat=%s, loai_ap_dung=%s, ghi_chu=%s
                        WHERE id=%s
                    """
                    cursor.execute(sql_update, (kh_id, ten_phu_phi, don_gia_pp, dk_kich_hoat, loai_ap_dung, ghi_chu, pp_id))
                    sc_updated += 1
                else:
                    sql_insert = """
                        INSERT INTO phu_phi_khach_hang (
                            khach_hang_id, ten_phu_phi, don_gia_phu_phi,
                            dieu_kien_kich_hoat, loai_ap_dung, ghi_chu
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(sql_insert, (kh_id, ten_phu_phi, don_gia_pp, dk_kich_hoat, loai_ap_dung, ghi_chu))
                    sc_inserted += 1

        # 3. HOÀN TẤT & GHI LOG
        progress_bar.progress(1.0)
        status_text.success("✅ Đã ghi nhận toàn bộ dữ liệu vào hệ thống!")

        log_detail = json.dumps({
            "rate_cards": {"new": rates_inserted, "update": rates_updated, "skipped": rates_skipped},
            "surcharges": {"new": sc_inserted, "update": sc_updated, "skipped": sc_skipped}
        }, ensure_ascii=False)
        ghi_log_he_thong(cursor, "QUAN_LY_BANG_GIA", None, current_user, "IMPORT_EXCEL_CAP_NHAT", log_detail)

        conn.commit()
        time.sleep(0.5)
        progress_bar.empty()
        status_text.empty()

        msg = f"""
        📊 **BẢNG GIÁ:** Đã cập nhật **{rates_updated}**, Thêm mới **{rates_inserted}**. (Bỏ qua {rates_skipped} dòng không hợp lệ)
        🏷️ **PHỤ PHÍ:** Đã cập nhật **{sc_updated}**, Thêm mới **{sc_inserted}**. (Bỏ qua {sc_skipped} dòng không hợp lệ)
        """
        return True, msg

    except Exception as e:
        if conn:
            conn.rollback()
        return False, f"Lỗi hệ thống khi Import: {str(e)}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def import_and_update_phu_phi_transaction(db_pool, df_surcharges, current_user):
    """
    Import/Update Phụ phí khách hàng từ Excel. Tự động chống trùng theo (khach_hang_id, ten_phu_phi).
    """
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id, ten_khach_hang, ma_khach_hang FROM khach_hang")
        kh_list = cursor.fetchall()
        kh_map_ten = {normalize_text(k['ten_khach_hang']): k['id'] for k in kh_list if k['ten_khach_hang']}
        kh_map_ma = {normalize_text(k['ma_khach_hang']): k['id'] for k in kh_list if k['ma_khach_hang']}

        row_inserted = 0
        row_updated = 0
        row_skipped = 0

        for _, row in df_surcharges.iterrows():
            pp_id = row.get('ID')
            if pd.isna(pp_id) or str(pp_id).strip() == '':
                pp_id = None
            else:
                try:
                    pp_id = int(float(pp_id))
                except Exception:
                    pp_id = None

            kh_raw = row.get('KHACH_HANG')
            if pd.isna(kh_raw) or str(kh_raw).strip() == '':
                kh_raw = row.get('TEN_KHACH_HANG', '')

            kh_str = normalize_text(kh_raw)
            kh_id = kh_map_ten.get(kh_str) or kh_map_ma.get(kh_str)
            if not kh_id:
                row_skipped += 1
                continue

            ten_phu_phi = str(row.get('TEN_PHU_PHI', '')).strip()
            if not ten_phu_phi or ten_phu_phi.lower() == 'nan':
                continue

            if not pp_id:
                cursor.execute(
                    "SELECT id FROM phu_phi_khach_hang WHERE khach_hang_id = %s AND ten_phu_phi = %s LIMIT 1",
                    (kh_id, ten_phu_phi)
                )
                dup_pp = cursor.fetchone()
                if dup_pp:
                    pp_id = dup_pp['id']

            raw_dg_pp = row.get('DON_GIA_PHU_PHI')
            if pd.isna(raw_dg_pp) or str(raw_dg_pp).strip() == '':
                raw_dg_pp = row.get('DON_GIA', 0)

            don_gia_pp, loai_ap_dung = _parse_surcharge_value_and_type(raw_dg_pp, row.get('LOAI_AP_DUNG', 'Tu_Dong'))

            dk_kich_hoat = str(row.get('DIEU_KIEN_KICH_HOAT', '')).strip().upper()
            if dk_kich_hoat.lower() == 'nan':
                dk_kich_hoat = ''

            ghi_chu = str(row.get('GHI_CHU', '')).strip()
            if ghi_chu.lower() == 'nan':
                ghi_chu = ''

            if pp_id:
                sql_update = """
                    UPDATE phu_phi_khach_hang
                    SET khach_hang_id=%s, ten_phu_phi=%s, don_gia_phu_phi=%s,
                        dieu_kien_kich_hoat=%s, loai_ap_dung=%s, ghi_chu=%s
                    WHERE id=%s
                """
                cursor.execute(sql_update, (kh_id, ten_phu_phi, don_gia_pp, dk_kich_hoat, loai_ap_dung, ghi_chu, pp_id))
                row_updated += 1
            else:
                sql_insert = """
                    INSERT INTO phu_phi_khach_hang (
                        khach_hang_id, ten_phu_phi, don_gia_phu_phi,
                        dieu_kien_kich_hoat, loai_ap_dung, ghi_chu
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql_insert, (kh_id, ten_phu_phi, don_gia_pp, dk_kich_hoat, loai_ap_dung, ghi_chu))
                if cursor.rowcount > 0:
                    row_inserted += 1

        log_detail = json.dumps({
            "phu_phi_moi": row_inserted,
            "phu_phi_cap_nhat": row_updated,
            "phu_phi_bo_qua": row_skipped
        }, ensure_ascii=False)
        ghi_log_he_thong(cursor, "QUAN_LY_PHU_PHI", None, current_user, "IMPORT_EXCEL_PHU_PHI", log_detail)

        conn.commit()

        msg = f"Đã cập nhật {row_updated} phụ phí | Thêm mới {row_inserted}."
        if row_skipped > 0:
            msg += f" (⚠️ Đã bỏ qua {row_skipped} dòng do sai tên Khách hàng)."
        return True, msg

    except Exception as e:
        if conn:
            conn.rollback()
        traceback.print_exc()
        return False, f"Lỗi hệ thống khi Import Phụ phí: {str(e)}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ==========================================
# 1. QUẢN LÝ BẢNG GIÁ (RATE CARDS) - SỬA/XÓA/THÊM TRỰC TIẾP
# ==========================================
def update_single_rate_card_transaction(db_pool, rate_id, data_dict, current_user):
    """Cập nhật một dòng bảng giá cụ thể theo ID."""
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False
        cursor = conn.cursor()

        sql = """
            UPDATE rate_cards
            SET ten_bang_gia = %s, diem_di = %s, diem_den = %s,
                phan_loai_phuong_tien = %s, loai_xe_quy_cach = %s,
                gioi_han_kg = %s, gioi_han_cbm = %s, is_hang_tra_ve = %s,
                don_gia_cuoc = %s, gia_chuyen_tiep_noi = %s, khoang_cach = %s, ghi_chu = %s
            WHERE id = %s
        """
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
            float(data_dict.get('khoang_cach', 0) or 0),
            data_dict.get('ghi_chu', ''),
            rate_id
        )

        cursor.execute(sql, values)

        if cursor.rowcount == 0:
            raise Exception("Không tìm thấy mức giá để cập nhật hoặc dữ liệu không thay đổi.")

        ghi_log_he_thong(cursor, "QUAN_LY_BANG_GIA", rate_id, current_user, "CAP_NHAT_DON", json.dumps(data_dict, ensure_ascii=False))

        conn.commit()
        return True, "✅ Cập nhật mức giá thành công!"
    except Exception as e:
        if conn:
            conn.rollback()
        traceback.print_exc()
        return False, f"Lỗi hệ thống: {str(e)}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def delete_single_rate_card_transaction(db_pool, rate_id, current_user):
    """Xóa một dòng bảng giá cụ thể theo ID."""
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False
        cursor = conn.cursor()

        cursor.execute("DELETE FROM rate_cards WHERE id = %s", (rate_id,))

        if cursor.rowcount == 0:
            raise Exception("Không tìm thấy mức giá cần xóa hoặc đã bị xóa trước đó.")

        ghi_log_he_thong(cursor, "QUAN_LY_BANG_GIA", rate_id, current_user, "XOA_DON", json.dumps({"id": rate_id}))

        conn.commit()
        return True, "✅ Xóa mức giá thành công!"
    except Exception as e:
        if conn:
            conn.rollback()
        traceback.print_exc()
        return False, f"Lỗi hệ thống: {str(e)}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def create_single_rate_card_transaction(db_pool, data_dict, current_user):
    """Thêm mới một dòng bảng giá từ giao diện UI."""
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False
        cursor = conn.cursor()

        sql = """
            INSERT INTO rate_cards (
                khach_hang_id, ten_bang_gia, diem_di, diem_den,
                phan_loai_phuong_tien, loai_xe_quy_cach,
                gioi_han_kg, gioi_han_cbm, is_hang_tra_ve,
                don_gia_cuoc, gia_chuyen_tiep_noi, khoang_cach, ghi_chu
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
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
            float(data_dict.get('khoang_cach', 0) or 0),
            data_dict.get('ghi_chu', '')
        )

        cursor.execute(sql, values)

        if cursor.rowcount == 0:
            raise Exception("Lỗi Database: Không thể lưu dữ liệu.")

        new_id = cursor.lastrowid
        ghi_log_he_thong(cursor, "QUAN_LY_BANG_GIA", new_id, current_user, "THEM_MOI_DON", json.dumps(data_dict, ensure_ascii=False))

        conn.commit()
        return True, "✅ Thêm mới tuyến đường báo giá thành công!"
    except Exception as e:
        if conn:
            conn.rollback()
        traceback.print_exc()
        return False, f"Lỗi hệ thống: {str(e)}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ==========================================
# 2. QUẢN LÝ PHỤ PHÍ (SURCHARGES) - SỬA/XÓA/THÊM TRỰC TIẾP
# ==========================================
def update_single_phu_phi_transaction(db_pool, pp_id, data_dict, current_user):
    """Cập nhật một dòng phụ phí cụ thể theo ID."""
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False
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
        if conn:
            conn.rollback()
        traceback.print_exc()
        return False, f"Lỗi hệ thống: {str(e)}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def delete_single_phu_phi_transaction(db_pool, pp_id, current_user):
    """Xóa một dòng phụ phí cụ thể theo ID."""
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False
        cursor = conn.cursor()

        cursor.execute("DELETE FROM phu_phi_khach_hang WHERE id = %s", (pp_id,))

        if cursor.rowcount == 0:
            raise Exception("Không tìm thấy phụ phí cần xóa hoặc đã bị xóa trước đó.")

        ghi_log_he_thong(cursor, "QUAN_LY_PHU_PHI", pp_id, current_user, "XOA_DON", json.dumps({"id": pp_id}))

        conn.commit()
        return True, "✅ Xóa phụ phí thành công!"
    except Exception as e:
        if conn:
            conn.rollback()
        traceback.print_exc()
        return False, f"Lỗi hệ thống: {str(e)}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def create_single_phu_phi_transaction(db_pool, data_add_pp, current_user):
    """Thêm mới 1 dòng Phụ phí vào cơ sở dữ liệu."""
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False
        cursor = conn.cursor()

        sql_insert = """
            INSERT INTO phu_phi_khach_hang
            (khach_hang_id, ten_phu_phi, don_gia_phu_phi, dieu_kien_kich_hoat, loai_ap_dung, ghi_chu)
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        don_gia_pp = parse_money_input(data_add_pp.get('don_gia_phu_phi', 0.0))

        values = (
            data_add_pp.get('khach_hang_id'),
            data_add_pp.get('ten_phu_phi'),
            don_gia_pp,
            data_add_pp.get('dieu_kien_kich_hoat'),
            data_add_pp.get('loai_ap_dung'),
            data_add_pp.get('ghi_chu')
        )

        cursor.execute(sql_insert, values)

        if cursor.rowcount <= 0:
            conn.rollback()
            return False, "❌ Thêm mới phụ phí thất bại, không có dòng nào được tác động."

        new_id = cursor.lastrowid
        chi_tiet_log = json.dumps(data_add_pp, ensure_ascii=False)
        ghi_log_he_thong(
            cursor,
            phan_he="QUAN_LY_PHU_PHI",
            record_id=new_id,
            nguoi_thuc_hien=current_user,
            hanh_dong="TAO_MOI",
            chi_tiet=chi_tiet_log
        )

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


# ==========================================
# 3. MA TRẬN PHỤ CẤP TÀI XẾ (TỰ ĐỘNG & IMPORT EXCEL)
# ==========================================
def tinh_tong_phu_cap_tu_dong(db_pool, xe_id, danh_sach_tieu_chi_id):
    """
    Hệ thống tự động dò ma trận để tính phụ cấp dựa trên Tải trọng xe và Tiêu chí phát sinh.
    Trả về: (tong_tien_phu_cap, chuoi_dien_giai_de_ghi_chu)
    """
    if not danh_sach_tieu_chi_id:
        return 0.0, ""

    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT tai_trong_thiet_ke FROM xe WHERE id = %s", (xe_id,))
        xe_info = cursor.fetchone()
        if not xe_info or not xe_info['tai_trong_thiet_ke']:
            return 0.0, ""

        tai_trong_xe = float(xe_info['tai_trong_thiet_ke'])

        sql_tim_khung = """
            SELECT id FROM dm_tai_trong_phu_cap
            WHERE tai_trong_min <= %s AND tai_trong_max >= %s
            ORDER BY tai_trong_min DESC LIMIT 1
        """
        cursor.execute(sql_tim_khung, (tai_trong_xe, tai_trong_xe))
        khung_tt = cursor.fetchone()

        if not khung_tt:
            return 0.0, ""

        tai_trong_id = khung_tt['id']

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
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def parse_tai_trong_excel(text):
    """Bóc tách Tải Trọng Min/Max từ Text Excel (Ví dụ: 1<=2T, 3.5T, >15T, <2T)."""
    text_clean = str(text).upper().replace('TẤN', '').replace('TAN', '').replace('T', '').replace(' ', '')
    if '<=' in text_clean:
        parts = text_clean.split('<=')
        if len(parts) == 2:
            min_val = float(parts[0]) if parts[0] else 0.0
            max_val = float(parts[1]) if parts[1] else 99.0
            return min_val, max_val
    if '>=' in text_clean:
        parts = text_clean.split('>=')
        if len(parts) == 2:
            min_val = float(parts[1]) if parts[1] else 0.0
            return min_val, 99.0
    if text_clean.startswith('>'):
        nums = re.findall(r'\d+\.?\d*', text_clean)
        if nums:
            return float(nums[0]), 99.0
    if text_clean.startswith('<'):
        nums = re.findall(r'\d+\.?\d*', text_clean)
        if nums:
            return 0.0, float(nums[0])
    if '-' in text_clean:
        parts = text_clean.split('-')
        if len(parts) == 2:
            try:
                return float(parts[0]), float(parts[1])
            except ValueError:
                pass

    nums = re.findall(r'\d+\.?\d*', text_clean)
    if nums:
        val = float(nums[0])
        return val, val
    return 0.0, 99.0


def import_excel_phu_cap_transaction(db_pool, df, current_user):
    """Hàm Import Excel Ma trận phụ cấp tuân thủ Transaction & Ghi Log."""
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False
        cursor = conn.cursor(dictionary=True)

        # 1. XỬ LÝ TRỤC Y: BẢNG TẢI TRỌNG
        tt_map = {}
        cursor.execute("SELECT id, ten_hien_thi FROM dm_tai_trong_phu_cap")
        for row in cursor.fetchall():
            tt_map[str(row['ten_hien_thi']).strip()] = row['id']

        tt_col = df.columns[0]
        for tt_name in df[tt_col].dropna().unique():
            tt_clean = str(tt_name).strip()
            if not tt_clean:
                continue
            if tt_clean not in tt_map:
                min_val, max_val = parse_tai_trong_excel(tt_clean)
                cursor.execute(
                    "INSERT INTO dm_tai_trong_phu_cap (ten_hien_thi, tai_trong_min, tai_trong_max) VALUES (%s, %s, %s)",
                    (tt_clean, min_val, max_val)
                )
                tt_map[tt_clean] = cursor.lastrowid

        # 2. XỬ LÝ TRỤC X: BẢNG TIÊU CHÍ
        tc_map = {}
        cursor.execute("SELECT id, ten_tieu_chi FROM dm_tieu_chi_phu_cap")
        for row in cursor.fetchall():
            tc_map[str(row['ten_tieu_chi']).strip()] = row['id']

        tieu_chi_cols = df.columns[1:]
        for tc_name in tieu_chi_cols:
            tc_clean = str(tc_name).strip()
            if tc_clean not in tc_map:
                cursor.execute("INSERT INTO dm_tieu_chi_phu_cap (ten_tieu_chi) VALUES (%s)", (tc_clean,))
                tc_map[tc_clean] = cursor.lastrowid

        # 3. XỬ LÝ MA TRẬN & UPSERT DỮ LIỆU
        so_luong_update = 0
        for _, row in df.iterrows():
            tt_name = row[tt_col]
            if pd.isna(tt_name):
                continue
            tt_clean = str(tt_name).strip()
            tt_id = tt_map.get(tt_clean)
            if not tt_id:
                continue

            for tc_name in tieu_chi_cols:
                tc_clean = str(tc_name).strip()
                tc_id = tc_map.get(tc_clean)

                val = row[tc_name]
                so_tien = 0.0
                if pd.notna(val) and str(val).strip() != "":
                    try:
                        so_tien = float(str(val).replace(",", "").replace(" ", ""))
                    except Exception:
                        pass

                cursor.execute(
                    "SELECT so_tien FROM ma_tran_phu_cap WHERE tai_trong_id=%s AND tieu_chi_id=%s",
                    (tt_id, tc_id)
                )
                if cursor.fetchone():
                    cursor.execute(
                        "UPDATE ma_tran_phu_cap SET so_tien=%s WHERE tai_trong_id=%s AND tieu_chi_id=%s",
                        (so_tien, tt_id, tc_id)
                    )
                else:
                    cursor.execute(
                        "INSERT INTO ma_tran_phu_cap (tai_trong_id, tieu_chi_id, so_tien) VALUES (%s, %s, %s)",
                        (tt_id, tc_id, so_tien)
                    )
                so_luong_update += 1

        # 4. GHI AUDIT LOG
        chi_tiet = json.dumps({"so_o_cap_nhat": so_luong_update, "nguon": "Import_Excel_2"}, ensure_ascii=False)
        cursor.execute("""
            INSERT INTO audit_logs (phan_he, nguoi_thuc_hien, hanh_dong, chi_tiet)
            VALUES (%s, %s, %s, %s)
        """, ('QUAN_LY_PHU_CAP', current_user, 'IMPORT_EXCEL_MA_TRAN', chi_tiet))

        conn.commit()
        return True, f"✅ Đã Import thành công toàn bộ {so_luong_update} ô dữ liệu vào Ma trận Phụ cấp!"
    except Exception as e:
        if conn:
            conn.rollback()
        return False, str(e)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()