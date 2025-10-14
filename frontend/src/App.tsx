import React, { useState, useEffect } from 'react';
import { Upload, Search, FileText, X, Loader2, AlertCircle, CheckCircle } from 'lucide-react';
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

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Unthinkable KBSE</h1>
              <p className="text-gray-600 mt-1">Upload documents and ask questions</p>
            </div>
            <div className="flex items-center space-x-4">
              <div className={`flex items-center space-x-2 px-3 py-1 rounded-full text-sm ${
                isBackendHealthy === null 
                  ? 'bg-yellow-100 text-yellow-800' 
                  : isBackendHealthy 
                    ? 'bg-green-100 text-green-800' 
                    : 'bg-red-100 text-red-800'
              }`}>
                <div className={`w-2 h-2 rounded-full ${
                  isBackendHealthy === null 
                    ? 'bg-yellow-400' 
                    : isBackendHealthy 
                      ? 'bg-green-400' 
                      : 'bg-red-400'
                }`}></div>
                <span>
                  {isBackendHealthy === null 
                    ? 'Checking...' 
                    : isBackendHealthy 
                      ? 'Backend Online' 
                      : 'Backend Offline'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid lg:grid-cols-2 gap-8">
          {/* Left Column - Document Upload */}
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Upload Documents</h2>
              
              {/* File Upload */}
              <div className="mb-6">
                <label className="block">
                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 hover:border-blue-400 transition-colors cursor-pointer bg-white">
                    <input
                      type="file"
                      multiple
                      accept=".txt,.pdf,.json,application/json"
                      onChange={handleFileUpload}
                      className="hidden"
                      disabled={uploading}
                    />
                    <div className="flex flex-col items-center gap-2 text-center">
                      <Upload className="w-8 h-8 text-gray-400" />
                      <div>
                        <p className="text-sm font-medium text-gray-900">
                          {uploading ? 'Uploading...' : 'Click to upload documents'}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          Supports .txt, .pdf and .json files • Multiple files allowed
                        </p>
                      </div>
                    </div>
                  </div>
                </label>
              </div>

              {/* Text Upload */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Or paste text directly:
                </label>
                <textarea
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                  rows={4}
                  placeholder="Paste your text content here..."
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
                <p className="text-xs text-gray-500 mt-1">
                  Press Ctrl+Enter to upload text
                </p>
              </div>

              {/* Document List */}
              {documents.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-medium text-gray-700">Uploaded Documents</h3>
                  {documents.map((doc) => (
                    <div key={doc.id} className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-lg">
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        {getStatusIcon(doc.status)}
                        <FileText className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 truncate">{doc.name}</p>
                          <p className="text-xs text-gray-500">
                            {formatFileSize(doc.size)}
                            {doc.status === 'ready' && doc.chunks != null && ` • ${doc.chunks} chunks`}
                            {doc.status === 'error' && doc.error && ` • ${doc.error}`}
                          </p>
                        </div>
                      </div>
                      <button 
                        onClick={() => removeDocument(doc.id)} 
                        className="p-1 hover:bg-gray-100 rounded transition-colors flex-shrink-0"
                      >
                        <X className="w-4 h-4 text-gray-400" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Column - Query Interface */}
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Ask Questions</h2>
              
              <div className="space-y-4">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="text"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    placeholder="Ask a question about your documents..."
                    className="w-full pl-10 pr-4 py-3 bg-white border border-gray-300 rounded-lg text-gray-900 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    disabled={isSearching}
                  />
                </div>
                
                <button
                  onClick={handleSearch}
                  disabled={!question.trim() || isSearching || documents.filter(d => d.status === 'ready').length === 0}
                  className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                  {isSearching ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Searching...
                    </>
                  ) : (
                    <>
                      <Search className="w-4 h-4" />
                      Ask Question
                    </>
                  )}
                </button>

                {documents.filter(d => d.status === 'ready').length === 0 && documents.length > 0 && (
                  <p className="text-sm text-yellow-600 bg-yellow-50 p-3 rounded-lg">
                    Please wait for documents to finish uploading before asking questions.
                  </p>
                )}

                {documents.length === 0 && (
                  <p className="text-sm text-gray-500 bg-gray-50 p-3 rounded-lg">
                    Upload some documents first to start asking questions.
                  </p>
                )}
              </div>
            </div>

            {/* Answer Section */}
            {(answer || sources.length > 0) && (
              <div className="bg-white border border-gray-200 rounded-lg p-6">
                <div className="mb-4">
                  <h3 className="text-lg font-semibold text-gray-900">Answer</h3>
                </div>
                
                {answer && (
                  <div className="mb-6">
                    <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">{answer}</p>
                  </div>
                )}

                {sources.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-900 mb-3">Sources ({sources.length})</h4>
                    <div className="space-y-3">
                      {sources.map((source, idx) => (
                        <div key={idx} className="text-sm text-gray-600 border border-gray-200 rounded p-3 bg-gray-50">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-gray-900 font-mono text-xs bg-white px-2 py-1 rounded">
                              [{idx + 1}]
                            </span>
                            <span className="text-gray-900 font-medium">
                              {source.filename || source.document_id}
                            </span>
                            <span className="text-gray-500">•</span>
                            <span className="font-mono text-xs">chunk {source.chunk_index}</span>
                          </div>
                          <p className="text-gray-700 line-clamp-3">{source.content}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Backend Status Warning */}
        {isBackendHealthy === false && (
          <div className="mt-8 bg-red-50 border border-red-200 rounded-md p-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <AlertCircle className="h-5 w-5 text-red-400" />
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-red-800">
                  Backend Connection Failed
                </h3>
                <div className="mt-2 text-sm text-red-700">
                  <p>
                    Unable to connect to the backend server. Please ensure the backend is running on{' '}
                    <code className="bg-red-100 px-1 rounded">http://127.0.0.1:8000</code>
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
      
      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="text-center text-sm text-gray-500">
            by Harshita Singh
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;