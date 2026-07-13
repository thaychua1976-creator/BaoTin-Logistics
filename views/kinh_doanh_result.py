import streamlit as st
import datetime
import pandas as pd
from trip_manager import get_bao_cao_pnl_chuyen_di
db = st.session_state['db']

st.markdown("## 💰 BÁO CÁO KẾT QUẢ KINH DOANH (P&L)")
st.caption("Phân tích Doanh thu, Chi phí trực tiếp và Lợi nhuận gộp theo từng chuyến đi.")
# --- 1. LẤY DANH SÁCH XE (TẠO XE_DICT) ---
@st.cache_data(ttl=300) # Cache lại 5 phút để tránh query DB liên tục
def get_danh_sach_xe(_db_pool):
    try:
        conn = _db_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, bien_so_xe FROM xe WHERE trang_thai = 'Dang_Hoat_Dong'")
        rows = cursor.fetchall()
        return {row[0]: row[1] for row in rows}
    except Exception as e:
        st.error(f"Lỗi lấy danh sách xe: {e}")
        return {}
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()

# Khởi tạo biến xe_dict từ hàm trên (Giả sử connection pool của bạn tên là db.pool)
xe_dict = get_danh_sach_xe(db.pool)

# --- BỘ LỌC TÌM KIẾM ---
with st.container(border=True):
    col1, col2, col3 = st.columns([2, 1, 1])
    # Tích hợp danh sách xe đã lấy từ DB
    xe_duoc_chon = col1.selectbox("🚛 Lọc theo phương tiện", options=[0] + list(xe_dict.keys()), format_func=lambda x: "🌟 Tất cả các xe" if x == 0 else xe_dict[x])
    tu_ngay = col2.date_input("📅 Từ ngày", datetime.date.today().replace(day=1), format="DD/MM/YYYY")
    den_ngay = col3.date_input("📅 Đến ngày", datetime.date.today(), format="DD/MM/YYYY")

st.markdown("<br>", unsafe_allow_html=True)

# --- XỬ LÝ DỮ LIỆU ---
df_pnl = get_bao_cao_pnl_chuyen_di(db.pool, tu_ngay.strftime('%Y-%m-%d'), den_ngay.strftime('%Y-%m-%d'), xe_duoc_chon)

if not df_pnl.empty:
    tong_doanh_thu = df_pnl['Doanh Thu'].sum()
    tong_chi_phi = df_pnl['Tổng Chi Phí'].sum()
    tong_loi_nhuan = df_pnl['Lợi Nhuận Gộp'].sum()
    ty_suat_loi_nhuan = (tong_loi_nhuan / tong_doanh_thu * 100) if tong_doanh_thu > 0 else 0

    # --- BẢNG CHỈ SỐ KPI TÀI CHÍNH ---
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💵 Tổng Doanh Thu", f"{tong_doanh_thu:,.0f} đ")
    k2.metric("🔥 Tổng Chi Phí (Trực tiếp)", f"{tong_chi_phi:,.0f} đ", delta="-", delta_color="inverse")
    k3.metric("💎 LỢI NHUẬN GỘP", f"{tong_loi_nhuan:,.0f} đ", delta="Lãi" if tong_loi_nhuan >= 0 else "Lỗ")
    k4.metric("📈 Biên Lợi Nhuận", f"{ty_suat_loi_nhuan:,.1f}%", help="Mức an toàn thường > 20%")

    st.divider()

    # --- BẢNG CHI TIẾT TỪNG CHUYẾN ---
    st.markdown("#### 📜 Sổ chi tiết Lãi/Lỗ từng chuyến")
    
    st.dataframe(
        df_pnl.style.format({
            "Doanh Thu": "{:,.0f}",
            "Lương TX & Thêm": "{:,.0f}",
            "Tiền Xăng/Dầu": "{:,.0f}",
            "Hải Quan": "{:,.0f}",
            "Bốc Xếp": "{:,.0f}",
            "Phí Khác": "{:,.0f}",
            "Tổng Chi Phí": "{:,.0f}",
            "Lợi Nhuận Gộp": "{:,.0f}"
        }).map(
            lambda x: 'color: red' if x < 0 else ('color: green' if x > 0 else ''),
            subset=['Lợi Nhuận Gộp']
        ),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("Không có chuyến đi nào hoàn thành trong giai đoạn được chọn.")
# ... (code st.dataframe(...) hiện tại của bạn) ...

st.markdown("<br>", unsafe_allow_html=True)
    
    # --- TẠO FILE EXCEL VÀ NÚT TẢI XUỐNG ---
import io
    
    # Tạo bộ đệm lưu file Excel trong bộ nhớ
buffer_pnl = io.BytesIO()
    
    # Sử dụng context manager (with) để tự động lưu file sau khi viết xong
with pd.ExcelWriter(buffer_pnl, engine='xlsxwriter') as writer:
        df_pnl.to_excel(writer, index=False, sheet_name="Bao_Cao_PnL")
        
        # Lấy đối tượng worksheet để định dạng
        worksheet = writer.sheets['Bao_Cao_PnL']
        
        # Định dạng Header (Tiêu đề): Nền đỏ đô (Màu tài chính), chữ trắng in đậm
        header_format = writer.book.add_format({
            'bold': True, 
            'font_color': 'white', 
            'bg_color': '#800000', 
            'border': 1
        })
        
        # Áp dụng định dạng cho dòng tiêu đề (Dòng 0)
        for col_num, col_name in enumerate(df_pnl.columns):
            worksheet.write(0, col_num, col_name, header_format)
            
        # Căn chỉnh tự động độ rộng của từng cột cho vừa với dữ liệu bên trong
        for idx, col in enumerate(df_pnl.columns):
            series_str = df_pnl[col].fillna("").astype(str)
            # Tính độ rộng cột: max(độ dài dữ liệu lớn nhất, độ dài tên cột) + một chút khoảng cách
            max_len = max(series_str.map(len).max() if not series_str.empty else 0, len(str(col))) + 2
            # Giới hạn độ rộng tối đa là 40 để bảng không bị quá bè
            worksheet.set_column(idx, idx, min(max_len, 40))

    # Căn chỉnh giao diện: Đẩy nút Download sang bên trái màn hình
col_btn_1, col_btn_2 = st.columns([1, 3])
with col_btn_1:
        # Lấy tên xe để đưa vào tên file (Nếu xe_duoc_chon = 0 thì tên là "Toan_Bo_Xe")
        ten_xe_file = "Toan_Bo_Xe" if xe_duoc_chon == 0 else str(xe_dict.get(xe_duoc_chon, "Xe")).replace(" ", "_")
        ngay_xuat = datetime.date.today().strftime('%d_%m_%Y')
        
        st.download_button(
            label="📥 XUẤT FILE EXCEL P&L",
            data=buffer_pnl.getvalue(),
            file_name=f"Bao_Cao_Loi_Nhuan_{ten_xe_file}_{ngay_xuat}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )