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
    model = genai.GenerativeModel('gemini-3.6-flash') 
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DOWNLOAD_DIR = os.path.join(BASE_DIR, "zalo_downloads")
    TEMP_FILE = os.path.join(BASE_DIR, "temp_parsing.txt")
    EXCEL_FILE = os.path.join(BASE_DIR, "Danh_Sach_Book_Xe_Tong_Hop.xlsx")
else:
    st.error("⚠️ Không tìm thấy GEMINI_API_KEY trong file .env")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@st.cache_resource
def load_ocr_model():
    return easyocr.Reader(['vi', 'en'], gpu=False)

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

# [CẬP NHẬT]: Hàm dọn dẹp CHỈ XÓA FILE (Tự động chạy để dọn rác từ phiên trước)
def clear_files_only():
    deleted_count = 0
    for root, dirs, files in os.walk(DOWNLOAD_DIR):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                os.remove(file_path)
                deleted_count += 1
            except Exception:
                pass
    return deleted_count

# [CẬP NHẬT]: Hàm dọn dẹp TOÀN BỘ FILE & THƯ MỤC (Chỉ chạy khi người dùng bấm nút)
def clear_files_and_folders():
    deleted_count = clear_files_only() # Tái sử dụng hàm xóa file
    
    # Xóa luôn các thư mục rỗng
    for root, dirs, files in os.walk(DOWNLOAD_DIR, topdown=False):
        for name in dirs:
            dir_path = os.path.join(root, name)
            if not os.listdir(dir_path):
                try:
                    os.rmdir(dir_path)
                except:
                    pass
    return deleted_count

def process_offline_zalo_files():
    # [THÊM MỚI] Hàm tra cứu MST từ Database
    def get_ma_so_thue(ten_kh):
        if not ten_kh or "db" not in st.session_state:
            return ""
        try:
            sql = "SELECT ma_khach_hang FROM khach_hang WHERE ten_khach_hang = %s LIMIT 1"
            df_kh = st.session_state['db'].execute_query(sql, (ten_kh,))
            if isinstance(df_kh, pd.DataFrame) and not df_kh.empty:
                val = df_kh.iloc[0]['ma_khach_hang']
                return str(val) if pd.notna(val) else ""
        except: pass
        return ""
    
    today_str = datetime.today().strftime('%Y-%m-%d')
    tomorrow_str = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    today_date = date.today()
    
    grouped_files = get_grouped_files()
    total_groups = len(grouped_files)
    
    if total_groups == 0:
        return {"status": "info", "message": "Thư mục trống. Không có dữ liệu để xử lý."}

    reader = load_ocr_model()

    ui_group_status = st.empty()
    ui_file_status = st.empty()
    ui_progress = st.progress(0)
    ui_logs = st.empty()
    
    logs = []
    valid_records = []
    unprocessed_files = [] 
    
    # [CẬP NHẬT] Prompt mới: Gộp các điểm đến của ô merge thành 1 chuyến duy nhất và sửa lỗi nhận diện 1T
    prompt = f"""
    Bạn là chuyên gia phân tích dữ liệu Logistics. Nhiệm vụ: Chuyển đổi văn bản thành mảng JSON chứa các chuyến đi độc lập.

    **QUY TẮC 1: BÓC TÁCH DỮ LIỆU DẠNG BẢNG**
    - Mỗi dòng ngang tương ứng với 1 chuyến xe, TRỪ KHI có ô bị gộp (Merged Cells) ở cột loại xe.

    **QUY TẮC 2: BÓC TÁCH CHUỖI TEXT TỔNG HỢP**
    - Nếu khách đặt nhiều xe trong 1 tin nhắn, tách thành các object riêng biệt cho từng chuyến.

    **QUY TẮC 3: CHUẨN HÓA KHỐI LƯỢNG BOOK XE (QUAN TRỌNG NHẤT)**
    - NẾU TRONG BẢNG CÓ CỘT "OUT SIDE TRUCK" (Hoặc quy định xe mấy Tấn): Khối lượng book xe (`khoi_luong_kg`) BẮT BUỘC phải được tính ra số KG từ số Tấn của xe đó (Ví dụ: "OUT SIDE TRUCK 1T" -> 1000, "OUT SIDE TRUCK 8T" -> 8000, "2.5T" -> 2500). 
    - Các con số lớn ở cột khác (VD: 16717, 35000, 200, 703) chỉ là số lượng hàng hóa, TUYỆT ĐỐI KHÔNG lấy làm `khoi_luong_kg`. Hãy đưa các số này vào `ghi_chu` (VD: "Số lượng hàng: 35000").
    - CHỈ KHI KHÔNG CÓ cột loại xe, thì mới dùng số đứng độc lập làm `khoi_luong_kg`.

    **QUY TẮC 4: TÁCH BIỆT KHO ĐI VÀ KHO ĐẾN (LÀM SẠCH TEXT)**
    - Bắt buộc tách rõ "Địa chỉ kho đi" và "Địa chỉ kho đến". 
    - ĐẶC BIỆT: Loại bỏ các từ dư thừa như "closing time", "CLOSING TIME T7" khỏi Điểm đến. Chỉ lấy tên địa danh cốt lõi.

    **QUY TẮC 5: XỬ LÝ NGÀY THÁNG VÀ THỜI GIAN**
    - Ngày đi: "Sáng mai", "mai" -> {tomorrow_str}. "Hôm nay", "tối nay" -> {today_str}.
    - Thời gian (Giờ giấc): Có thể nằm ở cột riêng (VD: "9H") hoặc lẫn trong điểm đến. Hãy trích xuất thời gian và đưa vào trường "ghi_chu".

    **QUY TẮC 6: XỬ LÝ LOẠI XE YÊU CẦU & Ô BỊ GỘP (MERGED CELLS) - RẤT QUAN TRỌNG**
    - Nhận diện cột loại xe (thường có chữ "OUT SIDE TRUCK"). Đọc thật cẩn thận số Tấn (VD: "1T" là 1 Tấn, tuyệt đối không được đọc nhầm thành "11T"). CHỈ LẤY SỐ TẤN cho trường `loai_xe_yeu_cau` (VD: "1T", "8T").
    - NẾU Ô LOẠI XE BỊ GỘP (dùng chung cho nhiều dòng bên trái, VD: 3 điểm đến sân bay dùng chung 1 xe 1T): BẮT BUỘC CHỈ TẠO 1 CHUYẾN XE DUY NHẤT đại diện cho khối này. 
    - Hãy gộp tên của tất cả các điểm đến trong khối đó thành một chuỗi (VD: "AIR CC HỜ, AIR CC - KHO SCSC, TCS- AIR CC") và đưa vào trường `dia_chi_kho_den` (và có thể nhắc lại trong `ghi_chu`). Gán khối lượng `khoi_luong_kg` quy đổi tương ứng với chiếc xe dùng chung đó.

    **SCHEMA JSON YÊU CẦU ĐẦU RA:**
    {{
        "is_booking": true,
        "danh_sach_xe": [
            {{
                "ngay_chuyen_di": "YYYY-MM-DD",
                "dia_chi_kho_di": "Địa điểm xuất phát",
                "dia_chi_kho_den": "Điểm giao hàng (Gộp chuỗi nếu 1 xe giao nhiều điểm)",
                "khoi_luong_kg": Số thực,
                "the_tich_cbm": Số thực,
                "loai_xe_yeu_cau": "Số tấn (VD: 1T, 8T)",
                "ghi_chu": "Chi tiết giờ giấc, Số lượng hàng, Các điểm đến gộp..."
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
                    ui_file_status.write(f"👉 Phân tích file {idx}/{total_files_in_group}: `{filename}`...")
                    raw_text = ""
                    
                    if is_image:
                        ocr_result = reader.readtext(filepath, detail=0, paragraph=True)
                        raw_text = " \n".join(ocr_result)
                    else:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            raw_text = f.read()
                    
                    response = model.generate_content(prompt + f'\nNội dung cần phân tích: "{raw_text}"')
                    
                    clean_text = re.sub(r"^```json\s*", "", response.text.strip(), flags=re.IGNORECASE)
                    clean_text = re.sub(r"\s*```$", "", re.sub(r"^```\s*", "", clean_text, flags=re.IGNORECASE))
                    
                    record_count_before = len(valid_records)
                    match = re.search(r'\{.*\}', clean_text, re.DOTALL)
                    
                    if match:
                        parsed = json.loads(match.group(0))
                        if parsed.get("is_booking"):
                            for xe in parsed.get("danh_sach_xe", []):
                                xe["nhom_zalo_nguon"] = nhom
                                # [THÊM MỚI] Gán cứng Tên khách & MST từ tên thư mục tải lên
                                ten_kh_goc = nhom if nhom != "Khong_Xac_Dinh" else ""
                                xe["ten_khach_hang"] = ten_kh_goc
                                xe["ma_so_thue"] = get_ma_so_thue(ten_kh_goc)
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
                    
                    if len(valid_records) == record_count_before:
                        logs.append(f"⚠️ Không có đơn hàng: {filename}")
                        unprocessed_files.append(f"{nhom} / {filename} (Trống)")
                    else:
                        logs.append(f"✅ Bóc tách xong: {filename}")
                        
                    ui_logs.text("\n".join(logs[-4:]))
                    
                    if os.path.exists(filepath): 
                        os.remove(filepath)
                        
                    ui_progress.progress(idx / total_files_in_group)
                    
                    if idx < total_files_in_group:
                        ui_file_status.warning("⏳ Nghỉ 4s tránh nghẽn API...")
                        time.sleep(4)
                        
                except Exception as e:
                    if "429" in str(e).lower() or "quota" in str(e).lower():
                        ui_file_status.error("⚠️ Quá tải API! Nghỉ 30s...")
                        time.sleep(30)
                    else:
                        logs.append(f"❌ Lỗi: {filename}")
                        ui_logs.text("\n".join(logs[-4:]))
                        success = True 
            
            if not success:
                unprocessed_files.append(f"{nhom} / {filename}")
        
        #group_path = os.path.join(DOWNLOAD_DIR, nhom)
        #if os.path.exists(group_path) and not os.listdir(group_path):  # các dòng này xoá thư mục
        #    os.rmdir(group_path)
            
        if group_idx < total_groups:
            ui_group_status.warning(f"🛑 Xong nhóm {nhom}. Nghỉ 5s...")
            time.sleep(5)
        
        group_idx += 1
                        
    ui_progress.empty()
    ui_file_status.empty()
    ui_group_status.empty()
    ui_logs.empty()
                    
    if valid_records:
        df_new = pd.DataFrame(valid_records)
        df_new['ngay_chuyen_di'] = df_new.get('ngay_chuyen_di', 'Khong_Xac_Dinh').fillna('Khong_Xac_Dinh').astype(str)
        
        # 1. Bổ sung các cột bị thiếu (nếu AI không trích xuất được để tránh lỗi code)
        # 1. Bổ sung các cột bị thiếu (bao gồm cả cột loai_xe_yeu_cau mới)
        for col in ['ma_so_thue', 'ten_khach_hang', 'dia_chi_kho_di', 'dia_chi_kho_den', 'khoi_luong_kg', 'the_tich_cbm', 'loai_xe_yeu_cau', 'ghi_chu']:
            if col not in df_new.columns: df_new[col] = ""

        # 2. Đổi tên cột cho khớp với file mẫu
        df_export = df_new.rename(columns={
            'ngay_chuyen_di': 'NGAY_CHAY',
            'ma_so_thue': 'MA_SO_THUE',
            'ten_khach_hang': 'TEN_KHACH_HANG',
            'dia_chi_kho_di': 'DIA_CHI_KHO_DI',
            'dia_chi_kho_den': 'DIA_CHI_KHO_DEN',
            'khoi_luong_kg': 'KHOI_LUONG_KG',
            'the_tich_cbm': 'THE_TICH_CBM',
            'loai_xe_yeu_cau': 'LOAI_XE_YEU_CAU',
            'ghi_chu': 'GHI_CHU'
        })

        # 3. Sắp xếp lại thứ tự cột chuẩn xác
        columns_order = ['NGAY_CHAY', 'MA_SO_THUE', 'TEN_KHACH_HANG', 'DIA_CHI_KHO_DI', 'DIA_CHI_KHO_DEN', 'KHOI_LUONG_KG', 'THE_TICH_CBM', 'LOAI_XE_YEU_CAU', 'GHI_CHU']
        df_export = df_export[columns_order]

        
        
        # 4. KHÔNG GỘP DỮ LIỆU - PHIÊN NÀO KẾT THÚC PHIÊN ĐÓ
        if os.path.exists(EXCEL_FILE):
            try: 
                os.remove(EXCEL_FILE)
            except Exception: 
                pass
        
        # 5. Ghi đè file Excel mới tinh (Chỉ chứa data của lần quét hiện tại)
        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
            grouped = df_export.groupby('NGAY_CHAY')
            for date_str, group_df in grouped:
                sheet_name = str(date_str).split('T')[0][:31]
                group_df.to_excel(writer, sheet_name=sheet_name, index=False)
                
        return {"status": "success", "message": f"✅ Đã lưu {len(valid_records)} chuyến xe vào Excel. File sẽ tự động xóa sau khi bạn tải về.", "unprocessed": unprocessed_files}
    
    return {"status": "warning", "message": "⚠️ Không tìm thấy dữ liệu hợp lệ.", "unprocessed": unprocessed_files}
def main_app():
    # [CẬP NHẬT]: Tự động quét và xóa file của phiên làm việc trước khi mở App
    if "auto_cleaned_files" not in st.session_state:
        clear_files_only()
        st.session_state["auto_cleaned_files"] = True

    # Khởi tạo bộ đếm form key để phục vụ việc reset widget file_uploader
    if "zalo_form_reset_key" not in st.session_state:
        st.session_state["zalo_form_reset_key"] = 0

    st.title("🤖 RPA - Lấy thông tin điều xe từ file Zalo")
    
    # 📌 KHU VỰC DỌN RÁC TỒN ĐỌNG
    st.subheader("🧹 Dọn dẹp dữ liệu tồn đọng")
    st.markdown("Nếu tiến trình trước đó bị lỗi hoặc dừng đột ngột, hãy dọn rác trước khi tải file mới lên để tránh quá tải AI.")
    
    if st.button("🗑️ Dọn sạch toàn bộ File VÀ Thư mục Zalo cũ", type="secondary"):
        deleted = clear_files_and_folders()
        if deleted > 0:
            st.success(f"✅ Đã xóa thành công {deleted} file rác và dọn sạch cấu trúc thư mục!")
        else:
            st.info("✨ Thư mục hiện tại đang hoàn toàn trống.")

    st.markdown("---")
    st.subheader("📤 Tải lên dữ liệu Zalo (Hình ảnh / File Text)")
    
    existing_groups = [d for d in os.listdir(DOWNLOAD_DIR) if os.path.isdir(os.path.join(DOWNLOAD_DIR, d))]
    options = ["+ Tạo nhóm mới"] + existing_groups
    
    selected_option = st.selectbox("📂 Chọn nhóm Zalo đích (hoặc tạo mới):", options, key=f"sel_group_{st.session_state['zalo_form_reset_key']}")
    
    if selected_option == "+ Tạo nhóm mới":
        group_name_input = st.text_input("Nhập tên nhóm Zalo mới:", key=f"input_new_group_{st.session_state['zalo_form_reset_key']}").strip()
    else:
        group_name_input = selected_option
    
    
    # 📌 SỬ DỤNG FORM BỌC ĐỂ CHO PHÉP RESET TRẮNG WIDGET FILE_UPLOADER
    form_key = f"zalo_upload_form_{st.session_state['zalo_form_reset_key']}"
    
    # [CẬP NHẬT 1]: Thêm clear_on_submit=True để tự động dọn dẹp form khi submit
    with st.form(key=form_key, clear_on_submit=True):
        
        # [CẬP NHẬT 2]: Gắn key động trực tiếp vào file_uploader
        uploaded_files = st.file_uploader(
            "Chọn các file ảnh (.jpg, .png) hoặc văn bản (.txt) cần xử lý:", 
            type=["jpg", "jpeg", "png", "txt"], 
            accept_multiple_files=True,
            key=f"uploader_zalo_{st.session_state['zalo_form_reset_key']}"
        )
        
        submitted_upload = st.form_submit_button("📥 Lưu file lên hệ thống Cloud", type="primary", use_container_width=True)
        
        if submitted_upload:
            if not group_name_input:
                st.error("❌ Vui lòng chọn hoặc nhập tên nhóm Zalo đích!")
            elif not uploaded_files:
                st.warning("⚠️ Vui lòng chọn ít nhất một file để tải lên!")
            else:
                target_group_dir = os.path.join(DOWNLOAD_DIR, group_name_input)
                os.makedirs(target_group_dir, exist_ok=True) 
                
                saved_count = 0
                for uploaded_file in uploaded_files:
                    file_path = os.path.join(target_group_dir, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    saved_count += 1
                    
                st.success(f"✅ Đã tải lên thành công {saved_count} file vào nhóm `{group_name_input}`.")
                
                # [CẬP NHẬT 3]: Tăng biến đếm và load lại trang để xóa hoàn toàn file trên UI
               
                time.sleep(1.2)
                st.session_state["zalo_form_reset_key"] += 1
                st.rerun()

    st.markdown("---")
    st.subheader("⚙️ Xử lý dữ liệu")
    
    if st.button("🚀 Bắt đầu phân tích AI", type="primary", use_container_width=True):
        with st.spinner("Đang kết nối thư viện OCR và Gemini AI..."):
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

        
    st.markdown("---")
    st.subheader("📥 Tải kết quả tổng hợp")
    
    if os.path.exists(EXCEL_FILE):
        try:
            # 1. Đọc TRỰC TIẾP file tạm mà hệ thống vừa sinh ra từ lần AI chạy gần nhất
            df_preview = pd.read_excel(EXCEL_FILE)
            
            # Lọc bỏ cột GHI_CHU nếu nó bị rỗng hoàn toàn để bảng preview nhìn gọn gàng hơn
            if 'GHI_CHU' in df_preview.columns and df_preview['GHI_CHU'].isnull().all():
                df_preview = df_preview.drop(columns=['GHI_CHU'])
                
            st.markdown("##### 👁️‍🗨️ XEM TRƯỚC DỮ LIỆU ĐÃ BÓC TÁCH (PREVIEW)")
            st.info("Vui lòng kiểm tra kỹ các cột Ngày, Khách hàng, Điểm đi/đến, và Tải trọng trước khi lưu về máy.")
            st.dataframe(df_preview, use_container_width=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # 2. Xử lý nút Tải về
            with open(EXCEL_FILE, "rb") as file:
                file_bytes = file.read()
                
            # Gán biến da_tai_xong để bắt sự kiện click của người dùng
            da_tai_xong = st.download_button(
                label="✅ TÔI XÁC NHẬN DỮ LIỆU ĐÚNG - TẢI XUỐNG NGAY",
                data=file_bytes,
                file_name=f"Book_Xe_{datetime.now().strftime('%H%M%S_%d%m%Y')}.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Nút thủ công (dành cho trường hợp thấy data bị sai, muốn hủy bỏ)
            if st.button("❌ Xóa trắng để quét lại", type="secondary", use_container_width=True):
                da_tai_xong = True # Ép chạy logic xóa bên dưới
                
            # NẾU NGƯỜI DÙNG ĐÃ BẤM TẢI XONG (HOẶC BẤM HỦY) -> LẬP TỨC DỌN SẠCH HỆ THỐNG
            if da_tai_xong:
                try:
                    if os.path.exists(EXCEL_FILE):
                        os.remove(EXCEL_FILE)
                except Exception: pass
                
                clear_files_only() # Xóa luôn các ảnh Zalo đầu vào
                
                st.session_state["zalo_form_reset_key"] += 1
                st.toast("🎉 Hệ thống đã tự động dọn sạch file rác của phiên làm việc này.")
                time.sleep(1.5)
                st.rerun()
                
        except Exception as e:
            st.error(f"Lỗi hiển thị dữ liệu Preview: {e}")
    else:
        st.info("Chưa có dữ liệu Excel nào được xuất ra trên hệ thống.")
if __name__ == "__main__":
    main_app()