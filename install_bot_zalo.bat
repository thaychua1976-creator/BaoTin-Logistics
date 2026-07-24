@echo off
chcp 65001 >nul
echo =========================================================
echo    CÀI ĐẶT MÔI TRƯỜNG CHẠY BOT ZALO - BẢO TÍN LOGISTICS
echo =========================================================
echo.
echo LƯU Ý TRƯỚC KHI CÀI ĐẶT:
echo Máy tính này bắt buộc phải có sẵn:
echo 1. Trình duyệt Google Chrome
echo 2. Python (Đảm bảo đã tích chọn "Add python.exe to PATH" lúc cài)
echo.
echo Nếu đã cài đủ, hãy nhấn phím bất kỳ để bắt đầu tải thư viện...
pause >nul

echo.
echo Đang cập nhật công cụ quản lý gói (pip)...
python -m pip install --upgrade pip

echo.
echo Đang cài đặt thư viện phần mềm (Streamlit, Selenium, Pandas,...)...
pip install streamlit pandas selenium pyperclip openpyxl mysql-connector-python

echo.
echo =========================================================
echo HOÀN TẤT CÀI ĐẶT!
echo Môi trường đã sẵn sàng để điều hành xe.
echo =========================================================
echo.
pause