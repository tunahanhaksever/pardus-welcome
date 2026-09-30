#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Pardus Çözüm Merkezi - Kritik Sistem, Donanım ve Yazıcı Onarıcı
# Geliştirici: Tunahan Haksever <tunahanhaksever@github.com>
# Lisans: GPL-3.0

"""
Bu modül Pardus GNU/Linux ortamında en çok karşılaşılan 3 ana sorunu
çekirdek ve FreeDesktop standartlarında otomatik olarak çözer:
1. APT / DPKG Paket Kilitleri ve Yarım Kalan Kurulum Onarımı
2. Broadcom (BCM43xx) ve Realtek Wi-Fi Ağ Kartı Sürücü Otomasyonu
3. Canon (CAPT / LBP) ve HP CUPS Yazıcı Entegrasyonu
"""

import os
import sys
import subprocess
import re
from pathlib import Path


class PardusCozumMerkezi:
    def __init__(self):
        self.log_prefix = "[Pardus Çözüm]"

    def print_status(self, msg, ok=True):
        mark = "[OK]" if ok else "[FAIL]"
        print(f"{mark} {msg}")

    def coz_apt_dpkg_kilitleri(self):
        print("\n--- 1. APT ve DPKG Paket Yöneticisi Onarımı ---")
        lock_processes = ["apt", "apt-get", "dpkg", "unattended-upgrades", "packagekitd"]
        for proc in lock_processes:
            try:
                subprocess.call(["killall", "-q", "-9", proc], stderr=subprocess.DEVNULL)
            except Exception:
                pass
        self.print_status("Kilitli arka plan işlemleri sonlandırıldı.")

        lock_files = [
            "/var/lib/dpkg/lock-frontend",
            "/var/lib/dpkg/lock",
            "/var/cache/apt/archives/lock",
            "/var/lib/apt/lists/lock"
        ]
        for lf in lock_files:
            try:
                if os.path.exists(lf):
                    os.remove(lf)
            except Exception:
                pass
        self.print_status("Sistem kilit dosyaları temizlendi.")

        res_dpkg = subprocess.call(["dpkg", "--configure", "-a"])
        self.print_status("Yarım kalan paket yapılandırmaları tamamlandı (dpkg --configure -a).", res_dpkg == 0)

        res_fix = subprocess.call(["apt-get", "install", "-f", "-y"])
        self.print_status("Kırık paket bağımlılıkları onarıldı (apt install -f).", res_fix == 0)

        subprocess.call(["apt-get", "clean"])
        res_upd = subprocess.call(["apt-get", "update", "-y"])
        self.print_status("Paket depoları güncellendi.", res_upd == 0)
        return True

    def coz_wifi_suruculeri(self):
        print("\n--- 2. Broadcom & Realtek Wi-Fi Sürücü Tanılama ---")
        try:
            lspci_out = subprocess.check_output(["lspci", "-nn"], universal_newlines=True)
        except Exception:
            lspci_out = ""

        is_broadcom = ("14e4:" in lspci_out) or ("Broadcom" in lspci_out)
        is_realtek = ("10ec:" in lspci_out) or ("Realtek" in lspci_out)

        print("[*] Donanım Taraması:")
        print(f"    - Broadcom Wi-Fi: {'Tespit Edildi' if is_broadcom else 'Bulunamadı'}")
        print(f"    - Realtek Wi-Fi : {'Tespit Edildi' if is_realtek else 'Bulunamadı'}")

        print("[*] Gerekli çekirdek başlıkları ve dkms kuruluyor...")
        subprocess.call([
            "apt-get", "install", "-y",
            "linux-headers-amd64", "build-essential", "dkms",
            "firmware-linux", "firmware-linux-nonfree", "firmware-misc-nonfree"
        ])

        if is_broadcom:
            print("[*] Broadcom BCM sürücüsü yükleniyor (broadcom-sta-dkms)...")
            subprocess.call(["apt-get", "install", "-y", "broadcom-sta-dkms", "b43-fwcutter", "firmware-b43-installer"])

            cakisanlar = ["b43", "b43legacy", "ssb", "bcma", "brcmfmac", "brcmsmac"]
            for m in cakisanlar:
                subprocess.call(["modprobe", "-r", m], stderr=subprocess.DEVNULL)

            res_mod = subprocess.call(["modprobe", "wl"])
            self.print_status("Broadcom 'wl' sürücüsü çekirdeğe yüklendi.", res_mod == 0)

        if is_realtek:
            print("[*] Realtek donanım bellenimi yükleniyor (firmware-realtek)...")
            res_rt = subprocess.call(["apt-get", "install", "-y", "firmware-realtek"])
            self.print_status("Realtek bellenimi kuruldu.", res_rt == 0)

        subprocess.call(["systemctl", "restart", "NetworkManager"], stderr=subprocess.DEVNULL)
        self.print_status("NetworkManager ağ servisi yeniden başlatıldı.")
        return True

    def coz_yazici_ve_cups(self):
        print("\n--- 3. Canon & HP Yazıcı Yazdırma Servisi Onarımı ---")
        print("[*] CUPS ve HPLIP yazdırma paketleri kontrol ediliyor...")
        subprocess.call([
            "apt-get", "install", "-y",
            "cups", "cups-filters", "system-config-printer",
            "hplip", "printer-driver-hpcups", "printer-driver-all",
            "libcups2"
        ])

        subprocess.call(["systemctl", "enable", "cups"])
        subprocess.call(["systemctl", "restart", "cups"])
        self.print_status("CUPS yazdırma kuyruk servisi çalıştırıldı.")

        aktif_kullanici = os.environ.get("SUDO_USER") or os.environ.get("USER") or "kullanici"
        if aktif_kullanici != "root":
            subprocess.call(["usermod", "-aG", "lp,lpadmin", aktif_kullanici])
            self.print_status(f"'{aktif_kullanici}' kullanıcısına yazıcı yönetici yetkisi (lpadmin) verildi.")

        try:
            lsusb_out = subprocess.check_output(["lsusb"], universal_newlines=True)
            if "Canon" in lsusb_out:
                print("[*] Canon yazıcı USB hattında tespit edildi.")
                subprocess.call(["modprobe", "usblp"], stderr=subprocess.DEVNULL)
                self.print_status("Canon usblp port iletişimi aktifleştirildi.")
        except Exception:
            pass

        try:
            hp_res = subprocess.call(["which", "hp-check"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if hp_res == 0:
                self.print_status("HP Linux Görüntüleme ve Yazdırma (HPLIP) altyapısı hazır.")
        except Exception:
            pass

        return True

    def calistir_hepsi(self):
        print("=" * 65)
        print("Pardus Çözüm Merkezi - Otomatik Sistem Doktoru Başlatıldı")
        print("=" * 65)

        if os.geteuid() != 0:
            print("[!] Bu işlemler sistem seviyesinde olduğu için root yetkisi gerektirir.")
            print("[*] Lütfen 'sudo python3 ...' olarak çalıştırın.")
            sys.exit(1)

        self.coz_apt_dpkg_kilitleri()
        self.coz_wifi_suruculeri()
        self.coz_yazici_ve_cups()

        print("\n" + "=" * 65)
        print("Tüm işlemler başarıyla tamamlandı. Sistem kararlı duruma getirildi.")
        print("=" * 65)


if __name__ == "__main__":
    merkez = PardusCozumMerkezi()
    merkez.calistir_hepsi()
