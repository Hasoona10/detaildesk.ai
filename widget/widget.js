/**
 * AI Receptionist Chat Widget
 */
(function() {
    'use strict';

    class ChatWidget {
        constructor(config) {
            this.config = {
                apiUrl: config.apiUrl || 'http://localhost:8000',
                businessId: config.businessId || 'oc_elite_detailing',
                businessName: config.businessName || 'OC Elite Detailing',
                position: config.position || 'bottom-right',
                primaryColor: config.primaryColor || '#0f172a',
                greeting: config.greeting || 'Hi — what vehicle are we helping you with today?',
                ...config
            };
            
            this.isOpen = false;
            this.ws = null;
            this.init();
        }

        init() {
            this.createWidget();
            this.attachStyles();
            this.connectWebSocket();
        }

        createWidget() {
            // Create widget container
            this.container = document.createElement('div');
            this.container.id = 'ai-receptionist-widget';
            this.container.className = 'ai-receptionist-widget';

            // Create chat button
            this.button = document.createElement('div');
            this.button.className = 'ai-receptionist-button';
            this.button.innerHTML = `
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
            `;
            this.button.addEventListener('click', () => this.toggleChat());

            // Create chat window
            this.chatWindow = document.createElement('div');
            this.chatWindow.className = 'ai-receptionist-window';
            this.chatWindow.innerHTML = `
                <div class="ai-receptionist-header">
                    <h3>${this.config.businessName} · AI Receptionist</h3>
                    <button class="ai-receptionist-close">&times;</button>
                </div>
                <div class="ai-receptionist-subheader">Never lose a detailing lead. Ask about quotes, mobile service, ceramic coating, or booking.</div>
                <div class="ai-receptionist-messages"></div>
                <div class="ai-receptionist-input-container">
                    <input type="text" class="ai-receptionist-input" placeholder="Tell us about your vehicle or service…">
                    <button class="ai-receptionist-send">Send</button>
                </div>
            `;

            this.container.appendChild(this.button);
            this.container.appendChild(this.chatWindow);

            // Add to page
            document.body.appendChild(this.container);

            // Event listeners
            const closeBtn = this.chatWindow.querySelector('.ai-receptionist-close');
            closeBtn.addEventListener('click', () => this.toggleChat());

            const sendBtn = this.chatWindow.querySelector('.ai-receptionist-send');
            const input = this.chatWindow.querySelector('.ai-receptionist-input');
            sendBtn.addEventListener('click', () => this.sendMessage());
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.sendMessage();
                }
            });

            // Initial greeting will come from WebSocket or we'll show it after connection
            this.greetingShown = false;
        }

        attachStyles() {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = `${this.config.apiUrl}/widget/widget.css`;
            document.head.appendChild(link);
        }

        connectWebSocket() {
            // Handle both http:// and https://, and ensure ws:// or wss://
            let wsUrl = this.config.apiUrl.replace(/^http/, 'ws');
            // If apiUrl doesn't have protocol, add ws://
            if (!wsUrl.startsWith('ws://') && !wsUrl.startsWith('wss://')) {
                wsUrl = 'ws://' + wsUrl;
            }
            wsUrl = wsUrl + '/api/chat/ws';
            console.log('Connecting to WebSocket:', wsUrl);
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('Chat widget connected');
                this.ws.send(JSON.stringify({
                    type: 'init',
                    business_id: this.config.businessId
                }));
                // WebSocket will send greeting, so we don't need to show one
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'message') {
                        this.addMessage('assistant', data.text);
                        this.greetingShown = true;
                    }
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                // Don't show error to user, HTTP fallback will handle it silently
            };

            this.ws.onclose = (event) => {
                console.log('Chat widget disconnected', event.code, event.reason);
                // If WebSocket closes unexpectedly, show greeting if not shown yet
                if (!this.greetingShown && event.code !== 1000) {
                    this.addMessage('assistant', this.config.greeting);
                    this.greetingShown = true;
                }
                // Only reconnect if it wasn't a normal closure
                if (event.code !== 1000) {
                    setTimeout(() => this.connectWebSocket(), 3000);
                }
            };
        }

        toggleChat() {
            this.isOpen = !this.isOpen;
            this.container.classList.toggle('open', this.isOpen);
        }

        addMessage(role, text, messageId = null) {
            const messagesContainer = this.chatWindow.querySelector('.ai-receptionist-messages');
            const message = document.createElement('div');
            message.className = `ai-receptionist-message ai-receptionist-message-${role}`;
            message.textContent = text;
            if (messageId) {
                message.setAttribute('data-message-id', messageId);
            }
            messagesContainer.appendChild(message);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
            return message;
        }

        sendMessage() {
            const input = this.chatWindow.querySelector('.ai-receptionist-input');
            const text = input.value.trim();
            
            if (!text) return;

            // Add user message
            this.addMessage('user', text);
            input.value = '';

            // Send via WebSocket
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'message',
                    text: text,
                    business_id: this.config.businessId
                }));
            } else {
                // Fallback to HTTP
                this.sendMessageHTTP(text);
            }
        }

        async sendMessageHTTP(text) {
            try {
                const sessionId = `web_${Date.now()}`;
                const response = await fetch(`${this.config.apiUrl}/api/chat/message`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Session-ID': sessionId
                    },
                    body: JSON.stringify({
                        text: text,
                        business_id: this.config.businessId
                    })
                });

                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
                }

                const data = await response.json();
                if (data.response) {
                    this.addMessage('assistant', data.response);
                    this.greetingShown = true;
                } else if (data.error) {
                    this.addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
                    console.error('API error:', data.error);
                } else {
                    console.warn('Unexpected response format:', data);
                    this.addMessage('assistant', 'Sorry, I received an unexpected response. Please try again.');
                }
            } catch (error) {
                console.error('Error sending message:', error);
                this.addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
            }
        }
    }

    // Auto-initialize if config is provided
    if (window.AIReceptionistConfig) {
        window.AIReceptionist = new ChatWidget(window.AIReceptionistConfig);
    }

    // Export for manual initialization
    window.AIReceptionistWidget = ChatWidget;
})();


