# TransitFlow 資料庫設計文件

**Team 40**
Members: 許芳瑀 (112403040) · 陳墨 (112403047) · 黃品皓 (112403050)

> 章節標題依 IM2002 設計文件評分指引固定,請勿更動。各段由負責人填寫後合併成這一份,上傳 eeclass。

---

## Section 1 — Entity-Relationship Diagram

TransitFlow 的關聯式資料庫(PostgreSQL)負責所有會變動、需要交易保證的資料,共分為四個實體群組:

1. **使用者與認證**:`users`、`user_credentials`、`user_salts`(認證資料刻意與使用者主檔分離,見 Section 2)。
2. **路網靜態資料**:`metro_stations`、`metro_station_lines`、`national_rail_stations`、`national_rail_station_lines`。
3. **班次與票價/座位**:`metro_schedules`、`metro_schedule_stops`、`metro_schedule_days`、`national_rail_schedules`、`national_rail_schedule_stops`、`national_rail_schedule_days`、`national_rail_fares`、`national_rail_seat_layouts`、`national_rail_seats`。
4. **交易與回饋**:`national_rail_bookings`、`metro_travel_history`、`payments`、`feedback`。

> **⚠️ 一定要做(只有你們能做)**:評分要求是工具產生、線上標 cardinality 的 ER 圖。請把下面的 DBML 貼到 **[dbdiagram.io](https://dbdiagram.io)**,它會自動畫出含 cardinality 的圖,匯出 PNG 後,把下面這行 placeholder 換成圖片:
>
> `![TransitFlow ER Diagram](er_diagram.png)`

**dbdiagram.io DBML(可直接貼上產生 ER 圖):**

```dbml
Table users {
  user_id varchar [pk]
  email varchar [unique, not null]
  full_name varchar [not null]
  date_of_birth date
  is_active boolean
}

Table user_credentials {
  user_id varchar [pk, ref: - users.user_id]
  password_hash text [not null]
}

Table user_salts {
  user_id varchar [pk, ref: - users.user_id]
  salt text [not null]
}

Table metro_stations {
  station_id varchar [pk]
  station_name varchar [not null]
  is_interchange_national_rail boolean
  interchange_national_rail_station_id varchar
}

Table metro_station_lines {
  station_id varchar [pk, ref: > metro_stations.station_id]
  line_code varchar [pk]
}

Table national_rail_stations {
  station_id varchar [pk]
  station_name varchar [not null]
  is_interchange_metro boolean
  interchange_metro_station_id varchar
}

Table national_rail_station_lines {
  station_id varchar [pk, ref: > national_rail_stations.station_id]
  line_code varchar [pk]
}

Table metro_schedules {
  schedule_id varchar [pk]
  line varchar
  base_fare_usd decimal
  per_stop_rate_usd decimal
}

Table metro_schedule_stops {
  schedule_id varchar [pk, ref: > metro_schedules.schedule_id]
  station_id varchar [pk, ref: > metro_stations.station_id]
  stop_order integer
  travel_time_min integer
}

Table metro_schedule_days {
  schedule_id varchar [pk, ref: > metro_schedules.schedule_id]
  day_of_week varchar [pk]
}

Table national_rail_schedules {
  schedule_id varchar [pk]
  line varchar
  service_type varchar
}

Table national_rail_schedule_stops {
  schedule_id varchar [pk, ref: > national_rail_schedules.schedule_id]
  station_id varchar [pk, ref: > national_rail_stations.station_id]
  stop_order integer
  travel_time_min integer
}

Table national_rail_schedule_days {
  schedule_id varchar [pk, ref: > national_rail_schedules.schedule_id]
  day_of_week varchar [pk]
}

Table national_rail_fares {
  schedule_id varchar [pk, ref: > national_rail_schedules.schedule_id]
  fare_class varchar [pk]
  base_fare_usd decimal
  per_stop_rate_usd decimal
}

Table national_rail_seat_layouts {
  layout_id varchar [pk]
  schedule_id varchar [unique, not null, ref: - national_rail_schedules.schedule_id]
}

Table national_rail_seats {
  layout_id varchar [pk, ref: > national_rail_seat_layouts.layout_id]
  seat_id varchar [pk]
  coach varchar
  fare_class varchar
}

Table national_rail_bookings {
  booking_id varchar [pk]
  user_id varchar [not null, ref: > users.user_id]
  schedule_id varchar [not null]
  seat_id varchar
  amount_usd decimal
  status varchar
}

Table metro_travel_history {
  trip_id varchar [pk]
  user_id varchar [not null, ref: > users.user_id]
  schedule_id varchar [not null]
  amount_usd decimal
  status varchar
}

Table payments {
  payment_id varchar [pk]
  booking_id varchar [not null, ref: > national_rail_bookings.booking_id]
  amount_usd decimal
  method varchar
  status varchar
}

Table feedback {
  feedback_id varchar [pk]
  booking_id varchar [not null]
  user_id varchar [not null, ref: > users.user_id]
  rating integer
}
```

**主要關係與 cardinality(對照用):**

| 關係 | Cardinality | 說明 |
|------|-------------|------|
| `users` 與 `user_credentials` | 1 : 1 | 認證與主檔分離(PK 即 FK)|
| `users` 與 `user_salts` | 1 : 1 | 每位使用者一組 salt |
| `users` 與 `national_rail_bookings` / `metro_travel_history` / `feedback` | 1 : N | 一位使用者多筆紀錄 |
| `metro_stations` 與 `metro_station_lines` | 1 : N | 站↔線為 M:N,用 junction 拆開 |
| `metro_schedules` 與 `metro_schedule_stops` / `_days` | 1 : N | 一班次多個停靠站/行駛日 |
| `national_rail_schedules` 與 `national_rail_fares` | 1 : N | 同班次不同 fare_class 一筆 |
| `national_rail_schedules` 與 `national_rail_seat_layouts` | 1 : 1 | 一班次一套座位配置 |
| `national_rail_seat_layouts` 與 `national_rail_seats` | 1 : N | 一套配置多個座位 |
| `national_rail_bookings` 與 `payments` | 1 : 1(邏輯上)| 一筆訂位一筆付款 |

> 注:`metro_schedule_stops` / `national_rail_schedule_stops` 既是班次與車站之間 M:N 的 junction,也承載 `stop_order`、`travel_time_min` 兩個關係屬性。

---

## Section 2 — Normalisation Justification

### 2.1 達到 3NF 的設計決策:班次停靠站使用 junction table

一個班次(schedule)會依序停靠多個車站,每個停靠站又各有自己的停靠順序與到站時間。一個錯誤的做法是在 `national_rail_schedules` 上塞一個 `stops` 陣列欄位,或開 `stop1, stop2, …` 這類重複欄位,這會違反 1NF(欄位不可為多值)並造成更新異常。

我們改用 `national_rail_schedule_stops`(以及對應的 `metro_schedule_stops`)作為 junction table,主鍵為複合鍵 `(schedule_id, station_id)`。其 functional dependency 為:

```
(schedule_id, station_id) → stop_order, travel_time_min
```

也就是說 `stop_order` 與 `travel_time_min` **完全相依於整個複合主鍵**(滿足 2NF:沒有部分相依),且不存在非鍵欄位相依於另一非鍵欄位的 transitive dependency(滿足 3NF)。同樣的拆法也用在:

- `metro_station_lines` / `national_rail_station_lines`:車站與路線是 M:N(一站可屬多條線),用 junction 拆開,而不是在車站列上放多值欄位。
- `national_rail_fares`:票價相依於 `(schedule_id, fare_class)` 複合鍵,因此獨立成表,而不是在班次上放 `standard_fare`、`first_fare` 等重複欄位。
- `*_schedule_days`:行駛日同樣是多值,獨立成 junction。

### 2.2 刻意的 de-normalisation:訂位金額快照

`national_rail_bookings` 存了 `amount_usd` 與 `stops_travelled`,這兩個值理論上可由班次票價 × 停靠站數即時推算,屬於受控的 de-normalisation。我們刻意這麼做的理由是:**訂位金額是交易當下的快照**。票價(`national_rail_fares`)未來若調整,已成立的歷史訂位金額**不能跟著變動**;把成交金額直接寫進 booking,既保證歷史正確性,也避免每次讀取訂位都要重算 join。這是用少量冗餘換歷史不可變性與讀取效能的合理取捨。

### 2.3 密碼雜湊:演算法、salt 與資料表設計

**資料表設計**:`users` 主檔**完全不存任何密碼資訊**。我們把認證資料拆成兩張獨立的表:
- `user_credentials(user_id PK/FK, password_hash)`,存雜湊後的密碼。
- `user_salts(user_id PK/FK, salt)`,每位使用者一組獨立 salt,**與雜湊分表存放**。

兩張表的 `user_id` 既是主鍵也是指向 `users` 的外鍵(1:1),以 `ON DELETE CASCADE` 維持一致性。這樣即使 `users` 主檔被讀取或外洩,也不會直接連帶洩漏密碼憑證。

**演算法**:目前實作為 `SHA-256( password + per-user salt )`,輸出十六進位字串存入 `password_hash`(見 `databases/relational/queries.py` 的 `_hash_password`)。

**為什麼用 SHA-256 而非 MD5/SHA-1**:MD5 與 SHA-1 已被證實有實際可行的碰撞攻擊(collision attack),不再適合任何安全用途;SHA-256 屬 SHA-2 家族,目前仍具抗碰撞性,是明顯較安全的選擇。

**salt 如何防 rainbow table**:salt 是一段每位使用者隨機且唯一的字串,雜湊前先與密碼串接。它的作用有二:(1) 即使兩位使用者設了**相同密碼**,因 salt 不同,算出的 hash 也**完全不同**,攻擊者無法從相同的 hash 反推出兩人用了相同密碼;(2) 由於每個 hash 都綁定一個獨特 salt,攻擊者**無法使用預先計算好的 rainbow table** 一次比對整個資料庫,他必須針對每位使用者的 salt 重新暴力計算,大幅提高破解成本。

> **誠實聲明與限制**:SHA-256 是快雜湊,本身沒有 cost factor / key stretching。在正式環境應改用 **argon2id / bcrypt / scrypt** 這類慢的密碼專用 KDF,透過可調的成本參數抵抗 GPU 暴力破解(此點列入 Section 6 的 production 差異)。本專案在現有 SHA-256 之上,以分表儲存加上每人獨立 salt,確保了 salt 的核心防護效果。

### 2.4 術語對照

本節涉及的概念:**candidate key / composite primary key**(如 `(schedule_id, station_id)`)、**functional dependency**(停靠屬性相依於複合鍵)、避免 **partial dependency**(2NF)與 **transitive dependency**(3NF),以及以受控冗餘進行的 **de-normalisation** 取捨。

---

## Section 3 — Graph Database Design Rationale

### 為什麼路網用 Neo4j,而不是塞進 PostgreSQL

我們一開始有考慮過把整個路網也放進 PostgreSQL,畢竟訂票、票價、座位那些資料本來就在關聯式資料庫裡了。可是實際去想從 A 站到 B 站怎麼走最快這個問題的時候,就發現不太對。這種查詢的本質是沿著一站接一站的連線一直走下去,而你事先並不知道要走幾站。用 SQL 做的話,得靠遞迴 CTE 或一層層的 self-join,路徑越長 join 越多,寫起來又臭又長,效能也難控制。我們不想為了硬塞進關聯式模型,把一個本來很直覺的問題搞複雜。

圖資料庫剛好相反,它天生就是用來表達東西跟東西之間的關係。我們把每個車站當成一個節點,分成 `MetroStation` 和 `RailStation` 兩種,把站跟站之間的連線當成 `CONNECTS_TO` 關係,連線上直接掛 `travel_time_min` 這個屬性當權重。這樣一來,找最短路徑就不必我們自己刻演算法,直接呼叫 Neo4j 透過 APOC 提供的 Dijkstra(`apoc.algo.dijkstra`)就能算出加權最短路徑。要找某站幾站範圍內會被影響的站,也只是一個變長度的 traversal(`*0..N`),不用拼一堆 join。同一份資料,放對地方,問題就簡單一半。

### 這個系統最麻煩的地方,是兩個網路要能互通

我們的資料其實有兩個獨立的網路:市區捷運 M1 到 M4,還有國鐵 NR1 到 NR2。乘客的真實旅程常常是先搭捷運,在轉乘站換到國鐵,所以系統一定要能算出跨網路的路線。這在關聯式模型裡會很尷尬,因為你得想辦法表達這兩張不同的表之間,某些站其實是同一個轉乘點。

在圖裡我們的做法很乾淨:另外開一種關係叫 `INTERCHANGE_TO`,專門連接互為轉乘站的捷運站和國鐵站,而且給它一個 5 分鐘的轉乘時間懲罰(`travel_time_min: 5`)。這樣最短路徑演算法在計算的時候,會自動把換網路要多花 5 分鐘這件事算進成本裡,它不會無腦地一直走捷運,也不會為了省一站而亂轉車。對演算法來說,跨網路只是走了一條不同類型的關係,完全不需要為這件事改 schema 或寫特例。我們覺得這正好說明了圖的優勢:現實世界裡本來就是關係的東西,在圖裡就直接是關係。

### 節點身分(node identity)

每個節點用 `station_id` 作為唯一識別。我們選 `station_id` 而不是站名,是因為站名可能重複或更動,而 `station_id`(如 `MS01`、`NR01`)是穩定且唯一的鍵;更重要的是,PostgreSQL 與 Neo4j 兩邊都用同一組 `station_id` 當共同的鍵,確保講到中央站的時候,兩個資料庫指的是同一個站,跨庫查詢才能對得起來。

### 圖支援的查詢(至少兩種)

- **最短路徑(`query_shortest_route`)**:用 APOC Dijkstra 以 `travel_time_min` 為權重,在 `CONNECTS_TO|INTERCHANGE_TO` 上找加權最短路徑。這正是圖模型的天生強項,換成 SQL 要用會累積路徑集合的遞迴 CTE。
- **跨網轉乘路徑(`query_interchange_path`)**:靠 `INTERCHANGE_TO` 關係把兩個網路接起來,一次 traversal 就能跨網路找路。
- **延誤漣漪(`query_delay_ripple`)**:用變長度 traversal(`*0..hops`)找出某延誤站 N 跳範圍內受影響的站,起站本身為 0 跳。
- **替代路線(`query_alternative_routes`)**:用 `apoc.path.expandConfig` 枚舉多條不經過指定站的簡單路徑,依總時間排序。

### 兩個資料庫的分工

所以整個系統其實是刻意分工的。會變動、需要精確交易的資料,像訂位、付款、票價、座位,放 PostgreSQL,靠它的交易保證和外鍵關聯;路網拓樸和路徑運算放 Neo4j,靠它的 traversal 和最短路徑演算法。兩邊用同一組 `station_id` 當共同的鍵。我們不是為了用圖而用圖,而是把每種問題交給最擅長它的工具。

---

## Section 4 — Vector / RAG Design

### 4.1 嵌入了什麼,以及為什麼用 cosine similarity

本系統的 RAG 知識來源是一組**政策文件**。我們把四份政策資料檔(`refund_policy.json`、`ticket_types.json`、`booking_rules.json`、`travel_policies.json`)交給 `seed_vectors.py` 處理:腳本會把每一份檔案切成一筆筆獨立的政策文件(例如每一條退款政策、每一個票種、每一個搭乘規則各自成為一筆),為每一筆呼叫 embedding 模型產生一個向量,連同原始文字一起存進 pgvector 的 `policy_documents` 表。因此被嵌入的不是整個資料庫,而是這些用自然語言完整描述、可獨立理解的政策段落。

相似度計算採用 **cosine similarity(餘弦相似度)**。它的關鍵特性是**只衡量兩個向量在語意空間中的方向,而不受向量長度(magnitude)影響**。這對我們的場景特別重要:政策文件通常是一大段文字,使用者的提問卻往往只是一句短問句,兩者的向量長度差很多。如果用會受長度影響的度量,長短差異會干擾判斷;而 cosine similarity 只比較方向,只要一段長政策和一句短問題在語意方向上接近,就會被判定為相似。換句話說,它衡量的是語意上的接近程度,而非文字多寡,非常適合語意搜尋。

### 4.2 RAG 的四個階段

當使用者提出問題時,系統依序執行下列四個階段:

1. **問題向量化**:把使用者的問題,用**與建立索引時完全相同的 embedding 模型**轉換成一個查詢向量。必須是同一個模型,輸出向量才會落在同一個語意空間、可以互相比較。
2. **相似度檢索**:在 `policy_documents` 表中,用 cosine similarity 比較查詢向量與每一筆政策向量,取出語意最接近的前幾筆。本系統設定 `VECTOR_TOP_K = 3`(只取最相關的 3 筆),並設**相似度門檻 0.5**,低於門檻的結果視為不夠相關而過濾掉。
3. **組裝 prompt**:把檢索到的政策文件原文,連同使用者的問題,一起組進要送給 LLM 的 prompt 中,作為回答依據(context)。
4. **生成回答**:LLM 根據被塞入的政策內容生成最終答案。因為答案建立在實際檢索到的政策文字之上,而非模型自己的記憶,能給出貼合本系統規則、可追溯的回覆,並降低幻覺。

### 4.3 Embedding 維度與更換 provider 的後果

不同 embedding provider 產生的向量**維度不同**:本系統使用 **Ollama 時為 768 維**,使用 **Gemini 時為 3072 維**。這個維度在資料灌入(seeding)時就固定下來,並決定了 `policy_documents` 向量欄位的尺寸與整個向量索引的結構。

關鍵後果是:**embedding 模型必須在灌資料前就選定,且查詢端與索引端要一致。** 如果在資料已經灌完之後才更換 provider,新查詢向量的維度(例如 3072)會與既有索引中的向量維度(例如 768)**對不上**,維度不一致就無法計算相似度,整個向量索引等於失效、查不出任何結果。要更換 provider,唯一作法是用新模型把所有政策文件**重新嵌入一次、重建 `policy_documents` 表**,再重新檢索。因此在設計階段就應確定使用哪個 embedding provider,避免事後切換造成索引重建成本。

---

## Section 5 — AI Tool Usage Evidence

> 以下為本專案實際使用 AI(Claude Code)協助的例子。請各成員依自己真實的對話補充/修正 Prompt 原文。

### 範例 1:擴充 RAG 政策知識庫(資料設計)
- **Context**:RAG 助理要能回答更多政策問題,需要擴充 `train-mock-data/` 下的政策 JSON,且每筆會被 `seed_vectors.py` 嵌入成一個向量。
- **Prompt**:在 `refund_policy.json` 新增『月票退款 RF006』,按未使用天數比例退費並收固定手續費,格式照現有條目寫;改完驗證 JSON 仍可被 `json.load` 解析,並確認 `ticket_types` 的 `monthly_pass.refund_rule` 對齊到 RF006。
- **Outcome**:產生了結構一致、ID 交叉對齊的條目,並通過 JSON 驗證。後續以同模式擴充 RF007/RF008、railcard、感應支付等,每筆獨立 commit。

### 範例 2:修正圖查詢的演算法缺陷(查詢撰寫)
- **Context**:`query_alternative_routes` 需要回傳多條不經過某站的替代路線。
- **Prompt**:目前用 `shortestPath` 只會回一條路徑,請改成能列舉多條、排除 avoid 站、依總 `travel_time_min` 排序、取前 `max_routes` 條,回傳格式維持 `list[list[dict]]`。
- **Outcome**:AI 指出 `shortestPath` 搭配 `LIMIT` 實際只會回一條,改用 `apoc.path.expandConfig`(`uniqueness: 'NODE_PATH'`)枚舉多條簡單路徑並排序,解決了需求。

### 範例 3:設計文件論述(設計理由)
- **Context**:撰寫 Section 4 RAG 設計,需要正確說明為何用 cosine similarity。
- **Prompt**:解釋為什麼語意搜尋用 cosine similarity,要講到它只看向量方向、不受長度(magnitude)影響,並完整描述 RAG 四階段與 embedding 維度(Ollama 768 / Gemini 3072)切換 provider 的後果。
- **Outcome**:產出可直接使用的論述段落,並與實作參數(`VECTOR_TOP_K = 3`、門檻 0.5、`vector(768)`)對齊。

### 範例 4:AI 出錯與修正(必備)
- **Context**:請 AI 把產出的文件存到桌面。
- **Prompt**:把這份檔案存到我的桌面。
- **Outcome**:**AI 一開始存錯位置** , 寫到 `C:\Users\niki2\Desktop`,但本機桌面已被 OneDrive 接管(實際路徑是 `C:\Users\niki2\OneDrive\桌面`),導致檔案在畫面上的桌面看不到。**我們發現檔案沒出現後**,AI 透過讀取登錄檔的 Shell Folders 找出真正的桌面路徑,再把檔案複製過去才解決。這提醒我們:AI 對本機環境的假設不一定正確,輸出後一定要實際驗證。

---

## Section 6 — Reflection & Trade-offs

### 設計決策一:多資料庫分工(polyglot persistence)
我們刻意把資料拆給兩種資料庫,而不是全部塞進一個。需要交易保證、外鍵一致性的訂位/付款/票價/座位放 **PostgreSQL**;路網拓樸與路徑運算(最短路徑、延誤漣漪)放 **Neo4j**。理由是這兩類問題的存取模式根本不同:前者是精確、需 ACID 的列級操作,後者是沿關係不定長度地 traversal。用 SQL 做不定長度路徑要寫累積路徑的遞迴 CTE,又難寫又難調效能;交給圖資料庫的 Dijkstra/traversal 則直接而高效。代價是要維運兩套資料庫,我們用同一組 `station_id` 當共同鍵讓兩邊對得起來。

### 設計決策二:訂位金額快照(受控冗餘)
我們在 `national_rail_bookings` 直接存成交 `amount_usd`,而非每次由票價表即時推算(見 Section 2.2)。理由是歷史訂位金額必須不可變:票價日後調整時,舊訂單金額不能跟著變。我們選擇用少量冗餘換取歷史正確性與讀取效能,而不是堅持完全正規化。

### 正式環境會做得不一樣的地方:密碼雜湊與機密管理
目前密碼用 **SHA-256 + 每人 salt**,salt 與雜湊分表儲存,已能防 rainbow table;但 SHA-256 是快雜湊,面對 GPU 大規模暴力破解的韌性不足。正式環境我們會改用 **argon2id(或 bcrypt/scrypt)** 這類具可調 cost factor 的密碼專用 KDF,透過 key stretching 拉高每次嘗試的成本。連帶地,資料庫連線目前每次操作都新開連線(`_connect()`),正式環境應導入 **connection pooling**(如 PgBouncer),並把 DB 帳密、API 金鑰等從設定改用 **secret manager** 管理,而非放在設定檔/環境變數明文。

---

<!-- 選做加分:Section 7,Optional Extension(最多 +15)。
需同時具備:動到資料庫的擴充或實質 UI 改進、詳細註解、本節(動機/schema 變更/範例查詢/測試證據)、repo 根目錄的 TASK6.md。若無擴充可整段刪除。 -->
