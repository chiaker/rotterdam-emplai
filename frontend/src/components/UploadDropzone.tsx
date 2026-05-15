import { useCallback, useState } from 'react';
import { Upload, X, File } from 'lucide-react';

interface UploadDropzoneProps {
  onUpload: (file: File) => Promise<void>;
  accept?: string;
  label?: string;
}

export function UploadDropzone({ 
  onUpload, 
  accept = '.txt,.pdf,.docx',
  label = 'Перетащите файл сюда или нажмите для выбора'
}: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    setError(null);

    const file = e.dataTransfer.files[0];
    if (file) {
      setSelectedFile(file);
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    
    setIsUploading(true);
    setError(null);
    
    try {
      await onUpload(selectedFile);
      setSelectedFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки файла');
    } finally {
      setIsUploading(false);
    }
  };

  const handleCancel = () => {
    setSelectedFile(null);
    setError(null);
  };

  return (
    <div className="w-full">
      {!selectedFile ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`
            border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
            ${isDragging 
              ? 'border-primary-500 bg-primary-50' 
              : 'border-gray-300 hover:border-primary-400 hover:bg-gray-50'
            }
          `}
        >
          <input
            type="file"
            accept={accept}
            onChange={handleFileSelect}
            className="hidden"
            id="file-upload"
          />
          <label htmlFor="file-upload" className="cursor-pointer">
            <Upload className={`w-12 h-12 mx-auto mb-4 ${isDragging ? 'text-primary-500' : 'text-gray-400'}`} />
            <p className="text-gray-600">{label}</p>
            <p className="text-sm text-gray-500 mt-2">Поддерживаемые форматы: TXT, PDF, DOCX</p>
          </label>
        </div>
      ) : (
        <div className="border rounded-lg p-4 bg-gray-50">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <File className="w-8 h-8 text-gray-400 mr-3" />
              <div>
                <p className="font-medium text-gray-900">{selectedFile.name}</p>
                <p className="text-sm text-gray-500">
                  {(selectedFile.size / 1024).toFixed(1)} КБ
                </p>
              </div>
            </div>
            <button
              onClick={handleCancel}
              className="p-2 text-gray-400 hover:text-gray-600"
              disabled={isUploading}
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          
          {error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}
          
          <button
            onClick={handleUpload}
            disabled={isUploading}
            className="mt-4 w-full py-2 px-4 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            {isUploading ? 'Загрузка...' : 'Загрузить'}
          </button>
        </div>
      )}
    </div>
  );
}
