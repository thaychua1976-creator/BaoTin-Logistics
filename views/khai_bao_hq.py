import streamlit as st
import pandas as pd
import datetime, time
import pypdf
import json,re
import uuid
import traceback
from utils_core import parse_money_input, tao_tieu_de_kem_nut_refresh
from declare_hq_manager import save_to_khai_transaction, delete_to_khai_transaction, get_don_gia_hq_tu_dong, get_phu_phi_theo_khach_hang
from audit_logger import ghi_log_he_thong

db = st.session_state.get('db')

current_user = st.session_state.get('username') or st.session_state.get('user') or st.session_state.get('logged_in_user', 'Admin')

if not db:
    st.error("⚠️ Lỗi kết nối Cơ sở dữ liệu.")
    st.stop()

# --- HỆ THỐNG CACHE BỘ NHỚ ĐỆM ---
@st.cache_data(ttl=1800, show_spinner=False)
def get_cached_master_data(query, params=None):
    return db.execute_query(query, params)

def clear_master_cache():
    get_cached_master_data.clear()
# ---------------------------------

def get_idx(lst, val, default=0):
    try: return lst.index(val)
    except: return default

st.markdown("<h3 style='text-align: center; color: #0b5394;'>🏢 PHÂN HỆ QUẢN LÝ TỜ KHAI HẢI QUAN & CONTAINER</h3>", unsafe_allow_html=True)
st.divider()

tab_khai_hq, tab_danh_sach, tab_container = st.tabs([
    "📋 KHAI BÁO TỜ KHAI MỚI", 
    "🔍 DANH SÁCH & QUẢN LÝ TỜ KHAI", 
    "📦 QUẢN LÝ CONTAINER & PHÍ (DVHQ, NÂNG/HẠ)"
])

# ==========================================
# HÀM TRANSACTION BATCH CHO CONTAINER (Giữ nguyên)
# ==========================================
def save_containers_batch_transaction(db_pool, link_col, parent_id, container_list_input, user=current_user):
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False 
        cursor = conn.cursor()

        sql_get_current = f"SELECT id, so_cont FROM container_quan_ly WHERE {link_col} = %s"
        cursor.execute(sql_get_current, (parent_id,))
        current_rows = cursor.fetchall() 
        current_db_map = {row[1]: row[0] for row in current_rows} 
        input_cont_set = set()

        for item in container_list_input:
            so_cont = str(item.get('so_cont') or '').strip().upper()
            if not so_cont: continue
            input_cont_set.add(so_cont)
            cd_id = item.get('chuyen_di_id')
            tk_id = item.get('to_khai_id')
            
            loai_cont = item.get('loai_cont', '40HC').strip()
            phi_dv_hq = parse_money_input(item.get('phi_to_khai', 0))
            phi_on = parse_money_input(item.get('phi_nang_ha_on', 0))
            inv_on = str(item.get('so_hoa_don_lift_on') or '').strip()
            phi_off = parse_money_input(item.get('phi_nang_ha_off', 0))
            inv_off = str(item.get('so_hoa_don_lift_off') or '').strip()
            phi_bot = parse_money_input(item.get('phi_bot', 0))
            phi_lay_mau = parse_money_input(item.get('phi_lay_mau', 0))
            phi_kiem_dich = parse_money_input(item.get('phi_kiem_dich', 0))
            hd_kiem_dich = str(item.get('so_hoa_don_kiem_dich') or '').strip()
            phi_luu_bai = parse_money_input(item.get('phi_luu_bai', 0))
            hd_luu_bai = str(item.get('so_hoa_don_luu_bai') or '').strip()
            phi_do = parse_money_input(item.get('phi_do', 0))
            hd_do = str(item.get('so_hoa_don_do') or '').strip()
            phi_handling = parse_money_input(item.get('phi_handling', 0))
            hd_handling = str(item.get('so_hoa_don_handling') or '').strip()
            phi_khu_trung = parse_money_input(item.get('phi_khu_trung', 0))
            hd_khu_trung = str(item.get('so_hoa_don_khu_trung') or '').strip()
            phi_van_chuyen = parse_money_input(item.get('phi_van_chuyen',0))
            phi_thong_quan = parse_money_input(item.get('phi_thong_quan',0))
            ghi_chu = str(item.get('ghi_chu') or '').strip()
            
            if so_cont in current_db_map:
                cont_id = current_db_map[so_cont]
                sql_update = """
                    UPDATE container_quan_ly 
                    SET loai_cont = %s, chuyen_di_id = %s, to_khai_id = %s,
                        phi_nang_ha_on = %s, so_hoa_don_lift_on = %s, phi_nang_ha_off = %s, so_hoa_don_lift_off = %s,
                        phi_to_khai = %s, phi_bot = %s, phi_lay_mau = %s, phi_kiem_dich = %s, so_hoa_don_kiem_dich = %s,
                        phi_luu_bai = %s, so_hoa_don_luu_bai = %s, phi_do = %s, so_hoa_don_do = %s,
                        phi_handling = %s, so_hoa_don_handling = %s, phi_khu_trung = %s, so_hoa_don_khu_trung = %s,
                        phi_van_chuyen = %s,phi_thong_quan = %s, ghi_chu = %s
                    WHERE id = %s
                """
                cursor.execute(sql_update, (loai_cont, phi_on, inv_on, phi_off, inv_off, phi_dv_hq, phi_bot, phi_lay_mau, phi_kiem_dich, hd_kiem_dich, phi_luu_bai, hd_luu_bai, phi_do, hd_do, phi_handling, hd_handling, phi_khu_trung, hd_khu_trung, phi_van_chuyen,phi_thong_quan, ghi_chu, cont_id))
            else:
                sql_insert = """
                    INSERT INTO container_quan_ly 
                    (so_cont, loai_cont, chuyen_di_id, to_khai_id, phi_nang_ha_on, so_hoa_don_lift_on, phi_nang_ha_off, so_hoa_don_lift_off, phi_to_khai, phi_bot, phi_lay_mau, phi_kiem_dich, so_hoa_don_kiem_dich, phi_luu_bai, so_hoa_don_luu_bai, phi_do, so_hoa_don_do, phi_handling, so_hoa_don_handling, phi_khu_trung, so_hoa_don_khu_trung, phi_van_chuyen,phi_thong_quan, ghi_chu) 
                    VALUES (%s,%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql_insert, (so_cont, loai_cont, cd_id, tk_id, phi_on, inv_on, phi_off, inv_off, phi_dv_hq, phi_bot, phi_lay_mau, phi_kiem_dich, hd_kiem_dich, phi_luu_bai, hd_luu_bai, phi_do, hd_do, phi_handling, hd_handling, phi_khu_trung, hd_khu_trung, phi_van_chuyen,phi_thong_quan, ghi_chu))
                
        log_detail = {link_col: parent_id, "danh_sach_cap_nhat": container_list_input, "tong_so_luong": len(container_list_input)}
        ghi_log_he_thong(cursor=cursor, phan_he="QUAN_LY_CONTAINER", record_id=parent_id, nguoi_thuc_hien=user, hanh_dong="DONG_BO_DANH_SACH_CONTAINER", chi_tiet=json.dumps(log_detail, ensure_ascii=False))

        conn.commit()
        return True, f"Đồng bộ thành công {len(container_list_input)} container!"
    except Exception as e:
        if conn: conn.rollback() 
        traceback.print_exc()
        return False, str(e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
######################################################

def delete_container_transaction(db_pool, cont_id, user=current_user):
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False
        cursor = conn.cursor()
        cursor.execute("SELECT so_cont FROM container_quan_ly WHERE id=%s", (cont_id,))
        row = cursor.fetchone()
        if not row: return False, "Không tìm thấy container trong hệ thống."
        cursor.execute("DELETE FROM container_quan_ly WHERE id=%s", (cont_id,))
        if cursor.rowcount == 0:
            conn.rollback()
            return False, "Xóa thất bại. Container không tồn tại."
        ghi_log_he_thong(cursor, "QUAN_LY_CONTAINER", cont_id, user, "XOA", json.dumps({"so_cont_bi_xoa": row[0]}, ensure_ascii=False))
        conn.commit()
        return True, "Xóa thành công!"
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ==========================================
# TAB 1: KHAI BÁO TỜ KHAI MỚI
# ==========================================
with tab_khai_hq:
    @st.fragment
    def vung_thao_tac_khai_hq():
        st.markdown("#### 📥 Nhập Liệu Tờ Khai Mới")
        st.info("💡 Hệ thống tự động đọc file Excel (.xls, .xlsx) hoặc PDF để trích xuất: Đơn vị XNK (Tự động điền vào Khách hàng & Tên đối tác), Số lượng hàng, Luồng, Hóa đơn TM.")
        
        if "hq_auto_data" not in st.session_state: 
            st.session_state["hq_auto_data"] = {
                "so_to_khai": "", "so_van_don": "", "extracted_ten_khach_hang": "", "ma_so_thue": "",
                "tong_trong_luong_hang": 0.0, "so_kien": "", "ngay_khai": datetime.date.today(),
                "loai_to_khai": "Xuat_Khau", "so_hoa_don_tm": "", "kho_cang_lay_hang": "",
                "ten_doi_tac": "", "ma_loai_hinh": "", "phan_luong": ""
            }

        try:
            uploaded_file = st.file_uploader("📂 Chọn file Excel / PDF tờ khai hải quan", type=["pdf", "txt", "xls", "xlsx"], key="upload_file_to_khai_hq")
            if uploaded_file is not None:
                file_sig = f"{uploaded_file.name}_{uploaded_file.size}"
                if st.session_state.get("last_uploaded_sig") != file_sig:
                    auto_data = st.session_state["hq_auto_data"]
                    
                    # --- XỬ LÝ FILE EXCEL (.xls, .xlsx) ---
                    if uploaded_file.name.lower().endswith(('.xls', '.xlsx')):
                        df = pd.read_excel(uploaded_file, sheet_name=0)
                        current_section = ""
                        for i, r in df.iterrows():
                            vals = [str(v).strip() for v in r.values if pd.notnull(v) and str(v).strip()]
                            if not vals: continue
                            text_line = " | ".join(vals)
                            
                            if "xuất khẩu" in text_line.lower():
                                auto_data["loai_to_khai"] = "Xuat_Khau"
                            elif "nhập khẩu" in text_line.lower() and "tờ khai" in text_line.lower():
                                auto_data["loai_to_khai"] = "Nhap_Khau"
                                
                            if "Người xuất khẩu" in text_line:
                                current_section = "Nguoi_Xuat_Khau"
                            elif "Người nhập khẩu" in text_line:
                                current_section = "Nguoi_Nhap_Khau"
                                
                            for idx, val in enumerate(vals):
                                if val == "Số tờ khai" and idx + 1 < len(vals):
                                    auto_data["so_to_khai"] = vals[idx+1]
                                elif val == "Số vận đơn" and idx + 1 < len(vals):
                                    auto_data["so_van_don"] = vals[idx+1]
                                elif val == "Mã loại hình" and idx + 1 < len(vals):
                                    auto_data["ma_loai_hinh"] = vals[idx+1].split()[0]
                                elif val == "Ngày đăng ký" and idx + 1 < len(vals):
                                    try:
                                        date_str = vals[idx+1].split()[0]
                                        auto_data['ngay_khai'] = datetime.datetime.strptime(date_str, '%d/%m/%Y').date()
                                    except ValueError: pass
                                elif val == "Mã phân loại kiểm tra" and idx + 1 < len(vals):
                                    pl = vals[idx+1]
                                    if pl == "1": auto_data["phan_luong"] = "Xanh"
                                    elif pl == "2": auto_data["phan_luong"] = "Vang"
                                    elif pl == "3": auto_data["phan_luong"] = "Do"
                                elif val == "Tổng trọng lượng hàng (Gross)" and idx + 1 < len(vals):
                                    try:
                                        auto_data["tong_trong_luong_hang"] = float(vals[idx+1].replace(",", "."))
                                    except: pass
                                elif val == "Số lượng" and i < 50 and idx + 1 < len(vals):
                                    so_kien_val = vals[idx+1]
                                    if idx + 2 < len(vals): so_kien_val += " " + vals[idx+2]
                                    auto_data["so_kien"] = so_kien_val
                                elif val == "Số hóa đơn" and idx + 1 < len(vals):
                                    filtered_invoice = [v for v in vals[idx+1:] if v != '-' and v != 'A' and v != 'B' and len(v) > 2]
                                    if filtered_invoice:
                                        auto_data["so_hoa_don_tm"] = filtered_invoice[-1]
                                
                                if val == "Mã" and idx + 1 < len(vals) and i < 40:
                                    if (auto_data.get("loai_to_khai") == "Xuat_Khau" and current_section == "Nguoi_Xuat_Khau") or \
                                       (auto_data.get("loai_to_khai") == "Nhap_Khau" and current_section == "Nguoi_Nhap_Khau"):
                                        auto_data["ma_so_thue"] = vals[idx+1]
                                if val == "Tên" and idx + 1 < len(vals) and i < 40:
                                    if (auto_data.get("loai_to_khai") == "Xuat_Khau" and current_section == "Nguoi_Xuat_Khau") or \
                                       (auto_data.get("loai_to_khai") == "Nhap_Khau" and current_section == "Nguoi_Nhap_Khau"):
                                        auto_data["extracted_ten_khach_hang"] = vals[idx+1]
                                        # Tự động gán tên khách hàng vào textbox Tên Đối Tác
                                        auto_data["ten_doi_tac"] = vals[idx+1]
                                        
                        st.success(f"✅ Đã trích xuất dữ liệu Excel. Đơn vị XNK: **{auto_data.get('extracted_ten_khach_hang')}**")
                        
                    # --- XỬ LÝ FILE PDF (.pdf) ---
                    else:
                        reader = pypdf.PdfReader(uploaded_file)
                        text = ""
                        for page in reader.pages:
                            text += page.extract_text() + "\n"
                        
                        m_stk = re.search(r'Số tờ khai[:\s]*(\d+)', text, re.IGNORECASE)
                        if m_stk: auto_data['so_to_khai'] = m_stk.group(1).strip()
                            
                        m_sql = re.search(r'Số quản lý hàng hóa[:\s]*(\d+)', text, re.IGNORECASE)
                        if m_sql: auto_data['so_van_don'] = m_sql.group(1).strip()
                            
                        m_ten_xnk = re.search(r'Đơn vị XNK[:\s]*([^\n\r]+)', text, re.IGNORECASE)
                        if m_ten_xnk:
                            auto_data['extracted_ten_khach_hang'] = m_ten_xnk.group(1).strip()
                            # Tự động gán tên khách hàng vào textbox Tên Đối Tác
                            auto_data['ten_doi_tac'] = auto_data['extracted_ten_khach_hang']
                            st.success(f"✅ Đã trích xuất Đơn vị XNK: **{auto_data['extracted_ten_khach_hang']}**")
                                
                        m_kien = re.search(r'1\s*\|\s*([\d\.,]+\s*[A-Za-z]+)', text) 
                        if not m_kien:
                            m_kien = re.search(r'(\d+\s*(?:CARTON|KIỆN|PALLET|PCS|BAO|THÙNG|CUỘN|CHIẾC|SET))', text, re.IGNORECASE)
                        if m_kien: auto_data['so_kien'] = m_kien.group(1).strip()
                        
                        m_wt = re.search(r'TỔNG TRỌNG\s*LƯỢNG HÀNG\s*[-–—]*\s*([\d\.]+)\s*Kilogam', text, re.IGNORECASE)
                        if not m_wt: m_wt = re.search(r'([\d\.]+)\s*Kilogam', text, re.IGNORECASE)
                        if m_wt: auto_data['tong_trong_luong_hang'] = float(m_wt.group(1))
                            
                        m_date = re.search(r'Ngày tờ khai[:\s]*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
                        if m_date:
                            try: auto_data['ngay_khai'] = datetime.datetime.strptime(m_date.group(1), '%d/%m/%Y').date()
                            except ValueError: pass
                                
                        if "xuất khẩu" in text.lower(): auto_data['loai_to_khai'] = "Xuat_Khau"
                        elif "nhập khẩu" in text.lower(): auto_data['loai_to_khai'] = "Nhap_Khau"

                        m_luong = re.search(r'Luồng[:\s]*([^\n\r]+)', text, re.IGNORECASE)
                        if m_luong:
                            luong_text = m_luong.group(1).strip().lower()
                            if 'xanh' in luong_text: auto_data['phan_luong'] = "Xanh"
                            elif 'vàng' in luong_text or 'vang' in luong_text: auto_data['phan_luong'] = "Vang"
                            elif 'đỏ' in luong_text or 'do' in luong_text: auto_data['phan_luong'] = "Do"
                            
                    st.session_state["last_uploaded_sig"] = file_sig
        except Exception as e:
            st.error(f"❌ Có lỗi xảy ra khi đọc file: {str(e)}")

        auto_data = st.session_state.get("hq_auto_data", {})

        c_out1, c_out2 = st.columns(2)
        loai_options = {"Nhap_Khau": "Hàng Nhập Khẩu", "Xuat_Khau": "Hàng Xuất Khẩu", "Noi_Dia": "Nhập Nội Địa", "DHL": "Hàng DHL", "Lẻ": "Hàng_Lẻ"}
        loai_keys = list(loai_options.keys())
        default_loai_idx = get_idx(loai_keys, auto_data.get('loai_to_khai')) if auto_data.get('loai_to_khai') in loai_keys else 0
        
        loai_tk = c_out1.selectbox("Loại Tờ Khai*", options=loai_keys, format_func=lambda x: loai_options[x], index=default_loai_idx)
        
        df_kh = get_cached_master_data("SELECT id, ten_khach_hang, ma_so_thue, ma_khach_hang FROM khach_hang")
        dict_kh = {None: "-- Vui lòng chọn khách hàng --"}
        kh_keys_list = [None]
        
        extracted_name = str(auto_data.get('extracted_ten_khach_hang', '')).strip().lower()
        extracted_mst = str(auto_data.get('ma_so_thue', '')).replace(" ", "").replace("-", "")
        default_kh_idx = 0
        
        if isinstance(df_kh, pd.DataFrame) and not df_kh.empty:
            for idx, r in df_kh.iterrows():
                kid = int(r['id'])
                ten_kh_db = str(r['ten_khach_hang'])
                mst = r['ma_so_thue'] if pd.notna(r['ma_so_thue']) and r['ma_so_thue'] != "" else (r['ma_khach_hang'] if pd.notna(r['ma_khach_hang']) else "KHÔNG CÓ MST")
                
                dict_kh[kid] = f"MST: {mst} — {ten_kh_db}"
                kh_keys_list.append(kid)
                
                db_mst_clean = mst.replace(" ", "").replace("-", "")
                if extracted_mst and extracted_mst != "" and extracted_mst in db_mst_clean:
                    default_kh_idx = len(kh_keys_list) - 1
                elif extracted_name and (extracted_name in ten_kh_db.lower() or ten_kh_db.lower() in extracted_name):
                    default_kh_idx = len(kh_keys_list) - 1

        kh_id = c_out2.selectbox("Khách Hàng*", options=kh_keys_list, index=default_kh_idx, format_func=lambda x: dict_kh[x])

        if auto_data.get('extracted_ten_khach_hang'):
            st.caption(f"📄 Khách hàng đề xuất từ file: **{auto_data.get('extracted_ten_khach_hang')}**")

        gia_hq_tu_dong = 0.0
        ds_phu_phi_tong_hop = []
        
        if kh_id:
            gia_hq_tu_dong = get_don_gia_hq_tu_dong(db.pool, kh_id, loai_options[loai_tk] if loai_tk else "")
                
            sql_bg = "SELECT id, nhom_dich_vu, phan_loai_chi_tiet, don_gia_hq FROM bang_gia_hai_quan WHERE khach_hang_id = %s AND nhom_dich_vu != 'Phí tờ khai'"
            df_bg = get_cached_master_data(sql_bg, (kh_id,))
            if isinstance(df_bg, pd.DataFrame) and not df_bg.empty:
                for _, r in df_bg.iterrows():
                    ten = r['nhom_dich_vu']
                    if r['phan_loai_chi_tiet']: ten += f" ({r['phan_loai_chi_tiet']})"
                    ds_phu_phi_tong_hop.append({'id': f"BG_{r['id']}", 'ten_phu_phi': ten, 'don_gia_phu_phi': float(r['don_gia_hq'])})
                
        dict_phu_phi = {p['id']: f"{p['ten_phu_phi']} (+{int(p['don_gia_phu_phi']):,} VNĐ)" for p in ds_phu_phi_tong_hop}

        if "form_tao_tokhai_key" not in st.session_state:
            st.session_state["form_tao_tokhai_key"] = "form_tao_moi_tokhai_batch_1"

        with st.form(key=st.session_state["form_tao_tokhai_key"], clear_on_submit=False):
            c1, c2 = st.columns(2)    
            so_to_khai = c1.text_input("Số Tờ Khai HQ*", value=auto_data.get('so_to_khai', ''))
            so_van_don = c2.text_input("Số Vận Đơn (B/L / AWB)", value=auto_data.get('so_van_don', '')) 

            c3, c4 = st.columns(2)
            ngay_khai = c3.date_input("Ngày Khai", value=auto_data.get('ngay_khai', datetime.date.today()), format="DD/MM/YYYY")
            
            luong_list = ["", "Xanh", "Vang", "Do"]
            default_luong_idx = get_idx(luong_list, auto_data.get('phan_luong')) if auto_data.get('phan_luong') else 0
            phan_luong = c4.selectbox("Phân Luồng", luong_list, index=default_luong_idx)
            
            c5, c6, c7, c8 = st.columns(4)
            so_hoa_don_tm = c5.text_input("Số Hóa Đơn TM", value=auto_data.get('so_hoa_don_tm', ''))
            kho_cang_lay_hang = c6.text_input("Kho cảng lấy hàng", value=auto_data.get('kho_cang_lay_hang', ''))
            
            # Tên đối tác sẽ tự nhận giá trị khách hàng vừa trích xuất được
            ten_doi_tac = c7.text_input("Tên Đối Tác", value=auto_data.get('ten_doi_tac', ''))
            ma_loai_hinh = c8.text_input("Mã Loại Hình (VD: E11, E42)", value=auto_data.get('ma_loai_hinh', ''))
            
            c9, c10 = st.columns(2)
            so_kien = c9.text_input("Số Kiện", value=auto_data.get('so_kien', ''))
            tong_trong_luong_hang = c10.number_input("Tổng trọng lượng (KG)", min_value=0.0, value=float(auto_data.get('tong_trong_luong_hang') or 0.0), step=0.1)
            
            st.markdown("**💰 Khai Báo Chi Phí Chung (VNĐ)**")
            phi_dvhq_input = st.text_input("Phí Dịch Vụ Hải Quan (VNĐ)*", value=f"{gia_hq_tu_dong:,.0f}")
            
            selected_phu_phi = st.multiselect("🏷️ Chọn Phụ Phí Đã Cấu Hình Cho Khách Này", options=list(dict_phu_phi.keys()), format_func=lambda x: dict_phu_phi[x])

            cp1, cp2 = st.columns(2)
            phi_van_chuyen_lien_ket = cp1.text_input("Phí Vận Chuyển (Lấy từ Chuyến)", value="0", disabled=(loai_tk in ["Noi_Dia", "DHL"]))
            phi_khac_nhap_tay = cp2.text_input("Phí Phát Sinh Khác (Gõ tay thêm nếu có)", value="0")
            ghi_chu = st.text_input("Ghi chú bổ sung")
            
            if st.form_submit_button("💾 LƯU TỜ KHAI HẢI QUAN", type="primary"):
                try:
                    if not kh_id:
                        st.error("❌ Vui lòng chọn khách hàng hợp lệ từ danh sách!")
                        st.stop()
                    if not so_van_don.strip() or not so_to_khai.strip():
                        st.error("❌ Số Tờ khai và Vận đơn không được để trống!")
                        st.stop()      
                    
                    tong_tien_phu_phi = sum([float(p['don_gia_phu_phi']) for p in ds_phu_phi_tong_hop if p['id'] in selected_phu_phi])
                    ten_cac_phu_phi = [p['ten_phu_phi'] for p in ds_phu_phi_tong_hop if p['id'] in selected_phu_phi]
                    
                    ghi_chu_final = ghi_chu.strip()
                    if ten_cac_phu_phi: ghi_chu_final += f" | Phụ phí: {', '.join(ten_cac_phu_phi)}"
                    
                    tk_data = {
                        'so_to_khai': so_to_khai, 'loai_to_khai': loai_tk, 'so_van_don': so_van_don, 
                        'ngay_khai': ngay_khai.strftime('%Y-%m-%d'), 'khach_hang_id': kh_id, 
                        'so_hoa_don_tm': so_hoa_don_tm, 'kho_cang_lay_hang': kho_cang_lay_hang,
                        'ten_doi_tac': ten_doi_tac, 'ma_loai_hinh': ma_loai_hinh, 
                        'so_kien': so_kien, 'tong_trong_luong_hang': tong_trong_luong_hang, 
                        'phan_luong': phan_luong, 'phi_khac': parse_money_input(phi_khac_nhap_tay) + tong_tien_phu_phi,       
                        'phi_dich_vu_hq': parse_money_input(phi_dvhq_input), 'ghi_chu': ghi_chu_final               
                    }
                    
                    # Khi tạo mới tờ khai, nếu không có danh sách chi tiết phí động riêng, ta truyền list rỗng [] hoặc gom nhóm từ multiselect phụ phí
                    chi_tiet_phi_list_moi = []
                    for p_id in selected_phu_phi:
                        # Lấy thông tin phụ phí từ dict_phu_phi tương ứng
                        p_item = next((p for p in ds_phu_phi_tong_hop if p['id'] == p_id), None)
                        if p_item:
                            chi_tiet_phi_list_moi.append({
                                'ten_loai_phi': p_item['ten_phu_phi'],
                                'so_tien': p_item['don_gia_phu_phi'],
                                'ghi_chu': 'Phụ phí tự động từ cấu hình giá'
                            })

                    ok, msg = save_to_khai_transaction(
                        db_pool=db.pool, 
                        tk_data=tk_data, 
                        chi_tiet_phi_list=chi_tiet_phi_list_moi, 
                        tk_id=None, 
                        current_user=current_user
                    )
                    # Yêu cầu gọi qua hàm parse_money_input và lưu audit transaction[cite: 5]
                    #ok, msg = save_to_khai_transaction(db.pool, tk_data, None,None, current_user)
                    if ok: 
                                # Lưu thông báo thành công vào session để giữ lại khi làm mới hoặc hiển thị trực tiếp
                                st.success("✅ Đã tạo tờ khai mới thành công!")
                                
                                # Reset toàn bộ session state liên quan đến form và file upload
                                st.session_state["form_tao_tokhai_key"] = f"form_tao_moi_tokhai_batch_{uuid.uuid4()}"
                                st.session_state["file_uploader_hq_key"] = f"upload_file_to_khai_hq_{uuid.uuid4()}"
                                st.session_state["hq_auto_data"] = {}
                                if "last_uploaded_sig" in st.session_state: 
                                    del st.session_state["last_uploaded_sig"]
                                    
                                time.sleep(1.2)
                                st.rerun()
                    else: 
                                st.error(f"Lỗi: {msg}")
                except Exception as ex:
                    st.error(f"❌ Có lỗi xảy ra trong quá trình lưu dữ liệu: {str(ex)}")
    vung_thao_tac_khai_hq()
# ==========================================
# TAB 2: DANH SÁCH & QUẢN LÝ TỜ KHAI
# ==========================================
with tab_danh_sach:
    tao_tieu_de_kem_nut_refresh("🔍 Danh sách Tờ Khai Hải Quan", "ref_tab_ds_hq")
    @st.fragment
    def vung_thao_tac_quan_ly_to_khai():
        col_f1, col_f2 = st.columns(2)
        today = datetime.date.today()
        ds_tu_ngay = col_f1.date_input("Từ ngày", value=today.replace(day=1), key="ds_tu_ngay")
        ds_den_ngay = col_f2.date_input("Đến ngày", value=today, key="ds_den_ngay")
        
        sql_ds = """
            SELECT tk.id, tk.so_to_khai, tk.so_van_don, tk.loai_to_khai, tk.ngay_khai, kh.ten_khach_hang, 
                tk.ten_doi_tac, tk.tong_trong_luong_hang, tk.so_hoa_don_tm, tk.kho_cang_lay_hang, tk.ma_loai_hinh, 
                tk.so_kien, tk.phan_luong, tk.phi_khac, tk.phi_dich_vu_hq,
                tk.ghi_chu, tk.khach_hang_id, tk.chuyen_di_id, cd.loai_hinh_xe
            FROM to_khai_hai_quan tk
            LEFT JOIN khach_hang kh ON tk.khach_hang_id = kh.id
            LEFT JOIN chuyen_di cd ON tk.chuyen_di_id = cd.id
            WHERE tk.ngay_khai BETWEEN %s AND %s
            ORDER BY tk.ngay_khai DESC, tk.id DESC
        """
        # Không dùng cache cho dữ liệu giao dịch động
        df_tk = db.execute_query(sql_ds, (ds_tu_ngay.strftime('%Y-%m-%d'), ds_den_ngay.strftime('%Y-%m-%d')))
        
        if isinstance(df_tk, pd.DataFrame) and not df_tk.empty:
            df_view = df_tk[['id', 'so_to_khai', 'so_van_don','loai_to_khai', 'ngay_khai', 'ten_khach_hang', 'ten_doi_tac', 'tong_trong_luong_hang', 'phi_khac', 'phan_luong', 'ghi_chu']]
            st.dataframe(df_view, use_container_width=True, hide_index=True)
            
            st.divider()
            st.markdown("#### 🛠️ Thao Tác Quản Lý (Sửa / Xóa Tờ Khai)")
            
            dict_tk_edit = {row['id']: f"[{row['loai_to_khai']}] Số TK: {row['so_to_khai']} - Khách: {row['ten_khach_hang']}" for _, row in df_tk.iterrows()}
            
            selected_tk_id = st.selectbox("📌 Chọn tờ khai để tiến hành sửa hoặc xóa:", options=list(dict_tk_edit.keys()), format_func=lambda x: dict_tk_edit[x], index=None, placeholder="-- Vui lòng click chọn 1 tờ khai --", key="select_to_khai_action")
            
            if selected_tk_id is not None:
                tk_info = df_tk[df_tk['id'] == selected_tk_id].iloc[0]
                
                st.markdown(f"Đang thao tác với Tờ khai: **{tk_info['so_to_khai']}**")
                action_mode = st.radio("Chọn hành động:", ["✏️ Sửa Tờ Khai", "🗑️ Xóa Tờ Khai"], horizontal=True, key="radio_action_mode")
                
                if action_mode == "🗑️ Xóa Tờ Khai":
                    st.warning(f"⚠️ Bạn có chắc chắn muốn xóa vĩnh viễn tờ khai **{tk_info['so_to_khai']}**?")
                    if st.button("Xác Nhận Xóa Tờ Khai", type="primary"):
                        ok, msg = delete_to_khai_transaction(db.pool, selected_tk_id, current_user)
                        if ok:
                            st.success("✅ Đã xóa tờ khai thành công!")
                            if "select_to_khai_action" in st.session_state: del st.session_state["select_to_khai_action"]
                            st.rerun()
                        else: st.error(f"Lỗi: {msg}")
                else:
                    loai_options = {"Nhap_Khau": "Hàng Nhập Khẩu", "Xuat_Khau": "Hàng Xuất Khẩu", "Noi_Dia": "Nhập Nội Địa", "DHL": "Hàng DHL","Lẻ": "Hàng_Lẻ"}
                    e_loai_tk = st.selectbox("Loại Tờ Khai*", options=list(loai_options.keys()), index=get_idx(list(loai_options.keys()), tk_info['loai_to_khai']), format_func=lambda x: loai_options[x], key=f"edit_loai_tk_{selected_tk_id}")

                    # --- LẤY DANH SÁCH PHỤ PHÍ CHO TAB SỬA (KẾT HỢP TỪ 2 BẢNG) ---
                    kh_id_edit = tk_info['khach_hang_id']
                    ds_phu_phi_edit_tong_hop = []
                    
                    if kh_id_edit:
                        ds_pp_goc_edit = get_phu_phi_theo_khach_hang(db.pool, kh_id_edit)
                        for p in ds_pp_goc_edit:
                            ds_phu_phi_edit_tong_hop.append({
                                'id': f"PP_{p['id']}", 
                                'ten_phu_phi': p['ten_phu_phi'], 
                                'don_gia_phu_phi': float(p['don_gia_phu_phi'])
                            })
                            
                        # Lấy phụ phí từ bảng giá hải quan qua Cache
                        sql_bge = "SELECT id, nhom_dich_vu, phan_loai_chi_tiet, don_gia_hq FROM bang_gia_hai_quan WHERE khach_hang_id = %s AND nhom_dich_vu != 'Phí tờ khai'"
                        df_bge = get_cached_master_data(sql_bge, (kh_id_edit,))
                        if isinstance(df_bge, pd.DataFrame) and not df_bge.empty:
                            for _, r in df_bge.iterrows():
                                ten = r['nhom_dich_vu']
                                if r['phan_loai_chi_tiet']:
                                    ten += f" ({r['phan_loai_chi_tiet']})"
                                ds_phu_phi_edit_tong_hop.append({
                                    'id': f"BG_{r['id']}", 
                                    'ten_phu_phi': ten, 
                                    'don_gia_phu_phi': float(r['don_gia_hq'])
                                })
                            
                    dict_phu_phi_edit = {p['id']: f"{p['ten_phu_phi']} (+{int(p['don_gia_phu_phi']):,} VNĐ)" for p in ds_phu_phi_edit_tong_hop}
                    # ----------------------------------------

                    with st.form(f"form_edit_hai_quan_{selected_tk_id}", clear_on_submit=False):
                        ec_tk1, ec_tk2 = st.columns(2)
                        e_so_to_khai = ec_tk1.text_input("Số Tờ Khai HQ*", value=tk_info['so_to_khai'])
                        e_so_van_don = ec_tk2.text_input("Số Vận Đơn (B/L / AWB)", value=tk_info.get('so_van_don', '') or "")

                        ec1, ec2 = st.columns(2)
                        e_ngay_khai = ec1.date_input("Ngày Khai", value=pd.to_datetime(tk_info['ngay_khai']).date())
                        e_phan_luong = ec2.selectbox("Phân Luồng", ["Xanh", "Vang", "Do"], index=get_idx(["Xanh", "Vang", "Do"], tk_info['phan_luong']))
                        
                        df_kh = get_cached_master_data("SELECT id, ten_khach_hang, ma_so_thue, ma_khach_hang FROM khach_hang")
                        dict_kh = {None: "-- Vui lòng chọn khách hàng --"}
                        if isinstance(df_kh, pd.DataFrame) and not df_kh.empty:
                            for _, r in df_kh.iterrows():
                                mst = r['ma_so_thue'] if pd.notna(r['ma_so_thue']) and r['ma_so_thue'] != "" else (r['ma_khach_hang'] if pd.notna(r['ma_khach_hang']) else "KHÔNG CÓ MST")
                                dict_kh[int(r['id'])] = f"MST: {mst} — {r['ten_khach_hang']}"
                        
                        e_kh_id = st.selectbox("Khách Hàng*", options=list(dict_kh.keys()), index=get_idx(list(dict_kh.keys()), tk_info['khach_hang_id']), format_func=lambda x: dict_kh[x])
                        
                        #df_cd = db.execute_query("SELECT id, ngay_chuyen_di, dia_diem_giao_nhan FROM chuyen_di ORDER BY id DESC LIMIT 50")
                        #dict_cd = {0: "Không liên kết"}
                        #if isinstance(df_cd, pd.DataFrame) and not df_cd.empty:
                        #    dict_cd.update({r['id']: f"Mã {r['id']} - {r['dia_diem_giao_nhan']} ({r['ngay_chuyen_di']})" for _, r in df_cd.iterrows()})
                        
                        #e_chuyen_di_id = st.selectbox("Chuyến Xe Liên Kết", options=list(dict_cd.keys()), index=get_idx(list(dict_cd.keys()), tk_info['chuyen_di_id'] or 0), format_func=lambda x: dict_cd[x])
                        #e_chuyen_di_id = None if e_chuyen_di_id == 0 else e_chuyen_di_id

                        ec3, ec4, ec5 = st.columns(3)
                        e_so_hoa_don = ec3.text_input("Số Hóa Đơn TM", value=tk_info['so_hoa_don_tm'] or "")
                        e_kho_cang_lay_hang = ec4.text_input("Kho cảng lấy hàng", value=tk_info['kho_cang_lay_hang'] or "")
                        e_ten_doi_tac = ec5.text_input("Tên Đối Tác", value=tk_info['ten_doi_tac'] or "")
                        e_ma_loai_hinh = st.text_input("Mã Loại Hình", value=tk_info['ma_loai_hinh'] or "")
                        
                        e_so_kien = st.text_input("Số Kiện", value=tk_info['so_kien'] or "")
                        e_trong_luong = st.number_input("Tổng trọng lượng (KG)", value=float(tk_info['tong_trong_luong_hang'] or 0.0), step=0.1)
                        
                        st.markdown("**💰 Khai Báo Chi Phí (VNĐ)**")
                        def fmt(val): return f"{int(float(val)):,}" if pd.notna(val) else "0"
                        
                        ep1, ep2, ep3 = st.columns(3)
                        is_disabled_edit_vc = e_loai_tk in ["Noi_Dia", "DHL"]
                        
                        e_phi_van_chuyen = ep1.text_input("Phí Vận Chuyển", value="0" if is_disabled_edit_vc else "0", disabled=is_disabled_edit_vc)
                        e_phi_dvhq = ep3.text_input("Phí DV Hải Quan", value=fmt(tk_info.get('phi_dich_vu_hq', 0)))
                        
                        st.caption("🏷️ Bổ sung thêm phụ phí cho tờ khai này (Sẽ được cộng vào Tổng Phí Phát Sinh đang hiển thị bên dưới)")
                        e_selected_phu_phi = st.multiselect("Phụ phí bổ sung:", options=list(dict_phu_phi_edit.keys()), format_func=lambda x: dict_phu_phi_edit[x])
                        
                        e_phi_khac = ep2.text_input("Tổng Phí Phát Sinh Hàng Lẻ/Khác (Chưa tính phí chọn ở trên)", value=fmt(tk_info['phi_khac']))

                        e_ghi_chu = st.text_input("Ghi chú bổ sung", value=tk_info['ghi_chu'] or "")
                        
                        if st.form_submit_button("💾 LƯU THAY ĐỔI TỜ KHAI", type="primary"):
                            if not e_so_to_khai.strip() or not e_so_van_don.strip():
                                st.error("❌ Số Tờ Khai và Số Vận Đơn không được để trống!")
                                st.stop()
                                
                            e_tong_phu_phi_moi = sum([float(p['don_gia_phu_phi']) for p in ds_phu_phi_edit_tong_hop if p['id'] in e_selected_phu_phi])
                            e_ten_phu_phi_moi = [p['ten_phu_phi'] for p in ds_phu_phi_edit_tong_hop if p['id'] in e_selected_phu_phi]
                            
                            e_phi_khac_final = parse_money_input(e_phi_khac) + e_tong_phu_phi_moi
                            
                            e_ghi_chu_final = e_ghi_chu.strip()
                            if e_ten_phu_phi_moi:
                                e_ghi_chu_final += f" | Thêm phí: {', '.join(e_ten_phu_phi_moi)}"

                            tk_data = {
                                'so_to_khai': e_so_to_khai, 
                                'so_van_don': e_so_van_don, 
                                'loai_to_khai': e_loai_tk, 
                                'ngay_khai': e_ngay_khai.strftime('%Y-%m-%d'),
                                'khach_hang_id': e_kh_id, 
                                'so_hoa_don_tm': e_so_hoa_don, 
                                'kho_cang_lay_hang': e_kho_cang_lay_hang,
                                'ten_doi_tac': e_ten_doi_tac,
                                'ma_loai_hinh': e_ma_loai_hinh, 
                                'so_kien': e_so_kien,
                                'tong_trong_luong_hang': e_trong_luong, 
                                'phan_luong': e_phan_luong, 
                                'phi_khac': e_phi_khac_final, 
                                'phi_dich_vu_hq': parse_money_input(e_phi_dvhq), 
                                'ghi_chu': e_ghi_chu_final
                            }
                            
                            #ok, msg = save_to_khai_transaction(db.pool, tk_data, selected_tk_id, current_user)
                            # Khi sửa tờ khai, tổng hợp các phụ phí được chọn thêm vào danh sách chi tiết phí
                            chi_tiet_phi_list_sua = []
                            for p_id in e_selected_phu_phi:
                                p_item = next((p for p in ds_phu_phi_edit_tong_hop if p['id'] == p_id), None)
                                if p_item:
                                    chi_tiet_phi_list_sua.append({
                                        'ten_loai_phi': p_item['ten_phu_phi'],
                                        'so_tien': p_item['don_gia_phu_phi'],
                                        'ghi_chu': 'Phụ phí bổ sung khi cập nhật tờ khai'
                                    })

                            ok, msg = save_to_khai_transaction(
                                db_pool=db.pool, 
                                tk_data=tk_data, 
                                chi_tiet_phi_list=chi_tiet_phi_list_sua, 
                                tk_id=selected_tk_id, 
                                current_user=current_user
                            )
                            
                            if ok: 
                                st.success("✅ Cập nhật thông tin tờ khai thành công!")
                                time.sleep(1)
                                if "select_to_khai_action" in st.session_state: del st.session_state["select_to_khai_action"]
                                st.rerun()
                            else: 
                                st.error(f"Lỗi: {msg}")
            else:
                st.info("👆 Vui lòng chọn một tờ khai ở khung bên trên để hiển thị form chỉnh sửa hoặc xóa.")
        else:
            st.info("📭 Không có tờ khai hải quan nào trong khoảng thời gian này.")
    vung_thao_tac_quan_ly_to_khai()

# ==========================================
# CÁC TAB 3 VÀ 4 GIỮ NGUYÊN HOÀN TOÀN TỪ SOURCE CŨ
# ==========================================
with tab_container:
    @st.fragment
    def vung_thao_tac_quan_ly_container():
        st.markdown("#### 📦 Quản Lý Danh Sách Container & Phí (DV Hải Quan, Nâng/Hạ Chi Tiết)")
        
        sub_tab_tao, sub_tab_sua_xoa, sub_tab_ds = st.tabs(["📥 Tạo Mới / Cập Nhật Cont Theo Lô", "🛠️ Sửa / Xóa Container Đơn Lẻ", "🔍 Tra Cứu Danh Sách"])
        
        df_cd_cont = db.execute_query("SELECT id, ngay_chuyen_di, dia_diem_giao_nhan FROM chuyen_di  WHERE trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di') ORDER BY id DESC LIMIT 100")
        dict_cd_cont = {0: "-- Không liên kết chuyến đi --"}
        if isinstance(df_cd_cont, pd.DataFrame) and not df_cd_cont.empty:
            dict_cd_cont.update({r['id']: f"Chuyến #{r['id']} - {r['dia_diem_giao_nhan']} ({r['ngay_chuyen_di']})" for _, r in df_cd_cont.iterrows()})

        dict_tk_cont = {0: "-- Không liên kết tờ khai hải quan --"}
        try:
            df_tk_cont = db.execute_query("SELECT id, so_to_khai, loai_to_khai FROM to_khai_hai_quan ORDER BY id DESC LIMIT 100")
            if isinstance(df_tk_cont, pd.DataFrame) and not df_tk_cont.empty:
                dict_tk_cont.update({r['id']: f"Tờ khai: {r['so_to_khai']} ({r['loai_to_khai']})" for _, r in df_tk_cont.iterrows()})
        except Exception:
            pass

        with sub_tab_tao:
            st.info("💡 **Mẹo:** Hệ thống sẽ tự động chuẩn hóa chữ in hoa và phân bổ Phí DVHQ, Phí Nâng/Hạ cho từng container trong lô.")
            
            if "form_tao_cont_key" not in st.session_state:
                st.session_state["form_tao_cont_key"] = "form_tao_moi_container_batch_1"

            with st.form(key=st.session_state["form_tao_cont_key"], clear_on_submit=False):
                sc1, sc2 = st.columns(2)
                cd_id_val = sc1.selectbox("Liên kết Chuyến Đi", options=list(dict_cd_cont.keys()), format_func=lambda x: dict_cd_cont[x])
                tk_id_val = sc2.selectbox("Liên kết Tờ Khai Hải Quan", options=list(dict_tk_cont.keys()), format_func=lambda x: dict_tk_cont[x])

                sc3, sc4 = st.columns(2)

                loai_cont_options = [None, "1T", "2T:","3T", "4T", "5T", "8T", "15T", "22T", "3X40", "1X40", "2X40", "1X20", "2X20","3X20", "4X40","1X45","2X45","3X45", "Khác"]
                loai_cont_default = sc3.selectbox(
                    "Loại Container chung", 
                    options=loai_cont_options, 
                    index=None, 
                    format_func=lambda x: "-- Vui lòng chọn loại container --" if x is None else x
                )
                phi_dv_hq_input = sc4.text_input("Phí DV Hải Quan (Cho mỗi cont trong lô)", value="0")
                
                st.markdown("**💰 Khai Báo Phí Nâng / Hạ Theo Lô Container**")
                p1, p2, p3, p4 = st.columns(4)
                phi_on_input = p1.text_input("Phí Nâng ON (VNĐ)", value="0")
                inv_on_input = p2.text_input("Số HĐ Nâng ON", value="")
                phi_off_input = p3.text_input("Phí Hạ OFF (VNĐ)", value="0")
                inv_off_input = p4.text_input("Số HĐ Hạ OFF", value="")
                p5, p6, p7, p8 = st.columns(4)
                phi_bot_input = p5.text_input("Phí BOT", value="0")
                phi_lay_mau_input = p6.text_input("Phí Lấy Mẫu", value="0")
                phi_kiem_dich_input = p7.text_input("Phí Kiểm Dịch", value="0")
                inv_kiem_dich_input = p8.text_input("Số HĐ Kiểm Dịch", value="")
                    
                p9, p10, p11, p12 = st.columns(4)
                phi_luu_bai_input = p9.text_input("Phí Lưu Bãi", value="0")
                inv_luu_bai_input = p10.text_input("Số HĐ Lưu Bãi", value="")
                phi_do_input = p11.text_input("Phí D/O", value="0")
                inv_do_input = p12.text_input("Số HĐ D/O", value="")
                    
                p13, p14, p15, p16 = st.columns(4)
                phi_handling_input = p13.text_input("Phí Handling", value="0")
                inv_handling_input = p14.text_input("Số HĐ Handling", value="")
                phi_khu_trung_input = p15.text_input("Phí Khử Trùng", value="0")
                inv_khu_trung_input = p16.text_input("Số HĐ Khử Trùng", value="")

                p17, p18,p19 = st.columns(3) 
                phi_van_chuyen_input = p17.text_input("Phí vận chuyển (Cho mỗi cont trong lô)", value="0")
                phi_thong_quan_input = p18.text_input("Phí thông quan (Cho mỗi cont trong lô)", value="0")
                ghi_chu_input= p19.text_input("Ghi chú", value="")

                raw_container_text = st.text_area(
                    "Danh sách số Container*",
                    placeholder="Nhập hoặc dán danh sách số container vào đây",
                    help="Hỗ trợ nhập liệu hàng loạt cho các lô hàng lớn."
                )

                if st.form_submit_button("💾 LƯU DANH SÁCH CONTAINER & CHI PHÍ", type="primary"):
                    if cd_id_val == 0 or tk_id_val == 0:
                        st.error("❌ Bắt buộc phải chọn cả liên kết Chuyến Đi và Tờ Khai Hải Quan!")
                        st.stop()
                    
                    if parse_money_input(phi_dv_hq_input)<= 0   or  parse_money_input(phi_off_input) <= 0:
                        st.error("❌ Phí DVHQ không được để trống và >0 )!")
                        st.stop()
                    if parse_money_input(phi_van_chuyen_input) <= 0 :
                        st.error("❌ Phí vận chuyển không để trống (Nhập vào)!")
                        st.stop()
                        
                    if parse_money_input(phi_on_input)<=0   or  parse_money_input(phi_off_input) <= 0:
                        st.error("❌ Số tiền phí Nâng ON và phí Hạ OFF không được để trống và >0 )!")
                        st.stop()
                        
                    if not inv_on_input.strip() or not inv_off_input.strip():
                        st.error("❌ Số hóa đơn Nâng ON và Hạ OFF không được để trống!")
                        st.stop()
                        
                    if parse_money_input(phi_bot_input) < 0 or parse_money_input(phi_lay_mau_input) < 0:
                        st.error("❌ Các giá trị phí không được phép là số âm. Vui lòng hiệu chỉnh lại!")
                        
                    if not raw_container_text.strip():
                        st.error("Vui lòng nhập ít nhất một số container.")
                    elif cd_id_val == 0 and tk_id_val == 0:
                        st.error("Vui lòng chọn liên kết Chuyến Đi và Tờ Khai Hải Quan.")
                    else:
                        tk_id_pass = tk_id_val if tk_id_val != 0 else None
                        cd_id_pass = cd_id_val if cd_id_val != 0 else None
                        
                        parts = raw_container_text.replace(',', '\n').split('\n')
                        container_list_input = []
                        
                        for p in parts:
                            std_cont = p.strip().upper()
                            if std_cont:
                                container_list_input.append({
                                    "so_cont": std_cont,
                                    "loai_cont": loai_cont_default,
                                    "chuyen_di_id": cd_id_pass, 
                                    "to_khai_id": tk_id_pass,   
                                    "phi_to_khai": phi_dv_hq_input, 
                                    "phi_nang_ha_on": phi_on_input,
                                    "so_hoa_don_lift_on": inv_on_input.strip(),
                                    "phi_nang_ha_off": phi_off_input,
                                    "so_hoa_don_lift_off": inv_off_input.strip(),
                                    "phi_bot": phi_bot_input,
                                    "phi_lay_mau": phi_lay_mau_input,
                                    "phi_kiem_dich": phi_kiem_dich_input,
                                    "so_hoa_don_kiem_dich": inv_kiem_dich_input.strip(),
                                    "phi_luu_bai": phi_luu_bai_input,
                                    "so_hoa_don_luu_bai": inv_luu_bai_input.strip(),
                                    "phi_do": phi_do_input,
                                    "so_hoa_don_do": inv_do_input.strip(),
                                    "phi_handling": phi_handling_input,
                                    "so_hoa_don_handling": inv_handling_input.strip(),
                                    "phi_khu_trung": phi_khu_trung_input,
                                    "so_hoa_don_khu_trung": inv_khu_trung_input.strip(),
                                    "phi_van_chuyen": phi_van_chuyen_input,
                                    "phi_thong_quan": phi_thong_quan_input,
                                    "ghi_chu": ghi_chu_input.strip()
                                })
                        
                        if not container_list_input:
                            st.error("Không tìm thấy số container hợp lệ sau khi bóc tách.")
                        else:
                            ok, msg = save_containers_batch_transaction(
                                db_pool=db.pool,
                                link_col="to_khai_id" if tk_id_pass else "chuyen_di_id",
                                parent_id=tk_id_pass if tk_id_pass else cd_id_pass,
                                container_list_input=container_list_input,
                                user=current_user
                            )
                            
                            if ok:
                                st.success(f"✅ Tạo mới container thành công")
                                st.session_state["form_tao_cont_key"] = f"form_tao_moi_container_batch_{uuid.uuid4()}"
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"Lỗi: {msg}")

        with sub_tab_sua_xoa:
            sql_get_all_cont = """
                SELECT c.id, c.so_cont, c.loai_cont, c.chuyen_di_id, c.to_khai_id, 
                    c.phi_to_khai, c.phi_nang_ha_on, c.so_hoa_don_lift_on, c.phi_nang_ha_off, c.so_hoa_don_lift_off,
                    c.phi_bot, c.phi_lay_mau, c.phi_kiem_dich, c.so_hoa_don_kiem_dich,
                    c.phi_luu_bai, c.so_hoa_don_luu_bai, c.phi_do, c.so_hoa_don_do,
                    c.phi_handling, c.so_hoa_don_handling, c.phi_khu_trung, c.so_hoa_don_khu_trung,c.phi_van_chuyen,c.phi_thong_quan,c.ghi_chu,
                    cd.dia_diem_giao_nhan, tk.so_to_khai
                FROM container_quan_ly c
                LEFT JOIN chuyen_di cd ON c.chuyen_di_id = cd.id
                LEFT JOIN to_khai_hai_quan tk ON c.to_khai_id = tk.id
                ORDER BY c.id DESC LIMIT 200
            """
            df_all_cont = db.execute_query(sql_get_all_cont)

            if isinstance(df_all_cont, pd.DataFrame) and not df_all_cont.empty:
                dict_cont_edit = {
                    r['id']: f"Cont: {r['so_cont']} ({r['loai_cont'] or 'N/A'}) - Chuyến #{r['chuyen_di_id'] or 'None'} - TK: {r['so_to_khai'] or 'None'}" 
                    for _, r in df_all_cont.iterrows()
                }

                selected_cont_id = st.selectbox(
                    "📌 Chọn container để thao tác sửa/xóa:",
                    options=list(dict_cont_edit.keys()),
                    format_func=lambda x: dict_cont_edit[x],
                    index=None,
                    placeholder="-- Click chọn container cần sửa / xóa --",
                    key="select_container_action_hq"
                )

                if selected_cont_id is not None:
                    cont_info = df_all_cont[df_all_cont['id'] == selected_cont_id].iloc[0]
                    action_mode_cont = st.radio("Hành động:", ["✏️ Sửa Container", "🗑️ Xóa Container"], horizontal=True, key="radio_cont_mode_hq")

                    if action_mode_cont == "🗑️ Xóa Container":
                        st.warning(f"⚠️ Bạn có chắc chắn muốn xóa container **{cont_info['so_cont']}**?")
                        if st.button("Xác Nhận Xóa Vĩnh Viễn Container", type="primary"):
                            ok, msg = delete_container_transaction(db.pool, selected_cont_id, current_user)
                            if ok:
                                st.success("✅ Đã xóa container thành công và reset lựa chọn!")
                                if "select_container_action_hq" in st.session_state:
                                    del st.session_state["select_container_action_hq"]
                                st.rerun()
                            else:
                                st.error(f"Lỗi: {msg}")
                    else:
                        with st.form(f"form_edit_cont_hq_{selected_cont_id}", clear_on_submit=False):
                            e_so_cont = st.text_input("Số Container*", value=cont_info['so_cont'])
                            
                            loai_list = ["", "1T", "2T", "3T", "4T", "5T", "8T", "15T", "22T", "3X40", "1X40", "2X40", "1X20", "2X20","3X20", "4X40","1X45","2X45","3X45", "20DC", "40HC", "45RF", "Khác"]
                            curr_loai = cont_info['loai_cont'] or ""
                            e_loai_cont = st.selectbox("Loại Container", options=loai_list, index=get_idx(loai_list, curr_loai))

                            e_chuyen_di_id = st.selectbox("Liên kết Chuyến Đi", options=list(dict_cd_cont.keys()), index=get_idx(list(dict_cd_cont.keys()), cont_info['chuyen_di_id'] or 0), format_func=lambda x: dict_cd_cont[x])
                            e_to_khai_id = st.selectbox("Liên kết Tờ Khai Hải Quan", options=list(dict_tk_cont.keys()), index=get_idx(list(dict_tk_cont.keys()), cont_info['to_khai_id'] or 0), format_func=lambda x: dict_tk_cont[x])

                            def fmt(val): return f"{int(float(val))}" if pd.notna(val) else "0"
                            st.markdown("**💰 Cập Nhật Chi Phí Riêng Cho Cont Này**")
                            ep1, ep2, ep3, ep4, ep5 = st.columns(5)
                            e_phi_dv_hq = ep1.text_input("Phí DVHQ", value=fmt(cont_info.get('phi_to_khai', 0)))
                            e_phi_on = ep2.text_input("Phí Nâng ON", value=fmt(cont_info.get('phi_nang_ha_on', 0)))
                            e_inv_on = ep3.text_input("Số HĐ Nâng ON", value=cont_info.get('so_hoa_don_lift_on') or "")
                            e_phi_off = ep4.text_input("Phí Hạ OFF", value=fmt(cont_info.get('phi_nang_ha_off', 0)))
                            e_inv_off = ep5.text_input("Số HĐ Hạ OFF", value=cont_info.get('so_hoa_don_lift_off') or "")
                            ep6, ep7, ep8, ep9 = st.columns(4)
                            e_phi_bot = ep6.text_input("Phí BOT", value=fmt(cont_info.get('phi_bot', 0)))
                            e_phi_lay_mau = ep7.text_input("Phí Lấy Mẫu", value=fmt(cont_info.get('phi_lay_mau', 0)))
                            e_phi_kiem_dich = ep8.text_input("Phí Kiểm Dịch", value=fmt(cont_info.get('phi_kiem_dich', 0)))
                            e_inv_kiem_dich = ep9.text_input("HĐ Kiểm Dịch", value=cont_info.get('so_hoa_don_kiem_dich') or "")

                            ep10, ep11, ep12, ep13 = st.columns(4)
                            e_phi_luu_bai = ep10.text_input("Phí Lưu Bãi", value=fmt(cont_info.get('phi_luu_bai', 0)))
                            e_inv_luu_bai = ep11.text_input("HĐ Lưu Bãi", value=cont_info.get('so_hoa_don_luu_bai') or "")
                            e_phi_do = ep12.text_input("Phí D/O", value=fmt(cont_info.get('phi_do', 0)))
                            e_inv_do = ep13.text_input("HĐ D/O", value=cont_info.get('so_hoa_don_do') or "")

                            ep14, ep15, ep16, ep17 = st.columns(4)
                            e_phi_handling = ep14.text_input("Phí Handling", value=fmt(cont_info.get('phi_handling', 0)))
                            e_inv_handling = ep15.text_input("HĐ Handling", value=cont_info.get('so_hoa_don_handling') or "")
                            e_phi_khu_trung = ep16.text_input("Phí Khử Trùng", value=fmt(cont_info.get('phi_khu_trung', 0)))
                            e_inv_khu_trung = ep17.text_input("HĐ Khử Trùng", value=cont_info.get('so_hoa_don_khu_trung') or "")
                            ep18, ep19,ep20 = st.columns(3) 
                            e_phi_van_chuyen = ep18.text_input("Phí vận chuyển (Cho mỗi cont trong lô)", value="0")
                            e_phi_thong_quan = ep19.text_input("Phí thông quan (Cho mỗi cont trong lô)", value="0")
                            e_ghi_chu= ep20.text_input("Ghi chú", value="")

                            if st.form_submit_button("💾 LƯU THAY ĐỔI CONTAINER", type="primary"):
                                if not e_so_cont:
                                    st.error("Số container không được để trống.")
                                else:
                                    std_so_cont = e_so_cont.strip().upper()
                                    
                                    conn_ed = None
                                    cursor_ed = None
                                    try:
                                        conn_ed = db.pool.get_connection()
                                        conn_ed.autocommit = False 
                                        cursor_ed = conn_ed.cursor()
                                        
                                        sql_up = """
                                            UPDATE container_quan_ly 
                                            SET so_cont=%s, loai_cont=%s, chuyen_di_id=%s, to_khai_id=%s, 
                                                phi_nang_ha_on=%s, so_hoa_don_lift_on=%s, phi_nang_ha_off=%s, so_hoa_don_lift_off=%s,
                                                phi_to_khai=%s, 
                                                phi_bot=%s, phi_lay_mau=%s, phi_kiem_dich=%s, so_hoa_don_kiem_dich=%s,
                                                phi_luu_bai=%s, so_hoa_don_luu_bai=%s, phi_do=%s, so_hoa_don_do=%s,
                                                phi_handling=%s, so_hoa_don_handling=%s, phi_khu_trung=%s, so_hoa_don_khu_trung=%s,phi_van_chuyen=%s,
                                                phi_thong_quan=%s,ghi_chu=%s
                                            WHERE id=%s
                                        """
                                        cursor_ed.execute(sql_up, (
                                            std_so_cont, e_loai_cont if e_loai_cont else None, e_chuyen_di_id if e_chuyen_di_id != 0 else None, e_to_khai_id if e_to_khai_id != 0 else None, 
                                            parse_money_input(e_phi_on), e_inv_on.strip(), parse_money_input(e_phi_off), e_inv_off.strip(), parse_money_input(e_phi_dv_hq),
                                            parse_money_input(e_phi_bot), parse_money_input(e_phi_lay_mau), parse_money_input(e_phi_kiem_dich), e_inv_kiem_dich.strip(),
                                            parse_money_input(e_phi_luu_bai), e_inv_luu_bai.strip(), parse_money_input(e_phi_do), e_inv_do.strip(),
                                            parse_money_input(e_phi_handling), e_inv_handling.strip(), parse_money_input(e_phi_khu_trung), e_inv_khu_trung.strip(),
                                            parse_money_input(e_phi_van_chuyen),parse_money_input(e_phi_thong_quan), e_ghi_chu.strip(), selected_cont_id
                                        ))
                                        
                                        if cursor_ed.rowcount == 0: 
                                            conn_ed.rollback()
                                            st.error("Không tìm thấy container hoặc không có thay đổi dữ liệu.")
                                        else:
                                            payload_log = {"so_cont": std_so_cont, "id": selected_cont_id}
                                            ghi_log_he_thong(cursor_ed, "QUAN_LY_CONTAINER", selected_cont_id, current_user, "CAP_NHAT_CONT_DON_LE", json.dumps(payload_log, ensure_ascii=False))
                                            conn_ed.commit()
                                            st.success("✅ Cập nhật container thành công và làm mới giao diện!")
                                            if "select_container_action_hq" in st.session_state:
                                                del st.session_state["select_container_action_hq"]
                                            st.rerun()
                                    except Exception as ex:
                                        if conn_ed: conn_ed.rollback() 
                                        st.error(f"Lỗi: {str(ex)}")
                                    finally:
                                        if cursor_ed: cursor_ed.close()
                                        if conn_ed: conn_ed.close()
                else:
                    st.info("👆 Vui lòng chọn một container từ danh sách bên trên để hiển thị form chỉnh sửa hoặc xóa.")
            else:
                st.warning("📭 Chưa có dữ liệu container nào trong hệ thống.")

        with sub_tab_ds:
            col_f1, col_f2 = st.columns(2)
            keyword = col_f1.text_input("Tìm kiếm theo Số Cont", placeholder="Nhập số cont...", key="kw_cont_hq")
            filter_loai = col_f2.selectbox("Lọc theo loại container", ["Tất cả", "20DC", "40HC", "45RF", "Khác"], key="filter_loai_hq")

            sql_ds_cont = """
                SELECT 
                    c.id AS 'ID', c.so_cont AS 'Số Container', c.loai_cont AS 'Loại Cont', c.phi_to_khai AS 'Phí DVHQ',
                    c.phi_nang_ha_on AS 'Phí Nâng ON', c.so_hoa_don_lift_on as 'HĐ Nâng ON',
                    c.phi_nang_ha_off AS 'Phí Hạ OFF', c.so_hoa_don_lift_off as 'HĐ Hạ OFF',
                    c.chuyen_di_id AS 'Mã Chuyến Đi', tk.so_to_khai AS 'Số Tờ Khai HQ', cd.doanh_thu AS 'Tổng cước vận chuyển của chuyến'
                FROM container_quan_ly c
                LEFT JOIN chuyen_di cd ON c.chuyen_di_id = cd.id
                LEFT JOIN to_khai_hai_quan tk ON c.to_khai_id = tk.id
                WHERE 1=1
            """
            params_cont = []
            if keyword:
                sql_ds_cont += " AND c.so_cont LIKE %s"
                params_cont.append(f"%{keyword.strip().upper()}%")
            if filter_loai != "Tất cả":
                sql_ds_cont += " AND c.loai_cont = %s"
                params_cont.append(filter_loai)

            sql_ds_cont += " ORDER BY c.id DESC"
            df_hien_thi_cont = db.execute_query(sql_ds_cont, tuple(params_cont) if params_cont else None)

            if isinstance(df_hien_thi_cont, pd.DataFrame) and not df_hien_thi_cont.empty:
                df_display_cont = df_hien_thi_cont.copy()
                for col_money in ['Phí DVHQ', 'Phí Nâng ON', 'Phí Hạ OFF']:
                    if col_money in df_display_cont.columns:
                        df_display_cont[col_money] = df_display_cont[col_money].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "0")
                st.markdown(f"**📊 Tìm thấy tổng cộng {len(df_display_cont)} container phù hợp:**")
                st.dataframe(df_display_cont, use_container_width=True, hide_index=True)
            else:
                st.warning("📭 Không tìm thấy dữ liệu container phù hợp với điều kiện tra cứu.")
    vung_thao_tac_quan_ly_container()