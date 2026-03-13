"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import lmsService from "@/services/lmsService";
import { Button } from "@/components/ui/button";
import ContentViewer from "@/components/lms/student/ContentViewer";
import { Content, Course, Section } from "@/types";
import { ArrowLeft } from "lucide-react";

export default function StudentCourseDetailPage() {
  const params = useParams();
  const router = useRouter();
  const courseId = parseInt(params.courseId as string);
  
  const [course, setCourse] = useState<Course | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedSections, setExpandedSections] = useState<Set<number>>(new Set());
  const [sectionContents, setSectionContents] = useState<Record<number, Content[]>>({});
  const [showContentViewer, setShowContentViewer] = useState(false);
  const [selectedContent, setSelectedContent] = useState<Content | null>(null);

  useEffect(() => {
    loadCourse();
    loadSections();
  }, [courseId]);

  const loadCourse = async () => {
    try {
      const data = await lmsService.getCourse(courseId);
      setCourse(data?.data);
    } catch (error) {
      console.error("Error loading course:", error);
      alert("Không tìm thấy khóa học");
      router.push("/lms/student");
    }
  };

  const loadSections = async () => {
    try {
      const data = await lmsService.listSections(courseId);
      setSections(data?.data || []);
      setLoading(false);
    } catch (error) {
      console.error("Error loading sections:", error);
      setLoading(false);
    }
  };

  const loadSectionContent = async (sectionId: number) => {
    try {
      const data = await lmsService.listContent(sectionId);
      setSectionContents(prev => ({
        ...prev,
        [sectionId]: data?.data || []
      }));
    } catch (error) {
      console.error("Error loading content:", error);
    }
  };

  const toggleSection = (sectionId: number) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(sectionId)) {
      newExpanded.delete(sectionId);
    } else {
      newExpanded.add(sectionId);
      if (!sectionContents[sectionId]) {
        loadSectionContent(sectionId);
      }
    }
    setExpandedSections(newExpanded);
  };

  const getContentTypeIcon = (type: string) => {
    const icons: Record<string, string> = {
      TEXT: "📝",
      VIDEO: "🎥",
      DOCUMENT: "📄",
      IMAGE: "🖼️",
      QUIZ: "❓",
      FORUM: "💬",
      ANNOUNCEMENT: "📢"
    };
    return icons[type] || "📎";
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return "";
    const mb = bytes / (1024 * 1024);
    return mb < 1 ? `${(bytes / 1024).toFixed(1)} KB` : `${mb.toFixed(1)} MB`;
  };

  if (loading || !course) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="bg-white rounded-xl shadow-sm border p-6 mb-6">
        <div className="mb-4">
          <Button
            onClick={() => router.push("/lms/student")}
            variant="outline"
            size="sm"
            className="flex items-center gap-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Quay lại
          </Button>
        </div>
        
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
              course.status === "PUBLISHED" 
                ? "bg-green-100 text-green-800"
                : "bg-yellow-100 text-yellow-800"
            }`}>
              {course.status === "PUBLISHED" ? "Đã xuất bản" : "Nháp"}
            </span>
            {course.level && (
              <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-semibold">
                {course.level}
              </span>
            )}
            {course.category && (
              <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-xs font-semibold">
                {course.category}
              </span>
            )}
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">{course.title}</h1>
          <p className="text-gray-600">{course.description || "Chưa có mô tả"}</p>
        </div>
      </div>

      {/* Main Content */}
      <div className="bg-white rounded-xl shadow-sm border">
        <div className="p-6 border-b">
          <h3 className="text-lg font-semibold">Nội dung khóa học</h3>
        </div>

        <div className="p-6">
          {sections.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <p>Khóa học chưa có nội dung nào</p>
            </div>
          ) : (
            <div className="space-y-4">
              {sections.map((section, index) => (
                <div key={section.id} className="border rounded-lg overflow-hidden">
                  <div className="p-4 bg-gray-50 flex justify-between items-center cursor-pointer hover:bg-gray-100 transition-colors" onClick={() => toggleSection(section.id)}>
                    <div className="flex-1">
                      <h4 className="font-semibold">
                        Chương {index + 1}: {section.title}
                      </h4>
                      <p className="text-sm text-gray-600">{section.description || "Chưa có mô tả"}</p>
                    </div>
                    <Button
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleSection(section.id);
                      }}
                      className="px-3 py-1 text-sm bg-white border rounded hover:bg-gray-100"
                    >
                      {expandedSections.has(section.id) ? "Thu gọn" : "Xem nội dung"}
                    </Button>
                  </div>

                  {expandedSections.has(section.id) && (
                    <div className="p-4 bg-white border-t">
                      <h5 className="font-medium mb-3">Nội dung trong chương</h5>
                      {!sectionContents[section.id] || sectionContents[section.id].length === 0 ? (
                        <p className="text-gray-600 text-sm">Chưa có nội dung nào</p>
                      ) : (
                        <div className="space-y-2">
                          {sectionContents[section.id].map((content, idx) => (
                            <div key={content.id} className="p-3 bg-gray-50 rounded">
                              <div className="flex justify-between items-start">
                                <div className="flex-1">
                                  <p className="font-medium text-sm flex items-center gap-2">
                                    <span>{getContentTypeIcon(content.type)}</span>
                                    <span>{idx + 1}. {content.title}</span>
                                    <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded">
                                      {content.type}
                                    </span>
                                    {content.is_mandatory && (
                                      <span className="px-2 py-0.5 bg-orange-100 text-orange-700 text-xs rounded">
                                        Bắt buộc
                                      </span>
                                    )}
                                  </p>
                                  <p className="text-xs text-gray-600 mt-1">
                                    {content.description || "Chưa có mô tả"}
                                  </p>
                                  {content.metadata?.file_name && (
                                    <p className="text-xs text-gray-500 mt-1">
                                      📎 {content.metadata.file_name}
                                      {content.metadata.file_size && ` (${formatFileSize(content.metadata.file_size)})`}
                                    </p>
                                  )}
                                </div>
                                <Button
                                  onClick={() => {
                                    setSelectedContent(content);
                                    setShowContentViewer(true);
                                  }}
                                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 whitespace-nowrap"
                                >
                                  Xem
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Content Viewer Modal */}
      {showContentViewer && selectedContent && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b sticky top-0 bg-white z-10 flex justify-between items-center">
              <h2 className="text-xl font-bold">{selectedContent.title}</h2>
              <Button
                onClick={() => {
                  setShowContentViewer(false);
                  setSelectedContent(null);
                }}
                className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
              >
                Đóng
              </Button>
            </div>
            <div className="p-6">
              <ContentViewer content={selectedContent} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
