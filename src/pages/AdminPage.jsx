import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-toastify'
import { adminService } from '../services/adminService'
import { authService } from '../services/authService'
import { syllabusService } from '../services/syllabusService'
import { Card, CardBody, Progress, Checkbox, Spinner, Pagination } from '@heroui/react'
import { motion, AnimatePresence } from 'framer-motion'
import Sidebar from '../components/Sidebar'

// Supported file types configuration
const SUPPORTED_EXTENSIONS = ['.pdf', '.md', '.ipynb']
const ACCEPT_STRING = SUPPORTED_EXTENSIONS.join(',')

// File type icons and colors
const FILE_TYPE_CONFIG = {
  '.pdf': { color: 'bg-red-100 text-red-600', label: 'PDF' },
  '.md': { color: 'bg-blue-100 text-blue-600', label: 'MD' },
  '.ipynb': { color: 'bg-orange-100 text-orange-600', label: 'IPYNB' },
}

const getFileExtension = (filename) => {
  if (!filename) return '.pdf'
  const ext = '.' + filename.toLowerCase().split('.').pop()
  return SUPPORTED_EXTENSIONS.includes(ext) ? ext : '.pdf'
}

const getFileTypeConfig = (filename) => {
  const ext = getFileExtension(filename)
  return FILE_TYPE_CONFIG[ext] || FILE_TYPE_CONFIG['.pdf']
}

function AdminPage() {
  const navigate = useNavigate()
  const [documents, setDocuments] = useState([])
  const [dragActive, setDragActive] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState('all')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalDocs, setTotalDocs] = useState(0)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [activeMenu, setActiveMenu] = useState('documents')
  const [user, setUser] = useState(null)
  
  // Syllabus upload state
  const [syllabusUploading, setSyllabusUploading] = useState(false)

  // Modal states
  const [viewModalOpen, setViewModalOpen] = useState(false)
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [selectedDoc, setSelectedDoc] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [clickPosition, setClickPosition] = useState({ x: 0, y: 0 })

  useEffect(() => {
    loadUser()
  }, [])

  useEffect(() => {
    fetchDocuments()
  }, [page, statusFilter])

  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(() => fetchDocuments(true), 5000)
    return () => clearInterval(interval)
  }, [autoRefresh, page, statusFilter])

  const loadUser = async () => {
    const currentUser = await authService.getCurrentUser()
    setUser(currentUser)
  }

  const PAGE_SIZE = 5

  const fetchDocuments = async (silent = false) => {
    try {
      if (!silent) setLoading(true)
      setError(null)
      const data = await adminService.listDocuments({
        page,
        pageSize: PAGE_SIZE,
        status: statusFilter === 'all' ? null : statusFilter,
      })
      setDocuments(data.items)
      setTotalPages(Math.ceil(data.total / PAGE_SIZE))
      setTotalDocs(data.total)
    } catch (err) {
      if (!silent) setError(err.message)
    } finally {
      if (!silent) setLoading(false)
    }
  }

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true)
    else if (e.type === 'dragleave') setDragActive(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    handleFiles(Array.from(e.dataTransfer.files))
  }

  const handleFileInput = (e) => {
    handleFiles(Array.from(e.target.files))
    e.target.value = ''
  }

  const handleFiles = async (files) => {
    const validFiles = files.filter((f) => {
      const ext = '.' + f.name.toLowerCase().split('.').pop()
      return SUPPORTED_EXTENSIONS.includes(ext)
    })
    
    if (validFiles.length === 0) {
      return alert(`Please select valid files: ${SUPPORTED_EXTENSIONS.join(', ')}`)
    }

    setUploading(true)
    setUploadProgress(
      validFiles.map((f) => ({ 
        filename: f.name, 
        size: f.size, 
        status: 'uploading', 
        progress: 0,
        fileType: getFileExtension(f.name)
      }))
    )

    for (let i = 0; i < validFiles.length; i++) {
      try {
        setUploadProgress((prev) =>
          prev.map((p, idx) => (idx === i ? { ...p, progress: 65 } : p))
        )
        await adminService.uploadDocument(validFiles[i])
        setUploadProgress((prev) =>
          prev.map((p, idx) => (idx === i ? { ...p, status: 'success', progress: 100 } : p))
        )
      } catch (err) {
        setUploadProgress((prev) =>
          prev.map((p, idx) => (idx === i ? { ...p, status: 'error', error: err.message } : p))
        )
      }
    }
    setUploading(false)
    setTimeout(() => fetchDocuments(), 2000)
  }

  const removeUploadItem = (idx) => setUploadProgress((prev) => prev.filter((_, i) => i !== idx))

  // Syllabus upload handler
  const handleSyllabusUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    const ext = '.' + file.name.toLowerCase().split('.').pop()
    if (ext !== '.md' && ext !== '.markdown') {
      toast.error('Please select a Markdown file (.md)', { icon: '📄' })
      return
    }
    
    setSyllabusUploading(true)
    const toastId = toast.loading(`Processing ${file.name}...`)
    
    try {
      const result = await syllabusService.uploadSyllabus(file)
      toast.update(toastId, {
        render: (
          <div>
            <p className="font-semibold">{result.subject_code} - {result.course_name}</p>
            <p className="text-sm text-gray-600">
              {result.sessions_count} sessions • {result.assessments_count} assessments
            </p>
          </div>
        ),
        type: 'success',
        isLoading: false,
        autoClose: 5000,
        icon: '📚'
      })
      setTimeout(() => fetchDocuments(), 2000)
    } catch (err) {
      toast.update(toastId, {
        render: err.message || 'Failed to upload syllabus',
        type: 'error',
        isLoading: false,
        autoClose: 5000,
        icon: '❌'
      })
    } finally {
      setSyllabusUploading(false)
      e.target.value = ''
    }
  }

  // View document details
  const handleViewDocument = (doc, e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    setClickPosition({ 
      x: rect.left + rect.width / 2, 
      y: rect.top + rect.height / 2 
    })
    setSelectedDoc(doc)
    setViewModalOpen(true)
  }

  // Delete document
  const handleDeleteClick = (doc, e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    setClickPosition({ 
      x: rect.left + rect.width / 2, 
      y: rect.top + rect.height / 2 
    })
    setSelectedDoc(doc)
    setDeleteModalOpen(true)
  }

  const confirmDelete = async () => {
    if (!selectedDoc) return
    setActionLoading(true)
    try {
      await adminService.deleteDocument(selectedDoc.doc_id)
      toast.success(`Document "${selectedDoc.filename}" deleted successfully`)
      setDeleteModalOpen(false)
      setSelectedDoc(null)
      fetchDocuments()
    } catch (err) {
      toast.error(err.message || 'Failed to delete document')
    } finally {
      setActionLoading(false)
    }
  }

  // Reprocess failed document
  const handleReprocess = async (doc) => {
    const toastId = toast.loading(`Reprocessing ${doc.filename}...`)
    try {
      await adminService.reprocessDocument(doc.doc_id)
      toast.update(toastId, {
        render: `Document "${doc.filename}" queued for reprocessing`,
        type: 'success',
        isLoading: false,
        autoClose: 3000
      })
      fetchDocuments()
    } catch (err) {
      toast.update(toastId, {
        render: err.message || 'Failed to reprocess document',
        type: 'error',
        isLoading: false,
        autoClose: 5000
      })
    }
  }

  // Download document
  const handleDownload = async (doc) => {
    try {
      const result = await adminService.downloadDocument(doc.doc_id)
      window.open(result.download_url, '_blank')
    } catch (err) {
      toast.error(err.message || 'Failed to download document')
    }
  }

  const formatFileSize = (bytes) => {
    if (!bytes) return '0 B'
    const k = 1024, sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
  }

  const getStatusBadge = (status) => {
    const config = {
      UPLOADED: { text: 'text-gray-600', dot: 'bg-gray-400' },
      IDP_RUNNING: { text: 'text-orange-600', dot: 'bg-orange-500' },
      EMBEDDING_DONE: { text: 'text-emerald-600', dot: 'bg-emerald-500' },
      FAILED: { text: 'text-red-600', dot: 'bg-red-500' },
    }[status] || { text: 'text-gray-600', dot: 'bg-gray-400' }

    return (
      <span className={`inline-flex items-center gap-2 text-sm font-medium ${config.text}`}>
        <span className={`w-2 h-2 rounded-full ${config.dot}`}></span>
        {status}
      </span>
    )
  }

  return (
    <div className="flex min-h-screen bg-slate-100">
      <Sidebar activeMenu={activeMenu} setActiveMenu={setActiveMenu} user={user} />

      <div className="flex-1 p-8">
        <h1 className="text-2xl font-bold text-gray-800 mb-8">Document Management</h1>

        {/* Upload Section */}
        <Card className="mb-8">
          <CardBody className="p-6">
            <h2 className="text-lg font-semibold mb-4">Upload New Documents</h2>
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-xl p-8 text-center transition-all ${
                dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="w-12 h-12 mx-auto mb-4 bg-green-100 rounded-full flex items-center justify-center">
                <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <p className="text-gray-800 font-medium mb-1">Drag & drop files here</p>
              <p className="text-sm text-gray-500 mb-6">
                Supports: PDF, Markdown (.md), Jupyter Notebooks (.ipynb). Max: 50MB per file.
              </p>
              
              {/* Two Upload Buttons */}
              <div className="flex items-center justify-center gap-3">
                <label className="cursor-pointer">
                  <span className={`inline-flex items-center gap-2 px-5 py-2.5 bg-blue-500 hover:bg-blue-600 text-white font-medium rounded-lg transition-colors ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Documents
                  </span>
                  <input type="file" className="hidden" accept={ACCEPT_STRING} multiple disabled={uploading} onChange={handleFileInput} />
                </label>
                
                <span className="text-gray-400">or</span>
                
                <label className="cursor-pointer">
                  <span className={`inline-flex items-center gap-2 px-5 py-2.5 bg-purple-500 hover:bg-purple-600 text-white font-medium rounded-lg transition-colors ${syllabusUploading ? 'opacity-50 cursor-not-allowed' : ''}`}>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                    </svg>
                    Syllabus
                  </span>
                  <input type="file" className="hidden" accept=".md,.markdown" disabled={syllabusUploading} onChange={handleSyllabusUpload} />
                </label>
              </div>
              
              <p className="text-xs text-gray-400 mt-3">
                <span className="text-blue-500">Documents</span>: General files • <span className="text-purple-500">Syllabus</span>: FPT course syllabus (.md)
              </p>
            </div>
            
            {/* Syllabus uploading indicator */}
            {syllabusUploading && (
              <div className="mt-4 p-4 bg-purple-50 rounded-lg flex items-center gap-3">
                <Spinner size="sm" color="secondary" />
                <span className="text-purple-600 font-medium">Processing syllabus...</span>
              </div>
            )}

            <AnimatePresence>
              {uploadProgress.length > 0 && (
                <div className="mt-4 space-y-3">
                  {uploadProgress.map((item, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, x: 100 }}
                      className={`flex items-center gap-4 p-4 rounded-lg ${
                        item.status === 'success' ? 'bg-green-50' : item.status === 'error' ? 'bg-red-50' : 'bg-gray-50'
                      }`}
                    >
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${getFileTypeConfig(item.filename).color}`}>
                        <span className="text-xs font-bold">{getFileTypeConfig(item.filename).label}</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-800 truncate">{item.filename}</p>
                        {item.status === 'uploading' && <p className="text-xs text-gray-500">{formatFileSize((item.size * item.progress) / 100)} of {formatFileSize(item.size)}</p>}
                        {item.status === 'success' && <p className="text-xs text-green-600">Upload Complete</p>}
                        {item.status === 'error' && <p className="text-xs text-red-600">Upload Failed</p>}
                      </div>
                      {item.status === 'uploading' && (
                        <div className="flex items-center gap-3 w-48">
                          <Progress value={item.progress} color="primary" size="sm" className="flex-1" />
                          <span className="text-sm text-gray-600 w-10">{item.progress}%</span>
                        </div>
                      )}
                      {item.status === 'success' && (
                        <div className="w-6 h-6 bg-green-500 rounded-full flex items-center justify-center">
                          <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        </div>
                      )}
                      {item.status === 'error' && (
                        <div className="w-6 h-6 bg-red-500 rounded-full flex items-center justify-center">
                          <span className="text-white text-xs font-bold">!</span>
                        </div>
                      )}
                      {(item.status === 'success' || item.status === 'error') && (
                        <button onClick={() => removeUploadItem(idx)} className="text-gray-400 hover:text-gray-600">
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      )}
                    </motion.div>
                  ))}
                </div>
              )}
            </AnimatePresence>
          </CardBody>
        </Card>

        {/* Documents Table */}
        <Card>
          <CardBody className="p-0">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <div className="flex items-center gap-4">
                <h2 className="text-lg font-semibold text-gray-800">All Documents</h2>
                <button
                  onClick={() => navigate('/admin/processing-history')}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Processing History
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-500">Status:</span>
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="all">All</option>
                    <option value="UPLOADED">Uploaded</option>
                    <option value="IDP_RUNNING">Processing</option>
                    <option value="EMBEDDING_DONE">Done</option>
                    <option value="FAILED">Failed</option>
                  </select>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox isSelected={autoRefresh} onValueChange={setAutoRefresh} size="sm" />
                  <span className="text-sm text-gray-500">Auto-refresh (5s)</span>
                </div>
                <button
                  onClick={() => fetchDocuments()}
                  disabled={loading}
                  className="p-2 text-blue-500 hover:bg-blue-50 rounded-lg transition-colors disabled:opacity-50"
                  title="Refresh"
                >
                  {loading ? <Spinner size="sm" /> : (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {loading && documents.length === 0 ? (
              <div className="flex items-center justify-center py-16">
                <Spinner size="lg" />
              </div>
            ) : error ? (
              <div className="p-8 text-center">
                <p className="text-red-600 mb-2">⚠️ {error}</p>
                <button onClick={() => fetchDocuments()} className="text-sm text-blue-500 hover:underline">
                  Try again
                </button>
              </div>
            ) : documents.length === 0 ? (
              <div className="py-16 text-center">
                <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="text-gray-500">No documents found</p>
                <p className="text-sm text-gray-400 mt-1">Upload PDF, Markdown, or Jupyter files to get started</p>
              </div>
            ) : (
              <>
                {/* Table */}
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Filename</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Doc ID</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Status</th>
                        <th className="px-6 py-3 text-center text-xs font-medium text-gray-400 uppercase tracking-wider">Page Count</th>
                        <th className="px-6 py-3 text-center text-xs font-medium text-gray-400 uppercase tracking-wider">Chunk Count</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Upload Time</th>
                        <th className="px-6 py-3 text-center text-xs font-medium text-gray-400 uppercase tracking-wider">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {documents.map((doc, idx) => (
                        <motion.tr
                          key={doc.doc_id}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: idx * 0.05 }}
                          className="hover:bg-gray-50/50 transition-colors"
                        >
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-2">
                              <span className={`px-1.5 py-0.5 text-xs font-medium rounded ${getFileTypeConfig(doc.filename).color}`}>
                                {getFileTypeConfig(doc.filename).label}
                              </span>
                              <p className="text-sm font-medium text-gray-800 truncate max-w-xs" title={doc.filename}>
                                {doc.filename}
                              </p>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <span className="text-sm text-gray-500 font-mono">doc_{doc.doc_id.slice(0, 7)}</span>
                          </td>
                          <td className="px-6 py-4">{getStatusBadge(doc.status)}</td>
                          <td className="px-6 py-4 text-center text-sm text-gray-600">{doc.page_count || 0}</td>
                          <td className="px-6 py-4 text-center text-sm text-gray-600">{doc.chunk_count || 0}</td>
                          <td className="px-6 py-4 text-sm text-gray-500">
                            {new Date(doc.uploaded_at).toLocaleString('en-US', {
                              month: '2-digit', day: '2-digit', year: 'numeric',
                              hour: '2-digit', minute: '2-digit', hour12: true,
                            })}
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center justify-center gap-1">
                              {/* View */}
                              <button 
                                onClick={(e) => handleViewDocument(doc, e)}
                                className="p-2 text-gray-400 hover:text-blue-600 transition-colors" 
                                title="View Details"
                              >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                </svg>
                              </button>
                              {/* Download */}
                              <button 
                                onClick={() => handleDownload(doc)}
                                className="p-2 text-gray-400 hover:text-green-600 transition-colors" 
                                title="Download"
                              >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                </svg>
                              </button>
                              {/* Reprocess (only for FAILED) */}
                              {doc.status === 'FAILED' && (
                                <button 
                                  onClick={() => handleReprocess(doc)}
                                  className="p-2 text-gray-400 hover:text-orange-600 transition-colors" 
                                  title="Reprocess"
                                >
                                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                  </svg>
                                </button>
                              )}
                              {/* Delete */}
                              <button 
                                onClick={(e) => handleDeleteClick(doc, e)}
                                className="p-2 text-gray-400 hover:text-red-500 transition-colors" 
                                title="Delete"
                              >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                              </button>
                            </div>
                          </td>
                        </motion.tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100">
                  <p className="text-sm text-gray-500">
                    Showing <span className="font-medium text-emerald-600">{(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, totalDocs)}</span> of <span className="font-medium text-emerald-600">{totalDocs}</span>
                  </p>
                  <div className="flex items-center gap-4">
                    {totalPages > 1 && (
                      <Pagination total={totalPages} page={page} onChange={setPage} showControls size="sm" color="primary" />
                    )}
                  </div>
                </div>
              </>
            )}
          </CardBody>
        </Card>
      </div>

      {/* View Document Modal */}
      <AnimatePresence>
        {viewModalOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 bg-black/50 z-50"
              onClick={() => setViewModalOpen(false)}
            />
            <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
              <motion.div
                initial={{ 
                  opacity: 0, 
                  scale: 0.3,
                  x: clickPosition.x - window.innerWidth / 2,
                  y: clickPosition.y - window.innerHeight / 2
                }}
                animate={{ 
                  opacity: 1, 
                  scale: 1,
                  x: 0,
                  y: 0
                }}
                exit={{ 
                  opacity: 0, 
                  scale: 0.3,
                  x: clickPosition.x - window.innerWidth / 2,
                  y: clickPosition.y - window.innerHeight / 2
                }}
                transition={{ type: "spring", damping: 25, stiffness: 300 }}
                className="w-full max-w-2xl mx-4 pointer-events-auto"
              >
                <div className="bg-white rounded-xl shadow-2xl border border-gray-200 overflow-hidden">
                  <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
                    <div>
                      <h3 className="text-lg font-semibold text-gray-800">Document Details</h3>
                      {selectedDoc && (
                        <p className="text-sm text-gray-500 mt-0.5">{selectedDoc.filename}</p>
                      )}
                    </div>
                    <button 
                      onClick={() => setViewModalOpen(false)}
                      className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                    >
                      <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                  
                  {selectedDoc && (
                    <div className="p-6">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="p-4 bg-gray-50 rounded-lg border border-gray-100">
                          <p className="text-xs text-gray-500 mb-1">Document ID</p>
                          <p className="font-mono text-sm break-all">{selectedDoc.doc_id}</p>
                        </div>
                        <div className="p-4 bg-gray-50 rounded-lg border border-gray-100">
                          <p className="text-xs text-gray-500 mb-1">File Type</p>
                          <span className={`px-2 py-1 text-xs font-medium rounded ${getFileTypeConfig(selectedDoc.filename).color}`}>
                            {getFileTypeConfig(selectedDoc.filename).label}
                          </span>
                        </div>
                        <div className="p-4 bg-gray-50 rounded-lg border border-gray-100">
                          <p className="text-xs text-gray-500 mb-1">Status</p>
                          {getStatusBadge(selectedDoc.status)}
                        </div>
                        <div className="p-4 bg-gray-50 rounded-lg border border-gray-100">
                          <p className="text-xs text-gray-500 mb-1">Uploaded By</p>
                          <p className="text-sm">{selectedDoc.uploaded_by}</p>
                        </div>
                        <div className="p-4 bg-gray-50 rounded-lg border border-gray-100">
                          <p className="text-xs text-gray-500 mb-1">Page Count</p>
                          <p className="text-sm font-medium">{selectedDoc.page_count || 0}</p>
                        </div>
                        <div className="p-4 bg-gray-50 rounded-lg border border-gray-100">
                          <p className="text-xs text-gray-500 mb-1">Chunk Count</p>
                          <p className="text-sm font-medium">{selectedDoc.chunk_count || 0}</p>
                        </div>
                        <div className="p-4 bg-gray-50 rounded-lg border border-gray-100 col-span-2">
                          <p className="text-xs text-gray-500 mb-1">Upload Time</p>
                          <p className="text-sm">{new Date(selectedDoc.uploaded_at).toLocaleString()}</p>
                        </div>
                        {selectedDoc.error_message && (
                          <div className="p-4 bg-red-50 rounded-lg border border-red-100 col-span-2">
                            <p className="text-xs text-red-500 mb-1">Error Message</p>
                            <p className="text-sm text-red-700">{selectedDoc.error_message}</p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  
                  <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50">
                    <button
                      onClick={() => setViewModalOpen(false)}
                      className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-200 rounded-lg transition-colors"
                    >
                      Close
                    </button>
                    {selectedDoc && (
                      <button
                        onClick={() => handleDownload(selectedDoc)}
                        className="px-4 py-2 text-sm font-medium text-white bg-blue-500 hover:bg-blue-600 rounded-lg transition-colors"
                      >
                        Download
                      </button>
                    )}
                  </div>
                </div>
              </motion.div>
            </div>
          </>
        )}
      </AnimatePresence>

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {deleteModalOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 bg-black/50 z-50"
              onClick={() => !actionLoading && setDeleteModalOpen(false)}
            />
            <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
              <motion.div
                initial={{ 
                  opacity: 0, 
                  scale: 0.3,
                  x: clickPosition.x - window.innerWidth / 2,
                  y: clickPosition.y - window.innerHeight / 2
                }}
                animate={{ 
                  opacity: 1, 
                  scale: 1,
                  x: 0,
                  y: 0
                }}
                exit={{ 
                  opacity: 0, 
                  scale: 0.3,
                  x: clickPosition.x - window.innerWidth / 2,
                  y: clickPosition.y - window.innerHeight / 2
                }}
                transition={{ type: "spring", damping: 25, stiffness: 300 }}
                className="w-full max-w-md mx-4 pointer-events-auto"
              >
                <div className="bg-white rounded-xl shadow-2xl border border-gray-200 overflow-hidden">
                  <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
                    <h3 className="text-lg font-semibold text-red-600">Delete Document</h3>
                    <button 
                      onClick={() => !actionLoading && setDeleteModalOpen(false)}
                      className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                      disabled={actionLoading}
                    >
                      <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                  
                  {selectedDoc && (
                    <div className="p-6">
                      <p className="text-gray-600 mb-4">
                        Are you sure you want to delete this document? This action cannot be undone.
                      </p>
                      <div className="p-4 bg-gray-50 rounded-lg border border-gray-100">
                        <p className="text-sm font-medium text-gray-800">{selectedDoc.filename}</p>
                        <p className="text-xs text-gray-500 mt-1 font-mono">ID: {selectedDoc.doc_id}</p>
                      </div>
                      <p className="text-xs text-gray-500 mt-4">
                        This will delete the document from S3, DynamoDB, and remove all embeddings from Qdrant.
                      </p>
                    </div>
                  )}
                  
                  <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50">
                    <button
                      onClick={() => setDeleteModalOpen(false)}
                      disabled={actionLoading}
                      className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-200 rounded-lg transition-colors disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={confirmDelete}
                      disabled={actionLoading}
                      className="px-4 py-2 text-sm font-medium text-white bg-red-500 hover:bg-red-600 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
                    >
                      {actionLoading && (
                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                      )}
                      Delete
                    </button>
                  </div>
                </div>
              </motion.div>
            </div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

export default AdminPage
