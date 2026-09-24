import streamlit as st
import os
import header
import footer

def show_page():
    # Cấu hình trang cơ bản
    st.set_page_config(
        page_title="BẢO TÍN LOGISTICS - Dịch Vụ Chính", 
        page_icon="🚚", 
        layout="wide"
    )

    # 1. GỌI HEADER (Truyền "dich_vu" để menu tự động đánh dấu trang hiện tại)
    header.render_header("dich_vu")

    # 2. CSS Tùy chỉnh (Chỉ giữ lại các CSS dành riêng cho các box dịch vụ của trang này)
    st.markdown("""
    <style>
        /* Service Box thông thường */
        .service-box {
            background-color: #ffffff;
            padding: 24px;
            border-radius: 16px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 4px 10px rgba(0,0,0,0.03);
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .service-box:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 20px rgba(11,46,158,0.08);
            border-color: #0B2E9E;
        }

        /* Service Box Cambodia (Nổi bật, có nhãn HOT) */
        .service-box-hot {
            background-color: #ffffff;
            padding: 24px;
            border-radius: 16px;
            border: 2px solid #FF6B00;
            box-shadow: 0 6px 15px rgba(255,107,0,0.15);
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            position: relative;
        }
        .hot-badge {
            position: absolute;
            top: -12px;
            right: 20px;
            background-color: #FF6B00;
            color: white;
            font-size: 12px;
            font-weight: 900;
            padding: 4px 12px;
            border-radius: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }

        /* Tiêu đề và mô tả trong box */
        .box-title {
            color: #0B2E9E;
            font-size: 20px;
            font-weight: 900;
            margin-bottom: 12px;
        }
        .box-desc {
            color: #334155;
            font-size: 15px;
            line-height: 1.6;
            margin-bottom: 20px;
        }

        /* Nút tư vấn (trỏ về trang liên hệ) */
        .consult-btn {
            display: inline-block;
            background-color: #0B2E9E;
            color: white !important;
            padding: 10px 18px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: bold;
            text-decoration: none !important;
            text-align: center;
            transition: background-color 0.2s;
            width: 100%;
        }
        .consult-btn:hover {
            background-color: #FF6B00;
            color: white !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # 3. TIÊU ĐỀ TRANG DỊCH VỤ 3D
    st.markdown("""
    <div style="width: 100%; text-align: center; margin-top: 10px;">
        <div style="
            color: #0B2E9E; 
            font-size: 42px; 
            font-weight: 900; 
            letter-spacing: 2px; 
            text-transform: uppercase; 
            margin-bottom: 5px; 
            text-shadow: 
                1px 1px 0px #e2e8f0, 
                2px 2px 0px #cbd5e1, 
                3px 3px 0px #94a3b8, 
                4px 4px 0px #64748b, 
                6px 6px 10px rgba(0,0,0,0.25);
        ">
            Dịch Vụ Chính
        </div>
        <div style="
            color: #475569; 
            font-size: 24px; 
            font-weight: 700; 
            margin-bottom: 40px;
        ">
            Giải pháp Logistics trọn gói cho nhà máy
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 4. HÀNG 1: 3 BOX DỊCH VỤ
    col1, col2, col3 = st.columns(3, gap="large")

    with col1:
        st.markdown("""
        <div class="service-box">
            <div>
                <div class="box-title">✈️ Nhà máy → Sân bay</div>
                <div class="box-desc">Chuyên tuyến nhà máy KCN Trảng Bàng, Tây Ninh đi Tân Sơn Nhất, Long Thành. Giao hàng gấp <b>2-4h</b>.</div>
            </div>
            <div><a href="?page=lien_he" target="_self" class="consult-btn">Tư vấn tuyến này</a></div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="service-box">
            <div>
                <div class="box-title">🏭 Nhà máy → Cảng & ICD</div>
                <div class="box-desc">Kéo cont, xe tải đi Cát Lái, Cái Mép-Thị Vải, ICD Tân Cảng, Sóng Thần, Transimex an toàn, đúng giờ.</div>
            </div>
            <div><a href="?page=lien_he" target="_self" class="consult-btn">Tư vấn tuyến này</a></div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="service-box-hot">
            <div class="hot-badge">HOT 🔥</div>
            <div>
                <div class="box-title" style="color: #FF6B00;">🌍 Quốc tế Cambodia LỢI THẾ</div>
                <div class="box-desc">Lợi thế cửa khẩu <b>Mộc Bài, Xa Mát</b>. Vận tải 2 chiều VN-Cambodia, thủ tục nhanh chóng, thông suốt.</div>
            </div>
            <div><a href="?page=lien_he" target="_self" class="consult-btn" style="background-color: #FF6B00;">Tư vấn tuyến này</a></div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 5. HÀNG 2: 3 BOX DỊCH VỤ TIẾP THEO
    col4, col5, col6 = st.columns(3, gap="large")

    with col4:
        st.markdown("""
        <div class="service-box" style="border: 2px solid #0B2E9E; background: linear-gradient(135deg, #ffffff 0%, #f0f4ff 100%);">
            <div>
                <div class="box-title" style="font-size: 21px; color: #0B2E9E;">📋 KHAI BÁO HẢI QUAN</div>
                <div class="box-desc"><b>Khai báo trọn gói</b>, C/O, kiểm dịch, hun trùng. Chuyên <b>xử lý luồng đỏ</b>, hàng khó tại cửa khẩu.</div>
            </div>
            <div><a href="?page=lien_he" target="_self" class="consult-btn">Tư vấn tuyến này</a></div>
        </div>
        """, unsafe_allow_html=True)

    with col5:
        st.markdown("""
        <div class="service-box">
            <div>
                <div class="box-title">🚛 Thuê xe 1T-15T & Container</div>
                <div class="box-desc">Đội xe <b>50+ đầu xe</b> sẵn sàng 24/7. Giám sát GPS hành trình, bảo hiểm <b>100% giá trị</b> hàng hóa.</div>
            </div>
            <div><a href="?page=lien_he" target="_self" class="consult-btn">Tư vấn tuyến này</a></div>
        </div>
        """, unsafe_allow_html=True)

    with col6:
        st.markdown("""
        <div class="service-box">
            <div>
                <div class="box-title">🏗️ Hàng dự án & Siêu trường</div>
                <div class="box-desc">Vận chuyển máy móc, dây chuyền nhà máy, hàng quá khổ quá tải. Hỗ trợ <b>khảo sát tuyến & cẩu hạ</b> trọn gói.</div>
            </div>
            <div><a href="?page=lien_he" target="_self" class="consult-btn">Tư vấn tuyến này</a></div>
        </div>
        """, unsafe_allow_html=True)
        
    # 6. GỌI FOOTER
    footer.render_footer()