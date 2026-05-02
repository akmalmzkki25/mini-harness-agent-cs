# PRD for Presentation Deck

## 1. Purpose of This Document

Dokumen ini adalah blueprint untuk membuat PPT tentang project `Qlip CS WhatsApp Agent`. Walaupun nama file ini `PRD.md`, isi dokumen ini difokuskan sebagai panduan presentasi slide-by-slide agar deck yang dibuat:

- akurat terhadap implementasi repo saat ini
- lengkap secara teknis
- tetap mudah dipahami oleh stakeholder
- tidak mengklaim fitur yang belum ada

Dokumen ini diasumsikan dipakai untuk membuat presentasi yang menjelaskan:

- masalah bisnis yang ingin diselesaikan
- solusi arsitektur yang dibangun
- cara kerja agent
- flow handoff ke CS manusia
- simulasi testing via web
- gap teknis dan next steps

---

## 2. Target Audience

Deck ini paling cocok untuk kombinasi audience berikut:

- engineering team
- product manager
- founder atau business stakeholder
- operations / CS lead

Jika audience dominan non-teknis, slide appendix teknis bisa dipindah ke belakang atau dijadikan backup slides.

---

## 3. Presentation Objective

Setelah melihat deck ini, audience harus memahami:

1. masalah apa yang diselesaikan oleh sistem
2. bagaimana agent menerima dan memproses chat
3. kapan agent bisa menjawab sendiri dan kapan harus handoff
4. bagaimana session, history, memory, dan retrieval diatur
5. bagaimana sistem bisa didemokan sekarang lewat website simulator
6. apa gap current-state yang masih harus dibenahi

---

## 4. Narrative Arc

Urutan cerita yang disarankan:

1. mulai dari problem bisnis
2. tunjukkan solusi produk secara sederhana
3. masuk ke arsitektur teknis
4. jelaskan data flow dan state flow
5. tunjukkan mode demo website
6. tutup dengan risk, limitation, dan roadmap

Jangan mulai presentasi dengan tabel env atau detail library. Bawa audience dari konteks ke mekanisme, baru ke detail teknis.

---

## 5. Slide-by-Slide Deck Plan

## Slide A - Title and Executive Summary

**Tujuan**

Membuka presentasi dengan positioning yang jelas: ini adalah agent customer service untuk Mahva Clinic yang mendukung WhatsApp dan mode web simulator untuk testing.

**Judul yang Disarankan**

`Qlip CS WhatsApp Agent for Mahva Clinic`

**Isi Wajib**

- nama project
- satu kalimat value proposition
- satu kalimat status current-state, misalnya: internal working prototype dengan end-to-end flow aktif

**Kalimat Value Proposition yang Bisa Dipakai**

`Sistem ini membantu mengotomasi percakapan customer service, menjawab pertanyaan berbasis knowledge base, dan melakukan handoff ke CS manusia saat kasus membutuhkan penanganan manual.`

**Visual yang Disarankan**

- hero title
- satu diagram sederhana atau screenshot simulator web

**Yang Harus Disiapkan**

- screenshot `http://localhost:8000/test-chat`

**Speaker Notes**

Jelaskan bahwa project ini bukan sekadar chatbot generik. Sistem ini sudah punya knowledge retrieval, session persistence, handoff timeout handling, dan mode testing tanpa Meta.

---

## Slide B - Problem Statement

**Tujuan**

Menjelaskan mengapa solusi ini dibutuhkan.

**Isi Wajib**

- volume atau kompleksitas pertanyaan customer service
- adanya pertanyaan berulang seputar FAQ dan produk
- kebutuhan eskalasi manusia untuk kasus sensitif
- kebutuhan testing cepat tanpa menunggu setup Meta WhatsApp

**Jangan Klaim Jika Belum Ada Datanya**

- jangan isi angka volume chat jika belum diukur
- jika belum ada KPI, tulis sebagai problem statement kualitatif

**Visual yang Disarankan**

- 3 sampai 4 pain points dalam bentuk cards
- optional: alur manual lama vs alur dengan agent

**Speaker Notes**

Fokus pada tiga masalah:

- pertanyaan repetitif
- kebutuhan handoff yang terkontrol
- sulitnya testing integrasi tanpa webhook real

---

## Slide C - Solution Overview

**Tujuan**

Memberi gambaran high-level tentang solusi sebelum masuk detail teknis.

**Isi Wajib**

- agent menerima chat
- agent mencari knowledge dari FAQ dan data produk
- agent memutuskan `reply` atau `handoff`
- jika handoff tidak direspons, scheduler mengaktifkan fallback
- sistem bisa jalan di dua mode: webhook dan website simulator

**Visual yang Disarankan**

- diagram 5 blok:
  - inbound channel
  - agent
  - knowledge retrieval
  - persistence + memory
  - response channel

**Speaker Notes**

Jangan terlalu teknis dulu. Tujuan slide ini hanya membuat audience tahu bahwa solusi sudah punya channel, memory, knowledge base, dan operational fallback.

---

## Slide D - Runtime Modes

**Tujuan**

Menjelaskan bahwa project ini punya dua mode operasi berbeda.

**Isi Wajib**

- `WhatsApp webhook mode`
- `Website simulator mode`
- kapan masing-masing dipakai

**Pesan Penting**

- mode webhook untuk integrasi real
- mode website untuk testing lokal tanpa Meta
- logic service utamanya tetap sama

**Visual yang Disarankan**

- tabel perbandingan dua mode

**Isi Tabel yang Disarankan**

| Aspek | Webhook Mode | Website Mode |
|---|---|---|
| Entry channel | Meta WhatsApp webhook | HTML simulator |
| Outbound | WhatsApp Cloud API | JSON + transcript UI |
| Auth | Verify token + API token | Dummy token |
| Use case | production/integration | local testing/demo |
| Fallback timeout | kirim ke WhatsApp | tampil di UI website |

**Speaker Notes**

Slide ini sangat penting karena menjelaskan kenapa tim bisa testing end-to-end walaupun Meta setup belum selesai.

---

## Slide E - High-Level Architecture

**Tujuan**

Menjelaskan komponen sistem dan hubungan antar komponen.

**Isi Wajib**

- FastAPI app
- routers
- services
- Postgres
- Redis
- Typesense
- Gemini
- WhatsApp adapter

**Visual yang Disarankan**

- arsitektur blok horizontal atau layered diagram

**Komponen yang Harus Muncul**

- `CustomerServiceAgent`
- `ConversationService`
- `MemoryService`
- `AgentSchedulerService`
- `WhatsAppService`
- `FaqObatSearchTool`
- `DataProdukSearchTool`

**Speaker Notes**

Tekankan bahwa desainnya dipisah jelas:

- router sebagai entrypoint
- service sebagai orchestration
- module/tool sebagai adapter ke dependency external

---

## Slide F - End-to-End Message Flow

**Tujuan**

Menjelaskan apa yang terjadi saat satu pesan user masuk.

**Isi Wajib**

Urutan flow:

1. pesan masuk
2. conversation dicari/dibuat
3. message disimpan ke Postgres
4. memory raw disimpan ke Redis
5. retrieval FAQ + produk dilakukan
6. Gemini memutuskan action
7. assistant message disimpan
8. response dikirim ke channel

**Visual yang Disarankan**

- sequence diagram sederhana

**Poin Teknis yang Harus Disebut**

- FAQ dan product retrieval berjalan paralel
- decision output berbentuk JSON terstruktur
- event agent juga disimpan untuk audit

**Speaker Notes**

Ini slide jembatan antara product view dan technical view. Buat runtut dan gampang dicerna.

---

## Slide G - Session, History, and Memory Model

**Tujuan**

Menjelaskan perbedaan peran Postgres dan Redis.

**Isi Wajib**

- Postgres menyimpan transcript persisten dan state session
- Redis menyimpan working memory dan summary
- agent membaca context aktif dari Redis
- UI website membaca transcript dari Postgres

**Visual yang Disarankan**

- diagram dua kolom:
  - `Postgres = system of record`
  - `Redis = agent working memory`

**Poin Teknis yang Wajib Jujur**

- jika Redis hilang, agent tidak me-rehydrate context dari Postgres
- field `conversations.summary` ada di schema tetapi belum dipakai

**Speaker Notes**

Slide ini biasanya jadi momen paling penting untuk audience teknis. Jelaskan bahwa persistence dan memory memang sengaja dipisah, tetapi implementasi saat ini belum punya recovery path dari Postgres ke Redis.

---

## Slide H - Knowledge Base and Retrieval

**Tujuan**

Menjelaskan dari mana agent mendapatkan knowledge faktual.

**Isi Wajib**

- sumber knowledge ada di dua file JSON
- `67` FAQ item
- `7` product item
- data di-index ke Typesense
- query user di-embed dengan Gemini embeddings
- pencarian dilakukan dengan hybrid search

**Visual yang Disarankan**

- flow kecil: JSON -> embeddings -> Typesense -> top hits -> prompt

**Detail yang Harus Disebut**

- FAQ fields: `pertanyaan`, `jawaban`
- Product fields: `nama_produk`, `function`, `description`, `caution_side_effect`, `aturan_pakai`, `objective`, `pricing`

**Speaker Notes**

Tegaskan bahwa agent tidak menjawab dari nol. Agent menjawab dengan membawa context knowledge retrieval ke prompt.

---

## Slide I - Agent Decision Logic and Business Rules

**Tujuan**

Menjelaskan bagaimana agent memutuskan kapan menjawab dan kapan handoff.

**Isi Wajib**

- output model: `reply`, `handoff`, `escalate`, `close`
- implementasi praktis saat ini: `reply`, `handoff`, `escalate` aktif; `close` belum di-handle
- prompt policy utama
- daftar kondisi wajib handoff

**Kondisi Handoff yang Harus Ditampilkan**

- refund/pembatalan setelah bayar
- komplain keras atau isu legal
- verifikasi bukti pembayaran
- konsultasi offline
- reschedule kompleks atau dokter tidak tersedia
- pengiriman obat bermasalah
- pertanyaan medis personal

**Visual yang Disarankan**

- decision tree sederhana

**Speaker Notes**

Jangan framing seolah model bebas memutuskan apapun. Tekankan bahwa prompt memberi operational constraints yang jelas.

---

## Slide J - Handoff Lifecycle and Timeout Recovery

**Tujuan**

Menjelaskan life cycle saat agent melempar ke manusia dan apa yang terjadi jika CS tidak merespons.

**Isi Wajib**

- state `handoff_pending`
- state `human_handoff`
- timeout `300` detik atau 5 menit
- scheduler polling tiap `45` detik
- fallback mengembalikan conversation ke `active`

**Visual yang Disarankan**

- state diagram

**Poin Teknis Penting**

- scheduler memproses `handoff_pending` dan `human_handoff`
- fallback di website mode hanya ditampilkan di UI
- fallback di webhook mode dikirim ke WhatsApp API

**Speaker Notes**

Slide ini menunjukkan bahwa sistem bukan hanya bisa handoff, tapi juga bisa recover jika handoff macet.

---

## Slide K - Website Simulator Demo

**Tujuan**

Menjelaskan alat demo/testing yang sekarang sudah tersedia.

**Isi Wajib**

- route `/test-chat`
- dummy `wa_id`
- dummy auth token
- transcript UI
- badge `fallback timeout`

**Visual yang Disarankan**

- screenshot penuh halaman simulator
- screenshot contoh chat yang memicu handoff
- screenshot fallback timeout badge

**Yang Harus Disiapkan**

- screenshot landing UI
- screenshot satu skenario `reply`
- screenshot satu skenario `handoff`
- screenshot fallback setelah timeout

**Speaker Notes**

Tekankan bahwa mode ini mempercepat development dan demo, karena tim bisa validasi service logic tanpa menunggu konektivitas Meta.

---

## Slide L - API Surface and Operational Setup

**Tujuan**

Memberikan gambaran cepat tentang endpoint dan dependency yang harus ada.

**Isi Wajib**

- endpoint `/health`
- endpoint webhook
- endpoint website simulator
- dependency infra: Postgres, Redis, Typesense, Gemini API key

**Visual yang Disarankan**

- tabel endpoint ringkas
- atau checklist setup

**Poin Jujur yang Harus Disebut**

- `docker-compose.yml` saat ini hanya menjalankan app
- Postgres, Redis, dan Typesense belum dimasukkan ke compose

**Speaker Notes**

Ini berguna untuk audience teknis yang ingin tahu bagaimana menjalankan sistem secara lokal.

---

## Slide M - Current Limitations and Technical Debt

**Tujuan**

Menjelaskan gap nyata tanpa menurunkan kepercayaan stakeholder.

**Isi Wajib**

- `stage` belum dipersist ke conversation
- `summary` column di Postgres belum dipakai
- Redis belum bisa di-rehydrate dari Postgres
- belum ada automated tests
- migration folder belum dipakai
- belum ada webhook signature verification
- `jinja2` belum eksplisit di requirements

**Visual yang Disarankan**

- 2 kolom: `current gap` dan `impact`

**Speaker Notes**

Jangan menyembunyikan gap. Presentasikan sebagai daftar engineering next steps yang jelas.

---

## Slide N - Roadmap / Next Steps

**Tujuan**

Menutup presentasi dengan arah pengembangan yang konkret.

**Isi Wajib**

Prioritas yang disarankan:

1. persist `stage`
2. tambahkan migration management
3. tambahkan automated tests
4. tambahkan webhook signature verification
5. tambahkan Redis rehydration dari Postgres
6. lengkapi Docker compose
7. handle `close` action

**Visual yang Disarankan**

- roadmap 3 fase:
  - hardening
  - operational maturity
  - scale-up

**Speaker Notes**

Tutup dengan nada bahwa fondasi sistem sudah ada, dan roadmap sekarang mostly tentang reliability dan production-readiness.

---

## 6. Optional Appendix Slides

Appendix dipakai jika audience teknis ingin lebih detail.

## Slide O - Data Model Appendix

**Isi**

- tabel `contacts`
- tabel `conversations`
- tabel `conversation_messages`
- tabel `agent_events`

**Tujuan**

Memberi referensi cepat untuk engineer atau reviewer.

## Slide P - Environment Variables Appendix

**Isi**

- env penting dan fungsinya
- mode flags
- timeout config

## Slide Q - Sample Logs Appendix

**Isi**

- contoh log scheduler
- contoh log handoff timeout
- contoh log WhatsApp unauthorized jika credential belum valid

## Slide R - Demo Scenarios Appendix

**Isi**

- FAQ answer
- product answer
- payment proof verification -> handoff
- timeout fallback -> back to agent

---

## 7. Asset Checklist Before Making the PPT

Sebelum membuat PPT final, siapkan asset berikut:

1. screenshot `/test-chat` halaman kosong
2. screenshot `/test-chat` dengan transcript aktif
3. screenshot status `Sent. action=handoff...`
4. screenshot fallback timeout badge di UI
5. snippet log scheduler timeout
6. diagram arsitektur yang sudah dirapikan
7. tabel env dan dependency
8. contoh satu FAQ seed dan satu product seed

Jika ingin deck lebih kuat secara bisnis, tambahkan:

9. volume chat aktual
10. estimasi pengurangan beban CS
11. estimasi response time improvement

Namun angka-angka ini **harus** diambil dari data aktual, bukan dari repo.

---

## 8. Demo Script for the Presenter

Script demo yang direkomendasikan:

1. buka slide solusi singkat
2. pindah ke simulator web
3. kirim pertanyaan FAQ umum
4. tunjukkan agent menjawab
5. kirim pertanyaan atau konteks yang memicu handoff
6. tunjukkan status `handoff`
7. jelaskan bahwa jika CS tidak merespons selama 5 menit, scheduler akan fallback
8. refresh transcript dan tunjukkan badge `fallback timeout`
9. kembali ke deck dan tutup dengan roadmap

Durasi ideal demo:

- 3 sampai 5 menit

---

## 9. Claims You Should Avoid in the Presentation

Supaya deck tetap akurat, jangan klaim hal-hal berikut kecuali implementasinya sudah ditambah:

- `stage conversation sudah tersimpan penuh di database`
- `history agent dipulihkan otomatis dari Postgres jika Redis hilang`
- `sistem sudah punya automated test coverage`
- `webhook sudah aman dengan signature verification`
- `deployment lokal sudah sepenuhnya one-command via docker-compose`
- `close lifecycle sudah berjalan end-to-end`

Kalimat yang lebih aman:

- `sudah ada fondasi state, tetapi sebagian persistence stage masih perlu dilengkapi`
- `saat ini memory operasional agent masih bergantung pada Redis`
- `simulator web sudah memungkinkan testing end-to-end sebelum integrasi Meta selesai`

---

## 10. Recommended Deck Length

Panjang deck yang direkomendasikan:

- versi utama: `12-14` slide
- versi singkat executive: `7-8` slide
- versi teknis lengkap: `14-18` slide dengan appendix

Jika hanya boleh satu deck, gunakan:

- Slide A sampai N sebagai main story
- Slide O sampai R sebagai appendix

---

## 11. Final Recommendation

Deck terbaik untuk project ini adalah deck yang tidak hanya menjelaskan chatbot, tetapi menjelaskan:

- bagaimana session dikelola
- bagaimana knowledge dipanggil
- bagaimana human handoff dijaga
- bagaimana tim bisa testing tanpa Meta setup
- apa gap current-state yang masih perlu dikerjakan

Dengan kata lain, deck ini harus memposisikan project sebagai `working technical foundation for CS automation`, bukan sebagai sistem production-complete yang semua operational concern-nya sudah selesai.
