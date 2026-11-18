# Pertanyaan terbuka untuk klien

Belum terjawab di meeting pertama. Sampai dijawab, pengembangan memakai asumsi di bawah.

| # | Pertanyaan | Asumsi sementara |
|---|---|---|
| 1 | Kapan deadline-nya? Apakah ada tanggal yang harus dikejar (mis. musim tahun ajaran baru)? | Belum ada; rilis bertahap, menu stok dulu. |
| 2 | Berapa batasan anggaran? | Belum diketahui. |
| 3 | Siapa saja stakeholder selain owner? Siapa yang memutuskan dan menyetujui? | Owner (keputusan & approval), admin, kasir. |
| 4 | Setelah selesai, sistem diserahkan ke tim internal atau pakai kontrak maintenance? | Kontrak maintenance. |
| 5 | Seberapa cepat usaha akan tumbuh? Jumlah produk (SKU) dan transaksi per hari saat ini? | 1 toko, < 5.000 SKU, beberapa ratus transaksi/hari, tumbuh pelan. |
| 6 | Apakah sistem harus bisa diakses 24/7? Se-realtime apa laporan yang dibutuhkan? | Online di cloud 24/7; transaksi muncul di dashboard owner dalam ±1 menit. |
| 7 | Apakah Smartlink yang dipakai sekarang adalah "Aplikasi Kasir Smartlink" (aplikasi kasir untuk laundry)? | Ya; Opname360 akan menggantikannya dengan POS sendiri. |
| 8 | Apa bedanya retur tipe A dan retur tipe B? | Tipe A: barang kembali ke stok dan bisa dijual lagi. Tipe B: barang rusak, dihapus dari stok. |
| 9 | Maksud "jam 5 - 10" di laporan laba rugi per jam? | Jam buka toko, 05:00–22:00. |
| 10 | Apakah usaha sudah PKP (memungut PPN)? | Belum; harga tanpa PPN. |
| 11 | Toko berada di zona waktu mana? | WIB. |
| 12 | Apakah ada pembeli (mis. sekolah) yang membeli seragam dalam jumlah besar secara kredit / tempo? | Tidak; semua penjualan dibayar lunas di kasir. |
| 13 | Perangkat apa yang sudah ada di toko (scanner barcode, printer struk, printer label, komputer/tablet kasir)? | Scanner USB/Bluetooth, printer struk thermal 58/80 mm, printer label thermal; dibeli jika belum ada. |
| 14 | Apakah koneksi internet di toko stabil? Ada cadangan (mis. hotspot HP)? | Stabil, dengan hotspot HP sebagai cadangan. POS tidak bisa dipakai tanpa internet. |
| 15 | Berapa hari batas waktu retur? | 7 hari. |
| 16 | Saat tutup shift, apakah semua uang di laci kasir disetor, lalu shift berikutnya mulai dengan modal kas baru? | Ya. |
| 17 | Ganti rugi karyawan dihitung dari harga pokok atau harga jual? | Harga pokok (HPP); owner bisa mengubah nominalnya. |
| 18 | Apakah admin kadang juga melayani penjualan di kasir? | Tidak. Admin tidak bisa menjual; kasir tidak bisa membuka menu admin. |
| 19 | Uang retur dikembalikan tunai atau lewat cara pembayaran semula? | Tunai dari laci; kasir bisa memilih cara lain. |
| 20 | Kapan mau mulai dipakai: setelah stok, opname, kasir dan dashboard owner jadi, atau menunggu laporan keuangan (neraca) juga? | Mulai dipakai setelah dashboard owner jadi; laporan keuangan menyusul dan mencatat mundur sejak hari pertama. |
| 21 | Apakah menjual obat China perlu izin khusus (mis. izin toko obat)? | Di luar sistem; klien yang mengurus. Sistem hanya mencatat batch dan tanggal kedaluwarsa. |
| 22 | Apakah kemasan obat dari pemasok mencantumkan nomor batch dan tanggal kedaluwarsa di barcode-nya? | Tidak; nomor batch dan tanggal kedaluwarsa diketik saat Barang Masuk. |
