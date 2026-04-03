"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import FileUpload from "@/components/lms/teacher/FileUpload";
import YouTubeVideoUpload from "./YoutubeVideoUpload";
import QuizSettingsForm, { QuizSettings } from "./QuizSettingsForm";
import MarkdownEditor from "@/components/markdown/MarkdownEditor";
import lmsService from "@/services/lmsService";

import quizService from "@/services/quizService";
import { Content, ContentType, FileInfo } from "@/types";

interface ContentModalProps {
  sectionId: number;
  onClose: () => void;
  onSuccess: () => void;
  existingContents: Content[];
}

export default function ContentModal({ 
  sectionId, 
  onClose, 
  onSuccess, 
  existingContents 
}: ContentModalProps) {
  const [formData, setFormData] = useState({
    type: "TEXT" as ContentType,
    title: "",
    description: "",
    order_index: existingContents.length + 1,
    is_mandatory: false,
    metadata: {} as Record<string, any>,
  });

  // Quiz settings state
  const [quizSettings, setQuizSettings] = useState<QuizSettings>({
    title: "",
    description: "",
    instructions: "",
    time_limit_minutes: undefined,
    available_from: undefined,
    available_until: undefined,
    max_attempts: undefined,
    shuffle_questions: false,
    shuffle_answers: false,
    passing_score: undefined,
    total_points: 100,
    auto_grade: true,
    show_results_immediately: true,
    show_correct_answers: true,
    allow_review: true,
    show_feedback: true,
    is_published: true,
  });

  const [loading, setLoading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<FileInfo | null>(null);
  const [textContent, setTextContent] = useState("");
  const [videoUrl, setVideoUrl] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [uploadMethod, setUploadMethod] = useState<'youtube' | 'server' | 'url'>('youtube');

  const contentTypes = [
    { value: "TEXT", label: "Văn bản", needsUpload: false },
    { value: "VIDEO", label: "Video", needsUpload: true, fileType: "video" as const },
    { value: "DOCUMENT", label: "Tài liệu", needsUpload: true, fileType: "document" as const },
    { value: "IMAGE", label: "Hình ảnh", needsUpload: true, fileType: "image" as const },
    { value: "QUIZ", label: "Quiz", needsUpload: false },
    { value: "FORUM", label: "Diễn đàn", needsUpload: false },
    { value: "ANNOUNCEMENT", label: "Thông báo", needsUpload: false },
  ];

  const selectedContentType = contentTypes.find(ct => ct.value === formData.type);

  const handleFileUploaded = (fileInfo: FileInfo) => {
    setUploadedFile(fileInfo);
    
    // For YouTube uploads, the fileInfo will have video_url and embed_url
    const metadata: Record<string, any> = {
      file_path: fileInfo.file_path,
      file_name: fileInfo.file_name,
      file_size: fileInfo.file_size,
      file_id: fileInfo.file_id,
    };

    // If it's a YouTube upload
    if ((fileInfo as any).video_type === 'youtube') {
      metadata.video_type = 'youtube';
      metadata.video_url = (fileInfo as any).video_url;
      metadata.embed_url = (fileInfo as any).embed_url;
      metadata.thumbnail_url = (fileInfo as any).thumbnail_url;
    }

    setFormData({
      ...formData,
      metadata,
    });

    if (!formData.title) {
      setFormData(prev => ({
        ...prev,
        title: fileInfo.file_name,
        metadata,
      }));
    }
  };

  const handleTypeChange = (newType: string) => {
    setUploadedFile(null);
    setTextContent("");
    setVideoUrl("");
    setImageUrl("");
    
    // Reset upload method to YouTube for videos
    if (newType === "VIDEO") {
      setUploadMethod('youtube');
    }
    
    if (newType === "QUIZ") {
      setQuizSettings(prev => ({
        ...prev,
        title: formData.title,
        description: formData.description,
      }));
    }
    
    setFormData({
      ...formData,
      type: newType as ContentType,
      metadata: {},
    });
  };

  // Sync quiz title with content title
  const handleTitleChange = (title: string) => {
    setFormData({ ...formData, title });
    if (formData.type === "QUIZ") {
      setQuizSettings(prev => ({ ...prev, title }));
    }
  };

  // Sync quiz description with content description
  const handleDescriptionChange = (description: string) => {
    setFormData({ ...formData, description });
    if (formData.type === "QUIZ") {
      setQuizSettings(prev => ({ ...prev, description }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const metadata = { ...formData.metadata };

    if (formData.type === "TEXT") {
      metadata.content = textContent;
    } else if (formData.type === "VIDEO") {
      if (uploadedFile) {
        // Video already uploaded (YouTube or server)
        // Metadata is already set in handleFileUploaded
      } else if (videoUrl) {
        metadata.video_url = videoUrl;
        metadata.video_type = "external";
      } else {
        alert("Vui lòng upload video hoặc nhập URL video");
        return;
      }
    } else if (formData.type === "IMAGE") {
      if (uploadedFile) {
        metadata.image_type = "uploaded";
      } else if (imageUrl) {
        metadata.image_url = imageUrl;
        metadata.image_type = "external";
      } else {
        alert("Vui lòng upload ảnh hoặc nhập URL ảnh");
        return;
      }
    } else if (formData.type === "DOCUMENT") {
      if (!uploadedFile) {
        alert("Vui lòng upload tài liệu");
        return;
      }
      metadata.document_type = "uploaded";
    } else if (formData.type === "QUIZ") {
      // Store quiz settings in metadata
      metadata.quiz_settings = quizSettings;
    }

    try {
      setLoading(true);
      
      // Create content first
      const contentResponse = await lmsService.createContent(sectionId, {
        ...formData,
        metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
      });

      // If it's a quiz, create the quiz record
      if (formData.type === "QUIZ" && contentResponse.data) {
        const contentId = contentResponse.data.id;
        
        try {
          await quizService.createQuizWithContent(contentId, quizSettings);
        } catch (quizError: any) {
          console.error("Error creating quiz:", quizError);
          // Content already created, inform user about quiz creation failure
          alert("Nội dung đã được tạo nhưng có lỗi khi tạo quiz. Vui lòng thử lại từ trang chỉnh sửa.");
        }
      }

      alert("Tạo nội dung thành công!");
      onSuccess();
    } catch (error: any) {
      console.error("Error creating content:", error);
      alert(error.response?.data?.error || "Lỗi khi tạo nội dung");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b sticky top-0 bg-white z-10">
          <h2 className="text-xl font-bold">Thêm nội dung mới</h2>
        </div>
        <form onSubmit={handleSubmit} className="p-6">
          <div className="space-y-4">
            {/* Content Type */}
            <div>
              <label className="block text-sm font-medium mb-2">Loại nội dung *</label>
              <select
                value={formData.type}
                onChange={(e) => handleTypeChange(e.target.value)}
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                required
                disabled={loading}
              >
                {contentTypes.map(type => (
                  <option key={type.value} value={type.value}>{type.label}</option>
                ))}
              </select>
            </div>

            {/* Title */}
            <div>
              <label className="block text-sm font-medium mb-2">Tiêu đề *</label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => handleTitleChange(e.target.value)}
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="Nhập tiêu đề nội dung..."
                required
                disabled={loading}
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium mb-2">Mô tả</label>
              <textarea
                value={formData.description}
                onChange={(e) => handleDescriptionChange(e.target.value)}
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                rows={3}
                placeholder="Mô tả ngắn về nội dung này..."
                disabled={loading}
              />
            </div>

            {/* QUIZ Settings */}
            {formData.type === "QUIZ" && (
              <div className="border-t pt-4">
                <QuizSettingsForm
                  settings={quizSettings}
                  onChange={setQuizSettings}
                  disabled={loading}
                />
              </div>
            )}

            {/* VIDEO Upload Options */}
            {formData.type === "VIDEO" && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Phương thức upload video</label>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setUploadMethod('youtube')}
                      className={`flex-1 px-4 py-2 rounded-lg border-2 transition-colors ${
                        uploadMethod === 'youtube'
                          ? 'border-red-500 bg-red-50 text-red-700'
                          : 'border-gray-300 hover:border-red-300'
                      }`}
                      disabled={loading}
                    >
                      📺 YouTube
                    </button>
                    <button
                      type="button"
                      onClick={() => setUploadMethod('server')}
                      className={`flex-1 px-4 py-2 rounded-lg border-2 transition-colors ${
                        uploadMethod === 'server'
                          ? 'border-blue-500 bg-blue-50 text-blue-700'
                          : 'border-gray-300 hover:border-blue-300'
                      }`}
                      disabled={loading}
                    >
                      💾 Server
                    </button>
                    <button
                      type="button"
                      onClick={() => setUploadMethod('url')}
                      className={`flex-1 px-4 py-2 rounded-lg border-2 transition-colors ${
                        uploadMethod === 'url'
                          ? 'border-green-500 bg-green-50 text-green-700'
                          : 'border-gray-300 hover:border-green-300'
                      }`}
                      disabled={loading}
                    >
                      🔗 URL
                    </button>
                  </div>
                </div>

                {/* YouTube Upload */}
                {uploadMethod === 'youtube' && (
                  <YouTubeVideoUpload onFileUploaded={handleFileUploaded} disabled={loading} />
                )}

                {/* Server Upload */}
                {uploadMethod === 'server' && (
                  <div>
                    <label className="block text-sm font-medium mb-2">Upload video lên server</label>
                    <FileUpload
                      fileType="video"
                      onFileUploaded={handleFileUploaded}
                    />
                  </div>
                )}

                {/* URL Input */}
                {uploadMethod === 'url' && (
                  <div>
                    <label className="block text-sm font-medium mb-2">Nhập URL video</label>
                    <input
                      type="url"
                      value={videoUrl}
                      onChange={(e) => setVideoUrl(e.target.value)}
                      placeholder="https://youtube.com/watch?v=... hoặc https://example.com/video.mp4"
                      className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                      disabled={loading}
                    />
                  </div>
                )}

                {/* Upload Success */}
                {uploadedFile && (
                  <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                    <p className="text-sm font-medium text-green-700 mb-1">
                      ✅ Đã upload thành công
                    </p>
                    <p className="text-sm text-green-600">
                      📹 {uploadedFile.file_name}
                    </p>
                    {(uploadedFile as any).video_url && (
                      <p className="text-xs text-green-600 mt-1">
                        🔗 {(uploadedFile as any).video_url}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* File Upload for DOCUMENT, IMAGE */}
            {selectedContentType?.needsUpload && formData.type !== "VIDEO" && (
              <div>
                <label className="block text-sm font-medium mb-2">
                  Upload {selectedContentType.label} *
                </label>
                <FileUpload
                  fileType={selectedContentType.fileType || "document"}
                  onFileUploaded={handleFileUploaded}
                />
                {uploadedFile && (
                  <div className="mt-3 p-4 bg-green-50 border border-green-200 rounded-lg">
                    <p className="text-sm font-medium text-green-700 mb-1">
                      ✅ Đã upload thành công
                    </p>
                    <p className="text-sm text-green-600">
                      📄 {uploadedFile.file_name}
                    </p>
                    <p className="text-xs text-green-600">
                      📊 {(uploadedFile.file_size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                )}

                {/* Alternative: External URL for IMAGE */}
                {formData.type === "IMAGE" && (
                  <div className="mt-3">
                    <label className="block text-sm font-medium mb-2">
                      Hoặc nhập URL ảnh từ internet
                    </label>
                    <input
                      type="url"
                      value={imageUrl}
                      onChange={(e) => setImageUrl(e.target.value)}
                      placeholder="https://example.com/image.jpg"
                      className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                      disabled={!!uploadedFile || loading}
                    />
                  </div>
                )}
              </div>
            )}

            {/* Text Content for TEXT type */}
            {formData.type === "TEXT" && (
              <MarkdownEditor
                label="Nội dung văn bản *"
                value={textContent}
                onChange={setTextContent}
                placeholder="Nhập nội dung bài học..."
              />
            )}

            {/* Order Index and Mandatory */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Thứ tự</label>
                <input
                  type="number"
                  value={formData.order_index}
                  onChange={(e) => setFormData({ ...formData, order_index: parseInt(e.target.value) || 0 })}
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  min="0"
                  disabled={loading}
                />
              </div>
              <div className="flex items-center">
                <label className="flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.is_mandatory}
                    onChange={(e) => setFormData({ ...formData, is_mandatory: e.target.checked })}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    disabled={loading}
                  />
                  <span className="ml-2 text-sm font-medium">Nội dung bắt buộc</span>
                </label>
              </div>
            </div>

            {/* Info box */}
            {formData.type !== "QUIZ" && (
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-700">
                  <strong>💡 Lưu ý:</strong> {" "}
                  {formData.type === "TEXT" && "Nội dung văn bản sẽ được hiển thị trực tiếp trên trang."}
                  {formData.type === "VIDEO" && "Video có thể upload lên YouTube (khuyến nghị), server, hoặc nhúng từ URL."}
                  {formData.type === "DOCUMENT" && "Tài liệu (PDF, Word, Excel) sẽ có thể xem và tải xuống."}
                  {formData.type === "IMAGE" && "Hình ảnh sẽ được hiển thị trong bài học."}
                  {formData.type === "FORUM" && "Diễn đàn cho phép học viên thảo luận."}
                  {formData.type === "ANNOUNCEMENT" && "Thông báo sẽ được gửi đến tất cả học viên."}
                </p>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-3 mt-6 pt-4 border-t">
            <Button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
            >
              {loading ? "Đang tạo..." : "✓ Tạo nội dung"}
            </Button>
            <Button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:opacity-50"
            >
              Hủy
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}