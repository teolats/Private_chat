# Private Chat: ένας server, πολλοί clients, επιλογή παραλήπτη

Chat πάνω σε TCP sockets (Python, μόνο standard library). Ένας server δέχεται πολλούς clients ταυτόχρονα. Κάθε client διαλέγει **σε ποιον ή σε ποιους** θα πάει κάθε μήνυμά του.

Βασίζεται στα `multi_client_chat_server.py` / `multi_client_chat_client.py` του μαθήματος.

---

## Αρχεία

| Αρχείο | Ρόλος |
|---|---|
| `private_chat_server.py` | Ο server. Κρατά λίστα συνδεδεμένων χρηστών και δρομολογεί κάθε μήνυμα μόνο στους παραλήπτες που επέλεξε ο αποστολέας. |
| `private_chat_client.py` | Ο client (full-duplex): ένα thread λαμβάνει, το κύριο thread διαβάζει από το πληκτρολόγιο και στέλνει. |
| `test_private_chat.py` | Αυτοματοποιημένο τεστ: ξεκινά τον server, συνδέει 3 clients και ελέγχει τη δρομολόγηση. |

Απαιτήσεις: **Python 3.8+**. Δεν χρειάζεται `pip install`.

---

## Εκτέλεση

**Terminal 1: server**
```bash
python3 private_chat_server.py                 # 127.0.0.1:5000
python3 private_chat_server.py --port 6000     # άλλη πόρτα
python3 private_chat_server.py --host 0.0.0.0  # δεκτές συνδέσεις και από το LAN
```

**Terminal 2, 3, 4…: clients**
```bash
python3 private_chat_client.py alice
python3 private_chat_client.py bob
python3 private_chat_client.py carol
python3 private_chat_client.py                 # ζητά όνομα κατά τη σύνδεση
python3 private_chat_client.py dave --host 192.168.1.10 --port 5000
```

**Τεστ**
```bash
python3 test_private_chat.py
```

---

## Εντολές του client

| Πληκτρολογείς | Τι γίνεται |
|---|---|
| `@bob γεια` | Ιδιωτικό μήνυμα **μόνο** στον bob |
| `@bob,carol γεια` | Μήνυμα σε **πολλούς** παραλήπτες *(bonus)* |
| `@bob @carol γεια` | Το ίδιο με το παραπάνω (εναλλακτική σύνταξη) |
| `/to bob,carol` | Ορίζει **προεπιλεγμένους παραλήπτες**: ό,τι γράφεις χωρίς `@` πάει σε αυτούς |
| `/to` | Δείχνει τους τρέχοντες προεπιλεγμένους παραλήπτες |
| `/clear` | Καθαρίζει τους προεπιλεγμένους παραλήπτες |
| `/all γεια σε όλους` | Broadcast σε όλους (η παλιά συμπεριφορά) |
| `/list` | Ποιοι είναι online |
| `/help` | Βοήθεια |
| `quit` | Αποσύνδεση |

Τα ονόματα **δεν** κάνουν διάκριση πεζών/κεφαλαίων (`@Bob` = `@bob`).

---

## Παράδειγμα συνεδρίας

**alice**
```
> @bob,carol meeting στις 5;
[sent to bob, carol]
> @dave hello
[!] Not online: dave
[!] Message not delivered (no valid recipients).
```

**bob**
```
[alice -> you, carol] meeting στις 5;
> /to alice
Default recipients set to: alice - plain messages now go to them.
> ναι, εντάξει
[sent to alice]
```

**carol**
```
[alice -> you, bob] meeting στις 5;
```
Η carol **δεν** βλέπει την απάντηση του bob, γιατί πήγε μόνο στην alice.

---

## Πρωτόκολλο (σε επίπεδο TCP)

- Κάθε μήνυμα είναι **μία γραμμή κειμένου UTF-8 που τελειώνει σε `\n`**. Με αυτό λύνεται το πρόβλημα framing του TCP stream: δύο μηνύματα δεν «κολλάνε» μεταξύ τους και ένα μήνυμα δεν «σπάει» στα δύο.
- Ροή σύνδεσης:
  1. Ο server στέλνει `Enter your name:`.
  2. Ο client στέλνει όνομα. Αν είναι πιασμένο ή άκυρο, ο server ξαναρωτάει.
  3. Ο server στέλνει `Welcome …` και τη λίστα online χρηστών, και ενημερώνει τους υπόλοιπους (`*** X has joined ***`).
  4. Από εκεί και πέρα κάθε γραμμή του client ερμηνεύεται από τον server ως εντολή (`/…`), ως μήνυμα με παραλήπτες (`@…`) ή ως απλό κείμενο προς τους προεπιλεγμένους παραλήπτες.
- Μορφή μηνύματος που λαμβάνει ο παραλήπτης: `[αποστολέας -> you, άλλοι_παραλήπτες] κείμενο`
- Ο αποστολέας λαμβάνει αναφορά παράδοσης: `[sent to …]` ή `[!] Not online: …`.

Η επιλογή παραλήπτη γίνεται **στον server**, άρα και ένας «χαζός» client (π.χ. `nc 127.0.0.1 5000` ή telnet) μπορεί να συμμετέχει στο chat.

---

## Γνωστοί περιορισμοί

- Αν φτάσει μήνυμα ενώ γράφεις, η γραμμή που πληκτρολογείς «χαλάει» οπτικά (το ίδιο συμβαίνει και στα αρχικά παραδείγματα). Αυτό που στέλνεται δεν επηρεάζεται.
- Δεν υπάρχει κρυπτογράφηση ούτε authentication: ο server βλέπει όλα τα μηνύματα και τα καταγράφει στο log του.
- Τα μηνύματα δεν αποθηκεύονται: αν ο παραλήπτης είναι offline, το μήνυμα δεν παραδίδεται και ο αποστολέας ενημερώνεται.
