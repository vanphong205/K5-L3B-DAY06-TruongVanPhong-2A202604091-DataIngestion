# Bộ Benchmark Đánh giá Hệ thống Data Ingestion (VinFast VF 8 FRG)

Bộ benchmark gồm **20 câu hỏi kỹ thuật** được trích xuất và xác thực trực tiếp từ tài liệu chính thức *VinFast VF8 EV SUV Hướng dẫn ứng phó khẩn cấp (First Responder's Guide)*.

## 1. Cấu trúc và Phân chia Split

Bộ câu hỏi được cố định và phân chia độc lập **trước khi chạy thử nghiệm**:
- **Tập Dev (15 câu - 75%):** Dùng để phân tích hành vi, so sánh và lựa chọn chiến lược dữ liệu tối ưu.
- **Tập Test (5 câu - 25%):** Dùng để kiểm thử độc lập (holdout evaluation) nhằm kiểm chứng khả năng tổng quát hóa của chiến lược đã chọn.

## 2. Phân loại Câu hỏi

Nhằm kiểm tra đa chiều khả năng của pipeline retrieval, bộ câu hỏi bao gồm:
- **Trực tiếp (Direct - 8 câu):** Truy vấn trực tiếp các thông số kỹ thuật, vị trí linh kiện (VD: vị trí VIN `q01`, mở nắp ca-pô `q09`, vị trí bộ căng đai `q20`).
- **Diễn đạt lại (Paraphrase - 5 câu):** Sử dụng ngôn từ ngữ nghĩa khác biệt so với văn bản gốc để thử thách khả năng semantic search của embedding model (VD: khoảng cách an toàn chìa khóa `q06`, màu nhận diện cáp HV `q11`, nguy cơ quay bánh xe `q18`).
- **Điều kiện / Ngoại lệ (Conditional / Exception - 4 câu):** Các tình huống sự cố đặc biệt hoặc ngoại lệ (VD: hỏng tay nắm cửa ngoài `q08`, mất điện 12V `q10`, túi khí bung `q19`).
- **Metadata Filter (3 câu: 2 dev, 1 test):** Các câu hỏi kiểm thử truy xuất kết hợp bộ lọc metadata theo chương mục (`section_no`).
  + `q05` (Dev): Lọc theo `section_no = 3` (Loại bỏ Mối nguy hiểm Trực tiếp).
  + `q10` (Dev): Lọc theo `section_no = 4` (Tiếp cận Người ngồi trong xe).
  + `q16` (Test): Lọc theo `section_no = 8` (Kéo xe, Vận chuyển, Bảo quản).

## 3. Cấu trúc trường dữ liệu
Mỗi bản ghi trong `questions.json` bao gồm:
- `id`: Mã định danh câu hỏi (`q01` -> `q20`).
- `split`: Tập phân chia (`dev` hoặc `test`).
- `question_type`: Thể loại câu hỏi (`truc_tiep`, `dien_dat_lai`, `dieu_kien_ngoai_le`, `metadata_filter`).
- `question`: Nội dung câu hỏi.
- `expected_answer`: Câu trả lời ngắn gọn, chuẩn xác.
- `gold_source_id`: Mã định danh tài liệu nguồn (`vf8-frg-vi-1690188048`).
- `gold_page`: Số trang vật lý chứa bằng chứng chính xác.
- `evidence_quote`: Đoạn trích nguyên văn từ tài liệu dùng làm bằng chứng xác thực (Ground Truth).
- `filter`: Điều kiện lọc metadata (nếu có).
