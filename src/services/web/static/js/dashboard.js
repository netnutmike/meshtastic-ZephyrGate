/**
 * ZephyrGate Web Administration Dashboard
 * JavaScript functionality for the web interface
 */

class ZephyrGateDashboard {
    constructor() {
        this.token = localStorage.getItem('zephyr_token');
        this.websocket = null;
        this.currentView = 'dashboard';
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.checkAuthentication();
        this.setupWebSocket();
        
        // Load initial data
        if (this.token) {
            this.loadDashboardData();
        }
    }
    
    setupEventListeners() {
        // Sidebar toggle
        document.getElementById('sidebar-toggle')?.addEventListener('click', () => {
            const sidebar = document.getElementById('sidebar');
            sidebar.classList.toggle('sidebar-hidden');
        });
        
        // Navigation links
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const view = link.getAttribute('href').substring(1);
                this.showView(view);
            });
        });
        
        // User menu
        document.getElementById('user-menu-button')?.addEventListener('click', () => {
            const menu = document.getElementById('user-menu');
            menu.classList.toggle('hidden');
        });
        
        // Logout
        document.getElementById('logout-btn')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.logout();
        });
        
        // Login form
        document.getElementById('login-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.login();
        });
        
        // Broadcast form
        document.getElementById('broadcast-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendBroadcast();
        });
        
        // Message search
        document.getElementById('search-btn')?.addEventListener('click', () => {
            this.searchMessages();
        });
        
        // Close user menu when clicking outside
        document.addEventListener('click', (e) => {
            const menu = document.getElementById('user-menu');
            const button = document.getElementById('user-menu-button');
            if (!button?.contains(e.target) && !menu?.contains(e.target)) {
                menu?.classList.add('hidden');
            }
        });
    }
    
    checkAuthentication() {
        if (!this.token) {
            this.showLoginModal();
        } else {
            this.hideLoginModal();
            this.loadUserProfile();
        }
    }
    
    showLoginModal() {
        document.getElementById('login-modal')?.classList.remove('hidden');
    }
    
    hideLoginModal() {
        document.getElementById('login-modal')?.classList.add('hidden');
    }
    
    async login() {
        const username = document.getElementById('username')?.value;
        const password = document.getElementById('password')?.value;
        const errorDiv = document.getElementById('login-error');
        
        if (!username || !password) {
            this.showError(errorDiv, 'Please enter both username and password');
            return;
        }
        
        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password }),
            });
            
            if (response.ok) {
                const data = await response.json();
                this.token = data.access_token;
                localStorage.setItem('zephyr_token', this.token);
                
                this.hideLoginModal();
                this.loadUserProfile();
                this.loadDashboardData();
                this.setupWebSocket();
            } else {
                const error = await response.json();
                this.showError(errorDiv, error.detail || 'Login failed');
            }
        } catch (error) {
            this.showError(errorDiv, 'Network error. Please try again.');
        }
    }
    
    logout() {
        this.token = null;
        localStorage.removeItem('zephyr_token');
        
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
        
        this.showLoginModal();
        this.updateConnectionStatus(false);
    }
    
    async loadUserProfile() {
        try {
            const response = await this.apiRequest('/api/auth/profile');
            if (response.ok) {
                const profile = await response.json();
                document.getElementById('username').textContent = profile.username;
            }
        } catch (error) {
            console.error('Failed to load user profile:', error);
        }
    }
    
    async loadDashboardData() {
        try {
            // Load system status
            const statusResponse = await this.apiRequest('/api/system/status');
            if (statusResponse.ok) {
                const status = await statusResponse.json();
                this.updateSystemStatus(status);
            }
            
            // Load nodes
            const nodesResponse = await this.apiRequest('/api/system/nodes');
            if (nodesResponse.ok) {
                const nodes = await nodesResponse.json();
                this.updateNodesTable(nodes);
            }
            
            // Load recent messages
            const messagesResponse = await this.apiRequest('/api/system/messages?limit=10');
            if (messagesResponse.ok) {
                const messages = await messagesResponse.json();
                this.updateRecentMessages(messages);
            }
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
        }
    }
    
    updateSystemStatus(status) {
        document.getElementById('system-status').textContent = status.status;
        document.getElementById('node-count').textContent = status.node_count;
        document.getElementById('message-count').textContent = status.message_count;
        document.getElementById('incident-count').textContent = status.active_incidents;
        
        // Update status indicator
        const indicator = document.querySelector('#system-status').parentElement.parentElement.querySelector('.status-indicator');
        indicator.className = `status-indicator ${status.status === 'running' ? 'status-running' : 'status-stopped'}`;
    }
    
    updateNodesTable(nodes) {
        const tbody = document.getElementById('nodes-tbody');
        if (!tbody) return;
        
        if (nodes.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-8 text-center text-gray-500">No nodes found</td></tr>';
            return;
        }
        
        tbody.innerHTML = nodes.map(node => `
            <tr class="border-b">
                <td class="px-4 py-2 font-mono text-sm">${node.node_id}</td>
                <td class="px-4 py-2">${node.short_name || node.long_name || 'Unknown'}</td>
                <td class="px-4 py-2">${node.hardware || 'Unknown'}</td>
                <td class="px-4 py-2">
                    ${node.battery_level ? `${node.battery_level}%` : 'N/A'}
                </td>
                <td class="px-4 py-2">${this.formatTimestamp(node.last_seen)}</td>
            </tr>
        `).join('');
    }
    
    updateRecentMessages(messages) {
        const container = document.getElementById('recent-messages');
        if (!container) return;
        
        if (messages.length === 0) {
            container.innerHTML = '<p class="text-gray-500 text-center py-4">No recent messages</p>';
            return;
        }
        
        container.innerHTML = messages.map(msg => `
            <div class="border-l-4 border-blue-500 pl-4 py-2">
                <div class="flex justify-between items-start">
                    <div>
                        <p class="font-semibold">${msg.sender_name || msg.sender_id}</p>
                        <p class="text-gray-600 text-sm">${msg.content}</p>
                    </div>
                    <span class="text-xs text-gray-500">${this.formatTimestamp(msg.timestamp)}</span>
                </div>
            </div>
        `).join('');
    }
    
    async sendBroadcast() {
        const content = document.getElementById('broadcast-content')?.value;
        const channel = document.getElementById('broadcast-channel')?.value;
        const interfaceId = document.getElementById('broadcast-interface')?.value;
        
        if (!content.trim()) {
            alert('Please enter a message to broadcast');
            return;
        }
        
        try {
            const response = await this.apiRequest('/api/broadcast/send', {
                method: 'POST',
                body: JSON.stringify({
                    content: content.trim(),
                    channel: channel ? parseInt(channel) : null,
                    interface_id: interfaceId || null
                })
            });
            
            if (response.ok) {
                alert('Broadcast sent successfully');
                document.getElementById('broadcast-content').value = '';
            } else {
                const error = await response.json();
                alert('Failed to send broadcast: ' + (error.detail || 'Unknown error'));
            }
        } catch (error) {
            alert('Network error. Please try again.');
        }
    }
    
    async searchMessages() {
        const query = document.getElementById('message-search')?.value;
        // Implement message search functionality
        console.log('Searching for:', query);
    }
    
    setupWebSocket() {
        if (!this.token) return;
        
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/dashboard_${Date.now()}`;
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('WebSocket connected');
            this.updateConnectionStatus(true);
        };
        
        this.websocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error);
            }
        };
        
        this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateConnectionStatus(false);
            
            // Attempt to reconnect after 5 seconds
            setTimeout(() => {
                if (this.token) {
                    this.setupWebSocket();
                }
            }, 5000);
        };
        
        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateConnectionStatus(false);
        };
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'system_event':
                this.addSystemEvent(data);
                break;
            case 'broadcast_sent':
                this.addSystemEvent({
                    type: 'broadcast',
                    message: `Broadcast sent by ${data.sender}: ${data.content}`,
                    timestamp: data.timestamp
                });
                break;
            default:
                console.log('Unknown WebSocket message type:', data.type);
        }
    }
    
    addSystemEvent(event) {
        const container = document.getElementById('system-events');
        if (!container) return;
        
        const eventDiv = document.createElement('div');
        eventDiv.className = 'border-l-4 border-green-500 pl-4 py-2';
        eventDiv.innerHTML = `
            <div class="flex justify-between items-start">
                <div>
                    <p class="font-semibold">${event.type || 'System Event'}</p>
                    <p class="text-gray-600 text-sm">${event.message || JSON.stringify(event.data)}</p>
                </div>
                <span class="text-xs text-gray-500">${this.formatTimestamp(event.timestamp)}</span>
            </div>
        `;
        
        // Add to top of events list
        if (container.firstChild && container.firstChild.textContent.includes('No recent events')) {
            container.innerHTML = '';
        }
        container.insertBefore(eventDiv, container.firstChild);
        
        // Keep only last 10 events
        while (container.children.length > 10) {
            container.removeChild(container.lastChild);
        }
    }
    
    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connection-status');
        if (!statusElement) return;
        
        const indicator = statusElement.querySelector('.status-indicator');
        const text = statusElement.querySelector('span:last-child') || statusElement;
        
        if (connected) {
            indicator.className = 'status-indicator status-running';
            text.textContent = 'Connected';
        } else {
            indicator.className = 'status-indicator status-stopped';
            text.textContent = 'Disconnected';
        }
    }
    
    showView(viewName) {
        // Hide all views
        document.querySelectorAll('.view').forEach(view => {
            view.classList.add('hidden');
        });
        
        // Show selected view
        const targetView = document.getElementById(`${viewName}-view`);
        if (targetView) {
            targetView.classList.remove('hidden');
            this.currentView = viewName;
        }
        
        // Update navigation
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('bg-blue-600');
            link.classList.add('hover:bg-gray-700');
        });
        
        const activeLink = document.querySelector(`[href="#${viewName}"]`);
        if (activeLink) {
            activeLink.classList.add('bg-blue-600');
            activeLink.classList.remove('hover:bg-gray-700');
        }
        
        // Load view-specific data
        this.loadViewData(viewName);
    }
    
    async loadViewData(viewName) {
        switch (viewName) {
            case 'dashboard':
                this.loadDashboardData();
                break;
            case 'nodes':
                // Refresh nodes data
                try {
                    const response = await this.apiRequest('/api/system/nodes');
                    if (response.ok) {
                        const nodes = await response.json();
                        this.updateNodesTable(nodes);
                    }
                } catch (error) {
                    console.error('Failed to load nodes:', error);
                }
                break;
            case 'messages':
                // Load message history
                try {
                    const response = await this.apiRequest('/api/system/messages?limit=50');
                    if (response.ok) {
                        const messages = await response.json();
                        this.updateMessagesList(messages);
                    }
                } catch (error) {
                    console.error('Failed to load messages:', error);
                }
                break;
        }
    }
    
    updateMessagesList(messages) {
        const container = document.getElementById('messages-list');
        if (!container) return;
        
        if (messages.length === 0) {
            container.innerHTML = '<p class="text-gray-500 text-center py-4">No messages found</p>';
            return;
        }
        
        container.innerHTML = messages.map(msg => `
            <div class="border border-gray-200 rounded-lg p-4">
                <div class="flex justify-between items-start mb-2">
                    <div>
                        <span class="font-semibold">${msg.sender_name || msg.sender_id}</span>
                        ${msg.recipient_id ? `<span class="text-gray-500">→ ${msg.recipient_id}</span>` : ''}
                        <span class="text-xs text-gray-500 ml-2">Channel ${msg.channel}</span>
                    </div>
                    <span class="text-xs text-gray-500">${this.formatTimestamp(msg.timestamp)}</span>
                </div>
                <p class="text-gray-700">${msg.content}</p>
                <div class="text-xs text-gray-500 mt-2">
                    Type: ${msg.message_type} | Interface: ${msg.interface_id}
                </div>
            </div>
        `).join('');
    }
    
    async apiRequest(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.token}`
            }
        };
        
        const mergedOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers
            }
        };
        
        const response = await fetch(url, mergedOptions);
        
        if (response.status === 401) {
            // Token expired or invalid
            this.logout();
            throw new Error('Authentication required');
        }
        
        return response;
    }
    
    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) { // Less than 1 minute
            return 'Just now';
        } else if (diff < 3600000) { // Less than 1 hour
            return `${Math.floor(diff / 60000)}m ago`;
        } else if (diff < 86400000) { // Less than 1 day
            return `${Math.floor(diff / 3600000)}h ago`;
        } else {
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        }
    }
    
    showError(element, message) {
        if (element) {
            element.textContent = message;
            element.classList.remove('hidden');
            setTimeout(() => {
                element.classList.add('hidden');
            }, 5000);
        }
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ZephyrGateDashboard();
});