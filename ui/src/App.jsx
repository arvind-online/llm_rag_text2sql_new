import { useState, useRef, useEffect, useCallback } from 'react'
import './App.css'

const API_BASE = import.meta.env.BASE_URL || '/';

function App() {
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef(null)
  const abortControllerRef = useRef(null)

  // Provider/model state
  const [providers, setProviders] = useState([])
  const [currentProvider, setCurrentProvider] = useState('')
  const [currentModel, setCurrentModel] = useState('')
  const [selectedProvider, setSelectedProvider] = useState('')
  const [selectedModel, setSelectedModel] = useState('')
  const [availableModels, setAvailableModels] = useState([])
  const [isSwitching, setIsSwitching] = useState(false)
  const [isLoadingModels, setIsLoadingModels] = useState(false)
  const [providerError, setProviderError] = useState(null)
  const [toast, setToast] = useState(null)

  // Settings modal state
  const [showSettings, setShowSettings] = useState(false)
  const [providerKeys, setProviderKeys] = useState([])
  const [keyInputs, setKeyInputs] = useState({})
  const [savingKey, setSavingKey] = useState(null)
  const [keyVisibility, setKeyVisibility] = useState({})

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 5000)
      return () => clearTimeout(timer)
    }
  }, [toast])

  const showToast = (message, type = 'error') => {
    setToast({ message, type })
  }

  // Fetch current provider on mount
  useEffect(() => {
    fetchCurrentProvider()
    fetchProviders()
  }, [])

  const fetchCurrentProvider = async () => {
    try {
      const resp = await fetch(`${API_BASE}providers/current`)
      if (resp.ok) {
        const data = await resp.json()
        setCurrentProvider(data.provider)
        setCurrentModel(data.model)
        setSelectedProvider(data.provider)
        setSelectedModel(data.model)
      }
    } catch (e) {
      console.error('Failed to fetch current provider:', e)
    }
  }

  const fetchProviders = async () => {
    try {
      const resp = await fetch(`${API_BASE}providers`)
      if (resp.ok) {
        const data = await resp.json()
        setProviders(data)
      }
    } catch (e) {
      console.error('Failed to fetch providers:', e)
    }
  }

  const fetchModels = useCallback(async (provider) => {
    if (!provider) return
    setIsLoadingModels(true)
    setProviderError(null)
    setAvailableModels([])

    try {
      const resp = await fetch(`${API_BASE}providers/${provider}/models`)
      if (resp.ok) {
        const data = await resp.json()
        setAvailableModels(data)
        setProviderError(null)
      } else {
        const errorData = await resp.json().catch(() => ({ detail: 'Failed to fetch models' }))
        setProviderError(errorData.detail || 'Failed to fetch models')
        showToast(errorData.detail || `Failed to fetch models for ${provider}`)
      }
    } catch (e) {
      const msg = `Cannot reach server to fetch ${provider} models. Is the backend running?`
      setProviderError(msg)
      showToast(msg)
    } finally {
      setIsLoadingModels(false)
    }
  }, [])

  // When selected provider changes, fetch models
  useEffect(() => {
    if (selectedProvider) {
      fetchModels(selectedProvider)
    }
  }, [selectedProvider, fetchModels])

  // When models load, pre-select current or first
  useEffect(() => {
    if (availableModels.length > 0 && selectedProvider === currentProvider) {
      const found = availableModels.find(m => m.id === currentModel)
      if (found) {
        setSelectedModel(currentModel)
      } else {
        setSelectedModel(availableModels[0].id)
      }
    } else if (availableModels.length > 0) {
      setSelectedModel(availableModels[0].id)
    }
  }, [availableModels])

  const handleProviderChange = (e) => {
    const provider = e.target.value
    setSelectedProvider(provider)
    setSelectedModel('')
    setProviderError(null)
  }

  const handleModelChange = (e) => {
    setSelectedModel(e.target.value)
  }

  const handleSwitchProvider = async () => {
    if (!selectedProvider || !selectedModel) return
    if (selectedProvider === currentProvider && selectedModel === currentModel) {
      showToast('Already using this provider and model', 'info')
      return
    }

    setIsSwitching(true)
    setProviderError(null)

    try {
      const resp = await fetch(`${API_BASE}providers/switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: selectedProvider, model: selectedModel }),
      })

      const data = await resp.json()

      if (resp.ok && data.success) {
        setCurrentProvider(data.provider)
        setCurrentModel(data.model)
        showToast(data.message, 'success')
      } else {
        setSelectedProvider(currentProvider)
        setSelectedModel(currentModel)
        const errorMsg = data.detail || data.message || 'Failed to switch provider'
        setProviderError(errorMsg)
        showToast(errorMsg)
        fetchModels(currentProvider)
      }
    } catch (e) {
      setSelectedProvider(currentProvider)
      setSelectedModel(currentModel)
      const msg = 'Failed to connect to the server'
      setProviderError(msg)
      showToast(msg)
      fetchModels(currentProvider)
    } finally {
      setIsSwitching(false)
    }
  }

  // ---- Settings / Key Management ----

  const fetchProviderKeys = async () => {
    try {
      const resp = await fetch(`${API_BASE}providers/keys`)
      if (resp.ok) {
        const data = await resp.json()
        setProviderKeys(data)
        // Initialize key inputs as empty (user will type new values)
        const inputs = {}
        data.forEach(k => { inputs[k.provider] = '' })
        setKeyInputs(inputs)
        setKeyVisibility({})
      }
    } catch (e) {
      console.error('Failed to fetch provider keys:', e)
    }
  }

  const openSettings = () => {
    fetchProviderKeys()
    setShowSettings(true)
  }

  const closeSettings = () => {
    setShowSettings(false)
    setSavingKey(null)
  }

  const handleKeyInputChange = (provider, value) => {
    setKeyInputs(prev => ({ ...prev, [provider]: value }))
  }

  const toggleKeyVisibility = (provider) => {
    setKeyVisibility(prev => ({ ...prev, [provider]: !prev[provider] }))
  }

  const handleSaveKey = async (provider) => {
    const keyValue = keyInputs[provider]?.trim()
    if (!keyValue) {
      showToast('Please enter a key value', 'error')
      return
    }

    setSavingKey(provider)

    try {
      const resp = await fetch(`${API_BASE}providers/keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, key_value: keyValue }),
      })

      const data = await resp.json()

      if (resp.ok && data.success) {
        showToast(data.message, 'success')
        // Refresh keys to show updated masked value
        fetchProviderKeys()
        // Also refresh providers (availability might have changed)
        fetchProviders()
      } else {
        showToast(data.detail || 'Failed to update key', 'error')
      }
    } catch (e) {
      showToast('Failed to connect to server', 'error')
    } finally {
      setSavingKey(null)
    }
  }

  // ---- Chat ----

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
  }

  const handleClearSession = () => {
    setMessages([])
    showToast('New session started', 'success')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim() || isLoading) return

    // Create a new AbortController for this request
    const controller = new AbortController()
    abortControllerRef.current = controller

    const userMessage = { type: 'user', content: query }
    setMessages(prev => [...prev, userMessage])
    setQuery('')
    setIsLoading(true)

    // Build conversation history (last 5 user+assistant pairs) to send with the request
    const history = []
    for (let i = 0; i < messages.length - 1 && history.length < 5; i++) {
      if (messages[i].type === 'user' && messages[i + 1].type === 'assistant') {
        history.push({
          user: messages[i].content,
          assistant: messages[i + 1].content,
          sql_query: messages[i + 1].sql_query || null,
        })
      }
    }

    try {
      const response = await fetch(`${API_BASE}query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Timezone': Intl.DateTimeFormat().resolvedOptions().timeZone,
        },
        body: JSON.stringify({ query: query, history }),
        signal: controller.signal,
      })

      const data = await response.json()

      if (response.ok) {
        const assistantMessage = {
          type: 'assistant',
          content: data.answer,
          route: data.route_taken,
          sources: data.sources,
          sql_query: data.sql_query,
          sql_results: data.sql_results,
          model_used: data.model_used,
        }
        setMessages(prev => [...prev, assistantMessage])
      } else {
        setMessages(prev => [...prev, {
          type: 'error',
          content: data.detail || 'Something went wrong'
        }])
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        setMessages(prev => [...prev, {
          type: 'cancelled',
          content: 'Request cancelled by user'
        }])
      } else {
        setMessages(prev => [...prev, {
          type: 'error',
          content: 'Failed to connect to the server. Make sure it\'s running on port 8000.'
        }])
      }
    } finally {
      abortControllerRef.current = null
      setIsLoading(false)
    }
  }

  const getRouteIcon = (route) => {
    switch (route) {
      case 'rag': return '📚'
      case 'sql': return '🗃️'
      case 'hybrid': return '🔀'
      default: return '💬'
    }
  }

  const getRouteName = (route) => {
    switch (route) {
      case 'rag': return 'Document Search'
      case 'sql': return 'Database Query'
      case 'hybrid': return 'Hybrid Analysis'
      default: return 'Response'
    }
  }

  const getProviderIcon = (provider) => {
    switch (provider) {
      case 'groq': return '⚡'
      case 'ollama': return '🦙'
      case 'bedrock': return '☁️'
      default: return '🤖'
    }
  }

  const getProviderDisplayName = (provider) => {
    switch (provider) {
      case 'groq': return 'GROQ'
      case 'ollama': return 'Ollama'
      case 'bedrock': return 'AWS Bedrock'
      default: return provider
    }
  }

  const isChanged = selectedProvider !== currentProvider || selectedModel !== currentModel

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">
          <span className="logo-icon">⚡</span>
          <span className="logo-text">LangGraph Router</span>
        </div>

        {/* Provider Selector */}
        <div className="provider-section">
          <div className="provider-header">
            <h3>LLM Provider</h3>
            <div className="provider-header-actions">
              <button
                className="settings-btn"
                onClick={openSettings}
                title="API Key Settings"
              >
                ⚙️
              </button>
              <div className={`status-dot ${currentProvider ? 'connected' : 'disconnected'}`} title={currentProvider ? 'Connected' : 'Not connected'} />
            </div>
          </div>

          {/* Current active badge */}
          {currentProvider && (
            <div className="active-provider-badge">
              <span className="badge-icon">{getProviderIcon(currentProvider)}</span>
              <div className="badge-info">
                <span className="badge-provider">{getProviderDisplayName(currentProvider)}</span>
                <span className="badge-model" title={currentModel}>{currentModel}</span>
              </div>
            </div>
          )}

          <div className="provider-controls">
            <label className="control-label">Provider</label>
            <select
              id="provider-select"
              className="provider-select"
              value={selectedProvider}
              onChange={handleProviderChange}
              disabled={isSwitching}
            >
              <option value="" disabled>Select provider...</option>
              {providers.length > 0
                ? providers.map(p => (
                  <option key={p.id} value={p.id} disabled={!p.available}>
                    {getProviderIcon(p.id)} {p.name} {!p.available ? '(unavailable)' : ''}
                  </option>
                ))
                : <>
                  <option value="groq">⚡ GROQ</option>
                  <option value="ollama">🦙 Ollama</option>
                  <option value="bedrock">☁️ AWS Bedrock</option>
                </>
              }
            </select>

            <label className="control-label">Model</label>
            <select
              id="model-select"
              className="model-select"
              value={selectedModel}
              onChange={handleModelChange}
              disabled={isSwitching || isLoadingModels || availableModels.length === 0}
            >
              {isLoadingModels ? (
                <option value="">Loading models...</option>
              ) : providerError ? (
                <option value="">Error loading models</option>
              ) : availableModels.length === 0 ? (
                <option value="">Select provider first</option>
              ) : (
                availableModels.map(m => (
                  <option key={m.id} value={m.id} title={m.description || ''}>
                    {m.name}
                  </option>
                ))
              )}
            </select>

            {/* Model description */}
            {selectedModel && availableModels.length > 0 && (
              <div className="model-description">
                {availableModels.find(m => m.id === selectedModel)?.description || ''}
              </div>
            )}

            {/* Error message */}
            {providerError && (
              <div className="provider-error">
                <span className="error-icon">⚠️</span>
                <span>{providerError}</span>
              </div>
            )}

            <button
              id="switch-provider-btn"
              className={`switch-btn ${isSwitching ? 'switching' : ''} ${isChanged ? 'has-changes' : ''}`}
              onClick={handleSwitchProvider}
              disabled={isSwitching || !selectedModel || !isChanged}
            >
              {isSwitching ? (
                <>
                  <span className="spinner"></span>
                  Validating...
                </>
              ) : isChanged ? (
                'Apply Changes'
              ) : (
                'Active'
              )}
            </button>
          </div>
        </div>

        <div className="sidebar-divider" />

        <nav className="nav-info">
          <div className="info-card">
            <h3>Query Types</h3>
            <div className="info-item">
              <span className="icon">📚</span>
              <div>
                <strong>RAG</strong>
                <p>Document & knowledge queries</p>
              </div>
            </div>
            <div className="info-item">
              <span className="icon">🗃️</span>
              <div>
                <strong>SQL</strong>
                <p>Database & data queries</p>
              </div>
            </div>
            <div className="info-item">
              <span className="icon">🔀</span>
              <div>
                <strong>Hybrid</strong>
                <p>Combined analysis</p>
              </div>
            </div>
          </div>
        </nav>
        <div className="sidebar-footer">
          <p>Powered by LangGraph</p>
        </div>
      </aside>

      <main className="main">
        <header className="header">
          <div className="header-content">
            <div>
              <h1>AI Query Assistant</h1>
              <p>Ask anything about your documents or data</p>
            </div>
            {messages.length > 0 && (
              <button
                className="new-session-btn"
                onClick={handleClearSession}
                title="Clear conversation and start a new session"
                disabled={isLoading}
              >
                + New Session
              </button>
            )}
          </div>
        </header>

        <div className="messages-container">
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-icon">🤖</div>
              <h2>Welcome!</h2>
              <p>I can help you query documents, analyze data, or combine both.</p>
              <div className="example-queries">
                <button onClick={() => setQuery('How many customers do we have?')}>
                  How many customers do we have?
                </button>
                <button onClick={() => setQuery('What is LangGraph?')}>
                  What is LangGraph?
                </button>
                <button onClick={() => setQuery('Compare our sales with industry benchmarks')}>
                  Compare sales with benchmarks
                </button>
              </div>
            </div>
          ) : (
            <div className="messages">
              {messages.map((msg, idx) => (
                <div key={idx} className={`message ${msg.type}`}>
                  {msg.type === 'user' ? (
                    <div className="message-bubble user-bubble">
                      <span className="avatar">👤</span>
                      <div className="content">{msg.content}</div>
                    </div>
                  ) : msg.type === 'cancelled' ? (
                    <div className="message-bubble cancelled-bubble">
                      <span className="avatar">🚫</span>
                      <div className="content">{msg.content}</div>
                    </div>
                  ) : msg.type === 'error' ? (
                    <div className="message-bubble error-bubble">
                      <span className="avatar">⚠️</span>
                      <div className="content">{msg.content}</div>
                    </div>
                  ) : (
                    <div className="message-bubble assistant-bubble">
                      <span className="avatar">🤖</span>
                      <div className="content">
                        <div className="route-badge">
                          {getRouteIcon(msg.route)} {getRouteName(msg.route)}
                        </div>
                        <div className="answer">{msg.content}</div>
                        {msg.sql_query && (
                          <div className="sql-section">
                            <div className="sql-label">SQL Query:</div>
                            <code className="sql-code">{msg.sql_query}</code>
                          </div>
                        )}
                        {msg.model_used && (
                          <div className="model-used">
                            <span className="model-used-label">Model:</span>
                            <span className="model-used-tag">{msg.model_used}</span>
                          </div>
                        )}
                        {msg.sources && msg.sources.length > 0 && (
                          <div className="sources">
                            <span className="sources-label">Sources:</span>
                            {msg.sources.map((src, i) => (
                              <span key={i} className="source-tag">{src}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {isLoading && (
                <div className="message assistant">
                  <div className="message-bubble assistant-bubble">
                    <span className="avatar">🤖</span>
                    <div className="content">
                      <div className="typing-indicator">
                        <span></span><span></span><span></span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <form className="input-form" onSubmit={handleSubmit}>
          <div className="input-container">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask a question..."
              disabled={isLoading}
            />
            {isLoading ? (
              <button
                type="button"
                className="cancel-btn"
                onClick={handleCancel}
                title="Stop generating"
              >
                ■
              </button>
            ) : (
              <button type="submit" disabled={!query.trim()}>
                →
              </button>
            )}
          </div>
        </form>
      </main>

      {/* Settings Modal */}
      {showSettings && (
        <div className="modal-overlay" onClick={closeSettings}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>⚙️ API Key Settings</h2>
              <button className="modal-close" onClick={closeSettings}>×</button>
            </div>
            <div className="modal-body">
              <p className="modal-description">
                Configure API keys and tokens for each provider. Values are loaded from your <code>.env</code> file by default.
                Override them here at runtime — changes take effect immediately.
              </p>

              {providerKeys.map((keyInfo) => (
                <div key={keyInfo.provider} className="key-card">
                  <div className="key-card-header">
                    <span className="key-provider-icon">{getProviderIcon(keyInfo.provider)}</span>
                    <div className="key-provider-info">
                      <span className="key-provider-name">{keyInfo.provider_name}</span>
                      <span className="key-label">{keyInfo.key_label}</span>
                    </div>
                    <span className={`key-status ${keyInfo.is_set ? 'set' : 'unset'}`}>
                      {keyInfo.is_set ? '✓ Set' : '✗ Not set'}
                    </span>
                  </div>

                  <div className="key-current">
                    <span className="key-hint">{keyInfo.key_hint}</span>
                    <span className="key-masked">{keyInfo.masked_value || '(empty)'}</span>
                  </div>

                  <div className="key-input-row">
                    <div className="key-input-wrapper">
                      <input
                        type={keyVisibility[keyInfo.provider] ? 'text' : 'password'}
                        className="key-input"
                        value={keyInputs[keyInfo.provider] || ''}
                        onChange={(e) => handleKeyInputChange(keyInfo.provider, e.target.value)}
                        placeholder={`Enter new ${keyInfo.key_label.toLowerCase()}...`}
                      />
                      <button
                        className="key-toggle-visibility"
                        type="button"
                        onClick={() => toggleKeyVisibility(keyInfo.provider)}
                        title={keyVisibility[keyInfo.provider] ? 'Hide' : 'Show'}
                      >
                        {keyVisibility[keyInfo.provider] ? '🙈' : '👁️'}
                      </button>
                    </div>
                    <button
                      className="key-save-btn"
                      onClick={() => handleSaveKey(keyInfo.provider)}
                      disabled={savingKey === keyInfo.provider || !keyInputs[keyInfo.provider]?.trim()}
                    >
                      {savingKey === keyInfo.provider ? (
                        <span className="spinner small"></span>
                      ) : (
                        'Save'
                      )}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Toast notification */}
      {toast && (
        <div className={`toast toast-${toast.type}`} onClick={() => setToast(null)}>
          <span className="toast-icon">
            {toast.type === 'success' ? '✅' : toast.type === 'info' ? 'ℹ️' : '❌'}
          </span>
          <span className="toast-message">{toast.message}</span>
          <button className="toast-close" onClick={() => setToast(null)}>×</button>
        </div>
      )}
    </div>
  )
}

export default App
