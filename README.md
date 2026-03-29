# 🚒 OSP Logbook

![Wersja](https://imgshields.io/badge/Wersja-2.0-ff6b3d)
![Stos technologiczny](https://img.shields.io/badge/Tech-Python%20%7C%20Flask%20%7C%20SQLite-blue)
![Licencja](https://img.shields.io/badge/Licencja-MIT-success)

**OSP Logbook** to szybki, nowoczesny i niezależny dziennik pojazdów stworzony z myślą o jednostkach Ochotniczej Straży Pożarnej (OSP). Aplikacja została zaprojektowana w podejściu *Mobile-First*, co pozwala na błyskawiczne wypełnianie ewidencji na telefonach komórkowych, bezpośrednio po powrocie z ciężkiej akcji.

Całość działa w 100% lokalnie. **Nie wymaga dostępu do Internetu**, nie pobiera zewnętrznych bibliotek (zero CDN), nie używa zewnętrznych fontów. Dzięki temu idealnie sprawdza się w zamkniętych, remizowych sieciach LAN (np. na starych routerach bez wyjścia na świat).

---

## ✨ Kluczowe funkcje

- **Ewidencja Wyjazdów**: Błyskawiczny zapis celu (akcja, ćwiczenia, gospodarcze), kierowcy i stanu licznika. Inteligentne podpowiedzi ostatniego przebiegu pojazdu.
- **Ewidencja Paliwowa**: Śledzenie ilości tankowanego paliwa oraz kosztów przypisanych do konkretnych wozów bojowych.
- **Książka Serwisowa**: Rejestrowanie przeglądów, napraw i awarii ułatwiające terminową konserwację sprzętu.
- **Raporty Miesięczne**: Generowanie czytelnych, zbiorczych podsumowań ze wszystkich pojazdów z opcją łatwego wydruku (A4/@media print) w celu rozliczeń z gminą.
- **Dark Mode**: Jednorodny, ciemny motyw o wysokim kontraście, specjalnie dostosowany do warunków nocnych – nie oślepia kierowców i ratowników 🖤.
- **Błyskawiczny UX**: W pełni autorskie, responsywne powiadomienia Toast, natywny HTML `<datalist>` uczący się wpisywanych kierowców (z ostatnich 90 dni) i gigantyczne, wygodne dla palców (nawet w rękawicach!) przyciski.

---

## 🚀 Szybki Start

Do uruchomienia aplikacji potrzebujesz **Python 3.8+**.

```bash
# 1. Sklonuj repozytorium
git clone https://github.com/TWOJ_NICK/osp-logbook.git
cd osp-logbook

# 2. Zainstaluj zależności
pip install -r requirements.txt

# 3. Uruchom serwer testowo (nasłuchuje na 0.0.0.0:5000)
python app.py
```

Po uruchomieniu, otwórz w przeglądarce: `http://localhost:5000` LUB `http://TWOJ_ADRES_IP:5000`

🔐 **Konto domyślne**: `admin`  
🔑 **Hasło**: `admin123`  
*(Koniecznie zmień hasło po pierwszym zalogowaniu w zakładce Użytkownicy!)*

---

## 🔒 Bezpieczeństwo i Produkcja (LAN)

Zalecane jest uruchomienie z flagą wymuszającą obsługę ruchu szyfrowanego **HTTPS**. Bez tego niektóre nowoczesne telefony komórkowe mogą blokować bezpieczne funkcje przeglądarki (np. zapamiętywanie haseł).

```bash
OSP_USE_HTTPS=1 python app.py
```

*Aplikacja (korzystając z biblioteki Werkzeug) spróbuje wygenerować certyfikaty ad-hoc. Możesz także podpiąć swoje własne podpisane certyfikaty lokalne:*

```bash
OSP_USE_HTTPS=1 OSP_SSL_CERT=cert.pem OSP_SSL_KEY=key.pem python app.py
```

Zmiana domyślnego portu 5000:
```bash
PORT=8080 python app.py
```

---

## 🐧 Uruchamianie przy starcie (Linux / Raspberry Pi)

Plik konfiguracyjny dla demona `systemd`, dzięki któremu dziennik będzie uruchamiał się samoczynnie wraz ze startem serwera/komputera w remizie.

Utwórz plik `/etc/systemd/system/osp-logbook.service`:

```ini
[Unit]
Description=OSP Logbook (Dziennik Pojazdow)
After=network.target

[Service]
User=pi
WorkingDirectory=/opt/osp_logbook
ExecStart=/usr/bin/python3 /opt/osp_logbook/app.py
Environment="OSP_USE_HTTPS=1"
Environment="PORT=443"
Restart=always

[Install]
WantedBy=multi-user.target
```

Następnie aktywuj:
```bash
sudo systemctl enable osp-logbook
sudo systemctl start osp-logbook
```

---

## 🛠 Stos Technologiczny (Tech Stack)

*   **Backend:** Python 3 + Flask + Werkzeug
*   **Baza danych:** SQLite3 (Wszystkie dane znajdują się w jednym pliku `logbook.db` - jego przekopiowanie to najprostszy backup na świecie!)
*   **Frontend:** HTML5 + Vanilla JS + Jinja2 (Zero frameworków typu React, zero Tailwind, zero zewnętrznych czcionek).

---

## 🤝 Kontrybucje

Pull Requesty są mile widziane! Aplikacja służy dobru publicznemu i ułatwia służbę – jeśli potrafisz dodać nowe funkcjonalności (np. moduł magazynu sprzętu, wyliczanie zużycia normatywnego), śmiało twórz *forka* i dziel się kodem.

---

## 📜 Licencja

Projekt dystrybuowany na licencji **[MIT](https://choosealicense.com/licenses/mit/)**.  
Możesz swobodnie kopiować, modyfikować i używać tego kodu – zarówno prywatnie jak i publicznie, z zachowaniem informacji o oryginalnym autorze. Mamy nadzieję, że oprogramowanie ułatwi codzienną służbę Twojej jednostce!
