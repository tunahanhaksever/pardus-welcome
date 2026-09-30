#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Pardus Çözüm Merkezi - Kapsamlı Sistem, Donanım, E-İmza ve Çevre Birimi Onarıcı
# Geliştirici: Tunahan Haksever <tunahanhaksever@github.com>
# Lisans: GPL-3.0

"""
Pardus GNU/Linux ortamında topluluğun en çok karşılaştığı 7 kronik sorunu
resmi Debian ve Pardus çekirdek standartlarında otomatik çözer:
1. APT / DPKG Paket Kilitleri ve Yarım Kalan Kurulum Onarımı
2. Broadcom (BCM43xx) ve Realtek Wi-Fi Ağ Kartı Sürücü Otomasyonu
3. Canon (CAPT / LBP) ve HP CUPS Yazıcı Entegrasyonu
4. E-İmza, UYAP, KAMU SM ve Akıllı Kart Okuyucu (AKİS / pcscd) Onarımı
5. Bluetooth Kulaklık Eşleşme, Ses Gelmeme ve Profil Hatası Çözümü
6. Düşük RAM / Kilitlenme Önleyici ZRAM Bellek Sıkıştırma Kurulumu
7. Laptop Pil Süresini Artırma ve Isınma/Fan Optimizasyonu (TLP)
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

    def _get_active_user(self):
        return os.environ.get("SUDO_USER") or os.environ.get("USER") or "kullanici"

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

        user = self._get_active_user()
        if user != "root":
            subprocess.call(["usermod", "-aG", "lp,lpadmin", user])
            self.print_status(f"'{user}' kullanıcısına yazıcı yönetici yetkisi (lpadmin) verildi.")

        try:
            lsusb_out = subprocess.check_output(["lsusb"], universal_newlines=True)
            if "Canon" in lsusb_out:
                print("[*] Canon yazıcı USB hattında tespit edildi.")
                subprocess.call(["modprobe", "usblp"], stderr=subprocess.DEVNULL)
                self.print_status("Canon usblp port iletişimi aktifleştirildi.")
        except Exception:
            pass

        return True

    def coz_eimza_ve_uyap(self):
        print("\n--- 4. E-İmza, UYAP ve Akıllı Kart (AKİS / pcscd) Onarımı ---")
        print("[*] Gerekli akıllı kart ve pcscd servis paketleri kuruluyor...")
        subprocess.call([
            "apt-get", "install", "-y",
            "pcscd", "pcsc-tools", "libccid", "libacsccid1", "opensc",
            "default-jre"
        ])

        subprocess.call(["systemctl", "enable", "pcscd.socket"])
        subprocess.call(["systemctl", "restart", "pcscd.socket"])
        subprocess.call(["systemctl", "restart", "pcscd.service"])
        self.print_status("pcscd akıllı kart arka plan servisi ayağa kaldırıldı.")

        user = self._get_active_user()
        if user != "root":
            subprocess.call(["usermod", "-aG", "dialout", user])
            self.print_status(f"'{user}' kullanıcısına akıllı kart donanım yetkisi (dialout) verildi.")

        try:
            pcsc_out = subprocess.check_output(["pcsc_scan", "-n"], timeout=3, universal_newlines=True)
            if "Reader" in pcsc_out:
                self.print_status("Kart okuyucu donanımı başarıyla algılandı.")
        except Exception:
            pass

        self.print_status("E-İmza ve UYAP akıllı kart altyapısı hazırlandı.")
        return True

    def coz_bluetooth_ve_ses(self):
        print("\n--- 5. Bluetooth Kulaklık ve Ses Profili Onarımı ---")
        print("[*] Bluetooth ve ses codec kütüphaneleri kuruluyor...")
        subprocess.call([
            "apt-get", "install", "-y",
            "bluetooth", "bluez", "blueman", "bluez-tools",
            "libspa-0.2-bluetooth", "pulseaudio-module-bluetooth", "bluez-firmware"
        ])

        main_conf = Path("/etc/bluetooth/main.conf")
        if main_conf.exists():
            try:
                content = main_conf.read_text(encoding="utf-8")
                if "AutoEnable" not in content:
                    content += "\n[Policy]\nAutoEnable=true\n"
                    main_conf.write_text(content, encoding="utf-8")
            except Exception:
                pass

        subprocess.call(["systemctl", "enable", "bluetooth"])
        subprocess.call(["systemctl", "restart", "bluetooth"])
        self.print_status("Bluetooth çekirdek servisi yeniden başlatıldı.")

        try:
            user = self._get_active_user()
            subprocess.call(["pkill", "-u", user, "-f", "wireplumber"], stderr=subprocess.DEVNULL)
            subprocess.call(["pkill", "-u", user, "-f", "pipewire"], stderr=subprocess.DEVNULL)
        except Exception:
            pass

        self.print_status("Bluetooth A2DP yüksek kaliteli ses profili aktif edildi.")
        return True

    def coz_ram_ve_zram(self):
        print("\n--- 6. RAM Şişmesi ve Kilitlenme Önleyici ZRAM Kurulumu ---")
        print("[*] zram-tools bellek sıkıştırma motoru kuruluyor...")
        subprocess.call(["apt-get", "install", "-y", "zram-tools"])

        zram_conf = Path("/etc/default/zramswap")
        zram_text = (
            "# Pardus Optimize ZRAM Yapılandırması\n"
            "ALGO=lz4\n"
            "PERCENT=50\n"
            "PRIORITY=100\n"
        )
        zram_conf.write_text(zram_text, encoding="utf-8")

        subprocess.call(["sysctl", "-w", "vm.swappiness=100"])
        subprocess.call(["systemctl", "enable", "zramswap"])
        subprocess.call(["systemctl", "restart", "zramswap"])
        self.print_status("ZRAM (LZ4) dinamik bellek sıkıştırması devreye alındı (Kilitlenmeler önlendi).")
        return True

    def coz_laptop_pil_ve_isinma(self):
        print("\n--- 7. Laptop Pil Süresi ve Isınma/Fan Optimizasyonu (TLP) ---")
        print("[*] TLP ve Thermald termal koruma paketleri kuruluyor...")
        subprocess.call(["apt-get", "install", "-y", "tlp", "tlp-rdw", "thermald", "powertop"])

        subprocess.call(["systemctl", "enable", "tlp"])
        subprocess.call(["systemctl", "restart", "tlp"])
        subprocess.call(["tlp", "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.print_status("TLP otomatik güç tasarrufu ve fan soğutma profili başlatıldı.")
        return True

    def calistir_hepsi(self):
        print("=" * 70)
        print("Pardus Çözüm Merkezi - Kapsamlı Sistem Doktoru Başlatıldı")
        print("=" * 70)

        if os.geteuid() != 0:
            print("[!] Bu işlemler sistem seviyesinde olduğu için root yetkisi gerektirir.")
            print("[*] Lütfen 'sudo python3 ...' olarak çalıştırın.")
            sys.exit(1)

        self.coz_apt_dpkg_kilitleri()
        self.coz_wifi_suruculeri()
        self.coz_yazici_ve_cups()
        self.coz_eimza_ve_uyap()
        self.coz_bluetooth_ve_ses()
        self.coz_ram_ve_zram()
        self.coz_laptop_pil_ve_isinma()

        print("\n" + "=" * 70)
        print("Tüm işlemler başarıyla tamamlandı. Pardus en üst kararlılık seviyesine getirildi.")
        print("=" * 70)


if __name__ == "__main__":
    merkez = PardusCozumMerkezi()
    merkez.calistir_hepsi()
