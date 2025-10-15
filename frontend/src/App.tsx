import React, { useState, useEffect } from 'react';
import { Upload, Search, FileText, X, Loader2, AlertCircle, CheckCircle, Sparkles, BookOpen, Database } from 'lucide-react';
import { ApiService, UploadDocumentRequest, QueryRequest } from './services/api';

interface UploadedDocument {
  id: string;
  name: string;
  size: number;
  status: 'uploading' | 'ready' | 'error';
  serverId?: string;
  chunks?: number;
  error?: string;
}

function App() {
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    const checkBackendHealth = async () => {
      try {
        await ApiService.healthCheck();
        setIsBackendHealthy(true);
      } catch (error) {
        console.error('Backend health check failed:', error);
        setIsBackendHealthy(false);
      }
    };

    checkBackendHealth();
  }, []);

  const fileToBase64 = (file: File): Promise<string> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result as string;
        const base64 = result.includes(',') ? result.split(',')[1] : result;
        resolve(base64);
      };
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const newDocs: UploadedDocument[] = Array.from(files).map((file) => ({
      id: Math.random().toString(36).substr(2, 9),
      name: file.name,
      size: file.size,
      status: 'uploading',
    }));

    // Add to UI immediately
    setDocuments((prev) => [...prev, ...newDocs]);
    setUploading(true);

    // Upload files in parallel for better performance
    const uploadPromises = Array.from(files).map(async (file, index) => {
      const localId = newDocs[index].id;
      
      try {
        console.log(`Starting upload for file ${index + 1}/${files.length}: ${file.name}`);
        const file_b64 = await fileToBase64(file);
        const payload: UploadDocumentRequest = {
          filename: file.name,
          mime_type: file.type || undefined,
          file_b64,
        };

        const result = await ApiService.uploadDocument(payload);
        console.log(`Upload successful for ${file.name}:`, result);
        
        setDocuments((prev) =>
          prev.map((d) =>
            d.id === localId
              ? { ...d, status: 'ready', serverId: result.document_id, chunks: result.chunks_created }
              : d
          )
        );
      } catch (err: any) {
        console.error(`Upload failed for ${file.name}:`, err);
        const message = err?.message || 'Upload failed';
        setDocuments((prev) => 
          prev.map((d) => 
            d.id === localId ? { ...d, status: 'error', error: message } : d
          )
        );
      }
    });

    // Wait for all uploads to complete
    await Promise.all(uploadPromises);
    setUploading(false);
    
    // Reset input value
    e.currentTarget.value = '';
  };

  const handleTextUpload = async (text: string, filename: string = 'text-input.txt') => {
    const localId = Math.random().toString(36).substr(2, 9);
    
    const newDoc: UploadedDocument = {
      id: localId,
      name: filename,
      size: text.length,
      status: 'uploading',
    };

    setDocuments((prev) => [...prev, newDoc]);
    setUploading(true);

    try {
      const payload: UploadDocumentRequest = {
        filename,
        text,
      };

      const result = await ApiService.uploadDocument(payload);
      
      setDocuments((prev) =>
        prev.map((d) =>
          d.id === localId
            ? { ...d, status: 'ready', serverId: result.document_id, chunks: result.chunks_created }
            : d
        )
      );
    } catch (err: any) {
      const message = err?.message || 'Upload failed';
      setDocuments((prev) => 
        prev.map((d) => 
          d.id === localId ? { ...d, status: 'error', error: message } : d
        )
      );
    }

    setUploading(false);
  };

  const removeDocument = async (id: string) => {
    const doc = documents.find(d => d.id === id);
    if (doc && doc.serverId && doc.status === 'ready') {
      try {
        // Delete from backend
        await ApiService.deleteDocument(doc.serverId);
      } catch (err) {
        console.error('Failed to delete document from backend:', err);
        // Still remove from UI even if backend deletion fails
      }
    }
    // Remove from UI
    setDocuments((docs) => docs.filter((doc) => doc.id !== id));
  };

  const handleSearch = async () => {
    if (!question.trim()) return;

    // Check if there are any ready documents
    const readyDocuments = documents.filter(d => d.status === 'ready');
    if (readyDocuments.length === 0) {
      setAnswer('No documents are currently uploaded. Please upload some documents first before asking questions.');
      return;
    }

    setIsSearching(true);
    setAnswer('');
    setSources([]);
    
    try {
      const queryData: QueryRequest = {
        question: question.trim(),
        max_chunks: 5,
        max_tokens: 500,
      };

      console.log(`Querying with ${readyDocuments.length} documents available:`, readyDocuments.map(d => d.name));
      const result = await ApiService.query(queryData);
      console.log('Query result:', result);
      setAnswer(result.answer);
      setSources(result.sources || []);
    } catch (err: any) {
      console.error('Query error:', err);
      
      // Check if there are any ready documents
      const readyDocuments = documents.filter(d => d.status === 'ready');
      
      if (readyDocuments.length === 0) {
        setAnswer('No documents are currently uploaded. Please upload some documents first before asking questions.');
      } else {
        // Show more specific error message
        const errorMessage = err?.response?.data?.detail || err?.message || 'Unknown error';
        setAnswer(`Error: ${errorMessage}. Please try again or check if your documents were uploaded correctly.`);
      }
    } finally {
      setIsSearching(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'uploading':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      case 'ready':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return null;
    }
  };

  const readyDocCount = documents.filter(d => d.status === 'ready').length;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-md shadow-sm border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center gap-3">
              <div className="bg-gradient-to-br from-blue-600 to-indigo-600 p-2 rounded-xl shadow-lg">
                <BookOpen className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                  Unthinkable KBSE
                </h1>
                <p className="text-sm text-slate-600">Knowledge Base Search Engine</p>
              </div>
            </div>
            
            <div className="flex items-center gap-4">
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-100 rounded-lg text-sm text-slate-600">
                <Database className="w-4 h-4" />
                <span className="font-medium">{readyDocCount}</span>
                <span>documents</span>
              </div>
              
              <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                isBackendHealthy === null 
                  ? 'bg-amber-100 text-amber-800' 
                  : isBackendHealthy 
                    ? 'bg-emerald-100 text-emerald-800' 
                    : 'bg-red-100 text-red-800'
              }`}>
                <div className={`w-2 h-2 rounded-full animate-pulse ${
                  isBackendHealthy === null 
                    ? 'bg-amber-500' 
                    : isBackendHealthy 
                      ? 'bg-emerald-500' 
                      : 'bg-red-500'
                }`}></div>
                <span>
                  {isBackendHealthy === null 
                    ? 'Connecting' 
                    : isBackendHealthy 
                      ? 'Online' 
                      : 'Offline'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid lg:grid-cols-5 gap-6">
          {/* Left Column - Document Upload */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden">
              <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-4">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Upload className="w-5 h-5" />
                  Upload Documents
                </h2>
              </div>
              
              <div className="p-6 space-y-4">
                {/* File Upload */}
                <label className="block">
                  <div className={`border-2 border-dashed rounded-xl p-8 transition-all cursor-pointer ${
                    uploading 
                      ? 'border-blue-300 bg-blue-50' 
                      : 'border-slate-300 bg-slate-50 hover:border-blue-400 hover:bg-blue-50'
                  }`}>
                    <input
                      type="file"
                      multiple
                      accept=".txt,.pdf,.json,application/json"
                      onChange={handleFileUpload}
                      className="hidden"
                      disabled={uploading}
                    />
                    <div className="flex flex-col items-center gap-3 text-center">
                      {uploading ? (
                        <Loader2 className="w-10 h-10 text-blue-600 animate-spin" />
                      ) : (
                        <div className="bg-white p-3 rounded-xl shadow-sm">
                          <Upload className="w-8 h-8 text-blue-600" />
                        </div>
                      )}
                      <div>
                        <p className="text-base font-semibold text-slate-900">
                          {uploading ? 'Uploading files...' : 'Click to upload'}
                        </p>
                        <p className="text-sm text-slate-500 mt-1">
                          PDF, TXT, JSON • Multiple files supported
                        </p>
                      </div>
                    </div>
                  </div>
                </label>

                {/* Text Upload */}
                <div className="relative">
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    Or paste text directly
                  </label>
                  <textarea
                    className="w-full px-4 py-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none bg-white transition-shadow"
                    rows={4}
                    placeholder="Paste your content here and press Ctrl+Enter..."
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && e.ctrlKey) {
                        const text = e.currentTarget.value.trim();
                        if (text) {
                          handleTextUpload(text);
                          e.currentTarget.value = '';
                        }
                      }
                    }}
                  />
                  <div className="absolute bottom-3 right-3 text-xs text-slate-400 bg-white px-2 py-1 rounded">
                    Ctrl+Enter to upload
                  </div>
                </div>

                {/* Document List */}
                {documents.length > 0 && (
                  <div className="space-y-3 mt-6">
                    <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                      <FileText className="w-4 h-4" />
                      Uploaded Documents ({documents.length})
                    </h3>
                    <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                      {documents.map((doc) => (
                        <div key={doc.id} className={`flex items-center justify-between p-3 rounded-xl transition-all ${
                          doc.status === 'ready' 
                            ? 'bg-emerald-50 border border-emerald-200' 
                            : doc.status === 'error'
                            ? 'bg-red-50 border border-red-200'
                            : 'bg-blue-50 border border-blue-200'
                        }`}>
                          <div className="flex items-center gap-3 flex-1 min-w-0">
                            {getStatusIcon(doc.status)}
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-slate-900 truncate">{doc.name}</p>
                              <p className="text-xs text-slate-500 mt-0.5">
                                {formatFileSize(doc.size)}
                                {doc.status === 'ready' && doc.chunks != null && ` • ${doc.chunks} chunks`}
                                {doc.status === 'error' && doc.error && ` • ${doc.error}`}
                              </p>
                            </div>
                          </div>
                          <button 
                            onClick={() => removeDocument(doc.id)} 
                            className="p-1.5 hover:bg-white rounded-lg transition-colors flex-shrink-0 ml-2"
                          >
                            <X className="w-4 h-4 text-slate-400 hover:text-red-500" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {documents.length === 0 && (
                  <div className="text-center py-8">
                    <div className="inline-flex items-center justify-center w-16 h-16 bg-slate-100 rounded-full mb-3">
                      <FileText className="w-8 h-8 text-slate-400" />
                    </div>
                    <p className="text-sm text-slate-500">No documents uploaded yet</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Column - Query Interface */}
          <div className="lg:col-span-3 space-y-6">
            <div className="bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden">
              <div className="bg-gradient-to-r from-indigo-600 to-purple-600 px-6 py-4">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Sparkles className="w-5 h-5" />
                  Ask Questions
                </h2>
              </div>
              
              <div className="p-6 space-y-4">
                <div className="relative">
                  <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                  <input
                    type="text"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    placeholder="What would you like to know about your documents?"
                    className="w-full pl-12 pr-4 py-4 bg-slate-50 border-2 border-slate-200 rounded-xl text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                    disabled={isSearching}
                  />
                </div>
                
                <button
                  onClick={handleSearch}
                  disabled={!question.trim() || isSearching || documents.filter(d => d.status === 'ready').length === 0}
                  className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white py-4 px-6 rounded-xl font-semibold hover:from-indigo-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-xl disabled:shadow-none flex items-center justify-center gap-2"
                >
                  {isSearching ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Searching...
                    </>
                  ) : (
                    <>
                      <Search className="w-5 h-5" />
                      Ask Question
                    </>
                  )}
                </button>

                {documents.filter(d => d.status === 'ready').length === 0 && documents.length > 0 && (
                  <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl">
                    <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                    <div className="text-sm text-amber-800">
                      <p className="font-medium">Please wait for documents to finish uploading before asking questions.</p>
                    </div>
                  </div>
                )}

                {documents.length === 0 && (
                  <div className="flex items-start gap-3 p-4 bg-blue-50 border border-blue-200 rounded-xl">
                    <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                    <div className="text-sm text-blue-800">
                      <p className="font-medium">Upload some documents first to start asking questions.</p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Answer Section */}
            {(answer || sources.length > 0) && (
              <div className="bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden">
                <div className="bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-4">
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <CheckCircle className="w-5 h-5" />
                    Answer
                  </h3>
                </div>
                
                <div className="p-6">
                  {answer && (
                    <div className="mb-6">
                      <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">{answer}</p>
                    </div>
                  )}

                  {sources.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                        <FileText className="w-4 h-4" />
                        Sources ({sources.length})
                      </h4>
                      <div className="space-y-3">
                        {sources.map((source, idx) => (
                          <div key={idx} className="border border-slate-200 rounded-xl p-4 bg-slate-50 hover:bg-slate-100 transition-colors">
                            <div className="flex items-center gap-2 mb-2 flex-wrap">
                              <span className="text-xs font-bold text-white bg-gradient-to-r from-indigo-600 to-purple-600 px-2.5 py-1 rounded-lg">
                                [{idx + 1}]
                              </span>
                              <span className="text-sm font-semibold text-slate-900">
                                {source.filename || source.document_id}
                              </span>
                              <span className="text-slate-400">•</span>
                              <span className="text-xs font-mono text-slate-500 bg-white px-2 py-1 rounded">
                                chunk {source.chunk_index}
                              </span>
                            </div>
                            <p className="text-sm text-slate-600 leading-relaxed line-clamp-3">{source.content}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Backend Status Warning */}
        {isBackendHealthy === false && (
          <div className="mt-8 bg-red-50 border-2 border-red-200 rounded-2xl p-6 shadow-lg">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0">
                <div className="bg-red-100 p-2 rounded-xl">
                  <AlertCircle className="h-6 w-6 text-red-600" />
                </div>
              </div>
              <div className="flex-1">
                <h3 className="text-base font-bold text-red-900 mb-2">
                  Backend Connection Failed
                </h3>
                <p className="text-sm text-red-700 leading-relaxed">
                  Unable to connect to the backend server. Please ensure the backend is running on{' '}
                  <code className="bg-red-100 px-2 py-1 rounded font-mono text-xs">http://127.0.0.1:8000</code>
                </p>
              </div>
            </div>
          </div>
        )}
      </main>
      
      {/* Footer */}
      <footer className="bg-white/80 backdrop-blur-md border-t border-slate-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="text-center">
            <p className="text-sm text-slate-600">
              by <span className="font-semibold text-slate-900">Harshita Singh</span>
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;