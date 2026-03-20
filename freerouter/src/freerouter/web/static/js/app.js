/**
 * FreeRouter Dashboard - Frontend Logic
 * Enhanced with Provider Instance Management and Chat Playground
 * FIXED VERSION - All bugs corrected
 */

// API Base URL
const API_BASE = '/api';

// State
const state = {
    providers: [],
    instances: [],
    providerTypes: [],
    models: [],
    modelGroups: {},
    primaryModels: [],
    usage: {},
    currentTab: 'providers',
    chatHistory: [],
    selectedModel: 'free-router/auto',
    conversations: [],
    currentConversationId: null,
    currentConversation: null,
    isStreaming: false,
    compareModels: [],
    showCompare: false,
};

// ─── Utility Functions ────────────────────────────────────────────────────────

async function fetchAPI(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            ...options,
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showToast(error.message, 'error');
        throw error;
    }
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container') || createToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
    return container;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(timestamp) {
    if (!timestamp) return 'Never';
    return new Date(timestamp * 1000).toLocaleString();
}

function formatDateTime(isoString) {
    if (!isoString) return '';
    return new Date(isoString).toLocaleString();
}

// ─── Tab Management ────────────────────────────────────────────────────────────

function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            switchTab(tab);
        });
    });
}

function switchTab(tab) {
    state.currentTab = tab;

    // Update buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });

    // Load content
    const content = document.getElementById('content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    switch (tab) {
        case 'providers':
            loadProvidersTab();
            break;
        case 'instances':
            loadInstancesTab();
            break;
        case 'chat':
            loadChatTab();
            break;
        case 'models':
            loadModelsTab();
            break;
        case 'config':
            loadConfigTab();
            break;
        case 'usage':
            loadUsageTab();
            break;
        default:
            content.innerHTML = '<p>Unknown tab</p>';
    }
}

// ─── Providers Tab (Legacy) ────────────────────────────────────────────────────

async function loadProvidersTab() {
    const content = document.getElementById('content');

    try {
        const [providersData, healthData] = await Promise.all([
            fetchAPI('/providers'),
            fetchAPI('/providers/status'),
        ]);

        state.providers = providersData.providers;

        // Merge health data
        const healthMap = {};
        healthData.providers.forEach(p => {
            healthMap[p.name] = p;
        });

        content.innerHTML = renderProvidersContent(state.providers, healthMap);
        initProvidersEvents();
    } catch (error) {
        content.innerHTML = `<div class="card"><p>Error loading providers: ${escapeHtml(error.message)}</p></div>`;
    }
}

function renderProvidersContent(providers, healthMap) {
    const providerIcons = {
        ollama: '🖥️',
        openrouter: '☁️',
        groq: '⚡',
        anthropic: '🤖',
        openai: '🧠',
        together: '🔗',
        deepinfra: '🔧',
    };

    return `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">🔑 API Providers (Quick Setup)</h2>
                <button class="btn btn-secondary btn-small" onclick="switchTab('instances')">
                    🖥️ Advanced View
                </button>
            </div>
            <p style="color: var(--text-secondary); margin-bottom: 20px;">
                Quick setup: Add API keys for cloud providers. For advanced configuration (multiple instances, custom URLs),
                use the <a href="#" onclick="switchTab('instances'); return false;" style="color: var(--primary);">Instances</a> tab.
            </p>
            <div class="provider-list">
                ${providers.map(provider => {
        const health = healthMap[provider.name] || {};
        const statusClass = getStatusClass(health);
        const statusText = getStatusText(health);
        const icon = providerIcons[provider.name] || '☁️';

        return `
                        <div class="provider-item" data-provider="${provider.name}">
                            <div class="provider-info">
                                <div class="provider-icon ${provider.provider_type}">
                                    ${icon}
                                </div>
                                <div>
                                    <div class="provider-name">${escapeHtml(provider.display_name)}</div>
                                    <div class="provider-type">
                                        ${provider.provider_type === 'local' ? 'Local' : 'Cloud'}
                                        ${provider.requires_auth ? '• API Key Required' : '• No API Key Needed'}
                                    </div>
                                </div>
                            </div>
                            <div class="provider-status">
                                <span class="status-badge ${statusClass}">${statusText}</span>
                                ${!provider.is_configured && provider.requires_auth ? `
                                    <button class="btn btn-primary btn-small" onclick="showApiKeyModal('${provider.name}', '${escapeHtml(provider.display_name)}', '${provider.signup_url}')">
                                        Add Key
                                    </button>
                                ` : ''}
                                ${provider.is_configured && provider.requires_auth ? `
                                    <button class="btn btn-secondary btn-small" onclick="showApiKeyModal('${provider.name}', '${escapeHtml(provider.display_name)}', '${provider.signup_url}')">
                                        Update
                                    </button>
                                    <button class="btn btn-secondary btn-small" onclick="testProvider('${provider.name}')">
                                        Test
                                    </button>
                                ` : ''}
                                ${!provider.requires_auth ? `
                                    <button class="btn btn-secondary btn-small" onclick="testProvider('${provider.name}')">
                                        Test
                                    </button>
                                ` : ''}
                            </div>
                        </div>
                    `;
    }).join('')}
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h2 class="card-title">💡 How to Get Free API Keys</h2>
            </div>
            <div style="color: var(--text-secondary);">
                <p style="margin-bottom: 10px;">All these providers offer free tiers:</p>
                <ul style="padding-left: 20px;">
                    <li><strong>Ollama:</strong> <a href="https://ollama.ai" target="_blank">Download here</a> - Runs locally, completely free</li>
                    <li><strong>Groq:</strong> <a href="https://console.groq.com/keys" target="_blank">Get free key</a> - Very fast inference, generous free tier</li>
                    <li><strong>OpenRouter:</strong> <a href="https://openrouter.ai/keys" target="_blank">Get free key</a> - Access to many free models</li>
                </ul>
            </div>
        </div>
    `;
}

function getStatusClass(health) {
    if (!health.is_configured && health.requires_auth !== false) return 'unconfigured';
    if (health.health && health.health.ok) return 'healthy';
    if (health.health && !health.health.ok) return 'unhealthy';
    return 'unconfigured';
}

function getStatusText(health) {
    if (!health.is_configured && health.requires_auth !== false) return 'Not Configured';
    if (health.health && health.health.ok) return 'Ready';
    if (health.health && !health.health.ok) return health.health.message || 'Error';
    return 'Unknown';
}

function initProvidersEvents() {
    // Any additional event listeners
}

async function testProvider(providerName) {
    showToast(`Testing ${providerName}...`, 'warning');
    try {
        const result = await fetchAPI(`/providers/${providerName}/test`, { method: 'POST' });
        if (result.ok) {
            showToast(`${providerName} is working!`, 'success');
        } else {
            showToast(`${providerName} test failed: ${result.message}`, 'error');
        }
    } catch (error) {
        // Error already shown by fetchAPI
    }
}

function refreshProviders() {
    loadProvidersTab();
}

// ─── API Key Modal ────────────────────────────────────────────────────────────

function showApiKeyModal(provider, displayName, signupUrl) {
    const existingModal = document.querySelector('.modal-overlay');
    if (existingModal) existingModal.remove();

    const modalHtml = `
        <div class="modal-overlay" onclick="closeModal(event)">
            <div class="modal" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h3 class="modal-title">🔑 Configure ${escapeHtml(displayName)}</h3>
                    <button class="modal-close" onclick="closeModal()">&times;</button>
                </div>
                <div class="form-group">
                    <p style="margin-bottom: 15px; color: var(--text-secondary);">
                        Get your API key from:
                        <a href="${escapeHtml(signupUrl)}" target="_blank" style="color: var(--primary);">
                            ${escapeHtml(signupUrl)}
                        </a>
                    </p>
                    <label class="form-label">API Key</label>
                    <input type="password" id="api-key-input" class="form-input"
                           placeholder="Paste your API key here" autocomplete="off">
                </div>
                <div style="display: flex; gap: 10px; justify-content: flex-end;">
                    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                    <button class="btn btn-primary" onclick="saveApiKey('${provider}')">Save Key</button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
    document.getElementById('api-key-input').focus();
}

async function saveApiKey(provider) {
    const input = document.getElementById('api-key-input');
    const apiKey = input.value.trim();

    if (!apiKey) {
        showToast('Please enter an API key', 'error');
        return;
    }

    try {
        const result = await fetchAPI(`/providers/${provider}/key`, {
            method: 'POST',
            body: JSON.stringify({
                provider: provider,
                api_key: apiKey,
            }),
        });

        if (result.success) {
            showToast(`API key saved for ${provider}`, 'success');
            closeModal();
            loadProvidersTab();
        }
    } catch (error) {
        // Error already shown
    }
}

function closeModal(event) {
    if (event && event.target !== event.currentTarget) return;
    const modal = document.querySelector('.modal-overlay');
    if (modal) modal.remove();
}

// ─── Instances Tab ─────────────────────────────────────────────────────────────

async function loadInstancesTab() {
    const content = document.getElementById('content');

    try {
        const [instancesData, typesData] = await Promise.all([
            fetchAPI('/instances'),
            fetchAPI('/providers/types'),
        ]);

        state.instances = instancesData.instances;
        state.providerTypes = typesData.types;

        content.innerHTML = renderInstancesContent();
        initInstancesEvents();
    } catch (error) {
        content.innerHTML = `<div class="card"><p>Error loading instances: ${escapeHtml(error.message)}</p></div>`;
    }
}

function renderInstancesContent() {
    const providerIcons = {
        ollama: '🖥️',
        groq: '⚡',
        openrouter: '☁️',
        anthropic: '🤖',
        openai: '🧠',
        together: '🔗',
        deepinfra: '🔧',
        custom: '⚙️',
    };

    // Group instances by provider type
    const grouped = {};
    state.instances.forEach(inst => {
        if (!grouped[inst.provider_type]) {
            grouped[inst.provider_type] = [];
        }
        grouped[inst.provider_type].push(inst);
    });

    return `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">🖥️ Provider Instances</h2>
                <button class="btn btn-primary btn-small" onclick="showAddInstanceModal()">
                    + Add Instance
                </button>
            </div>
            <p style="color: var(--text-secondary); margin-bottom: 20px;">
                Manage multiple provider instances. You can have both local (Ollama) and cloud instances
                of the same provider type.
            </p>

            ${Object.keys(grouped).length === 0 ? `
                <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
                    <p>No instances configured yet.</p>
                    <button class="btn btn-primary" onclick="showAddInstanceModal()">Add Your First Instance</button>
                </div>
            ` : Object.entries(grouped).map(([providerType, instances]) => {
        const typeInfo = state.providerTypes.find(t => t.type === providerType) || { name: providerType, icon: '☁️' };
        const icon = providerIcons[providerType] || typeInfo.icon || '☁️';

        return `
                    <div class="provider-group" style="margin-bottom: 25px;">
                        <h3 style="margin-bottom: 15px; display: flex; align-items: center; gap: 10px;">
                            <span style="font-size: 1.5rem;">${icon}</span>
                            ${escapeHtml(typeInfo.name)}
                            <span style="font-size: 0.8rem; color: var(--text-muted);">(${instances.length} instance${instances.length > 1 ? 's' : ''})</span>
                        </h3>
                        <div class="instance-list">
                            ${instances.map(inst => renderInstanceCard(inst, icon)).join('')}
                        </div>
                    </div>
                `;
    }).join('')}
        </div>

        <div class="card">
            <div class="card-header">
                <h2 class="card-title">ℹ️ About Instances</h2>
            </div>
            <div style="color: var(--text-secondary);">
                <p style="margin-bottom: 15px;">Each instance represents a connection to an AI provider:</p>
                <ul style="padding-left: 20px;">
                    <li><strong>Local instances</strong> (like Ollama) run on your machine - no API key needed</li>
                    <li><strong>Cloud instances</strong> require an API key from the provider</li>
                    <li>You can have <strong>multiple instances</strong> of the same provider (e.g., Ollama Local + Ollama Cloud)</li>
                    <li><strong>Priority</strong> determines fallback order - lower number = higher priority</li>
                </ul>
            </div>
        </div>
    `;
}

function renderInstanceCard(instance, icon) {
    const statusClass = instance.is_healthy ? 'healthy' : (instance.last_health_check ? 'unhealthy' : 'unconfigured');
    const statusText = instance.is_healthy ? 'Healthy' : (instance.last_health_check ? instance.health_message : 'Not Checked');

    return `
        <div class="instance-card" style="background: var(--bg-input); border-radius: var(--radius); padding: 15px; margin-bottom: 10px; border: 1px solid var(--border);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                <div>
                    <h4 style="margin: 0; display: flex; align-items: center; gap: 8px;">
                        ${instance.is_active ? '🟢' : '⚪'}
                        ${escapeHtml(instance.name)}
                        ${instance.instance_type === 'local' ? '<span style="font-size: 0.7rem; background: var(--success); color: white; padding: 2px 6px; border-radius: 4px;">LOCAL</span>' : '<span style="font-size: 0.7rem; background: var(--primary); color: white; padding: 2px 6px; border-radius: 4px;">CLOUD</span>'}
                    </h4>
                    <p style="margin: 5px 0 0; font-size: 0.85rem; color: var(--text-muted);">
                        ${escapeHtml(instance.base_url)}
                    </p>
                </div>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-secondary btn-small" onclick="testInstance('${instance.id}')">Test</button>
                    <button class="btn btn-secondary btn-small" onclick="showEditInstanceModal('${instance.id}')">Edit</button>
                    <button class="btn btn-secondary btn-small" onclick="deleteInstance('${instance.id}')" style="color: var(--error);">Delete</button>
                </div>
            </div>
            <div style="display: flex; gap: 15px; font-size: 0.85rem; color: var(--text-secondary);">
                <span>Priority: ${instance.priority}</span>
                <span class="status-badge ${statusClass}">${statusText}</span>
                ${instance.models && instance.models.length > 0 ? `<span>${instance.models.length} models</span>` : ''}
                ${instance.api_key ? `<span style="color: var(--success);">🔑 Key set</span>` : ''}
            </div>
            ${instance.provider_type === 'ollama' && instance.is_healthy ? `
                <div style="margin-top: 10px; display: flex; gap: 8px;">
                    <button class="btn btn-secondary btn-small" onclick="showModelsForInstance('${instance.id}')">View Models</button>
                    <button class="btn btn-secondary btn-small" onclick="showPullModelModal('${instance.id}')">Pull Model</button>
                </div>
            ` : ''}
        </div>
    `;
}

function initInstancesEvents() {
    // Event listeners for instances tab
}

async function testInstance(instanceId) {
    showToast('Testing instance...', 'warning');
    try {
        const result = await fetchAPI(`/instances/${instanceId}/test`, { method: 'POST' });
        if (result.ok) {
            showToast('Instance is healthy!', 'success');
        } else {
            showToast(`Test failed: ${result.message}`, 'error');
        }
        loadInstancesTab();
    } catch (error) {
        // Error already shown
    }
}

async function deleteInstance(instanceId) {
    if (!confirm('Are you sure you want to delete this instance?')) {
        return;
    }

    try {
        await fetchAPI(`/instances/${instanceId}`, { method: 'DELETE' });
        showToast('Instance deleted', 'success');
        loadInstancesTab();
    } catch (error) {
        // Error already shown
    }
}

// ─── Add/Edit Instance Modal ────────────────────────────────────────────────────

function showAddInstanceModal() {
    const existingModal = document.querySelector('.modal-overlay');
    if (existingModal) existingModal.remove();

    const providerTypesOptions = state.providerTypes.map(t =>
        `<option value="${t.type}">${t.icon} ${t.name}</option>`
    ).join('');

    const modalHtml = `
        <div class="modal-overlay" onclick="closeModal(event)">
            <div class="modal" onclick="event.stopPropagation()" style="max-width: 600px;">
                <div class="modal-header">
                    <h3 class="modal-title">➕ Add Provider Instance</h3>
                    <button class="modal-close" onclick="closeModal()">&times;</button>
                </div>
                <div class="form-group">
                    <label class="form-label">Provider Type</label>
                    <select id="instance-provider-type" class="form-input" onchange="updateInstanceForm()">
                        ${providerTypesOptions}
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Instance Name</label>
                    <input type="text" id="instance-name" class="form-input" placeholder="e.g., 'Ollama Local', 'My Groq Account'">
                </div>
                <div class="form-group">
                    <label class="form-label">Instance Type</label>
                    <select id="instance-type" class="form-input" onchange="updateBaseUrl()">
                        <option value="local">Local (self-hosted)</option>
                        <option value="cloud">Cloud (API)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Base URL</label>
                    <input type="text" id="instance-base-url" class="form-input" placeholder="https://api.example.com/v1">
                </div>
                <div class="form-group" id="api-key-group">
                    <label class="form-label">API Key (optional for local)</label>
                    <input type="password" id="instance-api-key" class="form-input" placeholder="Leave empty for local instances">
                </div>
                <div class="form-group">
                    <label class="form-label">Priority (lower = higher priority)</label>
                    <input type="number" id="instance-priority" class="form-input" value="100" min="1" max="1000">
                </div>
                <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
                    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                    <button class="btn btn-primary" onclick="createInstance()">Create Instance</button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
    updateInstanceForm();
}

function updateInstanceForm() {
    const providerType = document.getElementById('instance-provider-type').value;
    const instanceType = document.getElementById('instance-type').value;
    const typeInfo = state.providerTypes.find(t => t.type === providerType);

    if (typeInfo && typeInfo.default_base_urls) {
        const defaultUrl = typeInfo.default_base_urls[instanceType];
        if (defaultUrl && defaultUrl.base_url) {
            document.getElementById('instance-base-url').value = defaultUrl.base_url;
        }
    }

    // Update name placeholder
    const typeName = typeInfo ? typeInfo.name : providerType;
    const instanceTypeName = instanceType === 'local' ? 'Local' : 'Cloud';
    document.getElementById('instance-name').placeholder = `${typeName} ${instanceTypeName}`;

    // Show/hide API key field
    const apiKeyGroup = document.getElementById('api-key-group');
    if (instanceType === 'local' && providerType === 'ollama') {
        apiKeyGroup.style.display = 'none';
    } else {
        apiKeyGroup.style.display = 'block';
    }

    // Update instance type options
    const instanceTypeSelect = document.getElementById('instance-type');
    if (typeInfo && typeInfo.instance_types) {
        const currentType = instanceTypeSelect.value;
        instanceTypeSelect.innerHTML = typeInfo.instance_types.map(t =>
            `<option value="${t}" ${t === currentType ? 'selected' : ''}>${t.charAt(0).toUpperCase() + t.slice(1)}</option>`
        ).join('');
    }

    updateBaseUrl();
}

function updateBaseUrl() {
    const providerType = document.getElementById('instance-provider-type').value;
    const instanceType = document.getElementById('instance-type').value;
    const typeInfo = state.providerTypes.find(t => t.type === providerType);

    if (typeInfo && typeInfo.default_base_urls && typeInfo.default_base_urls[instanceType]) {
        document.getElementById('instance-base-url').value = typeInfo.default_base_urls[instanceType].base_url;
    }
}

async function createInstance() {
    const providerType = document.getElementById('instance-provider-type').value;
    const name = document.getElementById('instance-name').value.trim();
    const instanceType = document.getElementById('instance-type').value;
    const baseUrl = document.getElementById('instance-base-url').value.trim();
    const apiKey = document.getElementById('instance-api-key').value.trim() || null;
    const priority = parseInt(document.getElementById('instance-priority').value, 10) || 100;

    if (!name) {
        showToast('Please enter a name', 'error');
        return;
    }

    if (!baseUrl) {
        showToast('Please enter a base URL', 'error');
        return;
    }

    try {
        const result = await fetchAPI('/instances', {
            method: 'POST',
            body: JSON.stringify({
                provider_type: providerType,
                name: name,
                instance_type: instanceType,
                base_url: baseUrl,
                api_key: apiKey,
                priority: priority,
                is_active: true,
            }),
        });

        if (result.success) {
            showToast('Instance created!', 'success');
            closeModal();
            loadInstancesTab();
        }
    } catch (error) {
        // Error already shown
    }
}

function showEditInstanceModal(instanceId) {
    const instance = state.instances.find(i => i.id === instanceId);
    if (!instance) return;

    const existingModal = document.querySelector('.modal-overlay');
    if (existingModal) existingModal.remove();

    const modalHtml = `
        <div class="modal-overlay" onclick="closeModal(event)">
            <div class="modal" onclick="event.stopPropagation()" style="max-width: 600px;">
                <div class="modal-header">
                    <h3 class="modal-title">✏️ Edit Instance: ${escapeHtml(instance.name)}</h3>
                    <button class="modal-close" onclick="closeModal()">&times;</button>
                </div>
                <div class="form-group">
                    <label class="form-label">Name</label>
                    <input type="text" id="edit-instance-name" class="form-input" value="${escapeHtml(instance.name)}">
                </div>
                <div class="form-group">
                    <label class="form-label">Base URL</label>
                    <input type="text" id="edit-instance-base-url" class="form-input" value="${escapeHtml(instance.base_url)}">
                </div>
                <div class="form-group">
                    <label class="form-label">API Key ${instance.api_key ? '(currently set)' : '(not set)'}</label>
                    <input type="password" id="edit-instance-api-key" class="form-input" placeholder="Enter new key or leave empty to keep existing">
                </div>
                <div class="form-group">
                    <label class="form-label">Priority (lower = higher priority)</label>
                    <input type="number" id="edit-instance-priority" class="form-input" value="${instance.priority}" min="1" max="1000">
                </div>
                <div class="form-group">
                    <label style="display: flex; align-items: center; gap: 10px;">
                        <input type="checkbox" id="edit-instance-active" ${instance.is_active ? 'checked' : ''}>
                        <span>Active (enabled for routing)</span>
                    </label>
                </div>
                <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
                    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                    <button class="btn btn-primary" onclick="updateInstance('${instance.id}')">Save Changes</button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

async function updateInstance(instanceId) {
    const name = document.getElementById('edit-instance-name').value.trim();
    const baseUrl = document.getElementById('edit-instance-base-url').value.trim();
    const apiKey = document.getElementById('edit-instance-api-key').value.trim() || undefined;
    const priority = parseInt(document.getElementById('edit-instance-priority').value, 10);
    const isActive = document.getElementById('edit-instance-active').checked;

    if (!name) {
        showToast('Please enter a name', 'error');
        return;
    }

    try {
        const result = await fetchAPI(`/instances/${instanceId}`, {
            method: 'PUT',
            body: JSON.stringify({
                name: name,
                base_url: baseUrl,
                api_key: apiKey,
                priority: priority,
                is_active: isActive,
            }),
        });

        if (result.success) {
            showToast('Instance updated!', 'success');
            closeModal();
            loadInstancesTab();
        }
    } catch (error) {
        // Error already shown
    }
}

// ─── Model Management ────────────────────────────────────────────────────────────

async function showModelsForInstance(instanceId) {
    const instance = state.instances.find(i => i.id === instanceId);
    if (!instance) return;

    showToast('Fetching models...', 'warning');

    try {
        const result = await fetchAPI(`/instances/${instanceId}/models`);
        const models = result.models || [];

        if (models.length === 0) {
            showToast('No models found', 'warning');
            return;
        }

        const existingModal = document.querySelector('.modal-overlay');
        if (existingModal) existingModal.remove();

        const modalHtml = `
            <div class="modal-overlay" onclick="closeModal(event)">
                <div class="modal" onclick="event.stopPropagation()" style="max-width: 500px;">
                    <div class="modal-header">
                        <h3 class="modal-title">📦 Models: ${escapeHtml(instance.name)}</h3>
                        <button class="modal-close" onclick="closeModal()">&times;</button>
                    </div>
                    <div style="max-height: 400px; overflow-y: auto;">
                        ${models.map(m => `
                            <div style="padding: 10px; border-bottom: 1px solid var(--border);">
                                <div style="font-weight: 600;">${escapeHtml(m.id || m.name)}</div>
                                ${m.size ? `<div style="font-size: 0.85rem; color: var(--text-muted);">Size: ${formatSize(m.size)}</div>` : ''}
                            </div>
                        `).join('')}
                    </div>
                    <div style="margin-top: 15px; display: flex; justify-content: flex-end;">
                        <button class="btn btn-secondary" onclick="closeModal()">Close</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
    } catch (error) {
        showToast('Failed to fetch models', 'error');
    }
}

function formatSize(bytes) {
    if (!bytes) return '';
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb > 1) return `${gb.toFixed(1)} GB`;
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(0)} MB`;
}

function showPullModelModal(instanceId) {
    const instance = state.instances.find(i => i.id === instanceId);
    if (!instance) return;

    const existingModal = document.querySelector('.modal-overlay');
    if (existingModal) existingModal.remove();

    const modalHtml = `
        <div class="modal-overlay" onclick="closeModal(event)">
            <div class="modal" onclick="event.stopPropagation()" style="max-width: 500px;">
                <div class="modal-header">
                    <h3 class="modal-title">📥 Pull Model: ${escapeHtml(instance.name)}</h3>
                    <button class="modal-close" onclick="closeModal()">&times;</button>
                </div>
                <div class="form-group">
                    <label class="form-label">Model Name</label>
                    <input type="text" id="pull-model-name" class="form-input" placeholder="e.g., llama3.2, qwen2.5:7b">
                    <p style="font-size: 0.85rem; color: var(--text-muted); margin-top: 5px;">
                        Popular models: llama3.2, qwen2.5:7b, codellama:7b, mistral
                    </p>
                </div>
                <div style="display: flex; gap: 10px; justify-content: flex-end;">
                    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                    <button class="btn btn-primary" onclick="pullModel('${instanceId}')">Pull Model</button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
    document.getElementById('pull-model-name').focus();
}

async function pullModel(instanceId) {
    const modelName = document.getElementById('pull-model-name').value.trim();

    if (!modelName) {
        showToast('Please enter a model name', 'error');
        return;
    }

    showToast(`Pulling model "${modelName}"...`, 'warning');

    try {
        const result = await fetchAPI(`/instances/${instanceId}/pull`, {
            method: 'POST',
            body: JSON.stringify({ model_name: modelName }),
        });

        if (result.success) {
            showToast(result.message, 'success');
            closeModal();
            showModelsForInstance(instanceId);
        } else {
            showToast(result.message, 'error');
        }
    } catch (error) {
        showToast('Failed to pull model', 'error');
    }
}

// ─── Models Tab ────────────────────────────────────────────────────────────────

async function loadModelsTab() {
    const content = document.getElementById('content');

    try {
        const [aliasesData, groupsData, primaryData] = await Promise.all([
            fetchAPI('/aliases'),
            fetchAPI('/aliases/groups'),
            fetchAPI('/primary-models'),
        ]);

        state.modelAliases = aliasesData.aliases;
        state.modelGroups = groupsData.groups;
        state.primaryModels = primaryData.models;

        content.innerHTML = renderModelsContent();
        initModelsEvents();
    } catch (error) {
        content.innerHTML = `<div class="card"><p>Error loading models: ${escapeHtml(error.message)}</p></div>`;
    }
}

function renderModelsContent() {
    return `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">📦 Model Aliases</h2>
                <button class="btn btn-primary btn-small" onclick="showAddAliasModal()">
                    + Add Alias
                </button>
            </div>
            <p style="color: var(--text-secondary); margin-bottom: 20px;">
                Manage model aliases and their configurations. Each alias maps to a specific model from a provider.
            </p>

            ${state.modelAliases.length === 0 ? `
                <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
                    <p>No model aliases configured.</p>
                    <button class="btn btn-primary" onclick="showAddAliasModal()">Add Your First Alias</button>
                </div>
            ` : `
                <div class="model-groups">
                    ${Object.entries(state.modelGroups).map(([groupName, aliases]) => `
                        <div class="model-group" style="margin-bottom: 25px;">
                            <h3 style="margin-bottom: 15px; text-transform: capitalize;">
                                ${escapeHtml(groupName)} Models
                                <span style="font-size: 0.8rem; color: var(--text-muted); font-weight: normal;">
                                    (${aliases.length})
                                </span>
                            </h3>
                            <div class="model-list">
                                ${aliases.map(alias => renderModelAliasCard(alias)).join('')}
                            </div>
                        </div>
                    `).join('')}
                </div>
            `}
        </div>

        <div class="card">
            <div class="card-header">
                <h2 class="card-title">🔗 Fallback Chains</h2>
                <button class="btn btn-primary btn-small" onclick="showAddFallbackModal()">
                    + Add Chain
                </button>
            </div>
            <p style="color: var(--text-secondary); margin-bottom: 20px;">
                Configure fallback chains for automatic failover when a model is unavailable.
            </p>

            ${state.primaryModels.length === 0 ? `
                <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
                    <p>No fallback chains configured.</p>
                    <button class="btn btn-primary" onclick="showAddFallbackModal()">Add Fallback Chain</button>
                </div>
            ` : `
                <div class="fallback-list">
                    ${state.primaryModels.map(model => {
        const chain = state.modelGroups[model.name.split('/').pop().split('-')[0] || 'other'];
        return renderFallbackChain(model, chain);
    }).join('')}
                </div>
            `}
        </div>
    `;
}

function renderModelAliasCard(alias) {
    return `
        <div class="model-alias-card" style="background: var(--bg-input); border-radius: var(--radius); padding: 15px; margin-bottom: 10px; border: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h4 style="margin: 0 0 5px 0;">${escapeHtml(alias.name)}</h4>
                <p style="margin: 0; font-size: 0.85rem; color: var(--text-muted);">
                    ${escapeHtml(alias.model)}
                    ${alias.provider ? `• ${escapeHtml(alias.provider)}` : ''}
                </p>
                ${alias.description ? `<p style="margin: 5px 0 0; font-size: 0.85rem; color: var(--text-secondary);">${escapeHtml(alias.description)}</p>` : ''}
            </div>
            <div style="display: flex; gap: 8px;">
                <button class="btn btn-secondary btn-small" onclick="showEditAliasModal('${alias.name}')">Edit</button>
                <button class="btn btn-secondary btn-small" onclick="deleteAlias('${alias.name}')" style="color: var(--error);">Delete</button>
            </div>
        </div>
    `;
}

function renderFallbackChain(model, fallbackModels) {
    // Find fallbacks for this model
    const chain = state.modelGroups[model.name.split('/').pop().split('-')[0] || 'other'] || [];
    const fallbacks = chain.filter(m => m.is_fallback);

    return `
        <div class="fallback-chain" style="background: var(--bg-input); border-radius: var(--radius); padding: 15px; margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                <div>
                    <h4 style="margin: 0;">${escapeHtml(model.name)}</h4>
                    <p style="margin: 5px 0 0; font-size: 0.85rem; color: var(--text-muted);">
                        ${escapeHtml(model.description || 'No description')}
                    </p>
                </div>
                <button class="btn btn-secondary btn-small" onclick="showEditFallbackModal('${model.name}')">
                    Edit Fallbacks
                </button>
            </div>
            ${fallbacks.length > 0 ? `
                <div style="font-size: 0.85rem; color: var(--text-secondary);">
                    <strong>Fallbacks:</strong> ${fallbacks.map(f => escapeHtml(f.name)).join(' → ')}
                </div>
            ` : '<p style="color: var(--text-muted); font-size: 0.85rem; margin: 0;">No fallbacks configured</p>'}
        </div>
    `;
}

function initModelsEvents() {
    // Event listeners for models tab
}

// ─── Alias Management Modals ───────────────────────────────────────────────────

function showAddAliasModal() {
    const existingModal = document.querySelector('.modal-overlay');
    if (existingModal) existingModal.remove();

    const modalHtml = `
        <div class="modal-overlay" onclick="closeModal(event)">
            <div class="modal" onclick="event.stopPropagation()" style="max-width: 600px;">
                <div class="modal-header">
                    <h3 class="modal-title">➕ Add Model Alias</h3>
                    <button class="modal-close" onclick="closeModal()">&times;</button>
                </div>
                <div class="form-group">
                    <label class="form-label">Alias Name</label>
                    <input type="text" id="alias-name" class="form-input" placeholder="e.g., free-router/my-custom-model">
                </div>
                <div class="form-group">
                    <label class="form-label">Model</label>
                    <input type="text" id="alias-model" class="form-input" placeholder="e.g., ollama/qwen2.5:7b">
                    <p style="font-size: 0.85rem; color: var(--text-muted); margin-top: 5px;">
                        Format: provider/model-name (e.g., ollama/llama3.2, groq/llama-3.3-70b-versatile)
                    </p>
                </div>
                <div class="form-group">
                    <label class="form-label">API Base URL (optional)</label>
                    <input type="text" id="alias-api-base" class="form-input" placeholder="https://api.example.com/v1">
                </div>
                <div class="form-group">
                    <label class="form-label">API Key (optional)</label>
                    <input type="password" id="alias-api-key" class="form-input" placeholder="os.environ/GROQ_API_KEY or direct key">
                </div>
                <div class="form-group">
                    <label class="form-label">Timeout (seconds)</label>
                    <input type="number" id="alias-timeout" class="form-input" value="60" min="1">
                </div>
                <div class="form-group">
                    <label class="form-label">Max Tokens</label>
                    <input type="number" id="alias-max-tokens" class="form-input" value="8192" min="1">
                </div>
                <div class="form-group">
                    <label class="form-label">Description</label>
                    <input type="text" id="alias-description" class="form-input" placeholder="Brief description of this model">
                </div>
                <div class="form-group">
                    <label style="display: flex; align-items: center; gap: 10px;">
                        <input type="checkbox" id="alias-supports-vision">
                        <span>Supports Vision (image input)</span>
                    </label>
                </div>
                <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
                    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                    <button class="btn btn-primary" onclick="createAlias()">Create Alias</button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

async function createAlias() {
    const name = document.getElementById('alias-name').value.trim();
    const model = document.getElementById('alias-model').value.trim();
    const apiBase = document.getElementById('alias-api-base').value.trim() || undefined;
    const apiKey = document.getElementById('alias-api-key').value.trim() || undefined;
    const timeout = parseInt(document.getElementById('alias-timeout').value, 10);
    const maxTokens = parseInt(document.getElementById('alias-max-tokens').value, 10);
    const description = document.getElementById('alias-description').value.trim();
    const supportsVision = document.getElementById('alias-supports-vision').checked;

    if (!name || !model) {
        showToast('Name and model are required', 'error');
        return;
    }

    try {
        const result = await fetchAPI('/aliases', {
            method: 'POST',
            body: JSON.stringify({
                name,
                model,
                api_base: apiBase,
                api_key: apiKey,
                timeout,
                max_tokens: maxTokens,
                description,
                supports_vision: supportsVision,
            }),
        });

        if (result.success) {
            showToast('Alias created!', 'success');
            closeModal();
            loadModelsTab();
        }
    } catch (error) {
        // Error already shown
    }
}

function showEditAliasModal(aliasName) {
    const alias = state.modelAliases.find(a => a.name === aliasName);
    if (!alias) return;

    const existingModal = document.querySelector('.modal-overlay');
    if (existingModal) existingModal.remove();

    const modalHtml = `
        <div class="modal-overlay" onclick="closeModal(event)">
            <div class="modal" onclick="event.stopPropagation()" style="max-width: 600px;">
                <div class="modal-header">
                    <h3 class="modal-title">✏️ Edit Alias: ${escapeHtml(alias.name)}</h3>
                    <button class="modal-close" onclick="closeModal()">&times;</button>
                </div>
                <div class="form-group">
                    <label class="form-label">Model</label>
                    <input type="text" id="edit-alias-model" class="form-input" value="${escapeHtml(alias.model)}">
                </div>
                <div class="form-group">
                    <label class="form-label">API Base URL</label>
                    <input type="text" id="edit-alias-api-base" class="form-input" value="${escapeHtml(alias.api_base || '')}">
                </div>
                <div class="form-group">
                    <label class="form-label">API Key (leave empty to keep existing)</label>
                    <input type="password" id="edit-alias-api-key" class="form-input">
                </div>
                <div class="form-group">
                    <label class="form-label">Timeout (seconds)</label>
                    <input type="number" id="edit-alias-timeout" class="form-input" value="${alias.timeout}" min="1">
                </div>
                <div class="form-group">
                    <label class="form-label">Max Tokens</label>
                    <input type="number" id="edit-alias-max-tokens" class="form-input" value="${alias.max_tokens}" min="1">
                </div>
                <div class="form-group">
                    <label class="form-label">Description</label>
                    <input type="text" id="edit-alias-description" class="form-input" value="${escapeHtml(alias.description || '')}">
                </div>
                <div class="form-group">
                    <label style="display: flex; align-items: center; gap: 10px;">
                        <input type="checkbox" id="edit-alias-supports-vision" ${alias.supports_vision ? 'checked' : ''}>
                        <span>Supports Vision (image input)</span>
                    </label>
                </div>
                <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
                    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                    <button class="btn btn-primary" onclick="updateAlias('${alias.name}')">Save Changes</button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

async function updateAlias(aliasName) {
    const model = document.getElementById('edit-alias-model').value.trim();
    const apiBase = document.getElementById('edit-alias-api-base').value.trim() || undefined;
    const apiKey = document.getElementById('edit-alias-api-key').value.trim() || undefined;
    const timeout = parseInt(document.getElementById('edit-alias-timeout').value, 10);
    const maxTokens = parseInt(document.getElementById('edit-alias-max-tokens').value, 10);
    const description = document.getElementById('edit-alias-description').value.trim();
    const supportsVision = document.getElementById('edit-alias-supports-vision').checked;

    try {
        const result = await fetchAPI(`/aliases/${encodeURIComponent(aliasName)}`, {
            method: 'PUT',
            body: JSON.stringify({
                model: model || undefined,
                api_base: apiBase,
                api_key: apiKey,
                timeout,
                max_tokens: maxTokens,
                description,
                supports_vision: supportsVision,
            }),
        });

        if (result.success) {
            showToast('Alias updated!', 'success');
            closeModal();
            loadModelsTab();
        }
    } catch (error) {
        // Error already shown
    }
}

async function deleteAlias(aliasName) {
    if (!confirm(`Delete alias "${aliasName}"?`)) {
        return;
    }

    try {
        await fetchAPI(`/aliases/${encodeURIComponent(aliasName)}`, { method: 'DELETE' });
        showToast('Alias deleted', 'success');
        loadModelsTab();
    } catch (error) {
        // Error already shown
    }
}

// ─── Fallback Chain Modals ─────────────────────────────────────────────────────

function showAddFallbackModal() {
    const existingModal = document.querySelector('.modal-overlay');
    if (existingModal) existingModal.remove();

    const primaryModelsOptions = state.primaryModels.map(m =>
        `<option value="${m.name}">${escapeHtml(m.name)} - ${escapeHtml(m.description || '')}</option>`
    ).join('');

    const modalHtml = `
        <div class="modal-overlay" onclick="closeModal(event)">
            <div class="modal" onclick="event.stopPropagation()" style="max-width: 600px;">
                <div class="modal-header">
                    <h3 class="modal-title">🔗 Set Fallback Chain</h3>
                    <button class="modal-close" onclick="closeModal()">&times;</button>
                </div>
                <div class="form-group">
                    <label class="form-label">Primary Model</label>
                    <select id="fallback-primary" class="form-input">
                        ${primaryModelsOptions}
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Fallback Models (comma-separated)</label>
                    <textarea id="fallback-models" class="form-input" rows="4" placeholder="free-router/fast-groq, free-router/fast-openrouter"></textarea>
                    <p style="font-size: 0.85rem; color: var(--text-muted); margin-top: 5px;">
                        Enter model aliases in order of preference
                    </p>
                </div>
                <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
                    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                    <button class="btn btn-primary" onclick="setFallbackChain()">Save Chain</button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

async function setFallbackChain() {
    const primary = document.getElementById('fallback-primary').value;
    const fallbacksText = document.getElementById('fallback-models').value.trim();
    const fallbacks = fallbacksText ? fallbacksText.split(',').map(f => f.trim()).filter(f => f) : [];

    try {
        const result = await fetchAPI(`/fallbacks/${encodeURIComponent(primary)}`, {
            method: 'PUT',
            body: JSON.stringify({ fallbacks }),
        });

        if (result.success) {
            showToast('Fallback chain saved!', 'success');
            closeModal();
            loadModelsTab();
        }
    } catch (error) {
        // Error already shown
    }
}

function showEditFallbackModal(primaryModel) {
    // Find the primary model in the list
    const model = state.primaryModels.find(m => m.name === primaryModel);
    if (!model) return;

    const existingModal = document.querySelector('.modal-overlay');
    if (existingModal) existingModal.remove();

    // Get current fallbacks
    fetchAPI(`/fallbacks/${encodeURIComponent(primaryModel)}`).then(data => {
        const modalHtml = `
            <div class="modal-overlay" onclick="closeModal(event)">
                <div class="modal" onclick="event.stopPropagation()" style="max-width: 600px;">
                    <div class="modal-header">
                        <h3 class="modal-title">✏️ Edit Fallback Chain: ${escapeHtml(primaryModel)}</h3>
                        <button class="modal-close" onclick="closeModal()">&times;</button>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Fallback Models (comma-separated)</label>
                        <textarea id="edit-fallback-models" class="form-input" rows="4">${data.fallbacks ? data.fallbacks.join(', ') : ''}</textarea>
                    </div>
                    <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
                        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                        <button class="btn btn-primary" onclick="updateFallbackChain('${primaryModel}')">Save</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }).catch(() => {
        showToast('Failed to load fallback chain', 'error');
    });
}

async function updateFallbackChain(primaryModel) {
    const fallbacksText = document.getElementById('edit-fallback-models').value.trim();
    const fallbacks = fallbacksText ? fallbacksText.split(',').map(f => f.trim()).filter(f => f) : [];

    try {
        const result = await fetchAPI(`/fallbacks/${encodeURIComponent(primaryModel)}`, {
            method: 'PUT',
            body: JSON.stringify({ fallbacks }),
        });

        if (result.success) {
            showToast('Fallback chain updated!', 'success');
            closeModal();
            loadModelsTab();
        }
    } catch (error) {
        // Error already shown
    }
}

// ─── Chat Tab ─────────────────────────────────────────────────────────────────

async function loadChatTab() {
    const content = document.getElementById('content');

    try {
        // Load models and conversations
        const [modelsData, convsData] = await Promise.all([
            fetchAPI('/models'),
            fetchAPI('/chat/conversations'),
        ]);

        state.models = Object.keys(modelsData.models);
        state.conversations = convsData.conversations || [];

        // Create new conversation if none exists
        if (state.conversations.length === 0) {
            const newConvId = await createNewConversation();
            if (!newConvId) {
                content.innerHTML = `<div class="card"><p>Error creating conversation</p></div>`;
                return;
            }
        } else {
            // Load most recent conversation
            // Sort by updated_at descending
            const sortedConvs = [...state.conversations].sort((a, b) => {
                const dateA = new Date(a.updated_at || a.created_at || 0);
                const dateB = new Date(b.updated_at || b.created_at || 0);
                return dateB - dateA;
            });

            state.currentConversationId = sortedConvs[0].id;
            await loadConversation(state.currentConversationId);
        }

        content.innerHTML = renderChatContent();
        initChatEvents();
    } catch (error) {
        content.innerHTML = `<div class="card"><p>Error loading chat: ${escapeHtml(error.message)}</p></div>`;
    }
}

async function createNewConversation() {
    try {
        const result = await fetchAPI('/chat/conversations', {
            method: 'POST',
            body: JSON.stringify({ title: 'New Chat' }),
        });
        state.currentConversationId = result.conversation_id;

        // Refresh conversations list
        const convsData = await fetchAPI('/chat/conversations');
        state.conversations = convsData.conversations || [];

        await loadConversation(result.conversation_id);
        return result.conversation_id;
    } catch (error) {
        showToast('Failed to create conversation', 'error');
        return null;
    }
}

async function loadConversation(convId) {
    try {
        const result = await fetchAPI(`/chat/conversations/${convId}`);
        state.currentConversationId = convId;
        state.currentConversation = result;

        // Update conversation in the list if it exists, otherwise add it
        const existingIndex = state.conversations.findIndex(c => c.id === convId);
        if (existingIndex >= 0) {
            state.conversations[existingIndex] = {
                id: convId,
                title: result.title || 'Untitled',
                created_at: result.created_at,
                updated_at: result.updated_at,
                message_count: result.messages?.length || 0
            };
        } else {
            state.conversations.unshift({
                id: convId,
                title: result.title || 'Untitled',
                created_at: result.created_at,
                updated_at: result.updated_at,
                message_count: result.messages?.length || 0
            });
        }
    } catch (error) {
        showToast('Failed to load conversation', 'error');
    }
}

function renderChatContent() {
    const conversation = state.currentConversation || { messages: [], title: 'New Chat' };
    const hasMessages = conversation.messages && conversation.messages.length > 0;

    return `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">💬 Test Chat</h2>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <select id="model-select" class="form-input" style="width: auto;">
                        ${state.models.map(model => `
                            <option value="${model}" ${model === state.selectedModel ? 'selected' : ''}>
                                ${model}
                            </option>
                        `).join('')}
                    </select>
                    <button class="btn btn-secondary btn-small" onclick="loadChatTab()">↻ Refresh</button>
                </div>
            </div>

            <div class="chat-layout">
                <div class="chat-sidebar">
                    <div class="chat-sidebar-header">
                        <button class="btn btn-primary btn-small" onclick="createNewConversationAndRefresh()">+ New Chat</button>
                    </div>
                    <div class="conversation-list">
                        ${state.conversations.map(conv => `
                            <div class="conversation-item ${conv.id === state.currentConversationId ? 'active' : ''}"
                                 data-conv-id="${conv.id}">
                                <div class="conversation-title">${escapeHtml(conv.title || 'Untitled')}</div>
                                <div class="conversation-meta">
                                    ${conv.message_count || 0} messages
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <div class="chat-main">
                    <div class="chat-messages" id="chat-messages">
                        ${!hasMessages ? `
                            <div class="empty-state">
                                <p>Start a new conversation</p>
                            </div>
                        ` : conversation.messages.map(msg => renderChatMessage(msg)).join('')}
                    </div>

                    <div class="chat-input-area">
                        <div class="chat-input-container">
                            <textarea id="chat-input" class="chat-input"
                                      placeholder="Type your message... (Shift+Enter for newline)"
                                      rows="3"
                                      onkeydown="handleChatKeydown(event)"></textarea>
                            <div class="chat-actions">
                                <button class="btn btn-secondary btn-small" onclick="toggleImageUpload()" title="Upload image">
                                    📷
                                </button>
                                <button class="btn btn-primary" id="send-button" onclick="sendMessage()" ${state.isStreaming ? 'disabled' : ''}>
                                    ${state.isStreaming ? 'Sending...' : 'Send'}
                                </button>
                            </div>
                        </div>
                        <div id="image-preview-container" class="image-preview-container" style="display: none;"></div>
                        <div class="chat-options">
                            <label style="display: flex; align-items: center; gap: 5px; font-size: 0.85rem;">
                                <input type="checkbox" id="stream-toggle" checked onchange="toggleStreaming(this.checked)">
                                Streaming
                            </label>
                            <label style="display: flex; align-items: center; gap: 5px; font-size: 0.85rem;">
                                <input type="checkbox" id="compare-toggle" onchange="toggleCompare(this.checked)">
                                Compare Models
                            </label>
                        </div>
                        <div id="compare-models-container" class="compare-models-container" style="display: none;">
                            <div class="form-group">
                                <label class="form-label">Select models to compare</label>
                                <div class="model-checkboxes">
                                    ${state.models.map(model => `
                                        <label style="display: flex; align-items: center; gap: 5px; margin-right: 15px;">
                                            <input type="checkbox" class="compare-model-checkbox" value="${model}" ${model === state.selectedModel ? 'checked' : ''}>
                                            ${escapeHtml(model)}
                                        </label>
                                    `).join('')}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h2 class="card-title">ℹ️ About Auto-Routing</h2>
            </div>
            <div style="color: var(--text-secondary);">
                <p>Using <code>free-router/auto</code> will automatically classify your request and select the best model:</p>
                <ul style="padding-left: 20px; margin-top: 10px;">
                    <li><strong>Coding questions</strong> → free-router/coder</li>
                    <li><strong>Math/Reasoning</strong> → free-router/reasoning</li>
                    <li><strong>Image analysis</strong> → free-router/vision</li>
                    <li><strong>Simple chat</strong> → free-router/fast</li>
                    <li><strong>Complex tasks</strong> → free-router/smart</li>
                </ul>
            </div>
        </div>
    `;
}

function renderChatMessage(message) {
    const isUser = message.role === 'user';
    const hasImage = message.image || (message.content && message.content.includes && message.content.includes('data:image'));

    return `
        <div class="message ${isUser ? 'user' : 'assistant'}">
            <div class="message-header">
                ${isUser ? '👤 You' : '🤖 Assistant'}
                <span style="font-size: 0.75rem; color: var(--text-muted); margin-left: auto;">
                    ${formatDateTime(message.timestamp)}
                </span>
            </div>
            <div class="message-content">
                ${hasImage ? `
                    <div class="message-image">
                        <img src="${escapeHtml(message.image || (message.content && message.content.match && message.content.match(/data:image[^"]+/)?.[0]))}"
                             alt="Uploaded image" style="max-width: 100%; border-radius: 8px; margin-bottom: 10px;">
                    </div>
                ` : ''}
                <div class="message-text">${escapeHtml(message.content || '')}</div>
            </div>
        </div>
    `;
}

function initChatEvents() {
    const modelSelect = document.getElementById('model-select');
    if (modelSelect) {
        modelSelect.addEventListener('change', (e) => {
            state.selectedModel = e.target.value;
        });
    }

    // Add click handlers for conversation items
    const conversationItems = document.querySelectorAll('.conversation-item');
    conversationItems.forEach(item => {
        item.addEventListener('click', () => {
            const convId = item.dataset.convId;
            if (convId && convId !== state.currentConversationId) {
                loadConversationById(convId);
            }
        });
    });
}

function handleChatKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

async function createNewConversationAndRefresh() {
    await createNewConversation();
    const content = document.getElementById('content');
    if (content) {
        content.innerHTML = renderChatContent();
        initChatEvents();
    }
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    const imagePreview = document.getElementById('image-preview-container');
    const imageData = imagePreview?.dataset?.image || null;

    if (!message && !imageData) {
        showToast('Please enter a message or upload an image', 'error');
        return;
    }

    if (!state.currentConversationId) {
        showToast('No conversation selected', 'error');
        return;
    }

    // Clear input
    input.value = '';
    if (imagePreview) {
        imagePreview.style.display = 'none';
        imagePreview.dataset.image = '';
        imagePreview.innerHTML = '';
    }

    // Add user message to conversation
    const userMessage = {
        role: 'user',
        content: message,
        timestamp: new Date().toISOString(),
        ...(imageData && { image: imageData }),
    };

    // Add to UI immediately
    const chatMessages = document.getElementById('chat-messages');
    const userMsgHtml = renderChatMessage(userMessage);
    chatMessages.insertAdjacentHTML('beforeend', userMsgHtml);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Add to conversation
    try {
        await fetchAPI(`/chat/conversations/${state.currentConversationId}/messages`, {
            method: 'POST',
            body: JSON.stringify(userMessage),
        });
    } catch (error) {
        // Continue anyway
    }

    // Check if we should use compare mode
    const compareToggle = document.getElementById('compare-toggle');
    const selectedModels = Array.from(document.querySelectorAll('.compare-model-checkbox:checked')).map(cb => cb.value);

    if (compareToggle?.checked && selectedModels.length > 1) {
        await sendCompareRequest(selectedModels, [...(state.currentConversation?.messages || []), userMessage].map(m => ({ role: m.role, content: m.content })));
    } else {
        await sendStreamingRequest(userMessage);
    }
}

async function sendStreamingRequest(userMessage) {
    state.isStreaming = true;
    updateChatButtons();

    const chatMessages = document.getElementById('chat-messages');
    const assistantMsgId = 'msg-' + Date.now();

    // Add placeholder for assistant response
    const placeholderHtml = `
        <div id="${assistantMsgId}" class="message assistant">
            <div class="message-header">🤖 Assistant</div>
            <div class="message-text streaming">Thinking...</div>
        </div>
    `;
    chatMessages.insertAdjacentHTML('beforeend', placeholderHtml);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const messages = [...(state.currentConversation?.messages || []), userMessage].map(m => ({ role: m.role, content: m.content }));

        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model: state.selectedModel,
                messages: messages,
                stream: true,
                temperature: 0.7,
                max_tokens: 4096,
            }),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
            throw new Error(errorData.detail || errorData.error || `HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;

            // Process complete lines
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer

            for (const line of lines) {
                const trimmedLine = line.trim();
                if (!trimmedLine) continue;

                // Handle SSE format: "data: {...}"
                if (trimmedLine.startsWith('data: ')) {
                    const data = trimmedLine.slice(6);

                    // Skip heartbeat/completion markers
                    if (data === '[DONE]' || data === '') continue;

                    try {
                        // Try parsing as JSON
                        const parsed = JSON.parse(data);

                        // Handle different SSE event types
                        if (parsed.choices && parsed.choices[0]?.delta?.content) {
                            const content = parsed.choices[0].delta.content;
                            if (content) {
                                fullContent += content;
                                const msgElement = document.getElementById(assistantMsgId);
                                if (msgElement) {
                                    msgElement.querySelector('.message-text').textContent = fullContent;
                                    chatMessages.scrollTop = chatMessages.scrollHeight;
                                }
                            }
                        }
                    } catch (e) {
                        // If not JSON, try plain text format
                        // Some servers send raw text
                        if (data && !data.startsWith('{')) {
                            fullContent += data;
                            const msgElement = document.getElementById(assistantMsgId);
                            if (msgElement) {
                                msgElement.querySelector('.message-text').textContent = fullContent;
                                chatMessages.scrollTop = chatMessages.scrollHeight;
                            }
                        }
                    }
                }
            }
        }

        // Process any remaining buffer
        if (buffer.trim()) {
            const trimmedLine = buffer.trim();
            if (trimmedLine.startsWith('data: ')) {
                const data = trimmedLine.slice(6);
                if (data && data !== '[DONE]' && data !== '') {
                    try {
                        const parsed = JSON.parse(data);
                        if (parsed.choices && parsed.choices[0]?.delta?.content) {
                            fullContent += parsed.choices[0].delta.content;
                        }
                    } catch (e) {
                        // Plain text fallback
                        fullContent += data;
                    }
                }
            }
        }

        // Save assistant message
        const assistantMessage = {
            role: 'assistant',
            content: fullContent || 'No response received',
            timestamp: new Date().toISOString(),
        };

        try {
            await fetchAPI(`/chat/conversations/${state.currentConversationId}/messages`, {
                method: 'POST',
                body: JSON.stringify(assistantMessage),
            });
        } catch (error) {
            // Continue anyway
        }

    } catch (error) {
        const msgElement = document.getElementById(assistantMsgId);
        if (msgElement) {
            msgElement.querySelector('.message-text').innerHTML = `<span style="color: var(--error);">Error: ${escapeHtml(error.message)}</span>`;
        }
        showToast('Failed to get response: ' + error.message, 'error');
    } finally {
        state.isStreaming = false;
        updateChatButtons();
    }
}

async function sendCompareRequest(selectedModels, messages) {
    state.isStreaming = true;
    updateChatButtons();

    const chatMessages = document.getElementById('chat-messages');

    // Add placeholders for each model
    const msgIds = selectedModels.map((model, idx) => {
        const msgId = `msg-compare-${idx}-${Date.now()}`;
        const placeholderHtml = `
            <div id="${msgId}" class="message assistant compare">
                <div class="message-header">
                    🤖 ${escapeHtml(model)}
                    <span class="compare-badge">Thinking...</span>
                </div>
                <div class="message-text streaming">Waiting...</div>
            </div>
        `;
        chatMessages.insertAdjacentHTML('beforeend', placeholderHtml);
        return { id: msgId, model };
    });

    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const result = await fetchAPI('/chat/compare', {
            method: 'POST',
            body: JSON.stringify({
                models: selectedModels,
                messages: messages,
                temperature: 0.7,
                max_tokens: 1024,
            }),
        });

        // Update each model's response
        result.results.forEach((res) => {
            const msgId = msgIds.find(m => m.model === res.model)?.id;
            if (msgId) {
                const msgElement = document.getElementById(msgId);
                if (msgElement) {
                    if (res.error) {
                        msgElement.querySelector('.message-text').innerHTML = `<span style="color: var(--error);">Error: ${escapeHtml(res.error)}</span>`;
                    } else {
                        msgElement.querySelector('.message-text').textContent = res.response || 'No response';
                        const badge = msgElement.querySelector('.compare-badge');
                        if (badge) badge.textContent = 'Response';
                    }
                }
            }
        });

        chatMessages.scrollTop = chatMessages.scrollHeight;

    } catch (error) {
        showToast('Comparison failed: ' + error.message, 'error');
    } finally {
        state.isStreaming = false;
        updateChatButtons();
    }
}

function updateChatButtons() {
    const sendBtn = document.getElementById('send-button');
    if (sendBtn) {
        sendBtn.disabled = state.isStreaming;
        sendBtn.textContent = state.isStreaming ? 'Sending...' : 'Send';
    }
}

function toggleStreaming(enabled) {
    state.streamingEnabled = enabled;
}

function toggleCompare(enabled) {
    state.showCompare = enabled;
    const compareContainer = document.getElementById('compare-models-container');
    if (compareContainer) {
        compareContainer.style.display = enabled ? 'block' : 'none';
    }
}

async function loadConversationById(convId) {
    if (!convId || convId === state.currentConversationId) return;

    state.currentConversationId = convId;
    await loadConversation(convId);

    // Re-render chat
    const content = document.getElementById('content');
    if (content && state.currentTab === 'chat') {
        content.innerHTML = renderChatContent();
        initChatEvents();
    }
}

// ─── Image Upload ──────────────────────────────────────────────────────────────

function toggleImageUpload() {
    const existingModal = document.querySelector('.modal-overlay');
    if (existingModal) existingModal.remove();

    const modalHtml = `
        <div class="modal-overlay" onclick="closeModal(event)">
            <div class="modal" onclick="event.stopPropagation()" style="max-width: 500px;">
                <div class="modal-header">
                    <h3 class="modal-title">📷 Upload Image</h3>
                    <button class="modal-close" onclick="closeModal()">&times;</button>
                </div>
                <div class="form-group">
                    <label class="form-label">Select Image</label>
                    <input type="file" id="image-file-input" class="form-input" accept="image/*">
                </div>
                <div id="image-preview" style="margin: 15px 0; text-align: center; display: none;">
                    <img id="preview-img" style="max-width: 100%; max-height: 300px; border-radius: 8px;">
                </div>
                <div style="display: flex; gap: 10px; justify-content: flex-end;">
                    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                    <button class="btn btn-primary" onclick="confirmImageUpload()">Use Image</button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // Setup file input
    const fileInput = document.getElementById('image-file-input');
    const preview = document.getElementById('image-preview');
    const previewImg = document.getElementById('preview-img');

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (event) => {
                previewImg.src = event.target.result;
                preview.style.display = 'block';
            };
            reader.readAsDataURL(file);
        }
    });
}

async function confirmImageUpload() {
    const fileInput = document.getElementById('image-file-input');
    const file = fileInput.files[0];

    if (!file) {
        showToast('Please select an image', 'error');
        return;
    }

    const reader = new FileReader();
    reader.onload = async (event) => {
        const base64Data = event.target.result;

        // Show preview in chat input area
        const previewContainer = document.getElementById('image-preview-container');
        previewContainer.innerHTML = `
            <div style="display: flex; align-items: center; gap: 10px; padding: 10px; background: var(--bg-input); border-radius: 8px; margin-top: 10px;">
                <img src="${escapeHtml(base64Data)}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;">
                <span style="flex: 1;">${escapeHtml(file.name)}</span>
                <button class="btn btn-secondary btn-small" onclick="clearImageUpload()">Remove</button>
            </div>
        `;
        previewContainer.style.display = 'block';
        previewContainer.dataset.image = base64Data;

        closeModal();
        showToast('Image ready to send', 'success');
    };
    reader.readAsDataURL(file);
}

function clearImageUpload() {
    const previewContainer = document.getElementById('image-preview-container');
    previewContainer.style.display = 'none';
    previewContainer.dataset.image = '';
    previewContainer.innerHTML = '';
}

// ─── Config Tab ───────────────────────────────────────────────────────────────

async function loadConfigTab() {
    const content = document.getElementById('content');

    try {
        const configData = await fetchAPI('/config/export');
        content.innerHTML = renderConfigContent(configData.export);
    } catch (error) {
        content.innerHTML = `<div class="card"><p>Error loading config: ${escapeHtml(error.message)}</p></div>`;
    }
}

function renderConfigContent(exportConfig) {
    return `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">📋 Configuration Export</h2>
            </div>
            <p style="color: var(--text-secondary); margin-bottom: 20px;">
                Copy these settings to connect your favorite tools to FreeRouter.
            </p>

            ${renderConfigSection('cursor', 'Cursor IDE', exportConfig)}
            ${renderConfigSection('continue', 'VS Code + Continue', exportConfig)}
            ${renderConfigSection('python', 'Python', exportConfig)}
            ${renderConfigSection('curl', 'cURL', exportConfig)}
        </div>
    `;
}

function renderConfigSection(key, title, exportConfig) {
    const config = exportConfig[key];
    if (!config) return '';

    let contentHtml = '';

    if (config.instructions) {
        contentHtml += `<ol class="config-instructions">
            ${config.instructions.map(i => `<li>${escapeHtml(i)}</li>`).join('')}
        </ol>`;
    }

    if (config.config_example) {
        const json = JSON.stringify(config.config_example, null, 2);
        contentHtml += `
            <div class="config-content">
                <button class="btn btn-small btn-secondary copy-btn" onclick="copyToClipboard(${escapeHtml(JSON.stringify(json))})">
                    Copy
                </button>
                <pre>${escapeHtml(json)}</pre>
            </div>
        `;
    }

    if (config.code_example) {
        contentHtml += `
            <div class="config-content">
                <button class="btn btn-small btn-secondary copy-btn" onclick="copyToClipboard(${escapeHtml(JSON.stringify(config.code_example))})">
                    Copy
                </button>
                <pre>${escapeHtml(config.code_example)}</pre>
            </div>
        `;
    }

    if (config.command_example) {
        contentHtml += `
            <div class="config-content">
                <button class="btn btn-small btn-secondary copy-btn" onclick="copyToClipboard(${escapeHtml(JSON.stringify(config.command_example))})">
                    Copy
                </button>
                <pre>${escapeHtml(config.command_example)}</pre>
            </div>
        `;
    }

    return `
        <div class="config-section">
            <h3 class="config-title">${escapeHtml(title)}</h3>
            ${contentHtml}
        </div>
    `;
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!', 'success');
    }).catch(() => {
        showToast('Failed to copy', 'error');
    });
}

// ─── Usage Tab ────────────────────────────────────────────────────────────────

async function loadUsageTab() {
    const content = document.getElementById('content');

    try {
        const [usageData, healthData] = await Promise.all([
            fetchAPI('/usage'),
            fetchAPI('/health/summary'),
        ]);

        content.innerHTML = renderUsageContent(usageData.usage, healthData);
    } catch (error) {
        content.innerHTML = `<div class="card"><p>Error loading usage: ${escapeHtml(error.message)}</p></div>`;
    }
}

function renderUsageContent(usage, health) {
    return `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">📊 Provider Health Summary</h2>
                <button class="btn btn-secondary btn-small" onclick="loadUsageTab()">
                    ↻ Refresh
                </button>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px;">
                <div style="text-align: center; padding: 15px; background: var(--bg-input); border-radius: var(--radius);">
                    <div style="font-size: 2rem; font-weight: bold; color: var(--success);">${health.healthy || 0}</div>
                    <div style="color: var(--text-secondary);">Healthy</div>
                </div>
                <div style="text-align: center; padding: 15px; background: var(--bg-input); border-radius: var(--radius);">
                    <div style="font-size: 2rem; font-weight: bold; color: var(--error);">${health.unhealthy || 0}</div>
                    <div style="color: var(--text-secondary);">Unhealthy</div>
                </div>
                <div style="text-align: center; padding: 15px; background: var(--bg-input); border-radius: var(--radius);">
                    <div style="font-size: 2rem; font-weight: bold; color: var(--warning);">${health.unconfigured || 0}</div>
                    <div style="color: var(--text-secondary);">Not Configured</div>
                </div>
            </div>

            ${health.details?.map(d => `
                <div class="provider-item" style="margin-bottom: 10px;">
                    <div class="provider-info">
                        <span class="health-dot ${d.status}"></span>
                        <span>${escapeHtml(d.name)}</span>
                    </div>
                    <span class="status-badge ${d.status}">${escapeHtml(d.message)}</span>
                </div>
            `).join('')}
        </div>

        <div class="card">
            <div class="card-header">
                <h2 class="card-title">📈 Rate Limit Usage</h2>
            </div>
            ${Object.keys(usage || {}).length === 0 ? `
                <p style="color: var(--text-secondary);">
                    No usage data yet. Usage statistics will appear here after making requests.
                </p>
            ` : `
                <div class="provider-list">
                    ${Object.entries(usage).map(([name, data]) => {
        const pct = data.used_pct !== null && data.used_pct !== undefined ? data.used_pct * 100 : 0;
        const barClass = pct < 70 ? 'low' : (pct < 90 ? 'medium' : 'high');

        return `
                            <div class="card" style="margin-bottom: 10px; padding: 15px;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                                    <span style="font-weight: 600;">${escapeHtml(name)}</span>
                                    <span style="color: var(--text-secondary);">
                                        ${data.requests_remaining !== null && data.requests_remaining !== undefined ? `${data.requests_remaining} / ${data.requests_limit}` : 'Unlimited'}
                                    </span>
                                </div>
                                ${data.requests_limit > 0 ? `
                                    <div class="usage-bar-container">
                                        <div class="usage-bar ${barClass}" style="width: ${pct}%;"></div>
                                    </div>
                                    <div style="display: flex; justify-content: space-between; margin-top: 5px; font-size: 0.85rem; color: var(--text-muted);">
                                        <span>${pct.toFixed(1)}% used</span>
                                        ${data.is_soft_limited ? '<span style="color: var(--warning);">Near limit</span>' : ''}
                                        ${data.is_hard_limited ? '<span style="color: var(--error);">Rate limited</span>' : ''}
                                    </div>
                                ` : `
                                    <div style="color: var(--text-muted); font-size: 0.85rem;">No rate limit data available</div>
                                `}
                            </div>
                        `;
    }).join('')}
                </div>
            `}
        </div>
    `;
}

// ─── Initialize ───────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    switchTab('providers');
});
