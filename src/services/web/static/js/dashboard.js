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
        this.checkUserRole();
        
        // Load initial data
        if (this.token) {
            this.loadDashboardData();
        }
    }
    
    async checkUserRole() {
        try {
            const response = await this.apiRequest('/api/auth/profile');
            if (response.ok) {
                const profile = await response.json();
                this.userRole = profile.role;
                console.log('User role detected:', this.userRole);
                
                // Hide admin-only features for non-admin users
                if (this.userRole !== 'admin') {
                    console.log('Hiding admin-only features for non-admin user');
                    document.querySelectorAll('[data-admin-only="true"]').forEach(el => {
                        console.log('Hiding element:', el);
                        el.style.display = 'none';
                    });
                }
                
                // Hide operator features for viewers
                if (this.userRole === 'viewer') {
                    console.log('Hiding operator-only features for viewer');
                    document.querySelectorAll('[data-operator-only="true"]').forEach(el => {
                        el.style.display = 'none';
                    });
                }
            } else {
                console.warn('Failed to get user profile, status:', response.status);
            }
        } catch (error) {
            console.error('Error checking user role:', error);
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
        
        // User form
        document.getElementById('user-form')?.addEventListener('submit', (e) => {
            this.saveUser(e);
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
        
        // Logs controls
        document.getElementById('refresh-logs-btn')?.addEventListener('click', () => {
            this.loadLogs();
        });
        
        document.getElementById('download-logs-btn')?.addEventListener('click', () => {
            this.downloadLogs();
        });
        
        document.getElementById('auto-refresh-logs')?.addEventListener('change', () => {
            this.setupLogsAutoRefresh();
        });
        
        document.getElementById('log-service')?.addEventListener('change', () => {
            this.loadLogs();
        });
        
        document.getElementById('log-level')?.addEventListener('change', () => {
            this.loadLogs();
        });
        
        // Config controls
        document.getElementById('create-backup-btn')?.addEventListener('click', () => {
            this.createConfigBackup();
        });
        
        document.getElementById('save-general-config-btn')?.addEventListener('click', () => {
            this.saveGeneralConfig();
        });
        
        // Setup config tabs
        this.setupConfigTabs();
        
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
            this.showLoginPage();
        } else {
            this.hideLoginPage();
            this.loadUserProfile();
        }
    }
    
    showLoginPage() {
        document.getElementById('login-page')?.classList.remove('hidden');
        document.getElementById('main-dashboard')?.classList.remove('authenticated');
    }
    
    hideLoginPage() {
        document.getElementById('login-page')?.classList.add('hidden');
        document.getElementById('main-dashboard')?.classList.add('authenticated');
    }
    
    async login() {
        const username = document.getElementById('login-username')?.value;
        const password = document.getElementById('login-password')?.value;
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
                
                this.hideLoginPage();
                await this.checkUserRole(); // Check role and hide admin-only features
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
        
        this.showLoginPage();
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
        const text = document.getElementById('connection-text');
        
        if (connected) {
            indicator.className = 'status-indicator status-running';
            if (text) text.textContent = 'Connected';
        } else {
            indicator.className = 'status-indicator status-stopped';
            if (text) text.textContent = 'Disconnected';
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
            case 'system':
                this.loadSystemStatus();
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
            case 'logs':
                this.loadLogs();
                break;
            case 'users':
                this.loadUsers();
                break;
            case 'config':
                this.loadConfiguration();
                break;
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
    
    // ===== SYSTEM STATUS FUNCTIONALITY =====
    
    async loadSystemStatus() {
        try {
            // Load services status
            const servicesResponse = await this.apiRequest('/api/services');
            if (servicesResponse.ok) {
                const services = await servicesResponse.json();
                this.displaySystemStatus(services);
            } else {
                document.getElementById('service-status').innerHTML = 
                    '<p class="text-red-500">Failed to load service status</p>';
            }
            
            // Load system metrics
            const metricsResponse = await this.apiRequest('/api/system/metrics?limit=1');
            if (metricsResponse.ok) {
                const metrics = await metricsResponse.json();
                // Get the most recent metric
                if (metrics && metrics.length > 0) {
                    this.displaySystemMetrics(metrics[0]);
                }
            }
        } catch (error) {
            console.error('Error loading system status:', error);
            document.getElementById('service-status').innerHTML = 
                `<p class="text-red-500">Error: ${error.message}</p>`;
        }
    }
    
    displaySystemMetrics(metrics) {
        if (metrics.cpu_percent !== undefined) {
            const cpuEl = document.getElementById('cpu-usage');
            if (cpuEl) {
                cpuEl.textContent = `${metrics.cpu_percent.toFixed(1)}%`;
                cpuEl.className = metrics.cpu_percent > 80 ? 'text-2xl font-bold text-red-600' : 'text-2xl font-bold';
            }
        }
        
        if (metrics.memory_percent !== undefined) {
            const memEl = document.getElementById('memory-usage');
            if (memEl) {
                memEl.textContent = `${metrics.memory_percent.toFixed(1)}%`;
                memEl.className = metrics.memory_percent > 80 ? 'text-2xl font-bold text-red-600' : 'text-2xl font-bold';
            }
        }
        
        if (metrics.disk_percent !== undefined) {
            const diskEl = document.getElementById('disk-usage');
            if (diskEl) {
                diskEl.textContent = `${metrics.disk_percent.toFixed(1)}%`;
                diskEl.className = metrics.disk_percent > 90 ? 'text-2xl font-bold text-red-600' : 'text-2xl font-bold';
            }
        }
    }
    
    displaySystemStatus(services) {
        const container = document.getElementById('service-status');
        if (!container) return;
        
        if (!services || services.length === 0) {
            container.innerHTML = '<p class="text-gray-500">No services found</p>';
            return;
        }
        
        const html = services.map(service => {
            const statusColor = service.status === 'running' ? 'bg-green-500' : 'bg-red-500';
            const healthStatus = service.error_count > 0 ? 'degraded' : 'healthy';
            const healthColor = healthStatus === 'healthy' ? 'text-green-600' : 'text-yellow-600';
            
            // Only show control buttons for admin/operator roles
            const showControls = this.userRole === 'admin' || this.userRole === 'operator';
            
            return `
                <div class="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                    <div class="flex items-center space-x-4">
                        <div class="w-3 h-3 rounded-full ${statusColor}"></div>
                        <div>
                            <h4 class="font-semibold">${this.escapeHtml(service.name)}</h4>
                            <p class="text-sm text-gray-600">
                                Status: ${service.status} | Health: <span class="${healthColor}">${healthStatus}</span>
                                ${service.uptime > 0 ? ` | Uptime: ${this.formatUptime(service.uptime)}` : ''}
                                ${service.error_count > 0 ? ` | Errors: ${service.error_count}` : ''}
                            </p>
                        </div>
                    </div>
                    ${showControls ? `
                    <div class="flex space-x-2">
                        ${service.status === 'running' ? 
                            `<button onclick="dashboard.stopService('${service.name}')" 
                                    class="px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600">
                                Stop
                            </button>` :
                            `<button onclick="dashboard.startService('${service.name}')" 
                                    class="px-3 py-1 bg-green-500 text-white rounded hover:bg-green-600">
                                Start
                            </button>`
                        }
                        <button onclick="dashboard.restartService('${service.name}')" 
                                class="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600">
                            Restart
                        </button>
                    </div>
                    ` : ''}
                </div>
            `;
        }).join('');
        
        container.innerHTML = html;
    }
    
    async startService(serviceName) {
        if (!confirm(`Start service ${serviceName}?`)) return;
        
        try {
            const response = await this.apiRequest(`/api/services/${serviceName}/control`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'start' })
            });
            
            if (response.ok) {
                this.showNotification('Service started successfully', 'success');
                this.loadSystemStatus();
            } else {
                this.showNotification('Failed to start service', 'error');
            }
        } catch (error) {
            console.error('Error starting service:', error);
            this.showNotification(`Error: ${error.message}`, 'error');
        }
    }
    
    async stopService(serviceName) {
        if (!confirm(`Stop service ${serviceName}?`)) return;
        
        try {
            const response = await this.apiRequest(`/api/services/${serviceName}/control`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'stop' })
            });
            
            if (response.ok) {
                this.showNotification('Service stopped successfully', 'success');
                this.loadSystemStatus();
            } else {
                this.showNotification('Failed to stop service', 'error');
            }
        } catch (error) {
            console.error('Error stopping service:', error);
            this.showNotification(`Error: ${error.message}`, 'error');
        }
    }
    
    async restartService(serviceName) {
        if (!confirm(`Restart service ${serviceName}?`)) return;
        
        try {
            const response = await this.apiRequest(`/api/services/${serviceName}/control`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'restart' })
            });
            
            if (response.ok) {
                this.showNotification('Service restarted successfully', 'success');
                this.loadSystemStatus();
            } else {
                this.showNotification('Failed to restart service', 'error');
            }
        } catch (error) {
            console.error('Error restarting service:', error);
            this.showNotification(`Error: ${error.message}`, 'error');
        }
    }
    
    // ===== LOGS FUNCTIONALITY =====
    
    async loadLogs() {
        const service = document.getElementById('log-service')?.value || 'system';
        const level = document.getElementById('log-level')?.value || '';
        const lines = document.getElementById('log-lines')?.value || 100;
        
        try {
            let url = `/api/services/${service}/logs?lines=${lines}`;
            if (level && level !== '') {
                url += `&level=${level}`;
            }
            
            const response = await this.apiRequest(url);
            if (response.ok) {
                const data = await response.json();
                // Extract logs array from response
                const logs = data.logs || [];
                this.displayLogs(logs);
            } else {
                this.displayLogs([{
                    timestamp: new Date().toISOString(),
                    level: 'ERROR',
                    message: 'Failed to load logs'
                }]);
            }
        } catch (error) {
            console.error('Error loading logs:', error);
            this.displayLogs([{
                timestamp: new Date().toISOString(),
                level: 'ERROR',
                message: `Error: ${error.message}`
            }]);
        }
    }
    
    displayLogs(logs) {
        const container = document.getElementById('logs-content');
        if (!container) return;
        
        if (!logs || logs.length === 0) {
            container.innerHTML = '<p class="text-gray-400">No logs available</p>';
            return;
        }
        
        const logLevelColors = {
            'DEBUG': 'text-gray-400',
            'INFO': 'text-blue-400',
            'WARNING': 'text-yellow-400',
            'ERROR': 'text-red-400',
            'CRITICAL': 'text-red-600 font-bold'
        };
        
        const html = logs.map(log => {
            const levelColor = logLevelColors[log.level] || 'text-gray-300';
            const timestamp = new Date(log.timestamp).toLocaleString();
            return `<div class="mb-1">
                <span class="text-gray-500">[${timestamp}]</span>
                <span class="${levelColor}">[${log.level}]</span>
                <span class="text-gray-200">${this.escapeHtml(log.message)}</span>
            </div>`;
        }).join('');
        
        container.innerHTML = html;
        container.scrollTop = container.scrollHeight;
    }
    
    downloadLogs() {
        const service = document.getElementById('log-service')?.value || 'system';
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `zephyrgate-${service}-${timestamp}.log`;
        
        const container = document.getElementById('logs-content');
        const content = container?.textContent || '';
        
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }
    
    setupLogsAutoRefresh() {
        const checkbox = document.getElementById('auto-refresh-logs');
        if (!checkbox) return;
        
        if (this.logsRefreshInterval) {
            clearInterval(this.logsRefreshInterval);
            this.logsRefreshInterval = null;
        }
        
        if (checkbox.checked) {
            this.logsRefreshInterval = setInterval(() => {
                if (this.currentView === 'logs') {
                    this.loadLogs();
                }
            }, 5000); // Refresh every 5 seconds
        }
    }
    
    // ===== CONFIGURATION FUNCTIONALITY =====
    
    async loadConfiguration() {
        try {
            const response = await this.apiRequest('/api/config/sections');
            if (response.ok) {
                const sections = await response.json();
                // Load the first available section or 'app'
                const defaultSection = sections.includes('app') ? 'app' : 
                                      sections.includes('core') ? 'core' : 
                                      sections[0] || 'app';
                await this.loadConfigSection(defaultSection);
            } else {
                // Fallback: try to load app config directly
                await this.loadConfigSection('app');
            }
        } catch (error) {
            console.error('Error loading configuration:', error);
            // Show error message
            const container = document.getElementById('general-config-form');
            if (container) {
                container.innerHTML = '<p class="text-red-500">Failed to load configuration. Please check the console for errors.</p>';
            }
        }
    }
    
    async loadConfigSection(section) {
        try {
            const response = await this.apiRequest(`/api/config/${section}`);
            if (response.ok) {
                const config = await response.json();
                this.displayConfigForm(section, config);
            } else {
                const container = document.getElementById('general-config-form');
                if (container) {
                    container.innerHTML = `<p class="text-gray-500">No configuration available for section: ${section}</p>`;
                }
            }
        } catch (error) {
            console.error('Error loading config section:', error);
            const container = document.getElementById('general-config-form');
            if (container) {
                container.innerHTML = '<p class="text-red-500">Error loading configuration section.</p>';
            }
        }
    }
    
    displayConfigForm(section, config) {
        const container = document.getElementById('general-config-form');
        if (!container) return;
        
        if (!config || Object.keys(config).length === 0) {
            container.innerHTML = '<p class="text-gray-500">No configuration items available.</p>';
            return;
        }
        
        const html = Object.entries(config).map(([key, configItem]) => {
            // Handle both simple values and config objects with metadata
            const value = configItem?.value !== undefined ? configItem.value : configItem;
            const type = configItem?.type || typeof value;
            const required = configItem?.required || false;
            
            if (type === 'boolean' || typeof value === 'boolean') {
                return `<div class="flex items-center">
                    <input type="checkbox" id="config-${key}" ${value ? 'checked' : ''}
                           class="mr-2 h-4 w-4 text-blue-600 rounded">
                    <label for="config-${key}" class="text-sm font-medium text-gray-700">
                        ${this.formatConfigKey(key)}
                        ${required ? '<span class="text-red-500">*</span>' : ''}
                    </label>
                </div>`;
            } else if (typeof value === 'object' && value !== null) {
                return `<div class="border-l-4 border-blue-500 pl-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">
                        ${this.formatConfigKey(key)}
                        ${required ? '<span class="text-red-500">*</span>' : ''}
                    </label>
                    <textarea id="config-${key}" rows="4" 
                              class="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm"
                    >${JSON.stringify(value, null, 2)}</textarea>
                </div>`;
            } else {
                const inputType = type === 'integer' || type === 'number' || typeof value === 'number' ? 'number' : 'text';
                const displayValue = value === '***hidden***' ? '' : value;
                const placeholder = value === '***hidden***' ? '(hidden for security)' : '';
                
                return `<div>
                    <label for="config-${key}" class="block text-sm font-medium text-gray-700 mb-1">
                        ${this.formatConfigKey(key)}
                        ${required ? '<span class="text-red-500">*</span>' : ''}
                    </label>
                    <input type="${inputType}" id="config-${key}" value="${displayValue}"
                           placeholder="${placeholder}"
                           class="w-full px-3 py-2 border border-gray-300 rounded-md">
                </div>`;
            }
        }).join('');
        
        container.innerHTML = html || '<p class="text-gray-500">No configuration items to display.</p>';
    }
    
    async loadConfigBackups() {
        const container = document.getElementById('backups-list');
        if (!container) return;
        
        container.innerHTML = '<p class="text-gray-500">Loading backups...</p>';
        
        try {
            const response = await this.apiRequest('/api/config/backups');
            if (response.ok) {
                const backups = await response.json();
                this.displayConfigBackups(backups);
            } else {
                container.innerHTML = '<p class="text-gray-500">Failed to load backups. This feature may not be fully implemented yet.</p>';
            }
        } catch (error) {
            console.error('Error loading backups:', error);
            container.innerHTML = '<p class="text-gray-500">Backup feature is not yet available.</p>';
        }
    }
    
    displayConfigBackups(backups) {
        const container = document.getElementById('backups-list');
        if (!container) return;
        
        if (!backups || backups.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8">
                    <i class="fas fa-archive text-gray-400 text-4xl mb-4"></i>
                    <p class="text-gray-500">No backups available</p>
                    <p class="text-sm text-gray-400 mt-2">Create your first backup using the button above</p>
                </div>
            `;
            return;
        }
        
        const html = backups.map(backup => `
            <div class="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50">
                <div>
                    <p class="font-medium">${backup.description || 'Backup'}</p>
                    <p class="text-sm text-gray-500">${new Date(backup.created_at).toLocaleString()}</p>
                    <p class="text-xs text-gray-400">Size: ${this.formatBytes(backup.size || 0)}</p>
                </div>
                <div class="flex gap-2">
                    <button onclick="dashboard.restoreBackup('${backup.id}')" 
                            class="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm">
                        <i class="fas fa-undo mr-1"></i>Restore
                    </button>
                    <button onclick="dashboard.deleteBackup('${backup.id}')" 
                            class="px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700 text-sm">
                        <i class="fas fa-trash mr-1"></i>Delete
                    </button>
                </div>
            </div>
        `).join('');
        
        container.innerHTML = html;
    }
    
    async createConfigBackup() {
        const description = prompt('Enter backup description:');
        if (!description) return;
        
        try {
            const response = await this.apiRequest('/api/config/backup', {
                method: 'POST',
                body: JSON.stringify({ description })
            });
            
            if (response.ok) {
                alert('Backup created successfully');
                this.loadConfigBackups();
            } else {
                alert('Failed to create backup');
            }
        } catch (error) {
            console.error('Error creating backup:', error);
            alert('Error creating backup');
        }
    }
    
    async saveGeneralConfig() {
        // Collect all config values from the form
        const form = document.getElementById('general-config-form');
        if (!form) return;
        
        const config = {};
        form.querySelectorAll('input, textarea').forEach(input => {
            const key = input.id.replace('config-', '');
            if (input.type === 'checkbox') {
                config[key] = input.checked;
            } else if (input.type === 'number') {
                config[key] = parseFloat(input.value);
            } else if (input.tagName === 'TEXTAREA') {
                try {
                    config[key] = JSON.parse(input.value);
                } catch {
                    config[key] = input.value;
                }
            } else {
                config[key] = input.value;
            }
        });
        
        try {
            const response = await this.apiRequest('/api/config/app', {
                method: 'PUT',
                body: JSON.stringify(config)
            });
            
            if (response.ok) {
                alert('Configuration saved successfully');
            } else {
                alert('Failed to save configuration');
            }
        } catch (error) {
            console.error('Error saving config:', error);
            alert('Error saving configuration');
        }
    }
    
    async restoreBackup(backupId) {
        if (!confirm('Are you sure you want to restore this backup? This will restart the system.')) {
            return;
        }
        
        try {
            const response = await this.apiRequest(`/api/config/restore/${backupId}`, {
                method: 'POST'
            });
            
            if (response.ok) {
                alert('Backup restored successfully. System will restart.');
            } else {
                alert('Failed to restore backup');
            }
        } catch (error) {
            console.error('Error restoring backup:', error);
            alert('Error restoring backup');
        }
    }
    
    async deleteBackup(backupId) {
        if (!confirm('Are you sure you want to delete this backup?')) {
            return;
        }
        
        try {
            const response = await this.apiRequest(`/api/config/backups/${backupId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                this.loadConfigBackups();
            } else {
                alert('Failed to delete backup');
            }
        } catch (error) {
            console.error('Error deleting backup:', error);
            alert('Error deleting backup');
        }
    }
    
    setupConfigTabs() {
        document.querySelectorAll('.config-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const tabName = tab.dataset.tab;
                
                // Update tab styles
                document.querySelectorAll('.config-tab').forEach(t => {
                    t.classList.remove('border-blue-600', 'text-blue-600');
                    t.classList.add('border-transparent', 'text-gray-500');
                });
                tab.classList.remove('border-transparent', 'text-gray-500');
                tab.classList.add('border-blue-600', 'text-blue-600');
                
                // Show/hide content
                document.querySelectorAll('.config-content').forEach(content => {
                    content.classList.add('hidden');
                });
                document.getElementById(`config-${tabName}`)?.classList.remove('hidden');
                
                // Load data for the tab
                if (tabName === 'backups') {
                    this.loadConfigBackups();
                } else if (tabName === 'plugins') {
                    this.loadPluginsConfig();
                }
            });
        });
    }
    
    async loadPluginsConfig() {
        const container = document.getElementById('plugins-config-list');
        if (!container) return;
        
        container.innerHTML = '<p class="text-gray-500">Loading plugins...</p>';
        
        try {
            const response = await this.apiRequest('/api/plugins');
            if (response.ok) {
                const plugins = await response.json();
                this.displayPluginsConfig(plugins);
            } else {
                container.innerHTML = '<p class="text-gray-500">Failed to load plugins configuration.</p>';
            }
        } catch (error) {
            console.error('Error loading plugins config:', error);
            container.innerHTML = '<p class="text-red-500">Error loading plugins configuration.</p>';
        }
    }
    
    displayPluginsConfig(plugins) {
        const container = document.getElementById('plugins-config-list');
        if (!container) return;
        
        if (!plugins || plugins.length === 0) {
            container.innerHTML = '<p class="text-gray-500">No plugins installed.</p>';
            return;
        }
        
        // Only show control buttons for admin/operator roles
        const showControls = this.userRole === 'admin' || this.userRole === 'operator';
        
        const html = plugins.map(plugin => {
            // Determine actual status - check for errors first
            const hasError = plugin.status === 'error' || plugin.error;
            const isRunning = plugin.status === 'running' && !hasError;
            const statusClass = hasError ? 'status-warning' : (isRunning ? 'status-running' : 'status-stopped');
            const statusText = hasError ? 'Error' : (isRunning ? 'Running' : 'Stopped');
            
            // Get description - only show if it exists and isn't empty
            const description = plugin.description && plugin.description.trim() ? 
                               plugin.description : 
                               (plugin.metadata?.description || '');
            
            // Get version - only show if it exists and isn't "unknown"
            const version = plugin.version && plugin.version !== 'unknown' ? 
                           plugin.version : 
                           (plugin.metadata?.version || '');
            
            // Get author
            const author = plugin.author && plugin.author.trim() ? 
                          plugin.author : 
                          (plugin.metadata?.author || '');
            
            // Only show health if it's a boolean (not string "unknown")
            const showHealth = plugin.health && typeof plugin.health === 'object' && 
                              typeof plugin.health.is_healthy === 'boolean';
            
            return `
            <div class="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                <div class="flex items-start justify-between mb-3">
                    <div class="flex-1">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="status-indicator ${statusClass}"></span>
                            <h4 class="font-semibold text-lg">${plugin.name}</h4>
                            <span class="px-2 py-1 text-xs rounded ${
                                hasError ? 'bg-red-100 text-red-800' :
                                isRunning ? 'bg-green-100 text-green-800' : 
                                'bg-gray-100 text-gray-800'
                            }">
                                ${statusText}
                            </span>
                            ${version ? `<span class="text-xs text-gray-500">v${version}</span>` : ''}
                            ${showControls ? `
                            <div class="flex items-center gap-2 ml-auto">
                                <span class="text-xs text-gray-600">Enable at startup:</span>
                                <label class="toggle-switch">
                                    <input type="checkbox" 
                                           ${plugin.enabled ? 'checked' : ''} 
                                           onchange="dashboard.togglePluginEnabled('${plugin.name}', this.checked)">
                                    <span class="toggle-slider"></span>
                                </label>
                            </div>
                            ` : ''}
                        </div>
                        ${description ? `<p class="text-sm text-gray-600 mb-1">${description}</p>` : ''}
                        <div class="flex gap-4 text-xs text-gray-500">
                            ${author ? `<span><i class="fas fa-user mr-1"></i>${author}</span>` : ''}
                            ${plugin.uptime && plugin.uptime > 0 ? `<span><i class="fas fa-clock mr-1"></i>Uptime: ${this.formatUptime(plugin.uptime)}</span>` : ''}
                        </div>
                    </div>
                    ${showControls ? `
                    <div class="flex gap-2 ml-4 flex-shrink-0">
                        ${!hasError && isRunning ? 
                            `<button onclick="dashboard.restartPlugin('${plugin.name}')" 
                                    class="px-3 py-1 bg-yellow-600 text-white rounded text-sm hover:bg-yellow-700">
                                <i class="fas fa-redo mr-1"></i>Restart
                            </button>
                            <button onclick="dashboard.stopPlugin('${plugin.name}')" 
                                    class="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700">
                                <i class="fas fa-stop mr-1"></i>Stop
                            </button>` :
                            `<button onclick="dashboard.startPlugin('${plugin.name}')" 
                                    class="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700">
                                <i class="fas fa-play mr-1"></i>Start
                            </button>`
                        }
                        <button onclick="dashboard.configurePlugin('${plugin.name}')" 
                                class="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
                            <i class="fas fa-cog mr-1"></i>Configure
                        </button>
                    </div>
                    ` : ''}
                </div>
                
                ${showHealth ? `
                    <div class="mt-3 pt-3 border-t border-gray-200">
                        <div class="flex items-center justify-between text-sm">
                            <span class="text-gray-600">Health Status:</span>
                            <span class="${plugin.health.is_healthy ? 'text-green-600' : 'text-red-600'}">
                                <i class="fas fa-${plugin.health.is_healthy ? 'check-circle' : 'exclamation-circle'} mr-1"></i>
                                ${plugin.health.is_healthy ? 'Healthy' : 'Unhealthy'}
                            </span>
                        </div>
                        ${plugin.health.message ? `
                            <p class="text-xs text-gray-500 mt-1">${plugin.health.message}</p>
                        ` : ''}
                    </div>
                ` : ''}
                
                ${plugin.error || (plugin.error_count && plugin.error_count > 0) ? `
                    <div class="mt-2 p-2 bg-red-50 rounded text-sm">
                        <span class="text-red-600">
                            <i class="fas fa-exclamation-triangle mr-1"></i>
                            ${plugin.error ? 'Error: ' + plugin.error : 
                              plugin.error_count + ' error' + (plugin.error_count > 1 ? 's' : '') + ' recorded'}
                        </span>
                        ${plugin.last_error && !plugin.error ? `
                            <p class="text-xs text-gray-600 mt-1">Last: ${plugin.last_error}</p>
                        ` : ''}
                    </div>
                ` : ''}
            </div>
        `}).join('');
        
        container.innerHTML = html;
    }
    
    async togglePluginEnabled(pluginName, enabled) {
        try {
            const response = await this.apiRequest(`/api/plugins/${pluginName}/enable`, {
                method: 'POST',
                body: JSON.stringify({ enabled: enabled })
            });
            
            if (response.ok) {
                const message = enabled ? 
                    `Plugin ${pluginName} will be enabled at next startup` : 
                    `Plugin ${pluginName} will be disabled at next startup`;
                this.showNotification(message, 'success');
            } else {
                const error = await response.json();
                this.showNotification(`Failed to update plugin: ${error.detail || 'Unknown error'}`, 'error');
                // Reload to reset the toggle
                this.loadPluginsConfig();
            }
        } catch (error) {
            console.error('Error toggling plugin enabled state:', error);
            this.showNotification(`Error: ${error.message}`, 'error');
            // Reload to reset the toggle
            this.loadPluginsConfig();
        }
    }
    
    async startPlugin(pluginName) {
        try {
            const response = await this.apiRequest(`/api/plugins/${pluginName}/start`, {
                method: 'POST'
            });
            
            if (response.ok) {
                alert(`Plugin ${pluginName} started successfully`);
                this.loadPluginsConfig();
            } else {
                const error = await response.json();
                alert(`Failed to start plugin: ${error.detail || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Error starting plugin:', error);
            alert('Error starting plugin');
        }
    }
    
    async stopPlugin(pluginName) {
        if (!confirm(`Are you sure you want to stop ${pluginName}?`)) {
            return;
        }
        
        try {
            const response = await this.apiRequest(`/api/plugins/${pluginName}/stop`, {
                method: 'POST'
            });
            
            if (response.ok) {
                alert(`Plugin ${pluginName} stopped successfully`);
                this.loadPluginsConfig();
            } else {
                const error = await response.json();
                alert(`Failed to stop plugin: ${error.detail || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Error stopping plugin:', error);
            alert('Error stopping plugin');
        }
    }
    
    async restartPlugin(pluginName) {
        try {
            const response = await this.apiRequest(`/api/plugins/${pluginName}/restart`, {
                method: 'POST'
            });
            
            if (response.ok) {
                alert(`Plugin ${pluginName} restarted successfully`);
                this.loadPluginsConfig();
            } else {
                const error = await response.json();
                alert(`Failed to restart plugin: ${error.detail || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Error restarting plugin:', error);
            alert('Error restarting plugin');
        }
    }
    
    async configurePlugin(pluginName) {
        // Store current plugin name
        this.currentConfigPlugin = pluginName;
        
        // Show modal
        document.getElementById('plugin-config-modal').classList.remove('hidden');
        document.getElementById('config-plugin-name').textContent = pluginName;
        
        const editor = document.getElementById('plugin-config-editor');
        const errorDiv = document.getElementById('config-error');
        
        editor.value = 'Loading configuration...';
        errorDiv.classList.add('hidden');
        
        try {
            // Load plugin configuration from the API
            const response = await this.apiRequest(`/api/plugins/${pluginName}/config`);
            
            if (response.ok) {
                const config = await response.json();
                // Convert to YAML-like format for display
                editor.value = this.formatConfigAsYAML(pluginName, config);
            } else {
                editor.value = `# Configuration for ${pluginName}\n# No configuration found or error loading\n\n# Add your configuration here in YAML format`;
            }
        } catch (error) {
            console.error('Error loading plugin config:', error);
            editor.value = `# Error loading configuration\n# ${error.message}\n\n# Add your configuration here in YAML format`;
        }
    }
    
    formatConfigAsYAML(pluginName, config) {
        // Format the config object as YAML-like text
        let yaml = `# Configuration for ${pluginName}\n`;
        yaml += `# Edit the values below and click Save to update config/config.yaml\n\n`;
        yaml += `${pluginName}:\n`;
        
        if (!config || Object.keys(config).length === 0) {
            yaml += `  # No configuration items\n`;
            return yaml;
        }
        
        const formatValue = (value, indent = 2) => {
            const spaces = ' '.repeat(indent);
            if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                let result = '\n';
                for (const [k, v] of Object.entries(value)) {
                    result += `${spaces}${k}: ${formatValue(v, indent + 2)}`;
                }
                return result;
            } else if (Array.isArray(value)) {
                if (value.length === 0) return '[]\n';
                let result = '\n';
                for (const item of value) {
                    result += `${spaces}- ${typeof item === 'object' ? JSON.stringify(item) : item}\n`;
                }
                return result;
            } else if (typeof value === 'string') {
                return `"${value}"\n`;
            } else {
                return `${value}\n`;
            }
        };
        
        for (const [key, value] of Object.entries(config)) {
            yaml += `  ${key}: ${formatValue(value, 4)}`;
        }
        
        return yaml;
    }
    
    closeConfigModal() {
        document.getElementById('plugin-config-modal').classList.add('hidden');
        this.currentConfigPlugin = null;
    }
    
    async savePluginConfig() {
        const pluginName = this.currentConfigPlugin;
        if (!pluginName) return;
        
        const editor = document.getElementById('plugin-config-editor');
        const errorDiv = document.getElementById('config-error');
        const configText = editor.value;
        
        errorDiv.classList.add('hidden');
        
        try {
            // Parse YAML-like text to JSON
            // For now, we'll send the raw text and let the backend handle it
            // In a real implementation, you'd use a YAML parser
            
            const response = await this.apiRequest(`/api/plugins/${pluginName}/config`, {
                method: 'PUT',
                body: JSON.stringify({
                    config_text: configText,
                    format: 'yaml'
                })
            });
            
            if (response.ok) {
                alert('Configuration saved successfully! The system may need to restart for changes to take effect.');
                this.closeConfigModal();
                this.loadPluginsConfig();
            } else {
                const error = await response.json();
                errorDiv.textContent = `Failed to save: ${error.detail || 'Unknown error'}`;
                errorDiv.classList.remove('hidden');
            }
        } catch (error) {
            console.error('Error saving config:', error);
            errorDiv.textContent = `Error: ${error.message}`;
            errorDiv.classList.remove('hidden');
        }
    }
    
    formatUptime(seconds) {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
        return `${Math.floor(seconds / 86400)}d`;
    }
    
    formatConfigKey(key) {
        return key.split('_').map(word => 
            word.charAt(0).toUpperCase() + word.slice(1)
        ).join(' ');
    }
    
    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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
    
    showNotification(message, type = 'info') {
        const container = document.getElementById('notification-container');
        if (!container) return;
        
        const notification = document.createElement('div');
        notification.className = `px-6 py-4 rounded-lg shadow-lg text-white transform transition-all duration-300 ${
            type === 'success' ? 'bg-green-500' :
            type === 'error' ? 'bg-red-500' :
            type === 'warning' ? 'bg-yellow-500' :
            'bg-blue-500'
        }`;
        
        notification.innerHTML = `
            <div class="flex items-center space-x-3">
                <i class="fas ${
                    type === 'success' ? 'fa-check-circle' :
                    type === 'error' ? 'fa-exclamation-circle' :
                    type === 'warning' ? 'fa-exclamation-triangle' :
                    'fa-info-circle'
                }"></i>
                <span>${this.escapeHtml(message)}</span>
            </div>
        `;
        
        container.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.style.opacity = '1';
            notification.style.transform = 'translateX(0)';
        }, 10);
        
        // Remove after 5 seconds
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => {
                container.removeChild(notification);
            }, 300);
        }, 5000);
    }
    
    // ===== USER MANAGEMENT FUNCTIONALITY =====
    
    async loadUsers() {
        try {
            const response = await this.apiRequest('/api/admin/users');
            if (response.ok) {
                const users = await response.json();
                this.displayUsers(users);
            } else {
                document.getElementById('users-table-body').innerHTML = 
                    '<tr><td colspan="7" class="px-6 py-4 text-center text-red-500">Failed to load users</td></tr>';
            }
        } catch (error) {
            console.error('Error loading users:', error);
            document.getElementById('users-table-body').innerHTML = 
                `<tr><td colspan="7" class="px-6 py-4 text-center text-red-500">Error: ${error.message}</td></tr>`;
        }
    }
    
    displayUsers(users) {
        const tbody = document.getElementById('users-table-body');
        if (!tbody) return;
        
        if (!users || users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="px-6 py-4 text-center text-gray-500">No users found</td></tr>';
            return;
        }
        
        const html = users.map(user => {
            const statusBadge = user.is_active ? 
                '<span class="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800">Active</span>' :
                '<span class="px-2 py-1 text-xs rounded-full bg-red-100 text-red-800">Inactive</span>';
            
            const roleBadge = user.role === 'admin' ?
                '<span class="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-800">Admin</span>' :
                '<span class="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-800">Viewer</span>';
            
            const lastLogin = user.last_login ? new Date(user.last_login).toLocaleString() : 'Never';
            
            return `
                <tr>
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        ${this.escapeHtml(user.username)}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        ${this.escapeHtml(user.full_name || '-')}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        ${this.escapeHtml(user.email || '-')}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm">
                        ${roleBadge}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm">
                        ${statusBadge}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        ${lastLogin}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm space-x-2">
                        <button onclick="dashboard.editUser('${user.username}')" 
                                class="text-blue-600 hover:text-blue-900">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button onclick="dashboard.changeUserPassword('${user.username}')" 
                                class="text-green-600 hover:text-green-900">
                            <i class="fas fa-key"></i>
                        </button>
                        <button onclick="dashboard.deleteUser('${user.username}')" 
                                class="text-red-600 hover:text-red-900">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
        
        tbody.innerHTML = html;
    }
    
    showAddUserModal() {
        document.getElementById('user-modal-title').textContent = 'Add User';
        document.getElementById('user-form').reset();
        document.getElementById('user-edit-username').value = '';
        document.getElementById('user-username').disabled = false;
        document.getElementById('user-password').required = true;
        document.getElementById('user-modal').classList.remove('hidden');
    }
    
    async editUser(username) {
        try {
            const response = await this.apiRequest(`/api/admin/users/${username}`);
            if (response.ok) {
                const user = await response.json();
                
                document.getElementById('user-modal-title').textContent = 'Edit User';
                document.getElementById('user-edit-username').value = username;
                document.getElementById('user-username').value = user.username;
                document.getElementById('user-username').disabled = true;
                document.getElementById('user-fullname').value = user.full_name || '';
                document.getElementById('user-email').value = user.email || '';
                document.getElementById('user-role').value = user.role;
                document.getElementById('user-active').checked = user.is_active;
                document.getElementById('user-password').required = false;
                document.getElementById('user-password').value = '';
                
                document.getElementById('user-modal').classList.remove('hidden');
            }
        } catch (error) {
            console.error('Error loading user:', error);
            this.showNotification('Failed to load user details', 'error');
        }
    }
    
    closeUserModal() {
        document.getElementById('user-modal').classList.add('hidden');
        document.getElementById('user-form').reset();
    }
    
    async saveUser(event) {
        event.preventDefault();
        
        const editUsername = document.getElementById('user-edit-username').value;
        const isEdit = !!editUsername;
        
        const userData = {
            username: document.getElementById('user-username').value,
            full_name: document.getElementById('user-fullname').value || null,
            email: document.getElementById('user-email').value || null,
            role: document.getElementById('user-role').value,
            is_active: document.getElementById('user-active').checked
        };
        
        const password = document.getElementById('user-password').value;
        if (password) {
            userData.password = password;
        }
        
        try {
            const url = isEdit ? `/api/admin/users/${editUsername}` : '/api/admin/users';
            const method = isEdit ? 'PUT' : 'POST';
            
            const response = await this.apiRequest(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(userData)
            });
            
            if (response.ok) {
                this.showNotification(isEdit ? 'User updated successfully' : 'User created successfully', 'success');
                this.closeUserModal();
                this.loadUsers();
            } else {
                const error = await response.json();
                this.showNotification(error.detail || 'Failed to save user', 'error');
            }
        } catch (error) {
            console.error('Error saving user:', error);
            this.showNotification(`Error: ${error.message}`, 'error');
        }
    }
    
    async changeUserPassword(username) {
        const newPassword = prompt(`Enter new password for ${username}:`);
        if (!newPassword) return;
        
        const confirmPassword = prompt('Confirm new password:');
        if (newPassword !== confirmPassword) {
            this.showNotification('Passwords do not match', 'error');
            return;
        }
        
        try {
            const response = await this.apiRequest(`/api/admin/users/${username}/password`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: newPassword })
            });
            
            if (response.ok) {
                this.showNotification('Password changed successfully', 'success');
            } else {
                const error = await response.json();
                this.showNotification(error.detail || 'Failed to change password', 'error');
            }
        } catch (error) {
            console.error('Error changing password:', error);
            this.showNotification(`Error: ${error.message}`, 'error');
        }
    }
    
    async deleteUser(username) {
        if (!confirm(`Are you sure you want to delete user '${username}'?`)) return;
        
        try {
            const response = await this.apiRequest(`/api/admin/users/${username}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                this.showNotification('User deleted successfully', 'success');
                this.loadUsers();
            } else {
                const error = await response.json();
                this.showNotification(error.detail || 'Failed to delete user', 'error');
            }
        } catch (error) {
            console.error('Error deleting user:', error);
            this.showNotification(`Error: ${error.message}`, 'error');
        }
    }
}

// Initialize dashboard when DOM is loaded
let dashboard; // Global reference for onclick handlers
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new ZephyrGateDashboard();
});