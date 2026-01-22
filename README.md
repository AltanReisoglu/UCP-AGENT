# UCP-AGENT

[![PyPI version](https://badge.fury.io/py/ucp-agent.svg)](https://badge.fury.io/py/ucp-agent)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Universal Commerce Protocol (UCP)** reference implementation for AI-powered shopping agents.

UCP enables AI agents to securely make purchases on behalf of users through a standardized protocol that works with any merchant, any payment provider, and any AI platform.

## ✨ Features

- 🛒 **Shopping Agent** - AI-powered product search, cart management, and checkout
- 🔌 **MCP Server** - Model Context Protocol tools for LLM integration
- 🖼️ **Embedded Checkout** - Embeddable checkout UI with JSON-RPC 2.0 messaging
- 🔐 **AP2 Mandates** - Cryptographic signatures (ES256) for secure transactions
- 📜 **Buyer Consent** - GDPR/CCPA compliant consent management
- 🏷️ **Discounts** - Promo codes and automatic discounts
- 📦 **Fulfillment** - Shipping and pickup options
- 🤖 **LLM Support** - Works with Ollama, OpenAI, Google Gemini

## 🚀 Quick Start

### Installation

```bash
pip install ucp-agent
```

### One-Command Launch

```bash
ucp-agent run
```

This starts the MCP server and opens an interactive chat with the shopping agent.

### Or step by step:

```bash
# Start MCP server
ucp-agent server

# In another terminal, start chat
ucp-agent chat
```

## 📖 Usage

### CLI Commands

| Command | Description |
|---------|-------------|
| `ucp-agent run` | Start server + chat in one command |
| `ucp-agent server` | Start MCP server only |
| `ucp-agent chat` | Start interactive chat |
| `ucp-agent test` | Run system tests |

### Example Conversation

```
You: search for chips
Agent: Found 2 products: Classic Potato Chips ($3.79), Baked Sweet Potato Chips ($4.79)

You: buy 2 classic chips  
Agent: Created checkout with 2x Classic Potato Chips. Total: $7.58

You: complete the order
Agent: Order completed! Order ID: ORD-12345
```

### MCP Tools

The following tools are available for LLM integration:

| Tool | Description |
|------|-------------|
| `search_products` | Search product catalog |
| `get_product` | Get product details |
| `create_checkout` | Create new checkout session |
| `get_checkout` | Get checkout status |
| `update_checkout` | Update buyer/shipping info |
| `complete_checkout` | Complete the order |
| `cancel_checkout` | Cancel checkout |
| `ep_binding` | Get embedded checkout URL |

## ⚙️ Configuration

Create a `.env` file:

```env
# For Ollama (local LLM, free)
USE_OLLAMA=true
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://localhost:11434

# For OpenAI
# USE_OLLAMA=false
# OPENAI_API_KEY=your-api-key

# For Google Gemini
# USE_OLLAMA=false
# GOOGLE_API_KEY=your-api-key
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│              AI Platform (Host)                  │
│         (Claude, ChatGPT, Custom Agent)          │
└─────────────────────┬───────────────────────────┘
                      │ MCP Protocol
                      ▼
┌─────────────────────────────────────────────────┐
│               UCP-AGENT Server                   │
│  ┌─────────────────────────────────────────┐    │
│  │           Transport Bindings             │    │
│  │  • MCP (Tools)  • A2A  • EP (Embedded)  │    │
│  └─────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────┐    │
│  │              Extensions                  │    │
│  │  • Fulfillment  • AP2 Mandates          │    │
│  │  • Buyer Consent  • Discounts           │    │
│  └─────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────┐    │
│  │            Retail Store                  │    │
│  │  • Products  • Checkouts  • Orders      │    │
│  └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

## 🔌 UCP Protocol Extensions

| Extension | Description |
|-----------|-------------|
| **Checkout** | Core checkout capability |
| **Fulfillment** | Shipping/pickup options |
| **AP2 Mandates** | Cryptographic transaction signing |
| **Buyer Consent** | Privacy consent (GDPR/CCPA) |
| **Discounts** | Promo codes and automatic discounts |
| **EP Binding** | Embedded checkout protocol |

## 📁 Project Structure

```
ucp-agent/
├── app/                     # CLI application
│   ├── cmd.py              # CLI commands
│   └── __main__.py
├── backend/
│   ├── mcp_server/         # MCP server implementation
│   ├── host_agent/         # Shopping agent logic
│   ├── store.py            # Retail store simulation
│   ├── embedded_checkout.py # EP Binding
│   ├── ap2_mandates.py     # Cryptographic signing
│   ├── buyer_consent.py    # Consent management
│   ├── discount.py         # Discount handling
│   └── mock_datas/         # Sample data
├── sdk/                     # UCP SDK
├── run.py                   # Single-command launcher
└── pyproject.toml
```

## 🔗 Related Links

- [UCP Specification](https://ucp.dev/specification/)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [AP2 Protocol](https://ap2-protocol.org/)

## 📄 License

Apache 2.0 - See [LICENSE](LICENSE) for details.

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

---

**Built with ❤️ for the future of AI commerce**
