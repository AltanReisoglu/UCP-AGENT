# Copyright 2026 UCP Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
FastAPI Routes for Embedded Checkout

Provides HTTP endpoints for serving the embedded checkout UI and handling
checkout-related actions.
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional
import logging
import os

from .embedded_checkout import (
    create_embedded_checkout_session,
    EP_VERSION,
    SUPPORTED_DELEGATIONS,
)
from .store import RetailStore

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/embedded-checkout", tags=["Embedded Checkout"])

# Store instance (shared with MCP server)
store = RetailStore()


def get_checkout_html_template() -> str:
    """Read the embedded checkout HTML template."""
    template_path = os.path.join(
        os.path.dirname(__file__),
        "templates",
        "embedded_checkout.html"
    )
    
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    
    # Fallback to inline template if file doesn't exist
    return get_inline_checkout_template()


def get_inline_checkout_template() -> str:
    """Return inline HTML template for embedded checkout."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Checkout - {{ merchant_name }}</title>
    <style>
        :root {
            --primary-color: #6366f1;
            --primary-hover: #4f46e5;
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --border-color: #e2e8f0;
            --success-color: #10b981;
            --error-color: #ef4444;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: var(--bg-color);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 20px;
        }
        
        .checkout-container {
            max-width: 600px;
            margin: 0 auto;
        }
        
        .checkout-header {
            text-align: center;
            margin-bottom: 24px;
        }
        
        .checkout-header h1 {
            font-size: 24px;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .checkout-status {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            text-transform: uppercase;
            margin-top: 8px;
        }
        
        .status-incomplete { background: #fef3c7; color: #92400e; }
        .status-ready { background: #d1fae5; color: #065f46; }
        .status-completed { background: #dbeafe; color: #1e40af; }
        .status-canceled { background: #fee2e2; color: #991b1b; }
        
        .card {
            background: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            padding: 20px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        
        .card-title {
            font-size: 14px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 16px;
        }
        
        .line-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid var(--border-color);
        }
        
        .line-item:last-child { border-bottom: none; }
        
        .item-info {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .item-image {
            width: 60px;
            height: 60px;
            border-radius: 8px;
            object-fit: cover;
            background: var(--bg-color);
        }
        
        .item-details h3 {
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 4px;
        }
        
        .item-details .quantity {
            font-size: 13px;
            color: var(--text-secondary);
        }
        
        .item-price {
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .totals {
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid var(--border-color);
        }
        
        .total-row {
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            font-size: 14px;
        }
        
        .total-row.final {
            font-size: 18px;
            font-weight: 600;
            padding-top: 12px;
            margin-top: 8px;
            border-top: 2px solid var(--border-color);
        }
        
        .form-group {
            margin-bottom: 16px;
        }
        
        .form-group label {
            display: block;
            font-size: 13px;
            font-weight: 500;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }
        
        .form-group input {
            width: 100%;
            padding: 12px;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.2s;
        }
        
        .form-group input:focus {
            outline: none;
            border-color: var(--primary-color);
        }
        
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        
        .btn {
            display: block;
            width: 100%;
            padding: 14px 24px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .btn-primary {
            background: var(--primary-color);
            color: white;
        }
        
        .btn-primary:hover {
            background: var(--primary-hover);
        }
        
        .btn-primary:disabled {
            background: var(--text-secondary);
            cursor: not-allowed;
        }
        
        .btn-secondary {
            background: transparent;
            color: var(--text-secondary);
            border: 1px solid var(--border-color);
            margin-top: 12px;
        }
        
        .btn-secondary:hover {
            background: var(--bg-color);
        }
        
        .messages {
            margin-bottom: 16px;
        }
        
        .message {
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 8px;
        }
        
        .message-error {
            background: #fef2f2;
            color: var(--error-color);
            border: 1px solid #fecaca;
        }
        
        .message-info {
            background: #eff6ff;
            color: #1d4ed8;
            border: 1px solid #bfdbfe;
        }
        
        .success-container {
            text-align: center;
            padding: 40px 20px;
        }
        
        .success-icon {
            width: 64px;
            height: 64px;
            background: var(--success-color);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 20px;
        }
        
        .success-icon svg {
            width: 32px;
            height: 32px;
            color: white;
        }
        
        .order-id {
            font-family: monospace;
            background: var(--bg-color);
            padding: 8px 16px;
            border-radius: 4px;
            margin-top: 12px;
            display: inline-block;
        }
        
        #debug-panel {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: #1e293b;
            color: #e2e8f0;
            max-height: 200px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 11px;
            padding: 8px;
            display: none;
        }
        
        #debug-panel.active { display: block; }
        
        .debug-message {
            padding: 4px 0;
            border-bottom: 1px solid #334155;
        }
        
        .debug-sent { color: #a78bfa; }
        .debug-received { color: #34d399; }
    </style>
</head>
<body>
    <div class="checkout-container" id="checkout-app">
        <!-- Content will be rendered by JavaScript -->
        <div class="checkout-header">
            <h1>Loading checkout...</h1>
        </div>
    </div>
    
    <div id="debug-panel"></div>
    
    <script>
    // ========================================================================
    // Embedded Checkout Protocol Client
    // ========================================================================
    
    const EmbeddedCheckout = {
        // Configuration
        config: {
            checkoutId: '{{ checkout_id }}',
            version: '{{ ec_version }}',
            delegations: {{ delegations | tojson }},
            debug: true,
        },
        
        // State
        state: {
            checkout: {{ checkout | tojson }},
            isReady: false,
            isCompleted: false,
            messagePort: null,
            pendingRequests: {},
        },
        
        // Initialize the embedded checkout
        init() {
            this.log('Initializing Embedded Checkout Protocol');
            this.setupCommunication();
            this.render();
            this.sendReady();
        },
        
        // Set up communication channels
        setupCommunication() {
            // For native hosts
            window.EmbeddedCheckoutProtocol = {
                postMessage: (message) => this.handleMessage(message)
            };
            
            // For web hosts via postMessage
            window.addEventListener('message', (event) => {
                // Validate origin in production
                this.handleMessage(event.data);
            });
        },
        
        // Send message to host
        sendToHost(message) {
            const jsonMessage = typeof message === 'string' ? message : JSON.stringify(message);
            this.debugLog('sent', JSON.parse(jsonMessage));
            
            // Use MessagePort if available (upgraded channel)
            if (this.state.messagePort) {
                this.state.messagePort.postMessage(jsonMessage);
                return;
            }
            
            // For native hosts
            if (window.EmbeddedCheckoutProtocolConsumer) {
                window.EmbeddedCheckoutProtocolConsumer.postMessage(jsonMessage);
                return;
            }
            
            // WebKit message handler for iOS
            if (window.webkit?.messageHandlers?.EmbeddedCheckoutProtocolConsumer) {
                window.webkit.messageHandlers.EmbeddedCheckoutProtocolConsumer.postMessage(jsonMessage);
                return;
            }
            
            // For web hosts
            if (window.parent !== window) {
                window.parent.postMessage(jsonMessage, '*');
            }
        },
        
        // Handle incoming message
        handleMessage(data) {
            try {
                const message = typeof data === 'string' ? JSON.parse(data) : data;
                this.debugLog('received', message);
                
                // Handle response to our request
                if (message.id && this.state.pendingRequests[message.id]) {
                    const { resolve, reject } = this.state.pendingRequests[message.id];
                    delete this.state.pendingRequests[message.id];
                    
                    if (message.error) {
                        reject(message.error);
                    } else {
                        resolve(message.result || {});
                    }
                    return;
                }
                
                // Handle ec.ready response (special case - it's a response to our request)
                if (message.result !== undefined && !this.state.isReady) {
                    this.handleReadyResponse(message);
                    return;
                }
            } catch (e) {
                this.log('Error handling message:', e);
            }
        },
        
        // Send ec.ready request
        sendReady() {
            const request = {
                jsonrpc: '2.0',
                id: this.generateId(),
                method: 'ec.ready',
                params: {
                    delegate: this.config.delegations
                }
            };
            
            this.state.pendingRequests[request.id] = {
                resolve: (result) => this.handleReadyResponse({ id: request.id, result }),
                reject: (error) => this.log('ec.ready rejected:', error)
            };
            
            this.sendToHost(request);
        },
        
        // Handle ec.ready response
        handleReadyResponse(response) {
            this.state.isReady = true;
            const result = response.result || {};
            
            // Handle channel upgrade
            if (result.upgrade?.port) {
                this.state.messagePort = result.upgrade.port;
                this.log('Communication channel upgraded');
                // Re-send ec.ready on upgraded channel
                this.sendReady();
                return;
            }
            
            // Handle checkout state from host
            if (result.checkout) {
                if (result.checkout.payment?.instruments) {
                    this.state.checkout.payment = {
                        ...this.state.checkout.payment,
                        ...result.checkout.payment
                    };
                }
            }
            
            this.log('Handshake complete, sending ec.start');
            this.sendStart();
        },
        
        // Send ec.start notification
        sendStart() {
            this.sendToHost({
                jsonrpc: '2.0',
                method: 'ec.start',
                params: {
                    checkout: this.state.checkout
                }
            });
        },
        
        // Send ec.complete notification
        sendComplete() {
            this.state.isCompleted = true;
            this.sendToHost({
                jsonrpc: '2.0',
                method: 'ec.complete',
                params: {
                    checkout: this.state.checkout
                }
            });
        },
        
        // Send state change notification
        sendStateChange(changeType) {
            this.sendToHost({
                jsonrpc: '2.0',
                method: `ec.${changeType}.change`,
                params: {
                    checkout: this.state.checkout
                }
            });
        },
        
        // Request payment credential (delegation)
        async requestPaymentCredential() {
            if (!this.config.delegations.includes('payment.credential')) {
                return null;
            }
            
            const request = {
                jsonrpc: '2.0',
                id: this.generateId(),
                method: 'ec.payment.credential_request',
                params: {
                    checkout: this.state.checkout
                }
            };
            
            return new Promise((resolve, reject) => {
                this.state.pendingRequests[request.id] = { resolve, reject };
                this.sendToHost(request);
                
                // Timeout after 5 minutes
                setTimeout(() => {
                    if (this.state.pendingRequests[request.id]) {
                        delete this.state.pendingRequests[request.id];
                        reject({ code: -32001, message: 'Request timeout' });
                    }
                }, 300000);
            });
        },
        
        // Request address change (delegation)
        async requestAddressChange() {
            if (!this.config.delegations.includes('fulfillment.address_change')) {
                return null;
            }
            
            const request = {
                jsonrpc: '2.0',
                id: this.generateId(),
                method: 'ec.fulfillment.address_change_request',
                params: {
                    checkout: this.state.checkout
                }
            };
            
            return new Promise((resolve, reject) => {
                this.state.pendingRequests[request.id] = { resolve, reject };
                this.sendToHost(request);
                
                setTimeout(() => {
                    if (this.state.pendingRequests[request.id]) {
                        delete this.state.pendingRequests[request.id];
                        reject({ code: -32001, message: 'Request timeout' });
                    }
                }, 300000);
            });
        },
        
        // Generate unique ID
        generateId() {
            return 'req_' + Math.random().toString(36).substr(2, 9);
        },
        
        // Logging
        log(...args) {
            console.log('[EC]', ...args);
        },
        
        debugLog(direction, message) {
            if (!this.config.debug) return;
            
            const panel = document.getElementById('debug-panel');
            panel.classList.add('active');
            
            const div = document.createElement('div');
            div.className = `debug-message debug-${direction}`;
            div.textContent = `[${direction.toUpperCase()}] ${JSON.stringify(message)}`;
            panel.insertBefore(div, panel.firstChild);
            
            // Keep only last 50 messages
            while (panel.children.length > 50) {
                panel.removeChild(panel.lastChild);
            }
        },
        
        // Format currency
        formatCurrency(amount) {
            return new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: this.state.checkout.currency || 'USD'
            }).format(amount / 100);
        },
        
        // Render the checkout UI
        render() {
            const app = document.getElementById('checkout-app');
            const checkout = this.state.checkout;
            
            if (checkout.status === 'completed') {
                this.renderCompleted(app, checkout);
                return;
            }
            
            app.innerHTML = `
                <div class="checkout-header">
                    <h1>Checkout</h1>
                    <span class="checkout-status status-${checkout.status}">
                        ${checkout.status?.replace(/_/g, ' ') || 'incomplete'}
                    </span>
                </div>
                
                ${this.renderMessages(checkout)}
                ${this.renderLineItems(checkout)}
                ${this.renderBuyerForm(checkout)}
                ${this.renderTotals(checkout)}
                ${this.renderActions(checkout)}
            `;
            
            this.attachEventListeners();
        },
        
        renderMessages(checkout) {
            if (!checkout.messages?.length) return '';
            
            return `
                <div class="messages">
                    ${checkout.messages.map(msg => `
                        <div class="message message-${msg.type || 'error'}">
                            ${msg.content || msg.message}
                        </div>
                    `).join('')}
                </div>
            `;
        },
        
        renderLineItems(checkout) {
            if (!checkout.line_items?.length) return '';
            
            return `
                <div class="card">
                    <div class="card-title">Order Summary</div>
                    ${checkout.line_items.map(item => `
                        <div class="line-item">
                            <div class="item-info">
                                ${item.item.image_url ? 
                                    `<img src="${item.item.image_url}" alt="${item.item.title}" class="item-image">` : 
                                    '<div class="item-image"></div>'
                                }
                                <div class="item-details">
                                    <h3>${item.item.title}</h3>
                                    <span class="quantity">Qty: ${item.quantity}</span>
                                </div>
                            </div>
                            <span class="item-price">
                                ${this.formatCurrency(item.item.price * item.quantity)}
                            </span>
                        </div>
                    `).join('')}
                </div>
            `;
        },
        
        renderBuyerForm(checkout) {
            const buyer = checkout.buyer || {};
            
            return `
                <div class="card">
                    <div class="card-title">Contact Information</div>
                    <div class="form-group">
                        <label for="email">Email</label>
                        <input type="email" id="email" name="email" 
                               value="${buyer.email || ''}" 
                               placeholder="your@email.com">
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="firstName">First Name</label>
                            <input type="text" id="firstName" name="firstName" 
                                   value="${buyer.first_name || ''}" 
                                   placeholder="John">
                        </div>
                        <div class="form-group">
                            <label for="lastName">Last Name</label>
                            <input type="text" id="lastName" name="lastName" 
                                   value="${buyer.last_name || ''}" 
                                   placeholder="Doe">
                        </div>
                    </div>
                </div>
            `;
        },
        
        renderTotals(checkout) {
            if (!checkout.totals?.length) return '';
            
            return `
                <div class="card">
                    <div class="card-title">Order Total</div>
                    <div class="totals">
                        ${checkout.totals.map(total => `
                            <div class="total-row ${total.type === 'total' ? 'final' : ''}">
                                <span>${total.display_text}</span>
                                <span>${this.formatCurrency(total.amount)}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        },
        
        renderActions(checkout) {
            const canComplete = checkout.status === 'ready_for_complete';
            
            return `
                <button id="completeBtn" class="btn btn-primary" ${canComplete ? '' : 'disabled'}>
                    ${canComplete ? 'Complete Order' : 'Fill Required Information'}
                </button>
                <button id="updateBtn" class="btn btn-secondary">
                    Update Information
                </button>
            `;
        },
        
        renderCompleted(app, checkout) {
            app.innerHTML = `
                <div class="card success-container">
                    <div class="success-icon">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                        </svg>
                    </div>
                    <h2>Order Confirmed!</h2>
                    <p>Thank you for your purchase</p>
                    ${checkout.order?.id ? `
                        <div class="order-id">Order ID: ${checkout.order.id}</div>
                    ` : ''}
                    ${checkout.order?.permalink_url ? `
                        <a href="${checkout.order.permalink_url}" class="btn btn-primary" style="margin-top: 20px; display: inline-block; width: auto;">
                            View Order Details
                        </a>
                    ` : ''}
                </div>
            `;
            
            this.sendComplete();
        },
        
        attachEventListeners() {
            // Update button
            document.getElementById('updateBtn')?.addEventListener('click', () => {
                this.updateBuyerInfo();
            });
            
            // Complete button
            document.getElementById('completeBtn')?.addEventListener('click', () => {
                this.completeCheckout();
            });
        },
        
        async updateBuyerInfo() {
            const email = document.getElementById('email')?.value;
            const firstName = document.getElementById('firstName')?.value;
            const lastName = document.getElementById('lastName')?.value;
            
            try {
                const response = await fetch(`/embedded-checkout/${this.config.checkoutId}/update`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        buyer: {
                            email,
                            first_name: firstName,
                            last_name: lastName
                        }
                    })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    this.state.checkout = data.checkout;
                    this.render();
                    this.sendStateChange('buyer');
                }
            } catch (e) {
                this.log('Error updating buyer info:', e);
            }
        },
        
        async completeCheckout() {
            try {
                // Request payment credential if delegated
                if (this.config.delegations.includes('payment.credential')) {
                    try {
                        const credential = await this.requestPaymentCredential();
                        if (credential?.credential) {
                            // Handle payment credential
                            this.log('Received payment credential');
                        }
                    } catch (e) {
                        if (e.code === -32001) {
                            this.log('User cancelled payment');
                            return;
                        }
                    }
                }
                
                const response = await fetch(`/embedded-checkout/${this.config.checkoutId}/complete`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        idempotency_key: this.generateId()
                    })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    this.state.checkout = data.checkout;
                    this.render();
                }
            } catch (e) {
                this.log('Error completing checkout:', e);
            }
        }
    };
    
    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', () => {
        EmbeddedCheckout.init();
    });
    </script>
</body>
</html>'''


@router.get("/{checkout_id}", response_class=HTMLResponse)
async def get_embedded_checkout(
    checkout_id: str,
    ec_version: str = Query(..., description="UCP version (format: YYYY-MM-DD)"),
    ec_delegate: Optional[str] = Query(None, description="Comma-separated delegation identifiers"),
    ec_auth: Optional[str] = Query(None, description="Authentication token"),
):
    """
    Serve the embedded checkout HTML page.
    
    This endpoint is called when a host loads a checkout continue_url in embedded mode.
    Query parameters configure the EP Binding session.
    """
    # Get checkout from store
    checkout = store.get_checkout(checkout_id)
    
    if checkout is None:
        raise HTTPException(
            status_code=404,
            detail=f"Checkout with ID {checkout_id} not found"
        )
    
    # Parse delegations
    delegations = []
    if ec_delegate:
        delegations = [d.strip() for d in ec_delegate.split(",") if d.strip()]
        # Filter to only supported delegations
        delegations = [d for d in delegations if d in SUPPORTED_DELEGATIONS]
    
    # Create session (for tracking)
    try:
        session = create_embedded_checkout_session(
            checkout_id=checkout_id,
            ec_version=ec_version,
            ec_delegate=ec_delegate or "",
            ec_auth=ec_auth,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    logger.info(f"Serving embedded checkout for {checkout_id}, delegations: {delegations}")
    
    # Get and render template
    template = get_inline_checkout_template()
    
    # Simple template replacement (in production, use Jinja2)
    import json as json_module
    checkout_json = checkout.model_dump(mode="json")
    
    html = template.replace("{{ checkout_id }}", checkout_id)
    html = html.replace("{{ ec_version }}", ec_version)
    html = html.replace("{{ delegations | tojson }}", json_module.dumps(delegations))
    html = html.replace("{{ checkout | tojson }}", json_module.dumps(checkout_json))
    html = html.replace("{{ merchant_name }}", "UCP Store")
    
    return HTMLResponse(content=html)


@router.post("/{checkout_id}/update")
async def update_embedded_checkout(
    checkout_id: str,
    request: Request,
):
    """Update buyer information in the checkout."""
    checkout = store.get_checkout(checkout_id)
    
    if checkout is None:
        raise HTTPException(
            status_code=404,
            detail=f"Checkout with ID {checkout_id} not found"
        )
    
    data = await request.json()
    
    # Update buyer info
    if "buyer" in data:
        from ucp_sdk.models.schemas.shopping.types.buyer import Buyer
        
        buyer_data = data["buyer"]
        checkout.buyer = Buyer(
            email=buyer_data.get("email"),
            first_name=buyer_data.get("first_name"),
            last_name=buyer_data.get("last_name"),
        )
    
    # Re-validate checkout status
    start_result = store.start_payment(checkout_id)
    if not isinstance(start_result, str):
        checkout = start_result
    
    return JSONResponse({
        "status": "success",
        "checkout": checkout.model_dump(mode="json")
    })


@router.post("/{checkout_id}/complete")
async def complete_embedded_checkout(
    checkout_id: str,
    request: Request,
):
    """Complete the checkout and place the order."""
    checkout = store.get_checkout(checkout_id)
    
    if checkout is None:
        raise HTTPException(
            status_code=404,
            detail=f"Checkout with ID {checkout_id} not found"
        )
    
    data = await request.json()
    idempotency_key = data.get("idempotency_key")
    
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="idempotency_key is required"
        )
    
    # Validate checkout is ready
    start_result = store.start_payment(checkout_id)
    if isinstance(start_result, str):
        raise HTTPException(
            status_code=400,
            detail=f"Checkout not ready: {start_result}"
        )
    
    # Place the order
    try:
        checkout = store.place_order(checkout_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return JSONResponse({
        "status": "success",
        "checkout": checkout.model_dump(mode="json")
    })
