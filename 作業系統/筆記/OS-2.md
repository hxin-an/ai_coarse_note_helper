# 作業系統 — OS-2
> 來源：`OS-2.pptx` | 產生日期：2026-03-21

## 前言

本章節涵蓋兩大核心主題：CPU 排程與記憶體管理。CPU 排程討論 OS 如何決定哪個 process/thread 在何時使用 CPU，從最簡單的 FCFS 到複雜的 Multilevel Feedback Queue，並延伸至 Real-Time 系統的特殊需求。記憶體管理則從基本的地址概念出發，介紹 MMU、分段、分頁（Paging）與 TLB，說明 OS 如何讓多個 process 共享有限的物理記憶體。

## 大綱

- [CPU 排程基礎](#cpu-排程基礎)
  - Life Cycle 與 CPU/I/O Burst
  - 排程準則（Scheduling Criteria）
- [排程演算法](#排程演算法)
  - FCFS
  - SJF / SRTF
  - Round Robin（RR）
  - Priority Scheduling
  - Multilevel Queue
  - Multilevel Feedback Queue
- [Real-Time 排程](#real-time-排程)
  - EDF / LSF / Rate Monotonic
- [記憶體定址](#記憶體定址)
  - Logical vs Physical Address
  - MMU
  - Static/Dynamic Linking & Loading
- [記憶體管理](#記憶體管理)
  - Swapping
  - Multiple Fixed/Variable Partitions
  - Allocation Algorithms
- [Paging（分頁）](#paging分頁)
  - Page Table
  - TLB
  - Large Address Space

---

## CPU 排程基礎

### Life Cycle 與 CPU/I/O Burst

- Thread/Process 的執行是 **CPU burst** 和 **I/O burst** 的交替循環：
  - **CPU burst**：正在計算，佔用 CPU
  - **I/O burst**：等待 I/O 完成，CPU 閒置
- → 排程器在某個 thread 進入 I/O 等待時，可以趁機讓另一個 thread 用 CPU，提升整體 throughput

**排程器介入的時機：**
1. Running → Waiting（非 preemptive，system call 主動讓出）
2. Running → Ready（preempted，時間到被強制切換）
3. Waiting → Ready（I/O 完成，可能搶佔當前執行中的 thread）
4. Terminates

**Dispatcher（調度器）**：實際執行上下文切換的模組
- 工作：切換 context、切回 user mode、跳到正確的程式位址
- **Dispatch latency**：停掉一個 thread 並啟動另一個所花的時間

### 排程準則（Scheduling Criteria）

| 指標 | 定義 |
|------|------|
| **CPU Utilization** | CPU 忙碌的時間百分比（越高越好） |
| **Throughput** | 單位時間完成的 thread 數量 |
| **Turnaround Time** | 從提交到完成的總時間 |
| **Waiting Time** | 在 ready queue 等待的總時間 |
| **Response Time** | 從請求送出到第一個回應的時間（time-sharing 特別重要） |
| **Time Quantum（Time Slice）** | thread 被強制切換前可執行的最大時間 |

---

## 排程演算法

### FCFS（First-Come, First-Served）

- 按到達順序執行，非 preemptive
- **問題：Convoy Effect（護送效應）**
  - 一個長 CPU burst 的 process 會讓後面所有短 process 等很久
  - 範例：P1(24), P2(3), P3(3) 照順序 → 平均等待時間 = 17；換成 P2, P3, P1 → 平均等待時間 = 3

### SJF / SRTF

**Shortest-Job-First（SJF）**：
- 選擇下一次 CPU burst 最短的 process 先執行
- **最佳化**：在給定 process 集合下，SJF 的平均等待時間是最小的
- **非 preemptive**：一旦開始就跑到完

**Shortest Remaining Time First（SRTF）**：
- SJF 的 preemptive 版本
- 新 process 到達時，若剩餘時間比當前執行中的更短，立刻搶佔
- → 平均等待時間更短，但 overhead 更大

**困難點**：如何知道下一次 CPU burst 的長度？
- 使用加權指數平均（weighted exponential average）估算：
  $\tau_{n+1} = \alpha \cdot t_n + (1-\alpha) \cdot \tau_n$
  - $t_n$：最近一次的實際 burst 長度
  - $\alpha$：調整近期 vs 歷史的權重

### Round Robin（RR）

- 每個 thread 輪流得到一段固定時間 **time quantum q**（通常 10–100ms）
- 超時未完成 → preempt，放到 ready queue 末端
- n 個 thread、quantum q → 每個 thread 最多等 $(n-1) \cdot q$ 時間

**q 的選擇影響：**
- **q 太大** → 退化成 FCFS
- **q 太小** → context switch overhead 過高（q 應遠大於 context switch 時間）

### Priority Scheduling

- 每個 thread 有一個優先數字，CPU 給優先序最高的 thread
- 可以是 preemptive 或 non-preemptive
- SJF 是一種特殊的 priority scheduling（優先序 = 預測 burst 長度的倒數）
- **問題：Starvation（餓死）**：低優先序 thread 永遠等不到
- **解法：Aging**：隨時間增加等待中 thread 的優先序

### Multilevel Queue

- Ready queue 分成多個獨立的 queue，各有自己的排程演算法：
  - **Foreground（互動式）** → RR（響應快）
  - **Background（批次）** → FCFS（吞吐量優先）
- Queue 之間的排程：
  - **固定優先序**：foreground 全部跑完才輪到 background → 可能 starvation
  - **Time slice**：各 queue 各分配一定 CPU 時間比例（例：foreground 80%, background 20%）

### Multilevel Feedback Queue

- 進階版：**process 可在 queue 之間移動**（動態調整）
- 典型三層範例：
  - Q0：RR，quantum = 8ms
  - Q1：RR，quantum = 16ms
  - Q2：FCFS
- 規則：
  - 新 process 進 Q0；8ms 跑不完 → 降到 Q1
  - Q1 給 16ms；還跑不完 → 降到 Q2（跑到結束）
- **優點**：CPU-bound 的長工作自動被降到低優先 queue，短的互動式工作保持在高優先 queue → 自動 aging

---

## Real-Time 排程

### 基本概念

- **Hard deadline**：錯過 deadline 完全沒有價值（例：安全控制系統）
- **Soft deadline**：錯過 deadline 價值遞減（例：影音串流）
- RT process 的特性：`C ≤ D ≤ T`
  - C = compute time；D = deadline；T = period

### EDF（Earliest Deadline First）

- 動態優先序：**deadline 最近的 process 優先執行**
- 優點：最大化 CPU 利用率（對周期性可 preempt 任務是 universal 的）
- 缺點：超載時有 Domino Effect

### LSF（Least Slack First）

- **Slack = 距 deadline 的剩餘時間 - 剩餘計算時間**
- Slack 最小的 process 優先
- 比 EDF 更「公平」：
  - EDF 超載 → 只有少數早 deadline 的完成
  - LSF 超載 → 所有任務 deadline 差不多同時 miss（更均勻的降解）

### Rate Monotonic Scheduling

- **固定優先序**：週期越短的 task 優先序越高
- 對所有固定優先序演算法是**最佳的**（optimal）
  - → 如果任何固定優先序演算法能排得進去，RMS 也能
- 必要條件：所有周期性任務事先已知且同時在跑

---

## 記憶體定址

### Logical vs Physical Address

- **Logical address（邏輯/虛擬位址）**：CPU 產生的位址（程式看到的）
- **Physical address（實體位址）**：記憶體模組實際看到的位址

**位址綁定（Address Binding）發生時機：**
| 時機 | 說明 |
|------|------|
| **Compile time** | 直接產生絕對位址（程式必須載到固定位置） |
| **Load time** | 產生可重定位（relocatable）的程式碼，載入時決定位址 |
| **Execution time** | 執行期才綁定，程式可以在記憶體中移動 → 需要 MMU 硬體支援 |

### MMU（Memory Management Unit）

- **Base register**：加到每個邏輯位址 → 得到實體位址
- **Limit register**：確保邏輯位址合法（不超界）
- 公式：`physical = logical + base_register`（且 `logical < limit`）

→ 程式只看到邏輯位址，永遠不知道自己在哪個實體位址

### Static & Dynamic Linking

| 方式 | 說明 |
|------|------|
| **Static Linking** | 所有 library 程式碼在 link time 合併進 executable；執行時不需外部 library |
| **Dynamic Linking** | 某些 library 到執行時才載入；多個 process 共享同一份 library 程式碼 |
| **Dynamic Loading** | 子程式到被呼叫時才載入；節省記憶體空間 |

**Shared Library（共享函式庫）：**
- 同一份程式碼可被多個 process 參照（節省記憶體）
- 需用 **Position Independent Code（PIC）**，使用相對位址
- OS 追蹤 reference count；最後一個 process 結束後才 unload

---

## 記憶體管理

### Single Partition

- 最簡單：同時只有一個程式在記憶體中（與 OS 共用）
- MSDOS 採用此方式
- 問題：資源利用率極低

### Swapping

- 暫時把某個 process 的記憶體搬到 **backing store**（快速磁碟）
- 需要空間時，把低優先序的 process swap out，讓高優先序的 swap in
- **Swap 的主要時間開銷**：資料傳輸時間（正比於被 swap 的記憶體大小）

### Multiple Fixed Partitions

- 把記憶體切成大小固定的分區（不一定等大）
- 每個 process 占用整個分區
- 問題：
  - **Internal fragmentation**：分區內未使用的空間浪費
  - **External fragmentation**：空的分區因為太小而無法使用

### Multiple Variable Partitions（MVP）

- 記憶體動態分割，有空洞（Holes）散佈其中
- 新 process 到達時，找夠大的洞分配

**Allocation Algorithms：**
| 策略 | 說明 | 優缺點 |
|------|------|--------|
| **First-fit** | 找第一個夠大的洞 | 速度快 |
| **Best-fit** | 找最剛好夠大的洞 | 最小化剩餘空洞，但剩餘洞可能太小而無用 |
| **Worst-fit** | 找最大的洞 | 剩餘洞最大，但搜尋慢 |

→ 一般而言 first-fit 和 best-fit 效果優於 worst-fit

---

## Paging（分頁）

### 基本概念

**傳統連續配置的問題**：外部碎裂（external fragmentation）
**分頁的解法**：允許 process 的 logical address space 不連續

- **實體記憶體** → 切成固定大小的 **frames**（通常是 2 的次方，512B~8KB）
- **邏輯記憶體** → 也切成同樣大小的 **pages**
- **Page table**：把每個 page 對應到一個 frame

**好處：**
- 完全消除 external fragmentation
- 可能有少量 internal fragmentation（最後一個 page 不一定填滿）

### Page Table 運作

- Logical address 拆成：`[page number | page offset]`
- `page number` → 查 page table → 得到 frame number
- `physical address = frame number × frame size + page offset`
- Page table 存在主記憶體中，PTBR（Page Table Base Register）指向它

**問題：每次記憶體存取都需要兩次記憶體存取（一次查 page table，一次取資料）**

### TLB（Translation Look-aside Buffer）

- 硬體快取（associative memory），儲存最近用過的 page → frame 對應
- 查表流程：
  1. 先查 TLB → 若 hit：直接得到 frame（快）
  2. 若 miss：查主記憶體的 page table，並更新 TLB
- 有些 TLB 儲存 **ASID（Address Space ID）**，讓不同 process 的 TLB entry 共存，不需 flush

**Effective Access Time（EAT）：**
- 設 TLB hit ratio = $\alpha$，存取時間 = $m$
- $EAT = \alpha \cdot (t_{TLB} + m) + (1-\alpha) \cdot (t_{TLB} + 2m)$

### 大型 Address Space 的解法

32-bit 系統、4KB page → page table 有 $2^{20}$ 個 entries（超大）

**三種解法：**

| 方法 | 說明 |
|------|------|
| **Hierarchical Paging（多級分頁）** | 把 page number 再分層，只配置用到的部份（二層 page table） |
| **Hashed Page Tables** | 用 hash function 找 page，適合 > 32-bit 的 address space |
| **Inverted Page Tables** | 每個 frame 一個 entry（而非每個 page）；節省記憶體，但查表慢 → 搭配 hash table 加速 |

**Two-Level Paging 範例（32-bit, 4KB page）：**
- Logical address = `[outer page (12 bits) | inner page (10 bits) | offset (10 bits)]`
- → 只有被使用的 outer page 才需要配置 inner page table
