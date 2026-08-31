import streamlit as st
import pandas as pd
import datetime
import io,os,requests
import time
from map_service import MapService
from trip_manager import save_trip_full_process, tao_khach_hang_nhanh,settle_trip_transaction,delete_trip_safe,update_trip_transaction,update_trip_full_process,group_trips_transaction
from utils_core import parse_money_input, tao_tieu_de_kem_nut_refresh
from dotenv import load_dotenv
load_dotenv()

@st.cache_resource
def get_map_service(): return MapService()

map_srv = get_map_service()
db = st.session_state['db']

hide_enter_submit_css = """
<style>
    div[data-testid="InputInstructions"] { display: none !important; visibility: hidden !important; }
</style>
"""
st.markdown(hide_enter_submit_css, unsafe_allow_html=True)

STATUS_MAP = {
    "Tạo Mới": "Tao_Moi",
    "Đang Đi": "Dang_Di",
    "Quyết Toán": "Quyet_Toan",
    "Hoàn Thành": "Hoan_Thanh",
    "Hủy Chuyến": "Huy_Chuyen"
}

st.markdown("<h3 style='text-align: center; color: #0b5394;'>📝 PHÂN HỆ QUYẾT TOÁN CHUYẾN ĐI</h3>", unsafe_allow_html=True)

tab1, tab2, tab3,tab4 = st.tabs([
    "🏁 Quyết toán đơn chuyến",
    "🏁 Sửa chuyến đi đã quyết toán", 
    "🤖 Quyết toán theo file",
    "📊 Lịch sử quyết toán",
])
# =========================================================================
# HÀM LÕI: ĐỘNG CƠ LUẬT TÍNH PHỤ PHÍ (RULE ENGINE) - DÙNG CHUNG CHO TAB 1 & TAB 3
# ========================================================================

import re

def clean_money_val(val):
    """Hàm làm sạch tiền tệ, giữ nguyên độ chuẩn xác"""
    if val is None or pd.isna(val) or str(val).strip() == "": return 0.0
    if isinstance(val, (int, float)): return float(val)
    s = str(val).replace(',', '').replace(' ', '').strip()
    try:
        return float(s)
    except:
        return 0.0
def rule_engine_calc(kh_id, tai_trong_xe_tan, doanh_thu, facts, db_instance):
    tong_tien_tu_dong = 0.0
    ghi_chu_tu_dong = []
    if not kh_id: return 0.0, []
    
    if tai_trong_xe_tan >= 50:
        tai_trong_xe_tan = tai_trong_xe_tan / 1000.0
        
    def tinh_tien_goc(gia_niem_yet, loai_chuoi, doanh_thu_chuyen):
        loai_str = str(loai_chuoi).strip().lower()
        is_phan_tram = ('%' in loai_str) or ('phan_tram' in loai_str) or ('phantram' in loai_str)
        if not is_phan_tram and loai_str not in ['co_dinh', 'codinh', 'vnd', '']:
            try:
                val = float(loai_str)
                if 0 < val <= 1.0: is_phan_tram = True
            except: pass
            
        if is_phan_tram:
            if doanh_thu_chuyen <= 0: return 0.0 
            import re
            nums = re.findall(r'\d+\.?\d*', loai_str)
            if nums:
                ty_le = float(nums[0])
                return (ty_le * doanh_thu_chuyen) if ty_le <= 1.0 else ((ty_le / 100.0) * doanh_thu_chuyen)
            else:
                if gia_niem_yet > 0 and gia_niem_yet <= 1.0: return gia_niem_yet * doanh_thu_chuyen
                elif gia_niem_yet > 1.0: return (gia_niem_yet / 100.0) * doanh_thu_chuyen
        return float(gia_niem_yet)
        
    try:
        sql_pp = "SELECT ten_phu_phi, don_gia_phu_phi, loai_ap_dung, dieu_kien_kich_hoat FROM phu_phi_khach_hang WHERE khach_hang_id = %s"
        df_pp = db_instance.execute_query(sql_pp, (kh_id,))
        
        matched_candidates = []
        
        import json
        if isinstance(df_pp, pd.DataFrame) and not df_pp.empty:
            for _, pp in df_pp.iterrows():
                dk_str = str(pp.get('dieu_kien_kich_hoat', '')).strip()
                ten_pp = str(pp['ten_phu_phi'])
                loai = str(pp.get('loai_ap_dung', 'Co_Dinh'))
                gia = float(pp.get('don_gia_phu_phi') or 0.0)
                
                tien_item = 0.0
                ly_do = ""
                ldk_key = ""
                range_size = 99999.0
                
                if dk_str.startswith("{") and dk_str.endswith("}"):
                    try:
                        dk_raw = json.loads(dk_str)
                        dk = {str(k).strip().lower(): v for k, v in dk_raw.items()}
                        
                        ldk = str(dk.get('loai', '')).strip().lower()
                        ldk_key = ldk
                        
                        raw_min = float(dk.get('tai_trong_min', 0.0))
                        raw_max = float(dk.get('tai_trong_max', 999.0))
                        tt_min = (raw_min / 1000.0) if raw_min >= 50 else raw_min
                        tt_max = (raw_max / 1000.0) if raw_max >= 50 else raw_max
                        
                        range_size = tt_max - tt_min
                        has_weight_limit = (raw_min > 0 or raw_max < 999.0)
                        is_tt_ok = (tt_min <= tai_trong_xe_tan <= tt_max) if has_weight_limit else True
                        
                        if ldk == "giao_diem_them" and facts.get('so_diem_giao_them', 0) > 0:
                            km_min = float(dk.get('km_min', 0.0))
                            km_max = float(dk.get('km_max', 9999.0))
                            km = facts.get('so_km_phat_sinh', 0.0)
                            if (km_min <= km <= km_max) and is_tt_ok:
                                kieu_tinh = str(dk.get('kieu_tinh', '')).strip().lower()
                                if kieu_tinh == "phan_tram_diem_xa_nhat": tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                                else: tien_item = gia * facts['so_diem_giao_them']
                                ly_do = f"Giao {facts['so_diem_giao_them']} điểm, {km}km"
                        
                        elif ldk == "boc_xep" and facts.get('is_boc_xep') and is_tt_ok:
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                            ly_do = f"Bốc xếp {tai_trong_xe_tan}T"
                                
                        elif ldk == "ve_khuya" and facts.get('is_ve_khuya') and is_tt_ok:
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                            ly_do = f"Về khuya {tai_trong_xe_tan}T"
                                
                        elif ldk in ["nang_ha_cont", "phi_qua_cang"] and facts.get('cang_nang_ha'):
                            cang_dk = str(dk.get('cang', '')).strip().lower()
                            cang_fact = str(facts.get('cang_nang_ha', '')).strip().lower()
                            if cang_dk == cang_fact:
                                tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                                ly_do = f"Qua cảng/Nâng hạ {dk.get('cang')}"
                                
                        elif ldk == "phu_thu_chu_nhat" and facts.get('is_chu_nhat'):
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                            ly_do = "Phụ thu Chủ Nhật"
                            
                        elif ldk == "lay_seal_som" and facts.get('is_lay_seal_som') and is_tt_ok:
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                            ly_do = "Lấy seal/cont sớm 1 ngày"

                        elif ldk == "lam_hang_cang" and facts.get('is_lam_hang_cang') and is_tt_ok:
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                            ly_do = "Làm hàng cảng"    

                        elif ldk == "chuyen_cont_rong" and facts.get('is_cont_rong') and is_tt_ok:
                            nghiep_vu = str(dk.get('nghiep_vu', '')).strip().lower()
                            if nghiep_vu == "trai_tuyen" and not facts.get('is_cont_rong_trai_tuyen'): pass 
                            else:
                                tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                                ly_do = f"{facts.get('loai_cont_rong_text', 'Xử lý Cont rỗng')}"
                        # 👇 THÊM MỚI NHÁNH NÀY: Xử lý đích danh cấu hình JSON "ha_xa_trai_tuyen"
                        elif ldk == "ha_xa_trai_tuyen" and facts.get('is_cont_rong_trai_tuyen') and is_tt_ok:
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                            ly_do = f"{facts.get('loai_cont_rong_text', 'Hạ xả cont rỗng trái tuyến')}"
                                
                        elif ldk == "neo_xe_tai":
                            so_ngay = facts.get('so_ngay_neo_xe', 0)
                            if so_ngay > 0:
                                tien_item = tinh_tien_goc(gia, loai, doanh_thu) * so_ngay
                                ly_do = f"Neo Xe tải {so_ngay} ngày"

                        elif ldk == "neo_xe_tai_nha_may":
                            so_ngay = facts.get('so_ngay_neo_xe_nha_may', 0)
                            if so_ngay > 0:
                                tien_item = tinh_tien_goc(gia, loai, doanh_thu) * so_ngay
                                ly_do = f"Neo Xe tải Nhà máy {so_ngay} ngày"

                        #elif ldk == "neo_cont":
                        #    so_ngay = facts.get('so_ngay_neo_cont', 0)
                        #    if so_ngay > 0:
                        #        tien_item = tinh_tien_goc(gia, loai, doanh_thu) * so_ngay
                        #        ly_do = f"Neo Container {so_ngay} ngày"
                        # 1. TRƯỜNG HỢP CẤU HÌNH BẰNG CHUỖI JSON
                        elif ldk == "neo_cont":
                            so_ngay = facts.get('so_ngay_neo_cont', 0)
                            if so_ngay > 0:
                                # Trích xuất chiều cont từ cấu hình JSON và từ UI truyền vào
                                chieu_dk = str(dk.get('chieu', '')).strip().lower()
                                chieu_fact = str(facts.get('chieu_cont', '')).strip().lower()
                                
                                # Chỉ áp dụng giá nếu không cấu hình chiều, hoặc chiều cấu hình khớp hoàn toàn với thực tế
                                if not chieu_dk or chieu_dk == chieu_fact:
                                    tien_item = tinh_tien_goc(gia, loai, doanh_thu) * so_ngay
                                    ly_do = f"Neo Container {so_ngay} ngày"
                                    # Ghi chú rõ chiều cont để hiển thị log quyết toán
                                    if chieu_dk: 
                                        ly_do += f" (Chiều {chieu_fact.title()})"
                                        ldk_key = f"{ldk}_{chieu_fact}" #
                            
                        elif ldk == "huy_chuyen" and facts.get('is_huy_chuyen'):
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                            ly_do = "Hủy chuyến"
                            
                        elif ldk == "qua_tai_cont" and facts.get('is_overload_cont'):
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                            ly_do = "Quá tải cont"
                        #elif ldk == "hai_quan_kiem_dich" and facts.get('is_luong_do'):
                        #    tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                        #    ly_do = "HQ/Kiểm hóa"
                            
                        elif ldk == "phu_phi_khac" or "khác khu" in ten_pp.lower() or "khac khu" in ten_pp.lower():
                            if facts.get('is_giao_khac_khu'):
                                tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                                ly_do = "Giao khác khu nội bộ"
                            
                    except Exception as e: pass
                else:
                    tl = ten_pp.lower()
                    ldk_key = "text_match_" + tl
                    if "neo xe tải nhà máy" in tl or "neo xe tai nha may" in tl:
                        so_ngay = facts.get('so_ngay_neo_xe_nha_may', 0)
                        if so_ngay > 0:
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu) * so_ngay
                            ly_do = f"Neo Xe tải Nhà máy {so_ngay} ngày"
                    elif "neo xe tải" in tl or "neo xe tai" in tl:
                        so_ngay = facts.get('so_ngay_neo_xe', 0)
                        if so_ngay > 0:
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu) * so_ngay
                            ly_do = f"Neo Xe tải {so_ngay} ngày"
                    # 2. TRƯỜNG HỢP CẤU HÌNH BẰNG TEXT GÕ TAY (Text Match)
                    elif "neo cont" in tl:
                        so_ngay = facts.get('so_ngay_neo_cont', 0)
                        if so_ngay > 0:
                            chieu_fact = str(facts.get('chieu_cont', '')).strip().lower()
                            
                            # Kiểm tra xem tên phụ phí có cấu hình đích danh chữ "nhập" hoặc "xuất" hay không
                            is_match = True
                            if ("nhập" in tl or "nhap" in tl) and chieu_fact != "nhap": is_match = False
                            if ("xuất" in tl or "xuat" in tl) and chieu_fact != "xuat": is_match = False
                            
                            if is_match:
                                tien_item = tinh_tien_goc(gia, loai, doanh_thu) * so_ngay
                                ly_do = f"Neo Container {so_ngay} ngày"
                                if chieu_fact:
                                    ly_do += f" (Chiều {chieu_fact.title()})"
                                    ldk_key = f"text_match_neocont_{chieu_fact}"
                    elif facts.get('is_huy_chuyen') and ("huỷ" in tl or "hủy" in tl):
                        tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                        ly_do = "Hủy chuyến"
                    elif facts.get('is_chu_nhat') and ("chủ nhật" in tl or "chu nhat" in tl):
                        tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                        ly_do = "Phụ thu Chủ Nhật"
                    elif facts.get('is_lay_seal_som') and ("seal sớm" in tl or "seal som" in tl or "trước 1 ngày" in tl):
                        tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                        ly_do = "Lấy seal/cont sớm 1 ngày"
                    # 👇 THÊM MỚI NHÁNH NÀY (Bên dưới lấy seal sớm, bên trên cont rỗng): Bắt chữ "trái tuyến"
                    elif facts.get('is_cont_rong_trai_tuyen') and ("trái tuyến" in tl or "trai tuyen" in tl):
                        tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                        ly_do = f"{facts.get('loai_cont_rong_text', 'Hạ xả cont rỗng trái tuyến')}"

                    elif facts.get('is_cont_rong') and ("cont rỗng" in tl or "cont rong" in tl):
                        tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                        ly_do = f"{facts.get('loai_cont_rong_text', 'Xử lý Cont rỗng')}"
                    elif facts.get('is_giao_khac_khu') and ("khác khu" in tl or "khac khu" in tl):
                        tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                        ly_do = "Giao khác khu nội bộ"
                        
                if tien_item > 0:
                    matched_candidates.append({
                        'ldk': ldk_key,
                        'ten_pp': ten_pp,
                        'tien': tien_item,
                        'ly_do': ly_do,
                        'range_size': range_size
                    })

        final_fees = []
        best_per_ldk = {}
        for cand in matched_candidates:
            c_ldk = cand['ldk']
            if c_ldk == "phu_phi_khac" or c_ldk.startswith("text_match_"):
                final_fees.append(cand)
            else:
                if c_ldk not in best_per_ldk: best_per_ldk[c_ldk] = cand
                else:
                    if cand['range_size'] < best_per_ldk[c_ldk]['range_size']: best_per_ldk[c_ldk] = cand
                        
        for k, v in best_per_ldk.items(): final_fees.append(v)
            
        for f in final_fees:
            tong_tien_tu_dong += f['tien']
            ghi_chu_tu_dong.append(f"{f['ten_pp']}: {f['tien']:,.0f}đ ({f['ly_do']})")
            
    except Exception as e: print(f"Lỗi DB Phụ phí: {e}")
    
    return tong_tien_tu_dong, ghi_chu_tu_dong

# =========================================================================
# BỔ SUNG: HÀM LÕI TÍNH TOÁN PHỤ CẤP TÀI XẾ TỪ MA TRẬN
# =========================================================================
def tinh_phu_cap_tai_xe(db_instance, xe_id, danh_sach_tieu_chi_id):
    if not danh_sach_tieu_chi_id or pd.isna(xe_id) or not xe_id: 
        return 0.0, ""
    try:
        df_xe = db_instance.execute_query("SELECT tai_trong_thiet_ke FROM xe WHERE id = %s", (int(xe_id),))
        if not isinstance(df_xe, pd.DataFrame) or df_xe.empty: return 0.0, ""
        tai_trong = float(df_xe.iloc[0]['tai_trong_thiet_ke'] or 0)
        
        sql_khung = "SELECT id FROM dm_tai_trong_phu_cap WHERE tai_trong_min <= %s AND tai_trong_max >= %s ORDER BY tai_trong_min DESC LIMIT 1"
        df_khung = db_instance.execute_query(sql_khung, (tai_trong, tai_trong))
        if not isinstance(df_khung, pd.DataFrame) or df_khung.empty: return 0.0, ""
        tt_id = int(df_khung.iloc[0]['id'])
        
        format_strs = ','.join(['%s'] * len(danh_sach_tieu_chi_id))
        sql_tien = f"SELECT mt.so_tien, tc.ten_tieu_chi FROM ma_tran_phu_cap mt JOIN dm_tieu_chi_phu_cap tc ON mt.tieu_chi_id = tc.id WHERE mt.tai_trong_id = %s AND mt.tieu_chi_id IN ({format_strs})"
        params = [tt_id] + danh_sach_tieu_chi_id
        df_tien = db_instance.execute_query(sql_tien, tuple(params))
        
        tong_tien = 0.0
        dien_giai = []
        if isinstance(df_tien, pd.DataFrame) and not df_tien.empty:
            for _, r in df_tien.iterrows():
                tong_tien += float(r['so_tien'])
                dien_giai.append(f"{r['ten_tieu_chi']} (+{float(r['so_tien']):,.0f}đ)")
        
        return tong_tien, " | ".join(dien_giai)
    except Exception as e:
        print(f"Lỗi tính phụ cấp: {e}")
        return 0.0, ""
# ==========================================
# TAB 1: QUYẾT TOÁN ĐƠN CHUYẾN (ĐÃ TỐI ƯU HÓA)
# ==========================================
with tab1:
    tao_tieu_de_kem_nut_refresh("📋 Quyết toán và cập nhật chi phí chuyến đi", "ref_tab1")

    @st.fragment
    def vung_thao_tac_quyet_toan_chuyen_di():
        if "reset_chuyen_form" not in st.session_state: 
            st.session_state["reset_chuyen_form"] = 0

            # có bổ sung cd.stt_chuyen_ghep
        sql_load = """
            SELECT cd.id, cd.ngay_chuyen_di, cd.ten_khach_hang, cd.khach_hang_id, cd.xe_id,
                COALESCE(x.bien_so_xe, cd.bien_so_xe_ngoai) AS bien_so_xe, 
                CAST(x.tai_trong_thiet_ke AS FLOAT) AS tai_trong,
                x.quy_cach_thung, cd.ghi_chu,
                COALESCE(nv.ho_ten, cd.tai_xe_ngoai_ten) AS ten_tai_xe, 
                cd.trang_thai_chuyen, cd.doanh_thu, cd.dia_diem_giao_nhan,
                cd.cong_chuyen, cd.tien_them,
                cd.phi_hai_quan, cd.phi_boc_xep, cd.phi_khac, cd.ghi_chu_quyet_toan,
                cd.is_gop_chuyen, cd.stt_chuyen_ghep, cd.is_ve_khuya, cd.khoi_luong_kg, cd.the_tich_cbm,cd.is_hang_tra_ve,
                cd.is_thue_ngoai, cd.chi_phi_thue_ngoai, cd.hinh_thuc_thanh_toan_ngoai
            FROM chuyen_di cd
            LEFT JOIN xe x ON cd.xe_id = x.id
            LEFT JOIN chuyen_di_tai_xe ctx ON cd.id = ctx.chuyen_di_id AND ctx.loai_tai_xe = 'Tai_Chinh'
            LEFT JOIN nhan_vien nv ON ctx.tai_xe_id = nv.id
            WHERE cd.trang_thai_chuyen IN ('Quyet_Toan','Tao_Moi','Dang_Di')
            ORDER BY cd.ngay_chuyen_di DESC
        """
        df_cd = db.execute_query(sql_load)

        if isinstance(df_cd, pd.DataFrame) and not df_cd.empty:
            trip_options = {
                row['id']: f"Mã: {row['id']} | Ngày: {row['ngay_chuyen_di']} | Khách: {row['ten_khach_hang']} | Xe: {row['bien_so_xe']} | TX: {row['ten_tai_xe']}"
                for _, row in df_cd.iterrows()
            }
            
            cd_id = st.selectbox(
                "🔍 Chọn chuyến đi đang chờ quyết toán:", 
                options=list(trip_options.keys()), 
                format_func=lambda x: trip_options[x],
                key=f"sel_trip_{st.session_state['reset_chuyen_form']}"
            )
            
            row_sel = df_cd[df_cd['id'] == cd_id].iloc[0]
            is_thue_ngoai = bool(row_sel['is_thue_ngoai'])
            
            kh_id_raw = row_sel.get('khach_hang_id')
            ten_kh_qt = row_sel.get('ten_khach_hang')
            kh_id_qt = int(float(kh_id_raw)) if pd.notna(kh_id_raw) and str(kh_id_raw).strip() != "" else None
            
            if not kh_id_qt and pd.notna(ten_kh_qt):
                try:
                    df_find_kh = db.execute_query("SELECT id FROM khach_hang WHERE ten_khach_hang LIKE %s LIMIT 1", (f"%{str(ten_kh_qt).strip()}%",))
                    if isinstance(df_find_kh, pd.DataFrame) and not df_find_kh.empty: 
                        kh_id_qt = int(df_find_kh.iloc[0]['id'])
                except: pass

            # ========================================================
            # 📦 THÊM GIAO DIỆN CHỌN THUỘC TÍNH HÀNG HÓA & CONTAINER
            # ========================================================
            st.markdown("##### 📦 Khai báo Tính chất Hàng hóa & Container")
            # 🚀 CHỈNH SỬA: Tăng lên 4 cột và kéo Checkbox "Hàng về" ra khỏi Form để load giá Real-time
            col_hh1, col_hh2, col_hh3, col_hh4 = st.columns(4)
            loai_hang_ui = col_hh1.selectbox("Tính chất hàng", options=["Thường", "Nguy hiểm"], key=f"lh_{cd_id}")
            loai_cont_ui = col_hh2.selectbox("Loại Container", options=["Thường", "Lạnh (RF)"], key=f"lc_{cd_id}")
            chieu_cont_ui = col_hh3.selectbox("Chiều Cont", options=["Không phân biệt", "Nhập", "Xuất"], key=f"chieu_{cd_id}")
            
            is_hang_ve_db_val = bool(row_sel.get('is_hang_tra_ve', 0))
            is_hang_ve_ui = col_hh4.checkbox("🔄 Chở hàng về (Lấy giá 2 chiều)", value=is_hang_ve_db_val, key=f"is_ve_{cd_id}")

            # Đính kèm biến is_hang_ve_ui vào key để AI biết mà load lại giá khi check/uncheck
            dt_state_key = f"cached_dt_{cd_id}_{loai_hang_ui}_{loai_cont_ui}_{is_hang_ve_ui}"
            
            if dt_state_key not in st.session_state:
                doanh_thu_db = float(row_sel.get('doanh_thu', 0) or 0.0)
                lo_trinh_hien_tai = str(row_sel.get('dia_diem_giao_nhan', ''))
                # --- KHỞI TẠO CỜ HIỆU ĐỂ BÁO CÁO RA UI ---
                st.session_state[f"has_route_{cd_id}"] = False
                st.session_state[f"tt_tan_{cd_id}"] = 0.0
                if doanh_thu_db == 0 and "➡️" in lo_trinh_hien_tai and kh_id_qt:
                    try:
                        import re
                        parts = lo_trinh_hien_tai.split("➡️")
                        ddi = parts[0].strip()
                        dden = parts[1].strip()
                        
                        # 🚀 NÂNG CẤP SQL: TÌM GIÁ KẾT HỢP BIẾN HÀNG VỀ & LOGIC ĐẢO CHIỀU
                        flag_hang_ve = 1 if is_hang_ve_ui else 0
                        
                        sql_rc = """
                            SELECT id, don_gia_cuoc,gia_chuyen_tiep_noi, phan_loai_phuong_tien, loai_xe_quy_cach 
                            FROM rate_cards 
                            WHERE khach_hang_id = %s AND diem_di LIKE %s AND diem_den LIKE %s AND is_hang_tra_ve = %s
                            ORDER BY id DESC
                        """
                        df_rc = db.execute_query(sql_rc, (kh_id_qt, f"%{ddi}%", f"%{dden}%", flag_hang_ve))
                        
                        # 💡 BỘ LỌC DỰ PHÒNG (FALLBACK): 
                        # Nếu là chuyến bình thường (flag_hang_ve = 0) mà lại không tìm thấy giá gốc.
                        # -> Đảo ngược Điểm Đến & Điểm Đi để lấy 100% giá chiều đi (VD: Cát Lái -> Cty sẽ lấy giá của Cty -> Cát Lái)
                        if flag_hang_ve == 0 and (not isinstance(df_rc, pd.DataFrame) or df_rc.empty):
                            df_rc = db.execute_query(sql_rc, (kh_id_qt, f"%{dden}%", f"%{ddi}%", 0))
                        
                        if isinstance(df_rc, pd.DataFrame) and not df_rc.empty:
                            matched_price = 0.0
                            # 2. FIX LỖI SO SÁNH TRỌNG TẢI: Ưu tiên lấy Khối lượng (KG) khách book của riêng mã chuyến này
                            booked_kg = float(row_sel.get('khoi_luong_kg', 0.0) or 0.0)
                            tt_xe_tan = (booked_kg / 1000.0) if booked_kg > 0 else 0.0
                            
                            # Fallback: Chỉ khi Kế toán lúc lên lệnh quên nhập KG thì mới lấy tạm tải trọng xe
                            if tt_xe_tan <= 0:
                                tt_xe_float = float(row_sel.get('tai_trong', 99.0) or 99.0)
                                tt_xe_tan = (tt_xe_float / 1000.0) if tt_xe_float >= 50 else tt_xe_float
                            
                            quy_cach_xe = str(row_sel.get('quy_cach_thung', '')).lower()
                            ghi_chu_chuyen = str(row_sel.get('ghi_chu', '')).lower()
                            text_context = f"{quy_cach_xe} {ghi_chu_chuyen}".replace("_", " ")

                            has_nguy_hiem = (loai_hang_ui == "Nguy hiểm") or ('nguy hiem' in text_context) or ('nguyhiem' in text_context)
                            has_lanh = (loai_cont_ui == "Lạnh (RF)") or ('lạnh' in text_context) or ('lanh' in text_context) or ('rf' in text_context)
                            # 2. BỐC DỮ LIỆU TỪ DATABASE (Đã fix theo đúng schema của bạn)
                            is_ghep = int(row_sel.get('is_gop_chuyen', 0) if pd.notna(row_sel.get('is_gop_chuyen')) else 0)
                            stt_ghep = int(row_sel.get('stt_chuyen_ghep', 1) if pd.notna(row_sel.get('stt_chuyen_ghep')) else 1)

                            for _, rc in df_rc.iterrows():
                                pl_pt_gia = str(rc.get('phan_loai_phuong_tien', '')).strip() 
                                qc_gia = str(rc.get('loai_xe_quy_cach', '')).strip().lower().replace("_", " ")

                                req_nguy_hiem = any(x in qc_gia for x in ['nguy hiem', 'nguyhiem'])
                                req_lanh = any(x in qc_gia for x in ['lạnh', 'lanh', 'rf'])
                                req_thuong = any(x in qc_gia for x in ['thường', 'thuong'])

                                is_prop_match = True
                                if req_nguy_hiem and not has_nguy_hiem: is_prop_match = False
                                if req_lanh and not has_lanh: is_prop_match = False
                                if req_thuong and (has_nguy_hiem or has_lanh): is_prop_match = False

                                if pl_pt_gia == 'Xe_May':
                                    if tt_xe_tan < 1.0 or 'xe may' in text_context or 'xe máy' in text_context:
                                        if is_prop_match:
                                            matched_price = float(rc['don_gia_cuoc'])
                                            break
                                    continue

                                if pl_pt_gia == 'Container':
                                    cont_kws = ['20', '40', '45', 'hc', 'dc','rf'] 
                                    req_kws = [kw for kw in cont_kws if kw in qc_gia]
                                    
                                    if req_kws:
                                        if all(kw in text_context for kw in req_kws) and is_prop_match:
                                            matched_price = float(rc['don_gia_cuoc'])
                                            break
                                    else:
                                        if ('cont' in text_context or tt_xe_tan >= 15) and is_prop_match:
                                            matched_price = float(rc['don_gia_cuoc'])
                                            break
                                    continue

                                if pl_pt_gia in ['Xe_Tai', 'Hang_Le']:
                                    nums_in_str = re.findall(r'\d+\.?\d*', qc_gia)
                                    float_nums = [float(n) for n in nums_in_str]
                                    is_weight_match = False

                                    if len(float_nums) == 2:
                                        if min(float_nums) <= tt_xe_tan <= max(float_nums): is_weight_match = True
                                    elif len(float_nums) == 1:
                                        val = float_nums[0]
                                        if any(op in qc_gia for op in ['<=', 'dưới', 'duoi']):
                                            if tt_xe_tan <= val: is_weight_match = True
                                        elif '<' in qc_gia:
                                            if tt_xe_tan < val: is_weight_match = True
                                        elif any(op in qc_gia for op in ['>=', 'trên', 'tren']):
                                            if tt_xe_tan >= val: is_weight_match = True
                                        elif '>' in qc_gia:
                                            if tt_xe_tan > val: is_weight_match = True
                                        else:
                                            # 🎯 CHỈ SO SÁNH CHÍNH XÁC (KHÔNG TỰ Ý LÀM TRÒN)
                                            if tt_xe_tan == val: is_weight_match = True
                                    elif len(float_nums) == 0:
                                        is_weight_match = True 

                                    if not (is_weight_match and is_prop_match):
                                        continue

                                
                                    # 3. CHỐT GIÁ: Dùng đúng dữ liệu stt_chuyen_ghep từ Database của bạn
                                    gia_goc = float(rc.get('don_gia_cuoc', 0) or 0.0)
                                    gia_tiep_noi = float(rc.get('gia_chuyen_tiep_noi', 0) or 0.0)
                                    
                                    if is_ghep == 1 and stt_ghep > 1:
                                        # Nếu là chuyến thứ 2 trở đi -> Lấy giá tiếp nối. 
                                        # Nếu giá tiếp nối = 0 (chưa thiết lập) -> Fallback lấy giá gốc.
                                        matched_price = gia_tiep_noi if gia_tiep_noi > 0 else gia_goc
                                    else:
                                        # Chuyến đầu tiên (STT = 1) -> Lấy giá gốc
                                        matched_price = gia_goc
                                        
                                    break # Match thành công -> Thoát vòng lặp
                            
                            if matched_price > 0:
                                doanh_thu_db = matched_price
                                
                    except Exception as e: pass 
                
                st.session_state[dt_state_key] = doanh_thu_db

            doanh_thu_hien_tai = st.session_state[dt_state_key]
            has_route_in_db = st.session_state.get(f"has_route_{cd_id}", False)
            tt_xe_tan = st.session_state.get(f"tt_tan_{cd_id}", 0.0)

            with st.form(key=f"form_qt_{st.session_state['reset_chuyen_form']}"):
                st.markdown(f"##### 📍 1. Chi phí vận hành {'[THUÊ NGOÀI]' if is_thue_ngoai else '[NỘI BỘ]'}")
                edit_cong_ty = st.text_input("Tên Khách hàng / Công ty", value=str(row_sel['ten_khach_hang'] or ""))
                
                show_save_rate = False

                if doanh_thu_hien_tai > 0:
                    st.success(f"💡 HỆ THỐNG ĐÃ XÁC NHẬN CƯỚC BẢNG GIÁ: **{doanh_thu_hien_tai:,.0f} VNĐ**")
                elif has_route_in_db:
                    st.warning(f"⚠️ Tuyến đường đã có trong Bảng giá nhưng **lệch tải trọng/quy cách** ({tt_xe_tan} Tấn). Vui lòng tự nhập cước và lưu lại để dùng cho lần sau!")
                    show_save_rate = True
                else:
                    st.warning("⚠️ Tuyến đường này chưa có trong Bảng giá. Vui lòng tự nhập cước vào ô bên dưới:")

                doanh_thu_input = st.text_input(
                    "Doanh thu cước khách (VNĐ)", 
                    value=f"{doanh_thu_hien_tai:,.0f}" if doanh_thu_hien_tai > 0 else "0"
                )

                is_save_to_rc = False
                if show_save_rate:
                    is_save_to_rc = st.checkbox(f"💾 Lưu mức giá này cho tải trọng {tt_xe_tan}T vào Bảng giá (rate_cards)", value=True)

                if not is_thue_ngoai:
                    chi_phi_ngoai_input = "0"
                    hinh_thuc_thanh_toan_ngoai = "Cong_No"
                else:
                    col_n1, col_n2 = st.columns(2)
                    chi_phi_ngoai_input = col_n1.text_input("Chi phí thuê xe ngoài (VNĐ)*", value=f"{float(row_sel['chi_phi_thue_ngoai'] or 0):,.0f}")
                    tt_opts = ["Cong_No", "Tien_Mat"]
                    def_idx = tt_opts.index(row_sel['hinh_thuc_thanh_toan_ngoai']) if pd.notna(row_sel['hinh_thuc_thanh_toan_ngoai']) and row_sel['hinh_thuc_thanh_toan_ngoai'] in tt_opts else 0
                    hinh_thuc_thanh_toan_ngoai = col_n2.selectbox("Hình thức thanh toán", options=tt_opts, index=def_idx, format_func=lambda x: "Công nợ" if x=="Cong_No" else "Tiền mặt")

                st.divider()
                
                st.markdown("##### 🤖 2. Khai báo phát sinh (AI sẽ tự động tính ra Phụ phí)")
                c_f1, c_f2, c_f3 = st.columns(3)
                f_km = c_f1.number_input("🛣️ Số KM đi lố (Phát sinh)", min_value=0.0, step=1.0)
                f_diem = c_f2.number_input("📍 Số điểm giao thêm", min_value=0, step=1)
                f_neo_xe = c_f3.number_input("⏳ Số ngày neo xe tải", min_value=0, step=1)

                c_f4, c_f5, c_f6, c_f7 = st.columns(4)
                f_neo_cont = c_f4.number_input("🧊 Số ngày neo Cont", min_value=0, step=1)
                f_huy = c_f5.checkbox("❌ Khách Hủy chuyến")
                f_boc = c_f6.checkbox("📦 Có bốc xếp")
                f_overload_cont = c_f7.checkbox("🛂 Quá tải container")

                # GIAO DIỆN MỚI CHO CÁC NGHIỆP VỤ CAO CẤP (Đã bỏ checkbox hàng về)
                c_f8, c_f9, c_f10, c_f11,c_f12 = st.columns(5)
                f_seal = c_f8.checkbox("🔒 Lấy Seal/Cont sớm 1 ngày")
                f_khac_khu = c_f9.checkbox("🏢 Giao khác khu nội bộ")
                cang_opts = ["", "Dong_Nai", "Hiep_Phuoc", "VICT", "Cai_Mep"]
                f_cang = c_f10.selectbox("⚓ Nâng hạ/Qua cảng", options=cang_opts)
                cont_rong_opts = ["Không", "Lấy Cont rỗng", "Hạ Cont rỗng", "Trái tuyến (Lấy/Hạ)"]
                f_cont_rong = c_f11.selectbox("🔄 Xử lý Cont rỗng", options=cont_rong_opts)
                f_lam_hang_cang = c_f12.checkbox("📦 Có làm hàng cảng")
                st.divider()

                # --- BỔ SUNG: KHAI BÁO PHỤ CẤP TÀI XẾ ---
                selected_tc_ids = []
                if not is_thue_ngoai:
                    st.markdown("##### 🎁 3. Khai báo Phụ cấp Tài xế (Theo ma trận tải trọng)")
                    
                    
                    # 🚀 LẤY KHOẢNG CÁCH TỪ BẢNG GIÁ ĐỂ TỰ ĐỘNG CHỌN TIÊU CHÍ PHỤ CẤP
                    kc_auto = 0.0
                    auto_tc_ids = []
                    try:
                        if "➡️" in str(row_sel.get('dia_diem_giao_nhan', '')) and kh_id_qt:
                            parts = str(row_sel['dia_diem_giao_nhan']).split("➡️")
                            df_kc = db.execute_query("SELECT khoang_cach FROM rate_cards WHERE khach_hang_id=%s AND diem_di LIKE %s AND diem_den LIKE %s LIMIT 1", (kh_id_qt, f"%{parts[0].strip()}%", f"%{parts[1].strip()}%"))
                            if isinstance(df_kc, pd.DataFrame) and not df_kc.empty:
                                kc_auto = float(df_kc.iloc[0]['khoang_cach'] or 0.0)
                                
                            if kc_auto > 0:
                                sql_find_tc = "SELECT id, ten_tieu_chi FROM dm_tieu_chi_phu_cap WHERE %s >= km_min AND %s <= km_max"
                                df_find_tc = db.execute_query(sql_find_tc, (kc_auto, kc_auto))
                                
                                if isinstance(df_find_tc, pd.DataFrame) and not df_find_tc.empty:
                                    lo_trinh_hien_tai_lower = str(row_sel.get('dia_diem_giao_nhan', '')).lower()
                                    # Danh sách các từ khóa địa danh đặc thù có trong nội dung phụ cấp
                                    ds_dia_danh = ["nhơn trạch", "cát lái", "cái mép", "hiệp phước", "vict", "sóng thần", "mỹ phước", "ngoại quan", "phú hữu", "bến lức", "đức hòa", "củ chi", "daklak", "đắk lắk", "biên hoà", "biên hòa", "tbs", "mộc bài"]
                                    
                                    for _, r_tc in df_find_tc.iterrows():
                                        tc_id = int(r_tc['id'])
                                        ten_tc = str(r_tc['ten_tieu_chi']).lower()
                                        
                                        # 1. KIỂM TRA ĐỊA DANH (Nếu tên tiêu chí có địa danh mà lộ trình thực tế không có -> Bỏ qua)
                                        is_sai_tuyen = False
                                        for dd in ds_dia_danh:
                                            if (dd in ten_tc) and (dd not in lo_trinh_hien_tai_lower):
                                                is_sai_tuyen = True
                                                break
                                        
                                        if is_sai_tuyen: 
                                            continue 
                                        
                                        # 2. KIỂM TRA TÍNH CHẤT HÀNG VỀ (2 CHIỀU) / KHÔNG HÀNG VỀ (1 CHIỀU)
                                        phu_dinh_kws = ["không nhận", "khong nhan", "không có", "khong co", "1 chiều", "1 chieu", "một chiều", "mot chieu"]
                                        is_tieu_chi_khong_hang_ve = any(kw in ten_tc for kw in phu_dinh_kws)
                                        
                                        khang_dinh_kws = ["có nhận", "co nhan", "hàng về", "hang ve", "2 chiều", "2 chieu", "hai chiều", "hai chieu", "nhận về", "nhan ve"]
                                        is_tieu_chi_hang_ve = any(kw in ten_tc for kw in khang_dinh_kws) and not is_tieu_chi_khong_hang_ve
                                        
                                        if is_hang_ve_ui:
                                            # Nếu có tick hàng về -> Dùng tiêu chí có hàng về (hoặc tiêu chí không có ràng buộc 1/2 chiều)
                                            if is_tieu_chi_hang_ve or (not is_tieu_chi_hang_ve and not is_tieu_chi_khong_hang_ve):
                                                auto_tc_ids.append(tc_id)
                                        else:
                                            # Nếu KHÔNG tick hàng về -> Dùng tiêu chí không hàng về (hoặc tiêu chí không có ràng buộc)
                                            if is_tieu_chi_khong_hang_ve or (not is_tieu_chi_hang_ve and not is_tieu_chi_khong_hang_ve):
                                                auto_tc_ids.append(tc_id)
                    except Exception: pass

                    df_tc = db.execute_query("SELECT id, ten_tieu_chi FROM dm_tieu_chi_phu_cap")
                    if isinstance(df_tc, pd.DataFrame) and not df_tc.empty:
                        tc_cols = st.columns(2)
                        for i, r_tc in df_tc.iterrows():
                            tc_id = int(r_tc['id'])
                            is_checked = tc_id in auto_tc_ids # Tự động tick nếu khớp cự ly
                            if tc_cols[i % 2].checkbox(r_tc['ten_tieu_chi'].upper(), value=is_checked, key=f"tc_{cd_id}_{tc_id}"):
                                selected_tc_ids.append(tc_id)
                    st.divider()

                st.markdown("##### 🧾 4. Quyết toán Phí thủ công & Ghi chú")

                
                col3_1, col3_2, col3_3 = st.columns(3)
                num_hq = col3_1.text_input("Phí Hải Quan/Bến bãi (Nhập tay)", value=f"{float(row_sel['phi_hai_quan'] or 0):,.0f}")
                num_bx = col3_2.text_input("Phí Bốc Xếp (Nhập tay)", value=f"{float(row_sel['phi_boc_xep'] or 0):,.0f}")
                num_k  = col3_3.text_input("Phí Khác (Nhập tay)", value=f"{float(row_sel['phi_khac'] or 0):,.0f}")
                
                gc_hien_thi = "" if pd.isna(row_sel['ghi_chu_quyet_toan']) else str(row_sel['ghi_chu_quyet_toan'])
                edit_gc = st.text_input("Ghi chú quyết toán", value=gc_hien_thi, placeholder="Nhập thêm ghi chú nếu cần...")
                
                st.markdown("##### 🛡️ Xác nhận thao tác")
                xac_nhan_chot = st.checkbox("⚠️ TÔI XÁC NHẬN SỐ LIỆU LÀ HỢP LÝ VÀ ĐỒNG Ý CHỐT SỔ CHUYẾN ĐI.")
                
                b1, b2= st.columns(2)
                #submit_luu  = b1.form_submit_button("💾 LƯU CẬP NHẬT TẠM", type="secondary")
                submit_chot = b1.form_submit_button("🏁 CHỐT SỔ CHUYẾN ĐI", type="primary")
                submit_xoa  = b2.form_submit_button("🗑️ XÓA CHUYẾN ĐI")

                if  submit_chot:
                    try:
                        doanh_thu_val = clean_money_val(doanh_thu_input)
                        phi_khac_nhap_tay = clean_money_val(num_k)
                        phi_bx_nhap_tay = clean_money_val(num_bx)
                        phi_hq_nhap_tay = clean_money_val(num_hq)
                        
                        # 🚀 SỬA LỖI: Ưu tiên lấy Khối lượng (KG) Khách book làm mốc so sánh
                        booked_kg = float(row_sel.get('khoi_luong_kg', 0.0) or 0.0)
                        tai_trong_so_sanh_tan = (booked_kg / 1000.0) if booked_kg > 0 else 0.0
                        
                        # Fallback (chỉ kích hoạt nếu Kế toán lúc Book quên nhập Khối lượng)
                        if tai_trong_so_sanh_tan <= 0:
                            raw_tt = float(row_sel.get('tai_trong', 0.0) or 0.0)
                            tai_trong_so_sanh_tan = (raw_tt / 1000.0) if raw_tt >= 50 else raw_tt
                        
                        # [Đoạn ngay_chd, facts_dict... giữ nguyên]
                        
                        # 🚀 LẤY NGÀY CHUYẾN ĐI ĐỂ KIỂM TRA CHỦ NHẬT
                        ngay_chd = row_sel['ngay_chuyen_di']
                        is_chu_nhat = False
                        if pd.notna(ngay_chd):
                            try:
                                if hasattr(ngay_chd, 'weekday'): is_chu_nhat = (ngay_chd.weekday() == 6)
                                else: is_chu_nhat = (pd.to_datetime(ngay_chd).weekday() == 6)
                            except: pass
                        
                        facts_dict = {
                            'so_km_phat_sinh': f_km,
                            'so_diem_giao_them': f_diem,
                            'so_ngay_neo_xe': f_neo_xe,
                            'so_ngay_neo_cont': f_neo_cont,
                            'is_huy_chuyen': f_huy,
                            'is_boc_xep': f_boc,
                            'is_ve_khuya': bool(row_sel['is_ve_khuya']),
                            'is_overload_cont': f_overload_cont,
                            'cang_nang_ha': f_cang,
                            'chieu_cont': 'nhap' if chieu_cont_ui == "Nhập" else ('xuat' if chieu_cont_ui == "Xuất" else ''),
                            'is_lay_seal_som': f_seal,
                            'is_giao_khac_khu': f_khac_khu,
                            'is_cont_rong': (f_cont_rong != "Không"),
                            'is_cont_rong_trai_tuyen': (f_cont_rong == "Trái tuyến (Lấy/Hạ)"),
                            'loai_cont_rong_text': f_cont_rong,
                            'is_lam_hang_cang': f_lam_hang_cang,
                            'is_hang_tra_ve': is_hang_ve_ui,
                            'is_chu_nhat': is_chu_nhat
                        }
                        
                        tong_phi_ai, chuoi_ghi_chu_ai = rule_engine_calc(kh_id_qt, tai_trong_so_sanh_tan, doanh_thu_val, facts_dict, db)
                        # --- BỔ SUNG: TÍNH TỔNG PHỤ CẤP TÀI XẾ ---
                        tien_phu_cap_tx, chuoi_phu_cap_tx = tinh_phu_cap_tai_xe(db, row_sel.get('xe_id'), selected_tc_ids)
                        tien_them_final = float(row_sel.get('tien_them', 0.0) or 0.0) + tien_phu_cap_tx

                        phi_khac_final = phi_khac_nhap_tay + tong_phi_ai
                        gc_final = str(edit_gc).strip()
                        if chuoi_ghi_chu_ai:
                            gc_final += f" [AI Tự động: {', '.join(chuoi_ghi_chu_ai)}]"
                        if chuoi_phu_cap_tx:
                            # Nối cả tổng tiền và chi tiết phụ cấp vào ghi chú
                            gc_final += f" [Phụ cấp TX: +{tien_phu_cap_tx:,.0f}đ ({chuoi_phu_cap_tx})]"

                        data_dict_thu_cong = {
                            'ten_khach_hang': edit_cong_ty,
                            'doanh_thu': doanh_thu_val, 
                            'chi_phi_thue_ngoai': clean_money_val(chi_phi_ngoai_input),
                            'hinh_thuc_thanh_toan_ngoai': hinh_thuc_thanh_toan_ngoai,
                            'phi_hai_quan': phi_hq_nhap_tay,
                            'phi_boc_xep': phi_bx_nhap_tay,
                            'phi_khac': phi_khac_final,
                            'tien_them': tien_them_final, # Đã tự động cộng tiền phụ cấp
                            'ghi_chu_quyet_toan': gc_final
                        }

                        if submit_chot and not xac_nhan_chot:
                            st.error("✋ HỆ THỐNG ĐÃ CHẶN: Vui lòng tick vào ô 'Tôi xác nhận...' trước khi chốt sổ!")
                        else:
                            # --- AI TỰ ĐỘNG LƯU BẢNG GIÁ NẾU ĐƯỢC CHỌN ---
                            if is_save_to_rc and doanh_thu_val > 0:
                                ddi_save = st.session_state.get(f"ddi_{cd_id}", "")
                                dden_save = st.session_state.get(f"dden_{cd_id}", "")
                                qc_moi = f"{tt_xe_tan}T"
                                
                                sql_insert_rc = """
                                    INSERT INTO rate_cards (khach_hang_id, diem_di, diem_den, phan_loai_phuong_tien, loai_xe_quy_cach, don_gia_cuoc, gia_chuyen_tiep_noi, is_hang_tra_ve) 
                                    VALUES (%s, %s, %s, %s, %s, %s, 0, %s)
                                """
                                try:
                                    flag_luu_db = 1 if is_hang_ve_ui else 0
                                    db.execute_non_query(sql_insert_rc, (kh_id_qt, ddi_save, dden_save, 'Hang_Le', qc_moi, doanh_thu_val, flag_luu_db))
                                    st.toast(f"✅ Đã tự động thêm lộ trình mới cho mức tải {qc_moi} vào Bảng giá!")
                                except Exception as e:
                                    st.error(f"Lỗi khi lưu Bảng giá: {e}")
                                        
                            trang_thai_luu = 'Hoan_Thanh' if submit_chot else row_sel['trang_thai_chuyen']
                            is_ok, msg = settle_trip_transaction(db.pool, data_dict_thu_cong, trang_thai_luu, cd_id)
                            if is_ok:
                                if dt_state_key in st.session_state: del st.session_state[dt_state_key]
                                st.session_state["reset_chuyen_form"] += 1
                                st.success(f"🎉 THÀNH CÔNG! AI đã tính thêm **{tong_phi_ai:,.0f} VNĐ** phụ phí vào Phí Khác!")
                                time.sleep(2)
                                st.rerun()
                            else: st.error(f"❌ Lỗi Database: {msg}")
                    except Exception as ex: st.error(f"❌ Lỗi xử lý dữ liệu: {ex}")

                if submit_xoa:
                    success, msg = delete_trip_safe(db.pool, cd_id)
                    if success:
                        if dt_state_key in st.session_state: del st.session_state[dt_state_key]
                        st.session_state["reset_chuyen_form"] += 1
                        st.success("✅ Đã xóa chuyến đi thành công!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ Lỗi xóa chuyến: {msg}")
        else:
            st.info("🎉 Tuyệt vời! Hiện tại không có chuyến đi nào đang chờ quyết toán.")
    vung_thao_tac_quyet_toan_chuyen_di()        

# ==========================================
# TAB 2: SỬA DỮ LIỆU ĐÃ QUYẾT TOÁN (HỖ TRỢ XE NGOÀI)
# ==========================================
with tab2:
    tao_tieu_de_kem_nut_refresh("📋 Sửa dữ liệu chuyến đi đã quyết toán", "ref_tab4")

    @st.fragment
    def vung_thao_tac_sua_quyet_toan():
        if "reset_sqt" not in st.session_state:
            st.session_state["reset_sqt"] = 0
        if "sqt_searched" not in st.session_state:
            st.session_state["sqt_searched"] = False
            
        st.info("Tính năng này dùng để điều chỉnh chi phí, công lương cho các chuyến đã chốt. Dữ liệu chỉ được tải khi bạn bấm 'Tìm Kiếm'.")
        
        col_filter1, col_filter2, col_filter3 = st.columns(3)
        
        with col_filter1:
            ngay_tim_kiem = st.date_input("Chọn ngày chạy", value=datetime.date.today(), key="sqt_date")
            
        with col_filter2:
            loai_tim_kiem = st.radio("Tìm kiếm theo:", ["Theo Xe Nội Bộ", "Theo Tài xế", "Tất cả các chuyến trong ngày"], horizontal=True, key="sqt_type")
            
        with col_filter3:
            if loai_tim_kiem == "Theo Xe Nội Bộ":
                df_xe = db.execute_query("SELECT id, bien_so_xe FROM xe WHERE trang_thai = 'Dang_Hoat_Dong'")
                if isinstance(df_xe, pd.DataFrame) and not df_xe.empty:
                    dict_xe = dict(zip(df_xe['id'], df_xe['bien_so_xe']))
                    doi_tuong_id = st.selectbox("Chọn Xe", options=list(dict_xe.keys()), format_func=lambda x: dict_xe[x], key="sqt_obj_xe")
                else:
                    st.warning("Không có dữ liệu xe"); doi_tuong_id = None
            elif loai_tim_kiem == "Theo Tài xế":
                df_tx = db.execute_query("SELECT id, ho_ten FROM nhan_vien WHERE trang_thai = 'Dang_Lam_Viec'")
                if isinstance(df_tx, pd.DataFrame) and not df_tx.empty:
                    dict_tx = dict(zip(df_tx['id'], df_tx['ho_ten']))
                    doi_tuong_id = st.selectbox("Chọn Tài xế", options=list(dict_tx.keys()), format_func=lambda x: dict_tx[x], key="sqt_obj_tx")
                else:
                    st.warning("Không có dữ liệu tài xế"); doi_tuong_id = None
            else:
                doi_tuong_id = "ALL"

        if st.button("🔍 Tìm Kiếm Dữ Liệu", type="primary", use_container_width=True):
            st.session_state["sqt_searched"] = True
            st.session_state["sqt_date_val"] = ngay_tim_kiem
            st.session_state["sqt_type_val"] = loai_tim_kiem
            st.session_state["sqt_obj_val"] = doi_tuong_id
            
            select_key = f"chon_chuyen_sua_{st.session_state['reset_sqt']}"
            if select_key in st.session_state:
                del st.session_state[select_key]

        st.divider()

        if st.session_state.get("sqt_searched") and st.session_state.get("sqt_obj_val") is not None:
            
            ngay_str = st.session_state["sqt_date_val"].strftime('%Y-%m-%d')
            saved_type = st.session_state["sqt_type_val"]
            saved_obj = st.session_state["sqt_obj_val"]
            
            base_query = """
                SELECT cd.id, cd.dia_diem_giao_nhan, cd.ten_khach_hang, cd.doanh_thu, cd.khoi_luong_kg,
                    cd.cong_chuyen, cd.is_thue_ngoai, cd.chi_phi_thue_ngoai, cd.hinh_thuc_thanh_toan_ngoai,
                    cd.tien_them, cd.phi_hai_quan, cd.phi_boc_xep, cd.phi_khac, cd.ghi_chu_quyet_toan
                FROM chuyen_di cd
            """
            
            if saved_type == "Theo Xe Nội Bộ":
                sql_find_trips = base_query + " WHERE cd.ngay_chuyen_di = %s AND cd.xe_id = %s AND cd.trang_thai_chuyen = 'Hoan_Thanh'"
                df_trips = db.execute_query(sql_find_trips, (ngay_str, saved_obj))
            elif saved_type == "Theo Tài xế":
                sql_find_trips = base_query + """ JOIN chuyen_di_tai_xe ctx ON cd.id = ctx.chuyen_di_id
                                                WHERE cd.ngay_chuyen_di = %s AND ctx.tai_xe_id = %s AND cd.trang_thai_chuyen = 'Hoan_Thanh' """
                df_trips = db.execute_query(sql_find_trips, (ngay_str, saved_obj))
            else:
                sql_find_trips = base_query + " WHERE cd.ngay_chuyen_di = %s AND cd.trang_thai_chuyen = 'Hoan_Thanh'"
                df_trips = db.execute_query(sql_find_trips, (ngay_str,))

            if isinstance(df_trips, pd.DataFrame) and not df_trips.empty:
                dict_trips = {}
                for _, row in df_trips.iterrows():
                    tag = "[NGOÀI]" if row['is_thue_ngoai'] == 1 else "[NỘI BỘ]"
                    label = f"Mã: {row['id']} {tag} | Khách: {row['ten_khach_hang']} | Lộ trình: {row['dia_diem_giao_nhan']}"
                    dict_trips[row['id']] = label
                    
                chuyen_can_sua = st.selectbox(
                    "📌 Chọn chuyến cần sửa quyết toán:", 
                    options=list(dict_trips.keys()), 
                    format_func=lambda x: dict_trips[x],
                    key=f"chon_chuyen_sua_{st.session_state['reset_sqt']}",
                    index=None, 
                    placeholder="-- Vui lòng chọn 1 chuyến đi --"
                )
                
                if chuyen_can_sua is not None:
                    df_filtered = df_trips[df_trips['id'].astype(str) == str(chuyen_can_sua)]
                    
                    if not df_filtered.empty:
                        trip_info = df_filtered.iloc[0]
                        is_thue_ngoai = bool(trip_info['is_thue_ngoai'])
                        
                        with st.form("form_sua_quyet_toan", clear_on_submit=True):
                            st.markdown(f"**Đang sửa dữ liệu chuyến {chuyen_can_sua} {'(THUÊ XE NGOÀI)' if is_thue_ngoai else '(XE NỘI BỘ)'}**")
                            
                            def format_money(val):
                                if pd.isna(val) or val == "": return "0"
                                try: return f"{int(float(val)):,}" 
                                except: return "0"
                                    
                            def parse_money(val_str):
                                clean_str = str(val_str).replace(",", "").replace(".", "").replace(" ", "")
                                try: return float(clean_str)
                                except: return 0.0 

                            c1, c2, c3, c4 = st.columns(4)
                            
                            edit_khoi_kuong = c1.number_input(
                                "Trọng tải Kg", 
                                value=0.0 if pd.isna(trip_info['khoi_luong_kg']) else float(trip_info['khoi_luong_kg']), 
                                step=1.0, key=f"kholuong_{chuyen_can_sua}"
                            )
                            edit_doanh_thu_str = c2.text_input(
                                "Doanh thu chuyến (VNĐ)", 
                                value=format_money(trip_info['doanh_thu']), key=f"doanhthu_{chuyen_can_sua}"
                            )
                            edit_tien_them_str = c3.text_input(
                                "Tiền phụ cấp/thưởng thêm", 
                                value=format_money(trip_info['tien_them']), key=f"them_{chuyen_can_sua}"
                            )
                            
                            if not is_thue_ngoai:
                                edit_cong_str = c4.text_input("Công tài xế (Lương)*", value=format_money(trip_info['cong_chuyen']))
                                
                                #c5, c6 = st.columns(2)
                                #edit_so_lit_xang_str = c5.text_input("Số lít xăng", value=format_money(trip_info['so_lit_xang']))
                                #edit_tien_xang_str = c6.text_input("Tiền xăng", value=format_money(trip_info['tien_xang']))
                                
                                edit_chi_phi_ngoai = "0"
                                edit_thanh_toan_ngoai = "Cong_No"
                            else:
                                edit_chi_phi_ngoai = c4.text_input("Chi phí thuê ngoài (VNĐ)*", value=format_money(trip_info['chi_phi_thue_ngoai']))
                                
                                tt_opts = ["Cong_No", "Tien_Mat"]
                                def_tt_idx = tt_opts.index(trip_info['hinh_thuc_thanh_toan_ngoai']) if pd.notna(trip_info['hinh_thuc_thanh_toan_ngoai']) and trip_info['hinh_thuc_thanh_toan_ngoai'] in tt_opts else 0
                                edit_thanh_toan_ngoai = st.selectbox("Thanh toán thuê xe", tt_opts, index=def_tt_idx, format_func=lambda x: "Công nợ" if x=="Cong_No" else "Tiền mặt")
                                
                                edit_cong_str = "0"

                            c7, c8, c9 = st.columns(3)
                            edit_hai_quan_str = c7.text_input("Phí hải quan", value=format_money(trip_info['phi_hai_quan']))
                            edit_boc_xep_str = c8.text_input("Phí bốc xếp", value=format_money(trip_info['phi_boc_xep']))
                            edit_khac_str = c9.text_input("Phí khác (Luật, cầu đường...)", value=format_money(trip_info['phi_khac']))
                            
                            edit_ghi_chu = st.text_input(
                                "Ghi chú quyết toán (Lý do sửa)", 
                                value="" if pd.isna(trip_info['ghi_chu_quyet_toan']) else str(trip_info['ghi_chu_quyet_toan'])
                            )
                            
                            if st.form_submit_button("💾 Lưu sửa đổi quyết toán", type="primary"):
                                data_update = {
                                    'khoi_luong_kg': edit_khoi_kuong,
                                    'doanh_thu': parse_money(edit_doanh_thu_str),
                                    'tien_them': parse_money(edit_tien_them_str),
                                    'cong_chuyen': parse_money(edit_cong_str),
                                    #'so_lit_xang': parse_money(edit_so_lit_xang_str),
                                    #'tien_xang': parse_money(edit_tien_xang_str),
                                    'chi_phi_thue_ngoai': parse_money(edit_chi_phi_ngoai),
                                    'hinh_thuc_thanh_toan_ngoai': edit_thanh_toan_ngoai,
                                    'phi_hai_quan': parse_money(edit_hai_quan_str),
                                    'phi_boc_xep': parse_money(edit_boc_xep_str),
                                    'phi_khac': parse_money(edit_khac_str),
                                    'ghi_chu_quyet_toan': edit_ghi_chu
                                }
                                
                                is_ok, msg = update_trip_transaction(db.pool, data_chuyen_di=data_update, trang_thai_enum='Hoan_Thanh', chuyen_di_id=chuyen_can_sua)
                                
                                if is_ok:
                                    st.success(f"✅ Đã cập nhật thành công quyết toán cho chuyến {chuyen_can_sua}!")
                                    st.session_state["reset_sqt"] += 1
                                    time.sleep(1.2) 
                                    st.rerun()
                                else:
                                    st.error(f"❌ Lỗi khi lưu: {msg}")
            else:
                st.info("📭 Không tìm thấy chuyến đi nào đã quyết toán khớp với điều kiện tìm kiếm của bạn.")
    vung_thao_tac_sua_quyet_toan()

# ==========================================
# TAB 3: 🤖 TỰ ĐỘNG ĐIỀU XE & EXCEL TOOLS
# ==========================================
with tab3:
    @st.fragment
    def vung_thao_tac_quyet_toan_auto():
        
        st.markdown("##### 📋 Danh sách chuyến đi chờ Quyết toán (Hoặc rỗng doanh thu)")
        
        # Truy vấn các chuyến chưa quyết toán, hoặc đã hoàn thành nhưng doanh thu = 0
        sql_pending = """
            SELECT cd.id AS 'MA_CHUYEN', cd.ngay_chuyen_di AS 'NGAY_CHAY', cd.ten_khach_hang AS 'KHACH_HANG',
                COALESCE(x.bien_so_xe, cd.bien_so_xe_ngoai) AS 'BIEN_SO',
                COALESCE(nv.ho_ten, cd.tai_xe_ngoai_ten) AS 'TAI_XE',
                cd.dia_diem_giao_nhan AS 'LO_TRINH',
                cd.doanh_thu AS 'DOANH_THU_HIEN_TAI',
                cd.trang_thai_chuyen AS 'TRANG_THAI'
            FROM chuyen_di cd
            LEFT JOIN xe x ON cd.xe_id = x.id
            LEFT JOIN chuyen_di_tai_xe ctx ON cd.id = ctx.chuyen_di_id AND ctx.loai_tai_xe = 'Tai_Chinh'
            LEFT JOIN nhan_vien nv ON ctx.tai_xe_id = nv.id
            WHERE cd.trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di', 'Quyet_Toan')
               OR (cd.trang_thai_chuyen = 'Hoan_Thanh' AND (cd.doanh_thu IS NULL OR cd.doanh_thu <= 0))
            ORDER BY cd.ngay_chuyen_di ASC
        """
        df_pending = db.execute_query(sql_pending)
        
        if isinstance(df_pending, pd.DataFrame) and not df_pending.empty:
            df_display = df_pending.copy()
            df_display['NGAY_CHAY'] = pd.to_datetime(df_display['NGAY_CHAY']).dt.strftime('%d/%m/%Y')
            df_display['DOANH_THU_HIEN_TAI'] = df_display['DOANH_THU_HIEN_TAI'].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "0")
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            template_data = []
            for _, row in df_pending.iterrows():
                template_data.append({
                    "MA_CHUYEN": row['MA_CHUYEN'],
                    "LỘ TRÌNH (Tham khảo)": row['LO_TRINH'],
                    "TÀI XẾ (Tham khảo)": row['TAI_XE'],
                    "BIỂN SỐ (Tham khảo)": row['BIEN_SO'],
                    "DOANH_THU_CHUYEN": row['DOANH_THU_HIEN_TAI'] if pd.notnull(row['DOANH_THU_HIEN_TAI']) and row['DOANH_THU_HIEN_TAI'] > 0 else 0,
                    "TIEN_CONG_TAI_XE": 0,
                    "CHI_PHI_THUE_NGOAI": 0,
                    "HINH_THUC_THANH_TOAN_NGOAI": "Cong_No",
                    "PHI_HAI_QUAN": 0,
                    "PHI_BOC_XEP": 0,
                    "PHI_KHAC": 0,
                    "SO_KM_PHAT_SINH": 0,
                    "SO_DIEM_GIAO_THEM": 0,
                    "SO_NGAY_NEO_XE": 0,
                    "SO_NGAY_NEO_XE_NHA_MAY": 0,
                    "SO_NGAY_NEO_CONT": 0,
                    "IS_HUY_CHUYEN": 0,
                    "IS_BOC_XEP": 0,
                    "IS_VE_KHUYA": 0,
                    "IS_OVERLOAD_CONT": 0,
                    "CANG_NANG_HA": "",
                    "LOAI_HANG_HOA": "Thường",
                    "LOAI_CONT": "Thường",
                    "CHIEU_CONT": "Không",
                    "LAY_SEAL_SOM": 0,
                    "GIAO_KHAC_KHU": 0,
                    "CONT_RONG": "Không",
                    "IS_HANG_VE": 0,
                    "DS_PHU_CAP_TAI_XE": "",
                    "GHI_CHU": ""
                })
            df_tpl_close = pd.DataFrame(template_data)
        else:
            st.info("Hiện không có chuyến đi nào đang chờ quyết toán hoặc bị rỗng doanh thu.")
            df_tpl_close = pd.DataFrame([{
                "MA_CHUYEN": 1001, 
                "LỘ TRÌNH (Tham khảo)": "Bình Dương -> Cát Lái",
                "TÀI XẾ (Tham khảo)": "Nguyễn Văn A",
                "BIỂN SỐ (Tham khảo)": "51C-123.45",
                "DOANH_THU_CHUYEN": 2000000, 
                "TIEN_CONG_TAI_XE": 300000, 
                "CHI_PHI_THUE_NGOAI": 0,
                "HINH_THUC_THANH_TOAN_NGOAI": "Cong_No",
                "PHI_HAI_QUAN": 0,
                "PHI_BOC_XEP": 100000,
                "PHI_KHAC": 0,
                "SO_KM_PHAT_SINH": 15,
                "SO_DIEM_GIAO_THEM": 1,
                "SO_NGAY_NEO_XE": 0,
                "SO_NGAY_NEO_XE_NHA_MAY": 0,
                "SO_NGAY_NEO_CONT": 0,
                "IS_HUY_CHUYEN": 0,
                "IS_BOC_XEP": 0,
                "IS_VE_KHUYA": 0,
                "IS_OVERLOAD_CONT": 0,
                "CANG_NANG_HA": "Dong_Nai",
                "LOAI_HANG_HOA": "Thường",
                "LOAI_CONT": "Thường",
                "CHIEU_CONT": "Không",
                "LAY_SEAL_SOM": 0,
                "GIAO_KHAC_KHU": 0,
                "CONT_RONG": "Không",
                "IS_HANG_VE": 0,
                "DS_PHU_CAP_TAI_XE": "1, 3 (Hoặc gõ chữ: Bốc xếp, Về khuya)",
                "GHI_CHU": "Chốt cuối tháng"
            }])
        
        st.divider()
        st.markdown("##### 📥 1. Tải File Mẫu (Đã tự động nạp mã chuyến và thông tin tham khảo)")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            # --- XUẤT 2 SHEET ĐỂ HỖ TRỢ KẾ TOÁN ---
            df_dm_pc = db.execute_query("SELECT id, ten_tieu_chi FROM dm_tieu_chi_phu_cap")
            
            buffer_close = io.BytesIO()
            with pd.ExcelWriter(buffer_close, engine='xlsxwriter') as writer: 
                df_tpl_close.to_excel(writer, index=False, sheet_name="MAU_QUYET_TOAN")
                if isinstance(df_dm_pc, pd.DataFrame) and not df_dm_pc.empty:
                    df_dm_pc.columns = ["ID_PHU_CAP", "TEN_TIEU_CHI_COPPY_SANG_SHEET_1"]
                    df_dm_pc.to_excel(writer, index=False, sheet_name="TỪ ĐIỂN PHỤ CẤP")
                
            st.download_button(
                label="⬇️ Tải mẫu Excel Quyết toán hàng loạt", 
                data=buffer_close.getvalue(), 
                file_name=f"Mau_Quyet_Toan_Tudong_{datetime.date.today().strftime('%d_%m_%Y')}.xlsx",
                use_container_width=True
            )
        
        with st.form("form_mass_close"):
            file_close = st.file_uploader("Chọn file Excel Quyết toán (Đuôi .xlsx, .csv)", type=["xlsx", "xls", "csv"])
            submit_close = st.form_submit_button("🏁 Khóa sổ & Chốt chuyến hàng loạt", type="primary")
            
            if submit_close:
                if not file_close:
                    st.warning("⚠️ Bạn chưa tải file Excel lên!")
                else:
                    with st.spinner("⏳ Đang quét Bảng giá & Phụ phí theo Khối Lượng Book ban đầu..."):
                        try:
                            if file_close.name.endswith('.csv'):
                                df_close = pd.read_csv(file_close)
                            else:
                                df_close = pd.read_excel(file_close)
                                
                            df_close.columns = [str(c).strip().upper() for c in df_close.columns]
                            
                            closed_count = 0
                            error_list = []
                            
                            import re
                            def parse_excel_money(val):
                                if pd.isna(val) or val == "" or val is None: return 0.0
                                try:
                                    if isinstance(val, (int, float)): return float(val)
                                    clean_str = str(val).replace(",", "").replace(" ", "").strip()
                                    match = re.search(r'[-+]?\d*\.\d+|\d+', clean_str)
                                    if match: return float(match.group())
                                    return 0.0
                                except Exception: return 0.0

                            def parse_excel_bool(val):
                                if pd.isna(val) or val == "" or val is None: return False
                                v_str = str(val).replace(".0", "").strip().lower()
                                return v_str in ['1', 'true', 'yes', 'có', 'x', 'v', 'y']

                            for index, r in df_close.iterrows():
                                raw_cid = r.get('MA_CHUYEN')
                                if pd.isna(raw_cid) or str(raw_cid).strip() == "": 
                                    continue 
                                try:
                                    cid = int(float(raw_cid))
                                except ValueError:
                                    continue
                                    
                                try:
                                    sql_check = """
                                        SELECT trang_thai_chuyen, khach_hang_id, ten_khach_hang, 
                                            doanh_thu, dia_diem_giao_nhan, chi_phi_thue_ngoai, 
                                            hinh_thuc_thanh_toan_ngoai, ghi_chu,
                                            ngay_chuyen_di, khoi_luong_kg, xe_id
                                        FROM chuyen_di 
                                        WHERE id = %s
                                    """
                                    df_check = db.execute_query(sql_check, (cid,))
                                    
                                    if not isinstance(df_check, pd.DataFrame) or df_check.empty:
                                        error_list.append(f"❌ Dòng {index + 2} (Mã {cid}): Không tồn tại chuyến đi.")
                                        continue
                                    
                                    row_db = df_check.iloc[0]
                                    trang_thai = row_db['trang_thai_chuyen']
                                    kh_id = int(row_db.get('khach_hang_id')) if pd.notna(row_db.get('khach_hang_id')) else None
                                    ten_khach_hang_db = str(row_db.get('ten_khach_hang', ''))
                                    
                                    if trang_thai == 'Hoan_Thanh' and float(row_db.get('doanh_thu', 0.0) or 0.0) > 0:
                                        error_list.append(f"⚠️ Dòng {index + 2} (Mã {cid}): Đã khóa sổ và có doanh thu hợp lệ trước đó.")
                                        continue
                                    
                                    booked_kg = float(row_db.get('khoi_luong_kg', 0.0) or 0.0)
                                    tai_trong_so_sanh_tan = booked_kg / 1000.0 if booked_kg > 0 else 0.0

                                    doanh_thu_db = float(row_db.get('doanh_thu', 0.0) or 0.0)
                                    lo_trinh_hien_tai = str(row_db.get('dia_diem_giao_nhan', '')).strip()
                                    
                                    doanh_thu_chuyen = parse_excel_money(r.get('DOANH_THU_CHUYEN'))
                                    if doanh_thu_chuyen == 0: doanh_thu_chuyen = doanh_thu_db
                                        
                                    # ĐỐI CHIẾU RATE CARDS
                                    matched_khoang_cach = 0.0
                                    
                                    is_hang_ve_excel = parse_excel_bool(r.get('IS_HANG_VE'))
                                    
                                    if "➡️" in lo_trinh_hien_tai and kh_id:
                                        try:
                                            parts = lo_trinh_hien_tai.split("➡️")
                                            ddi = parts[0].strip()
                                            dden = parts[1].strip()
                                            
                                            flag_hang_ve = 1 if is_hang_ve_excel else 0
                                            
                                            sql_rc = """
                                                SELECT id, don_gia_cuoc, phan_loai_phuong_tien, loai_xe_quy_cach, khoang_cach 
                                                FROM rate_cards 
                                                WHERE khach_hang_id = %s AND diem_di LIKE %s AND diem_den LIKE %s AND is_hang_tra_ve = %s
                                                ORDER BY id DESC
                                            """
                                            df_rc = db.execute_query(sql_rc, (kh_id, f"%{ddi}%", f"%{dden}%", flag_hang_ve))
                                            
                                            if flag_hang_ve == 0 and (not isinstance(df_rc, pd.DataFrame) or df_rc.empty):
                                                df_rc = db.execute_query(sql_rc, (kh_id, f"%{dden}%", f"%{ddi}%", 0))

                                            if isinstance(df_rc, pd.DataFrame) and not df_rc.empty:
                                                matched_price = 0.0
                                                
                                                loai_hang_excel = str(r.get('LOAI_HANG_HOA', 'Thường')).strip().lower()
                                                loai_cont_excel = str(r.get('LOAI_CONT', 'Thường')).strip().lower()
                                                has_nguy_hiem = 'nguy hiểm' in loai_hang_excel or 'nguy hiem' in loai_hang_excel
                                                has_lanh = 'lạnh' in loai_cont_excel or 'lanh' in loai_cont_excel

                                                for _, rc in df_rc.iterrows():
                                                    pl_pt_gia = str(rc.get('phan_loai_phuong_tien', '')).strip()
                                                    qc_gia = str(rc.get('loai_xe_quy_cach', '')).strip().lower().replace("_", " ")

                                                    req_nguy_hiem = any(x in qc_gia for x in ['nguy hiem', 'nguyhiem'])
                                                    req_lanh = any(x in qc_gia for x in ['lạnh', 'lanh', 'rf'])
                                                    req_thuong = any(x in qc_gia for x in ['thường', 'thuong'])

                                                    is_prop_match = True
                                                    if req_nguy_hiem and not has_nguy_hiem: is_prop_match = False
                                                    if req_lanh and not has_lanh: is_prop_match = False
                                                    if req_thuong and (has_nguy_hiem or has_lanh): is_prop_match = False

                                                    if pl_pt_gia in ['Xe_Tai', 'Hang_Le']:
                                                        nums_in_str = re.findall(r'\d+\.?\d*', qc_gia)
                                                        float_nums = [float(n) for n in nums_in_str]
                                                        is_weight_match = False

                                                        if len(float_nums) == 2:
                                                            if min(float_nums) <= tai_trong_so_sanh_tan <= max(float_nums): is_weight_match = True
                                                        elif len(float_nums) == 1:
                                                            val = float_nums[0]
                                                            if any(op in qc_gia for op in ['<=', 'dưới', 'duoi']) and tai_trong_so_sanh_tan <= val: is_weight_match = True
                                                            elif '<' in qc_gia and tai_trong_so_sanh_tan < val: is_weight_match = True
                                                            elif any(op in qc_gia for op in ['>=', 'trên', 'tren']) and tai_trong_so_sanh_tan >= val: is_weight_match = True
                                                            elif '>' in qc_gia and tai_trong_so_sanh_tan > val: is_weight_match = True
                                                            else:
                                                                if tai_trong_so_sanh_tan == val: is_weight_match = True
                                                        elif len(float_nums) == 0:
                                                            is_weight_match = True

                                                        if is_weight_match and is_prop_match:
                                                            matched_price = float(rc['don_gia_cuoc'])
                                                            matched_khoang_cach = float(rc.get('khoang_cach', 0.0) or 0.0)
                                                            break
                                                
                                                if matched_price > 0  and doanh_thu_chuyen == 0:
                                                    doanh_thu_chuyen = matched_price
                                        except Exception as ex: pass
                                    
                                    if doanh_thu_chuyen == 0:
                                        error_list.append(f"⚠️ Dòng {index + 2} (Mã {cid}): Không dò ra Doanh Thu (Khối lượng book {tai_trong_so_sanh_tan}T không khớp Rate Cards). Phụ phí % bị nhân với 0đ = 0đ!")

                                    is_chu_nhat = False
                                    ngay_chd = row_db.get('ngay_chuyen_di')
                                    if pd.notna(ngay_chd):
                                        try:
                                            is_chu_nhat = (pd.to_datetime(ngay_chd).weekday() == 6)
                                        except: pass

                                    chieu_cont_excel = str(r.get('CHIEU_CONT', '')).strip().lower()
                                    chieu_val = 'nhap' if 'nhập' in chieu_cont_excel or 'nhap' in chieu_cont_excel else ('xuat' if 'xuất' in chieu_cont_excel or 'xuat' in chieu_cont_excel else '')
                                    cont_rong_excel = str(r.get('CONT_RONG', 'Không')).strip()
                                    is_hang_ve_excel = parse_excel_bool(r.get('IS_HANG_VE'))
                                    facts = {
                                        'so_km_phat_sinh': parse_excel_money(r.get('SO_KM_PHAT_SINH')),
                                        'so_diem_giao_them': parse_excel_money(r.get('SO_DIEM_GIAO_THEM')),
                                        'so_ngay_neo_xe': parse_excel_money(r.get('SO_NGAY_NEO_XE')),
                                        'so_ngay_neo_xe_nha_may': parse_excel_money(r.get('SO_NGAY_NEO_XE_NHA_MAY')), 
                                        'so_ngay_neo_cont': parse_excel_money(r.get('SO_NGAY_NEO_CONT')),
                                        'is_huy_chuyen': parse_excel_bool(r.get('IS_HUY_CHUYEN')),
                                        'is_boc_xep': parse_excel_bool(r.get('IS_BOC_XEP')),
                                        'is_ve_khuya': parse_excel_bool(r.get('IS_VE_KHUYA')),
                                        'is_overload_cont': parse_excel_bool(r.get('IS_OVERLOAD_CONT')),
                                        'cang_nang_ha': str(r.get('CANG_NANG_HA', '')).strip() if pd.notna(r.get('CANG_NANG_HA')) else "",
                                        'chieu_cont': chieu_val,
                                        'is_lay_seal_som': parse_excel_bool(r.get('LAY_SEAL_SOM')),
                                        'is_giao_khac_khu': parse_excel_bool(r.get('GIAO_KHAC_KHU')),
                                        'is_cont_rong': (cont_rong_excel.lower() not in ['không', 'khong', '0', 'nan', '']),
                                        'is_cont_rong_trai_tuyen': ('trái tuyến' in cont_rong_excel.lower() or 'trai tuyen' in cont_rong_excel.lower()),
                                        'loai_cont_rong_text': cont_rong_excel,
                                        'is_hang_tra_ve': is_hang_ve_excel,
                                        'is_chu_nhat': is_chu_nhat
                                    }
                                    
                                    tong_phi_ai, chuoi_ghi_chu_ai = rule_engine_calc(kh_id, tai_trong_so_sanh_tan, doanh_thu_chuyen, facts, db)
                                    
                                    df_tc_db = db.execute_query("SELECT id, ten_tieu_chi FROM dm_tieu_chi_phu_cap")
                                    tc_dict = {}
                                    if isinstance(df_tc_db, pd.DataFrame) and not df_tc_db.empty:
                                        for _, r_tc in df_tc_db.iterrows():
                                            tc_dict[str(r_tc['id'])] = int(r_tc['id'])
                                            tc_dict[str(r_tc['ten_tieu_chi']).strip().lower()] = int(r_tc['id'])

                                    ds_phu_cap_str = str(r.get('DS_PHU_CAP_TAI_XE', '')).strip()
                                    selected_tc_ids_excel = []
                                    if ds_phu_cap_str and ds_phu_cap_str.lower() not in ['nan', '']:
                                        items = [x.strip() for x in ds_phu_cap_str.split(',')]
                                        for item in items:
                                            if item in tc_dict:
                                                selected_tc_ids_excel.append(tc_dict[item])
                                            else:
                                                item_lower = item.lower()
                                                for k_name, v_id in tc_dict.items():
                                                    if not k_name.isdigit() and item_lower in k_name:
                                                        selected_tc_ids_excel.append(v_id)
                                                        break
                                                        
                                    if matched_khoang_cach > 0:
                                        try:
                                            sql_find_tc = "SELECT id, ten_tieu_chi FROM dm_tieu_chi_phu_cap WHERE %s >= km_min AND %s <= km_max"
                                            df_find_tc = db.execute_query(sql_find_tc, (matched_khoang_cach, matched_khoang_cach))
                                            
                                            if isinstance(df_find_tc, pd.DataFrame) and not df_find_tc.empty:
                                                lo_trinh_lower = lo_trinh_hien_tai.lower()
                                                ds_dia_danh = ["nhơn trạch", "cát lái", "cái mép", "hiệp phước", "vict", "sóng thần", "mỹ phước", "ngoại quan", "phú hữu", "bến lức", "đức hòa", "củ chi", "daklak", "đắk lắk"]
                                                
                                                for _, r_tc in df_find_tc.iterrows():
                                                    tc_id = int(r_tc['id'])
                                                    ten_tc = str(r_tc['ten_tieu_chi']).lower()
                                                    
                                                    is_sai_tuyen = False
                                                    for dd in ds_dia_danh:
                                                        if (dd in ten_tc) and (dd not in lo_trinh_lower):
                                                            is_sai_tuyen = True
                                                            break
                                                    
                                                    if is_sai_tuyen: 
                                                        continue 
                                                    
                                                    phu_dinh_kws = ["không nhận hàng về", "khong nhan hang ve", "không có hàng về", "khong co hang ve", "không hàng về", "khong hang ve", "1 chiều", "1 chieu", "một chiều", "mot chieu", "giao đi", "giao di"]
                                                    is_tieu_chi_khong_hang_ve = any(kw in ten_tc for kw in phu_dinh_kws)
                                                    
                                                    khang_dinh_kws = ["hàng về", "hang ve", "2 chiều", "2 chieu", "hai chiều", "hai chieu", "nhận về", "nhan ve"]
                                                    is_tieu_chi_hang_ve = any(kw in ten_tc for kw in khang_dinh_kws) and not is_tieu_chi_khong_hang_ve
                                                    
                                                    if is_hang_ve_excel: 
                                                        if is_tieu_chi_hang_ve or (not is_tieu_chi_hang_ve and not is_tieu_chi_khong_hang_ve):
                                                            selected_tc_ids_excel.append(tc_id)
                                                    else: 
                                                        if is_tieu_chi_khong_hang_ve or (not is_tieu_chi_hang_ve and not is_tieu_chi_khong_hang_ve):
                                                            selected_tc_ids_excel.append(tc_id)
                                        except: pass
                                        
                                    selected_tc_ids_excel = list(set(selected_tc_ids_excel)) 

                                    tien_phu_cap_tx, chuoi_phu_cap_tx = tinh_phu_cap_tai_xe(db, row_db.get('xe_id'), selected_tc_ids_excel)
                                    tien_them_final = float(row_db.get('tien_them', 0.0) or 0.0) + tien_phu_cap_tx
                                    
                                    phi_khac_excel = parse_excel_money(r.get('PHI_KHAC'))
                                    tong_phi_khac_final = phi_khac_excel + tong_phi_ai
                                    
                                    ghi_chu_goc = str(r.get('GHI_CHU', '')).strip() if pd.notna(r.get('GHI_CHU')) else ""
                                    if ghi_chu_goc.lower() == 'nan': ghi_chu_goc = ""
                                    if chuoi_ghi_chu_ai: ghi_chu_goc = f"{ghi_chu_goc} [Phụ phí Khách: {', '.join(chuoi_ghi_chu_ai)}]".strip()
                                    if chuoi_phu_cap_tx: ghi_chu_goc = f"{ghi_chu_goc} [Phụ cấp TX: {chuoi_phu_cap_tx}]".strip()

                                    chi_phi_thue_ngoai_val = parse_excel_money(r.get('CHI_PHI_THUE_NGOAI'))
                                    if chi_phi_thue_ngoai_val == 0:
                                        raw_cp = row_db.get('chi_phi_thue_ngoai')
                                        chi_phi_thue_ngoai_val = float(raw_cp) if pd.notna(raw_cp) else 0.0
                                        
                                    hinh_thuc_tt = str(r.get('HINH_THUC_THANH_TOAN_NGOAI', '')).strip()
                                    if not hinh_thuc_tt or hinh_thuc_tt.lower() == 'nan': hinh_thuc_tt = 'Cong_No'

                                    data_dict_excel = {
                                        'ten_khach_hang': ten_khach_hang_db,
                                        'cong_chuyen': parse_excel_money(r.get('TIEN_CONG_TAI_XE')),
                                        'doanh_thu': doanh_thu_chuyen,
                                        'chi_phi_thue_ngoai': chi_phi_thue_ngoai_val,
                                        'hinh_thuc_thanh_toan_ngoai': hinh_thuc_tt,
                                        'phi_hai_quan': parse_excel_money(r.get('PHI_HAI_QUAN')),
                                        'phi_boc_xep': parse_excel_money(r.get('PHI_BOC_XEP')),
                                        'phi_khac': tong_phi_khac_final,
                                        'tien_them': tien_them_final,
                                        'ghi_chu_quyet_toan': ghi_chu_goc 
                                    }
                        
                                    success, msg = settle_trip_transaction(db.pool, data_dict_excel, 'Hoan_Thanh', cid)
                                    if success: closed_count += 1
                                    else: error_list.append(f"❌ Dòng {index + 2} (Mã {cid}): Lỗi DB - {msg}")
                                        
                                except Exception as ex:
                                    error_list.append(f"❌ Dòng {index + 2} (Mã {cid}): Lỗi tính toán - {str(ex)}")
                                    
                            if error_list:
                                st.warning(f"⚠️ Đã chốt thành công {closed_count} chuyến. Có {len(error_list)} lỗi/cảnh báo:")
                                for err in error_list: st.error(err)
                            else:
                                if closed_count > 0:
                                    st.success(f"🎉 TUYỆT VỜI! Đã chốt {closed_count} chuyến thành công!")
                                    time.sleep(2.5)
                                    st.rerun()
                                        
                        except Exception as e:
                            st.error(f"❌ Lỗi đọc file Excel: {str(e)}")
    vung_thao_tac_quyet_toan_auto()                      
########################################
# ==========================================
# TAB 4: 📊 LỊCH SỬ & CẢNH BÁO QUYẾT TOÁN
# ==========================================
with tab4:
    tao_tieu_de_kem_nut_refresh("📋 Tra cứu các chuyến đi đã quyết toán (Hoàn Thành)", "ref_tab_ls_qt")

    @st.fragment
    def vung_thao_tac_tra_cuu_quyet_toan():
        st.markdown("##### 🔍 Lọc dữ liệu theo khoảng thời gian")
        col_d1, col_d2 = st.columns(2)
        
        today = datetime.date.today()
        start_of_month = today.replace(day=1)
        
        with col_d1:
            tu_ngay = st.date_input("Từ ngày", value=start_of_month, format="DD/MM/YYYY", key="ls_qt_tu_ngay")
        with col_d2:
            den_ngay = st.date_input("Đến ngày", value=today, format="DD/MM/YYYY", key="ls_qt_den_ngay")
            
        if st.button("🚀 Tra cứu dữ liệu", type="primary", use_container_width=True):
            # Truy vấn lấy các chuyến đã Hoàn Thành trong khoảng ngày đã chọn
            sql_tra_cuu = """
                SELECT cd.id AS 'Mã Chuyến', cd.ngay_chuyen_di AS 'Ngày', cd.ten_khach_hang AS 'Khách Hàng',
                    COALESCE(x.bien_so_xe, cd.bien_so_xe_ngoai) AS 'Biển Số',
                    COALESCE(nv.ho_ten, cd.tai_xe_ngoai_ten) AS 'Tài Xế',
                    cd.dia_diem_giao_nhan AS 'Lộ Trình',
                    cd.doanh_thu AS 'Doanh Thu',
                    cd.tien_them AS 'Phụ Cấp',
                    cd.phi_khac AS 'Phí Khác', cd.chi_phi_thue_ngoai AS 'Phí Thuê Ngoài',
                    cd.ghi_chu_quyet_toan AS 'Ghi Chú'
                FROM chuyen_di cd
                LEFT JOIN xe x ON cd.xe_id = x.id
                LEFT JOIN chuyen_di_tai_xe ctx ON cd.id = ctx.chuyen_di_id AND ctx.loai_tai_xe = 'Tai_Chinh'
                LEFT JOIN nhan_vien nv ON ctx.tai_xe_id = nv.id
                WHERE cd.trang_thai_chuyen = 'Hoan_Thanh'
                  AND cd.ngay_chuyen_di >= %s AND cd.ngay_chuyen_di <= %s
                ORDER BY cd.ngay_chuyen_di DESC, cd.id DESC
            """
            
            df_kq = db.execute_query(sql_tra_cuu, (tu_ngay.strftime('%Y-%m-%d'), den_ngay.strftime('%Y-%m-%d')))
            
            st.divider()
            
            if isinstance(df_kq, pd.DataFrame) and not df_kq.empty:
                # Ép kiểu Doanh Thu về số thực để so sánh
                df_kq['Doanh Thu'] = pd.to_numeric(df_kq['Doanh Thu'], errors='coerce').fillna(0)
                
                # BỘ LỌC CẢNH BÁO: Tìm các chuyến Doanh thu = 0
                df_loi = df_kq[df_kq['Doanh Thu'] <= 0]
                
                if not df_loi.empty:
                    st.error(f"🚨 PHÁT HIỆN {len(df_loi)} CHUYẾN ĐI ĐÃ QUYẾT TOÁN NHƯNG BỊ SÓT DOANH THU (0 VNĐ)!")
                    st.markdown("⚠️ Kế toán vui lòng copy **Mã Chuyến** bên dưới, sang tab **Sửa chuyến đi đã quyết toán** để cập nhật lại mức cước chuẩn:")
                    
                    df_loi_hien_thi = df_loi[['Mã Chuyến', 'Ngày', 'Khách Hàng', 'Biển Số', 'Lộ Trình']].copy()
                    df_loi_hien_thi['Ngày'] = pd.to_datetime(df_loi_hien_thi['Ngày']).dt.strftime('%d/%m/%Y')
                    st.dataframe(df_loi_hien_thi, use_container_width=True, hide_index=True)
                    st.divider()

                # Xử lý format tiền tệ và ngày tháng để hiển thị tổng quan
                df_hien_thi = df_kq.copy()
                df_hien_thi['Ngày'] = pd.to_datetime(df_hien_thi['Ngày']).dt.strftime('%d/%m/%Y')
                
                for col in ['Doanh Thu', 'Phụ Cấp', 'Phí Khác', 'Phí Thuê Ngoài']:
                    df_hien_thi[col] = df_hien_thi[col].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "0")
                    
                st.success(f"✅ Tìm thấy {len(df_kq)} chuyến đi đã quyết toán trong khoảng thời gian này.")
                st.dataframe(df_hien_thi, use_container_width=True, hide_index=True)
            else:
                st.info("📭 Không có chuyến đi nào được quyết toán trong khoảng thời gian bạn chọn.")

    vung_thao_tac_tra_cuu_quyet_toan()