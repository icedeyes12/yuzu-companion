// config.js - Configuration page logic

document.addEventListener('DOMContentLoaded', () => {
  loadProfile();
  loadProviders();
  loadApiKeys();
  
  // Profile settings
  document.getElementById('save-profile')?.addEventListener('click', saveProfile);
  document.getElementById('affection-level')?.addEventListener('input', (e) => {
    document.getElementById('affection-value').textContent = e.target.value;
  });

  // Provider settings
  document.getElementById('ai-provider')?.addEventListener('change', onProviderChange);
  document.getElementById('test-provider')?.addEventListener('click', testProvider);
  document.getElementById('save-provider')?.addEventListener('click', saveProvider);

  // API keys
  document.getElementById('add-api-key')?.addEventListener('click', addApiKey);
});

// Load profile
async function loadProfile() {
  try {
    const data = await apiCall('/api/get_profile');
    if (data) {
      document.getElementById('display-name').value = data.display_name || '';
      document.getElementById('partner-name').value = data.partner_name || '';
      document.getElementById('affection-level').value = data.affection || 50;
      document.getElementById('affection-value').textContent = data.affection || 50;
    }
  } catch (error) {
    console.error('Failed to load profile:', error);
  }
}

// Save profile
async function saveProfile() {
  try {
    const data = {
      display_name: document.getElementById('display-name').value,
      partner_name: document.getElementById('partner-name').value,
      affection: parseInt(document.getElementById('affection-level').value)
    };

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

// Load providers
async function loadProviders() {
  try {
    const data = await apiCall('/api/get_providers');
    const providerSelect = document.getElementById('ai-provider');
    
    if (data && data.providers) {
      providerSelect.innerHTML = '<option value="">Select provider...</option>';
      data.providers.forEach(provider => {
        const option = document.createElement('option');
        option.value = provider.name;
        option.textContent = provider.display_name || provider.name;
        providerSelect.appendChild(option);
      });

      if (data.current_provider) {
        providerSelect.value = data.current_provider;
        document.getElementById('current-provider').textContent = data.current_provider;
        onProviderChange();
      }
    }
  } catch (error) {
    console.error('Failed to load providers:', error);
  }
}

// Provider change handler
async function onProviderChange() {
  const provider = document.getElementById('ai-provider').value;
  if (!provider) return;

  try {
    const data = await apiCall(`/api/get_models?provider=${provider}`);
    const modelSelect = document.getElementById('ai-model');
    
    if (data && data.models) {
      modelSelect.innerHTML = '<option value="">Select model...</option>';
      data.models.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        modelSelect.appendChild(option);
      });

      if (data.current_model) {
        modelSelect.value = data.current_model;
      }
    }
  } catch (error) {
    console.error('Failed to load models:', error);
  }
}

// Test provider
async function testProvider() {
  const provider = document.getElementById('ai-provider').value;
  const statusEl = document.getElementById('connection-status');
  
  if (!provider) {
    showNotification('Please select a provider', 'warning');
    return;
  }

  statusEl.textContent = 'Testing...';

  try {
    const data = await apiCall('/api/test_provider', {
      method: 'POST',
      body: JSON.stringify({ provider })
    });

    if (data.success) {
      statusEl.textContent = 'Connected ✓';
      showNotification('Provider test successful', 'success');
    } else {
      statusEl.textContent = 'Failed ✗';
      showNotification('Provider test failed', 'error');
    }
  } catch (error) {
    statusEl.textContent = 'Error ✗';
    console.error('Failed to test provider:', error);
    showNotification('Provider test failed', 'error');
  }
}

// Save provider
async function saveProvider() {
  const provider = document.getElementById('ai-provider').value;
  const model = document.getElementById('ai-model').value;

  if (!provider || !model) {
    showNotification('Please select provider and model', 'warning');
    return;
  }

  try {
    await apiCall('/api/set_provider', {
      method: 'POST',
      body: JSON.stringify({ provider, model })
    });

    showNotification('Provider settings saved', 'success');
    document.getElementById('current-provider').textContent = provider;
  } catch (error) {
    console.error('Failed to save provider:', error);
    showNotification('Failed to save provider', 'error');
  }
}

// Load API keys
async function loadApiKeys() {
  try {
    const data = await apiCall('/api/get_api_keys');
    const keysList = document.getElementById('keys-list');
    
    if (data && data.keys) {
      keysList.innerHTML = '';
      
      if (data.keys.length === 0) {
        keysList.innerHTML = '<li>No API keys stored</li>';
      } else {
        data.keys.forEach(key => {
          const li = document.createElement('li');
          li.textContent = `${key.provider}: ${key.key_preview}`;
          
          const removeBtn = document.createElement('button');
          removeBtn.textContent = 'Remove';
          removeBtn.onclick = () => removeApiKey(key.provider);
          
          li.appendChild(removeBtn);
          keysList.appendChild(li);
        });
      }
    }
  } catch (error) {
    console.error('Failed to load API keys:', error);
  }
}

// Add API key
async function addApiKey() {
  const provider = document.getElementById('api-key-provider').value;
  const key = document.getElementById('api-key').value;

  if (!key) {
    showNotification('Please enter an API key', 'warning');
    return;
  }

  try {
    await apiCall('/api/add_api_key', {
      method: 'POST',
      body: JSON.stringify({ provider, api_key: key })
    });

    document.getElementById('api-key').value = '';
    showNotification('API key added successfully', 'success');
    loadApiKeys();
  } catch (error) {
    console.error('Failed to add API key:', error);
    showNotification('Failed to add API key', 'error');
  }
}

// Remove API key
async function removeApiKey(provider) {
  if (!confirm(`Remove API key for ${provider}?`)) return;

  try {
    await apiCall('/api/remove_api_key', {
      method: 'POST',
      body: JSON.stringify({ provider })
    });

    showNotification('API key removed', 'success');
    loadApiKeys();
  } catch (error) {
    console.error('Failed to remove API key:', error);
    showNotification('Failed to remove API key', 'error');
  }
}
