import sys # Sistem işlemlerini yönetmek için (özellikle uygulamayı başlatma ve kapatma)
import sqlite3 # SQLite veri tabanına bağlanmak ve sorgu çalıştırmak için
import os # İşletim sistemi işlemleri için (örneğin dosya yollarını kontrol etme)
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QComboBox, 
                             QScrollArea, QGridLayout, QRadioButton, QButtonGroup, 
                             QMessageBox, QFrame, QStackedWidget, QLineEdit, QTextBrowser)
#QScrollArea,İçeriğin ekrana sığmadığı durumda yatay ya da dikey kaydırma çubuğu ekler,içeriğin kaymasını sağlar.
#QFrame,Etrafına kenarlık eklenebilen çerçevelerdir.Arayüzdeki belli bölümleri ayırmada kullanılır.
#QStackedWidget,İçine birden fazla sayfa/widget eklenebilen fakat aynı anda sadece birini göstermeyi sağlayan araçtır.

from PyQt5.QtCore import Qt, QTimer # Qt temel özellikleri (hizalama vb.) ve Zamanlayıcı (robot süresi için)
from PyQt5.QtGui import QFont, QPixmap, QPainter # Yazı tipi, görsel işleme ve çizim (arka plan) işlemleri için
#QPixmap,Bilgisayardaki resim ve ikon dosyalarını hafızaya yükleyip ekranda göstermeyi sağlar.

# --- 1. ÖZEL ARKA PLAN SINIFI ---
# Bu sınıf, ürünlerin listelendiği sayfalarda arka plana kategori resmini silik (transparan) olarak eklemek için yazıldı.
class FaintBackgroundWidget(QWidget):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.bg_pixmap = QPixmap(image_path) # Arka plan yapılacak görseli yüklüyoruz
    # paintEvent: Ekrana her çizim yapıldığında otomatik tetiklenen gömülü bir fonksiyondur.    
    def paintEvent(self, event):
        painter = QPainter(self)  # Çizim aracını başlatıyoruz
        painter.fillRect(self.rect(), Qt.white)  # Önce ekranı bembeyaz bir tuvalle dolduruyoruz
        
        if not self.bg_pixmap.isNull(): # Eğer görsel başarıyla yüklendiyse
            painter.setOpacity(0.12)  # Görselin opaklığını %12'ye düşürüyoruz (silik görünmesi için)
            # Görseli en-boy oranını bozmadan ekrana sığacak şekilde yeniden boyutlandırıyoruz
            scaled = self.bg_pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
          #scaled,Görseli pencere boyutuna göre yeniden boyutlandırır.Qt.KeepAspectRatioByExpanding,resmin en boy oranının bozulmadan tam alan kaplamasını sağlar.
              # Resmi tam ekranın ortasına hizalamak için x ve y koordinatlarını hesaplıyoruz
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)

# --- 2. VERİ TABANI YARDIMCI SINIFI ---
# Tüm veri tabanlarından ürünleri okumak için genel bir yardımcı sınıf.
class DatabaseHelper:
    @staticmethod # Sınıftan nesne üretmeden doğrudan DatabaseHelper.get_products() şeklinde çağırabilmek için statik yaptık
    def get_products(db_name, table_name):
        products = [] # Okunan ürünleri tutacağımız boş liste
        try:
            conn = sqlite3.connect(db_name) # İstenilen SQLite veri tabanına bağlanıyoruz
            cursor = conn.cursor() # SQL komutlarını çalıştırmak için imleç (cursor) oluşturuyoruz
            cursor.execute(f'SELECT * FROM "{table_name}"') # Tablodaki TÜM verileri çekiyoruz
             # description özelliği ile sütun isimlerini (Kategori, Fiyat, Süt Tipi vb.) alıp bir listeye çeviriyoruz
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()  # Sorgu sonucundaki tüm satırları alıyoruz
            for row in rows: # Her bir satır (ürün) üzerinde dönüyoruz
                row_dict = {} # Sütun adı : Hücre değeri şeklinde tutmak için boş sözlük
                for i, col in enumerate(columns):
                    val = row[i]# İlgili sütunun verisini alıyoruz
                     # Eğer veri Byte (BLOB) tipindeyse ve görsel değilse (metin bozulmuşsa) UTF-8'e çeviriyoruz
                    if isinstance(val, bytes) and "görsel" not in col.lower() and "gorsel" not in col.lower():
                        try:
                            val = val.decode('utf-8', 'ignore')
                        except:
                            pass
                    row_dict[col] = val # Sözlüğe ekliyoruz (Örn: {'Ürün Adı': 'Latte'})
                products.append(row_dict) # Tamamlanan ürünü ana listeye ekliyoruz
            conn.close()  # Veri tabanı bağlantısını kapatıyoruz (önemli!)
        except Exception as e:
            print(f"Veri tabanı hatası: {e}") # Hata olursa konsola yazdırıyoruz (çökmesini engelliyoruz)
        return products # Tüm ürünlerin listesini geri döndürüyoruz

# --- 3. ANA UYGULAMA SINIFI ---
# Uygulamanın kalbi. Tüm pencereler, sayfalar ve mantık burada çalışır.
class CoffeeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kahve Robotu Otomasyonu") #Pencere başlığı
        self.setGeometry(100, 100, 1100, 800) # Uygulamanın ekranda açılacağı konum (x,y) ve boyutu (genişlik, yükseklik)
        
        self.sepet = [] # Müşterinin eklediği ürünleri tutacak liste
        self.robot_kuyrugu = [] # Onaylanan siparişleri robotun sırasına ekleyeceğimiz liste
        self.current_bg_image = "" # O anki sayfanın arka plan resminin yolunu tutar
        self.current_size_prices = {} # Seçilen butonlara göre fiyatları hafızada tutar
        
        self.init_user_db() # Program açılır açılmaz kullanıcı veri tabanını kontrol et/oluştur
        
        self.current_user = ""    # Sisteme giren kişinin adını tutar   
        self.is_admin = False      # Giren kişi admin mi (yönetici mi) kontrol bayrağı   
        
        self.kalan_saniye = 0 # Robotun siparişi hazırlama süresi sayacı
        self.timer = QTimer() # Geri sayım için PyQt'nin zamanlayıcı nesnesi
        self.timer.timeout.connect(self.update_countdown) # Zamanlayıcı her saniye tık ettiğinde bu fonksiyonu çalıştır
         # Sayfalar arası geçiş yapmak için QStackedWidget kullanıyoruz (Sekme mantığı gibi ama gizli)
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget) # Uygulamanın merkezine bu yığın widget'ını koyuyoruz
        
        # Uygulamadaki tüm farklı ekranları (sayfaları) önceden oluşturuyoruz
        self.login_page = QWidget()    
        self.register_page = QWidget() 
        self.category_page = QWidget()
        self.products_page = QWidget()
        self.robot_page = QWidget() 
        self.change_password_page = QWidget() 
        
          # Oluşturulan sayfaları StackedWidget (yığın) içerisine ekliyoruz
        self.stacked_widget.addWidget(self.login_page)
        self.stacked_widget.addWidget(self.register_page)
        self.stacked_widget.addWidget(self.category_page)
        self.stacked_widget.addWidget(self.products_page)
        self.stacked_widget.addWidget(self.robot_page)
        self.stacked_widget.addWidget(self.change_password_page)
        
        # Sayfaların iç dizaynını (butonlar, yazılar vb.) oluşturan fonksiyonları çağırıyoruz
        self.setup_login_page() 
        self.setup_register_page() 
        self.setup_robot_page()
        self.setup_change_password_page()
        self.stacked_widget.setCurrentWidget(self.login_page)
 
 # Sistemin kullanıcı kayıtları için kendi veritabanını oluşturduğu fonksiyon
    def init_user_db(self):
        try:
            conn = sqlite3.connect("users.db") # users.db adında bir dosya oluşturur veya bağlanır
            cursor = conn.cursor()
            # users adında bir tablo oluşturur. İsim (name) Primary Key'dir (aynı isimden iki tane olamaz)
            # Telefon numarası sütunu eski veritabanlarında kalabilir, sorun yaratmaz.
            # Yeni veritabanları için en sade haliyle tablo oluşturulur.
            cursor.execute('''CREATE TABLE IF NOT EXISTS users
                              (name TEXT PRIMARY KEY, password TEXT, security_word TEXT)''')
            # Eğer eski tablo varsa ve security_word yoksa eklemeye çalış
            try:
                 # Eski veritabanı sürümlerini güncellemek için güvenlik kelimesi sütununu eklemeyi dener
                cursor.execute("ALTER TABLE users ADD COLUMN security_word TEXT")
            except:
                pass # Sütun zaten varsa hata vereceği için try-except ile hatayı yoksayıyoruz
            conn.commit() # Değişiklikleri kaydet
            conn.close() # Bağlantıyı kapat
        except Exception as e:
            print(f"Kullanıcı veri tabanı oluşturulamadı: {e}")

    # --- AKILLI FİYATLANDIRMA MOTORU ---
    # İçeceğin geldiği veritabanına ve seçilen boyut ismine göre dinamik fiyat döndürür
    def get_price(self, db_name, size_str):
        s = size_str.lower() # Büyük/küçük harf duyarlılığını kaldırmak için hepsini küçültüyoruz
        if db_name == "hazır_kahveler.db":
            if "büyük" in s or "large" in s: return 110
            if "orta" in s or "medium" in s: return 95
            if "küçük" in s or "small" in s: return 70
            if "single" in s: return 40
            if "double" in s: return 50
            if "standart" in s: return 80
            return 80  # Eğer tanınmayan bir boyutsa varsayılan olarak 80 döndür
            
        elif db_name == "Caylar.db":# Çayların hacmine (ml) göre fiyatlandırma
            if "600" in s: return 110
            if "470" in s: return 95
            if "400" in s: return 85
            if "350" in s: return 75
            if "250" in s: return 60
            return 75 
            
        elif db_name == "Matcha_ve_Yabancı_Çaylar.db":
            if "büyük" in s or "large" in s: return 110
            if "orta" in s or "medium" in s: return 95
            if "küçük" in s or "small" in s: return 70
            if "standart" in s: return 80
            return 80 
            
        return 0 # Hiçbir şeye uymazsa ücretsiz (0) kalır

    # --- GİRİŞ SAYFASI ---
    def setup_login_page(self):
        if self.login_page.layout(): # Eğer sayfada zaten bir düzen (layout) varsa sıfırlıyoruz
            QWidget().setLayout(self.login_page.layout())
            
        layout = QVBoxLayout(self.login_page) # Sayfadaki elemanları dikey (Yukarıdan aşağı) dizmek için VBoxLayout
        layout.setAlignment(Qt.AlignCenter) # Elemanları sayfanın tam ortasına hizalıyoruz
        layout.setSpacing(15) # Elemanlar arasına 15 piksel boşluk koyuyoruz
        
        title = QLabel("🤖 NEVV COFFEE ROBOT\nGiriş ve Güvenlik Sistemi")
        title.setFont(QFont("Arial", 22, QFont.Bold))
        title.setStyleSheet("color: #3E2723; margin-bottom: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
         # MÜŞTERİ GİRİŞ KARTI (Etrafı çerçeveli alan)
        user_card = QFrame()
        user_card.setStyleSheet("border: 1px solid #BCAAA4; border-radius: 10px; background-color: #F5F5F5; padding: 20px;")
        user_layout = QVBoxLayout(user_card)
        
        # Üst kısımdaki Şifremi Unuttum ve Kayıt Ol butonlarının yan yana (Yatay - HBox) durduğu kısım
        register_bar = QHBoxLayout()
        register_bar.addWidget(QLabel("<b>MÜŞTERİ GİRİŞİ</b>"))
        register_bar.addStretch()  # Araya esnek boşluk atıp butonları sağa yaslıyoruz
        
        btn_go_forgot_pass = QPushButton("🔑 Şifremi Unuttum")
        btn_go_forgot_pass.setFont(QFont("Arial", 10, QFont.Bold))
        btn_go_forgot_pass.setStyleSheet("color: #8D6E63; background: transparent; border: none; text-decoration: underline;")
        btn_go_forgot_pass.setCursor(Qt.PointingHandCursor)# Fare üzerine gelince el işareti çıksın
        # Butona tıklanınca şifre değiştirme sayfasını öne getirir
        btn_go_forgot_pass.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.change_password_page))
        register_bar.addWidget(btn_go_forgot_pass)
        
        btn_go_register = QPushButton("📝 Kayıt Ol")
        btn_go_register.setFont(QFont("Arial", 10, QFont.Bold))
        btn_go_register.setStyleSheet("color: #00796B; background: transparent; border: none; text-decoration: underline;")
        btn_go_register.setCursor(Qt.PointingHandCursor) # Butona tıklanınca kayıt olma sayfasını öne getirir
        btn_go_register.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.register_page))
        register_bar.addWidget(btn_go_register)
        user_layout.addLayout(register_bar) # Bu yatay şeridi dikey düzene ekliyoruz
        
        # Kullanıcı Adı Girdi Kutusu
        self.txt_customer_name = QLineEdit()
        self.txt_customer_name.setPlaceholderText("Adınızı Soyadınızı Giriniz...")
        self.txt_customer_name.setFont(QFont("Arial", 11))
        user_layout.addWidget(self.txt_customer_name)
        
        self.txt_customer_pass = QLineEdit()
        self.txt_customer_pass.setPlaceholderText("Şifrenizi Giriniz...")
        self.txt_customer_pass.setEchoMode(QLineEdit.Password) # Yazılanları nokta (****) şeklinde gizler
        self.txt_customer_pass.setFont(QFont("Arial", 11))
        user_layout.addWidget(self.txt_customer_pass)
        
        btn_customer_login = QPushButton("Giriş Yap")
        btn_customer_login.setStyleSheet("background-color: #5D4037; color: white; padding: 10px; font-weight: bold; border-radius: 5px;")
        btn_customer_login.clicked.connect(self.login_as_customer) # Tıklanınca müşteri giriş doğrulama fonksiyonunu çalıştırır
        user_layout.addWidget(btn_customer_login)
        layout.addWidget(user_card)
        
        # YÖNETİCİ GİRİŞ KARTI
        admin_card = QFrame()
        admin_card.setStyleSheet("border: 1px solid #B0BEC5; border-radius: 10px; background-color: #ECEFF1; padding: 20px;")
        admin_layout = QVBoxLayout(admin_card)
        admin_layout.addWidget(QLabel("<b>YÖNETİCİ / ROBOT GİRİŞİ</b>:"))
        
        self.txt_admin_pass = QLineEdit()
        self.txt_admin_pass.setPlaceholderText("Yönetici Şifresini Giriniz...")
        self.txt_admin_pass.setEchoMode(QLineEdit.Password)
        self.txt_admin_pass.setFont(QFont("Arial", 11))
        admin_layout.addWidget(self.txt_admin_pass)
        
        btn_admin_login = QPushButton("Yönetici Olarak Giriş Yap")
        btn_admin_login.setStyleSheet("background-color: #37474F; color: white; padding: 10px; font-weight: bold; border-radius: 5px;")
        btn_admin_login.clicked.connect(self.login_as_admin) # Tıklanınca admin giriş doğrulama fonksiyonunu çalıştırır
        admin_layout.addWidget(btn_admin_login)
        layout.addWidget(admin_card)

    # --- MÜŞTERİ KAYIT OL SAYFASI ---
     # Bu fonksiyon da yukarıdaki login tasarımıyla aynı mantıkta QLineEdit (Girdi kutuları) ve butonlar oluşturur.
    def setup_register_page(self):
        layout = QVBoxLayout(self.register_page)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(15)
        
        title = QLabel("📝 YENİ MÜŞTERİ KAYIT PANELİ")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setStyleSheet("color: #00796B; margin-bottom: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        register_card = QFrame()
        register_card.setFixedWidth(400)
        register_card.setStyleSheet("border: 1px solid #B2DFDB; border-radius: 10px; background-color: #F5F5F5; padding: 25px;")
        reg_layout = QVBoxLayout(register_card)
        
        # Kullanıcı kayıt verilerini alacağımız TextBox'lar
        self.txt_reg_name = QLineEdit()
        self.txt_reg_name.setPlaceholderText("Adınız Soyadınız...")
        self.txt_reg_name.setFont(QFont("Arial", 11))
        reg_layout.addWidget(QLabel("Ad Soyad:"))
        reg_layout.addWidget(self.txt_reg_name)

        self.txt_reg_sec_word = QLineEdit()
        self.txt_reg_sec_word.setPlaceholderText("Unutmayacağınız bir kelime girin...")
        self.txt_reg_sec_word.setFont(QFont("Arial", 11))
        reg_layout.addWidget(QLabel("Güvenlik Kelimesi:"))
        reg_layout.addWidget(self.txt_reg_sec_word)
        
        self.txt_reg_pass = QLineEdit()
        self.txt_reg_pass.setPlaceholderText("Şifre Belirleyin...")
        self.txt_reg_pass.setEchoMode(QLineEdit.Password)
        self.txt_reg_pass.setFont(QFont("Arial", 11))
        reg_layout.addWidget(QLabel("Şifre:"))
        reg_layout.addWidget(self.txt_reg_pass)
        
        self.txt_reg_pass_confirm = QLineEdit()
        self.txt_reg_pass_confirm.setPlaceholderText("Şifreyi Tekrar Giriniz...")
        self.txt_reg_pass_confirm.setEchoMode(QLineEdit.Password)
        self.txt_reg_pass_confirm.setFont(QFont("Arial", 11))
        reg_layout.addWidget(QLabel("Şifre Tekrar:"))
        reg_layout.addWidget(self.txt_reg_pass_confirm)
        
        btn_register = QPushButton("Kaydol")
        btn_register.setStyleSheet("background-color: #00796B; color: white; padding: 12px; font-weight: bold; border-radius: 5px; margin-top: 10px;")
        btn_register.clicked.connect(self.register_new_customer) # Kaydı tamamlayan fonksiyona bağlarız
        reg_layout.addWidget(btn_register)
        
        btn_back_login = QPushButton("← Giriş Ekranına Dön")
        btn_back_login.setStyleSheet("color: #555; background: transparent; border: none; margin-top: 5px;")
        btn_back_login.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.login_page))
        reg_layout.addWidget(btn_back_login)
        
        layout.addWidget(register_card)

# KULLANICIYI VERİ TABANINA KAYDETME İŞLEMİ
    def register_new_customer(self): # Kutuya yazılan metinleri alıp, baştaki sondaki boşlukları strip() ile siliyoruz
        name = self.txt_reg_name.text().strip()
        sec_word = self.txt_reg_sec_word.text().strip()
        p1 = self.txt_reg_pass.text().strip()
        p2 = self.txt_reg_pass_confirm.text().strip()
        
         # Alanlardan herhangi biri boşsa uyarı ver
        if not name or not sec_word or not p1 or not p2:
            QMessageBox.warning(self, "Eksik Alan", "Lütfen tüm kutuları eksiksiz doldurunuz!")
            return
        if p1 != p2: # Şifreler uyuşmuyorsa uyarı ver
            QMessageBox.critical(self, "Şifre Uyuşmazlığı", "Girdiğiniz şifreler birbiriyle eşleşmiyor!")
            return
            
        try:
            conn = sqlite3.connect("users.db")
            cursor = conn.cursor() # Bu isimde biri kayıtlı mı diye veritabanına soruyoruz
            cursor.execute("SELECT * FROM users WHERE name=?", (name,))
            if cursor.fetchone(): # Eğer sonuç dönerse (böyle biri varsa)
                QMessageBox.warning(self, "Kullanıcı Mevcut", "Bu ad-soyad ile daha önce kayıt yapılmış.")
                conn.close()
                return
             # Yoksa INSERT INTO ile yeni kullanıcıyı tabloya ekliyoruz
            cursor.execute("INSERT INTO users (name, password, security_word) VALUES (?, ?, ?)", (name, p1, sec_word))
            conn.commit()  # Değişiklikleri onayla
            conn.close() # Kapat
            
            QMessageBox.information(self, "Başarılı", f"Hesabınız başarıyla oluşturuldu!")
             # Kayıt başarılı olunca giriş yapsın diye kutuların içini temizliyoruz
            self.txt_reg_name.clear()
            self.txt_reg_sec_word.clear()
            self.txt_reg_pass.clear()
            self.txt_reg_pass_confirm.clear()
             # Giriş ekranına geri yönlendiriyoruz
            self.stacked_widget.setCurrentWidget(self.login_page)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kayıt işlemi başarısız: {e}")

    # --- ŞİFRE DEĞİŞTİRME SAYFASI ---
    # Tasarım mantığı kayıt sayfasıyla birebir aynı.
    def setup_change_password_page(self):
        if self.change_password_page.layout():
            QWidget().setLayout(self.change_password_page.layout())
            
        layout = QVBoxLayout(self.change_password_page)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(15)
        
        title = QLabel("🔑 ŞİFRE SIFIRLAMA PANELİ")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setStyleSheet("color: #4E342E; margin-bottom: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        cp_card = QFrame()
        cp_card.setFixedWidth(400)
        cp_card.setStyleSheet("border: 1px solid #BCAAA4; border-radius: 10px; background-color: #F5F5F5; padding: 25px;")
        cp_layout = QVBoxLayout(cp_card)
        
        self.txt_cp_name = QLineEdit()
        self.txt_cp_name.setPlaceholderText("Kayıtlı Adınız Soyadınız...")
        self.txt_cp_name.setFont(QFont("Arial", 11))
        cp_layout.addWidget(QLabel("Ad Soyad:"))
        cp_layout.addWidget(self.txt_cp_name)
        
        self.txt_cp_sec_word = QLineEdit()
        self.txt_cp_sec_word.setPlaceholderText("Güvenlik Kelimenizi Girin...")
        self.txt_cp_sec_word.setFont(QFont("Arial", 11))
        cp_layout.addWidget(QLabel("Güvenlik Kelimesi:"))
        cp_layout.addWidget(self.txt_cp_sec_word)
        
        self.txt_cp_new = QLineEdit()
        self.txt_cp_new.setPlaceholderText("Yeni Şifrenizi Belirleyin...")
        self.txt_cp_new.setEchoMode(QLineEdit.Password)
        self.txt_cp_new.setFont(QFont("Arial", 11))
        cp_layout.addWidget(QLabel("Yeni Şifre:"))
        cp_layout.addWidget(self.txt_cp_new)
        
        self.txt_cp_new_confirm = QLineEdit()
        self.txt_cp_new_confirm.setPlaceholderText("Yeni Şifreyi Tekrar Giriniz...")
        self.txt_cp_new_confirm.setEchoMode(QLineEdit.Password)
        self.txt_cp_new_confirm.setFont(QFont("Arial", 11))
        cp_layout.addWidget(QLabel("Yeni Şifre Tekrar:"))
        cp_layout.addWidget(self.txt_cp_new_confirm)
        
        btn_update_pass = QPushButton("Şifreyi Sıfırla")
        btn_update_pass.setStyleSheet("background-color: #00796B; color: white; padding: 12px; font-weight: bold; border-radius: 5px; margin-top: 10px;")
        btn_update_pass.clicked.connect(self.update_password)
        cp_layout.addWidget(btn_update_pass)
        
        btn_back_home = QPushButton("← Giriş Ekranına Dön")
        btn_back_home.setStyleSheet("color: #555; background: transparent; border: none; margin-top: 5px;")
        btn_back_home.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.login_page))
        cp_layout.addWidget(btn_back_home)
        
        layout.addWidget(cp_card)

    def update_password(self):  # ŞİFRE SIFIRLAMA MANTIĞI
        name = self.txt_cp_name.text().strip()
        sec_word = self.txt_cp_sec_word.text().strip()
        new_pass = self.txt_cp_new.text().strip()
        confirm_pass = self.txt_cp_new_confirm.text().strip()
        
        if not name or not sec_word or not new_pass or not confirm_pass:
            QMessageBox.warning(self, "Eksik Alan", "Lütfen tüm kutuları eksiksiz doldurunuz!")
            return
            
        if new_pass != confirm_pass:
            QMessageBox.critical(self, "Şifre Uyuşmazlığı", "Girdiğiniz yeni şifreler birbiriyle eşleşmiyor!")
            return
            
        try:
            conn = sqlite3.connect("users.db")
            cursor = conn.cursor()
             # Adı ve Güvenlik Kelimesi uyuşan birisi var mı kontrol ediyoruz
            cursor.execute("SELECT name FROM users WHERE name=? AND security_word=?", (name, sec_word))
            result = cursor.fetchone()
            
            if result:  # Varsa
                cursor.execute("UPDATE users SET password=? WHERE name=?", (new_pass, name)) # UPDATE ile kullanıcının şifresini güncelliyoruz
                conn.commit()
                QMessageBox.information(self, "Başarılı", "Şifreniz başarıyla sıfırlandı!")
                self.txt_cp_name.clear()
                self.txt_cp_sec_word.clear()
                self.txt_cp_new.clear()
                self.txt_cp_new_confirm.clear()
                self.stacked_widget.setCurrentWidget(self.login_page)
            else:
                QMessageBox.critical(self, "Hata", "Ad veya güvenlik kelimesi eşleşmiyor!")
                
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Şifre sıfırlama başarısız: {e}")

    # --- HESAP SİLME İŞLEMİ ---
     # Parametreye *args koyduk çünkü PyQt butonları tıklanma durumunu (True/False) gönderir, bu hatayı engeller
    def delete_account(self, *args):
         # Kullanıcıya "Emin misin?" diye soran uyarı mesajı (Yes/No butonlu)
        reply = QMessageBox.question(self, 'Hesabı Sil', 
                                     'Hesabınızı kalıcı olarak silmek istediğinize emin misiniz? Bu işlem geri alınamaz.', 
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes: # Eğer Evet dediyse
            try:
                conn = sqlite3.connect("users.db")
                cursor = conn.cursor()
                # O an sisteme giriş yapmış olan kullanıcıyı (self.current_user) tablodan siliyoruz
                cursor.execute("DELETE FROM users WHERE name=?", (self.current_user,))
                conn.commit()
                conn.close()
                QMessageBox.information(self, "Başarılı", "Hesabınız sistemden tamamen silinmiştir.")
                self.logout() # Hesabı silince sistemden çıkış yapıyoruz
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Hesap silinirken hata oluştu: {e}")

# --- MÜŞTERİ OLARAK GİRİŞ DOĞRULAMASI ---
    def login_as_customer(self):
        name = self.txt_customer_name.text().strip()
        password = self.txt_customer_pass.text().strip()
        
        if not name or not password:
            QMessageBox.warning(self, "Hata", "Ad-Soyad ve Şifre alanları boş bırakılamaz!")
            return
            
        try:
            conn = sqlite3.connect("users.db")
            cursor = conn.cursor()
             # Girilen ada ait şifreyi veri tabanından getir
            cursor.execute("SELECT password FROM users WHERE name=?", (name,))
            result = cursor.fetchone() # Sonucu al (Örn: ('12345',))
            conn.close()
            
            if result: # Kullanıcı varsa
                if result[0] == password:# Veritabanındaki şifre (result[0]) ile kutuya yazılan şifre aynıysa
                    self.current_user = name  # Aktif kullanıcıyı bu kişi yap
                    self.is_admin = False # Admin değil
                    self.txt_customer_name.clear()
                    self.txt_customer_pass.clear()
                    self.setup_category_page() # Başarılı girişte Kategori (Menü) sayfasına geç
                else:
                    QMessageBox.critical(self, "Hatalı Şifre", "Girdiğiniz şifre yanlış!")
            else:
                QMessageBox.warning(self, "Kayıt Bulunamadı", "Lütfen önce 'Kayıt Ol' seçeneğinden üye olunuz.")
        except Exception as e:
             QMessageBox.critical(self, "Hata", f"Giriş işlemi başarısız: {e}")
 
 # --- YÖNETİCİ GİRİŞİ DOĞRULAMASI ---
    def login_as_admin(self):
        sifre = self.txt_admin_pass.text()
        if sifre == "admin123":# Yönetici şifresi kod içerisine gömülü (hardcoded)
            self.current_user = "Yönetici"
            self.is_admin = True # Yönetici yetkisini aç
            self.txt_admin_pass.clear()
            self.load_robot_page()# Yönetici ürün satın almaz, direkt robot kuyruğunu takip ekranına gider
        else:
            QMessageBox.critical(self, "Hatalı Şifre", "Girdiğiniz yönetici şifresi yanlış!")
  
  # ÇIKIŞ YAPMA 
    def logout(self):
        self.current_user = "" # Aktif kullanıcı adını sıfırla
        self.is_admin = False # Admin yetkisini kapat
        self.stacked_widget.setCurrentWidget(self.login_page) # Giriş ekranına döndür

     # ÜST BİLGİ (NAVİGASYON) ÇUBUĞU OLUŞTURMA
    # Kod tekrarını önlemek için sayfa üstlerindeki (Geri dön, Sepetim, Çıkış, Profil adı) barını tek fonksiyonla yapıyoruz.

    def create_top_bar(self, back_function=None, title_text=""):
        bar_widget = QWidget()
        layout = QHBoxLayout(bar_widget) # İçindekiler yan yana dizilecek (Yatay)
        layout.setContentsMargins(10, 5, 10, 5)
        
         # Eğer parametre olarak bir geri dön fonksiyonu verildiyse "Geri Dön" butonu ekle
        if back_function:
            btn_back = QPushButton("← Geri Dön")
            btn_back.setFont(QFont("Arial", 11))
            btn_back.clicked.connect(back_function)
            layout.addWidget(btn_back)
            
        lbl_user_status = QLabel(f"👤 Aktif Hesap: <b>{self.current_user}</b>")
        lbl_user_status.setStyleSheet("color: #4E342E; margin-left: 10px;")
        layout.addWidget(lbl_user_status)
        
        layout.addStretch() # Elemanları sağa-sola itmek için boşluk
        
        lbl_title = QLabel(title_text)
        lbl_title.setFont(QFont("Arial", 16, QFont.Bold))
        lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_title)
        
        layout.addStretch()
        # Yönetici değilse (yani müşteriyse) "Hesabımı Sil" butonu göster
        if not self.is_admin:
            btn_delete_acc = QPushButton("🗑️ Hesabımı Sil")
            btn_delete_acc.setFont(QFont("Arial", 10, QFont.Bold))
            btn_delete_acc.setStyleSheet("background-color: #D32F2F; color: white; padding: 8px 12px; border-radius: 5px; border: none;")
            btn_delete_acc.clicked.connect(self.delete_account)
            layout.addWidget(btn_delete_acc)
        
        btn_robot_view = QPushButton("🤖 Robot Paneli")
        btn_robot_view.setFont(QFont("Arial", 10, QFont.Bold))
        btn_robot_view.setStyleSheet("background-color: #37474F; color: white; padding: 8px 12px; border-radius: 5px; border: none;")
        btn_robot_view.clicked.connect(self.load_robot_page)
        layout.addWidget(btn_robot_view)
         # Yönetici değilse Sepet butonunu göster (içinde kaç ürün olduğunu len(self.sepet) ile yazar)
        if not self.is_admin:
            btn_cart = QPushButton(f"🛒 Sepetim ({len(self.sepet)})")
            btn_cart.setFont(QFont("Arial", 11, QFont.Bold))
            btn_cart.setStyleSheet("background-color: #FF9800; color: white; padding: 8px 15px; border-radius: 5px; border: none;")
            btn_cart.clicked.connect(self.load_cart_page)
            layout.addWidget(btn_cart)
            
        btn_logout = QPushButton("🚪 Çıkış")
        btn_logout.setStyleSheet("background-color: #78909C; color: white; padding: 8px 12px; border-radius: 5px; border: none;")
        btn_logout.clicked.connect(self.logout)
        layout.addWidget(btn_logout)
        
        return bar_widget

    # --- 1. SAYFA: KATEGORİ SEÇİMİ ---
    def setup_category_page(self):
        new_category_page = QWidget()
        layout = QVBoxLayout(new_category_page)
        layout.setSpacing(30) 
        
        layout.addWidget(self.create_top_bar(title_text=""))  # Üst menüyü ekliyoruz (geri butonu yok, ana sayfa burası)
        
        title = QLabel("KATEGORİ SEÇİNİZ")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("margin-top: 50px; color: #3E2723;") 
        layout.addWidget(title)
        
        btn_layout = QHBoxLayout() # Kategorilerin yan yana durması için
        btn_layout.setSpacing(30)
        btn_layout.setAlignment(Qt.AlignCenter)
        # Kategoriler listesi: (Veritabanı Dosyası, Tablo Adı, Butonda Yazacak İsim, Veritabanındaki İsim Sütunu, Arka Plan Görseli, Çerçeve Rengi)
        kategoriler = [
            ("hazır_kahveler.db", "Hazır Kahveler", "☕ KAHVELER", "Kahveler", "Kahve Çekirdeği.jpeg", "#5C4336"),
            ("Matcha_ve_Yabancı_Çaylar.db", "Matchalı İçecekler ve Yabancı Çaylar", "🍃 MATCHA VE\nYABANCI ÇAYLAR", "İçecek", "Matcha.jpeg", "#4A6E43"),
            ("Caylar.db", "Çaylar", "🫖 ÇAYLAR", "Çaylar", "Çay yaprağı.jpeg", "#7C2A1E")
        ]
        
        for db, tablo, gorunen_ad, ad_sutunu, gorsel, border_color in kategoriler:
            btn = QPushButton()
            btn.setFixedSize(320, 260)
            btn.setCursor(Qt.PointingHandCursor)
             # Butona CSS mantığıyla arkaplan resmi ve renkli çerçeve ekliyoruz
            btn.setStyleSheet(f"""
                QPushButton {{
                    border-image: url("{gorsel}");
                    border-radius: 15px; 
                    border: 3px solid {border_color};
                }}
            """)
            # Resimli butonun üzerine siyah saydam bir şerit çekip yazının okunmasını sağlıyoruz 
            lbl_ad = QLabel(gorunen_ad, btn)
            lbl_ad.setFont(QFont("Arial", 19, QFont.Bold))
            lbl_ad.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 140); border-radius: 15px;")
            lbl_ad.setAlignment(Qt.AlignCenter)
            lbl_ad.resize(320, 260)
            lbl_ad.setAttribute(Qt.WA_TransparentForMouseEvents)  # Fare tıklamasını engelle, alttaki butona geçsin
            
            # Lambda kullanarak hangi kategoriye tıklandıysa o veritabanı bilgilerini Ürün Yükleme (load_products) sayfasına gönderiyoruz
            btn.clicked.connect(lambda checked, d=db, t=tablo, g=gorunen_ad, a=ad_sutunu, img=gorsel: self.load_products_data(d, t, g, a, img))
            btn_layout.addWidget(btn)
            
        layout.addLayout(btn_layout)
        layout.addStretch() 
        
        # Sayfayı yığına ekle ve göster
        self.stacked_widget.removeWidget(self.category_page)
        self.category_page = new_category_page
        self.stacked_widget.insertWidget(2, self.category_page)
        self.stacked_widget.setCurrentWidget(self.category_page)
    
    # Bir içeceğin (mesela Latte) isminde veya malzemelerinde süt geçip geçmediğini anlayan yardımcı algoritma
    def check_if_milky(self, urun_adi, ana_p):
        sutlu_kelimeler = ["latte", "cappuccino", "mocha", "süt", "köpük", "macchiato", "cortado", "white", "flat", "japanese"]
        if any(k in urun_adi.lower() for k in sutlu_kelimeler): return True
        
        hedef_sutun_parcalari = ["sos", "şurup", "toz", "ekstra", "içerik"]
        arama_metni = ""
        # Veritabanındaki diğer sütunları okuyup içeriklerinde süt tozu, sütlü şurup vs var mı kontrol eder
        for k, v in ana_p.items():
            k_norm = str(k).replace('I', 'ı').replace('İ', 'i').lower().strip()
            if any(p in k_norm for p in hedef_sutun_parcalari):
                if v: arama_metni += f" {v}"
                
        arama_metni = arama_metni.lower().replace("sütsüz", "") 
        return any(k in arama_metni for k in sutlu_kelimeler)

    # --- 2. SAYFA: ÜRÜN LİSTELEME VE FİLTRELEME ---
    def load_products_data(self, db_name, table_name, category_title, name_column, bg_image=""):
        self.name_column = name_column
        self.current_bg_image = bg_image 
         # Daha önce tanımladığımız FaintBackgroundWidget ile transparan arka planlı bir sayfa oluştur
        if bg_image:
            new_products_page = FaintBackgroundWidget(bg_image)
        else:
            new_products_page = QWidget()
            
        layout = QVBoxLayout(new_products_page)
        layout.addWidget(self.create_top_bar(back_function=self.setup_category_page, title_text=category_title))
         # Veri tabanından tüm ürünleri (satırları) çeker
        tum_urunler = DatabaseHelper.get_products(db_name, table_name)
        self.grouped_products = {} # Aynı isimdeki ürünleri gruplamak için Sözlük
        
        # ComboBox (Açılır kutu) filtrelerine eklemek için eşsiz (benzersiz) özellikleri toplayacağımız Set (Küme) listeleri
        all_sut_tipleri = set()
        all_sut_durumlari = set()
        all_sicakliklar = set()
        all_boyutlar = set()
        all_kafein = set()
 
 # Karmaşık veri tabanını işleyip uygulamaya hazır hale getiren Ayrıştırma (Parse) Döngüsü
        for p in tum_urunler:
            urun_adi = p.get(name_column)
            if not urun_adi: continue # Ürün adı boşsa atla
             # Eğer ürün daha önce gruplanmadıysa yeni bir kayıt aç
            if urun_adi not in self.grouped_products:
                self.grouped_products[urun_adi] = {
                    "ana_bilgi": p, 
                    "sut_tipleri": set(), 
                    "sut_durumlari": set(), 
                    "sicakliklar": set(),
                    "boyutlar": set(),
                    "kafein": set()
                }
            
            s_tipi, s_durumu, sicaklik_raw, boyut, kafein_durumu = "", "", "", "", ""

             # Sütun adlarını farklı yazım şekillerine (Süt Tipi, sut_tipi vs) rağmen bulabilmek için kontrol
            for k, v in p.items():
                if v is None: continue
                v_str = str(v).strip()
                if not v_str: continue
                
                k_lower = k.lower()
                if k_lower in ["süt tipi", "sut tipi", "süt_tipi", "sut_tipi"]:
                    s_tipi = v_str
                elif k_lower in ["süt durumu", "sut durumu", "süt_durumu", "sut_durumu", "sütlü/sütsüz"]:
                    s_durumu = v_str
                elif k_lower in ["sıcaklık", "sicaklik", "sicaklik/turu"]:
                    sicaklik_raw = v_str
                elif k_lower in ["boyut", "boyutlar"]:
                    boyut = v_str
                elif "kafein" in k_lower:
                    kafein_durumu = v_str
            # Veri tabanında "Sıcak, Soğuk" gibi bitişik yazılanları virgüllerden koparıp ayırır
            if not sicaklik_raw or sicaklik_raw.lower() in ["none", "null"]: 
                self.grouped_products[urun_adi]["sicakliklar"].add("Belirtilmemiş")
                all_sicakliklar.add("Belirtilmemiş")
            else:
                parts = [pt.strip() for pt in sicaklik_raw.replace("/", ",").split(",") if pt.strip()]
                for pt in parts:
                    self.grouped_products[urun_adi]["sicakliklar"].add(pt)
                    all_sicakliklar.add(pt)

            if not kafein_durumu or kafein_durumu.lower() in ["none", "null"]: 
                kafein_durumu = "Belirtilmemiş"
            self.grouped_products[urun_adi]["kafein"].add(kafein_durumu)
            all_kafein.add(kafein_durumu)
            
            if not boyut or boyut.lower() in ["none", "null"]: 
                boyut = "Standart"
            self.grouped_products[urun_adi]["boyutlar"].add(boyut)
            all_boyutlar.add(boyut)

            sutlu_mu = False  # Ürünün sütlü mü sütsüz mü olduğunu tespit et
            
            if s_durumu and s_durumu.lower() not in ["none", "null", "yok", "-", "sütsüz"]:
                sutlu_mu = True
            elif s_tipi and s_tipi.lower() not in ["none", "null", "yok", "-", "belirtilmemiş"]:
                sutlu_mu = True
            elif self.check_if_milky(urun_adi, p):
                sutlu_mu = True
                
            if sutlu_mu:
                s_durumu = "Sütlü"
                self.grouped_products[urun_adi]["sut_durumlari"].add("Sütlü")
                all_sut_durumlari.add("Sütlü")
                
                if s_tipi and s_tipi.lower() not in ["none", "null", "yok", "-", "belirtilmemiş"]:
                    tipler = [t.strip() for t in s_tipi.split(',')] if ',' in s_tipi else [s_tipi]
                    for t in tipler:
                        if t.lower() not in ["none", "null", "yok", "-", "belirtilmemiş"]:
                            self.grouped_products[urun_adi]["sut_tipleri"].add(t)
                            all_sut_tipleri.add(t)

                 # Sütlü bir içecek olmasına rağmen DB'de süt tipi girilmemişse, otomatik popüler sütleri ekle            
                if not self.grouped_products[urun_adi]["sut_tipleri"]:
                    varsayilan_sutler = ["Tam Yağlı Süt", "Yağsız Süt", "Laktozsuz Süt", "Yulaflı Süt", "Bademli Süt"]
                    for vs in varsayilan_sutler:
                        self.grouped_products[urun_adi]["sut_tipleri"].add(vs)
                        all_sut_tipleri.add(vs)
            else:
                s_durumu = "Sütsüz"
                self.grouped_products[urun_adi]["sut_durumlari"].add("Sütsüz")
                all_sut_durumlari.add("Sütsüz")


         # FİLTRELEME ÇUBUĞU ARAYÜZÜ (ComboBox'lar)
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(15, 0, 15, 10)
        
        combo_style = "QComboBox { border: 1px solid #BCAAA4; border-radius: 4px; padding: 5px; min-width: 120px; background-color: white; }"
        
        self.cmb_sicaklik = QComboBox()
        self.cmb_sicaklik.setStyleSheet(combo_style)
        self.cmb_sicaklik.addItem("Sıcaklık (Tümü)")
        self.cmb_sicaklik.addItems(sorted(list(all_sicakliklar)))
        filter_layout.addWidget(self.cmb_sicaklik)
        
        self.cmb_sut_durumu = QComboBox()
        self.cmb_sut_durumu.setStyleSheet(combo_style)
        self.cmb_sut_durumu.addItem("Süt Durumu (Tümü)")
        self.cmb_sut_durumu.addItems(sorted(list(all_sut_durumlari)))
        filter_layout.addWidget(self.cmb_sut_durumu)
        
        self.cmb_sut_tipi = QComboBox()
        self.cmb_sut_tipi.setStyleSheet(combo_style)
        self.cmb_sut_tipi.addItem("Süt Tipi (Tümü)")
        self.cmb_sut_tipi.addItems(sorted(list(all_sut_tipleri)))
        filter_layout.addWidget(self.cmb_sut_tipi)

        self.cmb_kafein = QComboBox()
        self.cmb_kafein.setStyleSheet(combo_style)
        self.cmb_kafein.addItem("Kafein (Tümü)")
        self.cmb_kafein.addItems(sorted(list(all_kafein)))
        filter_layout.addWidget(self.cmb_kafein)
        
        self.cmb_boyut = QComboBox()
        self.cmb_boyut.setStyleSheet(combo_style)
        self.cmb_boyut.addItem("Boyut (Tümü)")
        self.cmb_boyut.addItems(sorted(list(all_boyutlar)))
        filter_layout.addWidget(self.cmb_boyut)

        filter_layout.addStretch()

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Ürün Ara...")
        self.txt_search.setStyleSheet("border: 1px solid #795548; border-radius: 15px; padding: 5px 15px; font-size: 14px; background-color: white;")
        self.txt_search.setFixedWidth(250)
        filter_layout.addWidget(self.txt_search)

        layout.addLayout(filter_layout)

        scroll_area = QScrollArea() # Izgara (Grid) yapısında ürünlerin yana yana ve aşağı kaydırılabilir (ScrollArea) olması için yapı
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        scroll_area.viewport().setStyleSheet("background-color: transparent;")
        
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background-color: transparent;")
        
        self.grid_layout = QGridLayout(self.scroll_content)
        
        for i in range(4):  # 4 Sütunlu bir tasarım
            self.grid_layout.setColumnStretch(i, 1)
        self.grid_layout.setAlignment(Qt.AlignTop) 
        
        scroll_area.setWidget(self.scroll_content)
        layout.addWidget(scroll_area)
        
         # Combobox değerleri veya arama kutusu değiştiğinde filtrelemeyi tetikle
        self.cmb_sicaklik.currentTextChanged.connect(self.apply_filters)
        self.cmb_sut_durumu.currentTextChanged.connect(self.toggle_sut_tipi_combo) 
        self.cmb_sut_tipi.currentTextChanged.connect(self.apply_filters)
        self.cmb_kafein.currentTextChanged.connect(self.apply_filters)
        self.cmb_boyut.currentTextChanged.connect(self.apply_filters)
        self.txt_search.textChanged.connect(self.apply_filters)

        self.stacked_widget.removeWidget(self.products_page)
        self.products_page = new_products_page
        self.stacked_widget.insertWidget(3, self.products_page)
        self.stacked_widget.setCurrentWidget(self.products_page)
        
        self.apply_filters() # Tüm ürünleri başlangıçta ekrana çizmek için çağırıyoruz

    def toggle_sut_tipi_combo(self): # Eğer filtrelerden Sütsüz seçilirse, Süt Tipi combobox'ını devre dışı bırakır (Akıllı arayüz)
        if self.cmb_sut_durumu.currentText() == "Sütsüz":
            self.cmb_sut_tipi.setCurrentIndex(0) 
            self.cmb_sut_tipi.setEnabled(False)  
            self.cmb_sut_tipi.setStyleSheet("QComboBox { background-color: #E0E0E0; color: #9E9E9E; border: 1px solid #BCAAA4; border-radius: 4px; padding: 5px; min-width: 120px; }")
        else:
            self.cmb_sut_tipi.setEnabled(True)
            self.cmb_sut_tipi.setStyleSheet("QComboBox { background-color: white; border: 1px solid #BCAAA4; border-radius: 4px; padding: 5px; min-width: 120px; }")
        
        self.apply_filters()

     # FİLTRELEME MOTORU VE ÜRÜNLERİ EKRANA ÇİZME
    def apply_filters(self): 
         # Önce ekrandaki tüm mevcut ürün widget'larını temizle (sil)
        for i in reversed(range(self.grid_layout.count())): 
            widget_to_remove = self.grid_layout.itemAt(i).widget()
            if widget_to_remove is not None:
                widget_to_remove.setParent(None)

         # Kullanıcının seçtiği filtre değerlerini değişkenlere al
        search_text = self.txt_search.text().lower()
        sel_sicaklik = self.cmb_sicaklik.currentText()
        sel_sut_durumu = self.cmb_sut_durumu.currentText()
        sel_sut_tipi = self.cmb_sut_tipi.currentText()
        sel_boyut = self.cmb_boyut.currentText()
        sel_kafein = self.cmb_kafein.currentText()

        row, col = 0, 0
        # Gruplanmış ürünler içinde dön ve filtrelere uymayanları 'continue' diyerek atla
        for urun_adi, veri in self.grouped_products.items():
            if search_text and search_text not in urun_adi.lower():
                continue

            if sel_sicaklik != "Sıcaklık (Tümü)" and sel_sicaklik not in veri["sicakliklar"]:
                continue
            if sel_sut_durumu != "Süt Durumu (Tümü)" and sel_sut_durumu not in veri["sut_durumlari"]:
                continue
                
            if sel_sut_tipi != "Süt Tipi (Tümü)":
                if not veri["sut_tipleri"] or sel_sut_tipi not in veri["sut_tipleri"]:
                    continue
                    
            if sel_boyut != "Boyut (Tümü)" and sel_boyut not in veri["boyutlar"]:
                continue
            if sel_kafein != "Kafein (Tümü)" and sel_kafein not in veri["kafein"]:
                continue

            prod_widget = QWidget() # Filtreden geçen her ürün için ekranda KUTUCUK (Widget) oluştur
            prod_widget.setFixedSize(240, 280) 
            
            prod_vbox = QVBoxLayout(prod_widget)
            
            img_label = QLabel() # GÖRSEL İŞLEME (Veritabanındaki BLOB bytes verisini veya Resim Yolunu QPixmap nesnesine dönüştürür)
            blob_data = veri["ana_bilgi"].get("Görsel") or veri["ana_bilgi"].get("Gorsel")
            pixmap = QPixmap()
            if blob_data:
                if isinstance(blob_data, bytes):
                    pixmap.loadFromData(blob_data) # Byte verisi ise
                elif isinstance(blob_data, str):
                    if os.path.exists(blob_data):
                        pixmap.load(blob_data) # Dosya yolu ise (Örn: c:\resimler\latte.png)
                        
            if pixmap.isNull(): # Görsel yoksa/bozuksa yedek metin göster
                img_label.setText("[ Görsel Yok ]")
                img_label.setStyleSheet("background-color: #D7CCC8; border-radius: 8px;")
            else:
                img_label.setPixmap(pixmap.scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                
            img_label.setAlignment(Qt.AlignCenter)
            img_label.setFixedSize(160, 160)
            img_label.setCursor(Qt.PointingHandCursor)
            
            name_label = QLabel(urun_adi)
            name_label.setFont(QFont("Arial", 12, QFont.Bold))
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setWordWrap(True)  # İsmi uzunsa alt satıra geçsin
            
            prod_vbox.addWidget(img_label)
            prod_vbox.addWidget(name_label)
            prod_widget.setStyleSheet("border: 1px solid #D7CCC8; border-radius: 8px; background-color: white; padding: 10px;")
            
             # Arkaplandaki kategoriyi tespit edip, ürüne tıklandığında ona göre fiyat hesaplanması için db_name'i yollama
            db_name = "hazır_kahveler.db"
            if "Caylar.db" in self.current_bg_image or "Çay yaprağı" in self.current_bg_image:
                db_name = "Caylar.db"
            elif "Matcha" in self.current_bg_image:
                db_name = "Matcha_ve_Yabancı_Çaylar.db"
            
             # Ürünün görseline tıklandığında Detay Sayfasına gitmesini sağlayan olay (Event)
            img_label.mouseReleaseEvent = lambda event, name=urun_adi, v=veri, db=db_name: self.load_detail_page(name, v, db)

            # Oluşturulan kutucuğu Grid (Izgara) sistemine satır ve sütun indexi ile yerleştir
            self.grid_layout.addWidget(prod_widget, row, col, Qt.AlignCenter | Qt.AlignTop)
            
            col += 1
            if col > 3: # 4. sütunu geçtiyse alt satıra atla
                col = 0
                row += 1

     # Radyo butonlarında küçük boyun başta, büyük boyun sonda sıralanması için boyutların "ağırlığını" belirleyen algoritma
    def get_size_weight(self, size_str):
        s = size_str.lower()
        if any(w in s for w in ["küçük", "small", "single", "short", "250", "350"]): return 1
        if any(w in s for w in ["orta", "medium", "standart", "tall", "400", "470"]): return 2
        if any(w in s for w in ["büyük", "large", "double", "grande", "venti", "600"]): return 3
        return 99

    # --- 3. SAYFA: ÜRÜN DETAY SAYFASI ---
    def load_detail_page(self, urun_adi, veri, db_name):
        if self.is_admin:
            QMessageBox.information(self, "Yetki Kısıtlaması", "Yöneticiler sipariş oluşturamaz!")
            return
            
        if self.current_bg_image:
            detail_page = FaintBackgroundWidget(self.current_bg_image)
        else:
            detail_page = QWidget()
            
        layout = QVBoxLayout(detail_page)
        layout.setSpacing(0)
        layout.addWidget(self.create_top_bar(back_function=lambda: self.stacked_widget.setCurrentWidget(self.products_page), title_text="Ürün Detayı"))
        
        detail_hbox = QHBoxLayout() # Ekranı yatayda ikiye böleceğiz. Sol: Resim, Sağ: Özellikler
        detail_hbox.setContentsMargins(10, 10, 10, 10)
        
        img_label = QLabel()
        blob_data = veri["ana_bilgi"].get("Görsel") or veri["ana_bilgi"].get("Gorsel")
        pixmap = QPixmap()
        
        if blob_data:
            if isinstance(blob_data, bytes):
                pixmap.loadFromData(blob_data)
            elif isinstance(blob_data, str):
                if os.path.exists(blob_data):
                    pixmap.load(blob_data)
                    
        if not pixmap.isNull():
            img_label.setPixmap(pixmap.scaled(340, 340, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            img_label.setText("[ Görsel ]")
            img_label.setStyleSheet("background-color: #D7CCC8; border-radius: 12px;")
            
        img_label.setFixedSize(340, 340)
        detail_hbox.addWidget(img_label, alignment=Qt.AlignTop)
        
        # 2) SAĞ TARAF (Özellikler, Seçim Butonları, Sepete Ekle)
        info_widget = QWidget()
        info_vbox = QVBoxLayout(info_widget)
        info_vbox.setSpacing(8)
        info_vbox.setContentsMargins(15, 0, 0, 0)
        
        title = QLabel(urun_adi)
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setStyleSheet("color: #3E2723; margin-bottom: 5px;")
        info_vbox.addWidget(title)
        
        ana_p = veri["ana_bilgi"]
        gercek_sut_tipleri = [s for s in veri["sut_tipleri"] if s.lower() not in ["yok", "none", "belirtilmemiş"]]
        is_sutlu = self.check_if_milky(urun_adi, ana_p) or len(gercek_sut_tipleri) > 0
        
        sabit_detaylar = [] # Ürünün açıklama metninde yazacak özellikleri
        
        self.sicaklik_grubu = None
        gercek_sicakliklar = [s for s in veri["sicakliklar"] if s.lower() not in ["none", "null", "belirtilmemiş"]]
        
        # Sadece tek sıcaklık varsa butona gerek yok, metin olarak yaz.
        if len(gercek_sicakliklar) <= 1:
            varsayilan_sicaklik = gercek_sicakliklar[0] if gercek_sicakliklar else "Belirtilmemiş"
            sabit_detaylar.append(f"<b>Sıcaklık / Türü:</b> {varsayilan_sicaklik}")
        else:
            varsayilan_sicaklik = "Belirtilmemiş"

        sut_durumu_degeri = "Sütlü" if is_sutlu else (", ".join(list(veri["sut_durumlari"])) if veri["sut_durumlari"] else "Sütsüz")
        sabit_detaylar.append(f"<b>Süt Durumu:</b> {sut_durumu_degeri}")

        def normalize_text(text):
            if text is None: return ""
            return str(text).replace('I', 'ı').replace('İ', 'i').lower().strip()

        # Veritabanında Şurup, Sos, Kalori, Alerjen vb. sütunlar varsa bunları akıllıca tespit edip ekrana yazdırma
        aranacak_anahtar_kelimeler = [
            "kafein", "tatlı", "acı", "aroma", "tat not", 
            "şurup", "sos", "ekstra", "toz", "kalori", "içerik", "alerjen"
        ]

        db_keys = list(ana_p.keys())
        for k in db_keys.copy():
            k_norm = normalize_text(k)
            if any(haric in k_norm for haric in ["süt", "boyut", "sıcaklık", "sicaklik", "görsel", "fiyat"]):
                continue
                
            if any(anahtar in k_norm for anahtar in aranacak_anahtar_kelimeler):
                v_norm = normalize_text(ana_p[k])
                if ana_p[k] and str(ana_p[k]).strip() and v_norm not in ["", "yok", "none", "belirtilmemiş", "-", "null", "nan"]:
                    sabit_detaylar.append(f"<b>{str(k).strip()}:</b> {ana_p[k]}")
                    
        details_browser = QTextBrowser() # Özellikleri HTML formatında güzel göstermek için
        html_icerik = f"<div style='line-height: 140%; font-family: Arial; font-size: 16px;'>{'<br>'.join(sabit_detaylar)}</div>"
        details_browser.setHtml(html_icerik)
        details_browser.setStyleSheet("QTextBrowser { border: none; background-color: transparent; }")
        info_vbox.addWidget(details_browser, 1)

        if len(gercek_sicakliklar) > 1:  # Hem Sıcak Hem Soğuk olan ürünlerde Yuvarlak Seçim (Radio Button) göster
            lbl_sicaklik_title = QLabel("<b>Sıcaklık Seçiniz:</b>")
            lbl_sicaklik_title.setFont(QFont("Arial", 11))
            info_vbox.addWidget(lbl_sicaklik_title)
            
            self.sicaklik_grubu = QButtonGroup(detail_page) # Butonları gruplar (sadece 1 tanesi seçilebilir olur)
            sicaklik_hbox = QHBoxLayout()
            
            for i, s_ad in enumerate(sorted(gercek_sicakliklar)):
                rb_sicaklik = QRadioButton(s_ad)
                if i == 0: rb_sicaklik.setChecked(True)
                self.sicaklik_grubu.addButton(rb_sicaklik)
                sicaklik_hbox.addWidget(rb_sicaklik)
                
            sicaklik_hbox.addStretch()
            info_vbox.addLayout(sicaklik_hbox)
        
        self.sut_grubu = None # Sütlü ürünlerde Süt Tipi (Laktozsuz, Yulaflı vb.) seçimi göster
        if is_sutlu:
            lbl_sut_title = QLabel("<b>Süt Tipi Seçiniz:</b>")
            lbl_sut_title.setFont(QFont("Arial", 11))
            info_vbox.addWidget(lbl_sut_title)
            self.sut_grubu = QButtonGroup(detail_page)
            sut_hbox = QHBoxLayout()
            
            sut_listesi = sorted(gercek_sut_tipleri) if gercek_sut_tipleri else ["Tam Yağlı Süt", "Yağsız Süt", "Laktozsuz Süt", "Yulaflı Süt", "Bademli Süt"]
            if not gercek_sut_tipleri and "Laktozsuz Süt" not in sut_listesi: 
                sut_listesi.append("Laktozsuz Süt")
                
            for i, sut_adi in enumerate(sut_listesi):
                rb_sut = QRadioButton(sut_adi)
                if i == 0: rb_sut.setChecked(True)
                self.sut_grubu.addButton(rb_sut)
                sut_hbox.addWidget(rb_sut)
            sut_hbox.addStretch()
            info_vbox.addLayout(sut_hbox)
        
        # BOYUT SEÇİMİ VE FİYAT EŞLEŞTİRMESİ   
        lbl_boyut_title = QLabel("<b>Boyut Seçiniz:</b>")
        lbl_boyut_title.setFont(QFont("Arial", 11))
        info_vbox.addWidget(lbl_boyut_title)
        
        self.boyut_grubu = QButtonGroup(detail_page)
        boyut_hbox = QHBoxLayout()
        self.current_size_prices.clear() #Fiyatı sıfırlar
        
        db_boyutlar = [b for b in veri.get("boyutlar", []) if b.lower() not in ["yok", "none", "belirtilmemiş"]]
        
        if db_boyutlar: # Veri tabanında boyut sütunu varsa
            db_boyutlar.sort(key=self.get_size_weight) # Önce yazdığımız sıralama algoritması ile diz
            for i, b_ad in enumerate(db_boyutlar):
                fiyat = self.get_price(db_name, b_ad) # Motorla fiyatı bul
                rb_boyut = QRadioButton(f"{b_ad} ({fiyat} TL)")
                self.current_size_prices[rb_boyut] = fiyat # Butonu ve fiyatını sözlüğe kaydet 
                if i == 0: rb_boyut.setChecked(True)
                self.boyut_grubu.addButton(rb_boyut)
                boyut_hbox.addWidget(rb_boyut)
        else: # Veri tabanında yoksa zeki yedek sistem devreye girer
            if db_name == "Caylar.db":
                varsayilan_boyutlar = ["250 ml", "400 ml", "600 ml"]
            elif db_name == "hazır_kahveler.db":
                varsayilan_boyutlar = ["Single", "Standart", "Double"]
            else:
                varsayilan_boyutlar = ["Küçük", "Standart", "Büyük"]
                
            for i, b_ad in enumerate(varsayilan_boyutlar):
                fiyat = self.get_price(db_name, b_ad)
                rb_boyut = QRadioButton(f"{b_ad} ({fiyat} TL)")
                self.current_size_prices[rb_boyut] = fiyat
                if i == 1: rb_boyut.setChecked(True)
                self.boyut_grubu.addButton(rb_boyut)
                boyut_hbox.addWidget(rb_boyut)
                
        boyut_hbox.addStretch()
        info_vbox.addLayout(boyut_hbox)
        
        # SEPETE EKLE BUTONU
        btn_sepet = QPushButton("Sepete Ekle")
        btn_sepet.setFont(QFont("Arial", 14, QFont.Bold))
        btn_sepet.setStyleSheet("background-color: #2E7D32; color: white; padding: 12px; border-radius: 8px; border: none;")
        # Lambda üzerinden tüm seçili bilgileri add_to_cart'a yollarız
        btn_sepet.clicked.connect(lambda: self.add_to_cart(urun_adi, sut_durumu_degeri, blob_data, varsayilan_sicaklik))
        info_vbox.addWidget(btn_sepet)
        
        info_vbox.addStretch()
        detail_hbox.addWidget(info_widget)
        layout.addLayout(detail_hbox)
        layout.addStretch()
        
        self.stacked_widget.addWidget(detail_page)
        self.stacked_widget.setCurrentWidget(detail_page)

    def add_to_cart(self, urun_adi, sut_durumu_degeri, blob_gorsel, varsayilan_sicaklik):
        secilen_rb = self.boyut_grubu.checkedButton()  # Kullanıcının işaretlediği radyo butonunu bul
        boyut_ismi = secilen_rb.text().split(" (")[0] # Metni parçala, fiyat kısmını at (örn: "Standart (80 TL)" -> "Standart")
        secilen_fiyat = self.current_size_prices.get(secilen_rb, 0) # Hafızadan fiyatını çek
        
        # Seçili olan diğer verileri oku
        secilen_sut_tipi = self.sut_grubu.checkedButton().text() if self.sut_grubu and self.sut_grubu.checkedButton() else "Yok"
        secilen_sicaklik = self.sicaklik_grubu.checkedButton().text() if getattr(self, "sicaklik_grubu", None) and self.sicaklik_grubu.checkedButton() else varsayilan_sicaklik
        # Kullanıcının listesine (Sepet) bir obje (Sözlük) olarak ürünü ekle
        self.sepet.append({
            "ad": urun_adi, "boyut": boyut_ismi, "secilen_sut_tipi": secilen_sut_tipi,
            "sut_durumu": sut_durumu_degeri, "secilen_sicaklik": secilen_sicaklik, 
            "gorsel_blob": blob_gorsel, "fiyat": secilen_fiyat
        })
        QMessageBox.information(self, "Başarılı", f"{urun_adi} sepetinize eklendi!\nTutar: {secilen_fiyat} TL")
        self.setup_category_page() # Ekledikten sonra Ana menüye dön
    
    # --- 4. SAYFA: SEPET VE SİPARİŞİ ONAYLAMA SAYFASI ---
    def load_cart_page(self):
        cart_page = QWidget()
        layout = QVBoxLayout(cart_page)
        layout.addWidget(self.create_top_bar(back_function=self.setup_category_page, title_text="SEPETİM"))
        
        if not self.sepet: # Sepet dizisi boşsa
            empty_label = QLabel("Sepetiniz şu anda boş.")
            empty_label.setFont(QFont("Arial", 14))
            empty_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(empty_label)
            layout.addStretch()
            self.stacked_widget.addWidget(cart_page)
            self.stacked_widget.setCurrentWidget(cart_page)
            return

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        cart_list_layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        
        toplam_tutar = sum(item.get("fiyat", 0) for item in self.sepet) # Tüm sepet item'larının 'fiyat' değerlerini toplar
        
        # Sepetteki her ürün için arayüzde bir kutu oluştur
        for index, item in enumerate(self.sepet):
            item_frame = QFrame()
            item_frame.setStyleSheet("border: 1px solid #CFD8DC; border-radius: 8px; background-color: #F8F9FA; padding: 10px; margin: 5px;")
            item_layout = QHBoxLayout(item_frame)
            
            # Ürün bilgisi ve fiyatını yazdır
            detay_text = f"<b>{item['ad']}</b> ({item['boyut']}) - <span style='color:#D32F2F; font-size:14px;'><b>{item.get('fiyat', 0)} TL</b></span><br><small>Sıcaklık: {item['secilen_sicaklik']} | Süt: {item['sut_durumu']} | Tip: {item['secilen_sut_tipi']}</small>"
            lbl_info = QLabel(detay_text)
            lbl_info.setFont(QFont("Arial", 12))
            item_layout.addWidget(lbl_info)
            item_layout.addStretch()
            
            # Çöp tenekesi / Sil butonu
            btn_delete = QPushButton("Sil")
            btn_delete.setStyleSheet("background-color: #D32F2F; color: white; padding: 5px 12px; border-radius: 4px; border: none;")
            btn_delete.clicked.connect(lambda checked, idx=index: self.remove_from_cart(idx))
            item_layout.addWidget(btn_delete)
            cart_list_layout.addWidget(item_frame)
            
        cart_list_layout.addStretch()
        bottom_layout = QHBoxLayout()
        
        btn_clear = QPushButton("Sepeti Temizle")
        btn_clear.setStyleSheet("background-color: #757575; color: white; padding: 10px 20px; border-radius: 6px; border: none;")
        btn_clear.clicked.connect(self.clear_cart)
        bottom_layout.addWidget(btn_clear)
        
        bottom_layout.addStretch()
        
        # Hesaplanan toplam tutarı alt bar'a yaz
        lbl_toplam = QLabel(f"Genel Toplam: <b>{toplam_tutar} TL</b>")
        lbl_toplam.setStyleSheet("font-size: 18px; color: #D32F2F; margin-right: 20px;")
        bottom_layout.addWidget(lbl_toplam)
        
        btn_confirm = QPushButton("Siparişi Onayla")
        btn_confirm.setStyleSheet("background-color: #2E7D32; color: white; padding: 10px 30px; font-weight: bold; font-size: 14px; border-radius: 6px; border: none;")
        btn_confirm.clicked.connect(self.confirm_order) # Robot kuyruğuna yollar
        bottom_layout.addWidget(btn_confirm)
        layout.addLayout(bottom_layout)
        
        self.stacked_widget.addWidget(cart_page)
        self.stacked_widget.setCurrentWidget(cart_page)

    def remove_from_cart(self, index):
        if 0 <= index < len(self.sepet):
            self.sepet.pop(index) # Diziden objeyi atar
            self.load_cart_page() # Sayfayı günceller

    def clear_cart(self):
        self.sepet.clear() # Dizinin tüm elemanlarını siler
        self.setup_category_page()

    def confirm_order(self):
        if not self.sepet: return
        # Tüm sepeti tek bir paket yapıp robot_kuyrugu dizisine atıyoruz
        self.robot_kuyrugu.append({"musteri": self.current_user, "urunler": list(self.sepet)})
        QMessageBox.information(self, "Sipariş Alındı", f"Siparişiniz robot kuyruğuna başarıyla iletildi.")
        self.sepet.clear() # Sepet onaylanınca boşaltılır
        # Eğer kuyrukta sadece 1 sipariş varsa (yani robot boşsa) sayacı anında başlatıyoruz
        if len(self.robot_kuyrugu) == 1:
            self.start_robot_timer()
        self.setup_category_page()

    # --- SAYAÇ VE ROBOT MOTORU MANTIĞI ---
    def start_robot_timer(self):
        if self.robot_kuyrugu:
            aktif_paket = self.robot_kuyrugu[0]  # Sıranın en başındaki (0. indeks) siparişi alıyoruz
            urun_sayisi = len(aktif_paket["urunler"])
            self.kalan_saniye = urun_sayisi * 150  # Siparişteki her bir kahve için robota 150 saniye veriyoruz
            self.timer.start(1000)  # Geri sayımı 1000 milisaniye (1 saniye) aralıklarla çalıştır

    def update_countdown(self): # Geri sayım her 1 saniyede tık ettiğinde bu fonksiyon tetiklenir
        if self.kalan_saniye > 0:
            self.kalan_saniye -= 1
            self.update_robot_queue_ui() # Arayüzdeki sayacı güncelle
        else: 
            self.timer.stop() # Süre 0 olunca motoru durdur
            if self.robot_kuyrugu: # Süresi biten siparişi (0. index) diziden sil (pop) ve tamamlandığını bildir
                tamamlanan = self.robot_kuyrugu.pop(0)
                QMessageBox.information(self, "Robot Bildirisi", f"🤖 {tamamlanan['musteri']} adlı müşterinin siparişi hazırlandı!")
                if self.robot_kuyrugu:
                    self.start_robot_timer()  # Eğer bekleyen başka sipariş varsa robota onu ver
                self.update_robot_queue_ui() # Arayüzü yenile

    # ROBOT TAKİP (SIRA) PANELİ TASARIMI
    def setup_robot_page(self): 
        self.robot_layout = QVBoxLayout(self.robot_page)
        self.robot_header_layout = QHBoxLayout()
        
        btn_back = QPushButton("← Geri Dön")
        # Adminse çıkış ekranına, Müşteriyse kategorilere döndürür
        btn_back.setFont(QFont("Arial", 11))
        btn_back.clicked.connect(lambda: self.setup_category_page() if not self.is_admin else self.logout())
        self.robot_header_layout.addWidget(btn_back)
        
        title = QLabel("🤖 KAHVE ROBOTU HAZIRLAMA SIRASI")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setStyleSheet("color: #006064;")
        title.setAlignment(Qt.AlignCenter)
        self.robot_header_layout.addWidget(title)
        self.robot_header_layout.addStretch()
        self.robot_layout.addLayout(self.robot_header_layout)
        
        self.queue_container = QWidget()
        self.queue_inner_layout = QVBoxLayout(self.queue_container) # Sıralı siparişlerin ekleneceği dikey düzen
        self.robot_layout.addWidget(self.queue_container) 
        self.robot_layout.addStretch()

    def load_robot_page(self):
        self.update_robot_queue_ui() # Robot ekranını açarken listeyi tazele
        self.stacked_widget.setCurrentWidget(self.robot_page)

    # KVKK gereği ekrandaki isimleri "M** Y***" şeklinde gizleyen algoritma
    def mask_name(self, full_name):
        parcalar = full_name.split() # Boşluklardan parçala (Ad, Soyad)
        maskeli_parcalar = []
        for p in parcalar:
            if len(p) > 0:
                maskeli_parcalar.append(p[0] + "*" * (len(p) - 1)) # İlk harfi al, kalanına yıldız at
            else:
                maskeli_parcalar.append(p)
        return " ".join(maskeli_parcalar)
    
    # Admin'in sipariş sıralamasını oklarla aşağı yukarı taşımasını sağlayan fonksiyon
    def move_order(self, index, yon_degisimi):
        yeni_index = index + yon_degisimi # -1 derse yukarı, 1 derse aşağı
        # 0. indeks (Şu an yapılan ürün) taşınamaz. Diğerleri yer değiştirilebilir.
        if 0 < yeni_index < len(self.robot_kuyrugu) and index > 0:
            # Dizideki iki elemanın Python taktiği ile yerini değiştiriyoruz (Swap)
            self.robot_kuyrugu[index], self.robot_kuyrugu[yeni_index] = self.robot_kuyrugu[yeni_index], self.robot_kuyrugu[index]
            self.update_robot_queue_ui() # Ekrana yansıt

    # ROBOT KUYRUĞUNUN EKRANA ÇİZİLMESİ
    def update_robot_queue_ui(self): # Ekrandaki eski listeyi tamamen siler
        while self.queue_inner_layout.count():
            item = self.queue_inner_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        if not self.robot_kuyrugu:
            empty_label = QLabel("Şu anda sırada bekleyen sipariş yok.\nRobot yeni emirleri bekliyor...")
            empty_label.setFont(QFont("Arial", 14))
            empty_label.setStyleSheet("color: #757575; margin-top: 50px;")
            empty_label.setAlignment(Qt.AlignCenter)
            self.queue_inner_layout.addWidget(empty_label)
            return

        # Saniyeyi formata böl (Örn: 150 saniye -> 02:30)
        dakika = self.kalan_saniye // 60
        saniye = self.kalan_saniye % 60
        zaman_metni = f"{dakika:02d}:{saniye:02d}"

        # Kuyruktaki siparişleri listele
        for index, paket in enumerate(self.robot_kuyrugu):
            queue_frame = QFrame()
            if index == 0:
                # 0. indeks Robotun o an hazırladığı içecektir. Rengi yeşildir ve Sayaç görünür
                queue_frame.setStyleSheet("border: 2px solid #2E7D32; border-radius: 10px; background-color: #E8F5E9; padding: 15px; margin: 5px;")
                durum_prefix = f"<span style='color:#D32F2F; font-size:16px;'><b>⏱️ {zaman_metni}</b></span> <span style='color:#2E7D32;'><b>[HAZIRLANIYOR]</b></span> "
            else:
                # Diğer indeksler bekleyen kuyruktur, gri görünür.
                queue_frame.setStyleSheet("border: 1px solid #B0BEC5; border-radius: 8px; background-color: #ECEFF1; padding: 12px; margin: 5px;")
                durum_prefix = f"<span style='color:#FF8F00;'>⏳ [SIRA NO: {index}]</span> "
                
            item_layout = QHBoxLayout(queue_frame)
            
            detaylar_listesi = [] # Bu paketin içindeki tüm içecek isimlerini yan yana "+" ile birleştir
            toplam_siparis_tutari = sum(urun.get("fiyat", 0) for urun in paket["urunler"])
            
            for urun in paket["urunler"]:
                u_detay = f"{urun['ad']} ({urun['boyut']})"
                if urun['secilen_sut_tipi'] != "Yok": u_detay += f" [{urun['secilen_sut_tipi']}]"
                detaylar_listesi.append(u_detay)
            urunler_metni = " + ".join(detaylar_listesi)
            
            if self.is_admin or (self.current_user == paket["musteri"]):# Admin veya sipariş sahibi ise ismi tam gör, yoksa maskeli (M** Y***) gör
                görünen_isim = paket["musteri"]
            else:
                görünen_isim = self.mask_name(paket["musteri"])
                
            tam_metin = f"{durum_prefix}<b>{görünen_isim}</b> - Siparişleri: <span style='color:#3E2723;'>{urunler_metni}</span> - <span style='color:#D32F2F; font-size: 14px;'><b>Toplam: {toplam_siparis_tutari} TL</b></span>"
            
            lbl_info = QLabel(tam_metin)
            lbl_info.setFont(QFont("Arial", 13))
            lbl_info.setWordWrap(True)
            item_layout.addWidget(lbl_info)
            item_layout.addStretch()
            
            if self.is_admin and index > 0: # Sadece adminse ok işaretleri (Sıra değiştirme butonları) ekle
                btn_up = QPushButton("⬆️")
                btn_up.setToolTip("Sırayı Yukarı Taşı")
                btn_up.setStyleSheet("background-color: #E0E0E0; border-radius: 4px; padding: 8px; margin-right: 2px;")
                if index == 1: btn_up.setEnabled(False)  # 1 numarayı daha yukarı çekemez (0 olamaz)
                btn_up.clicked.connect(lambda checked, idx=index: self.move_order(idx, -1))
                
                btn_down = QPushButton("⬇️")
                btn_down.setToolTip("Sırayı Aşağı Taşı")
                btn_down.setStyleSheet("background-color: #E0E0E0; border-radius: 4px; padding: 8px; margin-right: 10px;")
                if index == len(self.robot_kuyrugu) - 1: btn_down.setEnabled(False)  # En sondakini aşağı atamaz
                btn_down.clicked.connect(lambda checked, idx=index: self.move_order(idx, 1)) 
                
                item_layout.addWidget(btn_up)
                item_layout.addWidget(btn_down)

            btn_action = QPushButton("Siparişi İptal Et" if index == 0 else "Sıradan Çıkar") # Siparişi iptal et / sil butonu
            
            if self.is_admin or (self.current_user == paket["musteri"]):  # İptal etme yetkisi sadece Admin'e ya da Siparişi veren asıl kişiye (current_user) aittir
                btn_action.setEnabled(True)
                if index == 0:
                    btn_action.setStyleSheet("background-color: #C62828; color: white; padding: 10px 20px; font-weight: bold; border-radius: 5px; border: none;")
                else:
                    btn_action.setStyleSheet("background-color: #546E7A; color: white; padding: 8px 15px; border-radius: 5px; border: none;")
            else:
                btn_action.setEnabled(False) # Başkası müdahale edemesin diye tuş kilitlenir
                btn_action.setStyleSheet("background-color: #CFD8DC; color: #90A4AE; padding: 8px 15px; border-radius: 5px; border: none;")
                
            btn_action.clicked.connect(lambda checked, idx=index: self.complete_robot_order(idx))
            item_layout.addWidget(btn_action)
            
            self.queue_inner_layout.addWidget(queue_frame)

    def complete_robot_order(self, index): # Robot siparişi bitirdiğinde (ya da iptal edildiğinde) diziden siler
        if 0 <= index < len(self.robot_kuyrugu):
            self.robot_kuyrugu.pop(index) # Diziden at
            if index == 0: # Eğer silinen şey 0 numara ise (Yani hazırlanan sipariş ise)
                self.timer.stop() # Süreyi durdur
                if self.robot_kuyrugu:
                    self.start_robot_timer() # Yeni sıradakinin süresini başlat
            self.update_robot_queue_ui()

if __name__ == "__main__": # Python dosyasının doğrudan çalıştırıldığını kontrol eden standart yapı
    app = QApplication(sys.argv) # UI motorunu başlatır
    pencere = CoffeeApp() # Ana penceremizi sınıftan yaratır
    pencere.show() # Pencereyi ekranda görünür yapar
    sys.exit(app.exec_()) # Çarpıya basılana kadar programı döngüde tutar
