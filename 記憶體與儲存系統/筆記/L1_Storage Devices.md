## Agenda

1. 存儲裝置基礎概念 (Concepts of Storage Devices)

2. 傳統硬碟 (Hard Disk Drives, HDD)

- **運作原理 (How it works)**
- **疊瓦式磁記錄 (SMR)**：
- **磁碟調度 (Disk Scheduler)**
- **磁碟陣列 (RAID)**

3. 固態硬碟 (Solid State Drives, SSD)

- **運作原理 (Read/Program/Erase)**
- **多層單元技術 (MLC)**
- **數據留存錯誤 (Retention Error)**。
- **Flash Translation Layer, FTL**

# 前言

## AI/ML 發展與記憶體挑戰

---

- **記憶體容量發展追不上模型成長**：
    - 過去 10 年，AI/ML 模型大小增長了 $10^7$ 倍，
    - 記憶體容量大約每兩年才翻倍一次
        - 例如 :  2020 年的 A100 為 40GB，2022 年的 H100 僅增至 80GB
- **解決方案**：
    1. **量化 (Quantization)**：將資料壓縮（如降至 2-bit 或 4-bit），但可能會降低模型準確度。
    2. **資料轉移**：若不想犧牲準確率，可將資料移至 CPU 記憶體，甚至移到 Storage 中。

# Concepts of Storage Devices

## 記憶體階層 (Memory Hierarchy)

---

![image.png](attachment:b96b6de9-8339-4427-99c9-4d507463eabd:image.png)

- **設計目標**：在 **存取時間 (Access Time)** 與 **成本 (Cost)** 之間達成平衡。
- **理論依據  : Locality Principle**
    - **Spatial Locality**：當存取某個資料時，其鄰近的資料也很有可能在近期被存取（例如存取陣列時會順序存取下一個位置）。
    - **Temporal Locality**：最近剛被存取過的資料，在不久的將來極有可能再次被存取。
- **階層運作成效**：
    - **高效率快取**：由於局部性原理，CPU Cache 不需太大，僅需存放少量常用資料。
    - **高命中率**：根據 Intel 的報告，良好的快取設計其 Cache Hit Rate 可高達 90% 到 99%。
    - **效能優化**：這代表僅有約 1% 的存取需求需要真正去存取較慢的主記憶體，大幅提升運算速度。

### 常見三個記憶體階層

1. **CPU Cache (SRAM)**：
    - **速度與成本**：速度最快（奈秒等級，比 DRAM 快十倍），但非常昂貴且體積大。
    - **容量**：通常只有 MB 等級。
    - **特性**：揮發性 (Volatile)，斷電會遺失資料。
2. **主記憶體 (DRAM)**：
    - **速度與成本**：延遲約 10-100 奈秒，製造成本較低。
    - **容量**：較大，一般可達 16GB 到 64GB。
    - **特性**：揮發性。需要消耗額外的電力（漏電流功率）來維持電容狀態以確保資料正確。
3. **儲存裝置 (Storage - HDD / SSD)**：
    - **速度與成本**：速度最慢（比記憶體慢三個數量級以上，為微秒到毫秒等級），但價格最便宜。
    - **容量**：極大（TB 等級）。
    - **特性**：非揮發性 (Non-volatile)，斷電後資料不會遺失，是保障資料 100% 安全的成熟方案。

OS execution time :  介於 memory 和 storage 之間

- 從 memory 取資料 : 使用 CPU loads/store
- 從 storage 取資料 : execute OS (system calls)

> **新興挑戰**：當今最新的超低延遲儲存裝置（如新型 SSD）延遲已降至 1-10 微秒，與 OS 執行時間相當。這帶來了全新的研究議題：未來的 CPU 可能會嘗試繞過 OS，直接存取儲存裝置資料。
> 

## What is Storage & Data

---

- Data 定義 : a sequence of 0 and 1
- Storage 定義：儲存裝置底層都是類比信號
    - 磁場方向 : HDD
    - 電壓高低 : SSD
    - 電容是否充電 : DRAM
    - 電阻高低 : ReRAM, PCM, STT-MRAM
- **存取粒度 (Granularity)**：
    - SRAM / DRAM：可 Byte-addressable（位元組定址）
        - 因受限於 Cache Line 設計，通常一次存取 **64 Bytes**。
    - SSD：受限於硬體架構，存取單位為 flash Page（約 **4KB 到 16KB**）。
    - HDD : 受限於硬體架構，存取單位為 sector（約 512**B 到 4KB**）。

### 比較表

| **特性** | **SRAM** | **DRAM** | **HDD** | **NAND flash** | **STT-RAM** | **ReRAM** | **PCM** | **FeRAM** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **單元大小 ($F^2$)** | 120–200 | 60–100 | N/A | 4–6 | 6–50 | 4–10 | 4–12 | 6–40 |
| **寫入壽命** | $10^{16}$ | $>10^{15}$ | $>10^{15}$ (機械零件) | $10^4–10^5$ | $10^{12}–10^{15}$ | $10^8–10^{11}$ | $10^8–10^9$ | $10^{14}–10^{15}$ |
| **讀取延遲** | ~0.2–2ns | ~10ns | 3–5ms | 15–35$\mu$s | 2–35ns | ~10ns | 20–60ns | 20–80ns |
| **寫入延遲** | ~0.2–2ns | ~10ns | 3–5ms | 200–500$\mu$s | 3–50ns | ~50ns | 20–150ns | 50–75ns |
| **漏電功耗** | High | Medium | (機械零件) | Low | Low | Low | Low | Low |
| **動態能量 (R/W)** | Low | Medium | (機械零件) | Low | Low/High (非對稱) | Low/High (非對稱) | Medium/High | Low/High |
| **成熟度** | Mature | Mature | Mature | Mature | Test chips | Test chips | Test chips | Manufactured |

## **I/O Devices & OS I/O Systems**

---

![image.png](attachment:71efc33b-143b-4395-888f-731a93d2630f:image.png)

> 
> 
> 
> **資料傳遞流程**
> 
> - **User mode**：
>     - Applications  透過 `sys_read()` 或 `sys_write()` 等 System Call 發出請求。
> - **核心模式 (Kernel)**：
>     - 請求首先進入 **Virtual File System**。
>     - 視情況經過 **Page Cache** 或直接與 **Mapping Layer** 交互。
>     - 接著傳遞至 **Block I/O Layer** 與 **Block Device Driver**。
>     - 最後抵達硬體的 **Storage Devices (Firmware)** 完成實際物理存取。

### 本課程將涵蓋的內容

- 儲存裝置 (Storage Devices)
    - **傳統硬碟 (Hard Disk Drive, HDD)**。
    - **疊瓦式磁記錄硬碟 (Shingled Magnetic Recording, SMR)**。
    - **基於快閃記憶體的固態硬碟 (NAND-Flash-based SSD)**。
- I/O 軟體棧 (I/O Stacks)
    - **虛擬檔案系統 (Virtual File System)**：提供統一的檔案操作介面。
    - **分頁快取 (Page Cache)**：暫存檔案資料以提升存取速度。
    - **區塊 I/O 層 (Block I/O Layer)**：管理 I/O 請求的排隊與調度。
    - **區塊裝置驅動程式 (Block Device Driver)**：與底層硬體進行溝通的橋樑。
- 應用與系統行為 (Applications)
    - **鍵值儲存 (Key Value Store)**。
    - **圖形資料 (Graph)**。
    - **資料去重複化 (Data Deduplication)**。

## **Common Storage Devices**

---

![image.png](attachment:ed725846-402f-48b8-b0b3-c878f67e2b29:image.png)

- **硬碟機 (HDD)**：
    - **組成 :** 主軸 (Spindle)、磁盤 (Platters)、讀寫頭 (Head) 與驅動臂 (Actuator)
    - **運作原理**：磁盤不斷旋轉，讀寫頭利用磁力讀寫資料，
        - **讀寫頭不會碰觸到磁盤表面，**若碰觸會造成毀損
        - 新技術 SMR (疊瓦式磁記錄) 使得硬碟容量可達 15TB-20TB 以上。
- **固態硬碟 (SSD)**：
    - **運作原理**：內部全為晶片（NAND Flash、Controller 等），**無任何機械可動部件**。
    - **優缺點**：
        - 優點 : 速度遠快於 HDD、靜音、耐摔防震、重量輕
        - 缺點 : 寫入壽命短，且不適合長期斷電存放。

# **Hard Disk Drives (HDD)**

## Physical Organize of HDD

---

![image.png](attachment:2e9fb1a3-db70-4b40-a7bd-b64fe36b123f:image.png)

### 物理組件 (Physical Components)

- **碟盤 (Platters)**：硬碟由一個或多個碟盤組成。
    - **雙面存取**：每個碟盤都有上下兩個面（Sides/Surfaces）可用於儲存資料。
    - **讀寫頭與表面距離**：磁頭（Arm Head）與碟盤表面之間保持著極小的距離，透過 Magnetic 進行讀寫。
- **轉軸 (Spindle)**：所有的碟盤都固定在同一個轉軸上，帶動碟盤同步旋轉。
- **磁臂與讀寫頭 (Arm & R/W Head)**：磁臂帶動讀寫頭在碟盤表面移動以定位資料。

### 邏輯劃分 (Logical Division)

- **磁軌 (Tracks)**：碟盤表面被邏輯地劃分為許多同心圓，稱為「磁軌」。
- **磁柱 (Cylinder)**：所有碟盤上相同半徑（相同位置）的磁軌集合，定義為一個「磁柱」。
- **磁區 (Sectors)**：
    - 每個磁軌進一步劃分為固定大小的「磁區」。
    - **大小演進**：傳統磁區大小為 **512B**，但在 2011 年後為了提升效率與容量，已逐漸合併定義為 **4KB** (Advanced Format)。

### Read/Write Head Deep Dive

![image.png](attachment:ae3ce712-d737-4a03-8cdd-67eff328d25c:image.png)

**磁頭組成**

- **讀取頭 (Read Head)**：採用**巨磁阻 (Giant Magnetoresistance, GMR)** 技術。
- **寫入頭 (Write Head)**：採用**感應式寫入 (Inductive write)** 元件。

**讀取原理：GMR 狀態切換**

![image.png](attachment:ff4550f9-355a-4043-ae04-353ee7e6a15a:image.png)

1. 核心架構 : 兩層磁性物質中間夾著一層薄薄的非磁性層組成
    - **Fixed Layer**：磁場方向被固定住做為參考，不會改變 。
    - **Free Layer**：磁場方向會隨著下方硬碟磁盤的磁場而**變動** 。
2. 如何區分 0 與 1
    - **高電阻狀態 (High Resistance State)**：
        - 自由層與固定層磁場方向**反平行 (Anti-Parallel)**。
        - 對應邏輯數值 **0**。
    - **低電阻狀態 (Low Resistance State)**：
        - 自由層與固定層磁場方向**平行 (Parallel)**。
        - 對應邏輯數值 **1**。

**寫入原理**

- 透過 **Write Current** 改變電感元件的磁場，進而改變下方記錄介質的磁極方向。
- 難點 : 控制磁場大小

## HDD 提升存儲密度方法

---

### 區域位元記錄 (Zone Bit Recording)

![image.png](attachment:1e87ab7d-949f-4d58-ae54-d9d49a57ba35:image.png)

由於硬碟磁盤的物理幾何特性，外圈磁軌的周長比內圈磁軌長 。

- **核心概念**：
    - 原因 : 物理空間較大的 **Outer tracks** 能存儲更多的資料，固定劃分方法會浪費外ㄑㄩㄢ空間 。
    - 方法 : 固定劃分方式 →  外圈劃分成更多磁區。
        - 不論內外圈都只切成 3 個磁區 → 內圈固定 3 磁區 外圈切成 6 磁區
    - 外圈區域（Outer zones）由更多的磁區組成 。

### **疊瓦式磁記錄 (Shingled Magnetic Recording, SMR)**

提升硬碟儲存密度而開發的技術，但它同時也帶來了寫入上的限制。

![image.png](attachment:5fb855eb-8c54-4598-8ad6-3764140e0f33:image.png)

- **為什麼需要 SMR** : 讀取頭 的物理尺寸通常比 寫入頭 小很多 。
- **傳統磁軌 (Conventional Tracks)**：避免寫入時干擾到鄰近磁軌，每個磁軌之間須留有足夠的寬度，這限制了磁軌的密度 。
- SMR 的運作原理
    - **重疊磁軌**：SMR 利用讀取頭較小的特性，讓寫入頭在寫入時像「屋頂瓦片」一樣，部分重疊在先前的磁軌上 。
    - **優點**：可以在相同的磁碟表面積上擠進更多的磁軌，大幅提升儲存容量。
- SMR 的致命傷：順序寫入限制 (Sequential Write Constraint)
    - 由於磁軌是重疊的，產生了一個嚴重的問題：
        - **無法直接更新**：你不能直接更新先前磁軌（Prior Tracks）中的資料，因為寫入頭太寬，更新資料時會連帶**破壞 (Overwrite)** 到後方重疊的磁軌 。
    - **解決方法**：如果要修改資料，必須採取「**讀取 (Read) $\rightarrow$ 修改 (Modify) $\rightarrow$ 寫入 (Write)**」的流程，將資料重新寫入到新的空白磁軌中 。
    - **Write Pointer**：系統必須維護一個寫入指標，確保資料是按順序寫入的 。

**總結：**SMR 用「寫入效能」換取「儲存空間」。

**適用場景 :** 適合用來做備份或冷數據儲存（少寫多讀），不適合需要頻繁隨機寫入的情境。

## Disk Performance

---

- **Disk Performance**：
    - $\text{Total Time} = \text{Seek Time} + \text{Rotational Delay} + \text{Transfer Time}$
    - **尋道時間 (Seek Time)**：
        - 定義：將 Disk Arm 移動到正確 Track 所需的時間。
        - 數據：平均約為 **4.9ms**。
    - **旋轉延遲 (Rotational Delay)**：
        - 定義：旋轉 Spindle 使 Desired Sector 移動到磁頭下方的時間。
        - 轉速指標 (RPM)：例如 10000 RPM 的硬碟，旋轉一圈約需 **6ms**。
    - **傳輸時間 (Transfer Time)**：
        - 定義：磁頭實際在碟盤表面讀取或寫入（r/w）資料的時間。
- **存取特性**：
    - 擅長**順序存取 (Sequential Access)**
    - 不擅長**隨機存取 (Random Access) :** 因為磁頭必須頻繁在不同磁軌間移動 。

## 磁碟排程 (Disk Scheduler)

---

為了減少磁頭移動的距離（即降低 Seek Time），作業系統會對 I/O 請求進行排程：

- **FCFS (First Come First Serve)**：按請求順序服務，效能最差 。
- **SSTF (Shortest Seek Time First)**：優先選擇距離當前磁頭位置最近的請求，但可能導致遠端請求發生 **Starvation**。
- **SCAN (Elevator Algorithm)**：磁頭像電梯一樣向一端移動並服務途中所有請求，到頭後再反向移動，確保每個請求在每輪都能被服務 。

## RAID 技術 (Redundant Array of Inexpensive Disks)

---

相反的技術 : Just a Bunch of Disk (JBOD)，完全不做更進一步管理 

讓多顆硬碟協作以平衡可靠性、效能與容量 ：

![image.png](attachment:3644b8f4-5f21-49f8-a885-281bcb721acf:image.png)

- **RAID 0 (Striping)**：資料分佈在多顆磁碟，僅追求**效能**與容量，無容錯能力 。
- **RAID 1 (Mirror)**：全量備份資料，追求最高**可靠性**
- **RAID 0 + 1** : 先做 RAID 1 在做 RAID 0 已達到 reliable + performance
- **RAID 5**：至少需 3 顆磁碟，透過**奇偶校驗 (Parity)** 提供容錯，損壞一顆磁碟時可重建資料 。
- **RAID 50**：RAID 5 + RAID 0 的組合，能保護更多顆磁碟
- **RAID 5 的限制**：無論磁碟數量多少，一次只能重建 1 顆磁碟的資料

---

# Solid State Drives (SSD)

## NAND Flash 基礎

---

### 概觀

**NAND Flash Memory** 是目前最廣泛使用的儲存技術，應用於 USB 隨身碟、SSD、手機等。

> **USB 隨身碟 vs SSD 的差異**：兩者使用相同的 NAND Flash 晶片技術，但品質等級不同：
> - **USB**：使用較低品質（error-prone）的晶片 → 價格便宜，但需要更複雜的 ECC 處理 → 速度較慢
> - **SSD**：使用高品質、低錯誤率的晶片 → 價格較高，但效能更佳

另一種 Flash 技術是 **NOR Flash**：
- 用於取代 ROM，儲存 BIOS 和 Firmware
- 支援隨機讀取（每個 cell 有獨立 bitline）
- 但 cell 尺寸較大，不適合用作大容量儲存

**為什麼 HDD 還沒被完全取代？**
- SSD 的寫入壽命遠低於 HDD：$10^3$ P/E cycles vs HDD 的 $10^{16}$ 次
- 例：1TB QLC SSD 只能承受 $10^3 \times 1\text{TB}$ 的寫入量

### SSD 實體架構

SSD 的組成層次（由大到小）：

$$\text{Channel} \to \text{Chip} \to \text{Die} \to \text{Plane} \to \text{Block} \to \text{Page} \to \text{Cell}$$

- **1 Die** = 2 Plane × 1024 Block × 512 Page × 4KB = **4GB（32Gb）**
- **同一條 Wordline 上的所有 cell** 屬於同一個 Flash Page
- SSD 內部有 **Controller**（微型 CPU）和 **DRAM**（作為 Translation Table 的快取）
- **Page 大小（製程決定）**：Page 大小（4KB、16KB、32KB 等）**在製造時設定，出廠後無法更改**；與 OS 的 Page Size 完全無關

---

## NAND Flash Cell 運作原理

---

### Cell 結構與資料表示

**Floating-Gate Transistor** 是 NAND Flash 的核心：
- 資料儲存方式：cell 中**是否有電子**在 floating gate 內
  - **Bit 1**：floating gate 沒有電子（無負電荷）→ 低 Vth，通電時有電流
  - **Bit 0**：floating gate 有電子（有負電荷）→ 高 Vth，通電時無電流

**如何區分 0 和 1（讀取）：**
- 施加讀取電壓 $V_{read} = 2.5\text{V}$
  - floating gate 無電子（Bit 1）：$V_{th} = 2\text{V} < V_{read}$ → 有電流 → 讀到 **1**
  - floating gate 有電子（Bit 0）：$V_{th} > V_{read}$ → 無電流 → 讀到 **0**

### 三種操作

| 操作 | 說明 | 施加電壓 |
|------|------|---------|
| **Program（寫入）** | 將電子從 P-substrate 打入 floating gate（電子穿越絕緣層） | ~20V（高能量） |
| **Read（讀取）** | 檢查 n-source 與 n-drain 之間的電流值 | ~2.5V |
| **Erase（抹除）** | 從 floating gate 移除電子 | 0V 施於 gate，~20V 施於 substrate |

> **為什麼 Erase 必須以 Block 為單位？**
> 同一個 Block 內的所有 Pages 共享同一塊 P-substrate。對 P-substrate 施加 20V 時，整個 Block 內所有 floating gate 中的電子同時被拉出 → 無法只 erase 單一 Page。

**重要限制：**
- **Erase 的單位是 Block**（包含數百個 Pages）
- **Write/Read 的單位是 Page**（4KB ~ 16KB）
- → **Erase 單位 >> Write 單位**：無法直接覆寫一個 page，必須先 erase 整個 block

### Program 與 Read 的細節

**Program a Page（寫入某一頁）：**
- 目標 page 的 wordline 施加高電壓（~20V）注入電子
- 不需寫入的 cell：bitline 施加 **Inhibit 電壓（VINH ≈ 5V）** → 產生水平方向的電場，阻止電子穿越絕緣層進入 floating gate → 保護非目標 cell 不被誤寫

**Read a Page（讀取某一頁）：**
- 目標 page 的 wordline 施加 $V_{read} = 2.5\text{V}$
- 其他 page 的 wordline 施加 $V_{pass} = 5.0\text{V}$（讓其他 cell 導通，避免干擾）
- → 無法只 erase/write 一個 page，需採用 **read-modify-write** 到新 page 的方式

### NAND vs NOR Flash

- **NOR Flash**：每個 cell 有獨立 bitline → 支援 **random read**（可直接定址）
- **NAND Flash**：cell 串接共用 bitline → 一次只能 **讀出整個 page**，不支援 random read
- → NAND 密度更高、成本更低，適合大容量儲存

---

## Multi-Level Cells（多層單元）

---

**核心概念：讓一個 cell 儲存多個 bit**

透過區分 **多個電壓區間（threshold voltage states）** 來表示不同的值：

| 技術 | Bits/Cell | 電壓狀態數 | 速度 | 壽命（P/E Cycles） | 成本 |
|------|-----------|-----------|------|------------------|------|
| **SLC** | 1 bit | 2 | 最快 | ~100,000 | 最貴 |
| **MLC** | 2 bits | 4 | 中等 | ~10,000 | 中等 |
| **TLC** | 3 bits | 8 | 較慢 | ~3,000 | 便宜 |
| **QLC** | 4 bits | 16 | 最慢 | ~1,000 | 最便宜 |

**為什麼圖上顯示的是「分佈（distribution）」而非單一電壓值？**
- 由於製程偏差（Cell Variation），即使施加相同電壓，不同 cell 的實際 Vth 也會有差異
- → 每個「狀態」在電壓軸上呈現一段**常態分佈**而非一個點
- → MLC/TLC 的分佈必須比 SLC 更緊密，才能區分更多電壓狀態

### MLC 的 Programming 挑戰

**Program and Verify（P&V）機制：**
1. 施加 Program 電壓，注入電子
2. 立即 Read（Verify）檢查 Vth 是否達到目標
3. 若未達到 → 繼續注入；若超過 → 無法撤回（只能 erase 整個 block）
4. 重複直到所有 cell 到達目標電壓範圍

→ MLC 需要多次 P&V 迭代，**寫入時間遠長於 SLC**

---

## Retention Error（資料留存錯誤）

---

**問題：floating gate 中的電子會自然逸散**

- **Retention Error**：隨時間推移，電子緩慢從 floating gate 逃跑，導致 Vth 下降
- **P/E Cycle 加速劣化**：反覆 program/erase 使絕緣層變薄，電子更容易逸散

**影響：**
- 電壓分佈往低電壓方向移動（例：`00` 狀態 → 誤判為 `01`）
- → **Bit Error Rate（BER）上升**

**解決方法：Read Retry**
- 若標準電壓 $V_{REF}$ 讀出 BER 太高，則**調整 reference voltage** 重新讀取
- 步驟：
  1. 第一次 Read：BER 太高（High BER）
  2. 調整 $V_{REF}' \leftarrow$ 第一次 Read Retry：BER 降低
  3. 若仍高，再調整 $V_{REF}''$ → 第二次 Read Retry：成功（Low BER）

**代價：** 額外的讀取操作增加延遲，影響效能

**衡量壽命的指標：**
- **P/E Cycles**（隱式）：記錄每個 block 被 erase 的次數
- **Bit Error Rate（BER）**（顯式）：直接反映 cell 的可靠性狀態

---

## Flash Translation Layer（FTL）

---

**FTL 是 SSD Controller 裡最核心的軟體層**，解決兩個根本問題：

| 問題 | 解決方案 |
|------|---------|
| Sequential Write Constraint（erase-before-write） | **Address Remapping（LBA → PBA）+ Garbage Collection** |
| Limited Lifetime（P/E Cycles 有限） | **Wear Leveling** |

**SSD 架構：**
```
Host → Device Driver → FTL (Address Translator + Wear Leveler + GC) → MTD → NAND Flash Chips
                                             ↓
                                         DRAM (Data Buffer + Translation Table)
```

- **MTD（Memory Technology Device）**：直接對 NAND Flash 做 read/program 操作的底層介面
- **Translation Table**：儲存在 DRAM 中，記錄 LBA → PBA 的映射

### Address Translation（位址轉換）

**為什麼需要 Address Remapping？**
- NAND Flash 的 erase-before-write 特性 → 不能原地更新（in-place update）
- SSD 採用 **Out-of-place Update**：新資料寫到新位置，舊位置標為 invalid

**對 Host 透明：**
- Host 只操作 **LBA（Logical Block Address）**（虛擬位址）
- SSD 內部維護 LBA → PBA（Physical Block Address）的映射表

**Page-Level Address Translation：**
- 每個 LBA page 對應一個 PBA page（最精細）
- **問題：映射表非常大**
  - 1TB SSD（4KB page）：$1\text{TB} / 4\text{KB} = 256\text{M}$ 個 pages
  - 每個 entry 需 28 bits（20 bits block + 8 bits page）
  - 映射表大小：$256\text{M} \times 28 / 8 \approx 896\text{MB}$
  - → **SSD 內部需要大量 DRAM**（約為 SSD 容量的 1/1000）

**Block-Level Address Translation：**
- 以 block 為單位映射（較粗粒度）
- **問題：block 利用率低；write overhead 高**（一個 page 更新就要搬整個 block）

### Garbage Collection（垃圾回收）

**問題：** Out-of-place update 會產生大量 invalid pages，浪費空間

**GC 目標：** 回收 invalid pages，騰出 free blocks（Defragmentation）

**GC 三步驟：**
1. **Victim Block Selection**：選一個 block 來回收
2. **Live Pages Copy**：把 victim block 裡所有 valid pages 複製到 free block
3. **Release Victim Block**：Erase victim block → 變成 free block

**Victim Block 選擇策略：**

| 策略 | 邏輯 | 優點 | 缺點 |
|------|------|------|------|
| **Greedy** | 選 invalid pages 最多的 block | 最小化 live page 複製量 | Cold data 佔滿 SSD 時，少數 hot block 反覆被選 → 提前損壞 |
| **Cost-Benefit (CB)** | 最大化 $\frac{Age \times (1-V)}{2V}$ | 兼顧新鮮度（Age）與有效率（V） | 需追蹤時間戳 |
| **Hot/Cold Separation** | 根據存取頻率將 hot/cold pages 放到不同 block | GC 時 cold block 幾乎全是 invalid page → 效率高 | 需準確的 hot/cold 識別機制 |

> **Cost-Benefit 公式說明：**
> - $Age = T_{current} - T_{last\_page\_invalidate}$（block 有多「冷」）
> - $V$：block 中 valid pages 的比例
> - 分母 $2V$：每個 valid page 需要 1 次 read + 1 次 write → 代價為 $2V$

**Hot/Cold 識別方法：**
- **Counter-based**：記錄每個 page 的存取次數（需考慮：計數器多少 bits？計數器滿了怎麼辦？）
- **List-based**：用 LRU 或 FIFO 維護 hot/cold 排序（需考慮精確度與維護成本）

### Wear Leveling（磨損均衡）

**問題：** 若某些 block 反覆被寫入，會比其他 block 更早達到 P/E Cycle 上限而損壞

**目標：** 盡量讓所有 block 的 erase count 保持均衡

#### Dynamic Wear Leveling (DWL)

- **策略**：寫入新資料時，優先選擇 erase count 較低的 **free blocks**
- **問題**：只能在 hot blocks 之間均衡；cold blocks（長期存放靜態資料）的 erase count 永遠偏低
  - → Hot blocks 仍然比 cold blocks 損耗快

#### Static Wear Leveling (SWL)

- **策略**：主動將 cold data 從 young blocks（erase count 低）搬移到 old blocks（erase count 高）
- → 騰出 young block 給 hot data 使用，讓所有 block 更均衡損耗
- **代價**：額外的資料搬移 → 效能下降

**SWL – Dual Pool Wear Leveling：**
- 將 blocks 分為 hot pool 和 cold pool
- 動態調整 pool 大小（Adaptive Pool Resizing）
- 對 cold data 維護 access count（判斷 hot/cold），但不需追蹤精確時間

**SWL – Progressive Wear Leveling (PWL)：**
- **關鍵觀察**：SWL 的觸發時機很重要
  - **早期（erase count 低）**：懶得做 SWL → 效能好
  - **晚期（erase count 高）**：積極做 SWL → 延長壽命
- **方法**：設定一個動態增長的 threshold，只有當某 block 的 erase count 超過該 threshold 才觸發 SWL

**SWL – Error-Rate-Aware Wear Leveling：**
- **關鍵觀察**：P/E Cycle 數不能準確反映 cell 的實際健康狀態
  - 原因：Cell Variation（製程偏差）導致同樣 P/E Cycles 的 cells 可能有不同 BER
- **策略**：以 **BER（Bit Error Rate）** 取代 P/E Cycle 作為磨損度量
  - 追蹤每個 block 中「永久錯誤 bits（permanent error bits）」的最大值
  - → BER 較低（更健康）的 block 可以承受更多寫入 → 分配更多 hot data
  - → 真正延長 SSD 的整體使用壽命