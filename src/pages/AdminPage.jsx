import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminService } from '../services/adminService'
import { authService } from '../services/authService'
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
    // Filter for supported file types
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

  const formatFileSize = (bytes) => {
    if (!bytes) return '0 B'
    const k = 1024,
      sizes = ['B', 'KB', 'MB', 'GB']
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
              <p className="text-sm text-gray-500 mb-4">
                Supports: PDF, Markdown (.md), Jupyter Notebooks (.ipynb). Max: 50MB per file.
              </p>
              <label className="inline-block cursor-pointer">
                <span className="px-6 py-2.5 bg-blue-500 hover:bg-blue-600 text-white font-medium rounded-lg transition-colors">
                  Browse Files
                </span>
                <input type="file" className="hidden" accept={ACCEPT_STRING} multiple disabled={uploading} onChange={handleFileInput} />
              </label>
            </div>

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

        {/* Documents Table - Redesigned */}
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
                              month: '2-digit',
                              day: '2-digit',
                              year: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                              hour12: true,
                            })}
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center justify-center gap-1">
                              <button className="p-2 text-gray-400 hover:text-blue-600 transition-colors" title="View">
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                </svg>
                              </button>
                              <button className="p-2 text-gray-400 hover:text-red-500 transition-colors" title="Delete">
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
    </div>
  )
}

export default AdminPage
