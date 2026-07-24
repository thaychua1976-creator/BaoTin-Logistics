import streamlit as st
import pandas as pd
from io import BytesIO
from fleet_manager import save_do_xang_transaction, update_do_xang_transaction
from utils_core import tao_tieu_de_kem_nut_refresh, doc_anh_cay_xang

def render_fuel_management_tab(db, current_user):
    """
    Hàm hiển thị giao diện Quản lý Nhiên Liệu & Hiệu Suất 
    Yêu cầu: Các form nhập liệu để trống khi load, trống sau khi submit xong.
    """
    tao_tieu_de_kem_nut_refresh("⛽ Quản lý Nhiên Liệu & Hiệu Suất", "ref_fuel")
    
    # Khởi tạo bộ đếm reset form trong session_state nếu chưa có
    if "fuel_form_reset_key" not in st.session_state:
        st.session_state["fuel_form_reset_key"] = 0
    if "fuel_edit_reset_key" not in st.session_state:
        st.session_state["fuel_edit_reset_key"] = 0

    # 1. LẤY DANH SÁCH XE TỪ DATABASE
    df_xe = db.execute_query("SELECT id, bien_so_xe, tong_km_hien_tai, dinh_muc_nhien_lieu FROM xe WHERE trang_thai='Dang_Hoat_Dong'")
    if not isinstance(df_xe, pd.DataFrame) or df_xe.empty:
        st.warning("⚠️ Hiện tại không có dữ liệu xe hoạt động trong hệ thống.")
        return
        
    dict_xe = {row['id']: row for _, row in df_xe.iterrows()}
    
    # 2. CHIA GIAO DIỆN THÀNH 3 TAB CON NGHIỆP VỤ
    tab_nhap_moi, tab_chinh_sua, tab_bieu_do = st.tabs([
        "📝 Nhập phiếu mới", 
        "⚙️ Chỉnh sửa phiếu cũ", 
        "📊 Biểu đồ đo lường"
    ])
    
    # ==========================================
    # TAB 1: FORM TÍCH HỢP AI & NHẬP BIÊN LAI MỚI
    # ==========================================
    with tab_nhap_moi:
        col_ai, col_form = st.columns([1, 2])
        
        with col_ai:
            st.markdown("#### 🤖 AI Nhận diện Hóa đơn & ODO")
            st.info("Tải lên ảnh Bill xăng hoặc ảnh Taplo xe để AI tự động trích xuất số liệu điền vào form.")
            uploaded_file = st.file_uploader("Chọn ảnh (JPG, PNG)", type=['jpg', 'jpeg', 'png'], key="fuel_ai_img")
            
            if uploaded_file:
                st.image(uploaded_file, caption="Ảnh hóa đơn / Taplo chờ xử lý", use_container_width=True)
                if st.button("🔍 Quét AI trích xuất dữ liệu", type="secondary", use_container_width=True):
                    with st.spinner("AI đang phân tích hình ảnh..."):
                        ket_qua_ai = doc_anh_cay_xang(BytesIO(uploaded_file.getvalue()))
                        if ket_qua_ai:
                            if ket_qua_ai.get('so_lit'): 
                                st.session_state['ai_fuel_lit'] = float(ket_qua_ai['so_lit'])
                            if ket_qua_ai.get('tong_tien'): 
                                st.session_state['ai_fuel_tien'] = int(ket_qua_ai['tong_tien'])
                            if ket_qua_ai.get('odo'): 
                                st.session_state['ai_fuel_odo'] = float(ket_qua_ai['odo'])
                            st.success("✅ Trích xuất thành công! Số liệu đã được nạp tạm vào bộ nhớ đệm.")
                        else:
                            st.error("❌ AI không nhận diện được dữ liệu. Vui lòng nhập thủ công.")

        with col_form:
            st.markdown("#### 📝 Đăng ký phiếu đổ xăng mới")
            
            form_key = f"form_nhap_xang_{st.session_state['fuel_form_reset_key']}"
            
            with st.form(form_key, clear_on_submit=False):
                xe_id_chon = st.selectbox(
                    "Chọn xe đổ xăng", 
                    options=list(dict_xe.keys()), 
                    index=None,
                    placeholder="-- Vui lòng chọn xe --",
                    format_func=lambda x: f"🚛 {dict_xe[x]['bien_so_xe']} (Định mức: {dict_xe[x]['dinh_muc_nhien_lieu']} L/100km)"
                )
                
                if xe_id_chon:
                    odo_hien_tai_xe = float(dict_xe[xe_id_chon]['tong_km_hien_tai'] or 0)
                    st.caption(f"📍 Mốc ODO gốc hiện tại trên hệ thống của xe: **{odo_hien_tai_xe:,.1f} KM**")
                
                default_odo = st.session_state.get('ai_fuel_odo', 0.0)
                default_lit = st.session_state.get('ai_fuel_lit', 0.0)
                default_tien = st.session_state.get('ai_fuel_tien', "")
                
                c1, c2 = st.columns(2)
                odo_moi = c1.number_input("Nhập ODO trên taplo thực tế (KM)*", min_value=0.0, value=float(default_odo), step=1.0, format="%.1f")
                so_lit = c2.number_input("Số lít nhiên liệu thực tế (L)*", min_value=0.0, value=float(default_lit), step=0.1, format="%.1f")
                
                tong_tien_str = st.text_input("Tổng tiền thanh toán (VNĐ)*", value=str(default_tien) if default_tien else "", placeholder="VD: 2,000,000")
                ghi_chu = st.text_area("Ghi chú (Tên cây xăng, Số hóa đơn...)")
                
                xac_nhan = st.checkbox("⚠️ Tôi xác nhận số liệu đồng hồ ODO và tiền nhiên liệu là chính xác.")
                
                submitted = st.form_submit_button("💾 Lưu dữ liệu đổ xăng", type="primary")
                
                if submitted:
                    if not xe_id_chon:
                        st.error("⚠️ Vui lòng chọn xe cần đổ xăng!")
                    elif odo_moi <= 0:
                        st.error("⚠️ Chỉ số ODO mới phải lớn hơn 0!")
                    elif so_lit <= 0:
                        st.error("⚠️ Số lít xăng phải lớn hơn 0!")
                    elif not tong_tien_str or not xac_nhan:
                        st.error("⚠️ Vui lòng nhập tổng tiền và tích chọn xác nhận thông tin trước khi lưu.")
                    else:
                        data_xang = {
                            "xe_id": xe_id_chon,
                            "odo_hien_tai": odo_moi,
                            "so_lit": so_lit,
                            "tong_tien": tong_tien_str,
                            "ghi_chu": ghi_chu
                        }
                        with st.spinner("Đang lưu lịch sử và cập nhật ODO xe..."):
                            is_ok, msg = save_do_xang_transaction(db.pool, data_xang, current_user)
                            if is_ok:
                                for k in ['ai_fuel_lit', 'ai_fuel_tien', 'ai_fuel_odo']:
                                    if k in st.session_state: 
                                        del st.session_state[k]
                                        
                                st.session_state["fuel_form_reset_key"] += 1
                                st.success(msg)
                                import time
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(msg)

    # ==========================================
    # TAB 2: CHỈNH SỬA PHIẾU ĐỔ XĂNG ĐÃ NHẬP
    # ==========================================
    with tab_chinh_sua:
        st.markdown("#### ⚙️ Điều chỉnh / Sửa lỗi phiếu đổ xăng")
        st.info("Sử dụng tính năng này nếu nhân sự nhập sai chỉ số ODO hoặc nhầm lẫn số tiền trên biên lai.")
        
        sql_list_xang = """
            SELECT dx.id, dx.ngay_do, x.bien_so_xe, dx.odo_hien_tai, dx.so_lit, dx.tong_tien, dx.ghi_chu
            FROM lich_su_do_xang dx
            JOIN xe x ON dx.xe_id = x.id
            ORDER BY dx.id DESC LIMIT 50
        """
        df_list_xang = db.execute_query(sql_list_xang)
        
        if isinstance(df_list_xang, pd.DataFrame) and not df_list_xang.empty:
            dict_bills = {}
            for _, r in df_list_xang.iterrows():
                ngay_format = pd.to_datetime(r['ngay_do']).strftime('%d/%m/%Y %H:%M')
                dict_bills[r['id']] = f"Mã phiếu #{r['id']} | Xe: {r['bien_so_xe']} | Ngày: {ngay_format} | {r['so_lit']}L - {int(r['tong_tien']):,}đ"
                
            bill_edit_id = st.selectbox(
                "📌 Chọn phiếu đổ xăng cần chỉnh sửa thông tin:", 
                options=list(dict_bills.keys()), 
                index=None, 
                placeholder="-- Bấm vào đây để chọn phiếu --",
                key=f"sel_bill_edit_{st.session_state['fuel_edit_reset_key']}"
            )
            
            if bill_edit_id:
                row_edit = df_list_xang[df_list_xang['id'] == bill_edit_id].iloc[0]
                
                # Form chỉnh sửa với key động để reset sạch sau khi lưu thành công
                edit_form_key = f"form_sua_xang_{bill_edit_id}_{st.session_state['fuel_edit_reset_key']}"
                
                with st.form(key=edit_form_key):
                    st.markdown(f"Đang hiệu chỉnh Mã phiếu **#{bill_edit_id}** của xe **{row_edit['bien_so_xe']}**")
                    
                    e_col1, e_col2, e_col3 = st.columns(3)
                    e_odo = e_col1.number_input("ODO ghi nhận lại (KM)", value=float(row_edit['odo_hien_tai']), step=1.0, format="%.1f")
                    e_lit = e_col2.number_input("Số lít nhiên liệu sửa lại", value=float(row_edit['so_lit']), step=0.1, format="%.1f")
                    
                    tien_format = f"{int(row_edit['tong_tien']):,}" 
                    e_tien = e_col3.text_input("Tổng tiền sửa lại (VNĐ)", value=tien_format)
                    
                    e_gc = st.text_input("Ghi chú chỉnh sửa (Lý do hiệu chỉnh)", value=str(row_edit['ghi_chu'] or ""))
                    
                    if st.form_submit_button("💾 Lưu thay đổi thông tin", type="primary"):
                        data_sua = {
                            "odo_hien_tai": e_odo,
                            "so_lit": e_lit,
                            "tong_tien": e_tien,
                            "ghi_chu": e_gc
                        }
                        
                        with st.spinner("Đang cập nhật lại hệ thống..."):
                            is_ok, msg = update_do_xang_transaction(db.pool, bill_edit_id, data_sua, current_user)
                            if is_ok:
                                # Tăng biến đếm reset form chỉnh sửa để làm trống form và ẩn lựa chọn cũ
                                st.session_state["fuel_edit_reset_key"] += 1
                                st.success(msg)
                                import time
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(msg)
        else:
            st.caption("Chưa có lịch sử ghi nhận đổ xăng nào trong hệ thống.")

    # ==========================================
    # TAB 3: DASHBOARD BIỂU ĐỒ HIỆU SUẤT NHIÊN LIỆU
    # ==========================================
    with tab_bieu_do:
        st.markdown("#### 📊 Phân tích hiệu suất tiêu hao nhiên liệu (Lít/100km)")
        
        xe_filter = st.selectbox(
            "Lọc biểu đồ theo xe:", 
            options=list(dict_xe.keys()), 
            index=None,
            placeholder="-- Chọn xe xem biểu đồ --",
            format_func=lambda x: dict_xe[x]['bien_so_xe'], 
            key="chart_xe_fuel"
        )
        
        if xe_filter:
            sql_history = """
                SELECT ngay_do, hieu_suat_tieu_hao, trang_thai_canh_bao 
                FROM lich_su_do_xang 
                WHERE xe_id = %s 
                ORDER BY ngay_do ASC LIMIT 20
            """
            df_hist = db.execute_query(sql_history, (xe_filter,))
            
            if isinstance(df_hist, pd.DataFrame) and not df_hist.empty:
                df_chart = df_hist[df_hist['hieu_suat_tieu_hao'] > 0].copy()
                if not df_chart.empty:
                    df_chart['Ngày đổ'] = pd.to_datetime(df_chart['ngay_do']).dt.strftime('%d/%m')
                    df_chart.rename(columns={'hieu_suat_tieu_hao': 'Lít/100km'}, inplace=True)
                    
                    st.line_chart(df_chart.set_index('Ngày đổ')['Lít/100km'], color="#d32f2f")
                    
                    canh_bao = df_chart[df_chart['trang_thai_canh_bao'] == 'Hao_Hut_Bat_Thuong']
                    if not canh_bao.empty:
                        st.error(f"🚨 CẢNH BÁO: Phát hiện {len(canh_bao)} lần tiêu thụ vượt định mức an toàn trên xe này! Đề nghị bộ phận kỹ thuật kiểm tra.")
                else:
                    st.info("ℹ️ Cần tối thiểu 2 lần đổ xăng liên tiếp để hệ thống tính toán quãng đường và vẽ biểu đồ hiệu suất.")
            else:
                st.caption("Xe này hiện chưa có lịch sử dữ liệu đổ xăng.")

# =====================================================================
# GỌI THỰC THI TRỰC TIẾP KHI STREAMLIT NẠP TRANG NÀY
# =====================================================================
if __name__ == "__main" or True:
    db_instance = st.session_state.get('db')
    user_name = st.session_state.get('ho_ten', st.session_state.get('username', 'Admin_DieuHanh'))
    
    if db_instance:
        render_fuel_management_tab(db_instance, user_name)
    else:
        st.error("⚠️ Lỗi kết nối Cơ sở dữ liệu! Vui lòng đăng nhập lại từ trang chủ.")