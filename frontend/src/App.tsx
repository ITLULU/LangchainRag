import { Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './components/MainLayout'
import LoginPage from './pages/Login'
import DashboardPage from './pages/Dashboard'
import KBListPage from './pages/KnowledgeBase/KBList'
import DocumentListPage from './pages/Documents/DocumentList'
import QAChatPage from './pages/QAChat/QAChat'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<MainLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="knowledge" element={<KBListPage />} />
        <Route path="documents" element={<DocumentListPage />} />
        <Route path="chat" element={<QAChatPage />} />
      </Route>
    </Routes>
  )
}

export default App