// config.js - Configuration page logic

document.addEventListener('DOMContentLoaded', () => {
    console.log('Config page initialized');

    // Initialize all config sections
    initProfileSettings();
    initProviderSettings();
    initSessionContext();
    initGlobalProfile();
    initGlobalKnowledge();
    initAPIKeys();
});

/**
 * Profile Settings
 */
function initProfileSettings() {
    const form = document.getElementById('profileForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const displayName = document.getElementById('display-name').value;
        const partnerName = document.getElementById('partner-name').value;
        const affection = document.getElementById('affection-level').value;

        try {
            const response = await API.post('/api/update_profile', {
                display_name: displayName,
                partner_name: partnerName,
                affection: parseInt(affection)
            });

            if (response.success) {
                Utils.showNotification('Profile updated successfully', 'success');
            }
        } catch (error) {
            console.error('Error updating profile:', error);
            Utils.showNotification('Error updating profile', 'error');
        }
    });
}

/**
 * AI Provider Settings
 */
function initProviderSettings() {
    const providerSelect = document.getElementById('ai-provider');
    const modelSelect = document.getElementById('ai-model');
    const testButton = document.getElementById('test-provider');
    const saveButton = document.getElementById('save-provider');

    if (!providerSelect) return;

    // Load available providers
    loadProviders();

    // Handle provider change
    providerSelect.addEventListener('change', async () => {
        const provider = providerSelect.value;
        if (provider) {
            await loadModels(provider);
        }
    });

    // Test connection
    if (testButton) {
        testButton.addEventListener('click', async () => {
            const provider = providerSelect.value;
            const model = modelSelect.value;

            if (!provider || !model) {
                Utils.showNotification('Please select provider and model', 'warning');
                return;
            }

            testButton.textContent = 'Testing...';
            testButton.disabled = true;

            try {
                const response = await API.post('/api/providers/test_connection', {
                    provider: provider,
                    model: model
                });

                if (response.success) {
                    Utils.showNotification('Connection successful!', 'success');
                    document.getElementById('connection-status').textContent = 'Connected';
                } else {
                    Utils.showNotification('Connection failed', 'error');
                    document.getElementById('connection-status').textContent = 'Failed';
                }
            } catch (error) {
                console.error('Error testing provider:', error);
                Utils.showNotification('Error testing connection', 'error');
                document.getElementById('connection-status').textContent = 'Error';
            } finally {
                testButton.textContent = 'Test Connection';
                testButton.disabled = false;
            }
        });
    }

    // Save provider settings
    if (saveButton) {
        saveButton.addEventListener('click', async (e) => {
            e.preventDefault();

            const provider = providerSelect.value;
            const model = modelSelect.value;

            if (!provider || !model) {
                Utils.showNotification('Please select provider and model', 'warning');
                return;
            }

            try {
                const response = await API.post('/api/providers/set_preferred', {
                    provider: provider,
                    model: model
                });

                if (response.success) {
                    Utils.showNotification('Provider settings saved', 'success');
                }
            } catch (error) {
                console.error('Error saving provider:', error);
                Utils.showNotification('Error saving provider settings', 'error');
            }
        });
    }
}

async function loadProviders() {
    try {
        const response = await API.get('/api/providers/list');
        const providerSelect = document.getElementById('ai-provider');
        const currentProviderSpan = document.getElementById('current-provider');

        if (response.providers) {
            providerSelect.innerHTML = '<option value="">Select a provider...</option>';
            response.providers.forEach(provider => {
                const option = document.createElement('option');
                option.value = provider.id;
                option.textContent = provider.name;
                if (provider.is_current) {
                    option.selected = true;
                    currentProviderSpan.textContent = provider.name;
                }
                providerSelect.appendChild(option);
            });

            // Load models for current provider
            if (response.current_provider) {
                await loadModels(response.current_provider);
            }
        }
    } catch (error) {
        console.error('Error loading providers:', error);
    }
}

async function loadModels(provider) {
    try {
        const response = await API.get(`/api/models?provider=${provider}`);
        const modelSelect = document.getElementById('ai-model');

        if (response.models) {
            modelSelect.innerHTML = '<option value="">Select a model...</option>';
            response.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.name;
                if (model.is_current) {
                    option.selected = true;
                }
                modelSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading models:', error);
    }
}

/**
 * Session Context
 */
function initSessionContext() {
    const contextDiv = document.getElementById('session-context');
    const updateBtn = document.getElementById('update-session-context');
    const clearBtn = document.getElementById('clear-chat-history');

    if (!contextDiv) return;

    // Load session context
    loadSessionContext();

    // Update context
    if (updateBtn) {
        updateBtn.addEventListener('click', async () => {
            updateBtn.textContent = 'Updating...';
            updateBtn.disabled = true;

            try {
                const response = await API.post('/api/update_session_context', {});
                if (response.success) {
                    Utils.showNotification('Session context updated', 'success');
                    await loadSessionContext();
                }
            } catch (error) {
                console.error('Error updating context:', error);
                Utils.showNotification('Error updating context', 'error');
            } finally {
                updateBtn.textContent = 'Update Session Context';
                updateBtn.disabled = false;
            }
        });
    }

    // Clear chat history
    if (clearBtn) {
        clearBtn.addEventListener('click', async () => {
            if (!confirm('Are you sure you want to clear all chat history?')) {
                return;
            }

            try {
                const response = await API.post('/api/clear_history', {});
                if (response.success) {
                    Utils.showNotification('Chat history cleared', 'success');
                    contextDiv.textContent = 'No session context available';
                }
            } catch (error) {
                console.error('Error clearing history:', error);
                Utils.showNotification('Error clearing history', 'error');
            }
        });
    }
}

async function loadSessionContext() {
    try {
        const response = await API.get('/api/session_context');
        const contextDiv = document.getElementById('session-context');
        const lastUpdated = document.getElementById('session-last-updated');

        if (response.context) {
            contextDiv.textContent = response.context;
            if (response.last_updated) {
                lastUpdated.textContent = Utils.formatDate(response.last_updated);
            }
        } else {
            contextDiv.textContent = 'No session context available';
        }
    } catch (error) {
        console.error('Error loading session context:', error);
    }
}

/**
 * Global Profile
 */
function initGlobalProfile() {
    const updateBtn = document.getElementById('update-global-profile');

    if (!updateBtn) return;

    // Load global profile
    loadGlobalProfile();

    // Update profile
    updateBtn.addEventListener('click', async () => {
        updateBtn.textContent = 'Updating...';
        updateBtn.disabled = true;

        try {
            const response = await API.post('/api/update_global_profile', {});
            if (response.success) {
                Utils.showNotification('Global profile updated', 'success');
                await loadGlobalProfile();
            }
        } catch (error) {
            console.error('Error updating global profile:', error);
            Utils.showNotification('Error updating global profile', 'error');
        } finally {
            updateBtn.textContent = 'Update Global Profile (All Sessions)';
            updateBtn.disabled = false;
        }
    });
}

async function loadGlobalProfile() {
    try {
        const response = await API.get('/api/global_profile');

        if (response.profile) {
            document.getElementById('player-summary').textContent = response.profile.summary || 'N/A';
            document.getElementById('player-likes').textContent = response.profile.likes || 'N/A';
            document.getElementById('player-dislikes').textContent = response.profile.dislikes || 'N/A';
            document.getElementById('player-personality').textContent = response.profile.personality || 'N/A';
            document.getElementById('player-memories').textContent = response.profile.memories || 'N/A';
            document.getElementById('player-relationship').textContent = response.profile.relationship || 'N/A';

            if (response.last_updated) {
                document.getElementById('global-profile-last-updated').textContent = Utils.formatDate(response.last_updated);
            }
        }
    } catch (error) {
        console.error('Error loading global profile:', error);
    }
}

/**
 * Global Knowledge
 */
function initGlobalKnowledge() {
    const textarea = document.getElementById('global-knowledge');
    const saveBtn = document.getElementById('save-global-knowledge');

    if (!textarea) return;

    // Load global knowledge
    loadGlobalKnowledge();

    // Save knowledge
    if (saveBtn) {
        saveBtn.addEventListener('click', async () => {
            const knowledge = textarea.value.trim();

            try {
                const response = await API.post('/api/update_global_knowledge', {
                    knowledge: knowledge
                });

                if (response.success) {
                    Utils.showNotification('Global knowledge saved', 'success');
                }
            } catch (error) {
                console.error('Error saving global knowledge:', error);
                Utils.showNotification('Error saving global knowledge', 'error');
            }
        });
    }
}

async function loadGlobalKnowledge() {
    try {
        const response = await API.get('/api/global_knowledge');
        const textarea = document.getElementById('global-knowledge');

        if (response.knowledge) {
            textarea.value = response.knowledge;
        }
    } catch (error) {
        console.error('Error loading global knowledge:', error);
    }
}

/**
 * API Keys Management
 */
function initAPIKeys() {
    const form = document.getElementById('apiKeyForm');
    const keysList = document.getElementById('keys-list');

    if (!form) return;

    // Load existing keys
    loadAPIKeys();

    // Add new key
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const provider = document.getElementById('api-key-provider').value;
        const key = document.getElementById('api-key').value.trim();

        if (!key) {
            Utils.showNotification('Please enter an API key', 'warning');
            return;
        }

        try {
            const response = await API.post('/api/add_api_key', {
                provider: provider,
                key: key
            });

            if (response.success) {
                Utils.showNotification('API key added successfully', 'success');
                document.getElementById('api-key').value = '';
                await loadAPIKeys();
            }
        } catch (error) {
            console.error('Error adding API key:', error);
            Utils.showNotification('Error adding API key', 'error');
        }
    });
}

async function loadAPIKeys() {
    try {
        const response = await API.get('/api/api_keys');
        const keysList = document.getElementById('keys-list');

        if (response.keys && response.keys.length > 0) {
            keysList.innerHTML = '';
            response.keys.forEach(key => {
                const li = document.createElement('li');
                li.textContent = `${key.provider}: ${key.masked_key}`;
                
                const deleteBtn = document.createElement('button');
                deleteBtn.textContent = 'Delete';
                deleteBtn.className = 'contrast';
                deleteBtn.style.marginLeft = '1rem';
                deleteBtn.style.padding = '0.25rem 0.5rem';
                deleteBtn.addEventListener('click', async () => {
                    await deleteAPIKey(key.id);
                });
                
                li.appendChild(deleteBtn);
                keysList.appendChild(li);
            });
        } else {
            keysList.innerHTML = '<li>No API keys stored</li>';
        }
    } catch (error) {
        console.error('Error loading API keys:', error);
    }
}

async function deleteAPIKey(keyId) {
    if (!confirm('Are you sure you want to delete this API key?')) {
        return;
    }

    try {
        const response = await API.delete(`/api/api_key/${keyId}`);
        if (response.success) {
            Utils.showNotification('API key deleted', 'success');
            await loadAPIKeys();
        }
    } catch (error) {
        console.error('Error deleting API key:', error);
        Utils.showNotification('Error deleting API key', 'error');
    }
}
