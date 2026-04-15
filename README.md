# 📄 Invoice Duplicate Detector — WhatsApp

Système de détection de doublons de factures via WhatsApp Business API.  
Construit avec **FastAPI**, **SQLAlchemy** et **pdfplumber**.

---

## 🏗️ Architecture du projet

```
invoice-detector/
├── app/
│   ├── main.py                        # Point d'entrée FastAPI
│   ├── config.py                      # Configuration (variables d'env)
│   ├── database.py                    # Moteur SQLAlchemy & session
│   ├── schemas.py                     # Schémas Pydantic (validation)
│   ├── models/
│   │   └── invoice.py                 # Modèle SQLAlchemy Invoice
│   ├── repositories/
│   │   └── invoice_repository.py      # Couche d'accès aux données
│   ├── services/
│   │   └── invoice_service.py         # Logique métier (orchestration)
│   ├── routes/
│   │   ├── webhook.py                 # Endpoints /webhook (GET + POST)
│   │   └── health.py                  # /health + /invoices
│   └── utils/
│       ├── pdf_utils.py               # Hash SHA-256 + extraction PDF
│       └── whatsapp_client.py         # Client WhatsApp Business API
├── tests/
│   └── test_invoice_system.py         # Tests unitaires complets
├── scripts/
│   └── test_webhook.sh                # Script de test cURL
├── examples/
│   └── webhook_payload_example.json   # Exemple de payload WhatsApp
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
├── .env.example
└── README.md
```

---

## 🔁 Workflow fonctionnel

```
WhatsApp User
     │
     │  1. Envoie une facture PDF
     ▼
WhatsApp Business API
     │
     │  2. Webhook POST /webhook
     ▼
Invoice Detector API
     │
     ├─ 3. Téléchargement du PDF (WhatsApp Media API)
     ├─ 4. Calcul du hash SHA-256
     ├─ 5. Extraction des données (invoice_id, montant, date)
     ├─ 6. Vérification doublon (contrainte UNIQUE en base)
     │
     ├─ ✅ Nouvelle facture → Enregistrement + réponse "Facture valide"
     └─ ❌ Doublon détecté  → Réponse "Facture déjà utilisée"
```

---

## ⚙️ Installation

### Prérequis

- Python 3.11+
- pip

### 1. Cloner et configurer

```bash
git clone <repo>
cd invoice-detector

# Créer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

# Installer les dépendances
pip install -r requirements.txt
```

### 2. Variables d'environnement

```bash
cp .env.example .env
```

Éditer `.env` avec vos valeurs :

| Variable                  | Description                                      | Défaut                              |
|---------------------------|--------------------------------------------------|-------------------------------------|
| `APP_ENV`                 | Environnement (`development` / `production`)     | `development`                       |
| `DATABASE_URL`            | URL de connexion SQLAlchemy                      | `sqlite:///./invoices.db`           |
| `WHATSAPP_API_URL`        | URL de base de l'API WhatsApp                    | `https://graph.facebook.com/v18.0`  |
| `WHATSAPP_PHONE_NUMBER_ID`| ID du numéro de téléphone WhatsApp Business      | _(requis en production)_            |
| `WHATSAPP_ACCESS_TOKEN`   | Token d'accès Meta                               | _(requis en production)_            |
| `WHATSAPP_VERIFY_TOKEN`   | Token de vérification du webhook                 | `invoice_detector_verify_token`     |
| `MAX_PDF_SIZE_MB`         | Taille maximale d'un PDF (en Mo)                 | `10`                                |
| `LOG_TO_FILE`             | Écrire les logs dans `logs/app.log`              | `false`                             |

### 3. Lancer en développement

```bash
mkdir -p logs
uvicorn app.main:app --reload --port 8000
```

L'API est disponible sur : http://localhost:8000  
Documentation Swagger : http://localhost:8000/docs

---

## 🐳 Lancement avec Docker

```bash
# Lancer l'API + PostgreSQL
docker-compose up --build

# En arrière-plan
docker-compose up -d --build

# Arrêter
docker-compose down
```

---

## 🗄️ Schéma de base de données

```sql
CREATE TABLE invoices (
    id           INTEGER      PRIMARY KEY AUTOINCREMENT,
    invoice_id   VARCHAR(100) NOT NULL UNIQUE,   -- Identifiant métier
    amount       NUMERIC(12,2) NOT NULL,          -- Montant
    invoice_date DATE         NOT NULL,           -- Date de la facture
    pdf_hash     VARCHAR(64)  NOT NULL UNIQUE,    -- SHA-256 du PDF
    status       VARCHAR(20)  NOT NULL DEFAULT 'valid',  -- valid | duplicate
    sender_phone VARCHAR(20),                     -- Numéro WhatsApp expéditeur
    created_at   TIMESTAMP    NOT NULL DEFAULT now()
);
```

Les contraintes `UNIQUE` sur `invoice_id` et `pdf_hash` garantissent l'intégrité
des données même en cas de requêtes concurrentes.

---

## 🧪 Lancer les tests

```bash
pytest -v
```

Résultats attendus :

```
tests/test_invoice_system.py::TestPdfUtils::test_compute_sha256_retourne_64_chars  PASSED
tests/test_invoice_system.py::TestPdfUtils::test_parse_invoice_data_texte_complet  PASSED
tests/test_invoice_system.py::TestInvoiceRepository::test_create_nouvelle_facture  PASSED
tests/test_invoice_system.py::TestInvoiceRepository::test_create_doublon_invoice_id PASSED
tests/test_invoice_system.py::TestWebhookRoutes::test_verify_webhook_valide        PASSED
... (15 tests au total)
```

---

## 🔌 Tester le webhook manuellement

### Avec le script bash inclus

```bash
chmod +x scripts/test_webhook.sh
bash scripts/test_webhook.sh
```

### Avec cURL directement

**Vérification du webhook (GET) :**
```bash
curl "http://localhost:8000/webhook?hub.mode=subscribe&hub.verify_token=invoice_detector_verify_token&hub.challenge=test123"
```

**Simuler la réception d'une facture PDF (POST) :**
```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d @examples/webhook_payload_example.json
```

**Lister les factures enregistrées :**
```bash
curl http://localhost:8000/invoices
```

---

## 🌐 Exposer le webhook localement (ngrok)

Pour tester avec l'API WhatsApp réelle :

```bash
# Installer ngrok : https://ngrok.com
ngrok http 8000
```

Copier l'URL HTTPS générée (ex: `https://abc123.ngrok.io`) et la configurer
comme URL de webhook dans le tableau de bord Meta for Developers.

---

## 📋 Format des factures PDF supportées

Le parser reconnaît automatiquement les formats suivants :

**Numéro de facture :**
- `Facture N° : INV-2024-001`
- `Invoice #: 12345`
- `N° facture : FAC-001`

**Montant :**
- `Total : 1 250,00`
- `Montant TTC : 500.00`
- `Amount Due: 1,234.56`

**Date :**
- `15/01/2024` ou `15-01-2024`
- `2024-01-15`
- `15 janvier 2024` / `15 January 2024`

---

## 🚀 Évolutions possibles

- **File d'attente** : Intégrer Celery + Redis pour traitement asynchrone
- **OCR** : Ajouter Tesseract pour les PDFs scannés (images)
- **Multi-tenant** : Support de plusieurs entreprises
- **Dashboard** : Interface web de consultation des factures
- **Alertes** : Notifications email/Slack lors de détection de doublons
