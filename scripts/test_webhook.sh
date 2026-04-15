#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Script de test manuel du webhook
# Usage : bash scripts/test_webhook.sh
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL="${BASE_URL:-http://localhost:8000}"
VERIFY_TOKEN="${WHATSAPP_VERIFY_TOKEN:-invoice_detector_verify_token}"

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Invoice Detector — Tests Webhook                ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}\n"

# ── 1. Health check ──────────────────────────────────────────────────────────
echo -e "${BLUE}[1/5] Health check...${NC}"
curl -s "${BASE_URL}/health" | python3 -m json.tool
echo ""

# ── 2. Vérification webhook (GET) ────────────────────────────────────────────
echo -e "${BLUE}[2/5] Vérification du webhook (challenge/response)...${NC}"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  "${BASE_URL}/webhook?hub.mode=subscribe&hub.verify_token=${VERIFY_TOKEN}&hub.challenge=test_challenge_123")
if [ "$RESPONSE" -eq 200 ]; then
  echo -e "${GREEN}✅ Vérification réussie (HTTP 200)${NC}"
else
  echo -e "${RED}❌ Échec de la vérification (HTTP ${RESPONSE})${NC}"
fi
echo ""

# ── 3. Token invalide ────────────────────────────────────────────────────────
echo -e "${BLUE}[3/5] Test token invalide (doit retourner 403)...${NC}"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  "${BASE_URL}/webhook?hub.mode=subscribe&hub.verify_token=mauvais_token&hub.challenge=abc")
if [ "$RESPONSE" -eq 403 ]; then
  echo -e "${GREEN}✅ Token invalide correctement rejeté (HTTP 403)${NC}"
else
  echo -e "${RED}❌ Comportement inattendu (HTTP ${RESPONSE})${NC}"
fi
echo ""

# ── 4. Webhook avec message document PDF ────────────────────────────────────
echo -e "${BLUE}[4/5] Envoi d'un message document PDF (simulé)...${NC}"
curl -s -X POST "${BASE_URL}/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "33612345678",
            "type": "document",
            "document": {
              "id": "media_test_001",
              "filename": "facture_test.pdf",
              "mime_type": "application/pdf"
            }
          }]
        }
      }]
    }]
  }' | python3 -m json.tool
echo ""

# ── 5. Webhook avec message texte (doit être ignoré) ────────────────────────
echo -e "${BLUE}[5/5] Envoi d'un message texte (doit être ignoré)...${NC}"
curl -s -X POST "${BASE_URL}/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "33612345678",
            "type": "text",
            "text": { "body": "Bonjour" }
          }]
        }
      }]
    }]
  }' | python3 -m json.tool
echo ""

# ── 6. Liste des factures ────────────────────────────────────────────────────
echo -e "${BLUE}[Bonus] Liste des factures enregistrées...${NC}"
curl -s "${BASE_URL}/invoices" | python3 -m json.tool
echo ""

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   Tests terminés !${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"