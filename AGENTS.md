# AGENTS.md

### Hướng dẫn cho AI coding agent (Claude Code, Cursor, v.v.) khi làm việc trong repo này

---

## Đọc trước khi làm bất cứ việc gì

1. `PROJECT_CONTEXT.md` — bài toán, ràng buộc nghiệp vụ, pitch
2. `ARCHITECTURE.md` — pipeline, mapping công nghệ, cấu trúc thư mục
3. `TASK.md` — việc đã xong / đang làm / sắp làm

**Không thiết kế lại kiến trúc trừ khi được yêu cầu rõ ràng.** Nếu thấy vấn đề trong thiết kế hiện tại, hãy nêu ra và hỏi trước khi tự ý đổi.

---

## Quy tắc code bắt buộc (non-negotiable)

1. **Không dùng LLM cho Fact Engine / Pattern Engine / Policy Engine.** Đây là logic rule-based thuần, phải chính xác 100% về số liệu. LLM chỉ dùng ở Output Generator và Engagement Engine.
2. **Mọi Fact phải có `evidence` truy vết được** về dữ liệu gốc (transaction_id, ngày tháng, số liệu cụ thể).
3. **Safety Engine là gate bắt buộc**, áp dụng cho CẢ Observation/Nudge (P5) VÀ Challenge/Reward wording (P6) — không được bỏ qua bước này ở bất kỳ nhánh nào.
4. **Không bịa dữ liệu khi thiếu.** Nếu 1 field cần thiết cho 1 loại nudge không có trong dữ liệu khách hàng, Data Checker phải chặn việc tạo nudge đó — không suy diễn thay.
5. **Product Catalog là nguồn sự thật duy nhất về sản phẩm.** Không để LLM tự "biết" thông tin sản phẩm — luôn tra cứu `product_catalog.py`.
6. **Policy Engine không dùng balance/số dư làm điều kiện kích hoạt nudge.** Chỉ check eligibility (KYC, tuổi, jurisdiction, data availability, opt-out status).
7. **Mọi quyết định (kể cả bị từ chối) phải được Audit Logger ghi lại**, kèm lý do.
8. **Code phải chạy được với `MOCK_LLM=true`** — không bao giờ để demo phụ thuộc hoàn toàn vào việc cloud/LLM API available. Luôn có fallback template rule-based.
9. **Không dựng microservices thật.** Đây là modular monolith — 1 backend FastAPI, module hóa rõ theo tên, gọi hàm trực tiếp trong cùng process.
10. **Đừng viết thêm tài liệu kiến trúc mới.** Nếu cần cập nhật, sửa trực tiếp `ARCHITECTURE.md`/`TASK.md`, không tạo file doc mới.
11. **Môi trường chạy bắt buộc sử dụng Python >= 3.10.** Tuyệt đối không dùng Python 3.7 hay các bản cũ hơn để tránh lỗi không tương thích ABI và Pydantic v2.

---

## Wording bị cấm (Safety Engine phải chặn các cụm sau, không phân biệt hoa thường)

```
nên, khuyên, guaranteed, risk-free, you should, grow your money,
grow idle cash, optimize return, better use of your balance,
put idle money to work, maximize earnings, safe return,
diversify beyond cash, move x% of your balance
```

Challenge (P6) ưu tiên verb: `learn about, review, compare information, complete a tutorial on`
Challenge (P6) cấm verb: `deposit into, move money to, activate, invest in, transfer to, borrow more`

---

## Thứ tự implement (xem chi tiết trạng thái ở TASK.md)

```
product_catalog.py → data_checker.py → fact_pattern_engine.py →
policy_engine.py → safety_engine.py (rule-based) → run_demo.py (end-to-end local)
→ [sau khi có bản chạy được] → output_generator.py (LLM) → engagement_engine.py (LLM)
→ audit_logger.py hoàn chỉnh → API → dashboard
```

**Nguyên tắc ưu tiên:** Có 1 bản `run_demo.py` chạy end-to-end bằng template/rule-based TRƯỚC, rồi mới thay dần bằng LLM. Không để LLM/cloud block tiến độ.

---

## Khi nào hỏi lại người dùng thay vì tự quyết

- Khi phải đổi ràng buộc non-advisory hoặc nới lỏng Safety Engine
- Khi cần thêm dependency/package mới ngoài: `pydantic`, `fastapi`, `anthropic` (hoặc `boto3` nếu dùng Bedrock)
- Khi phát hiện mâu thuẫn giữa `PROJECT_CONTEXT.md` và `ARCHITECTURE.md`
