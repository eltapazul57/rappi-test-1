import Chat from './components/Chat'
import Insights from './components/Insights'
import { useState } from 'react'

export default function App() {
  const [tab, setTab] = useState('chat')
  return (
    <div>
      <nav>
        <button onClick={() => setTab('chat')}>Chat</button>
        <button onClick={() => setTab('insights')}>Insights</button>
      </nav>
      {tab === 'chat' ? <Chat /> : <Insights />}
    </div>
  )
}
