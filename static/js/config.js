// config.js - Configuration Page Logic

// Initialize config page
document.addEventListener('DOMContentLoaded', () => {
    initProfileSettings();
    initProviderSettings();
});

// Profile Settings
function initProfileSettings() {
    const affectionSlider = document.getElementById('affection-level');
    const affectionValue = document.getElementById('affection-value');
    const saveButton = document.getElementById('save-profile');

    if (affectionSlider && affectionValue) {
        affectionSlider.addEventListener('input', (e) => {
            affectionValue.textContent = e.target.value;
        });
    }

    if (saveButton) {
        saveButton.addEventListener('click', saveProfile);
    }
}

async function saveProfile() {
    const data = {
        display_name: document.getElementById('display-name').value,
        partner_name: document.getElementById('partner-name').value,
        affection: parseInt(document.getElementById('affection-level').value)
    };

    try {
        await apiCall('/api/update_profile', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        showNotification('Profile saved successfully', 'success');
    } catch (error) {
        console.error('Failed to save profile:', error);
        showNotification('Failed to save profile', 'error');
    }
}

// Provider Settings
function initProviderSettings() {
    loadProviders();
    
    const providerSelect = document.getElementById('provider-select');
    const saveProviderBtn = document.getElementById('save-provider');
    const testConnectionBtn = document.getElementById('test-connection');
    
    if (providerSelect) {
        providerSelect.addEventListener('change', onProviderChange);
    }
    
    if (saveProviderBtn) {
        saveProviderBtn.addEventListener('click', saveProviderSettings);
    }
    
    if (testConnectionBtn) {
        testConnectionBtn.addEventListener('click', testConnection);
    }
}

async function loadProviders() {
    try {
        const data = await apiCall('/api/providers/list');
        const providerSelect = document.getElementById('provider-select');
        const currentProvider = document.getElementById('current-provider');
        const statusText = document.getElementById('status-text');
        
        if (!providerSelect) return;
        
        // Clear existing options
        providerSelect.innerHTML = '<option value="">Select provider...</option>';
        
        if (data && data.providers) {
            data.providers.forEach(provider => {
                const option = document.createElement('option');
                option.value = provider.name;
                option.textContent = provider.display_name || provider.name;
                if (provider.is_preferred) {
                    option.selected = true;
                }
                providerSelect.appendChild(option);
            });
            
            // Show current provider
            if (data.current_provider && currentProvider) {
                currentProvider.textContent = data.current_provider.display_name || data.current_provider.name;
            }
            
            // Load models for current provider
            if (data.current_provider) {
                await loadModels(data.current_provider.name);
            }
            
            if (statusText) {
                statusText.textContent = 'Ready';
            }
        }
    } catch (error) {
        console.error('Failed to load providers:', error);
        const statusText = document.getElementById('status-text');
        if (statusText) {
            statusText.textContent = 'Error loading providers';
        }
    }
}

async function loadModels(provider) {
    try {
        const data = await apiCall(`/api/providers/list?provider=${provider}`);
        const modelSelect = document.getElementById('model-select');
        
        if (!modelSelect) return;
        
        // Clear existing options
        modelSelect.innerHTML = '<option value="">Select model...</option>';
        
        if (data && data.models) {
            data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.name;
                option.textContent = model.display_name || model.name;
                if (model.is_preferred) {
                    option.selected = true;
                }
                modelSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Failed to load models:', error);
        const modelSelect = document.getElementById('model-select');
        if (modelSelect) {
            modelSelect.innerHTML = '<option value="">Error loading models</option>';
        }
    }
}

async function onProviderChange(event) {
    const provider = event.target.value;
    if (provider) {
        await loadModels(provider);
    } else {
        const modelSelect = document.getElementById('model-select');
        if (modelSelect) {
            modelSelect.innerHTML = '<option value="">Select provider first...</option>';
        }
    }
}

async function saveProviderSettings() {
    const provider = document.getElementById('provider-select').value;
    const model = document.getElementById('model-select').value;
    
    if (!provider) {
        showNotification('Please select a provider', 'error');
        return;
    }
    
    try {
        await apiCall('/api/providers/set_preferred', {
            method: 'POST',
            body: JSON.stringify({ provider, model })
        });
        
        showNotification('Provider settings saved', 'success');
        await loadProviders(); // Reload to show updated settings
    } catch (error) {
        console.error('Failed to save provider settings:', error);
        showNotification('Failed to save provider settings', 'error');
    }
}

async function testConnection() {
    const provider = document.getElementById('provider-select').value;
    const statusText = document.getElementById('status-text');
    
    if (!provider) {
        showNotification('Please select a provider', 'error');
        return;
    }
    
    if (statusText) {
        statusText.textContent = 'Testing...';
    }
    
    try {
        const data = await apiCall('/api/providers/test_connection', {
            method: 'POST',
            body: JSON.stringify({ provider })
        });
        
        if (data && data.success) {
            if (statusText) {
                statusText.textContent = 'Connection successful';
            }
            showNotification('Connection test passed', 'success');
        } else {
            if (statusText) {
                statusText.textContent = 'Connection failed';
            }
            showNotification(data.message || 'Connection test failed', 'error');
        }
    } catch (error) {
        console.error('Connection test failed:', error);
        if (statusText) {
            statusText.textContent = 'Connection failed';
        }
        showNotification('Connection test failed', 'error');
    }
}
