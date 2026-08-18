import streamlit as st
import pandas as pd
import io
from utils_core import import_bang_gia_transaction



st.markdown("### 📥 CÔNG CỤ NẠP BIỂU CƯỚC & GHI CHÚ TỰ ĐỘNG")
st.info("Tải file mẫu, điền dữ liệu (bao gồm cột Ghi chú diễn giải từ các file báo giá thực tế) và upload lên hệ thống.")

# 1. TẠO FILE EXCEL MẪU CÓ CỘT GHI CHÚ
df_mau_rate = pd.DataFrame([{
    "KHACH_HANG": "ZHENGXING", 
    "TEN_BANG_GIA": "02 ZX-BT/2026",
    "DIEM_DI": "TÂN CẢNG", 
    "DIEM_DEN": "ZHENGXING",
    "PHAN_LOAI": "Hang_Le", 
    "LOAI_XE_QUY_CACH": "", 
    "GIOI_HAN_KG": 1000, 
    "GIOI_HAN_CBM": 6, 
    "IS_HANG_TRA_VE": 0, 
    "DON_GIA": 1600000,
    "GIA_CHUYEN_TIEP_NOI":0,
    "GHI_CHU": "Hàng lẻ đến ICD Tân Cảng"
}, {
    "KHACH_HANG": "SINCETECH", 
    "TEN_BANG_GIA": "BAOGIA_SINCETECH",
    "DIEM_DI": "TÂY NINH", 
    "DIEM_DEN": "VĨNH LONG",
    "PHAN_LOAI": "Xe_Tai", 
    "LOAI_XE_QUY_CACH": "1T", 
    "GIOI_HAN_KG": 0, 
    "GIOI_HAN_CBM": 0, 
    "IS_HANG_TRA_VE": 1, 
    "DON_GIA": 1400000,
    "GIA_CHUYEN_TIEP_NOI":0,
    "GHI_CHU": "Áp dụng cho hàng trả về"
}])

df_mau_surcharge = pd.DataFrame([{
    "KHACH_HANG": "CONTINENTAL",
    "TEN_PHU_PHI": "Phụ phí Đồng Nai",
    "DON_GIA": 330000,
    "DIEU_KIEN_KICH_HOAT": "ĐỒNG NAI",
    "LOAI_AP_DUNG": "Tu_Dong,Co_Dinh,%",
    "GHI_CHU": "Áp dụng cảng Hưng Đạo, Long Bình"
}])

buffer_template = io.BytesIO()
with pd.ExcelWriter(buffer_template, engine='xlsxwriter') as writer:
    df_mau_rate.to_excel(writer, index=False, sheet_name="BIEU_CUOC")
    df_mau_surcharge.to_excel(writer, index=False, sheet_name="PHU_PHI")

col1, col2 = st.columns([1, 2])
with col1:
    st.download_button(
        label="⬇️ TẢI MẪU EXCEL CÓ CỘT GHI CHÚ",
        data=buffer_template.getvalue(),
        file_name="Template_Import_BangGia_KemGhiChu.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

with col2:
    st.markdown("*Mẫu Excel đã được thiết kế sẵn sàng các cột tiêu chuẩn và cột **GHI_CHU** để lưu lại các điều kiện đặc thù của từng hãng.*")

st.divider()

# 2. XỬ LÝ UPLOAD FILE VÀ LƯU DATABASE
st.markdown("#### 🚀 Upload File Dữ Liệu")
with st.form("form_upload_bang_gia_ghichu"):
    uploaded_file = st.file_uploader("Chọn file Excel Biểu Cước (.xlsx)", type=["xlsx"])
    btn_submit = st.form_submit_button("XÁC NHẬN NẠP VÀO CƠ SỞ DỮ LIỆU", type="primary", use_container_width=True)

    if btn_submit:
        if not uploaded_file:
            st.warning("⚠️ Vui lòng chọn file Excel trước khi nạp!")
        else:
            with st.spinner("Đang xử lý và ghi dữ liệu kèm ghi chú vào CSDL..."):
                try:
                    xls = pd.ExcelFile(uploaded_file)
                    df_rates = None
                    df_surcharges = None
                    
                    if "BIEU_CUOC" in xls.sheet_names:
                        df_rates = pd.read_excel(xls, sheet_name="BIEU_CUOC")
                        df_rates.columns = [str(c).strip().upper() for c in df_rates.columns]
                    
                    if "PHU_PHI" in xls.sheet_names:
                        df_surcharges = pd.read_excel(xls, sheet_name="PHU_PHI")
                        df_surcharges.columns = [str(c).strip().upper() for c in df_surcharges.columns]

                    if df_rates is None and df_surcharges is None:
                        st.error("❌ File không đúng định dạng mẫu. Thiếu sheet BIEU_CUOC hoặc PHU_PHI.")
                    else:
                        current_user = st.session_state.get('username', 'Admin')
                        db = st.session_state['db'] 
                        
                        success, message = import_bang_gia_transaction(db.pool, df_rates, df_surcharges, current_user)
                        
                        if success:
                            st.success(message)
                        else:
                            st.error(message)

                except Exception as e:
                    st.error(f"❌ Lỗi hệ thống khi đọc file: {str(e)}")