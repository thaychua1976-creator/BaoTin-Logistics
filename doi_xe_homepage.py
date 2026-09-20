import streamlit as st
import os
import base64
import header
import footer

def show_page():
    # 1. Cấu hình trang cơ bản
    st.set_page_config(page_title="BẢO TÍN LOGISTICS - Đội Xe Đa Tải", page_icon="🚚", layout="wide")

    # 2. GỌI HEADER (Truyền "doi_xe" để menu tự động đánh dấu trang hiện tại)
    header.render_header("doi_xe")

    # 3. CSS Đặc thù cho trang Đội Xe (Đã lược bỏ các CSS chung vì header đã lo)
    st.markdown("""
    <style>
    /* Định dạng thẻ Box xe */
    .fleet-box {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 16px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.04);
        height: 100%;
        display: flex;
        flex-direction: column;
        position: relative;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .fleet-box:hover { transform: translateY(-4px); box-shadow: 0 8px 20px rgba(11,46,158,0.08); border-color: #0B2E9E; }

    .capacity-badge {
        position: absolute; top: -12px; left: 20px; background-color: #0B2E9E; color: white;
        font-size: 12px; font-weight: 900; padding: 4px 12px; border-radius: 20px; border: 1px solid #FF6B00;
    }
    .box-title { color: #0B2E9E; font-size: 19px; font-weight: 900; margin-top: 5px; margin-bottom: 10px; }
    .box-desc { color: #334155; font-size: 14px; line-height: 1.5; margin-bottom: 15px; }
    .status-tag { display: inline-block; background-color: #dcfce7; color: #166534; font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 6px; }

    /* =========================================================
       HACK CSS: BIẾN CHỮ "CHƯA CÓ ẢNH" THÀNH NÚT CLICK OPEN FILE
       ========================================================= */
    .empty-placeholder { transition: 0.2s; cursor: pointer; }
    .empty-placeholder:hover {
        background-color: #e2e8f0 !important;
        border-color: #0B2E9E !important;
        color: #0B2E9E !important;
    }

    /* Ẩn hoàn toàn nhãn "Upload" và "200MB" */
    div[data-testid="stFileUploader"] label,
    div[data-testid="stFileUploader"] small,
    div[data-testid="stFileUploader"] [data-testid="stMarkdownContainer"] {
        display: none !important; 
    }

    /* Kéo uploader tàng hình đè lên đúng vị trí của thẻ xám Placeholder */
    div[data-testid="stFileUploader"] {
        position: relative;
        margin-top: -285px !important; 
        margin-bottom: 85px !important; 
        height: 200px !important;
        opacity: 0 !important; 
        z-index: 999;
    }
    
    div[data-testid="stFileUploader"] > section {
        height: 200px !important;
        padding: 0 !important;
        border: none !important;
    }

    /* Phóng to nút Browse Files gốc tràn viền 100% */
    div[data-testid="stFileUploadDropzone"] button {
        width: 100% !important;
        height: 100% !important;
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        margin: 0 !important;
        opacity: 0 !important;
        cursor: pointer !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # 4. TIÊU ĐỀ TRANG (Hiệu ứng 3D)
    st.markdown("""
    <div style="width: 100%; text-align: center; margin-top: 10px;">
        <div style="color: #0B2E9E; font-size: 48px; font-weight: 900; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 5px; text-shadow: 1px 1px 0px #e2e8f0, 2px 2px 0px #cbd5e1, 3px 3px 0px #94a3b8, 4px 4px 0px #64748b, 6px 6px 10px rgba(0,0,0,0.25);">Đội Xe Đa Tải - Sẵn Sàng 24/7</div>
        <div style="color: #475569; font-size: 20px; font-weight: 700; margin-bottom: 35px;">Hệ thống phương tiện vận tải hiện đại, đáp ứng mọi nhu cầu giao nhận nội địa & quốc tế</div>
    </div>
    """, unsafe_allow_html=True)

    # 5. KHU VỰC XỬ LÝ LÔ-GIC ẢNH
    current_dir = os.path.dirname(os.path.abspath(__file__))
    image_dir = os.path.join(current_dir, "image")
    if not os.path.exists(image_dir): os.makedirs(image_dir)

    def render_fleet_item(box_key, title, capacity_text, dimensions, desc):
        img_path = os.path.join(image_dir, f"{box_key}.jpg")
        has_img = os.path.exists(img_path)
        
        if has_img:
            with open(img_path, "rb") as f: 
                b64_str = base64.b64encode(f.read()).decode()
            img_html = f'<img src="data:image/jpeg;base64,{b64_str}" style="width: 100%; height: 200px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #e2e8f0; object-fit: cover;">'
        else:
            img_html = '<div class="empty-placeholder" style="width: 100%; height: 200px; background-color: #f1f5f9; border-radius: 8px; margin-bottom: 15px; border: 2px dashed #cbd5e1; display: flex; align-items: center; justify-content: space-between; color: #64748b; font-weight: bold; font-size: 15px;">📷 Bấm vào đây để tải ảnh lên</div>'

        st.markdown(f"""
<div class="fleet-box">
<div class="capacity-badge">Tối đa: {capacity_text}</div>
<div class="box-title" style="margin-top: 12px;">{title}</div>
<div style="color: #FF6B00; font-size: 13px; font-weight: bold; margin-bottom: 8px;">📏 {dimensions}</div>
<div class="box-desc">{desc}</div>
{img_html}
<div style="display: flex; justify-content: center; align-items: center; margin-top: auto;">
<span class="status-tag">🟢 Sẵn sàng</span>
</div>
</div>
""", unsafe_allow_html=True)

        if not has_img:
            uploaded_file = st.file_uploader("Upload", type=["jpg", "png", "jfif"], key=f"upload_{box_key}", label_visibility="collapsed")
            if uploaded_file is not None:
                with open(img_path, "wb") as f: 
                    f.write(uploaded_file.getbuffer())
                st.rerun()

    # 6. LƯỚI HIỂN THỊ 6 BOX ĐỘI XE
    col1, col2, col3 = st.columns(3, gap="large")
    with col1: render_fleet_item("xe_1_2t5", "🚛 Xe tải 1T - 2.5T", "2.5 tấn", "L4.2m x W1.9m x H1.9m", "Chuyên tuyến nội thành, phân phối hàng tiêu dùng, giao linh kiện điện tử.")
    with col2: render_fleet_item("xe_5t", "🚚 Xe tải 5T", "5 tấn", "L6.2m x W2.2m x H2.2m", "Chuyên tuyến nhà máy - KCN trọng điểm, trung chuyển hàng hóa đi sân bay.")
    with col3: render_fleet_item("xe_8t", "🚚 Xe tải 8T", "8 tấn", "L8.0m x W2.35m x H2.5m", "Vận chuyển hàng hóa kích thước trung bình, sức chứa pallet tối ưu 10-12 kiện.")

    st.markdown("<br>", unsafe_allow_html=True)

    col4, col5, col6 = st.columns(3, gap="large")
    with col4: render_fleet_item("xe_15t", "🚛 Xe tải 15T", "15 tấn", "L9.5m x W2.4m x H2.6m", "Chuyên chở hàng nặng, vận tải tuyến dài Bắc-Nam, kết nối linh hoạt giữa các ICD.")
    with col5: render_fleet_item("cont_20ft", "🚢 Container 20ft", "26-28 tấn", "L5.9m x W2.35m x H2.39m", "Chuyên hàng xuất nhập khẩu, dịch vụ kéo container chuyên tuyến Cát Lái và Cái Mép.")
    with col6: render_fleet_item("cont_40ft", "🌍 Container 40ft / 40HC", "28 tấn", "L12m x W2.35m x H2.7m", "Giải pháp vận chuyển hàng dự án, số lượng lớn, thông quan thẳng tuyến đi Cambodia.")
    
    # 7. GỌI FOOTER Ở CUỐI TRANG
    footer.render_footer()