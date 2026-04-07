import { useState } from 'react'
import Chat from './components/Chat'
import Insights from './components/Insights'
import './App.css'

export default function App() {
  const [tab, setTab] = useState('chat')
  return (
    <div className="app">
      <header className="app-header">
        <span className="app-title">Rappi Analytics</span>
        <nav className="app-nav">
          <button
            className={`nav-btn${tab === 'chat' ? ' active' : ''}`}
            onClick={() => setTab('chat')}
          >
            Chat
          </button>
          <button
            className={`nav-btn${tab === 'insights' ? ' active' : ''}`}
            onClick={() => setTab('insights')}
          >
            Insights
          </button>
        </nav>
      </header>
      <main className="app-main">
        {tab === 'chat' ? <Chat /> : <Insights />}
      </main>
    </div>
  )
}
