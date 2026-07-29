// UPS Monitor Frontend JavaScript - Complete Recreation

// Debug utility for conditional logging
class DebugLogger {
    constructor() {
        this.isDebugEnabled = this.checkDebugEnabled();
    }
    
    checkDebugEnabled() {
        // Check localStorage, URL params, or global debug flag
        const urlParams = new URLSearchParams(window.location.search);
        const debugParam = urlParams.get('debug');
        const storageDebug = localStorage.getItem('ups_debug');
        const globalDebug = window.UPS_DEBUG;
        
        // Enable debug by default for testing historic data updates (remove "|| true" to disable)
        return debugParam === 'true' || storageDebug === 'true' || globalDebug === true;
    }
    
    log(...args) {
        if (this.isDebugEnabled) {
            console.log('[UPS Debug]', ...args);
        }
    }
    
    error(...args) {
        if (this.isDebugEnabled) {
            console.error('[UPS Debug Error]', ...args);
        }
    }
    
    warn(...args) {
        if (this.isDebugEnabled) {
            console.warn('[UPS Debug Warn]', ...args);
        }
    }
    
    info(...args) {
        if (this.isDebugEnabled) {
            console.info('[UPS Debug Info]', ...args);
        }
    }
}

// Global debug instance
const debug = new DebugLogger();

class UPSMonitor {
    constructor() {
        this.socket = null;
        this.currentData = {};
        this.historyData = [];
        this.events = [];
        this.batteryEvents = [];
        this.batteryStats = {};
        this.lastBatteryStatus = null;
        this.lastBatteryCharge = undefined;
        this.lastBatteryDataFetch = 0;
        this.isConnected = false;
        this.isRestarting = false;
        this.charts = {};
        this.settings = {
            apiUrl: this.getApiUrl(),
            wsUrl: this.getWebSocketUrl(),
            timeRange: '2',
            dataPoints: '200',
            autoRefresh: true
        };
        this.historicData = {
            currentPage: 1,
            rowsPerPage: 100,
            totalRecords: 0,
            data: [],
            filters: {
                dateFrom: null,
                dateTo: null
            }
        };
        
        this.init();
    }
    
    getApiUrl() {
        // Auto-detect API URL based on current window location
        const protocol = window.location.protocol;
        const hostname = window.location.hostname;
        const port = window.location.port || '8555'; // Default to service port
        return `${protocol}//${hostname}:${port}`;
    }
    
    getWebSocketUrl() {
        // Socket.IO expects an HTTP(S) origin and negotiates the transport itself.
        return window.location.origin;
    }

    init() {
        this.loadSettings();
        this.setupEventListeners();
        this.setupTabs();
        this.connectWebSocket();
        this.fetchInitialData();
        this.initializeCharts();
        this.startAutoRefresh();
        
        // Initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
        
        // Update status display with auto-detected URL
        this.updateApiUrlDisplay();
    }
    
    loadSettings() {
        const saved = localStorage.getItem('apc-ups-monitor-settings');
        if (saved) {
            const savedSettings = JSON.parse(saved);
            // Only load non-URL settings, URLs are auto-detected
            this.settings.timeRange = savedSettings.timeRange || this.settings.timeRange;
            this.settings.dataPoints = savedSettings.dataPoints || this.settings.dataPoints;
            this.settings.autoRefresh = savedSettings.autoRefresh !== undefined ? savedSettings.autoRefresh : this.settings.autoRefresh;
        }
    }
    
    saveSettings() {
        // Only save non-URL settings, URLs are auto-detected
        const settingsToSave = {
            timeRange: this.settings.timeRange,
            dataPoints: this.settings.dataPoints,
            autoRefresh: this.settings.autoRefresh
        };
        
        localStorage.setItem('apc-ups-monitor-settings', JSON.stringify(settingsToSave));
        
        // Refresh data with new settings
        this.fetchInitialData();
        this.fetchHistoryData();
    }
    
    updateApiUrlDisplay() {
        // Update the status display with auto-detected URL
        const apiUrlElement = document.getElementById('api-url');
        if (apiUrlElement) {
            apiUrlElement.textContent = this.settings.apiUrl;
        }
        
        // Update settings modal display
        const settingsApiUrlElement = document.getElementById('settings-api-url');
        if (settingsApiUrlElement) {
            settingsApiUrlElement.textContent = this.settings.apiUrl;
        }
    }
    
    setupEventListeners() {
        // Settings modal
        document.getElementById('settings-btn').addEventListener('click', () => {
            document.getElementById('settings-modal').classList.remove('hidden');
        });
        
        document.getElementById('close-settings').addEventListener('click', () => {
            document.getElementById('settings-modal').classList.add('hidden');
        });
        
        document.getElementById('save-settings').addEventListener('click', () => {
            this.saveSettings();
            document.getElementById('settings-modal').classList.add('hidden');
            this.showNotification('Settings saved successfully!', 'success');
        });
        
        
        // Header refresh button
        document.getElementById('refresh-btn').addEventListener('click', () => {
            this.fetchInitialData();
            this.fetchHistoryData();
        });
        
        // Chart controls
        document.getElementById('refresh-charts').addEventListener('click', () => {
            this.fetchHistoryData();
        });
        
        // Configuration tab event listeners
        this.setupConfigurationEventListeners();
        
        // Historic data event listeners
        this.setupHistoricDataEventListeners();
        
        // Close modal when clicking outside
        document.getElementById('settings-modal').addEventListener('click', (e) => {
            if (e.target === document.getElementById('settings-modal')) {
                document.getElementById('settings-modal').classList.add('hidden');
            }
        });
    }
    
    setupTabs() {
        const tabButtons = document.querySelectorAll('.tab-trigger');
        const tabContents = document.querySelectorAll('.tab-content');
        
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabName = button.getAttribute('data-tab');
                
                // Update active tab button
                tabButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                
                // Show corresponding tab content
                tabContents.forEach(content => {
                    if (content.id === `${tabName}-tab`) {
                        content.classList.add('active');
                    } else {
                        content.classList.remove('active');
                        // Disable real-time updates for historic tab when not active
                        if (content.id === 'historic-tab') {
                            this.disableHistoricRealTimeUpdates();
                        }
                    }
                });
                
                // Load tab-specific data
                this.loadTabData(tabName);
            });
        });
    }
    
    loadTabData(tabName) {
        switch (tabName) {
            case 'charts':
                this.fetchHistoryData();
                break;
            case 'battery':
                this.fetchBatteryData();
                break;
            case 'events':
                this.fetchEvents();
                break;
            case 'system':
                // System info is loaded with current data
                break;
            case 'config':
                this.loadConfigurationData();
                break;
            case 'historic':
                this.loadHistoricDataTab();
                this.enableHistoricRealTimeUpdates();
                break;
        }
    }
    
    setupSocketEventHandlers() {
        if (!this.socket) return;
        
        // Remove all existing listeners first
        this.socket.removeAllListeners();
        
        this.socket.on('connect', () => {
            this.isConnected = true;
            this.updateConnectionStatus();
            debug.log('WebSocket connected, session ID:', this.socket.id);
        });
        
        this.socket.on('disconnect', (reason) => {
            this.isConnected = false;
            this.updateConnectionStatus();
            debug.log('WebSocket disconnected, reason:', reason);
            
            // Auto-reconnect if disconnected by server
            if (reason === 'io server disconnect') {
                debug.log('Server initiated disconnect, attempting reconnection...');
                setTimeout(() => this.connectWebSocket(), 2000);
            }
        });
        
        this.socket.on('connect_error', (error) => {
            debug.error('WebSocket connection error:', error);
            this.isConnected = false;
            this.updateConnectionStatus();
        });
        
        this.socket.on('reconnect', (attemptNumber) => {
            debug.log('Reconnected after', attemptNumber, 'attempts');
            this.isConnected = true;
            this.updateConnectionStatus();
            // Re-setup handlers after reconnection
            this.setupSocketEventHandlers();
        });
        
        this.socket.on('reconnecting', (attemptNumber) => {
            debug.log('Reconnect attempt:', attemptNumber);
        });
        
        this.socket.on('error', (error) => {
            debug.error('WebSocket error:', error);
        });
        
        this.socket.on('ups_data', (data) => {
            debug.log('WebSocket ups_data received at:', new Date().toISOString());
            debug.log('Handler function ID:', this.socket.on.toString().slice(0, 50));
            debug.log('Socket connected:', this.socket.connected);
            debug.log('Data:', data);
            
            if (!data || !data.data) {
                debug.warn('Invalid WebSocket data received:', data);
                return;
            }
            
            if (data.data.stale || data.data.data_state === 'reconnecting') {
                this.setRestartingState(true, 'Reconnecting to UPS…');
                return;
            }

            this.setRestartingState(false);
            this.currentData = data.data;
            this.updateUI();
            this.updateLastUpdated();
            
            // Update charts with real-time data
            this.updateChartsWithRealTimeData(this.currentData);
            
            // Update historic data if the historic tab is active
            this.updateHistoricDataRealTime(this.currentData);
            
            // Update battery tab data in real-time if the battery tab is active
            this.updateBatteryTabRealTime(this.currentData);
            
            if (data.alerts && data.alerts.length > 0) {
                this.handleAlerts(data.alerts);
            }
        });

        this.socket.on('ups_state', (state) => {
            if (state && state.state === 'restarting') {
                this.setRestartingState(true, state.message || 'Restarting apcupsd…');
            }
        });
        
        this.socket.on('new_events', (events) => {
            debug.log('WebSocket new_events received:', events);
            this.events = [...events, ...this.events];
            // Update events display if events tab is active
            this.updateEventsTabRealTime(events);
        });
    }

    connectWebSocket() {
        if (this.socket) {
            this.socket.disconnect();
        }
        
        try {
            if (typeof io !== 'function') {
                throw new Error('The bundled Socket.IO client did not load');
            }
            this.socket = io(this.settings.wsUrl, {
                transports: ['polling', 'websocket'],  // Try polling first
                timeout: 120000,          // Increased to match server timeout
                pingInterval: 60000,      // Match server ping interval
                pingTimeout: 120000,      // Match server ping timeout
                forceNew: true,           // Force new connection
                reconnection: true,
                reconnectionDelay: 2000,
                reconnectionAttempts: 10,
                maxReconnectionAttempts: 20,
                path: '/socket.io/'       // Explicitly set path
            });
            
            // Setup event handlers
            this.setupSocketEventHandlers();
            
        } catch (error) {
            debug.error('Error connecting to WebSocket:', error);
            this.isConnected = false;
            this.updateConnectionStatus();
        }
    }
    
    updateConnectionStatus() {
        const dot = document.getElementById('connection-dot');
        const text = document.getElementById('connection-status');
        
        if (this.isRestarting) {
            dot.className = 'status-dot status-restarting';
            text.textContent = 'Restarting…';
        } else if (this.isConnected) {
            dot.className = 'status-dot status-online';
            text.textContent = 'Connected';
        } else {
            dot.className = 'status-dot status-offline';
            text.textContent = 'Disconnected';
        }
    }

    setRestartingState(restarting, message = 'Restarting…') {
        this.isRestarting = restarting;
        this.updateConnectionStatus();

        const statusText = document.getElementById('status-text');
        const statusBadge = document.getElementById('status-badge');
        if (restarting && statusText && statusBadge) {
            statusText.textContent = message;
            statusBadge.className = 'badge badge-warning';
        } else if (!restarting && this.currentData.status && statusText && statusBadge) {
            statusText.textContent = this.currentData.status;
            statusBadge.className = `badge ${this.getStatusBadgeClass(this.currentData.status)}`;
        }
    }
    
    updateLastUpdated() {
        const now = new Date();
        document.getElementById('last-updated').textContent = now.toLocaleTimeString();
    }
    
    async fetchInitialData() {
        try {
            const response = await fetch(`${this.settings.apiUrl}/api/current`);
            if (response.ok) {
                const data = await response.json();
                if (data && !data.stale && data.data_state !== 'reconnecting') {
                    this.currentData = data;
                    this.setRestartingState(false);
                    this.updateUI();
                    this.updateLastUpdated();
                } else {
                    this.setRestartingState(true, 'Reconnecting to UPS…');
                }
            }
        } catch (error) {
            debug.error('Error fetching initial data:', error);
        }
    }
    
    async fetchHistoryData() {
        try {
            const response = await fetch(`${this.settings.apiUrl}/api/history?hours=${this.settings.timeRange}&limit=${this.settings.dataPoints}`);
            if (response.ok) {
                this.historyData = await response.json();
                this.updateCharts();
            }
        } catch (error) {
            debug.error('Error fetching history data:', error);
        }
    }
    
    async fetchEvents() {
        try {
            const response = await fetch(`${this.settings.apiUrl}/api/events?limit=100`);
            if (response.ok) {
                this.events = await response.json();
                this.updateEventsDisplay();
            }
        } catch (error) {
            debug.error('Error fetching events:', error);
        }
    }
    
    async fetchBatteryData() {
        try {
            const [eventsResponse, statsResponse] = await Promise.all([
                fetch(`${this.settings.apiUrl}/api/battery-events?limit=50`),
                fetch(`${this.settings.apiUrl}/api/battery-stats?days=30`)
            ]);
            
            if (eventsResponse.ok) {
                this.batteryEvents = await eventsResponse.json();
                this.updateBatteryEventsDisplay();
            }
            
            if (statsResponse.ok) {
                this.batteryStats = await statsResponse.json();
                this.updateBatteryStatsDisplay();
            }
        } catch (error) {
            debug.error('Error fetching battery data:', error);
        }
    }
    
    updateUI() {
        const data = this.currentData;
        if (!data || data.stale || data.data_state === 'reconnecting') return;
        
        // Header info
        document.getElementById('ups-name').textContent = data.ups_name || 'Unknown UPS';
        document.getElementById('ups-model').textContent = data.model || '';
        
        // Status badge
        const statusBadge = document.getElementById('status-badge');
        const statusText = document.getElementById('status-text');
        statusText.textContent = data.status || 'Unknown';
        
        // Update badge class based on status
        statusBadge.className = `badge ${this.getStatusBadgeClass(data.status)}`;
        
        // Header metrics
        document.getElementById('header-battery').textContent = `${data.battery_charge ?? '—'}%`;
        document.getElementById('header-load').textContent = `${data.load_pct ?? '—'}%`;
        document.getElementById('header-temp').textContent = `${data.temperature ?? '—'}°C`;
        
        // Overview tab - Battery Status
        document.getElementById('battery-charge-percent').textContent = `${data.battery_charge || 0}%`;
        document.getElementById('battery-progress').style.width = `${data.battery_charge || 0}%`;
        document.getElementById('battery-progress').className = `progress-bar ${this.getBatteryProgressClass(data.battery_charge)}`;
        document.getElementById('time-remaining').textContent = `${data.time_left} min`;
        document.getElementById('battery-voltage').textContent = `${(data.battery_voltage || 0).toFixed(1)}V`;
        document.getElementById('battery-install-date').textContent = data.battery_date || 'Unknown';
        
        // Overview tab - Power Status
        document.getElementById('load-percent').textContent = `${data.load_pct || 0}%`;
        document.getElementById('load-progress').style.width = `${data.load_pct || 0}%`;
        document.getElementById('load-progress').className = `progress-bar ${this.getLoadProgressClass(data.load_pct)}`;
        document.getElementById('input-voltage').textContent = `${(data.line_voltage || 0).toFixed(1)}V`;
        document.getElementById('output-voltage').textContent = `${(data.output_voltage || 0).toFixed(1)}V`;
        document.getElementById('frequency').textContent = `${(data.frequency || 0).toFixed(1)}Hz`;
        document.getElementById('voltage-range').textContent = `${(data.min_line_v || 0).toFixed(0)}V - ${(data.max_line_v || 0).toFixed(0)}V`;
        
        // Overview tab - System Info
        document.getElementById('system-model').textContent = data.model || 'Unknown';
        document.getElementById('system-firmware').textContent = data.firmware || 'Unknown';
        document.getElementById('system-serial').textContent = data.serial_no || 'Unknown';
        document.getElementById('system-temperature').textContent = `${data.temperature || 0}°C`;
        document.getElementById('system-transfers').textContent = data.num_transfers || 0;
        document.getElementById('system-last-transfer').textContent = data.last_transfer || 'None';
        
        // Self test badge
        const selfTestBadge = document.getElementById('self-test-badge');
        selfTestBadge.textContent = data.self_test || 'Unknown';
        selfTestBadge.className = `badge ${this.getSelfTestBadgeClass(data.self_test)}`;
        
        // System tab - detailed info
        document.getElementById('detailed-ups-name').textContent = data.ups_name || 'Unknown';
        document.getElementById('detailed-model').textContent = data.model || 'Unknown';
        document.getElementById('detailed-serial').textContent = data.serial_no || 'Unknown';
        document.getElementById('detailed-firmware').textContent = data.firmware || 'Unknown';
        document.getElementById('detailed-driver').textContent = data.driver || 'Unknown';
        document.getElementById('detailed-hostname').textContent = data.hostname || 'Unknown';
        document.getElementById('detailed-start-time').textContent = data.start_time || 'Unknown';
        
        // System tab - configuration
        document.getElementById('min-battery-shutdown').textContent = `${data.min_battery_charge_shutdown || 0}%`;
        document.getElementById('min-time-shutdown').textContent = `${data.min_time_left_shutdown} min`;
        document.getElementById('max-time-battery').textContent = `${data.max_time_on_battery} min`;
        document.getElementById('low-battery-timeout').textContent = `${data.low_battery_timeout} min`;
        document.getElementById('required-return-charge').textContent = `${data.required_return_charge || 0}%`;
        document.getElementById('self-test-interval').textContent = `${Math.round((data.self_test_interval || 0) / 86400)} days`;
        
        // System tab - runtime stats
        document.getElementById('total-transfers').textContent = data.num_transfers || 0;
        document.getElementById('time-on-battery').textContent = this.formatTimeFromSeconds(data.time_on_battery);
        document.getElementById('cumulative-battery-time').textContent = this.formatTimeFromSeconds(this.batteryStats?.total_battery_time_seconds || data.cumulative_on_battery);
        document.getElementById('nominal-output-voltage').textContent = `${(data.nominal_output_voltage || 0).toFixed(0)}V`;
        document.getElementById('nominal-battery-voltage').textContent = `${(data.nominal_battery_voltage || 0).toFixed(0)}V`;
        document.getElementById('external-batteries').textContent = data.external_batteries || 0;
        document.getElementById('transfer-voltage-range').textContent = `${(data.min_line_v || 0).toFixed(0)}V - ${(data.max_line_v || 0).toFixed(0)}V`;
    }
    
    getStatusBadgeClass(status) {
        switch (status) {
            case 'ONLINE':
                return 'badge-success';
            case 'ONBATT':
                return 'badge-warning';
            case 'OFFLINE':
                return 'badge-error';
            default:
                return 'badge-default';
        }
    }
    
    getBatteryProgressClass(charge) {
        if (charge >= 80) return 'progress-success';
        if (charge >= 50) return 'progress-warning';
        return 'progress-error';
    }
    
    getLoadProgressClass(load) {
        if (load >= 80) return 'progress-error';
        if (load >= 60) return 'progress-warning';
        return 'progress-success';
    }
    
    formatTimeFromSeconds(seconds) {
        if (!seconds || seconds === 0) return '0 sec';
        
        const numSeconds = parseInt(seconds);
        
        if (numSeconds < 60) {
            return `${numSeconds} sec`;
        }
        
        const minutes = Math.floor(numSeconds / 60);
        const remainingSeconds = numSeconds % 60;
        
        if (minutes < 60) {
            if (remainingSeconds === 0) {
                return `${minutes} min`;
            }
            return `${minutes} min ${remainingSeconds} sec`;
        }
        
        const hours = Math.floor(minutes / 60);
        const remainingMinutes = minutes % 60;
        
        if (remainingMinutes === 0) {
            return `${hours} hr`;
        }
        return `${hours} hr ${remainingMinutes} min`;
    }
    
    getSelfTestBadgeClass(selfTest) {
        if (selfTest === 'OK') return 'badge-success';
        if (selfTest === 'NO') return 'badge-warning';
        return 'badge-error';
    }
    
    initializeCharts() {
        Chart.defaults.color = '#a1a1aa';
        Chart.defaults.borderColor = '#27272a';
        Chart.defaults.backgroundColor = '#1a1a1a';
        
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 250
            },
            interaction: {
                mode: 'index',
                intersect: false
            },
            normalized: true,
            parsing: false,
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'minute',
                        tooltipFormat: 'PPpp',
                        displayFormats: {
                            minute: 'h:mm a',
                            hour: 'HH:mm',
                            day: 'MM/DD'
                        }
                    },
                    grid: {
                        color: '#27272a'
                    },
                    ticks: {
                        color: '#a1a1aa',
                        maxRotation: 0,
                        autoSkipPadding: 18
                    }
                },
                y: {
                    grid: {
                        color: '#27272a'
                    },
                    ticks: {
                        color: '#a1a1aa',
                        maxTicksLimit: 6
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    displayColors: false
                },
                decimation: {
                    enabled: true,
                    algorithm: 'min-max'
                }
            }
        };
        
        // Battery chart
        this.charts.battery = new Chart(document.getElementById('battery-chart'), {
            type: 'line',
            data: {
                datasets: [{
                    label: 'Battery Charge (%)',
                    data: [],
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true,
                    tension: 0.25,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    spanGaps: false
                }]
            },
            options: {
                ...chartOptions,
                scales: {
                    ...chartOptions.scales,
                    y: {
                        ...chartOptions.scales.y,
                        suggestedMin: 80,
                        suggestedMax: 100
                    }
                }
            }
        });
        
        // Load chart
        this.charts.load = new Chart(document.getElementById('load-chart'), {
            type: 'line',
            data: {
                datasets: [{
                    label: 'Load (%)',
                    data: [],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.25,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    spanGaps: false
                }]
            },
            options: {
                ...chartOptions,
                scales: {
                    ...chartOptions.scales,
                    y: {
                        ...chartOptions.scales.y,
                        beginAtZero: true,
                        suggestedMax: 10
                    }
                }
            }
        });
        
        // Voltage chart
        this.charts.voltage = new Chart(document.getElementById('voltage-chart'), {
            type: 'line',
            data: {
                datasets: [{
                    label: 'Line Voltage',
                    data: [],
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    fill: false,
                    tension: 0.25,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    spanGaps: false
                }]
            },
            options: chartOptions
        });
        
        // Temperature chart
        this.charts.temperature = new Chart(document.getElementById('temperature-chart'), {
            type: 'line',
            data: {
                datasets: [{
                    label: 'Temperature',
                    data: [],
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    fill: false,
                    tension: 0.25,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    spanGaps: false
                }]
            },
            options: chartOptions
        });
    }
    
    updateCharts() {
        if (!this.historyData || this.historyData.length === 0) return;
        
        const data = this.historyData
            .filter(item => !item.stale && item.using_mock_data !== true)
            .map(item => ({
                x: new Date(item.timestamp).getTime(),
                battery: this.validMetric(item.battery_charge, 0, 100),
                load: this.validMetric(item.load_pct, 0, 100),
                voltage: this.validMetric(item.line_voltage, 1),
                temperature: this.validMetric(item.temperature, -50, 100)
            }))
            .filter(item => Number.isFinite(item.x))
            .sort((a, b) => a.x - b.x);
        
        // Update battery chart
        this.charts.battery.data.datasets[0].data = data.map(d => ({
            x: d.x,
            y: d.battery
        }));
        this.charts.battery.update();
        
        // Update load chart
        this.charts.load.data.datasets[0].data = data.map(d => ({
            x: d.x,
            y: d.load
        }));
        this.charts.load.update();
        
        // Update voltage chart
        this.charts.voltage.data.datasets[0].data = data.map(d => ({
            x: d.x,
            y: d.voltage
        }));
        this.charts.voltage.update();
        
        // Update temperature chart
        this.charts.temperature.data.datasets[0].data = data.map(d => ({
            x: d.x,
            y: d.temperature
        }));
        this.charts.temperature.update();
    }
    
    updateChartsWithRealTimeData(data) {
        if (!this.charts.battery || !data || data.stale || data.data_state !== 'live') return;
        
        // Use current time if no timestamp is provided
        const currentTime = data.timestamp ? new Date(data.timestamp).getTime() : Date.now();
        const cutoff = Date.now() - (Number(this.settings.timeRange) * 60 * 60 * 1000);
        
        // Update battery chart
        if (this.charts.battery) {
            const batteryData = this.charts.battery.data.datasets[0].data;
            batteryData.push({
                x: currentTime,
                y: this.validMetric(data.battery_charge, 0, 100)
            });
            
            this.trimChartData(batteryData, cutoff);
            
            this.charts.battery.update('none');
        }
        
        // Update load chart
        if (this.charts.load) {
            const loadData = this.charts.load.data.datasets[0].data;
            loadData.push({
                x: currentTime,
                y: this.validMetric(data.load_pct, 0, 100)
            });
            
            this.trimChartData(loadData, cutoff);
            
            this.charts.load.update('none');
        }
        
        // Update voltage chart
        if (this.charts.voltage) {
            const voltageData = this.charts.voltage.data.datasets[0].data;
            voltageData.push({
                x: currentTime,
                y: this.validMetric(data.line_voltage, 1)
            });
            
            this.trimChartData(voltageData, cutoff);
            
            this.charts.voltage.update('none');
        }
        
        // Update temperature chart
        if (this.charts.temperature) {
            const tempData = this.charts.temperature.data.datasets[0].data;
            tempData.push({
                x: currentTime,
                y: this.validMetric(data.temperature, -50, 100)
            });
            
            this.trimChartData(tempData, cutoff);
            
            this.charts.temperature.update('none');
        }
    }

    validMetric(value, min = -Infinity, max = Infinity) {
        const number = Number(value);
        return Number.isFinite(number) && number >= min && number <= max ? number : null;
    }

    trimChartData(points, cutoff) {
        while (points.length && new Date(points[0].x).getTime() < cutoff) {
            points.shift();
        }
        if (points.length > 5000) {
            points.splice(0, points.length - 5000);
        }
    }
    
    updateEventsDisplay() {
        const container = document.getElementById('system-events');
        container.innerHTML = '';
        
        this.events.forEach(event => {
            const eventDiv = document.createElement('div');
            eventDiv.className = `card p-4 flex items-start gap-3`;
            
            const date = new Date(event.timestamp).toLocaleString();
            eventDiv.innerHTML = `
                <i data-lucide="${this.getEventIcon(event.severity)}" class="w-5 h-5 ${this.getEventIconClass(event.severity)} flex-shrink-0 mt-0.5"></i>
                <div class="flex-1">
                    <div class="flex items-center gap-2 mb-1">
                        <span class="badge ${this.getEventBadgeClass(event.severity)}">${event.severity}</span>
                        <span class="font-medium">${event.event_type}</span>
                        <span class="text-xs text-muted ml-auto">${date}</span>
                    </div>
                    <p class="text-sm text-secondary">${event.message}</p>
                </div>
            `;
            
            container.appendChild(eventDiv);
        });
        
        // Initialize icons for new content
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
    
    updateEventsTabRealTime(newEvents) {
        debug.log('updateEventsTabRealTime called with:', newEvents);
        
        // Check if events tab is active
        const activeTab = document.querySelector('.nav-link.active')?.getAttribute('data-tab');
        debug.log('Current active tab:', activeTab);
        
        // Always update the events count/badge regardless of active tab
        const eventsCountBadge = document.querySelector('[data-events-count]');
        if (eventsCountBadge) {
            eventsCountBadge.textContent = this.events.length;
        }
        
        // Always update the events display since it appears on both overview and events tabs
        debug.log('Updating events display for all tabs with new events');
        this.updateEventsDisplay();
        
        // Only add flash animation if events tab is active
        if (activeTab !== 'events') {
            debug.log('Events tab not active, updated display but skipping flash animation');
            return;
        }
        
        debug.log('Events tab active, adding flash animation');
        
        // Add flash animation to newly added events
        const container = document.getElementById('system-events');
        const newEventElements = container.querySelectorAll('.card');
        
        // Flash the first few events (corresponding to the new events count)
        for (let i = 0; i < Math.min(newEvents.length, newEventElements.length); i++) {
            const eventElement = newEventElements[i];
            
            // Add flash animation class
            eventElement.style.backgroundColor = '#10b981';  // Green flash
            eventElement.style.transform = 'scale(1.02)';
            eventElement.style.transition = 'background-color 0.5s ease, transform 0.3s ease';
            
            // Remove flash after animation
            setTimeout(() => {
                eventElement.style.backgroundColor = '';
                eventElement.style.transform = '';
            }, 1000);
        }
    }
    
    updateBatteryEventsDisplay() {
        const container = document.getElementById('battery-events');
        container.innerHTML = '';
        
        this.batteryEvents.forEach(event => {
            const eventDiv = document.createElement('div');
            eventDiv.className = 'card p-4';
            
            const startDate = new Date(event.start_timestamp).toLocaleString();
            const duration = Math.round(event.duration_seconds / 60);
            const drainRate = event.drain_rate_percent_per_hour.toFixed(2);
            
            eventDiv.innerHTML = `
                <div class="flex items-center justify-between mb-2">
                    <span class="font-medium flex items-center gap-2">
                        <i data-lucide="battery" class="w-4 h-4 text-warning"></i>
                        Battery Event
                    </span>
                    <span class="text-xs text-muted">${startDate}</span>
                </div>
                <div class="grid grid-cols-2 gap-4 text-sm">
                    <div>
                        <span class="text-muted">Duration</span>
                        <p class="font-semibold">${duration} min</p>
                    </div>
                    <div>
                        <span class="text-muted">Drain Rate</span>
                        <p class="font-semibold">${drainRate}%/hour</p>
                    </div>
                    <div>
                        <span class="text-muted">Battery Change</span>
                        <p class="font-semibold">${event.start_battery_percent}% → ${event.end_battery_percent}%</p>
                    </div>
                    <div>
                        <span class="text-muted">Trigger</span>
                        <p class="font-semibold text-xs">${event.trigger_reason}</p>
                    </div>
                </div>
            `;
            
            container.appendChild(eventDiv);
        });
        
        // Initialize icons for new content
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
    
    updateBatteryStatsDisplay() {
        const stats = this.batteryStats;
        
        // Battery Performance stats
        document.getElementById('battery-total-events').textContent = stats.total_events || 0;
        document.getElementById('battery-avg-duration').textContent = this.formatTimeFromSeconds(stats.avg_duration_seconds || 0);
        document.getElementById('battery-avg-drain').textContent = `${(stats.avg_drain_rate || 0).toFixed(2)}%/hour`;
        document.getElementById('battery-max-drain').textContent = `${(stats.max_drain_rate || 0).toFixed(2)}%/hour`;
        
        // Usage Statistics
        document.getElementById('battery-total-time').textContent = this.formatTimeFromSeconds(stats.total_battery_time_seconds || 0);
        document.getElementById('battery-avg-drained').textContent = `${(stats.avg_percent_drained || 0).toFixed(1)}%`;
        document.getElementById('battery-min-drain').textContent = `${(stats.min_drain_rate || 0).toFixed(2)}%/hour`;
        
        // Power Issues breakdown
        const powerIssuesContainer = document.getElementById('power-issues');
        powerIssuesContainer.innerHTML = '';
        
        if (stats.trigger_breakdown) {
            Object.entries(stats.trigger_breakdown).forEach(([trigger, count]) => {
                const issueDiv = document.createElement('div');
                issueDiv.className = 'flex justify-between text-sm';
                issueDiv.innerHTML = `
                    <span class="text-muted">${trigger}</span>
                    <span class="font-semibold">${count}</span>
                `;
                powerIssuesContainer.appendChild(issueDiv);
            });
        }
    }
    
    updateBatteryTabRealTime(data) {
        // Only update if battery tab is active
        const activeTab = document.querySelector('.nav-link.active')?.getAttribute('data-tab');
        if (activeTab !== 'battery') {
            return;
        }
        
        // Check if there are new battery events to fetch
        // This is triggered by battery status changes or low battery conditions
        if (this.shouldRefreshBatteryEvents(data)) {
            // Rate limit battery data fetching to prevent duplicates
            const now = Date.now();
            if (now - this.lastBatteryDataFetch > 10000) { // 10 second minimum interval
                this.lastBatteryDataFetch = now;
                this.fetchBatteryData();
            }
        }
        
        // Update real-time battery status in the battery tab if it has live status indicators
        this.updateBatteryTabStatus(data);
    }
    
    shouldRefreshBatteryEvents(data) {
        // Refresh battery events when:
        // 1. UPS transitions between ONLINE/ONBATT status
        // 2. Battery charge drops significantly (indicating new drain event)
        // 3. Battery charge returns to high level (indicating charge completion)
        
        const currentStatus = data.status;
        const currentBatteryCharge = data.battery_charge || 0;
        
        // Check for status change that would create battery events
        if (this.lastBatteryStatus && this.lastBatteryStatus !== currentStatus) {
            if ((this.lastBatteryStatus === 'ONLINE' && currentStatus === 'ONBATT') ||
                (this.lastBatteryStatus === 'ONBATT' && currentStatus === 'ONLINE')) {
                this.lastBatteryStatus = currentStatus;
                return true;
            }
        }
        
        // Check for significant battery charge changes
        if (this.lastBatteryCharge !== undefined) {
            const chargeDiff = Math.abs(currentBatteryCharge - this.lastBatteryCharge);
            // Refresh if battery charge changes by more than 5% or battery is critically low
            if (chargeDiff > 5 || currentBatteryCharge < 20) {
                this.lastBatteryCharge = currentBatteryCharge;
                return true;
            }
        }
        
        // Store current values for next comparison
        this.lastBatteryStatus = currentStatus;
        this.lastBatteryCharge = currentBatteryCharge;
        
        return false;
    }
    
    updateBatteryTabStatus(data) {
        // Update any live status indicators in the battery tab
        // This could include current battery level, status indicators, etc.
        
        // Update battery charge indicators if they exist in the battery tab
        const batteryTabChargeElements = document.querySelectorAll('[data-battery-charge]');
        batteryTabChargeElements.forEach(element => {
            element.textContent = `${data.battery_charge || 0}%`;
        });
        
        // Update battery status indicators if they exist in the battery tab  
        const batteryTabStatusElements = document.querySelectorAll('[data-battery-status]');
        batteryTabStatusElements.forEach(element => {
            element.textContent = data.status || 'Unknown';
            element.className = `badge ${this.getStatusBadgeClass(data.status)}`;
        });
        
        // Update time remaining indicators if they exist in the battery tab
        const batteryTabTimeElements = document.querySelectorAll('[data-battery-time]');
        batteryTabTimeElements.forEach(element => {
            element.textContent = `${data.time_left || 0} min`;
        });
    }
    
    getEventIcon(severity) {
        switch (severity) {
            case 'CRITICAL':
                return 'alert-circle';
            case 'WARNING':
                return 'alert-triangle';
            case 'INFO':
                return 'info';
            default:
                return 'circle';
        }
    }
    
    getEventIconClass(severity) {
        switch (severity) {
            case 'CRITICAL':
                return 'text-error';
            case 'WARNING':
                return 'text-warning';
            case 'INFO':
                return 'text-info';
            default:
                return 'text-secondary';
        }
    }
    
    getEventBadgeClass(severity) {
        switch (severity) {
            case 'CRITICAL':
                return 'badge-error';
            case 'WARNING':
                return 'badge-warning';
            case 'INFO':
                return 'badge-info';
            default:
                return 'badge-default';
        }
    }
    
    handleAlerts(alerts) {
        const container = document.getElementById('alerts-container');
        
        alerts.forEach(alert => {
            const alertDiv = document.createElement('div');
            alertDiv.className = `alert ${this.getAlertClass(alert.severity)}`;
            alertDiv.innerHTML = `
                <i data-lucide="${this.getEventIcon(alert.severity)}" class="w-5 h-5 flex-shrink-0"></i>
                <div>
                    <strong>${alert.event_type}</strong>
                    <p>${alert.message}</p>
                </div>
            `;
            
            container.appendChild(alertDiv);
            
            // Auto-remove alert after 10 seconds
            setTimeout(() => {
                if (alertDiv.parentNode) {
                    alertDiv.parentNode.removeChild(alertDiv);
                }
            }, 10000);
        });
        
        // Initialize icons for new content
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
    
    getAlertClass(severity) {
        switch (severity) {
            case 'CRITICAL':
                return 'alert-error';
            case 'WARNING':
                return 'alert-warning';
            case 'INFO':
                return 'alert-info';
            default:
                return 'alert-success';
        }
    }
    
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 alert ${this.getAlertClass(type.toUpperCase())}`;
        notification.innerHTML = `
            <i data-lucide="${this.getEventIcon(type.toUpperCase())}" class="w-5 h-5 flex-shrink-0"></i>
            <span>${message}</span>
        `;
        
        document.body.appendChild(notification);
        
        // Initialize icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
        
        // Remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
    }
    
    
    // Configuration tab methods
    setupConfigurationEventListeners() {
        // Install apcupsd button
        document.getElementById('install-apcupsd').addEventListener('click', () => {
            this.installApcupsd();
        });
        
        // Restart apcupsd button
        document.getElementById('restart-apcupsd').addEventListener('click', () => {
            this.restartApcupsd();
        });
        
        // Detect devices button
        document.getElementById('detect-devices').addEventListener('click', () => {
            this.detectUpsDevices();
        });
        
        // Save configuration button
        document.getElementById('save-config').addEventListener('click', () => {
            this.saveUpsConfiguration();
        });
        
        // Reset configuration button
        document.getElementById('reset-config').addEventListener('click', () => {
            this.resetUpsConfiguration();
        });
    }
    
    async loadConfigurationData() {
        try {
            // Load apcupsd status
            const statusResponse = await fetch(`${this.settings.apiUrl}/api/apcupsd/status`);
            const statusData = await statusResponse.json();
            this.updateApcupsdStatus(statusData);
            
            // Load current configuration values
            const currentConfigResponse = await fetch(`${this.settings.apiUrl}/api/apcupsd/current-config`);
            const currentConfigData = await currentConfigResponse.json();
            this.loadCurrentConfiguration(currentConfigData);
            
            // Load configuration template for validation/defaults
            const templateResponse = await fetch(`${this.settings.apiUrl}/api/apcupsd/config-template`);
            const templateData = await templateResponse.json();
            this.loadConfigurationTemplate(templateData);
            
        } catch (error) {
            debug.error('Error loading configuration data:', error);
            this.showNotification('Error loading configuration data', 'error');
        }
    }
    
    updateApcupsdStatus(statusData) {
        const statusColor = (value) => value ? 'text-success' : 'text-error';
        
        document.getElementById('apcupsd-installed').innerHTML = 
            `<span class="${statusColor(statusData.installed)}">${statusData.installed ? '✓ Installed' : '✗ Not Installed'}</span>`;
        
        document.getElementById('apcupsd-configured').innerHTML = 
            `<span class="${statusColor(statusData.configured)}">${statusData.configured ? '✓ Configured' : '✗ Not Configured'}</span>`;
        
        document.getElementById('apcupsd-active').innerHTML = 
            `<span class="${statusColor(statusData.active)}">${statusData.active ? '✓ Running' : '✗ Not Running'}</span>`;
        
        document.getElementById('apcupsd-enabled').innerHTML = 
            `<span class="${statusColor(statusData.enabled)}">${statusData.enabled ? '✓ Enabled' : '✗ Disabled'}</span>`;

        if (!statusData.communication_ok) {
            const deviceHint = statusData.configured_device && !statusData.device_present
                ? ` Configured device ${statusData.configured_device} is not present.`
                : '';
            this.showNotification(`UPS communication problem: ${statusData.communication_status || 'unknown error'}.${deviceHint}`, 'error');
        }
        
        // Update button states
        const installBtn = document.getElementById('install-apcupsd');
        if (statusData.installed) {
            installBtn.disabled = true;
            installBtn.innerHTML = '<i data-lucide="check" class="w-4 h-4"></i> Already Installed';
        } else {
            installBtn.disabled = false;
            installBtn.innerHTML = '<i data-lucide="download" class="w-4 h-4"></i> Install apcupsd';
        }
    }
    
    loadCurrentConfiguration(currentConfig) {
        // Load current configuration values into form fields
        if (currentConfig) {
            // Map configuration keys to form field IDs
            const configFieldMapping = {
                'UPSNAME': 'config-upsname',
                'UPSCABLE': 'config-upscable',
                'UPSTYPE': 'config-upstype',
                'DEVICE': 'config-device',
                'BATTERYLEVEL': 'config-batterylevel',
                'MINUTES': 'config-minutes',
                'ONBATTERYDELAY': 'config-onbatterydelay',
                'TIMEOUT': 'config-timeout',
                'NETSERVER': 'config-netserver',
                'NISIP': 'config-nisip',
                'NISPORT': 'config-nisport'
            };
            
            Object.keys(configFieldMapping).forEach(configKey => {
                const element = document.getElementById(configFieldMapping[configKey]);
                if (element && currentConfig[configKey] !== undefined) {
                    element.value = currentConfig[configKey];
                }
            });
        }
    }
    
    loadConfigurationTemplate(templateData) {
        // Load default values from template (only if current config is not available)
        if (templateData.basic) {
            Object.keys(templateData.basic).forEach(key => {
                const element = document.getElementById(`config-${key.toLowerCase()}`);
                if (element && element.value === '') {
                    element.value = templateData.basic[key].value;
                }
            });
        }
        
        if (templateData.power) {
            Object.keys(templateData.power).forEach(key => {
                const element = document.getElementById(`config-${key.toLowerCase()}`);
                if (element && element.value === '') {
                    element.value = templateData.power[key].value;
                }
            });
        }
        
        if (templateData.network) {
            Object.keys(templateData.network).forEach(key => {
                const element = document.getElementById(`config-${key.toLowerCase()}`);
                if (element && element.value === '') {
                    element.value = templateData.network[key].value;
                }
            });
        }
    }
    
    async installApcupsd() {
        try {
            const response = await fetch(`${this.settings.apiUrl}/api/apcupsd/install`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('apcupsd installed successfully!', 'success');
                this.loadConfigurationData(); // Refresh status
            } else {
                this.showNotification(`Installation failed: ${result.message}`, 'error');
            }
        } catch (error) {
            debug.error('Error installing apcupsd:', error);
            this.showNotification('Error installing apcupsd', 'error');
        }
    }
    
    async restartApcupsd() {
        this.setRestartingState(true, 'Restarting apcupsd…');
        try {
            const response = await fetch(`${this.settings.apiUrl}/api/apcupsd/restart`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('apcupsd restart requested; waiting for UPS data…', 'success');
                this.loadConfigurationData(); // Refresh status
                await this.pollForLiveData();
            } else {
                this.setRestartingState(false);
                this.showNotification(`Restart failed: ${result.message}`, 'error');
            }
        } catch (error) {
            this.setRestartingState(false);
            debug.error('Error restarting apcupsd:', error);
            this.showNotification('Error restarting apcupsd', 'error');
        }
    }

    async pollForLiveData(timeoutMs = 30000) {
        const deadline = Date.now() + timeoutMs;
        while (Date.now() < deadline) {
            try {
                const response = await fetch(`${this.settings.apiUrl}/api/current`, {
                    cache: 'no-store'
                });
                if (response.ok) {
                    const data = await response.json();
                    if (data && !data.stale && data.data_state === 'live') {
                        this.currentData = data;
                        this.setRestartingState(false);
                        this.updateUI();
                        this.updateLastUpdated();
                        return true;
                    }
                }
            } catch (error) {
                debug.warn('Waiting for apcupsd to return:', error);
            }
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
        this.setRestartingState(true, 'UPS reconnect delayed…');
        this.showNotification('apcupsd restarted, but UPS data is still reconnecting.', 'warning');
        return false;
    }
    
    async detectUpsDevices() {
        try {
            const response = await fetch(`${this.settings.apiUrl}/api/apcupsd/detect-devices`);
            const result = await response.json();
            const devices = Array.isArray(result) ? result : (result.devices || []);
            
            const devicesContainer = document.getElementById('detected-devices');
            devicesContainer.innerHTML = '';
            
            if (devices.length > 0) {
                devices.forEach(device => {
                    const deviceDiv = document.createElement('div');
                    deviceDiv.className = 'p-2 bg-muted rounded border';
                    deviceDiv.innerHTML = `
                        <div class="text-sm font-medium">${device.type.toUpperCase()} Device</div>
                        <div class="text-xs text-muted">${device.description}</div>
                        ${device.device ? `<div class="text-xs font-mono">${device.device}</div>` : ''}
                        <button class="btn btn-sm btn-secondary mt-2" onclick="upsMonitor.selectDevice('${device.device}', '${device.cable}', '${device.upstype || device.type}')">
                            Select This Device
                        </button>
                    `;
                    devicesContainer.appendChild(deviceDiv);
                });
            } else {
                devicesContainer.innerHTML = '<p class="text-muted text-sm">No UPS devices detected</p>';
            }
        } catch (error) {
            debug.error('Error detecting devices:', error);
            this.showNotification('Error detecting devices', 'error');
        }
    }
    
    selectDevice(device, cable, type) {
        document.getElementById('config-device').value = device || '';
        document.getElementById('config-upscable').value = cable || 'usb';
        document.getElementById('config-upstype').value = type || 'usb';
        this.showNotification('Device selected and configuration updated', 'success');
    }
    
    async saveUpsConfiguration() {
        this.setRestartingState(true, 'Applying configuration…');
        try {
            const config = {
                UPSNAME: document.getElementById('config-upsname').value,
                UPSCABLE: document.getElementById('config-upscable').value,
                UPSTYPE: document.getElementById('config-upstype').value,
                DEVICE: document.getElementById('config-device').value,
                BATTERYLEVEL: document.getElementById('config-batterylevel').value,
                MINUTES: document.getElementById('config-minutes').value,
                ONBATTERYDELAY: document.getElementById('config-onbatterydelay').value,
                TIMEOUT: document.getElementById('config-timeout').value,
                NETSERVER: document.getElementById('config-netserver').value,
                NISIP: document.getElementById('config-nisip').value,
                NISPORT: document.getElementById('config-nisport').value
            };
            
            // Save the configuration (validation is done server-side)
            const response = await fetch(`${this.settings.apiUrl}/api/apcupsd/configure`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('Configuration saved; waiting for UPS data…', 'success');
                this.loadConfigurationData(); // Refresh status
                await this.pollForLiveData();
            } else {
                this.setRestartingState(false);
                this.showNotification(`Configuration failed: ${result.message}`, 'error');
            }
        } catch (error) {
            this.setRestartingState(false);
            debug.error('Error saving configuration:', error);
            this.showNotification('Error saving configuration', 'error');
        }
    }
    
    resetUpsConfiguration() {
        if (confirm('Are you sure you want to reset the configuration to defaults?')) {
            this.loadConfigurationData(); // Reload defaults
            this.showNotification('Configuration reset to defaults', 'success');
        }
    }

    // Historic Data Tab Methods
    setupHistoricDataEventListeners() {
        // Filter button
        document.getElementById('filter-historic-data').addEventListener('click', () => {
            this.filterHistoricData();
        });
        
        // Export button
        document.getElementById('export-historic-data').addEventListener('click', () => {
            this.exportHistoricData();
        });
        
        // Pagination controls
        document.getElementById('historic-prev-page').addEventListener('click', () => {
            if (this.historicData.currentPage > 1) {
                this.historicData.currentPage--;
                this.loadHistoricData();
            }
        });
        
        document.getElementById('historic-next-page').addEventListener('click', () => {
            const maxPages = Math.ceil(this.historicData.totalRecords / this.historicData.rowsPerPage);
            if (this.historicData.currentPage < maxPages) {
                this.historicData.currentPage++;
                this.loadHistoricData();
            }
        });
        
        // Rows per page change
        document.getElementById('historic-rows-per-page').addEventListener('change', (e) => {
            this.historicData.rowsPerPage = parseInt(e.target.value);
            this.historicData.currentPage = 1;
            this.loadHistoricData();
        });
    }
    
    loadHistoricDataTab() {
        // Set default date range to last 24 hours with future buffer for real-time data
        const now = new Date();
        const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        const futureBuffer = new Date(now.getTime() + 60 * 60 * 1000); // 1 hour in future for real-time updates
        
        document.getElementById('historic-date-from').value = this.formatDateTimeLocal(yesterday);
        document.getElementById('historic-date-to').value = this.formatDateTimeLocal(now);
        
        this.historicData.filters.dateFrom = yesterday;
        this.historicData.filters.dateTo = futureBuffer; // Use future buffer internally for real-time updates
        this.historicData.currentPage = 1;
        
        debug.log('Historic data tab loaded with filters:', {
            dateFrom: this.historicData.filters.dateFrom.toISOString(),
            dateTo: this.historicData.filters.dateTo.toISOString()
        });
        
        this.loadHistoricData();
    }
    
    async loadHistoricData() {
        try {
            const params = new URLSearchParams({
                limit: this.historicData.rowsPerPage * 10 // Load more data since API doesn't support pagination
            });
            
            // Calculate hours from date range
            let hours = 24; // default to 24 hours
            if (this.historicData.filters.dateFrom && this.historicData.filters.dateTo) {
                const timeDiff = this.historicData.filters.dateTo - this.historicData.filters.dateFrom;
                hours = timeDiff / (1000 * 60 * 60); // convert to hours
            }
            params.append('hours', hours);
            
            const response = await fetch(`${this.settings.apiUrl}/api/history?${params}`);
            if (response.ok) {
                const allData = await response.json();
                
                // Filter data based on date range if specified
                let filteredData = allData;
                if (this.historicData.filters.dateFrom || this.historicData.filters.dateTo) {
                    filteredData = allData.filter(record => {
                        const recordDate = new Date(record.timestamp);
                        if (this.historicData.filters.dateFrom && recordDate < this.historicData.filters.dateFrom) {
                            return false;
                        }
                        if (this.historicData.filters.dateTo && recordDate > this.historicData.filters.dateTo) {
                            return false;
                        }
                        return true;
                    });
                }
                
                // Data is already sorted by SQL query (timestamp DESC)
                
                // Store all filtered data for real-time updates
                this.historicData.allData = filteredData;
                
                // Apply client-side pagination
                this.historicData.totalRecords = filteredData.length;
                const startIndex = (this.historicData.currentPage - 1) * this.historicData.rowsPerPage;
                const endIndex = startIndex + this.historicData.rowsPerPage;
                this.historicData.data = filteredData.slice(startIndex, endIndex);
                
                this.updateHistoricDataTable();
                this.updateHistoricPaginationControls();
            }
        } catch (error) {
            debug.error('Error loading historic data:', error);
            this.showNotification('Error loading historic data', 'error');
        }
    }
    
    filterHistoricData() {
        const fromInput = document.getElementById('historic-date-from');
        const toInput = document.getElementById('historic-date-to');
        
        this.historicData.filters.dateFrom = fromInput.value ? new Date(fromInput.value) : null;
        
        // Add future buffer to dateTo for real-time updates, or use null for no upper limit
        if (toInput.value) {
            const userToDate = new Date(toInput.value);
            const now = new Date();
            
            // If user selected "to" date is recent (within 24 hours), add future buffer for real-time
            if (userToDate.getTime() >= now.getTime() - 24 * 60 * 60 * 1000) {
                this.historicData.filters.dateTo = new Date(userToDate.getTime() + 60 * 60 * 1000); // 1 hour buffer
            } else {
                this.historicData.filters.dateTo = userToDate;
            }
        } else {
            this.historicData.filters.dateTo = null;
        }
        
        this.historicData.currentPage = 1;
        
        debug.log('Manual filter applied:', {
            dateFrom: this.historicData.filters.dateFrom ? this.historicData.filters.dateFrom.toISOString() : null,
            dateTo: this.historicData.filters.dateTo ? this.historicData.filters.dateTo.toISOString() : null
        });
        
        this.loadHistoricData();
    }
    
    updateHistoricDataTable() {
        const tbody = document.getElementById('historic-data-table-body');
        tbody.innerHTML = '';
        
        this.historicData.data.forEach((record) => {
            const row = document.createElement('tr');
            
            // Base row styling
            row.className = 'border-b border-border hover:bg-bg-muted transition-colors duration-300';
            
            // Add flash animation for new records
            if (record.isNewRecord) {
                row.classList.add('new-record-flash');
                row.style.backgroundColor = 'rgba(16, 185, 129, 0.3)'; // Brighter green flash
                row.style.transform = 'scale(1.01)'; // Slight scale effect
                row.style.transition = 'all 1200ms ease-out';
                
                // Remove the flash after 1.2 seconds
                setTimeout(() => {
                    row.style.backgroundColor = '';
                    row.style.borderLeft = '';
                    row.style.transform = '';
                    row.classList.remove('new-record-flash');
                }, 1200);
                
                // Clear the isNewRecord flag so it doesn't flash again on subsequent updates
                record.isNewRecord = false;
                
                debug.log('Applied flash animation to new record:', record.timestamp);
            }
            
            const formatDate = (timestamp) => {
                return new Date(timestamp).toLocaleString('en-US', {
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                });
            };
            
            row.innerHTML = `
                <td class="py-2 px-4 font-mono text-xs">${formatDate(record.timestamp)}</td>
                <td class="py-2 px-4">
                    <span class="badge ${this.getStatusBadgeClass(record.status)}">${record.status || 'Unknown'}</span>
                </td>
                <td class="py-2 px-4">${record.battery_charge || 0}%</td>
                <td class="py-2 px-4">${record.load_pct || 0}%</td>
                <td class="py-2 px-4">${(record.line_voltage || 0).toFixed(1)}V</td>
                <td class="py-2 px-4">${(record.output_voltage || 0).toFixed(1)}V</td>
                <td class="py-2 px-4">${record.temperature || 0}°C</td>
                <td class="py-2 px-4">${record.time_left} min</td>
            `;
            
            tbody.appendChild(row);
        });
        
        document.getElementById('historic-record-count').textContent = this.historicData.totalRecords;
    }
    
    updateHistoricPaginationControls() {
        const maxPages = Math.ceil(this.historicData.totalRecords / this.historicData.rowsPerPage);
        
        document.getElementById('historic-prev-page').disabled = this.historicData.currentPage <= 1;
        document.getElementById('historic-next-page').disabled = this.historicData.currentPage >= maxPages;
        document.getElementById('historic-page-info').textContent = `Page ${this.historicData.currentPage} of ${maxPages}`;
    }
    
    async exportHistoricData() {
        try {
            const params = new URLSearchParams();
            
            // Calculate hours from date range
            let hours = 24; // default to 24 hours
            if (this.historicData.filters.dateFrom && this.historicData.filters.dateTo) {
                const timeDiff = this.historicData.filters.dateTo - this.historicData.filters.dateFrom;
                hours = timeDiff / (1000 * 60 * 60); // convert to hours
                params.append('from', this.historicData.filters.dateFrom.toISOString());
                params.append('to', this.historicData.filters.dateTo.toISOString());
            }
            params.append('hours', hours);
            params.append('limit', 10000); // Large limit for export
            
            const response = await fetch(`${this.settings.apiUrl}/api/export/csv?${params}`);
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `ups-historic-data-${new Date().toISOString().split('T')[0]}.csv`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                this.showNotification('Historic data exported successfully', 'success');
            } else {
                throw new Error('Export request failed');
            }
        } catch (error) {
            debug.error('Error exporting historic data:', error);
            this.showNotification('Error exporting historic data', 'error');
        }
    }
    
    formatDateTimeLocal(date) {
        const pad = (num) => num.toString().padStart(2, '0');
        return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
    }

    updateHistoricDataRealTime(newData) {
        debug.log('updateHistoricDataRealTime called with data:', newData);
        
        // Only update if historic tab is active
        const historicTab = document.getElementById('historic-tab');
        const isActive = historicTab && historicTab.classList.contains('active');
        debug.log('Historic tab active:', isActive);
        
        if (!isActive) {
            debug.log('Historic tab not active, skipping update');
            return;
        }

        // Initialize allData if it doesn't exist
        if (!this.historicData.allData) {
            this.historicData.allData = [];
            debug.log('Initialized allData array');
        }

        // Create a new record from the current data
        const newRecord = {
            id: Date.now(), // Use timestamp as ID
            timestamp: newData.timestamp || new Date().toISOString(),
            status: newData.status,
            battery_charge: newData.battery_charge,
            load_pct: newData.load_pct,
            line_voltage: newData.line_voltage,
            output_voltage: newData.output_voltage,
            temperature: newData.temperature,
            time_left: newData.time_left,
            isNewRecord: true // Mark as new for flash animation
        };

        // Check for duplicates (prevent adding the same data within 5 seconds)
        const fiveSecondsAgo = Date.now() - 5000;
        const isDuplicate = this.historicData.allData.some(record => {
            const recordTime = new Date(record.timestamp).getTime();
            return recordTime > fiveSecondsAgo && 
                   record.battery_charge === newRecord.battery_charge &&
                   record.load_pct === newRecord.load_pct &&
                   record.status === newRecord.status;
        });

        debug.log('Duplicate check:', {
            isDuplicate,
            allDataLength: this.historicData.allData.length,
            newRecord: {
                battery_charge: newRecord.battery_charge,
                load_pct: newRecord.load_pct,
                status: newRecord.status
            }
        });

        if (isDuplicate) {
            debug.log('Skipping duplicate historic data record');
            return;
        }

        // Check if this record should be included based on current filters
        const recordDate = new Date(newRecord.timestamp);
        let shouldInclude = true;
        const now = new Date();
        const isRecentData = (now.getTime() - recordDate.getTime()) < 10 * 60 * 1000; // Within 10 minutes
        
        debug.log('Filter check:', {
            recordDate: recordDate.toISOString(),
            dateFrom: this.historicData.filters.dateFrom ? this.historicData.filters.dateFrom.toISOString() : null,
            dateTo: this.historicData.filters.dateTo ? this.historicData.filters.dateTo.toISOString() : null,
            isRecentData
        });
        
        // For real-time data, be more lenient with the "to" filter
        if (this.historicData.filters.dateFrom && recordDate < this.historicData.filters.dateFrom) {
            shouldInclude = false;
            debug.log('Record before dateFrom filter');
        }
        
        // Only apply "to" filter strictly for non-recent data
        if (this.historicData.filters.dateTo && recordDate > this.historicData.filters.dateTo && !isRecentData) {
            shouldInclude = false;
            debug.log('Record after dateTo filter (not recent data)');
        }

        // Override filter restrictions for very recent real-time data
        if (!shouldInclude && isRecentData) {
            debug.log('Allowing recent real-time data despite filters');
            shouldInclude = true;
        }

        if (!shouldInclude) {
            debug.log('New record outside current filter range, not adding to display');
            return;
        }

        // Add the new record to the beginning of the data array (latest first)
        this.historicData.allData.unshift(newRecord);

        // Limit the total number of records to prevent memory issues
        const maxRecords = 10000;
        if (this.historicData.allData.length > maxRecords) {
            this.historicData.allData = this.historicData.allData.slice(0, maxRecords);
        }

        // Update the total record count
        this.historicData.totalRecords = this.historicData.allData.length;

        debug.log('About to update display:', {
            currentPage: this.historicData.currentPage,
            totalRecords: this.historicData.totalRecords,
            allDataLength: this.historicData.allData.length
        });

        // Only refresh the display if we're on the first page (to see latest data)
        if (this.historicData.currentPage === 1) {
            const startIndex = (this.historicData.currentPage - 1) * this.historicData.rowsPerPage;
            const endIndex = startIndex + this.historicData.rowsPerPage;
            this.historicData.data = this.historicData.allData.slice(startIndex, endIndex);

            debug.log('Updating table with data:', {
                startIndex,
                endIndex,
                dataLength: this.historicData.data.length,
                firstRecord: this.historicData.data[0] ? this.historicData.data[0].timestamp : 'none'
            });

            // Update the table and pagination
            this.updateHistoricDataTable();
            this.updateHistoricPaginationControls();

            // Show a subtle indicator that new data was added
            this.showNewDataIndicator();
            
            debug.log('Table update completed');
        } else {
            // Just update the record count if we're not on the first page
            document.getElementById('historic-record-count').textContent = this.historicData.totalRecords;
            debug.log('Not on first page, only updated record count');
        }

        debug.log('Added new record to historic data:', newRecord);
    }

    showNewDataIndicator() {
        // Add a subtle flash animation to the record count to indicate new data
        const recordCount = document.getElementById('historic-record-count');
        if (recordCount) {
            recordCount.style.transition = 'color 0.3s ease';
            recordCount.style.color = '#10b981'; // success color
            setTimeout(() => {
                recordCount.style.color = '';
            }, 1000);
        }

        // Update the "last updated" text for historic data
        this.updateHistoricLastUpdated();

        // Also add a small indicator badge near the Historic tab
        // this.showHistoricTabIndicator();
    }

    updateHistoricLastUpdated() {
        // Add or update a "last updated" indicator in the historic data section
        const historicTitle = document.querySelector('#historic-tab .card-title');
        if (!historicTitle) return;

        let lastUpdated = historicTitle.querySelector('.last-updated');
        if (!lastUpdated) {
            lastUpdated = document.createElement('span');
            lastUpdated.className = 'last-updated text-xs text-muted ml-4';
            historicTitle.appendChild(lastUpdated);
        }

        lastUpdated.textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
    }

    showHistoricTabIndicator() {
        // Add a small dot indicator to the Historic tab to show live updates
        const historicTabButton = document.querySelector('[data-tab="historic"]');
        if (!historicTabButton) return;

        // Remove any existing indicator
        const existingIndicator = historicTabButton.querySelector('.live-indicator');
        if (existingIndicator) {
            existingIndicator.remove();
        }

        // Add new indicator
        const indicator = document.createElement('span');
        indicator.className = 'live-indicator inline-block w-2 h-2 bg-green-500 rounded-full ml-2 animate-pulse';
        indicator.title = 'Live data updates';
        historicTabButton.appendChild(indicator);

        // Remove indicator after a few seconds
        setTimeout(() => {
            if (indicator.parentNode) {
                indicator.remove();
            }
        }, 3000);
    }

    enableHistoricRealTimeUpdates() {
        // Add a "LIVE" indicator to the historic data header
        const historicTitle = document.querySelector('#historic-tab .card-title');
        if (!historicTitle) return;

        // Remove existing live badge
        const existingBadge = historicTitle.querySelector('.live-badge');
        if (existingBadge) {
            existingBadge.remove();
        }

        // Add live indicator badge
        const liveBadge = document.createElement('span');
        liveBadge.className = 'live-badge inline-flex items-center gap-1 ml-2 px-2 py-1 text-xs font-medium bg-green-500 text-white rounded-full';
        liveBadge.innerHTML = '<span class="w-1.5 h-1.5 bg-white rounded-full animate-pulse"></span>LIVE';
        liveBadge.title = 'Real-time data updates active';
        
        historicTitle.appendChild(liveBadge);

        debug.log('Historic data real-time updates enabled');
    }

    disableHistoricRealTimeUpdates() {
        // Remove live indicator badge
        const liveBadge = document.querySelector('#historic-tab .live-badge');
        if (liveBadge) {
            liveBadge.remove();
        }
        debug.log('Historic data real-time updates disabled');
    }

    startAutoRefresh() {
        setInterval(() => {
            if (this.settings.autoRefresh && !this.isConnected) {
                this.fetchInitialData();
            }
            
            // Check WebSocket connection health and reconnect if needed
            if (!this.socket || !this.socket.connected) {
                debug.log('WebSocket disconnected, attempting to reconnect...');
                this.connectWebSocket();
            }
        }, 30000); // Refresh every 30 seconds when not connected
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.upsMonitor = new UPSMonitor();
});
