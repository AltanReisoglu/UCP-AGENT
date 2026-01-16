# UCP Agent

Google ADK, UCP (Universal Commerce Protocol) ve MCP (Model Context Protocol) ile gelistirilmis alisveris ajansi.

## Ozellikler

- Urun arama ve sepet yonetimi
- MCP sunucusu ile arac entegrasyonu
- Ollama ve Google Gemini destegi
- UCP uyumlu odeme akisi

## Hizli Baslangic

### 1. Bagimliliklari yukleyin

```bash
pip install -e .
```

### 2. Ortam degiskenlerini ayarlayin

`.env` dosyasi olusturun:

```env
# Ollama icin (yerel LLM)
USE_OLLAMA=true
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://localhost:11434

# Google Gemini icin
# USE_OLLAMA=false
# GOOGLE_API_KEY=api_anahtariniz
```

### 3. MCP Sunucusunu baslatin

```bash
python -m app server
```

### 4. Sohbeti baslatin (yeni terminal)

```bash
python -m app chat
```

## CLI Komutlari

| Komut | Aciklama |
|-------|----------|
| `python -m app server` | MCP sunucusunu baslatir |
| `python -m app chat` | Interaktif sohbet |
| `python -m app test` | Sistem testi |
| `python -m app mcp` | MCP baglantisini test eder |

## Proje Yapisi

```
UCP-AGENT/
├── app/                    # CLI uygulamasi
│   ├── cmd.py             # CLI komutlari
│   └── __main__.py        # Giris noktasi
├── backend/
│   ├── host_agent/        # Ajan mantigi
│   │   ├── agent.py       # Ajan tanimi
│   │   └── agent_executor.py
│   ├── mcp_server/        # MCP sunucusu
│   │   ├── streamable_http_server.py
│   │   ├── mcp_adapter.py
│   │   └── mcp_config.json
│   ├── store.py           # Magaza mantigi
│   └── mock_datas/        # Ornek veriler
├── sdk/                   # UCP SDK
├── pyproject.toml         # Proje bagimliliklari
└── .env                   # Yapilandirma
```

## MCP Araclari

- `search_products` - Katalogda arama yapar
- `get_product` - Urun detaylarini getirir
- `create_checkout` - Yeni sepet olusturur
- `get_checkout` - Sepet durumunu gosterir
- `update_checkout` - Sepeti gunceller
- `complete_checkout` - Siparisi tamamlar
- `cancel_checkout` - Sepeti iptal eder

## Ornek Kullanim

```
Sen: chips ara
Ajan: 2 urun bulundu: Classic Potato Chips ($3.79), Baked Sweet Potato Chips ($4.79)

Sen: 2 adet classic chips al
Ajan: 2x Classic Potato Chips ile sepet olusturuldu. Toplam: $7.58

Sen: siparisi tamamla
Ajan: Siparis tamamlandi! Siparis ID: ORD-12345
```

## Lisans

Apache 2.0
