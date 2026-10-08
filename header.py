import streamlit as st
import os
import base64

def render_header(current_page="home"):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    image_dir = os.path.join(current_dir, "image")
    logo_path = os.path.join(image_dir, "logo_baotin.jfif")

    def get_base64_image(path):
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        return None
        
    logo_b64 = get_base64_image(logo_path)

    # Sử dụng layout chuẩn của Streamlit cho phần Logo & Tiêu đề
    cols = st.columns([0.15, 0.85])
    with cols[0]:
        if logo_b64:
            st.markdown(f'<img src="data:image/jpeg;base64,{logo_b64}" style="width: 60px; height: 60px; border-radius: 8px; object-fit: cover;">', unsafe_allow_html=True)
        else:
            st.write("🚚")
    with cols[1]:
        st.markdown("<h3 style='margin: 0; color: #0B2E9E;'>BẢO TÍN LOGISTICS</h3>", unsafe_allow_html=True)
        st.markdown("<p style='margin: 0; color: #FF6B00; font-weight: bold; font-size: 14px;'>TRUCKINGBAOTIN.COM</p>", unsafe_allow_html=True)

    st.divider()

    # Dùng st.radio theo dạng horizontal (thanh ngang) để thay thế cho các thẻ link HTML trên mobile
    pages_map = {
        "🏠 Trang chủ": "home",
        "📦 Dịch vụ": "dich_vu",
        "🚚 Đội xe": "doi_xe",
        "🌏 Tuyến Cambodia": "tuyen_cambodia",
        "📞 Liên hệ": "lien_he",
        "⚙️ Điều hành nội bộ": "app"
    }

    # Xác định index hiện tại dựa vào current_page truyền vào
    reverse_map = {v: k for k, v in pages_map.items()}
    current_label = reverse_map.get(current_page, "🏠 Trang chủ")
    all_labels = list(pages_map.keys())
    
    selected_label = st.radio(
        "Điều hướng hệ thống",
        options=all_labels,
        index=all_labels.index(current_label) if current_label in all_labels else 0,
        horizontal=True,
        label_visibility="collapsed"
    )

    # Chuyển trang ngay lập tức khi user chọn menu mới trên điện thoại
    chosen_page_key = pages_map[selected_label]
    if chosen_page_key != current_page:
        st.query_params["page"] = chosen_page_key
        st.rerun()

    # Thanh thông tin nhận diện 3D phía dưới
    st.markdown("""
    <div style="background: linear-gradient(180deg, #1342c4 0%, #0B2E9E 50%, #061c63 100%); 
    color: white; text-align: center; padding: 8px; font-size: 13px; font-weight: bold; 
    border-bottom: 2px solid #FF6B00; border-radius: 6px; margin: 15px 0;">
    VPDD CÔNG TY TNHH BẢO TÍN LOGISTICS | 宝信物流公司 | We truck your trust
    </div>
    """, unsafe_allow_html=True)