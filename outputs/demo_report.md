# Demo results

LLM mode: `llm:openai/gpt-oss-120b`


## 1. Excel test question for WF001

*Checks:* Tests workflow selection and threshold logic

```text
Request: Which products need restocking?

Selected Workflow: WF001 - Inventory Restock Check
Routing: llm, confidence 0.99
Why: User asks which products need restocking, matching WF001 trigger
Alternatives: WF002 (0.758), WF004 (0.758)
Inputs: (none extracted)
Defaults used (sample data / settings): inventory_path, reorder_multiplier

Steps Executed:
  1. [OK] Load inventory  (8.8 ms)  tools: csv_reader, data_validation
       - 10 inventory rows loaded
  2. [OK] compare current stock with minimum threshold  (6.2 ms)
       - 1 rows skipped (non-numeric stock)
  3. [OK] identify low-stock products  (1.1 ms)
  4. [OK] calculate reorder quantity  (2.4 ms)  tools: calculator
  5. [OK] generate restock list  (3.8 ms)

Status: SUCCESS  (23 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
4 of 9 products need restocking:
- SKU-006 Laptop Stand: stock 0 < min 5 -> reorder 10
- SKU-003 USB-C Hub: stock 2 < min 8 -> reorder 14
- SKU-008 Canvas Tote Bag: stock 3 < min 12 -> reorder 21
- SKU-001 Wireless Mouse: stock 4 < min 10 -> reorder 16
1 row(s) skipped due to invalid stock data: SKU-010
```

## 2. Excel test question for WF002

*Checks:* Tests comparison and decision logic

```text
Request: Find products where vendor price differs by more than 10%.

Selected Workflow: WF002 - Product Price Validation
Routing: llm, confidence 0.97
Why: The request is to compare product prices with vendor prices and identify differences over 10%, which aligns directly with the Product Price Validation workflow (WF002).
Alternatives: WF003 (0.715), WF004 (0.355)
Inputs: {'threshold_percent': 10}
Defaults used (sample data / settings): product_path, vendor_path

Steps Executed:
  1. [OK] Load product prices  (7.4 ms)  tools: csv_reader, csv_reader, data_validation, data_validation
       - 10 internal rows, 10 vendor rows
  2. [OK] match products by SKU  (23.9 ms)
       - 9 matched, 1 internal-only, 1 vendor-only
  3. [OK] compare internal and vendor prices  (4.3 ms)
  4. [OK] calculate percentage difference  (1.8 ms)  tools: calculator
  5. [OK] flag exceptions  (3.1 ms)

Status: SUCCESS  (41 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
8 products matched; 3 exceed the 10% threshold:
- SKU-002 Mechanical Keyboard: internal 2500 vs vendor 2900 (+16.0%)
- SKU-005 Steel Water Bottle: internal 900 vs vendor 1050 (+16.7%)
- SKU-008 Canvas Tote Bag: internal 1200 vs vendor 1500 (+25.0%)
Not validated -> internal only: SKU-009; vendor only: SKU-011; invalid prices: SKU-010
```

## 3. Excel test question for WF003

*Checks:* Tests file ingestion and validation

```text
Request: Process this vendor spreadsheet and show invalid rows.

Selected Workflow: WF003 - Vendor File Processing
Routing: llm, confidence 0.98
Why: User wants to process a vendor spreadsheet and see invalid rows, which matches the Vendor File Processing workflow (WF003).
Alternatives: WF002 (0.322), WF001 (0.0)
Inputs: (none extracted)
Defaults used (sample data / settings): vendor_path

Steps Executed:
  1. [OK] Read file  (5.1 ms)  tools: csv_reader
       - 8 rows, columns: ['item_code', 'title', 'cat', 'mat', 'colour', 'qty']
  2. [OK] detect columns  (0.2 ms)
       - detected: item_code->sku, title->product_name, cat->category, mat->material, colour->color, qty->stock
  3. [OK] normalize column names  (18.4 ms)
  4. [OK] validate required fields  (11.3 ms)  tools: data_validation
  5. [OK] identify invalid rows  (4.6 ms)
  6. [OK] produce cleaned dataset  (25.2 ms)  tools: reporting, reporting

Status: SUCCESS  (74 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
Processed 8 rows: 5 valid, 3 invalid. Cleaned dataset has 4 rows (1 exact duplicate row(s) removed).
Invalid rows:
- row 4: missing product_name
- row 5: missing sku
- row 7: missing sku; missing product_name
Cleaned file: outputs\wf003_cleaned_vendor_file.csv; invalid-row report: outputs\wf003_invalid_rows.csv
```

## 4. Excel test question for WF004

*Checks:* Tests LLM workflow and missing-data handling

```text
Request: Generate SEO content for this product.

Selected Workflow: WF004 - Product Description Generator
Routing: llm, confidence 0.97
Why: The request is to generate SEO content for a product, which aligns with the Product Description Generator workflow that creates product descriptions, short descriptions, SEO titles, and meta descriptions.
Alternatives: WF008 (0.514), WF001 (0.474)
Inputs: (none extracted)

Steps Executed:
  1. [OK] Validate required attributes  (0.8 ms)
       - no product supplied -> using bundled sample product (data/mock/sample_product.json) | missing attributes: ['material']
  2. [OK] create product description  (1943.1 ms)  tools: llm
  3. [OK] generate short description  (0.0 ms)
       - short_description produced in the same structured LLM call
  4. [OK] generate SEO title  (0.0 ms)
       - seo_title produced in the same structured LLM call
  5. [OK] generate meta description  (0.1 ms)  tools: text_validation
       - text validation passed

Status: SUCCESS  (1944 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
Product Description: The Travel Backpack in sleek black offers a 20L capacity, perfect for frequent travelers seeking reliable storage. Its design balances durability and style for journeys of any length. [Missing information, not assumed: material.]
Short Description: Black 20L Travel Backpack for frequent travelers.
Seo Title: Black Travel Backpack – 20L for Frequent Travelers
Meta Description: Explore the black Travel Backpack with 20L capacity, designed for frequent travelers who need dependable, stylish storage.
Missing product information (explicitly not invented): material
```

## 5. Excel test question for WF005

*Checks:* Tests lookup and missing-order handling

```text
Request: Where is order ORD-1001?

Selected Workflow: WF005 - Customer Order Status
Routing: llm, confidence 0.99
Why: User asks for the status of a specific order (ORD-1001), which matches the Customer Order Status workflow.
Alternatives: WF001 (0.0), WF002 (0.0)
Inputs: {'order_id': 'ORD-1001'}
Defaults used (sample data / settings): orders_path, shipments_path

Steps Executed:
  1. [OK] Validate identifier  (0.0 ms)
  2. [OK] search order data  (5.9 ms)  tools: order_api
  3. [OK] retrieve order status  (0.0 ms)
  4. [OK] retrieve shipment information  (6.0 ms)  tools: shipment_lookup
  5. [OK] summarize current status  (0.0 ms)

Status: SUCCESS  (12 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
ORD-1001 (Wireless Mouse, USB-C Hub): order Shipped; shipment In Transit via BlueDart, tracking TRK1001, ETA 2026-10-09.
```

## 6. Excel test question for WF006

*Checks:* Tests similarity and confidence

```text
Request: Find likely duplicate products in the catalog.

Selected Workflow: WF006 - Duplicate Product Detection
Routing: llm, confidence 0.99
Why: The request is to find likely duplicate products in the catalog, which directly matches the purpose of WF006 (Duplicate Product Detection).
Alternatives: WF002 (0.337), WF004 (0.337)
Inputs: (none extracted)
Defaults used (sample data / settings): catalog_path

Steps Executed:
  1. [OK] Load products  (4.5 ms)  tools: csv_reader, data_validation
  2. [OK] normalize names/SKUs  (1.8 ms)
  3. [OK] compare identifiers  (6.5 ms)
  4. [OK] compare product attributes  (4.3 ms)  tools: pairwise_similarity
  5. [OK] group likely duplicates  (0.0 ms)
  6. [OK] assign confidence  (1.1 ms)

Status: SUCCESS  (18 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
3 duplicate group(s) found among 10 products:
- [DEFINITE SKU match + possible matches, high confidence 1.00] P-1001 Wireless Mouse | p1001 Wireless Mouse (Black) | P-1002 Wireless Mouse (matched on: brand, category, color, material, name, sku)
- [POSSIBLE, high confidence 1.00] P-1006 USB-C Hub 7-in-1 | P-1007 USB C Hub 7 in 1 (matched on: brand, category, color, material, name)
- [POSSIBLE, high confidence 0.98] P-1003 Mechanical Keyboard | P-1004 Mechanical Keybord (matched on: brand, category, color, material, name)
```

## 7. Excel test question for WF007

*Checks:* Tests structured content generation

```text
Request: Create a campaign brief for the new collection.

Selected Workflow: WF007 - Marketing Campaign Brief
Routing: llm, confidence 0.98
Why: User explicitly requests a campaign brief for a new collection, matching the Marketing Campaign Brief workflow.
Alternatives: WF004 (0.203), WF001 (0.0)
Inputs: (none extracted)
Defaults used (sample data / settings): products_path

Steps Executed:
  1. [ -- ] Validate inputs  (0.0 ms)
  2. [ -- ] identify campaign objective  (0.0 ms)
  3. [ -- ] summarize products  (0.0 ms)
  4. [ -- ] create messaging  (0.0 ms)
  5. [ -- ] create channel recommendations  (0.0 ms)
  6. [ -- ] create campaign checklist  (0.0 ms)

Status: NEEDS_INPUT  (0 ms, LLM mode: llm:openai/gpt-oss-120b)
Agent needs more info: What is the campaign goal (e.g. 'launch the new collection')? What are the campaign dates (e.g. 'Oct 10 to Oct 20')?

Result:
What is the campaign goal (e.g. 'launch the new collection')? What are the campaign dates (e.g. 'Oct 10 to Oct 20')?
```

## 8. Excel test question for WF008

*Checks:* Tests classification and mapping

```text
Request: Classify these keywords and map them to pages.

Selected Workflow: WF008 - SEO Keyword Classification
Routing: llm, confidence 0.95
Why: User wants keyword classification and page mapping, which matches the SEO Keyword Classification workflow.
Alternatives: WF001 (0.0), WF002 (0.0)
Inputs: (none extracted)
Defaults used (sample data / settings): keywords_path, categories_path

Steps Executed:
  1. [OK] Read keywords  (9.5 ms)  tools: csv_reader, data_validation, csv_reader
       - 20 keywords read from column 'keyword'
  2. [OK] remove duplicates  (6.3 ms)
       - 1 duplicate keyword(s) removed
  3. [OK] classify search intent  (2851.8 ms)  tools: llm
  4. [OK] map keywords to categories  (1.5 ms)
  5. [OK] identify high-priority keywords  (0.1 ms)
  6. [OK] export results  (4.0 ms)  tools: reporting

Status: SUCCESS  (2876 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
19 unique keywords classified (1 duplicates removed). Intent mix: {'commercial': 7, 'informational': 6, 'transactional': 4, 'navigational': 2}. 10 high priority:
- best mechanical keyboard 2026 [commercial] -> Category page -> /collections/electronics
- best travel backpack for carry on [commercial] -> Category page -> /collections/bags
- buy wireless mouse online [transactional] -> Category / product page -> /collections/electronics
- canvas tote bag buy [transactional] -> Category / product page -> /collections/bags
- cheap laptop stand deals [transactional] -> Category / product page -> /collections/electronics
- laptop stand near me [transactional] -> Category / product page -> /collections/electronics
- travel backpack [commercial] -> Category page -> /collections/bags
- usb-c hub price [commercial] -> Category page -> /collections/electronics
- webcam hd [commercial] -> Category page -> /collections/electronics
- wireless mouse [commercial] -> Category page -> /collections/electronics
Full report: outputs\wf008_keyword_report.csv
```

## 9. Excel test question for WF009

*Checks:* Tests ranking and decision logic

```text
Request: Assign this urgent task to the best available developer.

Selected Workflow: WF009 - Employee Task Assignment
Routing: llm, confidence 0.98
Why: The request is to assign an urgent task to the best available developer, which aligns with the Employee Task Assignment workflow (WF009) that handles task assignment based on description, skills, workload, and priority.
Alternatives: WF005 (0.216), WF006 (0.216)
Inputs: {'priority': 'urgent', 'role_filter': 'developer'}
Defaults used (sample data / settings): employees_path

Steps Executed:
  1. [ -- ] Understand task requirements  (0.0 ms)
  2. [ -- ] compare employee skills  (0.0 ms)
  3. [ -- ] check current workload  (0.0 ms)
  4. [ -- ] rank candidates  (0.0 ms)
  5. [ -- ] select employee  (0.0 ms)
  6. [ -- ] generate assignment summary  (0.0 ms)

Status: NEEDS_INPUT  (0 ms, LLM mode: llm:openai/gpt-oss-120b)
Agent needs more info: What is the task? Please describe it (and optionally the skills needed).

Result:
What is the task? Please describe it (and optionally the skills needed).
```

## 10. Excel test question for WF010

*Checks:* Tests aggregation and reporting

```text
Request: Which workflows are failing most often?

Selected Workflow: WF010 - Workflow Performance Report
Routing: llm, confidence 0.95
Why: The request asks for information on failing workflows, which matches WF010 that generates a performance report with metrics and problem areas.
Alternatives: WF001 (0.0), WF002 (0.0)
Inputs: (none extracted)
Defaults used (sample data / settings): logs_path, failure_threshold_percent, time_threshold_seconds, slow_step_seconds

Steps Executed:
  1. [OK] Load execution logs  (8.0 ms)  tools: csv_reader, data_validation
       - 327 log rows, 112 runs
  2. [OK] calculate success/failure rate  (60.7 ms)  tools: calculator, calculator, calculator, calculator, calculator, calculator, calculator, calculator, calculator, calculator, calculator, calculator, calculator, calculator, calculator, calculator, calculator, calculator, calculator, calculator
  3. [OK] calculate average execution time  (3.9 ms)  tools: calculator, calculator, calculator, calculator, calculator, calculator, calculator, calculator, calculator, calculator
  4. [OK] identify frequent errors  (17.8 ms)
  5. [OK] identify slow steps  (16.6 ms)
  6. [OK] generate recommendations  (3774.2 ms)  tools: llm, reporting

Status: SUCCESS  (3882 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
4 of 10 workflows flagged (failure rate > 10% or avg time > 8s).
- WF002: 50.0% failures (6/12), avg 1.64s  FLAGGED (failure rate 50.0% > 10%)
- WF004: 16.67% failures (2/12), avg 7.67s  FLAGGED (failure rate 16.67% > 10%)
- WF003: 16.67% failures (2/12), avg 1.41s  FLAGGED (failure rate 16.67% > 10%)
- WF005: 0.0% failures (0/12), avg 9.27s  FLAGGED (avg time 9.27s > 8s)
- WF007: 0.0% failures (0/12), avg 6.33s
- WF006: 0.0% failures (0/12), avg 2.58s
- WF008: 0.0% failures (0/12), avg 1.77s
- WF001: 0.0% failures (0/12), avg 1.15s
- WF009: 0.0% failures (0/12), avg 0.99s
- WF010: 0.0% failures (0/4), avg 0.92s
Top errors: Invalid price format x4; LLM timeout x2; Missing required column: sku x2
Slow steps: WF005.shipment_lookup 6.6s; WF004.llm_generate 5.44s; WF007.llm_messaging 4.34s
Recommendations:
  * Add automated validation for price fields to eliminate "Invalid price format" errors and reduce WF002 failures
  * Implement pre‑run checks for required columns (e.g., sku) and vendor file presence to stop "Missing required column" and "Vendor price file missing" errors
  * Increase LLM request timeout or add retry/back‑off logic to mitigate "LLM timeout" failures in WF004 and WF007
  * Reduce WF002 failure rate by adding idempotent retry logic and detailed error logging for the failing steps
  * Investigate and refactor the "shipment_lookup" step in WF005 to lower its average time (6.6 s) and bring total workflow time under the 8 s threshold
  * Optimize the "llm_generate" step in WF004 (5.44 s) by caching prompts or using a smaller model to improve overall latency
  * Set up monitoring alerts for any workflow whose failure_rate exceeds 10 % or avg_execution_time exceeds 8 s
  * Create a post‑run report that aggregates frequent error types and triggers targeted remediation tickets
Report: outputs\wf010_performance_report.json
```

## 11. WF001 with a custom threshold

*Checks:* threshold override

```text
Request: Which products are below a minimum stock threshold of 12?

Selected Workflow: WF001 - Inventory Restock Check
Routing: llm, confidence 0.98
Why: User asks for products below a minimum stock threshold, which matches the Inventory Restock Check workflow.
Alternatives: WF002 (0.337), WF004 (0.337)
Inputs: {'minimum_stock': 12}
Defaults used (sample data / settings): inventory_path, reorder_multiplier

Steps Executed:
  1. [OK] Load inventory  (17.2 ms)  tools: csv_reader, data_validation
       - 10 inventory rows loaded
  2. [OK] compare current stock with minimum threshold  (2.4 ms)
       - threshold overridden to 12 | 1 rows skipped (non-numeric stock)
  3. [OK] identify low-stock products  (1.2 ms)
  4. [OK] calculate reorder quantity  (2.0 ms)  tools: calculator
  5. [OK] generate restock list  (4.0 ms)

Status: SUCCESS  (27 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
6 of 9 products need restocking:
- SKU-006 Laptop Stand: stock 0 < min 12 -> reorder 24
- SKU-003 USB-C Hub: stock 2 < min 12 -> reorder 22
- SKU-008 Canvas Tote Bag: stock 3 < min 12 -> reorder 21
- SKU-001 Wireless Mouse: stock 4 < min 12 -> reorder 20
- SKU-007 Noise Cancelling Headphones: stock 7 < min 12 -> reorder 17
- SKU-005 Steel Water Bottle: stock 10 < min 12 -> reorder 14
1 row(s) skipped due to invalid stock data: SKU-010
```

## 12. WF002 with a custom 15% threshold

*Checks:* threshold from request; unmatched SKUs reported

```text
Request: Validate vendor prices and flag anything that differs by more than 15%.

Selected Workflow: WF002 - Product Price Validation
Routing: llm, confidence 0.98
Why: User wants to validate vendor prices and flag differences, which matches the Product Price Validation workflow (WF002) that compares product and vendor price lists and reports discrepancies.
Alternatives: WF003 (0.656), WF010 (0.178)
Inputs: {'threshold_percent': 15}
Defaults used (sample data / settings): product_path, vendor_path

Steps Executed:
  1. [OK] Load product prices  (31.3 ms)  tools: csv_reader, csv_reader, data_validation, data_validation
       - 10 internal rows, 10 vendor rows
  2. [OK] match products by SKU  (22.9 ms)
       - 9 matched, 1 internal-only, 1 vendor-only
  3. [OK] compare internal and vendor prices  (4.3 ms)
  4. [OK] calculate percentage difference  (1.6 ms)  tools: calculator
  5. [OK] flag exceptions  (3.2 ms)

Status: SUCCESS  (64 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
8 products matched; 3 exceed the 15% threshold:
- SKU-002 Mechanical Keyboard: internal 2500 vs vendor 2900 (+16.0%)
- SKU-005 Steel Water Bottle: internal 900 vs vendor 1050 (+16.7%)
- SKU-008 Canvas Tote Bag: internal 1200 vs vendor 1500 (+25.0%)
Not validated -> internal only: SKU-009; vendor only: SKU-011; invalid prices: SKU-010
```

## 13. WF003 on an XLSX vendor file

*Checks:* XLSX ingestion, column detection

```text
Request: Process this vendor spreadsheet data/mock/vendor_products.xlsx and show invalid rows.

Selected Workflow: WF003 - Vendor File Processing
Routing: llm, confidence 0.98
Why: User wants to process a vendor spreadsheet and see invalid rows, which matches the Vendor File Processing workflow.
Alternatives: WF002 (0.502), WF004 (0.19)
Inputs: {'vendor_path': 'data/mock/vendor_products.xlsx'}

Steps Executed:
  1. [OK] Read file  (28.1 ms)  tools: excel_parser
       - 8 rows, columns: ['item_code', 'title', 'cat', 'mat', 'colour', 'qty']
  2. [OK] detect columns  (0.1 ms)
       - detected: item_code->sku, title->product_name, cat->category, mat->material, colour->color, qty->stock
  3. [OK] normalize column names  (10.6 ms)
  4. [OK] validate required fields  (4.6 ms)  tools: data_validation
  5. [OK] identify invalid rows  (4.2 ms)
  6. [OK] produce cleaned dataset  (16.5 ms)  tools: reporting, reporting

Status: SUCCESS  (72 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
Processed 8 rows: 5 valid, 3 invalid. Cleaned dataset has 4 rows (1 exact duplicate row(s) removed).
Invalid rows:
- row 4: missing product_name
- row 5: missing sku
- row 7: missing sku; missing product_name
Cleaned file: outputs\wf003_cleaned_vendor_file.csv; invalid-row report: outputs\wf003_invalid_rows.csv
```

## 14. WF003 error handling: file does not exist

*Checks:* graceful failure + trace

```text
Request: Process this vendor file data/mock/does_not_exist.csv and show invalid rows.

Selected Workflow: WF003 - Vendor File Processing
Routing: llm, confidence 0.98
Why: User wants to process a vendor file and see invalid rows, which matches the Vendor File Processing workflow.
Alternatives: WF002 (0.195), WF004 (0.098)
Inputs: {'vendor_path': 'data/mock/does_not_exist.csv'}

Steps Executed:
  1. [FAILED] Read file  (0.4 ms)  tools: csv_reader
  2. [ -- ] detect columns  (0.0 ms)
  3. [ -- ] normalize column names  (0.0 ms)
  4. [ -- ] validate required fields  (0.0 ms)
  5. [ -- ] identify invalid rows  (0.0 ms)
  6. [ -- ] produce cleaned dataset  (0.0 ms)

Status: FAILED  (1 ms, LLM mode: llm:openai/gpt-oss-120b)
Error: FileNotFoundError: Data file not found: data/mock/does_not_exist.csv

Result:
Workflow could not complete: Data file not found: data/mock/does_not_exist.csv
```

## 15. WF004 with all attributes supplied

*Checks:* no missing-information note

```text
Request: Generate SEO content for this product.

Selected Workflow: WF004 - Product Description Generator
Routing: llm, confidence 0.97
Why: The request is to generate SEO content for a product, which aligns with the Product Description Generator workflow that creates product descriptions, short descriptions, SEO titles, and meta descriptions.
Alternatives: WF008 (0.514), WF001 (0.474)
Inputs: {'product_name': 'Travel Backpack', 'category': 'Bags', 'material': 'Nylon', 'color': 'Black', 'target_audience': 'frequent travelers', 'attributes': {'capacity': '20L'}}

Steps Executed:
  1. [OK] Validate required attributes  (0.0 ms)
       - missing attributes: none
  2. [OK] create product description  (2590.9 ms)  tools: llm
  3. [OK] generate short description  (0.0 ms)
       - short_description produced in the same structured LLM call
  4. [OK] generate SEO title  (0.0 ms)
       - seo_title produced in the same structured LLM call
  5. [OK] generate meta description  (0.1 ms)  tools: text_validation
       - text validation passed

Status: SUCCESS  (2591 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
Product Description: The Travel Backpack is a sleek black nylon bag designed for frequent travelers. It offers a 20L capacity, providing ample space for essentials on the go. Its durable construction ensures reliable performance on any journey.
Short Description: Black nylon Travel Backpack with 20L capacity for frequent travelers.
Seo Title: Travel Backpack – Black Nylon 20L for Frequent Travelers
Meta Description: Explore the world with the black nylon Travel Backpack, offering 20L capacity for frequent travelers seeking reliable, spacious gear.
```

## 16. WF005 order not found

*Checks:* ask for another identifier

```text
Request: Where is order ORD-9999?

Selected Workflow: WF005 - Customer Order Status
Routing: llm, confidence 0.99
Why: User asks for the status of a specific order, which matches the Customer Order Status workflow (WF005).
Alternatives: WF001 (0.0), WF002 (0.0)
Inputs: {'order_id': 'ORD-9999'}
Defaults used (sample data / settings): orders_path, shipments_path

Steps Executed:
  1. [OK] Validate identifier  (0.0 ms)
  2. [BLOCKED] search order data  (26.1 ms)  tools: order_api
  3. [ -- ] retrieve order status  (0.0 ms)
  4. [ -- ] retrieve shipment information  (0.0 ms)
  5. [ -- ] summarize current status  (0.0 ms)

Status: NEEDS_INPUT  (26 ms, LLM mode: llm:openai/gpt-oss-120b)
Agent needs more info: No order found for 'ORD-9999'. Please check it or provide another identifier (order ID or customer email).

Result:
No order found for 'ORD-9999'. Please check it or provide another identifier (order ID or customer email).
```

## 17. WF005 lookup by email (2 orders)

*Checks:* multiple orders

```text
Request: What is the status of orders for alice@example.com?

Selected Workflow: WF005 - Customer Order Status
Routing: llm, confidence 0.99
Why: User asks for order status using a customer email, which matches the trigger and inputs of WF005 (Customer Order Status).
Alternatives: WF001 (0.0), WF002 (0.0)
Inputs: {'customer_email': 'alice@example.com'}
Defaults used (sample data / settings): orders_path, shipments_path

Steps Executed:
  1. [OK] Validate identifier  (0.0 ms)
  2. [OK] search order data  (7.0 ms)  tools: order_api
  3. [OK] retrieve order status  (0.0 ms)
  4. [OK] retrieve shipment information  (31.6 ms)  tools: shipment_lookup, shipment_lookup
  5. [OK] summarize current status  (0.0 ms)

Status: SUCCESS  (39 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
ORD-1001 (Wireless Mouse, USB-C Hub): order Shipped; shipment In Transit via BlueDart, tracking TRK1001, ETA 2026-10-09.
ORD-1004 (Desk Organizer): order Shipped; shipment Out for Delivery via BlueDart, tracking TRK1004, ETA 2026-10-07.
```

## 18. WF005 order without shipment yet

*Checks:* tracking only when available

```text
Request: Where is order ORD-1002?

Selected Workflow: WF005 - Customer Order Status
Routing: llm, confidence 0.99
Why: User asks for the status of a specific order (ORD-1002), which matches the Customer Order Status workflow.
Alternatives: WF001 (0.0), WF002 (0.0)
Inputs: {'order_id': 'ORD-1002'}
Defaults used (sample data / settings): orders_path, shipments_path

Steps Executed:
  1. [OK] Validate identifier  (0.0 ms)
  2. [OK] search order data  (6.3 ms)  tools: order_api
  3. [OK] retrieve order status  (0.0 ms)
  4. [OK] retrieve shipment information  (7.8 ms)  tools: shipment_lookup
  5. [OK] summarize current status  (0.0 ms)

Status: SUCCESS  (14 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
ORD-1002 (Mechanical Keyboard): order Processing; no shipment/tracking information available yet.
```

## 19. WF005 invalid identifier

*Checks:* no identifier -> agent asks

```text
Request: Where is order 12?

Selected Workflow: WF005 - Customer Order Status
Routing: llm, confidence 0.99
Why: User is asking for the status of a specific order (order 12), which matches the Customer Order Status workflow.
Alternatives: WF001 (0.0), WF002 (0.0)
Inputs: {'order_id': '12'}
Defaults used (sample data / settings): orders_path, shipments_path

Steps Executed:
  1. [BLOCKED] Validate identifier  (0.0 ms)
  2. [ -- ] search order data  (0.0 ms)
  3. [ -- ] retrieve order status  (0.0 ms)
  4. [ -- ] retrieve shipment information  (0.0 ms)
  5. [ -- ] summarize current status  (0.0 ms)

Status: NEEDS_INPUT  (0 ms, LLM mode: llm:openai/gpt-oss-120b)
Agent needs more info: '12' is not a valid order ID (expected like ORD-1001). Please provide another identifier.

Result:
'12' is not a valid order ID (expected like ORD-1001). Please provide another identifier.
```

## 20. WF007 complete brief

*Checks:* structured brief

```text
Request: Create a campaign brief to launch the new autumn collection from Oct 10 to Oct 20 targeting young travelers with 20% off

Selected Workflow: WF007 - Marketing Campaign Brief
Routing: llm, confidence 0.98
Why: User requests a marketing campaign brief with goal, dates, target audience, and promotion, which matches WF007
Alternatives: WF004 (0.245), WF002 (0.131)
Inputs: {'goal': 'launch the new autumn collection', 'dates': 'Oct 10 to Oct 20', 'target_audience': 'young travelers', 'promotion': '20% off', 'products': ['autumn collection']}
Defaults used (sample data / settings): products_path

Steps Executed:
  1. [OK] Validate inputs  (0.0 ms)
       - goal and dates present
  2. [OK] identify campaign objective  (0.0 ms)
       - objective = launch
  3. [OK] summarize products  (26.4 ms)  tools: product_data_reader
       - products from request
  4. [OK] create messaging  (3137.6 ms)  tools: llm
  5. [OK] create channel recommendations  (0.0 ms)
  6. [OK] create campaign checklist  (1.7 ms)

Status: SUCCESS  (3166 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
CAMPAIGN BRIEF
Objective: launch the new autumn collection (launch)
Audience: young travelers
Products: autumn collection
Promotion: 20% off
Messaging:
  - Introducing the new autumn collection
  - Designed for young travelers
  - Enjoy 20% off
Channels: Email newsletter, Website homepage banner + landing page, Instagram / Reels, YouTube Shorts / short video, Google Shopping / paid search
Timeline:
  - Pre-launch (teasers, creative sign-off): 2026-10-03 to 2026-10-09
  - Campaign live: 2026-10-10 to 2026-10-20
  - Wrap-up & results review: 2026-10-21 to 2026-10-24
Checklist:
  [ ] Confirm campaign objective and KPIs
  [ ] Finalise product list and stock availability
  [ ] Configure promotion in store: 20% off
  [ ] Approve messaging and creative
  [ ] Set up landing page and tracking links
  [ ] Schedule channel posts / emails
  [ ] Launch campaign on the start date
  [ ] Monitor performance daily and adjust
  [ ] Run post-campaign review
```

## 21. WF009 task given

*Checks:* ranking + reasoning

```text
Request: Assign this urgent task to the best available developer by Friday.

Selected Workflow: WF009 - Employee Task Assignment
Routing: llm, confidence 0.97
Why: The request asks to assign an urgent task to the best available developer by a specific deadline, which aligns with the Employee Task Assignment workflow (WF009).
Alternatives: WF005 (0.216), WF006 (0.216)
Inputs: {'priority': 'urgent', 'deadline': 'Friday', 'role_filter': 'developer', 'task_description': 'Build a Python REST API with a database backend'}
Defaults used (sample data / settings): employees_path

Steps Executed:
  1. [OK] Understand task requirements  (23.9 ms)  tools: csv_reader, data_validation
       - required skills: ['api', 'backend', 'database', 'python']; priority: urgent
  2. [OK] compare employee skills  (4.6 ms)
  3. [OK] check current workload  (1.2 ms)
  4. [OK] rank candidates  (0.1 ms)  tools: ranking_logic
  5. [OK] select employee  (0.0 ms)
  6. [OK] generate assignment summary  (0.0 ms)

Status: SUCCESS  (30 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
Recommended: Rohan (E003).
Reason: Rohan covers 3/4 required skills (backend, database, python) and has 4 free capacity slots (80% available); score 0.775.
Task: Build a Python REST API with a database backend
Priority: urgent
Deadline: Friday
Runners-up: Aarav (0.575)
```

## 22. WF009 no suitable employee -> escalate

*Checks:* escalation

```text
Request: Assign this urgent task to the best available developer.

Selected Workflow: WF009 - Employee Task Assignment
Routing: llm, confidence 0.98
Why: The request is to assign an urgent task to the best available developer, which aligns with the Employee Task Assignment workflow (WF009) that handles task assignment based on description, skills, workload, and priority.
Alternatives: WF005 (0.216), WF006 (0.216)
Inputs: {'priority': 'urgent', 'role_filter': 'developer', 'task_description': 'Train a computer vision model', 'required_skills': ['computer vision']}
Defaults used (sample data / settings): employees_path

Steps Executed:
  1. [OK] Understand task requirements  (4.3 ms)  tools: csv_reader, data_validation
       - required skills: ['computer vision']; priority: urgent
  2. [OK] compare employee skills  (3.6 ms)
  3. [OK] check current workload  (1.0 ms)
  4. [OK] rank candidates  (0.0 ms)  tools: ranking_logic
  5. [OK] select employee  (0.0 ms)
  6. [OK] generate assignment summary  (0.0 ms)

Status: ESCALATED  (9 ms, LLM mode: llm:openai/gpt-oss-120b)

Result:
ESCALATE: no suitable employee for 'Train a computer vision model' (needs computer vision). Closest candidates: Rohan (insufficient skill match); Aarav (insufficient skill match); Diya (insufficient skill match). Please escalate to the manager.
```

## 23. Ambiguous request -> clarification

*Checks:* router refuses to guess

```text
Request: hello there

Selected Workflow: (none)
Reason: User greeting does not match any defined workflow triggers
Agent: None of the available workflows match your request. Available: Inventory Restock Check, Product Price Validation, Vendor File Processing, Product Description Generator, Customer Order Status, Duplicate Product Detection, Marketing Campaign Brief, SEO Keyword Classification, Employee Task Assignment, Workflow Performance Report
```