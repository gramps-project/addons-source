KinshipSort 0.2.8 — dodatek eksperymentalny dla Gramps 6.0.x
Autor: Jacek Kuznia
Kontakt: jacek.kuznia@gmail.com
GitHub: https://github.com/jacek-kuznia
Licencja: GNU GPL w wersji 2 lub dowolnej późniejszej (plik COPYING).

DZIAŁANIE
=========
Dodatek dodaje dwa widoki w kategorii Osoby:
1. Osoby według stopnia pokrewieństwa — lista płaska.
2. Osoby według pokrewieństwa, grupowane — grupowanie według nazwiska.

Punktem odniesienia obliczeń jest Osoba główna drzewa, a nie aktualnie
zaznaczona osoba. Wyniki znajdują się w kolumnie Stopień pokrewieństwa.

ZASADY LICZENIA
===============
Osoba główna ma stopień 0; biologiczny rodzic i dziecko — 1; rodzeństwo,
rodzeństwo przyrodnie, dziadek i wnuk — 2; wuj, ciotka, bratanek i siostrzenica
— 3; kuzyn będący dzieckiem rodzeństwa rodzica — 4.

Liczymy najkrótszą drogę przez wspólnego biologicznego przodka: najpierw
w górę od Osoby głównej, następnie w dół do krewnego. Każda relacja
biologicznego rodzica i dziecka zwiększa stopień o 1. Jedna z części drogi
może mieć długość 0. Przy kilku drogach wybieramy najmniejszy stopień.

Uwzględniamy wyłącznie relacje oznaczone jako urodzenie (Birth). Małżeństwo,
partnerstwo, adopcja, opieka zastępcza i powiązania osobowe nie tworzą
biologicznego pokrewieństwa. Nie dopuszczamy drogi przez wspólne dziecko do
małżonka. Małżonek będący krewnym otrzyma stopień przez wspólnego przodka.

Puste pole oznacza, że zapisane dane nie pozwalają ustalić pokrewieństwa.
Nie dowodzi, że osoby biologicznie nie są spokrewnione. Wynik jest liczbą
kroków genealogicznych, a nie współczynnikiem genetycznym. Bez Osoby głównej
wszystkie stopnie są puste.

SORTOWANIE I KOLUMNY
===================
Kliknięcie nagłówka kolumny wybiera sortowanie; ponowne kliknięcie odwraca
kolejność. Pozostałe kolumny zachowują zwykłe sortowanie Gramps.

Lista płaska rosnąco: stopień, poziom pokoleniowy (wyższy najpierw), alfabet.
Rodzice są przed dziećmi, a dziadkowie przed rodzeństwem, które jest przed
wnukami. Przy równie krótkich drogach wybieramy najwyższy poziom pokoleniowy.

Widok grupowany rosnąco: grupy według najniższego stopnia w grupie, potem
alfabet; osoby w grupie według stopnia i alfabetu. Stopień grupy uwzględnia
również członków ukrytych przez filtr. Przy innej kolumnie grupy są
alfabetyczne, a wybrana kolumna decyduje o kolejności osób w grupie.

Puste stopnie są na końcu przy sortowaniu rosnącym. Sortowanie malejące
odwraca całą kolejność: puste stopnie trafiają na początek, odwracane są
również rozstrzygnięcia remisów i kolejność grup nazwisk.

Kolumna jest początkowo druga, po Nazwie. Można ją przesuwać, zmieniać jej
szerokość i ukrywać w ustawieniach widoku. Po otwarciu widoku sortowanie
początkowe używa pokrewieństwa, gdy kolumna jest widoczna; w przeciwnym
razie używa pierwszej widocznej kolumny.

DANE
====
Stopnie i poziomy pokoleniowe są obliczane w pamięci, bez zapisywania ich
w rekordach genealogicznych. Zwykłe funkcje dodawania i edycji osób pozostają
dostępne i zapisują dane normalnie. Ustawienia widoku również są zapisywane.
Zmiany osób i rodzin mogą wymagać ponownego obliczenia całego drzewa.

INSTALACJA W WINDOWS
===================
1. Zamknij Gramps.
2. Rozpakuj paczkę instalacyjną do katalogu dodatków używanego przez program.
   W Gramps 6.0.8 jest to zwykle %APPDATA%\gramps\gramps60\plugins\.
   Starsza instalacja może używać %LOCALAPPDATA%, a ustawienie GRAMPSHOME
   może zmienić tę lokalizację.
3. Pliki powinny znajdować się bezpośrednio w podkatalogu KinshipSort,
   np. plugins\KinshipSort\KinshipSort.gpr.py. Zachowaj tylko jedną kopię
   dodatku w katalogach skanowanych przez Gramps.
4. Uruchom Gramps, otwórz drzewo, ustaw Osobę główną i wybierz nowy widok.

Paczka instalacyjna zawiera locale\pl\LC_MESSAGES\addon.mo. Paczka źródłowa
zawiera po\pl-local.po i wymaga kompilacji tłumaczenia przed instalacją.

STAN WERSJI 0.2.8
================
Dodano angielskie teksty, polskie tłumaczenie, dokumentację, licencję oraz
informacje o pochodzeniu fragmentów kodu. Wydzielono obliczenia do osobnego
modułu i dodano testy. Zabezpieczono brak bazy oraz odwołanie do nieistniejącej
Osoby głównej. Zachowano algorytm wersji 0.2.7.

Wersja pozostaje eksperymentalna. Testy modeli i obliczeń nie zastępują
sprawdzenia okien, odświeżania po edycji i działania na innych systemach.
Lista prób znajduje się w tests/README.md, historia w CHANGELOG.md.
Dodatek nie został jeszcze przyjęty do oficjalnego repozytorium ani programu.
