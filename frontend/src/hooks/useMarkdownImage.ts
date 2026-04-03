import { useState } from 'react';
import { lmsApiClient } from '@/services/lmsApiClient';

export const useMarkdownImage = () => {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const uploadImage = async (file: File): Promise<string> => {
    try {
      setUploading(true);
      setError(null);

      // Validate file type
      if (!file.type.startsWith('image/')) {
        throw new Error('Vui lòng chọn file ảnh');
      }

      // Validate file size (e.g., max 10MB)
      if (file.size > 10 * 1024 * 1024) {
        throw new Error('Ảnh không được vượt quá 10MB');
      }

      // Create FormData
      const formData = new FormData();
      formData.append('file', file);
      formData.append('type', 'image');

      // Upload using lmsApiClient (wraps /lmsapiv1)
      const response = await lmsApiClient.post<{ data: { file_path: string } }>(
        '/files/upload',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );

      if (!response.data?.data?.file_path) {
        throw new Error('Upload thất bại, không nhận được đường dẫn file');
      }

      // The backend returns a file_path like "uploads/..."
      // We assume it can be accessed via /lmsapiv1/files/download or similar, 
      // but usually the app serves it through the lmsapi proxy.
      // According to the hint: /files/${data.data.file_path}
      return `/lmsapiv1/files/${response.data.data.file_path}`;
    } catch (err: any) {
      console.error('Markdown Image Upload Error:', err);
      const message = err.response?.data?.error || err.message || 'Lỗi upload ảnh';
      setError(message);
      throw new Error(message);
    } finally {
      setUploading(false);
    }
  };

  return { uploadImage, uploading, error };
};
