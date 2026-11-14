# Báo cáo cá nhân — Day 6 · Data Ingestion Engineering

- **Họ và tên:** Trương Văn Phong
- **MSSV:** 2A202604091
- **Lớp:** L3B
- **Chủ đề & Corpus:** Hướng dẫn ứng phó khẩn cấp VinFast VF 8 EV SUV (First Responder's Guide - FRG)
- **Repository:** https://github.com/vanphong205/K5-L3B-DAY06-TruongVanPhong-2A202604091-DataIngestion

---

## 1. Dữ liệu và Pipeline

### 1.1. Chủ đề, Nguồn quyền, Số trang và Quy tắc tính trang
- **Chủ đề tài liệu:** Hướng dẫn kỹ thuật ứng phó tình huống khẩn cấp, cứu hộ, vô hiệu hóa nguồn điện cao áp, xử lý cháy nổ và kéo cứu hộ dành riêng cho dòng xe điện SUV VinFast VF 8.
- **Nguồn và giấy phép:** Tài liệu PDF chính thức do VinFast phát hành công khai phục vụ các đội cứu hỏa, cảnh sát và cứu hộ khẩn cấp (`docs/VF8_FRG_VI_1690188048.pdf`). Dữ liệu được sử dụng phi thương mại cho mục đích học thuật, nghiên cứu và kiểm thử pipeline Data Ingestion trong bài lab.
- **Số trang & quy tắc tính:**
  + Tổng số trang vật lý: **25 trang**.
  + Các trang phi nội dung (loại trừ theo quy tắc): Trang 1 (Bìa), Trang 2 (Thông báo pháp lý), Trang 3 (Giới thiệu & Mục lục), Trang 4 (Cảnh báo nguy hiểm chung).
  + Số trang nội dung kỹ thuật trực tiếp: **21 trang** (từ Trang 5 đến Trang 25), bao gồm trọn vẹn 10 chương mục cứu hộ kỹ thuật chuẩn (`Section 0` đến `Section 9`).
  + *Ghi chú hạn chế:* Mặc dù quy chuẩn đề bài khuyến nghị ≥30 trang, việc bảo toàn tính toàn vẹn của một tài liệu kỹ thuật nguyên bản chuẩn mực (25 trang vật lý, 21 trang nội dung) mang lại giá trị thực tiễn và tính nhất quán cao hơn so với việc gộp các tài liệu không liên quan. Chi tiết được phân tích ở mục Hạn chế.

### 1.2. Chuẩn hóa, Xử lý lỗi và Giới hạn bóc tách
- **Công cụ bóc tách:** Kết hợp `Docling 2.150` (layout-aware document parsing nhận diện tiêu đề cấp bậc, danh sách, thứ tự đọc và trích xuất hình ảnh) và `pypdf 6.21.4` (cho các trang bảng tổng quan kỹ thuật có text lồng ghép phức tạp).
- **Chuẩn hóa văn bản:**
  + Chuẩn hóa Unicode theo định dạng `NFKC`.
  + Loại bỏ các ký tự ẩn, zero-width (`\u200b`, `\ufeff`, v.v.).
  + Chuẩn hóa khoảng trắng liên tục và ngắt dòng dư thừa (`\n{3,}`).
  + Bóc tách và quản lý metadata cho **36 hình ảnh/sơ đồ kỹ thuật** (loại bỏ các icon cảnh báo nhỏ < 150px).
- **Giới hạn bóc tách:** Tại Trang 5 (Bảng tổng quan cứu hộ), Docling không nhận diện trọn vẹn các nhãn text nằm bên trong các linh kiện vector graphic; hệ thống đã kích hoạt fallback cơ chế đọc trực tiếp text layer qua `pypdf` và lưu vết vào `metadata["text_source"] = "pypdf"`.

### 1.3. Embedding Model, Vector Store và Chi phí Vận hành
- **Embedding Model:** `nomic-embed-text` (v1.5) chạy local thông qua máy chủ `Ollama` (`http://127.0.0.1:11434`).
  + Số chiều vector: **768 dimensions**.
  + Prefix định dạng: `search_document: <text>` khi nhúng chunk tài liệu và `search_query: <question>` khi nhúng câu hỏi người dùng (tuân thủ đặc tả của Nomic để tối ưu hóa không gian biểu diễn đa ngữ).
- **Vector Store:** `PostgreSQL 16.16` kết hợp extension `pgvector 0.8.7` chạy Docker Compose độc lập tại cổng `127.0.0.1:55433`.
  + Bảng lưu trữ: `document_chunks`.
  + Phép đo khoảng cách: Cosine Distance (`<=>`), điểm tương đồng Cosine Similarity tính bằng công thức `1 - (embedding <=> query::vector)`.
  + Chỉ mục (Indexes): Chỉ mục `GIN` trên trường `metadata` (JSONB), chỉ mục B-tree trên `strategy`, `document_id`, `section`, và `section_no` nhằm tối ưu hóa truy vấn lọc kết hợp vector ranking.
- **Lệnh chạy:** Khởi động database `docker compose -p day6_student_starter up -d` và thực thi toàn bộ pipeline bằng lệnh `python -m src.run`.
- **Chi phí vận hành:** **$0.00 USD** (100% On-Premise, chạy hoàn toàn local qua Ollama và Docker, không phụ thuộc vào API thương mại bên ngoài).

### 1.4. Metadata Quản lý và Trường Lọc Bổ Sung
- **Metadata bắt buộc:** `document_id`, `source`, `page`.
- **Trường lọc bổ sung:**
  + `section` (chuỗi): Tên đầy đủ của chương mục cứu hộ (VD: "3. Loại bỏ Mối nguy hiểm Trực tiếp").
  + `section_no` (số nguyên: 0 đến 9): Mã định danh số của chương mục kỹ thuật.
  + `chunk_index`, `strategy`, `char_count`, `has_text`, `images`.
- **Nguồn giá trị và Lý do chọn `section_no`:** Giá trị `section_no` được trích xuất trực tiếp và tin cậy tuyệt đối từ cấu trúc đánh số mục của tài liệu VinFast ("0. ...", "1. ...", ..., "9. ..."). Trong các cẩm nang cứu hộ xe điện, mỗi chương mục đại diện cho một pha hành động nghiệp vụ biệt lập (ổn định xe, ngắt điện cao áp, tiếp cận cabin, dập lửa, kéo xe). Việc lọc theo `section_no` cho phép loại bỏ hoàn toàn các thông tin gây nhiễu chéo từ các chương khác, ví dụ như các câu cảnh báo an toàn điện cao áp xuất hiện lặp đi lặp lại ở hầu hết các trang.

---

## 2. Cấu hình và Benchmark

### 2.1. Ba Chiến lược Dữ liệu (A / B / C)
- **Chiến lược A (Fixed-size Window):**
  + Tham số: Cửa sổ cố định `size = 500 ký tự`, bước nhảy dịch chuyển với độ gối đầu `overlap = 50 ký tự`.
  + Metadata: Lưu đầy đủ `document_id`, `source`, `page`, `section`, `section_no`.
  + Cơ chế tìm kiếm: Vector cosine search thuần túy, không lọc metadata.
- **Chiến lược B (Structure-aware Paragraph Chunking):**
  + Tham số: Gom cụm theo cấu trúc đoạn văn bản và tiêu đề Markdown của Docling, ngưỡng kích thước tối đa `max_size = 800 ký tự`. Các đoạn văn ngắn liên tiếp cùng chủ đề được gom gộp; các đoạn quá dài được phân rã đệ quy theo dấu ngắt câu hoặc ngắt dòng.
  + Metadata: Giữ nguyên bộ metadata tương tự Chiến lược A.
  + Cơ chế tìm kiếm: Vector cosine search thuần túy, không lọc metadata.
- **Chiến lược C (Paragraph Chunking + Metadata Filtering):**
  + Tham số chunk: Hoàn toàn tái sử dụng tập chunk của Chiến lược B (cùng model, cùng số lượng 33 chunks, cùng tham số nhúng).
  + Điểm khác biệt duy nhất so với B: Áp dụng cơ chế **Metadata Pre-filtering** trên trường `section_no` trong truy vấn SQL PostgreSQL khi câu hỏi có chỉ định phạm vi nghiệp vụ trước khi thực hiện tìm kiếm vector k-NN (`WHERE strategy = 'by_paragraph' AND section_no = %s`). Đối với các câu hỏi không có bộ lọc, C tự động chạy un-filtered giống B.

### 2.2. Bộ Benchmark và Quy trình Kiểm chứng Gold Evidence
- **Quy mô:** Cố định **20 câu hỏi kỹ thuật** trước khi thực nghiệm, phân chia độc lập thành:
  + **Tập Dev:** 15 câu (chiếm 75%) phục vụ khảo sát, tinh chỉnh và chọn lựa cấu hình.
  + **Tập Test:** 5 câu (chiếm 25%) làm tập kiểm thử độc lập (holdout).
- **Phân loại câu hỏi:**
  + Trực tiếp (Direct - 8 câu): `q01`, `q02`, `q04`, `q09`, `q12`, `q15`, `q17`, `q20`.
  + Diễn đạt lại (Paraphrase - 5 câu): `q06`, `q11`, `q13`, `q18`.
  + Điều kiện / Ngoại lệ (Conditional - 4 câu): `q03`, `q07`, `q08`, `q14`, `q19`.
  + Metadata Filter (3 câu: 2 dev, 1 test): `q05` (lọc section 3), `q10` (lọc section 4), `q16` (lọc section 8).
- **Kiểm chứng Gold Evidence:** Từng đoạn trích `evidence_quote` và số trang `gold_page` được kiểm tra thủ công đối chiếu nguyên văn với văn bản sau chuẩn hóa; đảm bảo 100% bằng chứng có thực và chứa đủ dữ liệu để trả lời câu hỏi.

### 2.3. Tiêu chí Chọn Chiến lược Tối ưu
Tiêu chí được quyết định **trước khi đánh giá tập Test**:
1. Ưu tiên hàng đầu: Tối đa hóa **Evidence Hit@3** trên tập Dev.
2. Tiêu chí thứ hai: **Tính mạch lạc của Chunk (Coherence)** đạt điểm trung bình ≥ 1.8 / 2.0 (không chấp nhận việc chunk bị chém gãy câu chữ giữa chừng).
3. Tiêu chí thứ ba: Khả năng bảo vệ chất lượng grounding và loại bỏ nhiễu bằng metadata filter.

---

## 3. Kết quả Thực nghiệm

### 3.1. Bảng Chỉ số Đo lường Định lượng (Retrieval Performance)

| Chiến lược | Phân tập (Split) | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Số lượng Chunk | Thời gian truy xuất (20 câu) | Chi phí |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **A (fixed_size)** | **Dev** | 4/15 (26.7%) | 6/15 (40.0%) | 46 chunks | 1.61s | $0.00 |
| **A (fixed_size)** | **Test** | 2/5 (40.0%) | 2/5 (40.0%) | 46 chunks | 1.61s | $0.00 |
| **B (by_paragraph)** | **Dev** | 4/15 (26.7%) | 7/15 (46.7%) | 33 chunks | 1.87s | $0.00 |
| **B (by_paragraph)** | **Test** | 2/5 (40.0%) | 3/5 (60.0%) | 33 chunks | 1.87s | $0.00 |
| **C (by_para + filter)** | **Dev** | 4/15 (26.7%) | **8/15 (53.3%)** | 33 chunks | 1.64s | $0.00 |
| **C (by_para + filter)** | **Test** | 2/5 (40.0%) | **3/5 (60.0%)** | 33 chunks | 1.64s | $0.00 |

### 3.2. Bảng Đánh giá Thủ công 5 Khía cạnh (Manual Audit)

| Chiến lược | Chunk Coherence trung bình /2 (n=10) | Metadata Đủ và Đúng (n/N, n=15) | Tỷ lệ Tuân thủ Filter (n/N) | Grounding Mức 0 / 1 / 2 (Số câu test) & Trung bình /2 |
|:---|:---:|:---:|:---:|:---:|
| **A (fixed_size)** | 1.50 / 2.0 (15/20 đ) | 15/15 (100%) | N/A (Không áp dụng) | [0: 2 câu, 1: 0 câu, 2: 3 câu] → **1.20 / 2.0** |
| **B (by_paragraph)** | **2.00 / 2.0** (20/20 đ) | 15/15 (100%) | N/A (Không áp dụng) | [0: 1 câu, 1: 0 câu, 2: 4 câu] → **1.60 / 2.0** |
| **C (by_para + filter)** | **2.00 / 2.0** (20/20 đ) | 15/15 (100%) | **1/1 (100%)** test <br> *(3/3 toàn bộ benchmark)* | [0: 1 câu, 1: 0 câu, 2: 4 câu] → **1.60 / 2.0** |

### 3.3. Chi tiết Đánh giá Chunk Coherence (10 Vị trí Cố định)
Kiểm tra trên 10 trang nội dung cố định: Trang 6, 7, 8, 9, 10, 11, 12, 15, 19, 20:
- **Chiến lược A (1.50/2.0):** Bị đứt đoạn ngữ nghĩa nghiêm trọng tại 5 vị trí:
  + Trang 10: Chunk 0 bị cắt ngang từ khóa `"MSD"` thành `"...nằm trong cổng sạc. MS"`; Chunk 1 bắt đầu bằng `"n ngắt dịch vụ cơ học..."` (mất hẳn chữ "Bộ phậ"). Điểm: 1/2.
  + Trang 11: Chunk 0 bị ngắt giữa chừng ở `"nhân viên ứng"` (mất chữ "phó đầu tiên"); Chunk 1 cắt đôi câu ở `"VF8 sẽ tự độ"` (mất chữ "ng tắt máy"). Điểm: 1/2.
  + Trang 12: Quy trình tháo phích sạc thủ công bị chia cắt làm hai nửa. Điểm: 1/2.
  + Trang 19: Chunk 0 bị đứt câu tại `"Khi ngắt kết nố"`; Chunk 1 chỉ là mảnh vụn 96 ký tự `"điện HV đi vào..."`. Điểm: 1/2.
  + Trang 20: Danh sách hướng dẫn dập lửa bị cắt đôi ở `"- Theo d"` (mất chữ "õi nhiệt độ"). Điểm: 1/2.
- **Chiến lược B (2.00/2.0):** Toàn bộ 10 vị trí đều giữ nguyên vẹn câu, ngữ cảnh danh sách và tiêu đề; mỗi chunk là một đơn vị thông tin độc lập, tự hiểu được hoàn toàn mà không bị mất từ hay gãy ý.

### 3.4. Chi tiết Grounding Quality (5 Câu Test)
- `q16` (Cách ly xe sau va chạm, Page 22):
  + A: Mức 2 (Rank 1 trúng chunk p22_c001).
  + B: Mức 2 (Rank 1 trúng chunk p22_c000).
  + C: Mức 2 (Nhờ filter, 100% top-3 đều thuộc Section 8, độ tin cậy tuyệt đối).
- `q17` (Vận chuyển cẩu kéo bằng xe sàn trượt, Page 23):
  + A: **Mức 0** (Trượt hoàn toàn top-3 do chunk bị cắt vụn, score thấp hơn các chunk trang 22 và trang 16).
  + B: **Mức 2** (Rank 1 trúng trọn vẹn chunk p23_c000: đặt 4 bánh lên sàn xe tải kéo, không chạm đường).
  + C: **Mức 2** (Tương tự B).
- `q18` (Nguy cơ quay bánh xe phát điện vào EDS, Page 23):
  + A: **Mức 0** (Trượt top-3).
  + B: **Mức 0** (Trượt top-3).
  + C: **Mức 0** (Trượt top-3 do câu hỏi không có filter; mô hình embedding bị nhiễu ngữ nghĩa).
- `q19` (Bung túi khí ngắt điện cao áp, Page 24):
  + A: Mức 2 (Rank 3 trúng p24_c000).
  + B: Mức 2 (Rank 3 trúng p24_c000).
  + C: Mức 2 (Rank 3 trúng p24_c000).
- `q20` (Bộ căng đai an toàn viền đỏ ở cột B, Page 25):
  + A: Mức 2 (Rank 1 trúng p25_c000).
  + B: Mức 2 (Rank 1 trúng p25_c000).
  + C: Mức 2 (Rank 1 trúng p25_c000).

- **Đường dẫn artifacts:**
  + Trace chi tiết 60 lượt truy xuất: `results/traces.json`.
  + File metrics tổng hợp: `results/metrics.json` và `results/benchmark_summary.md`.
  + Script kiểm tra audit: `starter/scripts/audit_analysis.py` và `starter/scripts/audit_coherence.py`.

---

## 4. Phân tích và Kết luận

### 4.1. So sánh Chiến lược và Hai Ví dụ Sai Cụ thể
- **So sánh A – B (Tác động của Chunking Strategy):**
  + Chuyển từ Fixed-size sang Structure-aware Chunking giúp giảm số lượng chunk từ 46 xuống 33 (tiết kiệm 28.3% dung lượng vector store).
  + Evidence Hit@3 tăng từ 40.0% lên 46.7% ở tập Dev, và tăng vọt từ 40.0% lên **60.0% (+20%)** ở tập Test.
  + Coherence tăng từ 1.5 lên 2.0. Việc giữ nguyên vẹn ranh giới đoạn giúp vector embedding bao hàm đầy đủ ngữ nghĩa của cả quy trình thao tác thay vì những mảnh câu cụt lủn.
- **So sánh B – C (Tác động của Metadata Filtering):**
  + B và C dùng chung hoàn toàn bộ chunk. Việc bổ sung bộ lọc metadata `section_no` trong C đã giúp Hit@3 ở tập Dev tăng từ 46.7% lên **53.3%** (tăng thêm 1 câu `q05` từ trượt thành trúng).
  + Tỷ lệ tuân thủ filter đạt **100%** (1/1 câu test, 3/3 toàn bộ benchmark). Các chunk rác ở những chương khác bị loại bỏ hoàn toàn khỏi không gian k-NN search.

#### Hai ví dụ sai cụ thể:
1. **Ví dụ 1: Câu `q17` (Strategy A Thất bại – Strategy B Thành công)**
   - *Nội dung câu hỏi:* "Phương pháp vận chuyển bắt buộc đối với xe VinFast VF 8 bằng xe cứu hộ chuyên dụng là gì?"
   - *Gold Evidence (Page 23):* "Phải đặt toàn bộ VF8 lên sàn xe tải kéo để vận chuyển. Cài xe về số mo (N), nhả phanh tay và tắt xe. Khi được kéo đi, các bánh xe không được phép tiếp xúc với mặt đường."
   - *Phân tích:* Ở Strategy A, trang 23 bị cắt cứng ở 500 ký tự khiến cụm từ "vận chuyển xe" bị phân tán khỏi ngữ cảnh các biện pháp an toàn. Khi tính cosine similarity, các chunk ở Page 22 (score 0.7770 ở Rank 1, 0.7725 ở Rank 2) và Page 16 (score 0.7723 ở Rank 3) có độ tương đồng bề mặt cao hơn nên đã chiếm trọn top-3. Hệ quả là Strategy A trượt hoàn toàn. Ngược lại, Strategy B bảo toàn toàn bộ đoạn văn cẩu kéo thành một chunk duy nhất (`p23_c000`), đạt score 0.7766 và xếp ngay vị trí Rank 1.
2. **Ví dụ 2: Câu `q18` (Cả 3 Chiến lược cùng thất bại Top-3)**
   - *Nội dung câu hỏi:* "Tại sao không được phép để các bánh xe của VF 8 tiếp xúc mặt đường và quay tự do trong quá trình cẩu kéo?"
   - *Gold Evidence (Page 23):* "Xoay bánh xe có thể tạo ra điện trong EDS. Điều này có thể khiến linh kiện HV nóng quá mức hoặc gây hư hỏng thêm."
   - *Phân tích:* Đây là câu hỏi dạng Diễn đạt lại (Paraphrase) với sắc thái hỏi về nguyên nhân vật lý/hậu quả kỹ thuật. Mô hình embedding `nomic-embed-text` khi không thấy từ khóa "EDS" trong câu hỏi đã bị đánh lừa bởi các từ "không được phép", "bánh xe", "quay", và đã ưu tiên xếp các chunk nói về quy trình ngắt điện tại Page 11 (Rank 1: 0.7755) và vùng cắt nguy hiểm tại Page 16 (Rank 2: 0.7532). Đoạn văn vàng ở trang 23 khá ngắn (154 ký tự), khiến vector ngữ nghĩa bị loãng khi so khớp với câu hỏi dạng nguyên nhân.

### 4.2. Chiến lược Được Chọn, Đánh đổi và Điều kiện Áp dụng
- **Chiến lược được lựa chọn:** **Chiến lược C (Structure-aware Paragraph Chunking kết hợp Metadata Pre-filtering)**.
- **Đánh đổi (Trade-offs):**
  + Để áp dụng C, tầng ứng dụng (AI Agent / Router) hoặc người dùng phải cung cấp được phạm vi nghiệp vụ (`section_no`). Nếu phân loại sai section ngay từ đầu, hệ thống sẽ lọc nhầm và bỏ sót bằng chứng (False Negative).
  + Tuy nhiên, kiến trúc của C có tính linh hoạt cao: khi câu hỏi không có metadata filter, hệ thống tự động suy biến về Chiến lược B một cách an toàn mà không làm gián đoạn trải nghiệm người dùng.
- **Điều kiện áp dụng:** Cực kỳ lý tưởng cho các hệ thống tài liệu kỹ thuật có cấu trúc chương mục phân cấp rõ ràng (sách hướng dẫn sửa chữa, quy chuẩn vận hành, văn bản pháp luật, tài liệu y tế).

### 4.3. Hạn chế của Thí nghiệm
1. **Dung lượng tập dữ liệu:** Tài liệu VinFast VF 8 FRG gồm 25 trang vật lý và 21 trang kỹ thuật thực tế (ít hơn mức khuyến nghị 30 trang). Dù vậy, dữ liệu có mật độ kỹ thuật dày đặc và cấu trúc section hoàn chỉnh, đủ để phản ánh chân thực hành vi của các chiến lược.
2. **Quy mô tập Test nhỏ (5 câu):** Khi tập test chỉ có 5 câu, mỗi câu trả lời đúng/sai làm chỉ số Hit biến động tới 20%. Kết quả này đóng vai trò minh chứng khái niệm (Proof-of-Concept) hơn là một kết luận thống kê tuyệt đối.
3. **Mô hình Embedding đa ngữ:** `nomic-embed-text` xử lý tốt tiếng Việt thông dụng nhưng vẫn có hạn chế với các câu hỏi mang tính suy luận nguyên nhân kỹ thuật chuyên sâu (như trường hợp câu `q18`).

### 4.4. Đề xuất Cải tiến Mở rộng
Nếu có thêm thời gian phát triển, hai hướng nâng cấp giá trị nhất gồm:
1. **Hybrid Retrieval (Dense + Sparse BM25):** Kết hợp vector similarity của pgvector với Full-Text Search tiếng Việt (`pg_trgm` hoặc `tsvector`) để bù đắp các từ khóa kỹ thuật hiếm (như "EDS", "MSD", "bộ căng đai").
2. **Tích hợp Reranker:** Bổ sung mô hình Cross-Encoder (như `BAAI/bge-reranker-v2-m3`) để xếp hạng lại top-10 chunk ứng viên trước khi lấy top-3, giải quyết triệt để các câu hỏi diễn đạt lại phức tạp.
