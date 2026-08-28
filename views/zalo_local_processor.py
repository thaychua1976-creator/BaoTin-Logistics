import os
import time
import json
import easyocr
import re
import pandas as pd
from PIL import Image
import google.generativeai as genai
from datetime import datetime, date, timedelta
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-3.6-flash') # Cập nhật theo chuẩn phiên bản khả dụng
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DOWNLOAD_DIR = os.path.join(BASE_DIR, "zalo_downloads")
    TEMP_FILE = os.path.join(BASE_DIR, "temp_parsing.txt")
    EXCEL_FILE = os.path.join(BASE_DIR, "Danh_Sach_Book_Xe_Tong_Hop.xlsx")
else:
    st.error("⚠️ Không tìm thấy GEMINI_API_KEY trong file .env")

# Đảm bảo thư mục gốc tồn tại
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def get_grouped_files():
    valid_extensions = ('.jpg', '.jpeg', '.png', '.txt')
    grouped_files = {}
    for root, dirs, files in os.walk(DOWNLOAD_DIR):
        valid_files = [f for f in files if f.lower().endswith(valid_extensions)]
        if valid_files:
            group_name = os.path.basename(root)
            if group_name == "zalo_downloads": 
                group_name = "Khong_Xac_Dinh"
            grouped_files[group_name] = [os.path.join(root, f) for f in valid_files]
    return grouped_files

def process_offline_zalo_files():
    today_str = datetime.today().strftime('%Y-%m-%d')
    tomorrow_str = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    today_date = date.today()
    
    grouped_files = get_grouped_files()
    total_groups = len(grouped_files)
    
    if total_groups == 0:
        return {"status": "info", "message": "Thư mục trống. Không có dữ liệu để xử lý."}

    ui_group_status = st.empty()
    ui_file_status = st.empty()
    ui_progress = st.progress(0)
    ui_logs = st.empty()
    
    logs = []
    valid_records = []
    unprocessed_files = [] # Danh sách file chưa xử lý được để báo cáo người điều phối
    
    prompt = f"""
    Bạn là chuyên gia phân tích dữ liệu Logistics. Nhiệm vụ: Chuyển đổi văn bản hoặc hình ảnh thành mảng JSON chứa các chuyến đi độc lập.

    **QUY TẮC 1: BÓC TÁCH DỮ LIỆU DẠNG BẢNG**
    - Nếu ảnh là dạng bảng (VD: "GOLDEN VICTORY OIA | 28,000 | PHUONG DONG | 14H"), BẮT BUỘC mỗi dòng ngang tương ứng với 1 chuyến xe. 
    - Cấu trúc ngầm định: [Điểm đi] | [Khối lượng] | [Điểm đến] | [Giờ giấc / Ghi chú].

    **QUY TẮC 2: BÓC TÁCH CHUỖI TEXT TỔNG HỢP (NHIỀU XE / NHIỀU ĐIỂM)**
    - Nếu khách đặt nhiều xe trong 1 tin nhắn (VD: "2XE 8TAN", "- 1XE 1TAN", "- 1XE 6TAN" hoặc viết dính liền "GOLDEN VICTORY 35,000..."), BẮT BUỘC tách thành các object riêng biệt cho từng loại xe/chuyến.
    - Cấu trúc ẩn thường là: [Số lượng xe] [Loại xe/Trọng tải] [Điểm đi -> Điểm đến] [Ghi chú].

    **QUY TẮC 3: CHUẨN HÓA KHỐI LƯỢNG (khoi_luong_kg)**
    - ĐẶC BIỆT LƯU Ý: Các con số lớn đứng độc lập trong bảng (VD: 35,000; 28,000; 7,643; 2,000) CHÍNH LÀ khối lượng tính bằng KG. 
    - BẮT BUỘC loại bỏ dấu phẩy (",") (VD: 35,000 -> 35000, 7,643 -> 7643).
    - Nếu gặp "T", "TAN", "TẤN" (VD: 1TAN, 6T), nhân số đó với 1000. Đơn vị "KG" thì giữ nguyên.
    - Kết quả phải là kiểu số thực (Float). Nếu không có, trả về 0.

    **QUY TẮC 4: CHUẨN HÓA THỂ TÍCH (the_tich_cbm)**
    - Nhận diện các từ "CBM", "KHỐI", "khoi" (VD: 4CBM, 85CBM, 4 KHỐI). Lấy chính xác phần số. Nếu không có, trả về 0.

    **QUY TẮC 5: LÀM SẠCH FORM "YÊU CẦU ĐIỀU XE" (F.T)**
    - Chỉ tạo 1 object duy nhất. Ngày đi: Lấy ở "Thời gian yêu cầu xuất phát".
    - Điểm đi -> Điểm đến: Gom từ "Địa điểm xuất phát" -> "Điểm đến".
    - Khối lượng & Thể tích: Lọc số liệu từ ô "Lý do sử dụng xe" và áp dụng QUY TẮC 3 & 4. 
    - Ghi chú: Chữ rác dư thừa gom vào "ghi_chu".

    **QUY TẮC 6: XỬ LÝ NGÀY THÁNG**
    - "Sáng mai", "mai" -> {tomorrow_str}. "Hôm nay", "tối nay" -> {today_str}.

    **SCHEMA JSON YÊU CẦU ĐẦU RA:**
    {{
        "is_booking": true,
        "danh_sach_xe": [
            {{
                "ngay_chuyen_di": "YYYY-MM-DD",
                "dia_diem_giao_nhan": "Điểm đi -> Điểm đến",
                "khoi_luong_kg": Số thực (Đã bỏ dấu phẩy hoặc quy đổi),
                "the_tich_cbm": Số thực,
                "ghi_chu": "Chi tiết giờ giấc, tên xưởng, số kiện..."
            }}
        ]
    }}
    """
    
    group_idx = 1
    for nhom, file_paths in grouped_files.items():
        total_files_in_group = len(file_paths)
        ui_group_status.info(f"📁 Đang xử lý nhóm {group_idx}/{total_groups}: **{nhom}**")
        
        for idx, filepath in enumerate(file_paths, 1):
            filename = os.path.basename(filepath)
            is_image = filename.lower().endswith(('.jpg', '.jpeg', '.png'))
            success = False
            
            while not success:
                try:
                    ui_file_status.write(f"👉 Phân tích AI file {idx}/{total_files_in_group}: `{filename}`...")
                    
                    if is_image:
                        with Image.open(filepath) as img_obj:
                            if img_obj.mode != 'RGB': img_obj = img_obj.convert('RGB')
                            img_obj.thumbnail((1024, 1024))
                            response = model.generate_content([prompt, img_obj])
                    else:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            text_content = f.read()
                        response = model.generate_content(prompt + f'\nNội dung: "{text_content}"')
                    
                    clean_text = re.sub(r"^```json\s*", "", response.text.strip(), flags=re.IGNORECASE)
                    clean_text = re.sub(r"\s*```$", "", re.sub(r"^```\s*", "", clean_text, flags=re.IGNORECASE))
                    # Đếm số lượng record trước khi phân tích file này
                    record_count_before = len(valid_records)
                    match = re.search(r'\{.*\}', clean_text, re.DOTALL)
                    if match:
                        parsed = json.loads(match.group(0))
                        if parsed.get("is_booking"):
                            for xe in parsed.get("danh_sach_xe", []):
                                xe["nhom_zalo_nguon"] = nhom
                                try:
                                    raw_date = str(xe.get("ngay_chuyen_di", "")).strip()[:10]
                                    ngay = datetime.strptime(raw_date, '%Y-%m-%d').date()
                                    if ngay >= today_date:
                                        xe["khoi_luong_kg"] = float(xe.get("khoi_luong_kg") or 0.0)
                                        xe["the_tich_cbm"] = float(xe.get("the_tich_cbm") or 0.0)
                                        valid_records.append(xe)
                                except Exception:
                                    pass
                    
                    success = True
                    # KIỂM TRA LOGIC THỰC TẾ: Nếu số lượng không tăng, tức là file không chứa chuyến đi hợp lệ
                    if len(valid_records) == record_count_before:
                        logs.append(f"⚠️ Đã quét nhưng không thấy đơn hàng: {filename}")
                        unprocessed_files.append(f"{nhom} / {filename} (Không có dữ liệu hợp lệ)")
                    else:
                        logs.append(f"✅ Hoàn tất bóc tách: {filename}")
                        
                    ui_logs.text("\n".join(logs[-4:]))
                    
                                      
                    
                    if os.path.exists(filepath): os.remove(filepath)
                    ui_progress.progress(idx / total_files_in_group)
                    
                    if idx < total_files_in_group:
                        ui_file_status.warning("⏳ Nghỉ 15s chuyển file...")
                        time.sleep(15)
                        
                except Exception as e:
                    if "429" in str(e).lower() or "quota" in str(e).lower():
                        ui_file_status.error("⚠️ Quá tải API! Nghỉ 60s...")
                        time.sleep(60)
                    else:
                        logs.append(f"❌ Lỗi file {filename}: {e}")
                        ui_logs.text("\n".join(logs[-4:]))
                        success = True 
            
            if not success:
                unprocessed_files.append(f"{nhom} / {filename}")
        
        if group_idx < total_groups:
            ui_group_status.warning(f"🛑 Xong nhóm {nhom}. Nghỉ làm mát 30s...")
            time.sleep(30)
        
        group_idx += 1
                        
    ui_progress.empty()
    ui_file_status.empty()
    ui_group_status.empty()
    ui_logs.empty()
                    
    if valid_records:
        df_new = pd.DataFrame(valid_records)
        if os.path.exists(EXCEL_FILE):
            df_existing = pd.read_excel(EXCEL_FILE)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined.to_excel(EXCEL_FILE, index=False)
        else:
            df_new.to_excel(EXCEL_FILE, index=False)
        return {"status": "success", "message": f"✅ Đã lưu {len(valid_records)} chuyến xe vào Excel.", "unprocessed": unprocessed_files}
    return {"status": "warning",
            "message": "⚠️ Không tìm thấy dữ liệu hợp lệ.",
            "unprocessed": unprocessed_files}

def main_app():
    st.title("🤖 RPA - Lấy thông tin điều xe từ file Zalo (Cloud Web)")
    st.markdown("---")
    
    st.subheader("📤 Tải lên dữ liệu Zalo (Hình ảnh / File Text)")
    
    # 1. Tự động quét các thư mục nhóm đã tạo trước đó
    existing_groups = [d for d in os.listdir(DOWNLOAD_DIR) if os.path.isdir(os.path.join(DOWNLOAD_DIR, d))]
    options = ["+ Tạo nhóm mới"] + existing_groups
    
    # 2. Hiển thị Selectbox để trỏ vào nhóm cũ hoặc tạo mới
    selected_option = st.selectbox("📂 Chọn nhóm Zalo đích (hoặc tạo mới):", options)
    
    if selected_option == "+ Tạo nhóm mới":
        group_name_input = st.text_input("Nhập tên nhóm Zalo mới (Ví dụ: FIRST_TEAM):").strip()
    else:
        group_name_input = selected_option
    
    uploaded_files = st.file_uploader(
        "Chọn các file ảnh (.jpg, .png) hoặc văn bản (.txt) cần xử lý:", 
        type=["jpg", "jpeg", "png", "txt"], 
        accept_multiple_files=True
    )
    
    if uploaded_files and group_name_input:
        if st.button("📥 Lưu file lên hệ thống Cloud"):
            target_group_dir = os.path.join(DOWNLOAD_DIR, group_name_input)
            
            # Lệnh này đảm bảo ổ cứng chỉ tạo thư mục 1 lần duy nhất, nếu có rồi sẽ tự động bỏ qua
            os.makedirs(target_group_dir, exist_ok=True) 
            
            saved_count = 0
            for uploaded_file in uploaded_files:
                file_path = os.path.join(target_group_dir, uploaded_file.name)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                saved_count += 1
                
            st.success(f"✅ Đã tải lên thành công {saved_count} file vào nhóm `{group_name_input}`.")

    st.markdown("---")
    st.subheader("⚙️ Xử lý dữ liệu")
    
       
    if st.button("🚀 Bắt đầu phân tích AI", type="primary"):
        with st.spinner("Đang kết nối Gemini AI để phân tích..."):
            result = process_offline_zalo_files()
            if result:
                if result["status"] == "success": 
                    st.success(result["message"])
                elif result["status"] == "warning": 
                    st.warning(result["message"])
                elif result["status"] == "info": 
                    st.info(result["message"])
                
                if result.get("unprocessed"):
                    st.error(f"🚨 Có {len(result['unprocessed'])} file hệ thống không thể xử lý:")
                    for f in result["unprocessed"]:
                        st.markdown(f"- `{f}`")

    # 📌 KHU VỰC TẢI FILE EXCEL VỀ MÁY
    st.markdown("---")
    st.subheader("📥 Tải kết quả tổng hợp")
    if os.path.exists(EXCEL_FILE):
        with open(EXCEL_FILE, "rb") as file:
            st.download_button(
                label="⬇️ Tải file Danh_Sach_Book_Xe_Tong_Hop.xlsx",
                data=file,
                file_name="Danh_Sach_Book_Xe_Tong_Hop.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
    else:
        st.info("Chưa có dữ liệu Excel nào được xuất ra trên hệ thống Cloud.")

if __name__ == "__main__":
    main_app()