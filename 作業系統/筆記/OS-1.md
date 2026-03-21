# 作業系統 — OS-1
> 來源：`OS-1.pptx` | 產生日期：2026-03-21

## 前言

本章節建立作業系統的基礎認識，從 OS 的歷史演進切入，說明它在電腦系統中扮演的角色：作為硬體與應用程式之間的抽象層，管理 CPU、記憶體、I/O 等資源。核心設計哲學是「機制與策略的分離」，這個原則貫穿整個 OS 設計。章節後半深入 Process 與 Thread 的概念，並介紹並行程式設計中最根本的問題：Race Condition 與 Critical Section 的解決方法。

## 大綱

- [作業系統概觀](#作業系統概觀)
  - OS 歷史演進
  - OS 的定義與功能
- [機制與策略的分離（Mechanism vs Policy）](#機制與策略的分離)
- [Booting 啟動流程](#booting-啟動流程)
- [Kernel Mode vs User Mode](#kernel-mode-vs-user-mode)
  - Mode Switch 與 System Call
  - Timer Interrupt 與 Context Switch
- [I/O 裝置管理](#io-裝置管理)
- [Process（行程）](#process行程)
  - Address Space 結構
  - Process States 與 PCB
- [Thread（執行緒）](#thread執行緒)
  - Thread vs Process
  - Thread 實作方式（Kernel/User/Hybrid）
  - pthreads
- [並行與同步（Concurrency & Synchronization）](#並行與同步)
  - Race Condition
  - Critical Section 解法
  - Spin Lock 與 Priority Inversion
  - Semaphore

---

## 作業系統概觀

### OS 的歷史演進

- **Batch systems（1956）**：一次只跑一個程式，跑完才載入下一個 → 資源使用率很低
- **Multiprogramming（1960）**：同時將多個程式放入記憶體，輪流切換 → 提升 throughput
- **Time-sharing（1961）**：加上 preemption，強制切換 → 讓每個使用者感覺有獨立的（較慢的）虛擬 CPU
- **Portable OS**：不綁定特定硬體，UNIX（1970）是早期代表
- **Microkernel OS**：只提供最基本的硬體互動機制（thread、memory），其他功能如 file system 交給 user-level process 處理 → Mach（1985）、MINIX（1987）

### OS 的定義與功能

**What is an OS?**
- 電腦啟動時第一個執行的程式
- 讓使用者可以執行其他程式的程式
- 提供對硬體資源受控存取的程式：CPU、Memory、I/O 裝置、網路

**OS 的核心職責：**
- 提供抽象層（abstraction），讓程式不需要直接面對硬體細節
- 管理資源存取：
  - CPU → 透過 **Scheduler（排程器）**
  - Memory → 透過 **MMU（Memory Management Unit）**
  - 持久化儲存 → 透過 **File System**
  - 網路 → 透過 **Sockets / IP drivers**
  - 裝置 → 透過 **Device Drivers**

---

## 機制與策略的分離

**Mechanism（機制）**：定義「如何做某件事」的軟體抽象介面
- 例：提供 priority queue 讓排程器使用

**Policy（策略）**：定義機制如何運作的規則
- 例：決定哪個 process 優先執行、能跑多久

**為什麼要分離？**
- → 同一套機制可以套用不同策略，不需要改底層實作
- 類比：開車的方向盤、油門、煞車是「機制」；你決定走哪條路是「策略」
- **一個好的 OS 設計原則：保持機制與策略的獨立性**

---

## Booting 啟動流程

- **Boot loader**：電腦啟動時執行的小程式，負責載入 OS
- 通常拆成多個階段（chain loading）：
  - 第一個 boot loader 載入更複雜的 boot loader → 再載入 OS
- 兩種主流機制：
  - **BIOS**：傳統，從固定記憶體位址讀取 boot sector
  - **UEFI**：現代，更靈活，支援更大磁碟
- Boot loader 把控制權交給 OS 後，OS 開始初始化並載入各種模組（device drivers、file systems）

---

## Kernel Mode vs User Mode

作業系統需要保護自己不被應用程式破壞，因此 CPU 硬體提供兩種執行模式：

| 模式 | 誰在跑 | 可執行指令 |
|------|--------|-----------|
| **Kernel mode**（特權模式） | OS / 微核心 | 所有指令：設定中斷向量、控制 I/O port、設定 timer、操作記憶體映射 |
| **User mode** | 一般應用程式 | 只限非特權指令 |

### Mode Switch 與 System Call

**如何從 User mode 切換到 Kernel mode？**
- 執行 **trap instruction**（軟體中斷）→ 最通用的方式
- 或執行專用的 system call 指令（把 kernel 入口放在 CPU register 而非記憶體，更快）

**System Call 流程：**
1. 設定 system call number
2. 儲存參數
3. 發出 trap（跳到 kernel mode）
4. OS 接手：儲存 registers、執行請求
5. return from exception（回到 user mode）
6. 取回結果

→ System call 介面通常封裝成 library function（如 `read()`, `write()`），程式設計師不需直接操作 trap

### Timer Interrupt 與 Context Switch

**OS 如何奪回 CPU 控制權？**
- 設置 **Programmable Interval Timer**，定期（例：每 10ms）發送硬體中斷
- → 中斷觸發時，控制權轉回 kernel 的 interrupt handler
- → OS 可以決定要繼續跑當前 process 還是切換

**Context Switch（上下文切換）：**
- OS 決定換 process 時，會：
  1. 儲存當前 process 的 context（registers、PC、stack pointer、memory mappings）
  2. 恢復另一個 process 的 context
- 這個存舊、換新的動作就叫 context switch

---

## I/O 裝置管理

### 裝置種類

| 類型 | 例子 | 特性 |
|------|------|------|
| **Character devices** | 鍵盤、滑鼠、音效 | byte stream |
| **Block devices** | 硬碟、Flash | 可定址的 block，適合快取（buffer cache） |
| **Network devices** | Ethernet、Wi-Fi | packet-based |

### 如何與裝置互動

裝置有 **command registers**（設備暫存器）用來傳送指令：
- **Memory-mapped I/O**：把 device registers 映射到記憶體位址，用普通的 load/store 存取
- **判斷裝置就緒的方式：**
  - **Polling**：主動輪詢狀態 → 浪費 CPU，但延遲低
  - **Interrupt**：裝置準備好時發中斷通知 OS → 不需一直查，但有 context switch 開銷

### 資料傳輸方式

- **Programmed I/O（PIO）**：CPU 親自讀寫 device registers 搬資料 → 佔用 CPU
- **Direct Memory Access（DMA）**：讓裝置直接存取 system memory，不需 CPU 介入 → CPU 可去做別的事

---

## Process（行程）

### Program vs Process

- **Program（程式）**：存在磁碟上的靜態程式碼與資料
- **Process（行程）**：程式正在執行中的狀態，有自己的 address space

### Address Space 結構

每個 process 的記憶體映射包含：

| 區段 | 內容 |
|------|------|
| **Text** | 機器碼（編譯後的指令） |
| **Data** | 已初始化的靜態/全域變數 |
| **BSS** | 未初始化的靜態資料 |
| **Heap** | 執行時期動態配置的記憶體（`malloc`/`new`） |
| **Stack** | 函式呼叫的返回位址、local 變數、暫存資料 |

→ Stack 由高位址往下長，Heap 由低位址往上長，中間是空的

### Process States 與 PCB

**三種基本狀態：**
- **Running**：目前正在 CPU 執行
- **Ready**：準備好了，等 OS 分配 CPU
- **Blocked（Waiting）**：在等待某個事件（如 I/O 完成），沒資格搶 CPU

**PCB（Process Control Block）**：OS 用來追蹤每個 process 的資料結構，包含：
- Process ID、parent/child 關係
- Machine state（registers、PC、stack pointer）
- Process state
- Memory map
- Open file descriptors
- Owner（user ID）
- Scheduling parameters

**Scheduler 的角色：**
- 負責在 ready 和 running 之間移動 process
- **Preemptive multitasking**：OS 可以中途打斷正在跑的 process → 現今主流做法
- **Non-preemptive**：讓程式跑到結束或 block 為止

---

## Thread（執行緒）

### Thread vs Process

- **Thread**：process 中負責執行流程的部份
- 一個 process 可以有多個 threads → 稱為 **multithreaded process**
- Thread 的狀態儲存在 **TCB（Thread Control Block）**

**Threads 共享（同一 process 內）：**
- Text、Data、BSS 段（程式碼、全域變數）
- Open file descriptors
- Signals、working directory、user/group ID

**Threads 不共享：**
- Thread ID
- Saved CPU registers、Program Counter、Stack Pointer
- Stack（local 變數）
- Signal mask、Priority

**為什麼用 Thread 而不是 Process？**
- 建立 thread 開銷遠小於 process（不需複製 address space、fd table 等）
- 記憶體共享天然容易，不需 IPC
- 可充分利用多核心 CPU

### Thread 實作方式

| 方式 | 說明 | 特點 |
|------|------|------|
| **Kernel-level threads** | OS 直接管理 | scheduling/synchronization 由 OS 處理；可跑在多核心 |
| **User-level threads** | 在 user space 的 library 管理 | OS 只看到一個 process；切換快，但一個 thread block 全部 block |
| **Hybrid（N:M）** | N 個 user thread 映射到 M 個 kernel thread | 兼顧彈性與效能 |

### pthreads

**POSIX Threads**（IEEE Std 1003.1c-1995）：
- 跨平台的 thread API，Linux、macOS、FreeBSD 均支援
- 關鍵 API：
  - `pthread_create()`：建立 thread
  - `pthread_join()`：等待另一個 thread 結束
  - `pthread_exit()`：終止自身
  - `pthread_cancel()`：終止目標 thread
- 編譯需加 `-pthread`

---

## 並行與同步

### Race Condition（競賽狀況）

- **定義**：多個 threads 同時存取共享資料，且結果取決於執行順序
- **範例**：銀行帳戶餘額 $1,000，提款 $500 與存款 $5,000 同時發生：
  - 可能結果：$5,500（正確）、$500、$6,000（皆不正確）
  - → 問題來自讀寫操作不是原子性的

### Critical Section（臨界區間）

- **定義**：程式中存取共享資源可能引發 race condition 的區段
- **解決方法**：每次只讓一個 thread 進入 CS
  - 進 CS 前：acquire lock
  - 出 CS 後：release lock
  - 若 lock 被佔用：blocking（等待）

**好的 CS 解法必須滿足：**
1. **Mutual Exclusion（互斥）**：同時只有一個 thread 在 CS 內
2. **Progress（進展性）**：CS 外的 thread 不能阻止其他人進入 CS；需在有限時間內決定誰進
3. **Bounded Waiting（有界等待）**：沒有 thread 應該永遠等不到

### Peterson's Algorithm

軟體層面的 CS 解法（假設共享變數的讀寫是原子性的）：

```c
// 共享變數
int turn;
bool flag[2];

// Thread i（j = 1-i）
flag[i] = TRUE;
turn = j;
while (flag[j] && turn == j) { }  // busy waiting
// --- Critical Section ---
flag[i] = FALSE;
// --- Remainder Section ---
```

- `flag[i]`：Thread i 表示想進入 CS 的意願
- `turn`：禮讓對方先進（turn = j 表示「你先」）
- → 滿足 Mutual Exclusion、Progress、Bounded Waiting

### Hardware Solutions

現代 CPU 提供原子指令（不可中斷）：

**TestAndSet：**
```c
bool TestAndSet(bool *target) {
    bool rv = *target;
    *target = TRUE;
    return rv;
}
// 使用：
while (TestAndSet(&lock)) { }  // spin until lock = FALSE
// Critical Section
lock = FALSE;
```

**Swap：**
```c
void Swap(bool *a, bool *b) {
    bool temp = *a; *a = *b; *b = temp;
}
// 使用：
key = TRUE;
while (key == TRUE) Swap(&lock, &key);
// Critical Section
lock = FALSE;
```

### Spin Lock 與 Priority Inversion

**Spin Lock（自旋鎖）**：用 busy waiting 持續等待 lock 釋放
- 優點：低延遲（不需 context switch）
- 缺點：浪費 CPU，且可能引發 **Priority Inversion（優先序反轉）**

**Priority Inversion 問題：**
- 高優先權 thread 在 spinlock 等待 → 佔用 CPU → 低優先權 thread 無法跑 → 無法釋放 lock → 死鎖
- 解法：**Priority Inheritance（優先序繼承）**
  - 進入 CS 的 thread 臨時提升到「所有等待者的最高優先序」
  - 離開 CS 後恢復原本優先序

### Semaphore（號誌）

**Semaphore S**：OS 提供的同步工具，是一個特殊整數變數
- 只能透過兩個原子操作存取：
  - `wait(S)`：S > 0 才繼續，否則 block；進入後 S--
  - `signal(S)`：S++，若有 thread 在等，喚醒一個

**兩種類型：**
- **Binary semaphore（= Mutex lock）**：值只有 0 或 1
- **Counting semaphore**：值可以是任意非負整數（管理多個資源單位）

**Mutex 使用範例：**
```c
Semaphore mutex = 1;
wait(mutex);   // acquire
// Critical Section
signal(mutex); // release
```

**無 Busy Waiting 的實作：**
- 每個 semaphore 附帶一個 waiting queue
- `wait(S)` 若需 block：把 thread 加入 queue，呼叫 `block()`
- `signal(S)` 若有 thread 在等：從 queue 取出一個，呼叫 `wakeup()`
- → 把 busy waiting 移進 OS 核心的 `wait()` 內部，應用層不需 spin
