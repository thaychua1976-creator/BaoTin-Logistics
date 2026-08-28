import streamlit as st
import pandas as pd
import io, datetime, time, json

# Import các hàm Backend chuẩn của dự án
from utils_core import (
    import_and_update_bang_gia_transaction,
    import_and_update_phu_phi_transaction,
    update_single_rate_card_transaction, 
    delete_single_rate_card_transaction,
    update_single_phu_phi_transaction,
    create_single_rate_card_transaction,
    delete_single_phu_phi_transaction,
    parse_money_input
)

db = st.session_state.get('db')

# Lấy chính xác username từ phiên đăng nhập thực tế của người dùng[cite: 3]
current_user = st.session_state.get('username') or st.session_state.get('user') or st.session_state.get('logged_in_user', 'Admin')

if not db:
    st.error("⚠️ Lỗi kết nối Cơ sở dữ liệu.")
    st.stop()

st.markdown("<h3 style='text-align: center; color: #0b5394;'>💸 QUẢN LÝ BIỂU CƯỚC & PHỤ PHÍ KHÁCH HÀNG (RATE CARDS & SURCHARGES)</h3>", unsafe_allow_html=True)
st.divider()

# Khai báo giải nén chính xác 4 Tabs giao diện
tab1, tab2, tab3, tab4 = st.tabs([
    "📝 1. Danh Sách & Sửa Bảng Giá", 
    "📥 2. Import Bảng Giá (Excel)",
    "🏷️ 3. Danh Sách & Sửa Phụ Phí",
    "📥 4. Import Phụ Phí (Excel)"
])


# =========================================================================
# TAB 1: DANH SÁCH, XUẤT EXCEL, THÊM, SỬA & XÓA TRỰC TIẾP BẢNG GIÁ
# =========================================================================
with tab1:
    st.markdown("#### 📋 Quản lý Biểu cước Vận chuyển (Rate Cards)")
    
    # Lấy danh sách khách hàng làm bộ lọc
    df_kh = db.execute_query("SELECT id, ten_khach_hang FROM khach_hang ORDER BY ten_khach_hang ASC")
    kh_opts = {"ALL": "🌟 TẤT CẢ CÔNG TY / KHÁCH HÀNG"}
    if isinstance(df_kh, pd.DataFrame) and not df_kh.empty:
        for _, row in df_kh.iterrows():
            kh_opts[int(row['id'])] = row['ten_khach_hang']
            
    chon_kh_id = st.selectbox(
        "🔍 Lọc theo công ty:", 
        options=list(kh_opts.keys()),
        format_func=lambda x: kh_opts[x],
        key="filter_rate_tab1",
        index=None, 
        placeholder="-- Vui lòng chọn Khách hàng để tải dữ liệu --"
    )
    st.divider()

    if chon_kh_id is None:
        st.info("💡 Mẹo: Hãy chọn một Khách hàng cụ thể từ danh sách trên để xem bảng giá. Hệ thống sẽ tải dữ liệu cực nhanh!")
    else:
        sql_base = """
            SELECT r.id, kh.ten_khach_hang, r.diem_di, r.diem_den,r.khoang_cach, r.ten_bang_gia,
                   r.phan_loai_phuong_tien, r.loai_xe_quy_cach, r.gioi_han_kg, r.gioi_han_cbm,
                   r.is_hang_tra_ve, r.don_gia_cuoc, r.gia_chuyen_tiep_noi, r.ghi_chu
            FROM rate_cards r
            JOIN khach_hang kh ON r.khach_hang_id = kh.id
        """
        
        if chon_kh_id == "ALL":
            st.warning("⚠️ Chế độ xem toàn bộ: Giao diện web chỉ hiển thị 500 dòng mới nhất để đảm bảo tốc độ. Hãy dùng nút 'Xuất Excel' bên dưới để lấy toàn bộ dữ liệu.")
            df_rates_ui = db.execute_query(sql_base + " ORDER BY r.id DESC LIMIT 500")
            df_rates_export = db.execute_query(sql_base + " ORDER BY r.id DESC")
            file_export_name = f"Bang_Gia_TatCa_{datetime.date.today().strftime('%d_%m_%Y')}.xlsx"
        else:
            df_rates_ui = db.execute_query(sql_base + " WHERE r.khach_hang_id = %s ORDER BY r.id DESC", (chon_kh_id,))
            df_rates_export = df_rates_ui 
            clean_name = "".join([c if c.isalnum() else "_" for c in kh_opts[chon_kh_id]])
            file_export_name = f"Bang_Gia_{clean_name}_{datetime.date.today().strftime('%d_%m_%Y')}.xlsx"

        # 🔧 FIX LỖI STREAMLIT API EXCEPTION TẠI ĐÂY
        if "mode_rate_t1_val" not in st.session_state:
            st.session_state["mode_rate_t1_val"] = "👀 Xem danh sách & Xuất Excel"
            
        opt_t1 = ["👀 Xem danh sách & Xuất Excel", "➕ Thêm mới tuyến đường", "✏️ Sửa trực tiếp tuyến đường", "🗑️ Xóa tuyến đường"]
        idx_t1 = opt_t1.index(st.session_state["mode_rate_t1_val"]) if st.session_state["mode_rate_t1_val"] in opt_t1 else 0
        
        mode_thao_tac = st.radio(
            "📌 Chọn hành động:", 
            opt_t1, 
            horizontal=True, 
            index=idx_t1
        )
        st.session_state["mode_rate_t1_val"] = mode_thao_tac
        
        st.markdown("<br>", unsafe_allow_html=True)

        # ===============================================
        # CHỨC NĂNG 1: THÊM MỚI
        # ===============================================
        if mode_thao_tac == "➕ Thêm mới tuyến đường":
            st.markdown("#### ➕ Thêm mới tuyến đường (Báo giá)")
            with st.form("form_add_single_rate", clear_on_submit=True):
                kh_list = {k: v for k, v in kh_opts.items() if k != "ALL"}
                default_kh_index = 0
                if chon_kh_id != "ALL" and chon_kh_id in kh_list:
                    default_kh_index = list(kh_list.keys()).index(chon_kh_id)

                selected_kh_create = st.selectbox("🏢 Chọn Khách Hàng*", options=list(kh_list.keys()), format_func=lambda x: kh_list[x], index=default_kh_index)
                
                c1, c2, c3,c4 = st.columns(4)
                e_ten_bg = c1.text_input("Tên bảng giá")
                e_diem_di = c2.text_input("Điểm đi*")
                e_diem_den = c3.text_input("Điểm đến*")
                e_khoang_cach = c4.number_input("Khoảng cách km", min_value=0.0, value=0.0,step=1.0)
                
                c5, c6, c7 = st.columns(3)
                phan_loai_opts = ['Container', 'Xe_Tai', 'Hang_Le', 'Hang_Air', 'Xe_May']
                e_phan_loai = c5.selectbox("Phân loại", phan_loai_opts, index=1)
                e_quy_cach = c6.text_input("Loại xe quy cách")
                e_is_ve = c7.selectbox("Chiều hàng", options=[0, 1], format_func=lambda x: "Chiều Đi (0)" if x==0 else "Chiều Về (1)")

                c8, c9, c10 = st.columns(3)
                e_gh_kg = c8.number_input("Giới hạn KG (LCL)", min_value=0.0, value=0.0, step=1.0)
                e_gh_cbm = c9.number_input("Giới hạn CBM (LCL)", min_value=0.0, value=0.0, step=0.1)
                e_gia_tp = c10.text_input("Giá chuyến tiếp nối (VNĐ)", value="0")

                c11, c12 = st.columns(2)
                e_don_gia = c11.text_input("Đơn giá cước (VNĐ)*", value="0")
                e_ghi_chu = c12.text_input("Ghi chú")

                if st.form_submit_button("💾 Xác Nhận Thêm Mới", type="primary"):
                    if not selected_kh_create or not e_diem_di.strip() or not e_diem_den.strip():
                        st.error("⚠️ Vui lòng điền đầy đủ thông tin Khách hàng, Điểm đi và Điểm đến.")
                    else:
                        data_add = {
                            "khach_hang_id": selected_kh_create, "ten_bang_gia": e_ten_bg.strip(), 
                            "diem_di": e_diem_di.strip().upper(), "diem_den": e_diem_den.strip().upper(),
                            "khoang_cach": e_khoang_cach, 
                            "phan_loai_phuong_tien": e_phan_loai, "loai_xe_quy_cach": e_quy_cach.strip(),
                            "gioi_han_kg": e_gh_kg, "gioi_han_cbm": e_gh_cbm, "is_hang_tra_ve": e_is_ve,
                            "don_gia_cuoc": e_don_gia, "gia_chuyen_tiep_noi": e_gia_tp, "ghi_chu": e_ghi_chu.strip()
                        }
                        success, message = create_single_rate_card_transaction(db.pool, data_add, current_user)
                        if success:
                            st.success(message)
                            time.sleep(1)
                            # Trả về trạng thái mặc định bằng biến val thay vì gọi trực tiếp key của widget
                            st.session_state['mode_rate_t1_val'] = "👀 Xem danh sách & Xuất Excel"
                            st.rerun()
                        else:
                            st.error(message)

        # ===============================================
        # CHỨC NĂNG: XEM, SỬA, XÓA KHI CÓ DỮ LIỆU
        # ===============================================
        else:
            if isinstance(df_rates_ui, pd.DataFrame) and not df_rates_ui.empty:
                
                # --- CHỨC NĂNG 2: XEM & XUẤT EXCEL ---
                if mode_thao_tac == "👀 Xem danh sách & Xuất Excel":
                    st.caption(f"Đang hiển thị **{len(df_rates_ui)}** mức giá trên giao diện.")
                    df_display = df_rates_ui.copy()
                    for col in ['don_gia_cuoc', 'gia_chuyen_tiep_noi']:
                        if col in df_display.columns:
                            df_display[col] = pd.to_numeric(df_display[col], errors='coerce').fillna(0).apply(lambda x: f"{x:,.0f}")
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df_rates_export.to_excel(writer, index=False, sheet_name='RateCards')
                        worksheet = writer.sheets['RateCards']
                        for i, col in enumerate(df_rates_export.columns):
                            max_len = df_rates_export[col].fillna('').astype(str).str.len().max() if not df_rates_export.empty else 0
                            col_width = int(max(max_len if not pd.isna(max_len) else 0, len(str(col)))) + 2
                            worksheet.set_column(i, i, col_width)

                    st.download_button(label="⬇️ XUẤT RA EXCEL BẢNG GIÁ (TẢI TOÀN BỘ)", data=buffer.getvalue(), file_name=file_export_name, mime="application/vnd.ms-excel", type="primary")

                # --- CHỨC NĂNG 3: SỬA TRỰC TIẾP ---
                elif mode_thao_tac == "✏️ Sửa trực tiếp tuyến đường":
                    rate_opts = {None: "-- Vui lòng chọn tuyến đường cần sửa --"}
                    for _, r in df_rates_ui.iterrows():
                        rate_opts[r['id']] = f"ID: {r['id']} | [{r['ten_khach_hang']}] {r['diem_di']} ➡️ {r['diem_den']} | Xe: {r['loai_xe_quy_cach']} | Giá: {float(r['don_gia_cuoc']):,}"
                            
                    selected_rate_id = st.selectbox("🔍 Chọn dòng giá cần sửa:", options=list(rate_opts.keys()), format_func=lambda x: rate_opts[x], index=0)
                        
                    if selected_rate_id is not None:
                        row_info = df_rates_ui[df_rates_ui['id'] == selected_rate_id].iloc[0]
                        
                        with st.form(f"form_edit_single_rate_{selected_rate_id}", clear_on_submit=False):
                            c1, c2, c3,c4 = st.columns(4)
                            e_ten_bg = c1.text_input("Tên bảng giá", value=str(row_info.get('ten_bang_gia', '')))
                            e_diem_di = c2.text_input("Điểm đi", value=str(row_info.get('diem_di', '')))
                            e_diem_den = c3.text_input("Điểm đến", value=str(row_info.get('diem_den', '')))
                            
                            kc_raw = row_info.get('khoang_cach')
                            kc_safe = float(kc_raw) if pd.notna(kc_raw) and str(kc_raw).strip() != "" else 0.0
                            e_khoang_cach = c4.number_input("Khoảng cách km", value=kc_safe, step=1.0)
                            
                            c5, c6, c7 = st.columns(3)
                            phan_loai_opts = ['Container', 'Xe_Tai', 'Hang_Le', 'Hang_Air', 'Xe_May']
                            default_pl = phan_loai_opts.index(row_info['phan_loai_phuong_tien']) if row_info['phan_loai_phuong_tien'] in phan_loai_opts else 1
                            e_phan_loai = c5.selectbox("Phân loại", phan_loai_opts, index=default_pl)
                            e_quy_cach = c6.text_input("Loại xe quy cách", value=str(row_info['loai_xe_quy_cach'] or ''))
                            e_is_ve = c7.selectbox("Chiều hàng", options=[0, 1], index=int(row_info['is_hang_tra_ve']), format_func=lambda x: "Chiều Đi (0)" if x==0 else "Chiều Về (1)")

                            c8, c9, c10 = st.columns(3)
                            e_gh_kg = c8.number_input("Giới hạn KG (LCL)", value=float(row_info.get('gioi_han_kg',  0)))
                            e_gh_cbm = c9.number_input("Giới hạn CBM (LCL)", value=float(row_info.get('gioi_han_cbm', 0)))
                            val_tiep_noi = float(row_info['gia_chuyen_tiep_noi'] or 0)
                            e_gia_tp = c10.text_input("Giá chuyến tiếp nối", value=f"{val_tiep_noi:,.0f}")

                            c11, c12 = st.columns(2)
                            val_don_gia = float(row_info['don_gia_cuoc'] or 0)
                            e_don_gia = c11.text_input("Đơn giá cước (VNĐ)*", value=f"{val_don_gia:,.0f}")
                            e_ghi_chu = c12.text_input("Ghi chú", value=str(row_info['ghi_chu'] or ''))

                            if st.form_submit_button("💾 Lưu Thay Đổi Mức Giá", type="primary"):
                                data_edit = {
                                    "ten_bang_gia": e_ten_bg, "diem_di": e_diem_di, "diem_den": e_diem_den, "khoang_cach": e_khoang_cach,
                                    "phan_loai_phuong_tien": e_phan_loai, "loai_xe_quy_cach": e_quy_cach,
                                    "gioi_han_kg": e_gh_kg, "gioi_han_cbm": e_gh_cbm, "is_hang_tra_ve": e_is_ve,
                                    "don_gia_cuoc": parse_money_input(e_don_gia), 
                                    "gia_chuyen_tiep_noi": parse_money_input(e_gia_tp), 
                                    "ghi_chu": e_ghi_chu
                                }
                                success, message = update_single_rate_card_transaction(db.pool, selected_rate_id, data_edit, current_user)
                                if success:
                                    st.success(message)
                                    time.sleep(1)
                                    st.session_state['mode_rate_t1_val'] = "👀 Xem danh sách & Xuất Excel"
                                    st.rerun()
                                else:
                                    st.error(message)

                # --- CHỨC NĂNG 4: XÓA ---
                elif mode_thao_tac == "🗑️ Xóa tuyến đường":
                    rate_opts_del = {None: "-- Vui lòng chọn tuyến đường cần xóa --"}
                    for _, r in df_rates_ui.iterrows():
                        rate_opts_del[r['id']] = f"ID: {r['id']} | [{r['ten_khach_hang']}] {r['diem_di']} ➡️ {r['diem_den']} | Giá: {float(r['don_gia_cuoc']):,}"
                        
                    selected_rate_id = st.selectbox("🗑️ Chọn dòng giá cần xóa:", options=list(rate_opts_del.keys()), format_func=lambda x: rate_opts_del[x], index=0)
                    
                    if selected_rate_id is not None:
                        st.warning(f"⚠️ Bạn có chắc chắn muốn xóa vĩnh viễn dòng báo giá mã **ID {selected_rate_id}** này không?")
                        if st.button("🗑️ Xác Nhận Xóa Vĩnh Viễn", type="primary"):
                            success, message = delete_single_rate_card_transaction(db.pool, selected_rate_id, current_user)
                            if success:
                                st.success(message)
                                time.sleep(1)
                                st.session_state['mode_rate_t1_val'] = "👀 Xem danh sách & Xuất Excel"
                                st.rerun()
                            else:
                                st.error(message)
            else:
                st.info("📭 Chưa có dữ liệu bảng giá nào trong hệ thống khớp với bộ lọc. Hãy chọn 'Thêm mới tuyến đường' để tạo báo giá đầu tiên.")


# =========================================================================
# TAB 2: IMPORT & CẬP NHẬT BẢNG GIÁ HÀNG LOẠT (EXCEL)
# ==========================================
with tab2:
    st.markdown("#### 📥 Nhập & Cập nhật Biểu cước từ Excel")
    st.warning("⚠️ **Lưu ý:** Tải lên file **Template_Import_BangGia_BaoTin.xlsx** để tạo mới (hệ thống tự động tách chiều về theo % phụ phí). Hoặc tải file xuất từ Tab 1 (có cột ID) để cập nhật giá cũ.")
    
    with st.form("form_import_rate_excel", clear_on_submit=True):
        file_rate_up = st.file_uploader("📂 Tải lên File Excel Bảng Giá (.xlsx)", type=["xlsx", "xls"])
        btn_import_rate = st.form_submit_button("🚀 XÁC NHẬN CẬP NHẬT DỮ LIỆU VÀO DATABASE", type="primary")
        
        if btn_import_rate:
            if file_rate_up is not None:
                try:
                    xls = pd.ExcelFile(file_rate_up)
                    
                    sheet_rate = "BIEU_CUOC" if "BIEU_CUOC" in xls.sheet_names else ("RateCards" if "RateCards" in xls.sheet_names else 0)
                    df_up_rate = pd.read_excel(xls, sheet_name=sheet_rate)
                    df_up_rate.columns = [str(c).strip().upper() for c in df_up_rate.columns]
                    
                    df_up_pp = None
                    if "PHU_PHI" in xls.sheet_names:
                        df_up_pp = pd.read_excel(xls, sheet_name="PHU_PHI")
                        df_up_pp.columns = [str(c).strip().upper() for c in df_up_pp.columns]
                    elif "PhuPhiKhachHang" in xls.sheet_names:
                        df_up_pp = pd.read_excel(xls, sheet_name="PhuPhiKhachHang")
                        df_up_pp.columns = [str(c).strip().upper() for c in df_up_pp.columns]

                    is_ok, msg = import_and_update_bang_gia_transaction(db.pool, df_up_rate, df_up_pp, current_user)
                    
                    if is_ok:
                        st.success("✅ CẬP NHẬT THÀNH CÔNG VÀO CƠ SỞ DỮ LIỆU!")
                        st.markdown(msg)
                        st.info("🔄 Giao diện sẽ tự động làm mới sau 5 giây để hiển thị dữ liệu mới...")
                        time.sleep(5)
                        st.rerun()
                    else:
                        st.error(f"❌ Cập nhật thất bại: {msg}")
                        
                except Exception as e:
                    st.error(f"❌ File Excel không hợp lệ hoặc sai định dạng. Chi tiết lỗi: {e}")
            else:
                st.warning("⚠️ Vui lòng tải file Excel lên trước khi bấm xác nhận!")


# =========================================================================
# TAB 3: DANH SÁCH, XUẤT EXCEL, SỬA, THÊM MỚI & XÓA TRỰC TIẾP PHỤ PHÍ
# =========================================================================
with tab3:
    st.markdown("#### 🏷️ Quản lý Phụ phí Khách hàng (Surcharges)")
    
    df_kh_pp = db.execute_query("SELECT id, ten_khach_hang FROM khach_hang ORDER BY ten_khach_hang ASC")
    kh_pp_opts = {"ALL": "🌟 TẤT CẢ CÔNG TY / KHÁCH HÀNG"}
    if isinstance(df_kh_pp, pd.DataFrame) and not df_kh_pp.empty:
        for _, row in df_kh_pp.iterrows():
            kh_pp_opts[int(row['id'])] = row['ten_khach_hang']
            
    chon_kh_pp_id = st.selectbox(
        "🔍 Lọc theo công ty:", 
        options=list(kh_pp_opts.keys()), 
        format_func=lambda x: kh_pp_opts[x], 
        key="filter_pp_t3",
        index=None,
        placeholder="-- Vui lòng chọn Khách hàng để tải dữ liệu phụ phí --"
    )
    st.divider()

    if chon_kh_pp_id is None:
        st.info("💡 Mẹo: Hãy chọn một Khách hàng cụ thể từ danh sách trên để xem phụ phí. Hệ thống sẽ tải dữ liệu cực nhanh!")
    else:
        sql_pp_base = """
            SELECT p.id, kh.ten_khach_hang, p.ten_phu_phi, p.don_gia_phu_phi, 
                   p.dieu_kien_kich_hoat, p.loai_ap_dung, p.ghi_chu
            FROM phu_phi_khach_hang p
            JOIN khach_hang kh ON p.khach_hang_id = kh.id
        """
        
        if chon_kh_pp_id == "ALL":
            st.warning("⚠️ Chế độ xem toàn bộ: Giao diện web chỉ hiển thị 500 dòng mới nhất để chống giật lag. Hãy dùng nút 'Xuất Excel' để lấy toàn bộ dữ liệu.")
            df_pp_ui = db.execute_query(sql_pp_base + " ORDER BY p.id DESC LIMIT 500")
            df_pp_export = db.execute_query(sql_pp_base + " ORDER BY p.id DESC")
            file_pp_name = f"Phu_Phi_TatCa_{datetime.date.today().strftime('%d_%m_%Y')}.xlsx"
        else:
            df_pp_ui = db.execute_query(sql_pp_base + " WHERE p.khach_hang_id = %s ORDER BY p.id DESC", (chon_kh_pp_id,))
            df_pp_export = df_pp_ui
            clean_name = "".join([c if c.isalnum() else "_" for c in kh_pp_opts[chon_kh_pp_id]])
            file_pp_name = f"Phu_Phi_{clean_name}_{datetime.date.today().strftime('%d_%m_%Y')}.xlsx"

        # 🔧 FIX LỖI STREAMLIT API EXCEPTION TẠI ĐÂY
        if "mode_pp_t3_val" not in st.session_state:
            st.session_state["mode_pp_t3_val"] = "👀 Xem danh sách & Xuất Excel"
            
        opt_t3 = ["👀 Xem danh sách & Xuất Excel", "➕ Thêm mới phụ phí", "✏️ Sửa trực tiếp phụ phí", "🗑️ Xóa phụ phí"]
        idx_t3 = opt_t3.index(st.session_state["mode_pp_t3_val"]) if st.session_state["mode_pp_t3_val"] in opt_t3 else 0
        
        mode_pp_act = st.radio(
            "📌 Chọn hành động:", 
            opt_t3, 
            horizontal=True, 
            index=idx_t3
        )
        st.session_state["mode_pp_t3_val"] = mode_pp_act
        
        st.markdown("<br>", unsafe_allow_html=True)

        # ===============================================
        # CHỨC NĂNG 1: THÊM MỚI PHỤ PHÍ
        # ===============================================
        if mode_pp_act == "➕ Thêm mới phụ phí":
            st.markdown("#### ➕ Thêm mới Phụ phí Khách hàng")
            with st.form("form_add_single_pp", clear_on_submit=True):
                kh_list = {k: v for k, v in kh_pp_opts.items() if k != "ALL"}
                default_kh_index = 0
                if chon_kh_pp_id != "ALL" and chon_kh_pp_id in kh_list:
                    default_kh_index = list(kh_list.keys()).index(chon_kh_pp_id)

                selected_kh_create = st.selectbox("🏢 Chọn Khách Hàng*", options=list(kh_list.keys()), format_func=lambda x: kh_list[x], index=default_kh_index)
                
                c1, c2 = st.columns(2)
                e_ten_pp = c1.text_input("Tên phụ phí*")
                e_don_gia_pp = c2.text_input("Đơn giá phụ phí (VNĐ)*", value="0")

                c3, c4 = st.columns(2)
                e_dk_kich_hoat = c3.text_input("Điều kiện kích hoạt", placeholder='VD: {"loai": "boc_xep"}')
                e_loai_ap_dung = c4.text_input("Loại áp dụng", value="Co_Dinh")

                e_ghi_chu_pp = st.text_input("Ghi chú")

                if st.form_submit_button("💾 Xác Nhận Thêm Mới", type="primary"):
                    if not selected_kh_create or not e_ten_pp.strip():
                        st.error("⚠️ Vui lòng điền đầy đủ thông tin Khách hàng và Tên phụ phí.")
                    else:
                        data_add_pp = {
                            "khach_hang_id": selected_kh_create,
                            "ten_phu_phi": e_ten_pp.strip(),
                            "don_gia_phu_phi": parse_money_input(e_don_gia_pp),
                            "dieu_kien_kich_hoat": e_dk_kich_hoat.strip(),
                            "loai_ap_dung": e_loai_ap_dung.strip(),
                            "ghi_chu": e_ghi_chu_pp.strip()
                        }
                        
                        try:
                            from utils_core import create_single_phu_phi_transaction
                            success, message = create_single_phu_phi_transaction(db.pool, data_add_pp, current_user)
                        except ImportError:
                            try:
                                from audit_logger import ghi_log_he_thong
                                conn = db.pool.get_connection()
                                conn.autocommit = False
                                cursor = conn.cursor()
                                sql_insert = """
                                    INSERT INTO phu_phi_khach_hang (khach_hang_id, ten_phu_phi, don_gia_phu_phi, dieu_kien_kich_hoat, loai_ap_dung, ghi_chu)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """
                                cursor.execute(sql_insert, (
                                    data_add_pp['khach_hang_id'], data_add_pp['ten_phu_phi'], data_add_pp['don_gia_phu_phi'],
                                    data_add_pp['dieu_kien_kich_hoat'], data_add_pp['loai_ap_dung'], data_add_pp['ghi_chu']
                                ))
                                new_id = cursor.lastrowid
                                ghi_log_he_thong(cursor, "QUAN_LY_PHU_PHI", new_id, current_user, "TAO_MOI", json.dumps(data_add_pp, ensure_ascii=False))
                                conn.commit()
                                success, message = True, "✅ Đã thêm mới phụ phí thành công!"
                            except Exception as ex:
                                if 'conn' in locals(): conn.rollback()
                                success, message = False, f"Lỗi DB: {str(ex)}"
                            finally:
                                if 'cursor' in locals(): cursor.close()
                                if 'conn' in locals(): conn.close()

                        if success:
                            st.success(message)
                            time.sleep(1)
                            st.session_state['mode_pp_t3_val'] = "👀 Xem danh sách & Xuất Excel"
                            st.rerun()
                        else:
                            st.error(message)

        # ===============================================
        # CHỨC NĂNG: XEM, SỬA, XÓA KHI CÓ DỮ LIỆU
        # ===============================================
        else:
            if isinstance(df_pp_ui, pd.DataFrame) and not df_pp_ui.empty:
                # --- CHỨC NĂNG 2: XEM & XUẤT EXCEL ---
                if mode_pp_act == "👀 Xem danh sách & Xuất Excel":
                    st.caption(f"Đang hiển thị **{len(df_pp_ui)}** loại phụ phí trên giao diện.")
                    df_display_pp = df_pp_ui.copy()
                    
                    if 'don_gia_phu_phi' in df_display_pp.columns:
                        df_display_pp['don_gia_phu_phi'] = pd.to_numeric(df_display_pp['don_gia_phu_phi'], errors='coerce').fillna(0).apply(lambda x: f"{x:,.0f}")
                    
                    df_display_pp = df_display_pp.rename(columns={
                        'id': 'ID',
                        'ten_khach_hang': 'Tên khách hàng',
                        'ten_phu_phi': 'Tên phụ phí',
                        'don_gia_phu_phi': 'Đơn giá',
                        'dieu_kien_kich_hoat': 'Điều kiện kích hoạt',
                        'loai_ap_dung': 'Loại áp dụng',
                        'ghi_chu': 'Ghi chú'
                    })
                    
                    st.dataframe(df_display_pp, use_container_width=True, hide_index=True)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    buffer_pp = io.BytesIO()
                    with pd.ExcelWriter(buffer_pp, engine='xlsxwriter') as writer:
                        df_pp_export.to_excel(writer, index=False, sheet_name='PhuPhiKhachHang')
                        worksheet = writer.sheets['PhuPhiKhachHang']
                        for i, col in enumerate(df_pp_export.columns):
                            max_len = df_pp_export[col].fillna('').astype(str).str.len().max() if not df_pp_export.empty else 0
                            if pd.isna(max_len): max_len = 0
                            col_width = int(max(max_len, len(str(col)))) + 2
                            worksheet.set_column(i, i, col_width)

                    st.download_button(
                        label="⬇️ XUẤT RA EXCEL PHỤ PHÍ (TẢI TOÀN BỘ)",
                        data=buffer_pp.getvalue(),
                        file_name=file_pp_name,
                        mime="application/vnd.ms-excel",
                        type="primary"
                    )

                # --- CHỨC NĂNG 3: SỬA TRỰC TIẾP ---
                elif mode_pp_act == "✏️ Sửa trực tiếp phụ phí":
                    pp_opts = {None: "-- Vui lòng chọn phụ phí cần sửa --"}
                    for _, r in df_pp_ui.iterrows(): 
                        pp_opts[r['id']] = f"ID: {r['id']} | [{r['ten_khach_hang']}] {r['ten_phu_phi']} | Giá: {float(r['don_gia_phu_phi']):,}"
                        
                    selected_pp_id = st.selectbox(
                        "🔍 Chọn phụ phí cần sửa:", 
                        options=list(pp_opts.keys()), 
                        format_func=lambda x: pp_opts[x],
                        index=0
                    )
                    
                    if selected_pp_id is not None:
                        row_pp = df_pp_ui[df_pp_ui['id'] == selected_pp_id].iloc[0]
                        with st.form(f"form_edit_single_pp_{selected_pp_id}", clear_on_submit=False):
                            c1, c2 = st.columns(2)
                            e_ten_pp = c1.text_input("Tên phụ phí*", value=str(row_pp['ten_phu_phi'] or ''))
                            
                            val_don_gia_pp = float(row_pp['don_gia_phu_phi'] or 0)
                            e_don_gia_pp = c2.text_input("Đơn giá phụ phí (VNĐ)*", value=f"{val_don_gia_pp:,.0f}")

                            c3, c4 = st.columns(2)
                            e_dk_kich_hoat = c3.text_input("Điều kiện kích hoạt", value=str(row_pp['dieu_kien_kich_hoat'] or ''))
                            e_loai_ap_dung = c4.text_input("Loại áp dụng", value=str(row_pp['loai_ap_dung'] or 'Tu_Dong'))

                            e_ghi_chu_pp = st.text_input("Ghi chú", value=str(row_pp['ghi_chu'] or ''))

                            if st.form_submit_button("💾 Lưu Thay Đổi Phụ Phí", type="primary"):
                                data_edit_pp = {
                                    "ten_phu_phi": e_ten_pp,
                                    "don_gia_phu_phi": parse_money_input(e_don_gia_pp),
                                    "dieu_kien_kich_hoat": e_dk_kich_hoat,
                                    "loai_ap_dung": e_loai_ap_dung,
                                    "ghi_chu": e_ghi_chu_pp
                                }
                                success, message = update_single_phu_phi_transaction(db.pool, selected_pp_id, data_edit_pp, current_user)
                                if success:
                                    st.success(message)
                                    time.sleep(1)
                                    st.session_state['mode_pp_t3_val'] = "👀 Xem danh sách & Xuất Excel"
                                    st.rerun()
                                else:
                                    st.error(message)

                # --- CHỨC NĂNG 4: XÓA ---
                elif mode_pp_act == "🗑️ Xóa phụ phí":
                    pp_opts_del = {None: "-- Vui lòng chọn phụ phí cần xóa --"}
                    for _, r in df_pp_ui.iterrows():
                        pp_opts_del[r['id']] = f"ID: {r['id']} | [{r['ten_khach_hang']}] {r['ten_phu_phi']} | Giá: {float(r['don_gia_phu_phi']):,}"
                        
                    selected_pp_id = st.selectbox(
                        "🗑️ Chọn phụ phí cần xóa:", 
                        options=list(pp_opts_del.keys()), 
                        format_func=lambda x: pp_opts_del[x],
                        index=0
                    )
                    
                    if selected_pp_id is not None:
                        st.warning(f"⚠️ Bạn có chắc chắn muốn xóa vĩnh viễn loại phụ phí mã **ID {selected_pp_id}** này không?")
                        if st.button("🗑️ Xác Nhận Xóa Vĩnh Viễn Phụ Phí", type="primary"):
                            success, message = delete_single_phu_phi_transaction(db.pool, selected_pp_id, current_user)
                            if success:
                                st.success(message)
                                time.sleep(1)
                                st.session_state['mode_pp_t3_val'] = "👀 Xem danh sách & Xuất Excel"
                                st.rerun()
                            else:
                                st.error(message)
            else:
                st.info("📭 Hiện chưa có phụ phí nào được thiết lập cho bộ lọc này. Hãy chọn 'Thêm mới phụ phí' để tạo.")


# =========================================================================
# TAB 4: IMPORT & CẬP NHẬT PHỤ PHÍ HÀNG LOẠT (EXCEL)
# ==========================================
with tab4:
    st.markdown("#### 📥 Nhập & Cập nhật Phụ phí từ Excel")
    st.warning("⚠️ **Lưu ý:** Giữ nguyên cột **ID** nếu bạn muốn cập nhật phụ phí cũ. Để trống cột **ID** nếu muốn thêm mới phụ phí.")
    
    with st.form("form_import_pp_excel", clear_on_submit=True):
        file_pp_up = st.file_uploader("📂 Tải lên File Excel Phụ Phí (.xlsx)", type=["xlsx", "xls"])
        btn_import_pp = st.form_submit_button("🚀 XÁC NHẬN CẬP NHẬT PHỤ PHÍ VÀO DATABASE", type="primary")
        
        if btn_import_pp:
            if file_pp_up is not None:
                try:
                    xls_pp = pd.ExcelFile(file_pp_up)
                    sheet_pp = "PHU_PHI" if "PHU_PHI" in xls_pp.sheet_names else ("PhuPhiKhachHang" if "PhuPhiKhachHang" in xls_pp.sheet_names else 0)
                    
                    df_up_pp = pd.read_excel(xls_pp, sheet_name=sheet_pp)
                    df_up_pp.columns = [str(c).strip().upper() for c in df_up_pp.columns]
                    
                    is_ok, msg = import_and_update_phu_phi_transaction(db.pool, df_up_pp, current_user)
                    if is_ok:
                        st.success(f"✅ KẾT QUẢ: {msg}")
                        st.info("🔄 Giao diện sẽ làm mới sau 3 giây...")
                        time.sleep(3) 
                        st.rerun()
                    else:
                        st.error(msg)
                except Exception as e:
                    st.error(f"❌ File Excel không hợp lệ. Chi tiết lỗi: {e}")
            else:
                st.warning("⚠️ Vui lòng chọn file Excel trước khi bấm xác nhận!")