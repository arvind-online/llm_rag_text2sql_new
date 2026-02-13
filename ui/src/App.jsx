import { useState, useRef, useEffect } from 'react'
import './App.css'

function App() {
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim() || isLoading) return

    const userMessage = { type: 'user', content: query }
    setMessages(prev => [...prev, userMessage])
    setQuery('')
    setIsLoading(true)

    try {
      const apiBase = import.meta.env.BASE_URL || '/';
      const response = await fetch(`${apiBase}query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: query }),
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
        }
        setMessages(prev => [...prev, assistantMessage])
      } else {
        setMessages(prev => [...prev, {
          type: 'error',
          content: data.detail || 'Something went wrong'
        }])
      }
    } catch (error) {
      setMessages(prev => [...prev, {
        type: 'error',
        content: 'Failed to connect to the server. Make sure it\'s running on port 8000.'
      }])
    } finally {
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

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">
          <span className="logo-icon">⚡</span>
          <span className="logo-text">LangGraph Router</span>
        </div>
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
          <p>Powered by GROQ • LangGraph</p>
        </div>
      </aside>

      <main className="main">
        <header className="header">
          <h1>AI Query Assistant</h1>
          <p>Ask anything about your documents or data</p>
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
            <button type="submit" disabled={isLoading || !query.trim()}>
              {isLoading ? '...' : '→'}
            </button>
          </div>
        </form>
      </main>
    </div>
  )
}

export default App
