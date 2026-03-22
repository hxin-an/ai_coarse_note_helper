# 作業系統 — OS-3
> 來源：`OS-3.pptx` | 產生日期：2026-03-21

## 前言

本章節涵蓋三個主題。首先是**虛擬記憶體**：透過 Demand Paging 讓 process 的邏輯位址空間大於實體記憶體，並探討 Page Replacement 演算法與 Thrashing 問題。接著是**檔案系統**：從抽象的 File 概念到目錄結構、FCB、VFS，以及磁碟上的 Block Allocation 與 Free Space 管理方法。最後是**磁碟排程**與 RAID，說明 OS 如何最小化 I/O 延遲，以及如何透過冗餘提升儲存可靠性。

## 大綱

- [虛擬記憶體（Virtual Memory）](#虛擬記憶體)
  - Demand Paging
  - Page Fault 處理流程
  - Page Replacement Algorithms
  - Belady's Anomaly
  - Frame Allocation 與 Thrashing
  - Locality Principle / Working Set
  - Page-Fault Frequency
- [檔案系統（File Systems）](#檔案系統)
  - File 的抽象概念與操作
  - Directory 結構
  - File System 實作（FCB、VFS）
  - Block Allocation Methods
  - Free Space Management
  - Journaling File System
  - Unix UFS / BSD FFS
- [磁碟排程（Disk Scheduling）](#磁碟排程)
  - 磁碟結構
  - 排程演算法（FCFS、SSTF、SCAN、C-SCAN）
- [RAID](#raid)

---

## 虛擬記憶體

### 核心概念

**虛擬記憶體（Virtual Memory）**：將 logical address space 與 physical memory 完全解耦
- Process 的邏輯位址空間可以**遠大於**實體記憶體
- 執行時只需把「目前會用到的部份」載入記憶體
- **好處：**
  - 多個 process 共享有限的實體記憶體
  - Process 建立更快（不需全部載入）
  - 可以執行比記憶體更大的程式

### Demand Paging

- **最常見的虛擬記憶體實作方式**
- 策略：**只在 page 被存取時才把它載入記憶體**（lazy loading）
- Page table entry 有一個 **valid bit**：
  - `valid`：page 已在記憶體中（合法映射）
  - `invalid`：page 不在記憶體中，或是非法存取

**存取流程：**
1. CPU 產生一個 logical address
2. Page table lookup → invalid bit
3. 觸發 **Page Fault Exception** → 陷入 OS
4. OS 檢查 PCB 判斷：
   - **非法存取** → out-of-bound，終止 process
   - **合法但不在記憶體** → swap in

**Lazy Swapper（Pager）**：只在需要時才 swap，不預先載入

### Page Fault 處理流程

1. 觸發 Page Fault，儲存 CPU 狀態
2. 找到一個空的 frame（或置換一個 frame）
3. 從磁碟把 page 讀進 frame
4. 更新 page table（設 valid bit = 1）
5. 重新執行觸發 fault 的指令

→ 理想情況下對程式透明，程式感覺不到 page fault 的存在

### Page Replacement

**何時發生？** 當 page fault 發生但沒有空 frame 時
- 需要把現有的某個 page swap out，騰出空間
- 若 page 被修改過（dirty bit = 1）才需要寫回磁碟，減少 swap 開銷

**目標**：最小化 page fault 總次數

### Page Replacement Algorithms

#### FIFO（First-In, First-Out）
- 換掉在記憶體中存在最久的 page
- 簡單但效果差
- 有 **Belady's Anomaly**（見下方）

#### Optimal Algorithm
- 換掉**未來最久不會被用到**的 page
- 需要預知未來 → 實際上不可實作，僅作為比較基準

#### LRU（Least Recently Used）
- 換掉**最近最少使用**的 page（以過去的使用行為估計未來）
- 接近 Optimal 的效果，實際中常用

#### Clock Algorithm（Second Chance）
- 所有 in-memory page 組成環狀 linked list
- 每個 page 有一個 **referenced bit**
- 置換時，從當前位置開始掃：
  - referenced bit = 0 → 選這個換掉
  - referenced bit = 1 → 清為 0，繼續掃
- 比 LRU 便宜（不需記錄精確時間戳）

**比較：**
| 演算法 | Page Faults（範例）| 特性 |
|--------|-----------------|------|
| FIFO | 15 | 最差；有 Belady's Anomaly |
| Optimal | 9 | 最佳；不可實作 |
| LRU | 12 | 接近 Optimal；較貴 |
| Clock | 14 | LRU 的近似；常見實作 |

### Belady's Anomaly

**FIFO 的反直覺現象**：給更多 frame 反而產生更多 page fault

- 範例（reference string：1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5）：
  - 3 frames → 9 page faults
  - 4 frames → 10 page faults（多了一個！）
- **為什麼？** FIFO 不考慮頁面的使用頻率，只看載入順序；frame 增加後，驅逐時機改變，反而打亂了「剛好在 cache 裡」的頁面

→ LRU 和 Optimal 不會有 Belady's Anomaly（它們屬於 **stack algorithm**）

### Frame Allocation 與 Thrashing

**每個 process 要分配多少 frames？**

| 方式 | 說明 |
|------|------|
| **Equal Allocation** | 所有 process 均等分配 |
| **Proportional Allocation** | 依 process 大小按比例分配 |
| **Priority Allocation** | 依優先序分配，也可從低優先序 process 搶 frame |

**Local vs Global Replacement：**
- **Local**：只能置換自己的 frame
- **Global**：可以從所有 process 的 frame 中選（更有效率但不可預測）

**Thrashing（抖動）：**
- **定義**：process 的 working set 不在記憶體中，導致頻繁 swap
- **惡性循環**：
  - 大量 page fault → CPU 利用率低
  - → OS 增加 multiprogramming 程度（更多 process）
  - → 每個 process 分到的 frame 更少
  - → 更多 page fault → 更嚴重的 thrashing

### Locality Principle 與 Working Set

**Locality（區域性原理）**：process 傾向於在一段時間內反覆存取相同的一組 pages

- **Working Set**：目前「活躍使用中」的 page 集合
- **Resident Set**：目前在實體記憶體中的 page 集合
- 若 working set ⊄ resident set → thrashing

**避免 Thrashing 的方法：**
1. **Working Set Model**：讓每個 process 的 resident set ≥ working set
2. **Page-Fault Frequency（PFF）**：
   - page fault 頻率太高 → 給更多 frames
   - page fault 頻率太低 → 回收一些 frames
   - → 動態調整每個 process 的 frame 分配

---

## 檔案系統

### File 的抽象概念

**File（檔案）**：一個連續邏輯位址空間的抽象資料型別，用於儲存持久化資訊

**File System（檔案系統）**：
- 提供 organize、create、store、retrieve、delete 的機制
- 實際資料存在 block device（磁碟/Flash）
- 多個檔案系統可透過 **mount** 機制組合成單一目錄樹

### File 操作

| 操作 | 說明 |
|------|------|
| **Create/Open** | `open(Fi)` 把 file entry（metadata）從磁碟載入記憶體 |
| **Read/Write** | 通過 file pointer 存取 |
| **Reposition** | 移動 file pointer |
| **Delete/Truncate** | 刪除/清空 |
| **Close** | `close(Fi)` 把更新後的 metadata 寫回磁碟 |

**Open 後在記憶體中存的 file 資訊：**
- **File pointer**：每個 process 獨立的讀寫位置
- **Access rights**：存取權限
- **File-open count**：多少 process 同時開啟
- **Disk location information**：磁碟位址快取

**存取方式：**
- **Sequential Access**：依序讀寫（read next、write next）
- **Direct Access（Random Access）**：直接跳到指定 block n 讀寫

### Directory 結構

Directory 是一種特殊的 file，內容是 `(name, reference)` 對的列表

**種類：**

| 類型 | 說明 |
|------|------|
| **Single-Level** | 所有檔案在一個目錄，無法重名 |
| **Two-Level** | 每個使用者一個目錄 |
| **Tree-Structured** | 樹狀分層，支援絕對/相對路徑 |
| **Acyclic-Graph** | 允許 sharing（同一個 file 可以有多個名字） |
| **General Graph** | 最通用，但需要垃圾收集或 cycle detection |

**Sharing 的實作方式：**
- **Hard Link**：另一個 directory entry 直接指向同一個 inode；reference count 追蹤有幾個名字
  - 刪除時只減 count，count = 0 才真正刪除
- **Soft Link（Symbolic Link）**：一個特殊 file，內容是目標的路徑名稱；target 不存在時會失效

**General Graph 的問題：**
- Cycle 會讓 reference count 永遠不歸零 → dangling object
- 解法：只允許 hard link 指向 file（不指向目錄）、或定期垃圾收集

### File System 實作

**FCB（File Control Block / inode）**：per-file 的元資料
- 包含：file 大小、timestamps、owner、permissions、disk block map

**In-memory 結構（OS 開啟 file 後）：**
- **System-wide open-file table**：記錄所有被開啟的 file
- **Per-process open-file table**：每個 process 自己的 file descriptor table，指向 system-wide table

**VFS（Virtual File System）：**
- 提供統一的 API，讓應用程式不管底下是什麼 file system（ext4、FAT32、NTFS）都用同樣的 `open()`、`read()`、`write()`
- 每個實體 file system 實作 VFS 的共同介面

**Directory Organization：**
| 結構 | 說明 |
|------|------|
| **Linear list** | 簡單，搜尋慢（O(n)），可用 cache 改善 |
| **Hash Table** | 快（O(1)），但需處理 collision 和固定 table 大小 |
| **B-Tree / HTree** | 固定深度的平衡樹，大目錄效能好 |

### Block Allocation Methods

檔案的磁碟 block 如何配置？

#### Contiguous Allocation（連續配置）
- 每個 file 占用連續的 disk blocks
- Directory entry 只需記錄起始 block 和長度
- 優點：簡單、random access 直接
- 缺點：file 無法輕易增長；產生 external fragmentation
- 折衷：**Extents**，每次配置一個連續 chunk，記錄所有 extent 的位置

#### Linked Allocation（鏈結配置）
- Directory entry 指向第一個 block，每個 block 包含下一個 block 的指標
- 優點：無 external fragmentation；file 可輕易增長
- 缺點：不支援 random access（需從頭走到底）；每個 block 浪費一點空間存指標
- 折衷：**FAT（File Allocation Table）**

**FAT（用於 MS-DOS / 早期 Windows）：**
- 整個 volume 有一個 FAT table，每個 disk block 對應一個 FAT entry
- FAT entry 記錄「這個 block 的下一個 block 在哪」
- → FAT 全部存在記憶體中，random access 變快（不需讀磁碟）

#### Indexed Allocation（索引配置 / inode）
- Directory entry → inode number → inode 儲存所有 data block 指標
- 優點：支援 random access；無 external fragmentation
- **UNIX UFS 的 inode 設計（應對大 file）：**

| 類型 | 說明 | 適合大小 |
|------|------|---------|
| Direct blocks | inode 直接記錄 data block 位址 | 小 file |
| Single indirect | inode → 一層 index block → data blocks | 中型 file |
| Double indirect | inode → index block → index block → data blocks | 大 file |
| Triple indirect | 三層 index | 超大 file |

### Free Space Management

磁碟上哪些 block 是空的？

| 方法 | 說明 | 優缺點 |
|------|------|--------|
| **Bit vector** | 每個 block 一個 bit（0=free, 1=used） | 容易找連續空間；需額外空間 |
| **Linked list** | 空 block 連成 linked list | 不易找連續空間；不浪費額外空間 |
| **Grouping** | 第一個空 block 儲存接下來 n 個空 block 的位址 | 可快速找到大量空 block |
| **Counting** | 每個空 block 記錄「後面有幾個連續空 block」 | 適合有大量連續空間的情況 |

### Journaling File System（日誌式檔案系統）

**問題**：系統崩潰（crash）時，正在寫入的 file system 可能留下不一致的狀態

**解法：Log（日誌）**
1. 所有更新先寫入 log（commit）
2. 再非同步地寫入實際 file system
3. 若 crash → 重開機時重放 log（redo logging）
4. 寫入 file system 成功後，從 log 移除該 transaction

→ 代表：系統崩潰後 file system 永遠是一致的狀態

### Unix UFS / BSD FFS

**UFS（Unix File System）：**
- 磁碟分三區：**Superblock**（全域資訊）、**Inodes**、**Data blocks**
- Superblock 記錄：file system 大小、free block 數量、inode 數量等
- 空閒 block 以 linked list 管理
- 問題：磁碟存取分散，每次讀取幾乎都需要 seek

**BSD FFS（Fast File System）：**
- **Cylinder Group**：把磁碟分成多個 cylinder groups
- 同一個 directory 的 file 盡量放在同一個 cylinder group
- inode 與其 data block 放在同一個 cylinder group
- → 減少 seek time，提升 sequential read 效能

---

## 磁碟排程

### 磁碟結構

磁碟存取時間 = **Seek time**（磁頭移到正確 cylinder）+ **Rotational latency**（等待 sector 轉到磁頭下）+ Transfer time

- Seek time >> Rotational latency → **最小化 seek distance 是主要目標**
- **Disk bandwidth** = 總傳輸 bytes / 總時間

磁碟定址為一維的 logical block array，從最外圈 cylinder 開始依序編號

### 排程演算法

以請求序列 {98, 183, 37, 122, 14, 124, 65, 67}，起始 head = 53 為例：

| 演算法 | 策略 | Total Seek | 說明 |
|--------|------|-----------|------|
| **FCFS** | 照到達順序 | 638 | 最差，亂跳 |
| **SSTF** | 選最近的請求（Shortest Seek Time First） | 320 | 效果好，但可能 starvation |
| **SCAN** | 磁頭往一個方向走到底，回頭再走 | 299 | 像電梯；公平但邊緣 cylinder 等較久 |
| **LOOK** | 同 SCAN 但只走到最後一個請求（不到底） | — | 比 SCAN 省一點 |
| **C-SCAN** | 單方向掃，到底後直接快速跳回起點再掃 | 183+α | 更均勻的等待時間 |

**C-SCAN 的優勢：**
- SCAN 回程時服務的 cylinder 剛剛才被掃過（等待時間短）但去程的 cylinder 等很久 → 不公平
- C-SCAN 只在一個方向服務，等待時間更均勻

---

## RAID

**RAID（Redundant Array of Independent Disks）**：用多顆磁碟提升可靠性與效能

| Level | 技術 | 特性 |
|-------|------|------|
| **RAID 0** | Striping（條帶化） | 高效能，無冗餘；一顆壞掉全 lost |
| **RAID 1** | Mirroring（鏡像） | 每份資料都有備份；write 兩次，read 可加速 |
| **RAID 4** | Block-level parity | Parity 集中在一顆磁碟（bottleneck） |
| **RAID 5** | Distributed parity | Parity 分散在各磁碟；常見選擇 |
| **RAID 6** | Double distributed parity | 可容許兩顆磁碟同時故障 |
| **RAID 1+0** | Stripe of mirrors（先 mirror 再 stripe） | 高效能 + 高容錯 |
| **RAID 0+1** | Mirror of stripes（先 stripe 再 mirror） | 效能相近，但容錯較差 |

**RAID 1+0 vs RAID 0+1 的關鍵差異：**
- **RAID 1+0**（stripe of mirrors）：每對磁碟互為鏡像，再跨 group stripe
  - 任意一對中一顆壞掉：另一顆還在，整體仍可運作
  - 容錯更好：最壞情況下每個 mirror group 各壞一顆（總共 n/2 顆）都能撐住
- **RAID 0+1**（mirror of stripes）：先 stripe 兩組，再互為鏡像
  - 一組內一顆壞掉 → 整組 stripe 失效 → 只剩另一組在撐
  - 再有一顆壞掉就全掛 → 容錯差

→ **RAID 1+0 在生產環境通常比 RAID 0+1 更受信任**

**Hot-spare（熱備）：**預留一顆空磁碟，當有磁碟故障時，自動開始重建資料，縮短 RAID 降級的時間窗口
